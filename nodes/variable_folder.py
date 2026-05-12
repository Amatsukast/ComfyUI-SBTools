# ComfyUI-SBTools - Variable Folder Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import re
from .compiler_utils import CompilerUtils


class SBTools_VariableFolder:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "variable_name": "Variable name for image (e.g., BODY_IMAGE, FACE_IMAGE)",
            "folder_map": "Conditional folder definitions with syntax:\n"
            "[condition] --mode\n"
            "folder_path1 --options\n"
            "folder_path2 --options\n\n"
            "Condition options: --random, --sequential\n"
            "Path options: --subfolder, --no-subfolder, --pattern=*.png, --fill-bg=#FFFFFF, --extension, --no-extension",
            "var_list": "Optional: Connect previous variable to enable conditional logic",
        }
        return {
            "required": {
                "variable_name": (
                    "STRING",
                    {"default": "IMAGE1", "tooltip": tooltips["variable_name"]},
                ),
                "folder_map": (
                    "STRING",
                    {
                        "default": "[condition]\nC:\\images\\folder1\nC:\\images\\folder2",
                        "multiline": True,
                        "tooltip": tooltips["folder_map"],
                    },
                ),
            },
            "optional": {
                "var_list": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
            },
        }

    RETURN_TYPES = ("VARIABLE_LIST",)
    RETURN_NAMES = ("var_list",)
    FUNCTION = "create_variable"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    def create_variable(self, variable_name, folder_map, var_list=None):
        # Inherit previous var_list
        result = list(var_list) if var_list else []

        # Auto-generate variable_name if empty
        if not variable_name or not variable_name.strip():
            import time

            unique_id = int(time.time() * 1000000) % 1000000
            variable_name = f"_IMAGE_{unique_id}"
            print(
                f"\033[90m[INFO] Auto-generated variable name: {variable_name}\033[0m"
            )

        # Parse folder_map
        parsed = self._parse_folder_map(folder_map, result)

        # Create variable data
        if parsed["has_conditions"]:
            # Conditional variable
            variable_data = {
                "tag_name": variable_name,
                "type": "image_folder",  # Mark as image variable
                "values": parsed["values"],  # {"common": [...], "conditional": {...}}
                "exclusions": parsed.get(
                    "exclusions", {"common": [], "conditional": {}}
                ),
                "only_flags": parsed.get("only_flags", {}),
                "mode": None,  # Will be set by Variable Image Loader
                "folder_configs": parsed["folder_configs"],  # Store folder metadata
            }
        else:
            # Normal variable (no conditions)
            variable_data = {
                "tag_name": variable_name,
                "type": "image_folder",
                "values": parsed["values"],  # [...]
                "exclusions": parsed.get(
                    "exclusions", {"common": [], "conditional": {}}
                ),
                "only_flags": parsed.get("only_flags", {}),
                "mode": None,  # Will be set by Variable Image Loader
                "folder_configs": parsed["folder_configs"],
            }

        result.append(variable_data)
        return (result,)

    def _parse_folder_map(self, folder_map_text, previous_vars):
        """Parse folder map with conditional syntax and options"""
        lines = folder_map_text.split("\n")

        common_folders = []
        common_exclusions = []  # For --folder_path syntax
        conditional_folders = {}
        conditional_exclusions = {}  # For --folder_path syntax in conditional blocks
        only_flags = {}  # Store --only flags for conditions
        folder_configs = {}  # Store folder options
        has_conditions = False
        current_condition = None
        current_is_only = False  # Track if current condition has --only
        current_mode = "Sequential"  # Default mode
        default_mode = "Sequential"

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check if condition line
            if stripped.startswith("[") and "]" in stripped:
                has_conditions = True

                # Parse condition and options (including --only)
                condition_part, mode_option, is_only = (
                    self._parse_condition_line_with_only(stripped)
                )

                # Store the --only flag for current condition
                current_is_only = is_only

                # Normalize syntax
                normalized = CompilerUtils.normalize_condition_syntax(condition_part)

                # Parse condition
                condition_parts = CompilerUtils.parse_condition_line(normalized)

                if condition_parts == [[("*", None, False)]]:
                    # [*] = back to common
                    current_condition = None
                    current_is_only = False
                    current_mode = mode_option if mode_option else "Sequential"
                else:
                    # Expand OR conditions into multiple condition keys
                    current_condition = CompilerUtils.expand_or_conditions(
                        condition_parts, previous_vars
                    )
                    current_mode = mode_option if mode_option else "Sequential"

                    # If --only flag is set, store it for these conditions
                    if current_is_only and current_condition:
                        for cond_key in current_condition:
                            only_flags[cond_key] = True

                    # Warn if condition didn't match anything
                    if not current_condition:
                        print(
                            f"\033[93m⚠️  WARNING: Condition '{condition_part}' did not match any values in previous variables\033[0m"
                        )
                        print(
                            f"\033[93m   → Folders following this condition will be ignored\033[0m"
                        )
            else:
                # Folder path line - check for exclusion syntax (--folder_path)
                is_exclusion = stripped.startswith("--")
                if is_exclusion:
                    # Remove -- prefix
                    folder_to_exclude = stripped[2:].strip()

                    if current_condition is None:
                        # Common exclusion
                        common_exclusions.append(folder_to_exclude)
                    else:
                        # Conditional exclusion
                        if isinstance(current_condition, list):
                            if not current_condition:
                                print(
                                    f"\033[93m   → Ignoring exclusion: '--{folder_to_exclude}'\033[0m"
                                )
                            else:
                                for cond_key in current_condition:
                                    if cond_key not in conditional_exclusions:
                                        conditional_exclusions[cond_key] = []
                                    conditional_exclusions[cond_key].append(
                                        folder_to_exclude
                                    )
                else:
                    # Normal folder path line
                    folder_path, options = self._parse_path_line(stripped)

                    if not folder_path:
                        continue

                    # Store folder configuration
                    folder_configs[folder_path] = options

                    if current_condition is None:
                        common_folders.append(folder_path)
                    else:
                        # current_condition is a list of condition keys (for OR expansion)
                        if isinstance(current_condition, list):
                            if not current_condition:
                                # Empty condition - folder will be ignored
                                print(
                                    f"\033[93m   → Ignoring folder: '{folder_path}'\033[0m"
                                )
                            else:
                                # Multiple conditions (OR) - add to all
                                for cond_key in current_condition:
                                    if cond_key not in conditional_folders:
                                        conditional_folders[cond_key] = []
                                    conditional_folders[cond_key].append(folder_path)

        # Convert folder paths to image paths
        common_images = []
        conditional_images = {}
        common_image_exclusions = []  # Store image paths from excluded folders
        conditional_image_exclusions = {}

        # Load images from common folders
        for folder_path in common_folders:
            config = folder_configs.get(folder_path, {})
            images = self._get_image_files_from_folder(folder_path, config)
            common_images.extend(images)

        # Load images from excluded common folders (for exclusion list)
        for folder_path in common_exclusions:
            config = folder_configs.get(folder_path, {})
            images = self._get_image_files_from_folder(folder_path, config)
            common_image_exclusions.extend(images)

        # Load images from conditional folders
        for cond_key, folder_list in conditional_folders.items():
            conditional_images[cond_key] = []
            for folder_path in folder_list:
                config = folder_configs.get(folder_path, {})
                images = self._get_image_files_from_folder(folder_path, config)
                conditional_images[cond_key].extend(images)

        # Load images from excluded conditional folders (for exclusion list)
        for cond_key, folder_list in conditional_exclusions.items():
            conditional_image_exclusions[cond_key] = []
            for folder_path in folder_list:
                config = folder_configs.get(folder_path, {})
                images = self._get_image_files_from_folder(folder_path, config)
                conditional_image_exclusions[cond_key].extend(images)

        if has_conditions:
            return {
                "has_conditions": True,
                "values": {"common": common_images, "conditional": conditional_images},
                "exclusions": {
                    "common": common_image_exclusions,
                    "conditional": conditional_image_exclusions,
                },
                "only_flags": only_flags,
                "default_mode": default_mode,
                "folder_configs": folder_configs,
            }
        else:
            # No conditions - return simple list
            return {
                "has_conditions": False,
                "values": common_images if common_images else [],
                "exclusions": {"common": common_image_exclusions, "conditional": {}},
                "only_flags": {},
                "default_mode": default_mode,
                "folder_configs": folder_configs,
            }

    def _parse_condition_line(self, line):
        """Parse condition line and extract mode option (legacy, kept for compatibility)

        Input: "[man&&Military fashion] --random"
        Output: ("[man&&Military fashion]", "Random")
        """
        condition, mode, _ = self._parse_condition_line_with_only(line)
        return condition, mode

    def _parse_condition_line_with_only(self, line):
        """Parse condition line and extract mode and --only option

        Input: "[man&&Military fashion] --random --only"
        Output: ("[man&&Military fashion]", "Random", True)
        """
        # Extract condition part [...]
        if not line.startswith("["):
            return line, None, False

        # Find closing bracket
        end_bracket = line.find("]")
        if end_bracket == -1:
            return line, None, False

        # Condition is everything up to and including ]
        condition = line[: end_bracket + 1]

        # Options are everything after ]
        options_part = line[end_bracket + 1 :].strip()

        # Look for mode options in the options part
        mode = None
        if "--random" in options_part:
            mode = "Random"
        elif "--sequential" in options_part:
            mode = "Sequential"

        # Check for --only flag
        is_only = "--only" in options_part

        return condition, mode, is_only

    def _parse_path_line(self, line):
        """Parse path line and extract options

        Input: "C:\\images\\folder --subfolder --pattern=*.png"
        Output: ("C:\\images\\folder", {"subfolder": True, "pattern": "*.png"})
        """
        # Split by space
        parts = line.split()

        if not parts:
            return None, {}

        # First part is the path
        path = parts[0]

        # Parse options
        options = {}
        for part in parts[1:]:
            if part == "--subfolder":
                options["include_subfolders"] = True
            elif part == "--no-subfolder":
                options["include_subfolders"] = False
            elif part == "--extension":
                options["include_extension"] = True
            elif part == "--no-extension":
                options["include_extension"] = False
            elif part == "--no-fill-bg":
                options["fill_background"] = False
            elif part.startswith("--pattern="):
                options["pattern"] = part.split("=", 1)[1]
            elif part.startswith("--fill-bg="):
                options["fill_background"] = True
                options["background_color"] = part.split("=", 1)[1]

        return path, options

    def _get_image_files_from_folder(self, folder_path, config):
        """Get list of image files from a folder with config options"""
        import os
        import glob

        if not folder_path or not os.path.exists(folder_path):
            print(f"\033[93m[WARNING] Folder not found: {folder_path}\033[0m")
            return []

        pattern = config.get("pattern", "*")
        include_subfolders = config.get("include_subfolders", False)

        # Build search pattern
        search_pattern = os.path.join(glob.escape(folder_path), pattern)

        # Supported formats
        supported_formats = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]

        # Find all matching files
        image_paths = []
        for file_path in glob.glob(search_pattern, recursive=include_subfolders):
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                if ext in supported_formats:
                    image_paths.append(os.path.abspath(file_path))

        # Sort by natural order (Windows-like)
        image_paths.sort(key=self._natural_sort_key)

        return image_paths

    def _natural_sort_key(self, path):
        """Natural sort key for human-friendly ordering (like Windows Explorer)."""
        import os

        def atoi(text):
            return int(text) if text.isdigit() else text.lower()

        basename = os.path.basename(path)
        return [atoi(c) for c in re.split(r"(\d+)", basename)]


NODE_CLASS_MAPPINGS = {"SBTools_VariableFolder": SBTools_VariableFolder}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariableFolder": "Variable Folder (SBTools)"}
