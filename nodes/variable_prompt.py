# ComfyUI-SBTools - Prompt Variable Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

from .compiler_utils import CompilerUtils


class SBTools_VariablePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "tag_name": "Tag name for template replacement (e.g., GENDER, CLOTHING)",
            "values": "List of values, one per line. Use [condition] syntax for conditional values (e.g., [man&&suit]).",
            "randomize": "Enable random selection (off = sequential cycle through all values)",
            "prefix": "Text to add before value (only in tag mode, ignored if value is empty)",
            "suffix": "Text to add after value (only in tag mode, ignored if value is empty)",
            "var_list": "Optional: Connect previous variable to enable conditional logic based on its values",
        }
        return {
            "required": {
                "tag_name": (
                    "STRING",
                    {"default": "", "tooltip": tooltips["tag_name"]},
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
            },
            "optional": {
                "var_list": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
            },
        }

    RETURN_TYPES = ("VARIABLE_LIST",)
    RETURN_NAMES = ("VAR_LIST",)
    FUNCTION = "create_variable"
    CATEGORY = "SBTools/Prompt"
    OUTPUT_NODE = False

    def create_variable(
        self, tag_name, values, randomize, prefix, suffix, var_list=None
    ):
        # Inherit previous var_list
        result = list(var_list) if var_list else []

        # Auto-generate tag_name if empty
        if not tag_name or not tag_name.strip():
            # Use a unique ID based on object identity to avoid collisions
            # Even in parallel connections, each node instance gets a unique tag
            import time

            unique_id = int(time.time() * 1000000) % 1000000  # Microsecond timestamp
            tag_name = f"_VAR_{unique_id}"
            print(f"\033[90m[INFO] Auto-generated tag name: {tag_name}\033[0m")

        # Parse values text
        parsed = self._parse_values(values, result)

        # Create variable data
        if parsed["has_conditions"]:
            # Conditional variable
            variable_data = {
                "tag_name": tag_name,
                "values": parsed["values"],  # {"common": [...], "conditional": {...}}
                "exclusions": parsed.get(
                    "exclusions", {"common": [], "conditional": {}}
                ),
                "only_flags": parsed.get("only_flags", {}),
                "mode": "ConditionalRandom" if randomize else "Conditional",
                "prefix": prefix,
                "suffix": suffix,
            }
        else:
            # Normal variable
            variable_data = {
                "tag_name": tag_name,
                "values": parsed["values"],  # [...]
                "exclusions": parsed.get(
                    "exclusions", {"common": [], "conditional": {}}
                ),
                "only_flags": parsed.get("only_flags", {}),
                "mode": "Random" if randomize else "Sequential",
                "prefix": prefix,
                "suffix": suffix,
            }

        result.append(variable_data)
        return (result,)

    def _parse_values(self, values_text, previous_vars):
        """Parse values text with optional conditional syntax and exclusions"""
        lines = values_text.split("\n")

        common = []
        common_exclusions = []  # For --value syntax
        conditional = {}
        conditional_exclusions = {}  # For --value syntax in conditional blocks
        only_flags = {}  # Store --only flags for conditions
        has_conditions = False
        current_condition = None
        current_is_only = False  # Track if current condition has --only

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Handle [NONE] explicitly as empty value
            if stripped == "[NONE]":
                if current_condition is None:
                    common.append("")
                else:
                    if isinstance(current_condition, list):
                        for cond_key in current_condition:
                            if cond_key not in conditional:
                                conditional[cond_key] = []
                            conditional[cond_key].append("")
                continue

            # Check if condition line
            if stripped.startswith("[") and "]" in stripped:
                has_conditions = True

                # Parse condition line with options
                condition_part, is_only = self._parse_condition_line_with_options(
                    stripped
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
                else:
                    # Expand OR conditions into multiple condition keys
                    current_condition = CompilerUtils.expand_or_conditions(
                        condition_parts, previous_vars
                    )

                    # If --only flag is set, store it for these conditions
                    if current_is_only and current_condition:
                        for cond_key in current_condition:
                            only_flags[cond_key] = True

                    # Warn if condition didn't match anything
                    if not current_condition:
                        print(
                            f"\033[93m⚠️  WARNING: Condition '{stripped}' did not match any values in previous variables\033[0m"
                        )
                        print(
                            f"\033[93m   → Values following this condition will be ignored\033[0m"
                        )
            else:
                # Value line - check for exclusion syntax (--value)
                is_exclusion = stripped.startswith("--")
                if is_exclusion:
                    # Remove -- prefix
                    value_to_exclude = stripped[2:].strip()

                    if current_condition is None:
                        # Common exclusion
                        common_exclusions.append(value_to_exclude)
                    else:
                        # Conditional exclusion
                        if isinstance(current_condition, list):
                            if not current_condition:
                                print(
                                    f"\033[93m   → Ignoring exclusion: '--{value_to_exclude}'\033[0m"
                                )
                            else:
                                for cond_key in current_condition:
                                    if cond_key not in conditional_exclusions:
                                        conditional_exclusions[cond_key] = []
                                    conditional_exclusions[cond_key].append(
                                        value_to_exclude
                                    )
                else:
                    # Normal value line
                    if current_condition is None:
                        common.append(stripped)
                    else:
                        # current_condition is a list of condition keys (for OR expansion)
                        if isinstance(current_condition, list):
                            if not current_condition:
                                # Empty condition - value will be ignored
                                print(
                                    f"\033[93m   → Ignoring value: '{stripped}'\033[0m"
                                )
                            else:
                                # Multiple conditions (OR) - add to all
                                for cond_key in current_condition:
                                    if cond_key not in conditional:
                                        conditional[cond_key] = []
                                    conditional[cond_key].append(stripped)

        if has_conditions:
            return {
                "has_conditions": True,
                "values": {"common": common, "conditional": conditional},
                "exclusions": {
                    "common": common_exclusions,
                    "conditional": conditional_exclusions,
                },
                "only_flags": only_flags,
            }
        else:
            # No conditions - return simple list
            return {
                "has_conditions": False,
                "values": (
                    common
                    if common
                    else [
                        v.strip() for v in lines if v.strip() and v.strip() != "[NONE]"
                    ]
                ),
                "exclusions": {"common": common_exclusions, "conditional": {}},
                "only_flags": {},
            }

    def _parse_condition_line_with_options(self, line):
        """Parse condition line and extract --only option

        Input: "[man&&young] --only"
        Output: ("[man&&young]", True)

        Input: "[man]"
        Output: ("[man]", False)
        """
        if not line.startswith("["):
            return line, False

        # Find closing bracket
        end_bracket = line.find("]")
        if end_bracket == -1:
            return line, False

        # Condition is everything up to and including ]
        condition = line[: end_bracket + 1]

        # Options are everything after ]
        options_part = line[end_bracket + 1 :].strip()

        # Check for --only flag
        is_only = "--only" in options_part

        return condition, is_only


NODE_CLASS_MAPPINGS = {"SBTools_VariablePrompt": SBTools_VariablePrompt}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariablePrompt": "Variable Prompt (SBTools)"}
