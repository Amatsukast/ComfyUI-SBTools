# ComfyUI-SBTools - Match Series Utilities
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import torch
import kornia


def validate_batch_sizes(target_image, target_alpha):
    """
    Validate that target_image and target_alpha have matching batch sizes.

    Args:
        target_image: (B, H, W, C) tensor
        target_alpha: (B, H, W) tensor or None

    Raises:
        ValueError: if batch sizes don't match
    """
    if target_alpha is not None and target_alpha.numel() > 0:
        batch_size = target_image.shape[0]

        # Check if alpha has correct dimensions
        if len(target_alpha.shape) != 3:
            raise ValueError(
                f"Invalid alpha shape: expected (B, H, W), got {target_alpha.shape}"
            )

        if target_alpha.shape[0] != batch_size:
            raise ValueError(
                f"Batch size mismatch: target_image has {batch_size} frames, "
                f"but target_alpha has {target_alpha.shape[0]} frames. "
                f"Both must have the same batch size."
            )


def extract_rgb(image):
    """
    Extract RGB channels from image tensor.

    Args:
        image: (B, H, W, 3 or 4) tensor

    Returns:
        (B, H, W, 3) tensor with RGB channels only
    """
    return image[:, :, :, :3]


def extract_alpha(image, explicit_alpha=None):
    """
    Extract alpha channel with priority: explicit_alpha > 4th channel > fully opaque.

    Args:
        image: (B, H, W, 3 or 4) tensor
        explicit_alpha: (B, H, W) MASK tensor or None
            ComfyUI MASK convention: 1.0=transparent, 0.0=opaque

    Returns:
        (B, H, W) tensor with alpha values (1.0=opaque, 0.0=transparent)
    """
    batch_size = image.shape[0]
    height = image.shape[1]
    width = image.shape[2]

    # Check if explicit_alpha is provided, not empty, and has correct shape
    if explicit_alpha is not None and explicit_alpha.numel() > 0:
        # Validate shape: must be 3D tensor (B, H, W) and match image size
        if len(explicit_alpha.shape) == 3:
            # Check if alpha size matches image size
            alpha_height = explicit_alpha.shape[1]
            alpha_width = explicit_alpha.shape[2]

            if alpha_height == height and alpha_width == width:
                # ComfyUI MASK convention: 1.0=transparent, 0.0=opaque
                # Need to invert for alpha channel (1.0=opaque, 0.0=transparent)
                return 1.0 - explicit_alpha
            else:
                # Size mismatch: ignore if it's ComfyUI's default 64×64 empty mask
                if alpha_height == 64 and alpha_width == 64:
                    # Default empty mask, silently ignore and fall through
                    pass
                else:
                    # Non-default size mismatch: this is likely a user error
                    raise ValueError(
                        f"Alpha mask size ({alpha_height}×{alpha_width}) does not match "
                        f"image size ({height}×{width}). Please ensure the mask has the same "
                        f"dimensions as the image."
                    )

    # Check if image has alpha channel
    if len(image.shape) > 3 and image.shape[3] == 4:
        # Use 4th channel as alpha
        return image[:, :, :, 3]

    # Fully opaque fallback
    return torch.ones(
        (batch_size, height, width),
        dtype=torch.float32,
        device=image.device,
    )


def combine_rgba(rgb, alpha):
    """
    Combine RGB and alpha into RGBA if alpha is not fully opaque, else return RGB.

    Args:
        rgb: (B, H, W, 3) tensor
        alpha: (B, H, W) tensor

    Returns:
        (B, H, W, 3) or (B, H, W, 4) tensor
    """
    # Check if alpha is fully opaque
    if torch.all(alpha == 1.0):
        return rgb

    # Combine RGB + Alpha
    return torch.cat([rgb, alpha.unsqueeze(-1)], dim=-1)


def apply_strength(original, modified, strength):
    """
    Blend original and modified based on strength parameter.

    Args:
        original: original tensor
        modified: modified tensor
        strength: float, blending strength (0=original, 1=modified, >1=overcorrection)

    Returns:
        blended tensor
    """
    if strength == 1.0:
        return modified
    return original + strength * (modified - original)


def get_valid_mask(alpha, threshold=0.95):
    """
    Create a boolean mask for pixels with alpha above threshold.

    Args:
        alpha: (B, H, W) tensor with alpha values (1.0=opaque, 0.0=transparent)
        threshold: float, minimum alpha value to consider valid (default: 0.95)

    Returns:
        (B, H, W) boolean tensor
    """
    return alpha > threshold


