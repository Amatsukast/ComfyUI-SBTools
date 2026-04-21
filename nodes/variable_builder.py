# ComfyUI-SBTools - Variable Builder Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import random
import torch
from PIL import Image, ImageOps
import numpy as np

from .compiler_utils import CompilerUtils


class SBTools_VariableBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "template": "Template text with [TAG_NAME] tags (e.g., 'A [AGE] [GENDER][CLOTHING].'). Leave empty for simple join mode.",
            "index": "Index to select which Sequential combination (loops automatically)",
            "seed": "Seed for Random TEXT variables (Image Variable has its own seed)",
            "separator": "Separator to join values (used for unused variables and empty template mode)",
            "var_list": "Variable list from Prompt Variable, Image Variable Loader, or Variable Combiner",
        }
        return {
            "required": {
                "template": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": tooltips["template"],
                    },
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
                "separator": (
                    "STRING",
                    {
                        "default": ", ",
                        "tooltip": tooltips["separator"],
                    },
                ),
            },
            "optional": {
                "var_list": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
            },
        }

    RETURN_TYPES = ("STRING", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "INT", "STRING")
    RETURN_NAMES = (
        "prompt",
        "image1",
        "image2",
        "image3",
        "image4",
        "max_combinations",
        "all_combinations",
    )
    FUNCTION = "compile"
    CATEGORY = "SBTools/Prompt"
    OUTPUT_NODE = False

    def compile(self, **kwargs):
        template = kwargs.get("template", "")
        index = kwargs.get("index", 0)
        seed = kwargs.get("seed", 0)
        separator = kwargs.get("separator", ", ")
        var_list = kwargs.get("var_list", [])
        variables = var_list if var_list else []

        empty_image = torch.zeros((1, 64, 64, 3))

        if not variables:
            return ("", empty_image, empty_image, empty_image, empty_image, 1, "")

        # Separate text and image variables
        text_vars = [v for v in variables if v.get("type") != "Image"]
        image_vars = [v for v in variables if v.get("type") == "Image"][:4]

        # Calculate total combinations (enumerates all)
        all_vars = text_vars + image_vars
        max_combinations = CompilerUtils.calculate_combinations(all_vars)

        if max_combinations == 0:
            return ("", empty_image, empty_image, empty_image, empty_image, 1, "")

        safe_index = index % max_combinations

        # Resolve text values
        if text_vars:
            text_values = CompilerUtils.resolve_index(safe_index, text_vars, seed)

            # Build prompt
            if template.strip():
                prompt = CompilerUtils.apply_template(
                    template, text_vars, text_values, separator
                )
            else:
                prompt = CompilerUtils.apply_simple_join(
                    text_vars, text_values, separator
                )
        else:
            prompt = ""

        # Resolve image paths
        selected_image_paths = []
        for img_var in image_vars:
            if img_var.get("mode") == "Random":
                image_seed = img_var.get("seed", 0)
                random.seed(image_seed)
                selected_image_paths.append(random.choice(img_var["values"]))
            else:
                # Sequential - resolve with same index
                img_values = CompilerUtils.resolve_index(safe_index, [img_var], seed)
                if img_values:
                    selected_image_paths.append(img_values[0])

        # Load images
        loaded_images = []
        for i, img_path in enumerate(selected_image_paths):
            try:
                img_var = image_vars[i]
                fill_background = img_var.get("fill_background", False)
                background_color = img_var.get("background_color", "#FFFFFF")

                image_tensor = self._load_image_as_tensor(
                    img_path, fill_background, background_color
                )
                loaded_images.append(image_tensor)
            except Exception as e:
                print(
                    f"\033[91m[ERROR] Failed to load image: {img_path} - {str(e)}\033[0m"
                )
                loaded_images.append(empty_image)

        # Fill empty slots
        while len(loaded_images) < 4:
            loaded_images.append(empty_image)

        # Generate debug output (enumerates all combinations)
        all_combinations_text = CompilerUtils.generate_all_combinations_text(text_vars)

        # Also print warnings to console if present
        if text_vars and "⚠️" in all_combinations_text:
            # Extract warning section
            warning_lines = all_combinations_text.split("=" * 70)
            if len(warning_lines) >= 3:
                warning_section = warning_lines[1].strip()
                print(f"\033[93m{warning_section}\033[0m")

        return (
            prompt,
            loaded_images[0],
            loaded_images[1],
            loaded_images[2],
            loaded_images[3],
            max_combinations,
            all_combinations_text,
        )

    def _load_image_as_tensor(
        self, image_path, fill_background=False, background_color="#FFFFFF"
    ):
        """Load image and convert to ComfyUI tensor format"""
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)

        if fill_background and img.mode in ["RGBA", "LA", "PA"]:
            bg_color = self._parse_hex_color(background_color)
            background = Image.new("RGB", img.size, bg_color)
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            elif img.mode == "LA":
                background.paste(img.convert("L"), mask=img.split()[1])
            else:
                background.paste(img.convert("P"), mask=img.split()[1])
            img = background
        elif img.mode not in ["RGB", "RGBA"]:
            img = img.convert("RGB")

        img_array = np.array(img).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(img_array)[None,]

        return image_tensor

    def _parse_hex_color(self, hex_color):
        """Convert hex color string to RGB tuple"""
        hex_color = hex_color.strip()
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]

        if len(hex_color) != 6:
            print(
                f"\033[93m[WARNING] Invalid hex color '{hex_color}', using white (#FFFFFF)\033[0m"
            )
            return (255, 255, 255)

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


NODE_CLASS_MAPPINGS = {"SBTools_VariableBuilder": SBTools_VariableBuilder}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariableBuilder": "Variable Builder (SBTools)"}
