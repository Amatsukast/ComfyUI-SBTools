# ComfyUI-SBTools - Prompt Compiler Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import itertools
import re
import random


class SBTools_PromptCompiler:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "template": "Template text with [TAG_NAME] tags (e.g., 'A [AGE] [GENDER][CLOTHING].'). Leave empty for simple join mode.",
            "index": "Index to select which Sequential combination (loops automatically)",
            "seed": "Seed for Random variables (use Primitive with increment for random batch)",
            "separator": "Separator to join values (used for unused variables and empty template mode)",
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
                "var_list": ("VARIABLE_LIST",),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("prompt", "max_combinations", "all_combinations")
    FUNCTION = "compile_prompt"
    CATEGORY = "SBTools/Prompt"
    OUTPUT_NODE = False

    def compile_prompt(self, **kwargs):
        # Extract parameters from kwargs (more robust than positional args)
        template = kwargs.get("template", "")
        index = kwargs.get("index", 0)
        seed = kwargs.get("seed", 0)
        separator = kwargs.get("separator", ", ")

        # Get variables from var_list
        var_list = kwargs.get("var_list", [])
        variables = var_list if var_list else []

        # If no variables connected, return empty
        if not variables:
            return ("", 1, "")

        # Separate Sequential and Random variables
        sequential_vars = [v for v in variables if v["mode"] == "Sequential"]
        random_vars = [v for v in variables if v["mode"] == "Random"]

        # Calculate Sequential combinations
        if sequential_vars:
            sequential_value_lists = [var["values"] for var in sequential_vars]
            all_combinations = list(itertools.product(*sequential_value_lists))
            max_combinations = len(all_combinations)
        else:
            # No Sequential variables, just one "combination"
            all_combinations = [()]
            max_combinations = 1

        # Handle empty case
        if max_combinations == 0:
            return ("", 1, "")

        # Loop index (modulo to wrap around)
        safe_index = index % max_combinations

        # Get the selected Sequential combination
        selected_sequential = all_combinations[safe_index]

        # Select Random values based on seed
        random.seed(seed)
        selected_random = [random.choice(var["values"]) for var in random_vars]

        # Merge Sequential and Random values (preserve original order)
        selected_values = self._merge_values(
            variables, selected_sequential, selected_random
        )

        # Build prompt
        if template.strip():
            # Template mode: replace [TAG_NAME] tags and append unused variables
            prompt = self._apply_template(
                template, variables, selected_values, separator
            )
            # Debug output for template mode
            all_combinations_text = self._generate_debug_template(
                template, variables, all_combinations, random_vars, separator
            )
        else:
            # Simple join mode with prefix/suffix (filter out empty values)
            formatted_values = []
            for var, value in zip(variables, selected_values):
                if value != "":
                    # Apply prefix/suffix
                    formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                    formatted_values.append(formatted)
            prompt = separator.join(formatted_values)
            # Debug output for simple mode
            all_combinations_text = self._generate_debug_simple(
                separator, variables, all_combinations, random_vars
            )

        return (prompt, max_combinations, all_combinations_text)

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
        self, template, all_vars, seq_combinations, rand_vars, separator
    ):
        """Generate debug output for template mode."""
        # Use seed=0 for Random variables in debug output
        random.seed(0)
        fixed_random = [random.choice(var["values"]) for var in rand_vars]

        lines = []
        for i, seq_combo in enumerate(seq_combinations):
            merged = self._merge_values(all_vars, seq_combo, fixed_random)
            prompt = self._apply_template(template, all_vars, merged, separator)
            lines.append(f"index {i}: {prompt}")

        if rand_vars:
            lines.append("\n(Random variables shown with seed=0)")

        return "\n".join(lines)

    def _generate_debug_simple(self, separator, all_vars, seq_combinations, rand_vars):
        """Generate debug output for simple join mode."""
        # Use seed=0 for Random variables in debug output
        random.seed(0)
        fixed_random = [random.choice(var["values"]) for var in rand_vars]

        lines = []
        for i, seq_combo in enumerate(seq_combinations):
            merged = self._merge_values(all_vars, seq_combo, fixed_random)
            # Apply prefix/suffix to each value
            formatted_values = []
            for var, value in zip(all_vars, merged):
                if value != "":
                    formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                    formatted_values.append(formatted)
            prompt = separator.join(formatted_values)
            lines.append(f"index {i}: {prompt}")

        if rand_vars:
            lines.append("\n(Random variables shown with seed=0)")

        return "\n".join(lines)

    def _apply_template(self, template, variables, selected_values, separator):
        """Apply template replacement with [TAG_NAME] tags and append unused variables."""
        result = template

        # Extract all tags from template
        tags_in_template = set(re.findall(r"\[([^\]]+)\]", template))

        # Create mapping with variable metadata and track index
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
                # Apply prefix/suffix only if value is not empty
                if data["value"] != "":
                    replacement = f"{data['prefix']}{data['value']}{data['suffix']}"
                else:
                    replacement = ""  # Empty value = no prefix/suffix

                result = result.replace(tag, replacement)
                used_tags.add(tag_name)

        # Collect unused variables with prefix/suffix (filter out empty values)
        unused_values = []
        for tag_name, data in sorted(tag_data.items(), key=lambda x: x[1]["index"]):
            if tag_name not in used_tags and data["value"] != "":
                # Apply prefix/suffix to unused variables too
                formatted_value = f"{data['prefix']}{data['value']}{data['suffix']}"
                unused_values.append(formatted_value)

        # Warning: Tags in template with no matching variable
        unmatched_tags = tags_in_template - used_tags
        if unmatched_tags:
            for tag_name in unmatched_tags:
                print(
                    f"\033[93m[WARNING] Tag '[{tag_name}]' in template has no matching variable\033[0m"
                )

        # Clean up spaces (punctuation before spaces, multiple spaces)
        result = re.sub(
            r"\s+([.,!?;:])", r"\1", result
        )  # Remove space before punctuation
        result = re.sub(r"\s+", " ", result).strip()

        # Append unused variables to the end
        if unused_values:
            if result:  # If result is not empty, add separator
                result += separator
            result += separator.join(unused_values)

        return result


NODE_CLASS_MAPPINGS = {"SBTools_PromptCompiler": SBTools_PromptCompiler}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_PromptCompiler": "Prompt Compiler (SBTools)"}
