# ComfyUI-SBTools - Luminance Match Node
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
)


class SBTools_MatchLuminance:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "target_image": "Image to be luminance matched (RGB or RGBA).",
            "target_alpha": "Optional alpha channel for target image (overrides target_image 4th channel if present).",
            "reference_image": "Reference image for luminance (RGB only, alpha channel is ignored).",
            "reference_alpha": "Optional alpha channel for reference image (overrides reference_image 4th channel if present).",
            "strength": "Luminance matching strength (0=no change, 1=full match, >1=overcorrection).",
        }
        return {
            "required": {
                "target_image": ("IMAGE", {"tooltip": tooltips["target_image"]}),
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
    FUNCTION = "match_luminance"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    def match_luminance(
        self,
        target_image,
        strength,
        target_alpha=None,
        reference_image=None,
        reference_alpha=None,
    ):
        """
        Match luminance by processing L channel only using histogram matching.

        Args:
            target_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            reference_image: (B, H, W, 3 or 4) tensor with values 0.0-1.0
            strength: float, matching strength

        Returns:
            tuple: (matched_image, rgb_output, alpha_mask)
        """
        # Validate reference image is provided
        if reference_image is None:
            raise ValueError("reference_image is required for luminance matching.")

        # Validate batch sizes
        validate_batch_sizes(target_image, target_alpha)

        # Extract RGB channels only (ignore alpha if present)
        target_rgb = extract_rgb(target_image)
        reference_rgb = extract_rgb(reference_image)

        # Extract alpha from target and reference
        target_alpha_final = extract_alpha(target_image, target_alpha)
        reference_alpha_final = extract_alpha(reference_image, reference_alpha)

        # Skip processing if strength is 0
        if strength == 0:
            output_image = combine_rgba(target_rgb, target_alpha_final)
            return (output_image, target_rgb, target_alpha_final)

        # Convert to Lab space
        target_bchw = target_rgb.permute(0, 3, 1, 2)
        reference_bchw = reference_rgb.permute(0, 3, 1, 2)

        target_lab = kornia.color.rgb_to_lab(target_bchw)
        reference_lab = kornia.color.rgb_to_lab(reference_bchw)

        # Extract L and ab channels
        target_L = target_lab[:, 0:1, :, :]
        target_ab = target_lab[:, 1:3, :, :]
        reference_L = reference_lab[:, 0:1, :, :]

        # Apply histogram matching
        matched_L = self._histogram_match(
            target_L, target_alpha_final, reference_L, reference_alpha_final
        )

        # Apply strength
        matched_L = apply_strength(target_L, matched_L, strength)

        # Reconstruct Lab (matched L + original ab)
        matched_lab = torch.cat([matched_L, target_ab], dim=1)

        # Convert back to RGB
        matched_rgb = kornia.color.lab_to_rgb(matched_lab)
        output_rgb = matched_rgb.permute(0, 2, 3, 1).clamp(0, 1)

        # Combine with alpha
        output_image = combine_rgba(output_rgb, target_alpha_final)

        return (output_image, output_rgb, target_alpha_final)

    def _histogram_match(self, target_L, target_mask, reference_L, reference_mask):
        """Histogram matching for luminance."""
        batch_size = target_L.shape[0]
        threshold = 0.95
        results = []

        for i in range(batch_size):
            # Get masks
            t_mask = target_mask[i] > threshold
            ref_idx = min(i, reference_mask.shape[0] - 1)
            r_mask = reference_mask[ref_idx] > threshold

            # Validate pixels
            if t_mask.sum() < 100:
                raise ValueError(f"Target batch {i}: Insufficient valid pixels.")
            if r_mask.sum() < 100:
                raise ValueError(
                    f"Reference batch {ref_idx}: Insufficient valid pixels."
                )

            # Extract L channel
            t_L = target_L[i, 0].cpu().numpy()
            r_L = reference_L[ref_idx, 0].cpu().numpy()

            t_valid = t_L[t_mask.cpu().numpy()]
            r_valid = r_L[r_mask.cpu().numpy()]

            # Compute histograms and CDFs
            t_hist, t_bins = np.histogram(t_valid.flatten(), bins=256, range=(0, 100))
            r_hist, r_bins = np.histogram(r_valid.flatten(), bins=256, range=(0, 100))

            t_cdf = t_hist.cumsum()
            t_cdf = t_cdf / t_cdf[-1]

            r_cdf = r_hist.cumsum()
            r_cdf = r_cdf / r_cdf[-1]

            # Build LUT
            lut = np.interp(t_cdf, r_cdf, r_bins[:-1])

            # Apply LUT
            matched = np.interp(t_L.flatten(), t_bins[:-1], lut).reshape(t_L.shape)

            # Clip to valid Lab L range to prevent floating-point errors
            matched = np.clip(matched, 0, 100)

            matched = torch.from_numpy(matched).to(target_L.device).unsqueeze(0)

            results.append(matched)

        return torch.stack(results, dim=0)


NODE_CLASS_MAPPINGS = {"SBTools_MatchLuminance": SBTools_MatchLuminance}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_MatchLuminance": "Match Luminance (SBTools)"}
