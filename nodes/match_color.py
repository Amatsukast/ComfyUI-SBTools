# ComfyUI-SBTools - Color Match Node
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
    compute_masked_mean_cov,
)
from .guided_filter import GuidedFilter2d


class SBTools_MatchColor:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "target_image": "Image to be color matched (RGB or RGBA).",
            "target_alpha": "Optional alpha channel for target image (overrides target_image 4th channel if present).",
            "reference_image": "Reference image for color statistics (RGB only, alpha channel is ignored).",
            "reference_alpha": "Optional alpha channel for reference image (overrides reference_image 4th channel if present).",
            "color_space": "Color space for MKL matching (Lab: perceptually uniform, RGB: brightness-color coupling, Adaptive: automatic blend of RGB+Lab for best quality).",
            "strength": "Color matching strength (0=no change, 1=full match, >1=overcorrection).",
        }
        return {
            "required": {
                "target_image": ("IMAGE", {"tooltip": tooltips["target_image"]}),
                "color_space": (
                    ["Lab", "RGB", "Adaptive"],
                    {"default": "Lab", "tooltip": tooltips["color_space"]},
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
    FUNCTION = "color_match"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    def color_match(
        self,
        target_image,
        color_space,
        strength,
        target_alpha=None,
        reference_image=None,
        reference_alpha=None,
    ):
        """
        Apply MKL (Monge-Kantorovich Linearization) color matching.

        Args:
            target_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            reference_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            color_space: "Lab" or "RGB"
            strength: float, matching strength

        Returns:
            tuple: (matched_image, rgb_output, alpha_mask)
        """
        # Validate reference image is provided
        if reference_image is None:
            raise ValueError("reference_image is required for color matching.")

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

        # Adaptive mode: compute both RGB and Lab, then blend
        if color_space == "Adaptive":
            output_rgb = self._adaptive_blend(
                target_rgb,
                target_alpha_final,
                reference_rgb,
                reference_alpha_final,
                strength,
            )
        else:
            # Standard MKL processing
            batch_size = target_image.shape[0]
            ref_batch = reference_rgb.shape[0]
            results = []

            # MKL uses numpy per-image processing with masked statistics
            for i in range(batch_size):
                # Select reference (broadcast if ref_batch=1)
                ref_idx = min(i, ref_batch - 1)

                target = target_rgb[i]  # (H, W, 3) tensor
                target_mask = target_alpha_final[i]  # (H, W) tensor
                reference = reference_rgb[ref_idx]  # (H, W, 3) tensor
                reference_mask = reference_alpha_final[ref_idx]  # (H, W) tensor

                # Apply MKL color matching with alpha masking
                matched = self._mkl_color_match(
                    target,
                    target_mask,
                    reference,
                    reference_mask,
                    strength,
                    color_space,
                )

                results.append(matched)

            # Stack results
            output_rgb = torch.stack(results, dim=0).to(torch.float32)

        output_rgb = output_rgb.clamp(0, 1)

        # Combine RGB with alpha
        output_image = combine_rgba(output_rgb, target_alpha_final)

        return (output_image, output_rgb, target_alpha_final)

    def _mkl_color_match(
        self, target, target_mask, reference, reference_mask, strength, color_space
    ):
        """
        MKL algorithm implementation based on optimal transport theory with alpha masking.

        Args:
            target: torch tensor (H, W, 3) with values 0.0-1.0
            target_mask: torch tensor (H, W) alpha values
            reference: torch tensor (H, W, 3) with values 0.0-1.0
            reference_mask: torch tensor (H, W) alpha values
            strength: float, matching strength
            color_space: "Lab" or "RGB"

        Returns:
            torch tensor: color matched image (H, W, 3)
        """
        # Convert to Lab space if needed
        if color_space == "Lab":
            # RGB -> Lab: (H, W, 3) -> (1, 3, H, W) -> Lab -> (H, W, 3)
            target_bchw = target.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)
            reference_bchw = reference.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)

            target_lab = kornia.color.rgb_to_lab(target_bchw)
            reference_lab = kornia.color.rgb_to_lab(reference_bchw)

            target_space = target_lab.squeeze(0).permute(1, 2, 0)  # (H, W, 3)
            reference_space = reference_lab.squeeze(0).permute(1, 2, 0)  # (H, W, 3)
        else:
            target_space = target
            reference_space = reference

        # Compute masked mean and covariance
        # Add batch dimension for compute_masked_mean_cov
        target_batch = target_space.unsqueeze(0)  # (1, H, W, 3)
        target_mask_batch = target_mask.unsqueeze(0)  # (1, H, W)
        reference_batch = reference_space.unsqueeze(0)  # (1, H, W, 3)
        reference_mask_batch = reference_mask.unsqueeze(0)  # (1, H, W)

        mu_target, cov_target = compute_masked_mean_cov(target_batch, target_mask_batch)
        mu_ref, cov_ref = compute_masked_mean_cov(reference_batch, reference_mask_batch)

        # Remove batch dimension: (1, 3, 1) -> (3, 1)
        mu_target = mu_target[0]  # (3, 1)
        mu_ref = mu_ref[0]  # (3, 1)
        cov_target = cov_target[0]  # (3, 3)
        cov_ref = cov_ref[0]  # (3, 3)

        # Convert to numpy for MKL computation
        mu_target_np = mu_target.cpu().numpy()
        mu_ref_np = mu_ref.cpu().numpy()
        cov_target_np = cov_target.cpu().numpy()
        cov_ref_np = cov_ref.cpu().numpy()

        # Compute transfer matrix using MKL method
        transfer_mat = self._compute_mkl_transfer(cov_target_np, cov_ref_np)

        # Reshape target to (3, N)
        target_np = target_space.cpu().numpy()  # (H, W, 3)
        target_flat = target_np.reshape(-1, 3).T  # (3, N)

        # Apply color transfer: T @ (x - mu_target) + mu_ref
        matched_flat = transfer_mat @ (target_flat - mu_target_np) + mu_ref_np

        # Reshape back to image
        matched_np = matched_flat.T.reshape(target_np.shape)

        # Convert back to torch
        matched_space = torch.from_numpy(matched_np).to(target.dtype).to(target.device)

        # Convert back to RGB if we were in Lab space
        if color_space == "Lab":
            # Lab -> RGB: (H, W, 3) -> (1, 3, H, W) -> RGB -> (H, W, 3)
            matched_bchw = matched_space.unsqueeze(0).permute(
                0, 3, 1, 2
            )  # (1, 3, H, W)
            matched_rgb = kornia.color.lab_to_rgb(matched_bchw)
            matched = matched_rgb.squeeze(0).permute(1, 2, 0)  # (H, W, 3)
        else:
            matched = matched_space

        # Blend with original based on strength
        matched = apply_strength(target, matched, strength)

        return matched

    def _compute_mkl_transfer(self, cov_target, cov_ref):
        """
        Compute MKL transfer matrix.

        Based on: mvgd_matcher.py mkl_solver()
        Reference: Monge-Kantorovich Linearization for optimal transport

        Args:
            cov_target: (3, 3) covariance matrix of target
            cov_ref: (3, 3) covariance matrix of reference

        Returns:
            numpy array: (3, 3) transfer matrix
        """
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

    def _adaptive_blend(
        self, target_rgb, target_alpha, reference_rgb, reference_alpha, strength
    ):
        """
        Adaptive blending of RGB-MKL and Lab-MKL results.

        Args:
            target_rgb: (B, H, W, 3) tensor
            target_alpha: (B, H, W) tensor
            reference_rgb: (B, H, W, 3) tensor
            reference_alpha: (B, H, W) tensor
            strength: float

        Returns:
            (B, H, W, 3) tensor, blended result
        """
        batch_size = target_rgb.shape[0]
        ref_batch = reference_rgb.shape[0]
        results = []

        for i in range(batch_size):
            ref_idx = min(i, ref_batch - 1)

            target = target_rgb[i]  # (H, W, 3)
            target_mask = target_alpha[i]  # (H, W)
            reference = reference_rgb[ref_idx]  # (H, W, 3)
            reference_mask = reference_alpha[ref_idx]  # (H, W)

            # Compute both RGB-MKL and Lab-MKL
            rgb_result = self._mkl_color_match(
                target, target_mask, reference, reference_mask, strength, "RGB"
            )
            lab_result = self._mkl_color_match(
                target, target_mask, reference, reference_mask, strength, "Lab"
            )

            # Compute adaptive weight map
            weight_lab = self._compute_adaptive_weight(
                target, reference, rgb_result, lab_result
            )  # (H, W)

            # Apply Guided Filter for edge-preserving smoothing
            weight_smooth = self._apply_guided_filter(
                target, weight_lab
            )  # (H, W) or (1, 1, H, W)

            # Ensure weight_smooth is (H, W)
            if weight_smooth.ndim == 4:
                weight_smooth = weight_smooth.squeeze(0).squeeze(0)

            # Blend results (Luminance-only blending)
            # Convert results to Lab space
            rgb_result_bchw = rgb_result.unsqueeze(0).permute(
                0, 3, 1, 2
            )  # (1, 3, H, W)
            lab_result_bchw = lab_result.unsqueeze(0).permute(
                0, 3, 1, 2
            )  # (1, 3, H, W)

            rgb_result_lab = kornia.color.rgb_to_lab(rgb_result_bchw)  # (1, 3, H, W)
            lab_result_lab = kornia.color.rgb_to_lab(lab_result_bchw)  # (1, 3, H, W)

            # Blend L channel only, keep a/b from RGB-MKL
            weight_bchw = weight_smooth.unsqueeze(0).unsqueeze(0)  # (1, 1, H, W)

            L_rgb = rgb_result_lab[:, 0:1, :, :]  # (1, 1, H, W)
            L_lab = lab_result_lab[:, 0:1, :, :]  # (1, 1, H, W)
            ab_rgb = rgb_result_lab[:, 1:3, :, :]  # (1, 2, H, W) - keep RGB color

            # Blend luminance
            L_blended = L_rgb * (1 - weight_bchw) + L_lab * weight_bchw

            # Reconstruct Lab with blended L and RGB's a/b
            blended_lab = torch.cat([L_blended, ab_rgb], dim=1)  # (1, 3, H, W)

            # Convert back to RGB
            blended_rgb = kornia.color.lab_to_rgb(blended_lab)  # (1, 3, H, W)
            blended = blended_rgb.squeeze(0).permute(1, 2, 0)  # (H, W, 3)

            results.append(blended)

        return torch.stack(results, dim=0).to(torch.float32)

    def _compute_adaptive_weight(
        self, target_original, reference_original, rgb_result, lab_result
    ):
        """
        Compute adaptive weight map using single metric: shadow crush detection.

        Design philosophy (simplified):
        - Default: RGB-biased (0.1 = Lab 10%, RGB 90%)
        - RGB is superior for color transfer in all cases
        - Lab is used ONLY to protect shadow crush in RGB results
        - Single continuous metric to avoid cliff effects and flickering

        Args:
            target_original: (H, W, 3) tensor, original target image
            reference_original: (H, W, 3) tensor, original reference image
            rgb_result: (H, W, 3) tensor, RGB-MKL result
            lab_result: (H, W, 3) tensor, Lab-MKL result

        Returns:
            (H, W) tensor, weight for Lab result (0-1)
        """
        # Convert to BCHW for kornia
        target_bchw = target_original.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)
        rgb_bchw = rgb_result.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)
        lab_bchw = lab_result.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)

        # Convert to Lab space for luminance analysis
        target_lab = kornia.color.rgb_to_lab(target_bchw)  # (1, 3, H, W)
        rgb_result_lab = kornia.color.rgb_to_lab(rgb_bchw)  # (1, 3, H, W)
        lab_result_lab = kornia.color.rgb_to_lab(lab_bchw)  # (1, 3, H, W)

        target_L = target_lab[:, 0, :, :]  # (1, H, W)
        rgb_result_L = rgb_result_lab[:, 0, :, :]  # (1, H, W)
        lab_result_L = lab_result_lab[:, 0, :, :]  # (1, H, W)

        # Base weight: Strong RGB-biased (Lab 10%)
        weight_lab = torch.full_like(target_L, 0.1)  # (1, H, W)

        # ============================================================
        # Single Metric: Shadow crush detection (continuous, per-pixel)
        # ============================================================
        # RGB結果で暗部が潰れている部分を検出
        # Continuous: 暗部の度合いに応じて連続的に増加
        shadow_threshold = 15.0  # Lab L value
        shadow_crush = torch.clamp(
            (shadow_threshold - rgb_result_L) / shadow_threshold, 0, 1
        )
        # rgb_result_L=0 -> 1.0 (完全に潰れている)
        # rgb_result_L=15 -> 0.0 (問題なし)

        # ターゲットの元の暗部と比較
        target_shadow = torch.clamp(
            (shadow_threshold - target_L) / shadow_threshold, 0, 1
        )

        # RGBで異常に暗くなった部分のみペナルティ（係数を2.0に増加）
        shadow_penalty = torch.clamp((shadow_crush - target_shadow) * 2.0, 0, 0.9)
        weight_lab = weight_lab + shadow_penalty.squeeze(0)  # (H, W)

        # ============================================================
        # Final clamping
        # ============================================================
        weight_lab = weight_lab.clamp(0, 1)

        # Debug info (detailed analysis)
        print(f"\n[Adaptive Debug (Detailed)]")
        print(f"  === Luminance Statistics ===")
        print(
            f"  Target L    : min={target_L.min():.1f}, mean={target_L.mean():.1f}, max={target_L.max():.1f}, std={target_L.std():.1f}"
        )
        print(
            f"  RGB result L: min={rgb_result_L.min():.1f}, mean={rgb_result_L.mean():.1f}, max={rgb_result_L.max():.1f}, std={rgb_result_L.std():.1f}"
        )
        print(
            f"  Lab result L: min={lab_result_L.min():.1f}, mean={lab_result_L.mean():.1f}, max={lab_result_L.max():.1f}, std={lab_result_L.std():.1f}"
        )

        print(f"\n  === Shadow Detection ===")
        print(f"  shadow_penalty mean: {shadow_penalty.mean():.3f}")
        print(f"  shadow_penalty max : {shadow_penalty.max():.3f}")
        pixels_affected = (shadow_penalty > 0.01).sum().item()
        total_pixels = shadow_penalty.numel()
        print(
            f"  Pixels affected: {pixels_affected}/{total_pixels} ({100*pixels_affected/total_pixels:.1f}%)"
        )

        print(f"\n  === Worst Case Pixel ===")
        worst_idx = shadow_penalty.argmax()
        W_size = shadow_penalty.shape[2]
        worst_y = (worst_idx // W_size).item()
        worst_x = (worst_idx % W_size).item()
        print(f"  Position: ({worst_y}, {worst_x})")
        print(f"  target_L: {target_L[0, worst_y, worst_x].item():.1f}")
        print(f"  rgb_result_L: {rgb_result_L[0, worst_y, worst_x].item():.1f}")
        print(f"  lab_result_L: {lab_result_L[0, worst_y, worst_x].item():.1f}")
        print(f"  shadow_crush: {shadow_crush[0, worst_y, worst_x].item():.3f}")
        print(f"  target_shadow: {target_shadow[0, worst_y, worst_x].item():.3f}")
        print(f"  shadow_penalty: {shadow_penalty[0, worst_y, worst_x].item():.3f}")

        print(f"\n  === Final Weights ===")
        print(f"  Base weight: 0.1 (RGB 90%)")
        print(f"  weight_lab mean: {weight_lab.mean():.3f}")
        print(f"  weight_lab max : {weight_lab.max():.3f}")
        print()

        return weight_lab.squeeze(0)  # (H, W)

    def _apply_guided_filter(self, target_image, weight_map):
        """
        Apply Guided Filter to weight map for edge-preserving smoothing.

        Args:
            target_image: (H, W, 3) tensor, target RGB image
            weight_map: (H, W) tensor, weight map to be smoothed

        Returns:
            (H, W) tensor, smoothed weight map
        """
        # Convert to BCHW format
        target_bchw = target_image.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)
        weight_bchw = weight_map.unsqueeze(0).unsqueeze(0)  # (1, 1, H, W)

        # Convert target to Lab and use L channel as guide
        target_lab = kornia.color.rgb_to_lab(target_bchw)  # (1, 3, H, W)
        guide = target_lab[:, 0:1, :, :]  # L channel (1, 1, H, W)

        # Apply Guided Filter
        gf = GuidedFilter2d(radius=8, eps=1e-4)
        smoothed = gf(weight_bchw, guide)  # (1, 1, H, W)

        return smoothed


NODE_CLASS_MAPPINGS = {"SBTools_MatchColor": SBTools_MatchColor}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_MatchColor": "Match Color (SBTools)"}
