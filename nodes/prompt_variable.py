# ComfyUI-SBTools - Prompt Variable Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0


class SBTools_PromptVariable:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "tag_name": "Tag name for template replacement (e.g., GENDER, CLOTHING)",
            "values": "List of values, one per line. Empty line or [NONE] = no value",
            "randomize": "Enable random selection (off = sequential cycle through all values)",
            "prefix": "Text to add before value (only in tag mode, ignored if value is empty)",
            "suffix": "Text to add after value (only in tag mode, ignored if value is empty)",
        }
        return {
            "required": {
                "tag_name": (
                    "STRING",
                    {"default": "TAG", "tooltip": tooltips["tag_name"]},
                ),
                "values": (
                    "STRING",
                    {
                        "default": "value1\nvalue2\nvalue3",
                        "multiline": True,
                        "tooltip": tooltips["values"],
                    },
                ),
                "randomize": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["randomize"]},
                ),
                "prefix": (
                    "STRING",
                    {"default": "", "tooltip": tooltips["prefix"]},
                ),
                "suffix": (
                    "STRING",
                    {"default": "", "tooltip": tooltips["suffix"]},
                ),
            }
        }

    RETURN_TYPES = ("VARIABLE_LIST",)
    RETURN_NAMES = ("var_list",)
    FUNCTION = "create_variable"
    CATEGORY = "SBTools/Prompt"
    OUTPUT_NODE = False

    def create_variable(self, tag_name, values, randomize, prefix, suffix):
        # Split by newline (keep empty lines)
        raw_values = values.split("\n")

        # Process values: empty line or [NONE] → empty string
        value_list = []
        for v in raw_values:
            stripped = v.strip()
            if stripped == "" or stripped == "[NONE]":
                value_list.append("")  # Keep empty string as valid value
            elif stripped:  # Non-empty value
                value_list.append(stripped)
            # else: skip completely empty lines at edges

        # Create variable data dictionary
        variable_data = {
            "tag_name": tag_name,
            "values": value_list,
            "mode": "Random" if randomize else "Sequential",
            "prefix": prefix,
            "suffix": suffix,
        }

        # Return as a single-element list
        return ([variable_data],)


NODE_CLASS_MAPPINGS = {"SBTools_PromptVariable": SBTools_PromptVariable}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_PromptVariable": "Prompt Variable (SBTools)"}