def compute_masked_mean_cov(image_rgb, alpha, threshold=0.95, min_pixels=100):
    """
    Compute mean and covariance of RGB values, excluding low-alpha pixels.

    Args:
        image_rgb: (B, H, W, 3) tensor
        alpha: (B, H, W) tensor
        threshold: float, minimum alpha value (default: 0.95)
        min_pixels: int, minimum valid pixels required

    Returns:
        tuple: (mean, cov) where mean is (B, 3, 1), cov is (B, 3, 3)
               Returns None if insufficient valid pixels

    Raises:
        ValueError: if valid pixels < min_pixels or shape mismatch
    """
    batch_size = image_rgb.shape[0]
    img_height = image_rgb.shape[1]
    img_width = image_rgb.shape[2]

    # Validate alpha shape matches image
    if alpha.shape[0] != batch_size:
        raise ValueError(
            f"Batch size mismatch: image has {batch_size} frames, alpha has {alpha.shape[0]}"
        )
    if alpha.shape[1] != img_height or alpha.shape[2] != img_width:
        raise ValueError(
            f"Size mismatch: image is {img_height}×{img_width}, "
            f"alpha is {alpha.shape[1]}×{alpha.shape[2]}"
        )

    results_mean = []
    results_cov = []

    for i in range(batch_size):
        mask = get_valid_mask(alpha[i], threshold)  # (H, W)
        valid_count = mask.sum().item()

        if valid_count < min_pixels:
            raise ValueError(
                f"Batch {i}: Insufficient valid pixels ({valid_count} < {min_pixels}). "
                f"Image may have too much transparency (alpha < {threshold})."
            )

        # Extract valid pixels: (H, W, 3) -> (N, 3) where N = valid_count
        valid_pixels = image_rgb[i][mask]  # (N, 3)

        # Compute mean: (3,)
        mean = valid_pixels.mean(dim=0)  # (3,)

        # Compute covariance: (3, 3)
        # Center the data
        centered = valid_pixels - mean  # (N, 3)
        # Cov = (X^T @ X) / (N-1)
        cov = (centered.T @ centered) / (valid_count - 1)  # (3, 3)

        results_mean.append(mean.unsqueeze(-1))  # (3, 1)
        results_cov.append(cov)

    # Stack results
    mean_batch = torch.stack(results_mean, dim=0)  # (B, 3, 1)
    cov_batch = torch.stack(results_cov, dim=0)  # (B, 3, 3)

    return mean_batch, cov_batch


def compute_masked_median_lab_ab(image_rgb, alpha, threshold=0.95, min_pixels=100):
    """
    Compute median of Lab a/b channels, excluding low-alpha pixels.

    Args:
        image_rgb: (B, H, W, 3) tensor in RGB format
        alpha: (B, H, W) tensor
        threshold: float, minimum alpha value (default: 0.95)
        min_pixels: int, minimum valid pixels required

    Returns:
        (B, 2, 1, 1) tensor with median [a, b] values

    Raises:
        ValueError: if valid pixels < min_pixels or shape mismatch
    """
    batch_size = image_rgb.shape[0]
    img_height = image_rgb.shape[1]
    img_width = image_rgb.shape[2]

    # Validate alpha shape matches image
    if alpha.shape[0] != batch_size:
        raise ValueError(
            f"Batch size mismatch: image has {batch_size} frames, alpha has {alpha.shape[0]}"
        )
    if alpha.shape[1] != img_height or alpha.shape[2] != img_width:
        raise ValueError(
            f"Size mismatch: image is {img_height}×{img_width}, "
            f"alpha is {alpha.shape[1]}×{alpha.shape[2]}"
        )

    # Convert to (B, C, H, W) for kornia
    rgb_bchw = image_rgb.permute(0, 3, 1, 2)  # (B, 3, H, W)

    # Convert to Lab
    lab_bchw = kornia.color.rgb_to_lab(rgb_bchw)  # (B, 3, H, W)
    ab_bchw = lab_bchw[:, 1:3, :, :]  # (B, 2, H, W)

    results = []

    for i in range(batch_size):
        mask = get_valid_mask(alpha[i], threshold)  # (H, W)
        valid_count = mask.sum().item()

        if valid_count < min_pixels:
            raise ValueError(
                f"Batch {i}: Insufficient valid pixels ({valid_count} < {min_pixels}). "
                f"Image may have too much transparency (alpha < {threshold})."
            )

        # Extract valid a/b values: (2, H, W) -> (2, N)
        ab_flat = ab_bchw[i].view(2, -1)  # (2, H*W)
        mask_flat = mask.view(-1)  # (H*W,)
        valid_ab = ab_flat[:, mask_flat]  # (2, N)

        # Compute median per channel
        median_a = valid_ab[0].median()  # scalar
        median_b = valid_ab[1].median()  # scalar

        # Stack to (2, 1, 1)
        median = torch.stack([median_a, median_b]).view(2, 1, 1)
        results.append(median)

    # Stack to (B, 2, 1, 1)
    median_batch = torch.stack(results, dim=0)

    return median_batch
