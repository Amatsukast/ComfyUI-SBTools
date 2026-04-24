# Guided Filter for PyTorch
#
# Based on: https://github.com/perrying/guided-filter-pytorch
# Original License: MIT License
# Copyright (c) 2020 perrying
#
# Integrated version for ComfyUI-SBTools
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import torch
import torch.nn as nn
import torch.nn.functional as F


# ========================================
# Box Filter Implementation
# ========================================


def _diff_x(src, r):
    """Horizontal difference using cumulative sum."""
    cum_src = src.cumsum(-2)

    left = cum_src[..., r : 2 * r + 1, :]
    middle = cum_src[..., 2 * r + 1 :, :] - cum_src[..., : -2 * r - 1, :]
    right = cum_src[..., -1:, :] - cum_src[..., -2 * r - 1 : -r - 1, :]

    output = torch.cat([left, middle, right], -2)

    return output


def _diff_y(src, r):
    """Vertical difference using cumulative sum."""
    cum_src = src.cumsum(-1)

    left = cum_src[..., r : 2 * r + 1]
    middle = cum_src[..., 2 * r + 1 :] - cum_src[..., : -2 * r - 1]
    right = cum_src[..., -1:] - cum_src[..., -2 * r - 1 : -r - 1]

    output = torch.cat([left, middle, right], -1)

    return output


def boxfilter2d(src, radius):
    """
    2D box filter using cumulative sum for efficient computation.

    Args:
        src: (B, C, H, W) tensor
        radius: int, filter radius

    Returns:
        (B, C, H, W) tensor, box-filtered result
    """
    return _diff_y(_diff_x(src, radius), radius)


# ========================================
# Guided Filter Implementation
# ========================================


class GuidedFilter2d(nn.Module):
    """
    Guided Filter for edge-preserving smoothing.

    Args:
        radius: int, filter radius
        eps: float, regularization coefficient
    """

    def __init__(self, radius: int, eps: float):
        super().__init__()
        self.r = radius
        self.eps = eps

    def forward(self, x, guide):
        """
        Apply guided filter.

        Args:
            x: (B, C, H, W) tensor, source image to be filtered
            guide: (B, 1 or 3, H, W) tensor, guide image

        Returns:
            (B, C, H, W) tensor, filtered result
        """
        if guide.shape[1] == 3:
            return guidedfilter2d_color(guide, x, self.r, self.eps)
        elif guide.shape[1] == 1:
            return guidedfilter2d_gray(guide, x, self.r, self.eps)
        else:
            raise NotImplementedError(
                f"Guide image must have 1 or 3 channels, got {guide.shape[1]}"
            )


class FastGuidedFilter2d(GuidedFilter2d):
    """
    Fast guided filter with downsampling.

    Args:
        radius: int, filter radius
        eps: float, regularization coefficient
        s: int, downsampling scale factor
    """

    def __init__(self, radius: int, eps: float, s: int):
        super().__init__(radius, eps)
        self.s = s

    def forward(self, x, guide):
        """
        Apply fast guided filter with downsampling.

        Args:
            x: (B, C, H, W) tensor, source image to be filtered
            guide: (B, 1 or 3, H, W) tensor, guide image

        Returns:
            (B, C, H, W) tensor, filtered result
        """
        if guide.shape[1] == 3:
            return guidedfilter2d_color(guide, x, self.r, self.eps, self.s)
        elif guide.shape[1] == 1:
            return guidedfilter2d_gray(guide, x, self.r, self.eps, self.s)
        else:
            raise NotImplementedError(
                f"Guide image must have 1 or 3 channels, got {guide.shape[1]}"
            )


