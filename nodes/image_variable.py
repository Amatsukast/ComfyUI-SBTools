# ComfyUI-SBTools - Image Variable Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import os
import glob
import random
import re
import torch
from PIL import Image, ImageOps
import numpy as np


class SBTools_ImageVariable:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "folder_path": "Path to folder containing images (absolute or relative)",
            "pattern": "File pattern for glob matching (e.g., '*.png', 'body_*.jpg'). Use '**/*' with subfolders enabled.",
            "index": "Index to select which image in sequential mode (loops automatically)",
            "randomize": "Enable random selection (off = sequential by index)",
            "seed": "Seed for random selection",
            "include_subfolders": "Search in subfolders (requires '**/' in pattern)",
            "include_extension": "Include file extension in filename output",
            "fill_background": "Fill transparent areas with solid color (default: keep transparency)",
            "background_color": "Background color in hex format (e.g., #FFFFFF for white)",
        }
        return {
            "required": {
                "folder_path": (
                    "STRING",
                    {"default": "", "tooltip": tooltips["folder_path"]},
                ),
                "pattern": (
                    "STRING",
                    {"default": "*", "tooltip": tooltips["pattern"]},
                ),
                "index": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 999999,
                        "step": 1,
                        "tooltip": tooltips["index"],
                    },
                ),
                "randomize": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["randomize"]},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFF,
                        "step": 1,
                        "tooltip": tooltips["seed"],
                    },
                ),
            },
            "optional": {
                "include_subfolders": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["include_subfolders"]},
                ),
                "include_extension": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["include_extension"]},
                ),
                "fill_background": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["fill_background"]},
                ),
                "background_color": (
                    "STRING",
                    {"default": "#FFFFFF", "tooltip": tooltips["background_color"]},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "VARIABLE_LIST", "INT", "STRING")
    RETURN_NAMES = ("image", "var_list", "total_images", "filename")
    FUNCTION = "load_image"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]

    def load_image(
        self,
        folder_path,
        pattern,
        index,
        seed,
        randomize,
        include_subfolders=False,
        include_extension=False,
        fill_background=False,
        background_color="#FFFFFF",
    ):
        # Get all image files
        image_paths = self._get_image_files(folder_path, pattern, include_subfolders)

        if not image_paths:
            # Return empty/error state
            error_msg = f"No images found in: {folder_path} with pattern: {pattern}"
            print(f"\033[91m[ERROR] {error_msg}\033[0m")
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, [], 0, error_msg)

        # Select image
        if randomize:
            random.seed(seed)
            selected_index = random.randint(0, len(image_paths) - 1)
        else:
            selected_index = index % len(image_paths)

        selected_path = image_paths[selected_index]

        # Load image
        try:
            image_tensor = self._load_image_as_tensor(
                selected_path, fill_background, background_color
            )
        except Exception as e:
            error_msg = f"Failed to load: {selected_path} - {str(e)}"
            print(f"\033[91m[ERROR] {error_msg}\033[0m")
            empty_image = torch.zeros((1, 64, 64, 3))
            return (empty_image, [], len(image_paths), error_msg)

        # Create variable data for Variable Combiner
        variable_data = {
            "tag_name": "IMAGE",  # Default tag name
            "values": image_paths,  # List of all image paths
            "mode": "Random" if randomize else "Sequential",
            "type": "Image",  # Mark as image type
            "seed": seed,  # Include seed for Multi Compiler to use
            "fill_background": fill_background,  # Background fill setting
            "background_color": background_color,  # Background color in hex
            "prefix": "",
            "suffix": "",
        }

        # Get filename
        filename = os.path.basename(selected_path)
        if not include_extension:
            filename = os.path.splitext(filename)[0]

        return (image_tensor, [variable_data], len(image_paths), filename)

    def _get_image_files(self, folder_path, pattern, include_subfolders=False):
        """Get sorted list of image files matching pattern."""
        if not folder_path or not os.path.exists(folder_path):
            return []

        # Build search pattern
        search_pattern = os.path.join(glob.escape(folder_path), pattern)

        # Find all matching files
        image_paths = []
        for file_path in glob.glob(search_pattern, recursive=include_subfolders):
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                if ext in self.SUPPORTED_FORMATS:
                    image_paths.append(os.path.abspath(file_path))

        # Sort by natural order (Windows-like)
        image_paths.sort(key=self._natural_sort_key)

        return image_paths

    def _natural_sort_key(self, path):
        """Natural sort key for human-friendly ordering (like Windows Explorer)."""

        def atoi(text):
            return int(text) if text.isdigit() else text.lower()

        basename = os.path.basename(path)
        return [atoi(c) for c in re.split(r"(\d+)", basename)]

    def _load_image_as_tensor(
        self, image_path, fill_background=False, background_color="#FFFFFF"
    ):
        """Load image and convert to ComfyUI tensor format."""
        # Load with PIL
        img = Image.open(image_path)

        # Handle EXIF orientation
        img = ImageOps.exif_transpose(img)

        # Handle RGBA to RGB conversion if requested
        if fill_background and img.mode in ["RGBA", "LA", "PA"]:
            # Parse hex color
            bg_color = self._parse_hex_color(background_color)

            # Create background and paste with alpha
            background = Image.new("RGB", img.size, bg_color)
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            elif img.mode == "LA":
                background.paste(img.convert("L"), mask=img.split()[1])
            else:  # PA
                background.paste(img.convert("P"), mask=img.split()[1])
            img = background
        elif img.mode not in ["RGB", "RGBA"]:
            # Convert other modes (L, P, CMYK, etc.) to RGB
            img = img.convert("RGB")

        # Convert to numpy array
        img_array = np.array(img).astype(np.float32) / 255.0

        # Convert to tensor: (H, W, C) -> (1, H, W, C)
        image_tensor = torch.from_numpy(img_array)[None,]

        return image_tensor

    def _parse_hex_color(self, hex_color):
        """Convert hex color string to RGB tuple."""
        hex_color = hex_color.strip()
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]

        # Validate length
        if len(hex_color) != 6:
            print(
                f"\033[93m[WARNING] Invalid hex color '{hex_color}', using white (#FFFFFF)\033[0m"
            )
            return (255, 255, 255)

        # Parse RGB values
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except ValueError:
            print(
                f"\033[93m[WARNING] Invalid hex color '{hex_color}', using white (#FFFFFF)\033[0m"
            )
            return (255, 255, 255)


NODE_CLASS_MAPPINGS = {"SBTools_ImageVariable": SBTools_ImageVariable}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SBTools_ImageVariable": "Image Variable Loader (SBTools)"
}
