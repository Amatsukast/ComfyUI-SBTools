# ComfyUI-SBTools - Compiler Utilities
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import re
import random


class CompilerUtils:
    """Shared logic for all compiler nodes"""

    @staticmethod
    def normalize_condition_syntax(line):
        """Normalize all condition syntaxes to unified format

        Converts: AND → &&, OR → ||
        Full-width support: ＆＆ → &&, ｜｜ → ||, ： → :, 　 → space
        Returns: normalized string
        """
        if not line.startswith("[") or not line.endswith("]"):
            return line

        content = line[1:-1]

        # Full-width space to half-width (for proper strip() later)
        content = content.replace("　", " ")

        # English keywords (UPPERCASE only, case sensitive)
        # Use word boundaries to avoid matching "or" in "orange" or "and" in "hand"
        content = re.sub(r"\bAND\b", "&&", content)
        content = re.sub(r"\bOR\b", "||", content)

        # Full-width to half-width
        content = content.replace("＆＆", "&&")
        content = content.replace("｜｜", "||")
        content = content.replace("：", ":")  # For tag name specification

        return f"[{content}]"

    @staticmethod
    def parse_condition_line(line):
        """Parse condition line into structured format

        Input: "[man&&suit||casual]"
        Output: [[("man", None)], [("suit", None), ("casual", None)]]

        With tag: "[GENDER:man&&suit]"
        Output: [[("man", "GENDER")], [("suit", None)]]
        """
        if not line.startswith("[") or not line.endswith("]"):
            return None

        content = line[1:-1].strip()

        # Special case: [*] = wildcard all
        if content == "*":
            return [[("*", None)]]

        # Split by && (AND/hierarchy)
        and_parts = content.split("&&")

        result = []
        for part in and_parts:
            # Split by || (OR)
            or_values = part.split("||")

            or_group = []
            for value in or_values:
                value = value.strip()

                # Check for tag name (GENDER:man)
                if ":" in value:
                    tag, val = value.split(":", 1)
                    or_group.append((val.strip(), tag.strip()))
                else:
                    or_group.append((value, None))

            result.append(or_group)

        return result

    @staticmethod
    def resolve_condition_tags(condition_parts, previous_vars):
        """Map condition values to tag names

        Input: [[("man", None)], [("suit", "CLOTHING")]]
        previous_vars: [GENDER_var, AGE_var, CLOTHING_var]

        Output: {"GENDER": "man", "CLOTHING": "suit"}
        """
        resolved = {}

        for or_group in condition_parts:
            for value, explicit_tag in or_group:
                if value == "*":
                    # Wildcard - will be handled during matching
                    continue

                if explicit_tag:
                    # Tag explicitly specified
                    resolved[explicit_tag] = value
                    break  # Only use first match in OR group
                else:
                    # Auto-detect from previous variables
                    for var in previous_vars:
                        tag_name = var["tag_name"]

                        # Skip if already assigned
                        if tag_name in resolved:
                            continue

                        # Check if value exists in this variable
                        if CompilerUtils._value_exists_in_var(value, var):
                            resolved[tag_name] = value
                            break
                    else:
                        # Value found, no need to check other OR values
                        break

        return resolved

    @staticmethod
    def expand_or_conditions(condition_parts, previous_vars):
        """Expand OR conditions into multiple condition keys

        Input: [[("suit", None), ("casual", None)]]  # OR condition
        Output: [("CLOTHING", "suit"), ("CLOTHING", "casual")]  # Two separate keys

        Input: [[("man", None)], [("suit", None), ("casual", None)]]  # AND + OR
        Output: [
            (("GENDER", "man"), ("CLOTHING", "suit")),
            (("GENDER", "man"), ("CLOTHING", "casual"))
        ]
        """
        import itertools

        # Separate AND parts and OR parts
        and_resolved = []
        or_groups = []

        for or_group in condition_parts:
            if len(or_group) > 1:
                # OR condition - expand later
                or_values = []
                for value, explicit_tag in or_group:
                    if value == "*":
                        # Wildcard - skip in OR group (means "any value")
                        continue

                    if explicit_tag:
                        or_values.append((explicit_tag, value))
                    else:
                        # Auto-detect
                        for var in previous_vars:
                            if CompilerUtils._value_exists_in_var(value, var):
                                or_values.append((var["tag_name"], value))
                                break
                if or_values:  # Only add if not empty
                    or_groups.append(or_values)
            else:
                # Single value (AND part)
                value, explicit_tag = or_group[0]
                if value == "*":
                    # Wildcard - skip, means "don't filter by this level"
                    continue

                if explicit_tag:
                    and_resolved.append((explicit_tag, value))
                else:
                    for var in previous_vars:
                        if CompilerUtils._value_exists_in_var(value, var):
                            and_resolved.append((var["tag_name"], value))
                            break

        # Expand OR combinations
        if or_groups:
            # Generate all combinations
            all_combinations = list(itertools.product(*or_groups))
            result = []
            for combo in all_combinations:
                # Combine AND parts with this OR combination
                combined = tuple(sorted(and_resolved + list(combo)))
                result.append(combined)
            return result
        else:
            # No OR conditions - return single tuple
            if and_resolved:
                return [tuple(sorted(and_resolved))]
            else:
                # No conditions at all - return empty (should not happen)
                return []

    @staticmethod
    def _value_exists_in_var(value, var):
        """Check if value exists in variable's values"""
        values = var.get("values", [])

        if isinstance(values, dict):
            # Conditional variable
            if value in values.get("common", []):
                return True
            for cond_values in values.get("conditional", {}).values():
                if value in cond_values:
                    return True
            return False
        else:
            # Simple list
            return value in values

    @staticmethod
    def matches_condition(condition_dict, current_values_dict):
        """Check if condition matches current values

        condition_dict: {"CLOTHING": "suit"}  # [*&&suit] becomes just suit check
        current_values_dict: {"GENDER": "man", "CLOTHING": "casual"}

        Returns: True if all conditions match
        """
        for tag, expected_value in condition_dict.items():
            if tag not in current_values_dict:
                return False

            if expected_value == "*":
                # Wildcard for this tag - always matches
                continue

            if current_values_dict[tag] != expected_value:
                return False

        return True

    @staticmethod
    def calculate_combinations(variables):
        """Calculate total combinations including conditional variables

        Uses lazy evaluation approach - doesn't generate all combinations
        """
        # Separate by mode
        independent_vars = []
        conditional_vars = []

        for var in variables:
            if var.get("mode") in ["Conditional", "ConditionalRandom"]:
                conditional_vars.append(var)
            elif var.get("mode") in ["Sequential", "Random"]:
                independent_vars.append(var)

        if not conditional_vars:
            # No conditional variables - use simple product
            sequential = [v for v in independent_vars if v["mode"] == "Sequential"]
            if not sequential:
                return 1

            total = 1
            for var in sequential:
                total *= len(var["values"])
            return total

        # With conditional variables - need to calculate per condition
        # This is a simplified version - full implementation would enumerate
        # For now, return estimate
        sequential = [v for v in variables if v.get("mode") == "Sequential"]
        if not sequential:
            return 1

        # Build dependency graph and calculate
        return CompilerUtils._calculate_conditional_combinations(variables)

    @staticmethod
    def _calculate_conditional_combinations(variables):
        """Calculate combinations with conditional variables"""
        # Enumerate all actual combinations
        all_combos = list(CompilerUtils._enumerate_combinations(variables))
        return len(all_combos)

    @staticmethod
    def _enumerate_combinations(variables, current_index=0, current_values=None):
        """Recursively enumerate all valid combinations"""
        if current_values is None:
            current_values = {}

        # Base case: all variables resolved
        if current_index >= len(variables):
            yield list(current_values.values())
            return

        var = variables[current_index]
        tag_name = var["tag_name"]
        mode = var.get("mode", "Sequential")

        if mode == "Random":
            # Random variables don't contribute to combinations
            # Show available choices
            values = var["values"]
            if isinstance(values, list) and values:
                # Convert empty strings to (none)
                choices = [v if v else "(none)" for v in values]
                choices_str = "|".join(str(c) for c in choices)
                current_values[tag_name] = f"[RANDOM: {choices_str}]"
            else:
                current_values[tag_name] = "[RANDOM]"
            yield from CompilerUtils._enumerate_combinations(
                variables, current_index + 1, current_values
            )

        elif mode == "Sequential":
            values = var["values"]
            if isinstance(values, list):
                # Simple sequential - iterate all values
                for value in values:
                    current_values[tag_name] = value
                    yield from CompilerUtils._enumerate_combinations(
                        variables, current_index + 1, dict(current_values)
                    )
            else:
                # Should not happen for Sequential
                current_values[tag_name] = ""
                yield from CompilerUtils._enumerate_combinations(
                    variables, current_index + 1, current_values
                )

        elif mode == "Conditional":
            # Get available values based on current context
            values_dict = var["values"]
            available = []

            # Add common values FIRST (written order)
            available.extend(values_dict.get("common", []))

            # Add conditional values that match AFTER
            for cond_key, cond_values in values_dict.get("conditional", {}).items():
                cond_dict = dict(cond_key)
                if CompilerUtils.matches_condition(cond_dict, current_values):
                    available.extend(cond_values)

            # Iterate through available values
            if available:
                for value in available:
                    current_values[tag_name] = value
                    yield from CompilerUtils._enumerate_combinations(
                        variables, current_index + 1, dict(current_values)
                    )
            else:
                # No available values - use empty
                current_values[tag_name] = ""
                yield from CompilerUtils._enumerate_combinations(
                    variables, current_index + 1, current_values
                )

        elif mode == "ConditionalRandom":
            # Random within conditional context - show actual choices
            values_dict = var["values"]
            available = []

            # Add common values FIRST (written order)
            available.extend(values_dict.get("common", []))

            # Add conditional values that match AFTER
            for cond_key, cond_values in values_dict.get("conditional", {}).items():
                cond_dict = dict(cond_key)
                if CompilerUtils.matches_condition(cond_dict, current_values):
                    available.extend(cond_values)

            # Display as [RANDOM: choice1|choice2|...]
            if available:
                # Convert empty strings to (none)
                choices = [v if v else "(none)" for v in available]
                choices_str = "|".join(choices)
                current_values[tag_name] = f"[RANDOM: {choices_str}]"
            else:
                current_values[tag_name] = "[RANDOM: (none)]"

            yield from CompilerUtils._enumerate_combinations(
                variables, current_index + 1, current_values
            )

    @staticmethod
    def resolve_index(index, variables, seed=0):
        """Resolve index to actual values using lazy evaluation

        Returns: list of selected values in variable order
        """
        # Separate Random and Sequential
        sequential_vars = [v for v in variables if v.get("mode") == "Sequential"]
        random_vars = [v for v in variables if v.get("mode") == "Random"]
        conditional_vars = [v for v in variables if v.get("mode") == "Conditional"]

        # Handle Random variables
        random.seed(seed)
        random_values = {}
        for var in random_vars:
            values = var["values"]
            if isinstance(values, list):
                random_values[var["tag_name"]] = random.choice(values)

        # Build current values context
        current_values = {}
        result = []

        # Resolve Sequential and Conditional in order
        remaining_index = index

        for var in variables:
            tag_name = var["tag_name"]
            mode = var.get("mode", "Sequential")

            if mode == "Random":
                # Use pre-selected random value
                result.append(random_values[tag_name])
                current_values[tag_name] = random_values[tag_name]

            elif mode == "Sequential":
                values = var["values"]
                if isinstance(values, list):
                    # Simple sequential
                    idx = remaining_index % len(values)
                    remaining_index //= len(values)
                    result.append(values[idx])
                    current_values[tag_name] = values[idx]

            elif mode == "Conditional":
                # Resolve based on current context
                values_dict = var["values"]
                available = []

                # Add common values FIRST (written order)
                available.extend(values_dict.get("common", []))

                # Check conditional values AFTER
                for cond_key, cond_values in values_dict.get("conditional", {}).items():
                    cond_dict = dict(cond_key)
                    if CompilerUtils.matches_condition(cond_dict, current_values):
                        available.extend(cond_values)

                if available:
                    idx = remaining_index % len(available)
                    remaining_index //= len(available)
                    result.append(available[idx])
                    current_values[tag_name] = available[idx]
                else:
                    result.append("")

            elif mode == "ConditionalRandom":
                # Resolve based on current context, then random select
                values_dict = var["values"]
                available = []

                # Add common values FIRST (written order)
                available.extend(values_dict.get("common", []))

                # Check conditional values AFTER
                for cond_key, cond_values in values_dict.get("conditional", {}).items():
                    cond_dict = dict(cond_key)
                    if CompilerUtils.matches_condition(cond_dict, current_values):
                        available.extend(cond_values)

                # Random selection from available
                if available:
                    random.seed(seed)
                    selected = random.choice(available)
                    result.append(selected)
                    current_values[tag_name] = selected
                else:
                    result.append("")

        return result

    @staticmethod
    def _check_unused_conditions(variables, all_combos):
        """Check for conditional values that are never used

        Returns: list of warning strings
        """
        warnings = []

        for var_idx, var in enumerate(variables):
            tag_name = var["tag_name"]
            mode = var.get("mode", "Sequential")

            # Only check Conditional and ConditionalRandom modes
            if mode not in ["Conditional", "ConditionalRandom"]:
                continue

            values_dict = var["values"]
            conditional = values_dict.get("conditional", {})

            # Track which conditional values were actually used
            used_conditions = set()

            # Check all combinations to see which conditional values appear
            for combo in all_combos:
                if var_idx < len(combo):
                    value = combo[var_idx]
                    # Skip [RANDOM: ...] placeholders
                    if isinstance(value, str) and value.startswith("[RANDOM:"):
                        continue
                    # Check which condition produced this value
                    for cond_key, cond_values in conditional.items():
                        if value in cond_values:
                            used_conditions.add(cond_key)

            # Find unused conditions
            all_conditions = set(conditional.keys())
            unused_conditions = all_conditions - used_conditions

            if unused_conditions:
                for cond_key in sorted(unused_conditions):
                    cond_values = conditional[cond_key]
                    # Format condition for display
                    cond_parts = []
                    for cond_tag, cond_value in cond_key:
                        if cond_value == "*":
                            cond_parts.append(f"{cond_tag}:*")
                        else:
                            cond_parts.append(f"{cond_tag}:{cond_value}")
                    cond_str = " AND ".join(cond_parts)

                    # Format values
                    values_str = ", ".join(
                        [f'"{v}"' if v else "(empty)" for v in cond_values]
                    )

                    warnings.append(
                        f"Variable '{tag_name}': Condition [{cond_str}] never matched\n"
                        f"  → Unused values: {values_str}"
                    )

        return warnings

    @staticmethod
    def generate_all_combinations_text(variables, max_display=100):
        """Generate text showing all combinations (for debug output)"""
        all_combos = list(CompilerUtils._enumerate_combinations(variables))

        # Check for unused conditional values
        unused_warnings = CompilerUtils._check_unused_conditions(variables, all_combos)

        lines = []

        # Add warnings at the top if any
        if unused_warnings:
            lines.append("=" * 70)
            lines.append("⚠️  WARNING: Unused conditional values detected")
            lines.append("=" * 70)
            for warning in unused_warnings:
                lines.append(warning)
            lines.append("=" * 70)
            lines.append("")

        for i, combo in enumerate(all_combos[:max_display]):
            # Convert empty strings to (none), but keep [RANDOM: ...] as is
            display_combo = []
            for v in combo:
                v_str = str(v)
                if v_str == "" or v_str == "None":
                    display_combo.append("(none)")
                else:
                    display_combo.append(v_str)
            values_str = ", ".join(display_combo)
            lines.append(f"index {i}: {values_str}")

        if len(all_combos) > max_display:
            lines.append(f"\n... and {len(all_combos) - max_display} more combinations")

        return "\n".join(lines)

    @staticmethod
    def merge_values(all_vars, seq_values, rand_values):
        """Merge Sequential and Random values in original variable order"""
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

    @staticmethod
    def apply_template(template, variables, selected_values, separator):
        """Apply template replacement with [TAG_NAME] tags and append unused variables"""
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

    @staticmethod
    def apply_simple_join(variables, selected_values, separator):
        """Simple join mode with prefix/suffix (filter out empty values)"""
        formatted_values = []
        for var, value in zip(variables, selected_values):
            if value != "":
                formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                formatted_values.append(formatted)
        return separator.join(formatted_values)
