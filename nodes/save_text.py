# ComfyUI-SBTools - Save Text Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import os
import re
from datetime import datetime

import folder_paths


class SBTools_SaveText:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "text": "Text content to save to file",
            "folder_path": (
                "Subfolder path relative to ComfyUI output directory. "
                "Supports strftime format (e.g., %Y/%m/%d)"
            ),
            "filename_prefix": (
                "Base filename. Supports strftime format (e.g., %Y%m%d_%H%M%S)"
            ),
            "extension": "File extension (dot is added automatically)",
            "save_mode": (
                "Sequential: numbered files. "
                "Overwrite: replace existing. "
                "Append: add to existing"
            ),
            "counter_digits": (
                "Number of digits for zero-padded counter "
                "(only used in Sequential mode)"
            ),
            "counter_position": (
                "Counter placement relative to filename "
                "(only used in Sequential mode)"
            ),
            "separator": (
                "Character between filename and counter "
                "(only used in Sequential mode)"
            ),
        }
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": tooltips["text"],
                    },
                ),
                "folder_path": (
                    "STRING",
                    {"default": "", "tooltip": tooltips["folder_path"]},
                ),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "text_output",
                        "tooltip": tooltips["filename_prefix"],
                    },
                ),
                "extension": (
                    "STRING",
                    {"default": "txt", "tooltip": tooltips["extension"]},
                ),
                "save_mode": (
                    ["Sequential", "Overwrite", "Append"],
                    {"default": "Overwrite", "tooltip": tooltips["save_mode"]},
                ),
                "counter_digits": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "max": 9,
                        "tooltip": tooltips["counter_digits"],
                    },
                ),
                "counter_position": (
                    ["Back", "Front"],
                    {
                        "default": "Back",
                        "tooltip": tooltips["counter_position"],
                    },
                ),
                "separator": (
                    "STRING",
                    {"default": "_", "tooltip": tooltips["separator"]},
                ),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save_text"
    CATEGORY = "SBTools/Text"
    OUTPUT_NODE = True

    def save_text(
        self,
        text,
        folder_path,
        filename_prefix,
        extension,
        save_mode,
        counter_digits,
        counter_position,
        separator,
    ):
        # 1. Capture datetime once to prevent cross-midnight inconsistency
        now = datetime.now()

        # 2. Apply strftime formatting
        folder_path = now.strftime(folder_path)
        filename_prefix = now.strftime(filename_prefix)

        # 3. Sanitize inputs
        folder_path = self._sanitize_folder_path(folder_path)
        filename_prefix = self._sanitize_filename(filename_prefix)
        extension = self._sanitize_extension(extension)

        # 4. Build output directory path
        output_base = folder_paths.get_output_directory()
        if folder_path:
            target_dir = os.path.join(output_base, folder_path)
        else:
            target_dir = output_base

        # 5. Path traversal protection
        target_dir_abs = os.path.abspath(target_dir)
        output_base_abs = os.path.abspath(output_base)
        try:
            common = os.path.commonpath([target_dir_abs, output_base_abs])
            if common != output_base_abs:
                raise ValueError(
                    f"Path traversal detected: '{folder_path}' "
                    f"escapes output directory"
                )
        except ValueError as e:
            if "path traversal" in str(e).lower():
                raise
            # Different drives on Windows — also reject
            raise ValueError(
                f"Invalid folder path: '{folder_path}' is on a different "
                f"drive than the output directory"
            ) from e

        # 6. Create directory recursively
        os.makedirs(target_dir_abs, exist_ok=True)

        # 7. Build filename based on save_mode
        if save_mode == "Sequential":
            counter = self._get_next_counter(
                target_dir_abs,
                filename_prefix,
                extension,
                counter_position,
                separator,
            )
            counter_str = str(counter).zfill(counter_digits)

            if counter_position == "Back":
                filename = f"{filename_prefix}{separator}{counter_str}.{extension}"
            else:  # Front
                filename = f"{counter_str}{separator}{filename_prefix}.{extension}"
        else:
            # Overwrite or Append — no counter
            filename = f"{filename_prefix}.{extension}"

        # 8. Build final file path
        file_path = os.path.join(target_dir_abs, filename)

        # 9. Write file
        if save_mode == "Append":
            # Smart newline: only prepend \n if file already has content
            prepend_newline = (
                os.path.exists(file_path) and os.path.getsize(file_path) > 0
            )
            with open(file_path, "a", encoding="utf-8") as f:
                if prepend_newline:
                    f.write("\n")
                f.write(text)
        else:
            # Sequential or Overwrite — write fresh
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)

        print(f"\033[92m[SBTools] Text saved: {file_path}\033[0m")

        return ()

    # ------------------------------------------------------------------
    # Sanitization helpers
    # ------------------------------------------------------------------

    def _sanitize_folder_path(self, path):
        """Sanitize folder path, preserving path separators (/ and \\)."""
        # Split by path separators, sanitize each component individually
        parts = re.split(r"[/\\]", path)
        forbidden = r'[<>:"|?*]'
        sanitized_parts = [re.sub(forbidden, "", part).strip() for part in parts]
        # Remove empty parts (from leading/trailing/double separators)
        sanitized_parts = [p for p in sanitized_parts if p]
        return os.sep.join(sanitized_parts)

    def _sanitize_filename(self, name):
        """Sanitize filename, removing all forbidden chars including path separators."""
        forbidden = r'[<>:"/\\|?*]'
        sanitized = re.sub(forbidden, "", name).strip()
        return sanitized if sanitized else "untitled"

    def _sanitize_extension(self, ext):
        """Sanitize extension, stripping leading dots and forbidden characters."""
        ext = ext.lstrip(".")
        forbidden = r'[<>:"/\\|?*.]'
        sanitized = re.sub(forbidden, "", ext).strip()
        return sanitized if sanitized else "txt"

    # ------------------------------------------------------------------
    # Counter logic
    # ------------------------------------------------------------------

    def _get_next_counter(self, directory, prefix, extension, position, separator):
        """Scan directory for existing files and return the next counter value.

        Uses os.scandir() for performance and matches any digit length
        for robustness (e.g., counter_digits changed between runs).
        """
        escaped_prefix = re.escape(prefix)
        escaped_sep = re.escape(separator)
        escaped_ext = re.escape(extension)

        if position == "Back":
            pattern = re.compile(
                rf"^{escaped_prefix}{escaped_sep}(\d+)\.{escaped_ext}$"
            )
        else:  # Front
            pattern = re.compile(
                rf"^(\d+){escaped_sep}{escaped_prefix}\.{escaped_ext}$"
            )

        max_counter = 0
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file():
                        match = pattern.match(entry.name)
                        if match:
                            counter_val = int(match.group(1))
                            if counter_val > max_counter:
                                max_counter = counter_val
        except OSError:
            pass

        return max_counter + 1


NODE_CLASS_MAPPINGS = {"SBTools_SaveText": SBTools_SaveText}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_SaveText": "Save Text (SBTools)"}