def guidedfilter2d_color(guide, src, radius, eps, scale=None):
    """
    Guided filter for a color guide image.

    Parameters
    ----------
    guide: (B, 3, H, W)-dim torch.Tensor
        guide image (RGB)
    src: (B, C, H, W)-dim torch.Tensor
        filtering image
    radius: int
        filter radius
    eps: float
        regularization coefficient
    scale: int, optional
        downsampling scale factor for fast filtering
    """
    assert guide.shape[1] == 3

    if src.ndim == 3:
        src = src[:, None]

    if scale is not None:
        guide_sub = guide.clone()
        src = F.interpolate(src, scale_factor=1.0 / scale, mode="nearest")
        guide = F.interpolate(guide, scale_factor=1.0 / scale, mode="nearest")
        radius = radius // scale

    guide_r, guide_g, guide_b = torch.chunk(guide, 3, 1)
    ones = torch.ones_like(guide_r)
    N = boxfilter2d(ones, radius)

    mean_I = boxfilter2d(guide, radius) / N
    mean_I_r, mean_I_g, mean_I_b = torch.chunk(mean_I, 3, 1)

    mean_p = boxfilter2d(src, radius) / N
    mean_Ip_r = boxfilter2d(guide_r * src, radius) / N
    mean_Ip_g = boxfilter2d(guide_g * src, radius) / N
    mean_Ip_b = boxfilter2d(guide_b * src, radius) / N

    cov_Ip_r = mean_Ip_r - mean_I_r * mean_p
    cov_Ip_g = mean_Ip_g - mean_I_g * mean_p
    cov_Ip_b = mean_Ip_b - mean_I_b * mean_p

    var_I_rr = boxfilter2d(guide_r * guide_r, radius) / N - mean_I_r * mean_I_r + eps
    var_I_rg = boxfilter2d(guide_r * guide_g, radius) / N - mean_I_r * mean_I_g
    var_I_rb = boxfilter2d(guide_r * guide_b, radius) / N - mean_I_r * mean_I_b
    var_I_gg = boxfilter2d(guide_g * guide_g, radius) / N - mean_I_g * mean_I_g + eps
    var_I_gb = boxfilter2d(guide_g * guide_b, radius) / N - mean_I_g * mean_I_b
    var_I_bb = boxfilter2d(guide_b * guide_b, radius) / N - mean_I_b * mean_I_b + eps

    cov_det = (
        var_I_rr * var_I_gg * var_I_bb
        + var_I_rg * var_I_gb * var_I_rb
        + var_I_rb * var_I_rg * var_I_gb
        - var_I_rb * var_I_gg * var_I_rb
        - var_I_rg * var_I_rg * var_I_bb
        - var_I_rr * var_I_gb * var_I_gb
    )

    inv_var_I_rr = (var_I_gg * var_I_bb - var_I_gb * var_I_gb) / cov_det
    inv_var_I_rg = -(var_I_rg * var_I_bb - var_I_rb * var_I_gb) / cov_det
    inv_var_I_rb = (var_I_rg * var_I_gb - var_I_rb * var_I_gg) / cov_det
    inv_var_I_gg = (var_I_rr * var_I_bb - var_I_rb * var_I_rb) / cov_det
    inv_var_I_gb = -(var_I_rr * var_I_gb - var_I_rb * var_I_rg) / cov_det
    inv_var_I_bb = (var_I_rr * var_I_gg - var_I_rg * var_I_rg) / cov_det

    inv_sigma = torch.stack(
        [
            torch.stack([inv_var_I_rr, inv_var_I_rg, inv_var_I_rb], 1),
            torch.stack([inv_var_I_rg, inv_var_I_gg, inv_var_I_gb], 1),
            torch.stack([inv_var_I_rb, inv_var_I_gb, inv_var_I_bb], 1),
        ],
        1,
    ).squeeze(-3)

    cov_Ip = torch.stack([cov_Ip_r, cov_Ip_g, cov_Ip_b], 1)

    a = torch.einsum("bichw,bijhw->bjchw", (cov_Ip, inv_sigma))
    b = mean_p - a[:, 0] * mean_I_r - a[:, 1] * mean_I_g - a[:, 2] * mean_I_b

    mean_a = torch.stack([boxfilter2d(a[:, i], radius) / N for i in range(3)], 1)
    mean_b = boxfilter2d(b, radius) / N

    if scale is not None:
        guide = guide_sub
        mean_a = torch.stack(
            [
                F.interpolate(mean_a[:, i], guide.shape[-2:], mode="bilinear")
                for i in range(3)
            ],
            1,
        )
        mean_b = F.interpolate(mean_b, guide.shape[-2:], mode="bilinear")

    q = torch.einsum("bichw,bihw->bchw", (mean_a, guide)) + mean_b

    return q


def guidedfilter2d_gray(guide, src, radius, eps, scale=None):
    """
    Guided filter for a gray scale guide image.

    Parameters
    ----------
    guide: (B, 1, H, W)-dim torch.Tensor
        guide image (grayscale)
    src: (B, C, H, W)-dim torch.Tensor
        filtering image
    radius: int
        filter radius
    eps: float
        regularization coefficient
    scale: int, optional
        downsampling scale factor for fast filtering
    """
    if guide.ndim == 3:
        guide = guide[:, None]

    if src.ndim == 3:
        src = src[:, None]

    if scale is not None:
        guide_sub = guide.clone()
        src = F.interpolate(src, scale_factor=1.0 / scale, mode="nearest")
        guide = F.interpolate(guide, scale_factor=1.0 / scale, mode="nearest")
        radius = radius // scale

    ones = torch.ones_like(guide)
    N = boxfilter2d(ones, radius)

    mean_I = boxfilter2d(guide, radius) / N
    mean_p = boxfilter2d(src, radius) / N
    mean_Ip = boxfilter2d(guide * src, radius) / N

    cov_Ip = mean_Ip - mean_I * mean_p
    mean_II = boxfilter2d(guide * guide, radius) / N
    var_I = mean_II - mean_I * mean_I

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = boxfilter2d(a, radius) / N
    mean_b = boxfilter2d(b, radius) / N

    if scale is not None:
        guide = guide_sub
        mean_a = F.interpolate(mean_a, guide.shape[-2:], mode="bilinear")
        mean_b = F.interpolate(mean_b, guide.shape[-2:], mode="bilinear")

    q = mean_a * guide + mean_b

    return q
