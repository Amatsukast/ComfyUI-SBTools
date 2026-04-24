# ComfyUI-SBTools - Color Balance Match Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import torch
import numpy as np
import kornia

from .match_utils import (
    validate_batch_sizes,
    extract_rgb,
    extract_alpha,
    combine_rgba,
    apply_strength,
    compute_masked_median_lab_ab,
    compute_masked_mean_cov,
)


class SBTools_MatchColorBalance:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "target_image": "Image to be color balance matched (RGB or RGBA).",
            "target_alpha": "Optional alpha channel for target image (overrides target_image 4th channel if present).",
            "reference_image": "Reference image for color balance (RGB only, alpha channel is ignored).",
            "reference_alpha": "Optional alpha channel for reference image (overrides reference_image 4th channel if present).",
            "method": "Matching algorithm (Shift: median-based uniform shift, MKL: optimal transport with covariance).",
            "strength": "Color balance matching strength (0=no change, 1=full match, >1=overcorrection).",
            "channel_mode": "Which Lab channels to shift (Both: temperature+tint, Temperature Only: warmth/coolness, Tint Only: green/magenta).",
        }
        return {
            "required": {
                "target_image": ("IMAGE", {"tooltip": tooltips["target_image"]}),
                "method": (
                    ["MKL", "Shift"],
                    {"default": "MKL", "tooltip": tooltips["method"]},
                ),
                "channel_mode": (
                    ["Both", "Temperature Only", "Tint Only"],
                    {"default": "Both", "tooltip": tooltips["channel_mode"]},
                ),
                "strength": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 5.0,
                        "step": 0.05,
                        "display": "number",
                        "tooltip": tooltips["strength"],
                    },
                ),
            },
            "optional": {
                "target_alpha": ("MASK", {"tooltip": tooltips["target_alpha"]}),
                "reference_image": ("IMAGE", {"tooltip": tooltips["reference_image"]}),
                "reference_alpha": ("MASK", {"tooltip": tooltips["reference_alpha"]}),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK")
    RETURN_NAMES = ("IMAGE", "RGB", "ALPHA")
    FUNCTION = "match_color_balance"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    def match_color_balance(
        self,
        target_image,
        method,
        channel_mode,
        strength,
        target_alpha=None,
        reference_image=None,
        reference_alpha=None,
    ):
        """
        Match color balance by shifting Lab a/b channels.

        Args:
            target_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            reference_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            method: "Shift" or "MKL"
            channel_mode: str, which channels to shift
            strength: float, matching strength

        Returns:
            tuple: (matched_image, rgb_output, alpha_mask)
        """
        # Validate reference image is provided
        if reference_image is None:
            raise ValueError("reference_image is required for color balance matching.")

        # Validate batch sizes
        validate_batch_sizes(target_image, target_alpha)

        # Extract RGB channels only (ignore alpha if present)
        target_rgb = extract_rgb(target_image)
        reference_rgb = extract_rgb(reference_image)

        # Extract alpha from target and reference (priority: explicit input > 4th channel > fully opaque)
        target_alpha_final = extract_alpha(target_image, target_alpha)
        reference_alpha_final = extract_alpha(reference_image, reference_alpha)

        # Skip processing if strength is 0
        if strength == 0:
            output_image = combine_rgba(target_rgb, target_alpha_final)
            return (output_image, target_rgb, target_alpha_final)

        # Convert target to Lab
        target_bchw = target_rgb.permute(0, 3, 1, 2)  # (B, 3, H, W)
        target_lab = kornia.color.rgb_to_lab(target_bchw)

        # Extract L, a, b channels
        target_L = target_lab[:, 0:1, :, :]  # (B, 1, H, W)
        target_ab = target_lab[:, 1:3, :, :]  # (B, 2, H, W)

        if method == "Shift":
            # Original median-based shift method
            matched_ab = self._shift_method(
                target_rgb,
                target_alpha_final,
                reference_rgb,
                reference_alpha_final,
                target_ab,
                channel_mode,
                strength,
            )
        else:  # MKL
            # MKL-based optimal transport method
            matched_ab = self._mkl_method(
                target_rgb,
                target_alpha_final,
                reference_rgb,
                reference_alpha_final,
                target_ab,
                channel_mode,
                strength,
            )

        # Reconstruct LAB image (original L + matched ab)
        matched_lab = torch.cat([target_L, matched_ab], dim=1)  # (B, 3, H, W)

        # Convert back to RGB
        matched_rgb = kornia.color.lab_to_rgb(matched_lab)

        # Convert back to (B, H, W, C) format
        output_rgb = matched_rgb.permute(0, 2, 3, 1).clamp(0, 1)

        # Combine RGB with alpha
        output_image = combine_rgba(output_rgb, target_alpha_final)

        return (output_image, output_rgb, target_alpha_final)

    def _shift_method(
        self,
        target_rgb,
        target_alpha,
        reference_rgb,
        reference_alpha,
        target_ab,
        channel_mode,
        strength,
    ):
        """Median-based uniform shift method."""
        # Compute median of Lab a/b channels with alpha masking
        target_median = compute_masked_median_lab_ab(target_rgb, target_alpha)
        reference_median = compute_masked_median_lab_ab(reference_rgb, reference_alpha)

        # Handle reference batch broadcasting
        if reference_median.shape[0] == 1 and target_median.shape[0] > 1:
            reference_median = reference_median.expand(
                target_median.shape[0], -1, -1, -1
            )

        # Compute shift (difference in median)
        ab_shift = reference_median - target_median  # (B, 2, 1, 1)

        # Apply channel mode filter
        if channel_mode == "Temperature Only":
            ab_shift[:, 0, :, :] = 0  # a channel = 0
        elif channel_mode == "Tint Only":
            ab_shift[:, 1, :, :] = 0  # b channel = 0

        # Apply shift to a/b channels
        matched_ab = target_ab + ab_shift

        # Apply strength
        matched_ab = apply_strength(target_ab, matched_ab, strength)

        return matched_ab

    def _mkl_method(
        self,
        target_rgb,
        target_alpha,
        reference_rgb,
        reference_alpha,
        target_ab,
        channel_mode,
        strength,
    ):
        """MKL-based optimal transport method for Lab a/b channels."""
        batch_size = target_rgb.shape[0]
        ref_batch = reference_rgb.shape[0]
        results = []

        # Convert target/reference RGB to Lab for statistics computation
        target_bchw = target_rgb.permute(0, 3, 1, 2)
        reference_bchw = reference_rgb.permute(0, 3, 1, 2)

        target_lab_full = kornia.color.rgb_to_lab(target_bchw)
        reference_lab_full = kornia.color.rgb_to_lab(reference_bchw)

        # Extract a/b channels for statistics: (B, 2, H, W) -> (B, H, W, 2)
        target_ab_stat = target_lab_full[:, 1:3, :, :].permute(0, 2, 3, 1)
        reference_ab_stat = reference_lab_full[:, 1:3, :, :].permute(0, 2, 3, 1)

        for i in range(batch_size):
            ref_idx = min(i, ref_batch - 1)

            # Compute masked mean and covariance for a/b channels (2D)
            target_batch = target_ab_stat[i : i + 1]  # (1, H, W, 2)
            target_mask_batch = target_alpha[i : i + 1]  # (1, H, W)
            reference_batch = reference_ab_stat[ref_idx : ref_idx + 1]  # (1, H, W, 2)
            reference_mask_batch = reference_alpha[ref_idx : ref_idx + 1]  # (1, H, W)

            mu_target, cov_target = compute_masked_mean_cov(
                target_batch, target_mask_batch
            )
            mu_ref, cov_ref = compute_masked_mean_cov(
                reference_batch, reference_mask_batch
            )

            # Remove batch dimension: (1, 2, 1) -> (2, 1)
            mu_target = mu_target[0]  # (2, 1)
            mu_ref = mu_ref[0]  # (2, 1)
            cov_target = cov_target[0]  # (2, 2)
            cov_ref = cov_ref[0]  # (2, 2)

            # Apply channel mode filter to covariance
            if channel_mode == "Temperature Only":
                # Only process b channel (index 1), zero out a channel
                mu_target[0] = 0
                mu_ref[0] = 0
                cov_target[0, :] = 0
                cov_target[:, 0] = 0
                cov_target[0, 0] = 1  # Identity for a channel
                cov_ref[0, :] = 0
                cov_ref[:, 0] = 0
                cov_ref[0, 0] = 1
            elif channel_mode == "Tint Only":
                # Only process a channel (index 0), zero out b channel
                mu_target[1] = 0
                mu_ref[1] = 0
                cov_target[1, :] = 0
                cov_target[:, 1] = 0
                cov_target[1, 1] = 1  # Identity for b channel
                cov_ref[1, :] = 0
                cov_ref[:, 1] = 0
                cov_ref[1, 1] = 1

            # Convert to numpy for MKL computation
            mu_target_np = mu_target.cpu().numpy()
            mu_ref_np = mu_ref.cpu().numpy()
            cov_target_np = cov_target.cpu().numpy()
            cov_ref_np = cov_ref.cpu().numpy()

            # Compute transfer matrix using MKL method
            transfer_mat = self._compute_mkl_transfer(cov_target_np, cov_ref_np)

            # Reshape target_ab to (2, N)
            target_ab_i = target_ab[i]  # (2, H, W)
            H, W = target_ab_i.shape[1], target_ab_i.shape[2]
            target_ab_flat = target_ab_i.reshape(2, -1).cpu().numpy()  # (2, N)

            # Apply color transfer: T @ (x - mu_target) + mu_ref
            matched_ab_flat = transfer_mat @ (target_ab_flat - mu_target_np) + mu_ref_np

            # Reshape back to (2, H, W)
            matched_ab_i = matched_ab_flat.reshape(2, H, W)

            # Convert back to torch
            matched_ab_tensor = (
                torch.from_numpy(matched_ab_i).to(target_ab.dtype).to(target_ab.device)
            )

            # Apply strength
            matched_ab_tensor = apply_strength(
                target_ab[i], matched_ab_tensor, strength
            )

            results.append(matched_ab_tensor)

        return torch.stack(results, dim=0)

    def _compute_mkl_transfer(self, cov_target, cov_ref):
        """Compute MKL transfer matrix for 2x2 covariance matrices."""
        # Eigenvalue decomposition of target covariance
        eig_val, eig_vec = np.linalg.eig(cov_target)

        # Clip negative eigenvalues for numerical stability
        eig_val = np.maximum(eig_val, 0)

        # Sort eigenvalues in descending order
        val_mat = np.diag(np.sqrt(eig_val[::-1]))
        vec_mat = eig_vec[:, ::-1]

        # Compute inverse with numerical stability
        inv_mat = np.diag(1.0 / (np.diag(val_mat) + 1e-6))

        # Compute intermediate matrix
        mat_c = val_mat @ vec_mat.T @ cov_ref @ vec_mat @ val_mat

        # Eigenvalue decomposition of intermediate matrix
        eig_val_c, eig_vec_c = np.linalg.eig(mat_c)

        # Clip negative eigenvalues
        eig_val_c = np.maximum(eig_val_c, 0)
        val_c = np.diag(np.sqrt(eig_val_c))

        # Compute transfer matrix
        transfer_mat = (
            vec_mat @ inv_mat @ eig_vec_c @ val_c @ eig_vec_c.T @ inv_mat @ vec_mat.T
        )

        return transfer_mat


NODE_CLASS_MAPPINGS = {"SBTools_MatchColorBalance": SBTools_MatchColorBalance}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SBTools_MatchColorBalance": "Match Color Balance (SBTools)"
}
