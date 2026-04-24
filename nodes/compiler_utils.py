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
    def _enumerate_combinations_reversed(variables):
        """Enumerate combinations with last variable changing fastest

        Strategy: Generate normally (forward), then reorder results so last variable changes fastest
        """
        if not variables:
            return

        # Generate all combinations normally (forward order maintains dependencies)
        all_combos = list(CompilerUtils._enumerate_combinations(variables))

        if not all_combos:
            return

        # Reorder: Create index mapping for each combination
        # We need to sort by: (var0_index, var1_index, ..., varN_index)
        # where varN changes fastest (reverse of generation order)

        # Build value->index mappings for each variable
        value_indices = []
        for var in variables:
            mode = var.get("mode", "Sequential")

            if mode in ["Random", "ConditionalRandom"]:
                # Random variables don't affect ordering
                value_indices.append({})
            elif mode == "Sequential":
                values = var.get("values", [])
                idx_map = {v: i for i, v in enumerate(values)}
                value_indices.append(idx_map)
            elif mode == "Conditional":
                # For conditional, collect all possible values and assign indices
                values_dict = var.get("values", {})
                all_vals = []
                all_vals.extend(values_dict.get("common", []))
                for cond_vals in values_dict.get("conditional", {}).values():
                    for v in cond_vals:
                        if v not in all_vals:
                            all_vals.append(v)
                idx_map = {v: i for i, v in enumerate(all_vals)}
                value_indices.append(idx_map)
            else:
                value_indices.append({})

        # Sort combinations: last variable index changes fastest
        def sort_key(combo):
            # Return tuple of indices in REVERSE order (last var first in tuple)
            indices = []
            for i in range(len(variables) - 1, -1, -1):  # Reverse order
                val = combo[i]
                if isinstance(val, str) and val.startswith("[RANDOM"):
                    indices.append(0)  # Random values stay at 0
                else:
                    idx_map = value_indices[i]
                    indices.append(idx_map.get(val, 0))
            return tuple(indices)

        sorted_combos = sorted(all_combos, key=sort_key)

        for combo in sorted_combos:
            yield combo

    @staticmethod
    def _enumerate_combinations(variables, current_index=0, current_values=None):
        """Recursively enumerate all valid combinations (forward order, for legacy use)

        Note: This is the OLD implementation. Use _enumerate_combinations_reversed for correct order.
        """
        if current_values is None:
            current_values = {}

        # Base case: all variables resolved
        if current_index >= len(variables):
            # Return values in original variable order
            result = []
            for var in variables:
                result.append(current_values.get(var["tag_name"], ""))
            yield result
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
            values_dict = var.get("values", {})
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
                # No available values - use empty string and continue
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
        """Resolve index to actual values using cumulative combination count

        Returns: list of selected values in variable order
        """
        # Handle Random variables first
        random.seed(seed)
        random_values = {}
        for var in variables:
            if var.get("mode") == "Random":
                values = var.get("values", [])
                if isinstance(values, list) and values:
                    random_values[var["tag_name"]] = random.choice(values)

        # Build current values context and result
        current_values = {}
        result = []
        remaining_index = index

        # Resolve each variable in order using cumulative combination count
        for var_idx, var in enumerate(variables):
            tag_name = var["tag_name"]
            mode = var.get("mode", "Sequential")

            if mode == "Random":
                # Use pre-selected random value
                result.append(random_values[tag_name])
                current_values[tag_name] = random_values[tag_name]

            elif mode == "Sequential":
                values = var.get("values", [])
                if isinstance(values, list) and values:
                    # Calculate subsequent combinations for each value
                    value_combos = []
                    for value in values:
                        # Simulate selecting this value
                        test_context = dict(current_values)
                        test_context[tag_name] = value
                        # Count subsequent combinations
                        sub_count = CompilerUtils._count_subsequent_combinations(
                            variables, var_idx + 1, test_context
                        )
                        value_combos.append((value, sub_count))

                    # Find which value range the remaining_index falls into
                    cumulative = 0
                    selected_value = values[0]
                    for value, count in value_combos:
                        if remaining_index < cumulative + count:
                            selected_value = value
                            remaining_index -= cumulative
                            break
                        cumulative += count

                    result.append(selected_value)
                    current_values[tag_name] = selected_value
                else:
                    result.append("")

            elif mode == "Conditional":
                # Get available values based on current context
                values_dict = var.get("values", {})
                available = []

                # Add common values FIRST (written order)
                available.extend(values_dict.get("common", []))

                # Check conditional values AFTER
                for cond_key, cond_values in values_dict.get("conditional", {}).items():
                    cond_dict = dict(cond_key)
                    if CompilerUtils.matches_condition(cond_dict, current_values):
                        available.extend(cond_values)

                if available:
                    # Calculate subsequent combinations for each available value
                    value_combos = []
                    for value in available:
                        # Simulate selecting this value
                        test_context = dict(current_values)
                        test_context[tag_name] = value
                        # Count subsequent combinations
                        sub_count = CompilerUtils._count_subsequent_combinations(
                            variables, var_idx + 1, test_context
                        )
                        value_combos.append((value, sub_count))

                    # Find which value range the remaining_index falls into
                    cumulative = 0
                    selected_value = available[0]
                    for value, count in value_combos:
                        if remaining_index < cumulative + count:
                            selected_value = value
                            remaining_index -= cumulative
                            break
                        cumulative += count

                    result.append(selected_value)
                    current_values[tag_name] = selected_value
                else:
                    result.append("")
                    current_values[tag_name] = ""

            elif mode == "ConditionalRandom":
                # Resolve based on current context, then random select
                values_dict = var.get("values", {})
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
                    # Use image-specific seed if available
                    image_seed = var.get("seed", seed)
                    random.seed(image_seed)
                    selected = random.choice(available)
                    result.append(selected)
                    current_values[tag_name] = selected
                else:
                    result.append("")
                    current_values[tag_name] = ""

        return result

    @staticmethod
    def _count_subsequent_combinations(variables, start_index, current_context):
        """Count how many combinations are possible from start_index onwards

        Args:
            variables: list of all variables
            start_index: index to start counting from
            current_context: dict of tag_name -> value for already resolved variables

        Returns:
            int: number of combinations
        """
        # Base case: no more variables
        if start_index >= len(variables):
            return 1

        var = variables[start_index]
        mode = var.get("mode", "Sequential")

        if mode == "Random" or mode == "ConditionalRandom":
            # Random modes don't multiply combinations (always 1 choice per execution)
            return CompilerUtils._count_subsequent_combinations(
                variables, start_index + 1, current_context
            )

        elif mode == "Sequential":
            values = var.get("values", [])
            if not values:
                return 1

            # Sum combinations for each possible value
            total = 0
            for value in values:
                test_context = dict(current_context)
                test_context[var["tag_name"]] = value
                count = CompilerUtils._count_subsequent_combinations(
                    variables, start_index + 1, test_context
                )
                total += count
            return total

        elif mode == "Conditional":
            values_dict = var.get("values", {})
            available = []

            # Add common values
            available.extend(values_dict.get("common", []))

            # Add conditional values that match
            for cond_key, cond_values in values_dict.get("conditional", {}).items():
                cond_dict = dict(cond_key)
                if CompilerUtils.matches_condition(cond_dict, current_context):
                    available.extend(cond_values)

            if not available:
                # No available values - use empty string and continue counting
                test_context = dict(current_context)
                test_context[var["tag_name"]] = ""
                return CompilerUtils._count_subsequent_combinations(
                    variables, start_index + 1, test_context
                )

            # Sum combinations for each available value
            total = 0
            for value in available:
                test_context = dict(current_context)
                test_context[var["tag_name"]] = value
                count = CompilerUtils._count_subsequent_combinations(
                    variables, start_index + 1, test_context
                )
                total += count
            return total

        return 1

    @staticmethod
    def _check_unused_conditions(variables, all_combos):
        """Check for conditional values that are never used

        Returns: list of warning strings
        """
        warnings = []

        for var_idx, var in enumerate(variables):
            tag_name = var["tag_name"]
            mode = var.get("mode", "Sequential")

            # Only check Conditional mode (not ConditionalRandom)
            # ConditionalRandom values are selected at runtime, not during enumeration
            if mode != "Conditional":
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
        # Calculate total combinations
        max_combinations = CompilerUtils.calculate_combinations(variables)

        # Generate combinations using resolve_index (matches actual behavior perfectly)
        all_combos = []
        for index in range(min(max_combinations, max_display)):
            combo = CompilerUtils.resolve_index(index, variables, seed=0)

            # Format Random variables to show available choices
            formatted_combo = []
            for i, (var, value) in enumerate(zip(variables, combo)):
                mode = var.get("mode", "Sequential")
                var_type = var.get("type", "")

                if mode == "Random":
                    # Show all available choices for Random variables
                    values = var.get("values", [])
                    if isinstance(values, list) and values:
                        # For images, just show count; for text, show all choices
                        if var_type in ["Image", "image_folder"]:
                            formatted_combo.append(f"[RANDOM: {len(values)} images]")
                        else:
                            choices = [v if v else "(none)" for v in values]
                            choices_str = "|".join(str(c) for c in choices)
                            formatted_combo.append(f"[RANDOM: {choices_str}]")
                    else:
                        formatted_combo.append("[RANDOM]")
                elif mode == "ConditionalRandom":
                    # For ConditionalRandom, show available choices based on current context
                    values_dict = var.get("values", {})

                    # Build current context from previous variables
                    current_context = {}
                    for j in range(i):
                        prev_var = variables[j]
                        if prev_var.get("mode") not in ["Random", "ConditionalRandom"]:
                            current_context[prev_var["tag_name"]] = combo[j]

                    # Get available values
                    available = []
                    available.extend(values_dict.get("common", []))
                    for cond_key, cond_values in values_dict.get(
                        "conditional", {}
                    ).items():
                        cond_dict = dict(cond_key)
                        if CompilerUtils.matches_condition(cond_dict, current_context):
                            available.extend(cond_values)

                    if available:
                        # For images, just show count; for text, show all choices
                        if var_type in ["Image", "image_folder"]:
                            formatted_combo.append(f"[RANDOM: {len(available)} images]")
                        else:
                            choices = [v if v else "(none)" for v in available]
                            choices_str = "|".join(choices)
                            formatted_combo.append(f"[RANDOM: {choices_str}]")
                    else:
                        formatted_combo.append("[RANDOM: (none)]")
                else:
                    formatted_combo.append(value)

            all_combos.append(formatted_combo)

        # Check for unused conditional values
        enumerated_combos = list(CompilerUtils._enumerate_combinations(variables))
        unused_warnings = CompilerUtils._check_unused_conditions(
            variables, enumerated_combos
        )

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

        for i, combo in enumerate(all_combos):
            # Convert empty strings to (none), but keep [RANDOM: ...] as is
            display_combo = []
            for j, v in enumerate(combo):
                v_str = str(v)
                if v_str == "" or v_str == "None":
                    display_combo.append("(none)")
                else:
                    # Check if this is an image variable (contains path separators)
                    if j < len(variables):
                        var_type = variables[j].get("type", "")
                        if (
                            var_type in ["Image", "image_folder"]
                            and "\\" in v_str
                            or "/" in v_str
                        ):
                            # Extract just the filename for images
                            import os

                            display_combo.append(os.path.basename(v_str))
                        else:
                            display_combo.append(v_str)
                    else:
                        display_combo.append(v_str)

            # Format with newlines for image variables
            formatted_parts = []
            image_counter = 1
            for j, (var, display_val) in enumerate(zip(variables, display_combo)):
                var_type = var.get("type", "")

                if var_type in ["Image", "image_folder"]:
                    # Use image1, image2, etc. to match Variable Builder output
                    formatted_parts.append(f"\n  image{image_counter}: {display_val}")
                    image_counter += 1
                else:
                    formatted_parts.append(display_val)

            # Join text variables with ", " and image variables are already formatted with newlines
            text_parts = [p for p in formatted_parts if not p.startswith("\n")]
            image_parts = [p for p in formatted_parts if p.startswith("\n")]

            if text_parts:
                values_str = ", ".join(text_parts)
            else:
                values_str = ""

            if image_parts:
                values_str += "".join(image_parts)

            lines.append(f"index {i}: {values_str}")

        if max_combinations > max_display:
            lines.append(
                f"\n... and {max_combinations - max_display} more combinations"
            )

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

    @staticmethod
    def _reorder_to_little_endian(combinations, variables):
        """Reorder combinations from big-endian to little-endian to match resolve_index

        Big-endian (enumerate): First variable fixed, iterate through rest
        Little-endian (resolve): First variable changes fastest (modulo)
        """
        if not combinations:
            return combinations

        # Get only Sequential and Conditional variables (ignore Random)
        sequential_vars = [
            v
            for v in variables
            if v.get("mode") in ["Sequential", "Conditional", "ConditionalRandom"]
        ]

        if len(sequential_vars) <= 1:
            return combinations  # No reordering needed

        # Check if any conditional variables exist
        has_conditional = any(
            v.get("mode") in ["Conditional", "ConditionalRandom"]
            for v in sequential_vars
        )

        if has_conditional:
            # With conditional variables, stride calculation is complex
            # Skip reordering for now
            # TODO: Implement proper reordering for conditional variables
            return combinations

        # Calculate stride sizes for each variable
        strides = []
        for var in sequential_vars:
            # Count how many values this variable can have in current context
            mode = var.get("mode")
            if mode == "Sequential":
                stride = len(var.get("values", []))
            elif mode in ["Conditional", "ConditionalRandom"]:
                # For conditional, use common + all conditional values
                values_dict = var.get("values", {})
                common = values_dict.get("common", [])
                conditional_all = []
                for cond_vals in values_dict.get("conditional", {}).values():
                    conditional_all.extend(cond_vals)
                stride = len(common) + len(conditional_all)
            else:
                stride = 1
            strides.append(stride)

        # Create index mapping from big-endian to little-endian
        total = len(combinations)
        reordered = [None] * total

        for big_endian_idx in range(total):
            # Convert big-endian index to variable indices
            remaining = big_endian_idx
            var_indices = []
            for stride in reversed(strides):  # Right to left for big-endian
                if stride > 0:
                    var_indices.insert(0, remaining % stride)
                    remaining //= stride
                else:
                    var_indices.insert(0, 0)

            # Convert variable indices to little-endian index
            little_endian_idx = 0
            multiplier = 1
            for var_idx, stride in zip(
                var_indices, strides
            ):  # Left to right for little-endian
                little_endian_idx += var_idx * multiplier
                multiplier *= stride

            reordered[little_endian_idx] = combinations[big_endian_idx]

        return reordered
