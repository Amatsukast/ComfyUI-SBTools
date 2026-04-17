# ComfyUI-SBTools - Multi Compiler Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import itertools
import re
import random
import os
import torch
from PIL import Image, ImageOps
import numpy as np


class SBTools_MultiCompiler:
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
        # Extract parameters
        template = kwargs.get("template", "")
        index = kwargs.get("index", 0)
        seed = kwargs.get("seed", 0)
        separator = kwargs.get("separator", ", ")

        # Get variables from var_list
        var_list = kwargs.get("var_list", [])
        variables = var_list if var_list else []

        # If no variables connected, return empty
        if not variables:
            empty_image = torch.zeros((1, 64, 64, 3))
            return ("", empty_image, empty_image, empty_image, empty_image, 1, "")

        # Separate text and image variables
        text_vars = [v for v in variables if v.get("type") != "Image"]
        image_vars = [v for v in variables if v.get("type") == "Image"][
            :4
        ]  # Max 4 images

        # Separate Sequential and Random for text variables
        sequential_text_vars = [v for v in text_vars if v["mode"] == "Sequential"]
        random_text_vars = [v for v in text_vars if v["mode"] == "Random"]

        # Separate Sequential and Random for image variables
        sequential_image_vars = [v for v in image_vars if v["mode"] == "Sequential"]
        random_image_vars = [v for v in image_vars if v["mode"] == "Random"]

        # Calculate Sequential combinations for ALL variables (text + ALL images)
        all_sequential_vars = sequential_text_vars + sequential_image_vars

        if all_sequential_vars:
            sequential_value_lists = [var["values"] for var in all_sequential_vars]
            all_combinations = list(itertools.product(*sequential_value_lists))
            max_combinations = len(all_combinations)
        else:
            all_combinations = [()]
            max_combinations = 1

        # Handle empty case
        if max_combinations == 0:
            empty_image = torch.zeros((1, 64, 64, 3))
            return ("", empty_image, empty_image, empty_image, empty_image, 1, "")

        # Loop index (modulo to wrap around)
        safe_index = index % max_combinations

        # Get the selected Sequential combination
        selected_sequential = all_combinations[safe_index]

        # Select Random TEXT values based on Multi Compiler's seed
        random.seed(seed)
        selected_random_text = [
            random.choice(var["values"]) for var in random_text_vars
        ]

        # Select Random IMAGE values (each image uses its own seed)
        selected_random_images = []
        for img_var in random_image_vars:
            image_seed = img_var.get("seed", 0)
            random.seed(image_seed)
            selected_random_images.append(random.choice(img_var["values"]))

        # Merge Sequential and Random values for TEXT only
        # (split the sequential combination back into text and image parts)
        num_seq_text = len(sequential_text_vars)
        num_seq_images = len(sequential_image_vars)

        selected_text_values = self._merge_values(
            text_vars,
            selected_sequential[:num_seq_text],  # Text part
            selected_random_text,
        )

        # Get selected image paths (Sequential + Random combined)
        selected_image_paths = []

        # Add Sequential images
        sequential_image_paths = selected_sequential[
            num_seq_text : num_seq_text + num_seq_images
        ]
        for img_path in sequential_image_paths:
            selected_image_paths.append(img_path)

        # Add Random images
        for img_path in selected_random_images:
            selected_image_paths.append(img_path)

        # Build prompt (same logic as Prompt Compiler)
        if template.strip():
            prompt = self._apply_template(
                template, text_vars, selected_text_values, separator
            )
            all_combinations_text = self._generate_debug_template(
                template,
                text_vars,
                all_combinations,
                random_text_vars,
                image_vars,
                separator,
            )
        else:
            formatted_values = []
            for var, value in zip(text_vars, selected_text_values):
                if value != "":
                    formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                    formatted_values.append(formatted)
            prompt = separator.join(formatted_values)
            all_combinations_text = self._generate_debug_simple(
                separator, text_vars, all_combinations, random_text_vars, image_vars
            )

        # Load all images (up to 4)
        loaded_images = []
        for i, img_path in enumerate(selected_image_paths):
            try:
                # Get corresponding image variable for this image
                if i < len(image_vars):
                    img_var = image_vars[i]
                    fill_background = img_var.get("fill_background", False)
                    background_color = img_var.get("background_color", "#FFFFFF")
                else:
                    fill_background = False
                    background_color = "#FFFFFF"

                image_tensor = self._load_image_as_tensor(
                    img_path, fill_background, background_color
                )
                loaded_images.append(image_tensor)
            except Exception as e:
                print(
                    f"\033[91m[ERROR] Failed to load image: {img_path} - {str(e)}\033[0m"
                )
                loaded_images.append(torch.zeros((1, 64, 64, 3)))

        # Fill empty slots with blank images (up to 4 total)
        empty_image = torch.zeros((1, 64, 64, 3))
        while len(loaded_images) < 4:
            loaded_images.append(empty_image)

        return (
            prompt,
            loaded_images[0],
            loaded_images[1],
            loaded_images[2],
            loaded_images[3],
            max_combinations,
            all_combinations_text,
        )

    def _merge_values(self, all_vars, seq_values, rand_values):
        """Merge Sequential and Random values in original variable order."""
        seq_idx = 0
        rand_idx = 0
        result = []

        for var in all_vars:
            if var["mode"] == "Sequential":
                result.append(seq_values[seq_idx])
                seq_idx += 1
            else:  # Random
                result.append(rand_values[rand_idx])
                rand_idx += 1

        return result

    def _generate_debug_template(
        self, template, text_vars, seq_combinations, rand_vars, image_vars, separator
    ):
        """Generate debug output for template mode."""
        # Use seed=0 for random TEXT variables in debug
        random.seed(0)
        fixed_random = [random.choice(var["values"]) for var in rand_vars]

        # For random images, use their own seeds (from Image Variables)
        fixed_random_images = []
        for img_var in image_vars:
            if img_var["mode"] == "Random":
                image_seed = img_var.get("seed", 0)
                random.seed(image_seed)
                fixed_random_images.append(random.choice(img_var["values"]))

        lines = []
        num_seq_text = len([v for v in text_vars if v["mode"] == "Sequential"])
        num_seq_images = len([v for v in image_vars if v["mode"] == "Sequential"])

        for i, seq_combo in enumerate(seq_combinations):
            # Split combo into text and image parts
            text_part = seq_combo[:num_seq_text]
            image_part = seq_combo[num_seq_text : num_seq_text + num_seq_images]

            merged = self._merge_values(text_vars, text_part, fixed_random)
            prompt = self._apply_template(template, text_vars, merged, separator)

            # Add prompt line
            lines.append(f"index {i}: {prompt}")

            # Add image filenames on separate line if present
            if image_vars:
                filenames = []
                # Add Sequential images
                for img_path in image_part:
                    filenames.append(os.path.basename(img_path))
                # Add Random images
                for img_path in fixed_random_images:
                    filenames.append(os.path.basename(img_path))

                image_str = ", ".join(
                    [f"img{idx+1}:{fn}" for idx, fn in enumerate(filenames)]
                )
                lines.append(f"  {image_str}")

        if rand_vars:
            lines.append("\n(Random text variables shown with seed=0)")
        if any(img["mode"] == "Random" for img in image_vars):
            seed_info = ", ".join(
                [
                    f"img{i+1}:seed={img.get('seed', 0)}"
                    for i, img in enumerate(image_vars)
                    if img["mode"] == "Random"
                ]
            )
            lines.append(f"(Random images: {seed_info})")

        return "\n".join(lines)

    def _generate_debug_simple(
        self, separator, text_vars, seq_combinations, rand_vars, image_vars
    ):
        """Generate debug output for simple join mode."""
        # Use seed=0 for random TEXT variables in debug
        random.seed(0)
        fixed_random = [random.choice(var["values"]) for var in rand_vars]

        # For random images, use their own seeds (from Image Variables)
        fixed_random_images = []
        for img_var in image_vars:
            if img_var["mode"] == "Random":
                image_seed = img_var.get("seed", 0)
                random.seed(image_seed)
                fixed_random_images.append(random.choice(img_var["values"]))

        lines = []
        num_seq_text = len([v for v in text_vars if v["mode"] == "Sequential"])
        num_seq_images = len([v for v in image_vars if v["mode"] == "Sequential"])

        for i, seq_combo in enumerate(seq_combinations):
            text_part = seq_combo[:num_seq_text]
            image_part = seq_combo[num_seq_text : num_seq_text + num_seq_images]

            merged = self._merge_values(text_vars, text_part, fixed_random)
            formatted_values = []
            for var, value in zip(text_vars, merged):
                if value != "":
                    formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                    formatted_values.append(formatted)
            prompt = separator.join(formatted_values)

            # Add prompt line
            lines.append(f"index {i}: {prompt}")

            # Add image filenames on separate line if present
            if image_vars:
                filenames = []
                # Add Sequential images
                for img_path in image_part:
                    filenames.append(os.path.basename(img_path))
                # Add Random images
                for img_path in fixed_random_images:
                    filenames.append(os.path.basename(img_path))

                image_str = ", ".join(
                    [f"img{idx+1}:{fn}" for idx, fn in enumerate(filenames)]
                )
                lines.append(f"  {image_str}")

        if rand_vars:
            lines.append("\n(Random text variables shown with seed=0)")
        if any(img["mode"] == "Random" for img in image_vars):
            seed_info = ", ".join(
                [
                    f"img{i+1}:seed={img.get('seed', 0)}"
                    for i, img in enumerate(image_vars)
                    if img["mode"] == "Random"
                ]
            )
            lines.append(f"(Random images: {seed_info})")

        return "\n".join(lines)

    def _apply_template(self, template, variables, selected_values, separator):
        """Apply template replacement with [TAG_NAME] tags."""
        result = template

        # Extract all tags from template
        tags_in_template = set(re.findall(r"\[([^\]]+)\]", template))

        # Create mapping with variable metadata
        tag_data = {}
        for idx, (var, value) in enumerate(zip(variables, selected_values)):
            tag_data[var["tag_name"]] = {
                "value": value,
                "prefix": var.get("prefix", ""),
                "suffix": var.get("suffix", ""),
                "index": idx,
            }

        # Track which tags are used
        used_tags = set()

        # Replace tags with prefix/suffix handling
        for tag_name, data in tag_data.items():
            tag = f"[{tag_name}]"
            if tag in result:
                if data["value"] != "":
                    replacement = f"{data['prefix']}{data['value']}{data['suffix']}"
                else:
                    replacement = ""
                result = result.replace(tag, replacement)
                used_tags.add(tag_name)

        # Collect unused variables
        unused_values = []
        for tag_name, data in sorted(tag_data.items(), key=lambda x: x[1]["index"]):
            if tag_name not in used_tags and data["value"] != "":
                formatted_value = f"{data['prefix']}{data['value']}{data['suffix']}"
                unused_values.append(formatted_value)

        # Clean up spaces
        result = re.sub(r"\s+([.,!?;:])", r"\1", result)
        result = re.sub(r"\s+", " ", result).strip()

        # Append unused variables
        if unused_values:
            if result:
                result += separator
            result += separator.join(unused_values)

        return result

    def _load_image_as_tensor(
        self, image_path, fill_background=False, background_color="#FFFFFF"
    ):
        """Load image and convert to ComfyUI tensor format."""
        img = Image.open(image_path)
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

        img_array = np.array(img).astype(np.float32) / 255.0
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


NODE_CLASS_MAPPINGS = {"SBTools_MultiCompiler": SBTools_MultiCompiler}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_MultiCompiler": "Multi Compiler (SBTools)"}
