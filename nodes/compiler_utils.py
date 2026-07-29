# ComfyUI-SBTools - Compiler Utilities
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

import re
import random
import zlib


# Exact combination counting is capped here. A graph with conditional variables can
# describe astronomically many combinations (values multiply per variable), and the
# count used to be obtained by materializing every combination in a list - which was
# enough to exhaust system memory. Past this many, callers get the cap back and
# resolve_index switches to a non-counting strategy.
COMBINATION_LIMIT = 100_000


class CompilerUtils:
    """Shared logic for all compiler nodes"""

    @staticmethod
    def normalize_condition_syntax(line):
        """Normalize all condition syntaxes to unified format

        Converts: AND -> &&, OR -> ||
        Full-width support: ＆＆ -> &&, ｜｜ -> ||, ： -> :, 　 -> space
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
    def warn_unparsed_condition_tail(line, options_part, known_flags):
        """Warn when a condition line has content past the first ']'.

        Only the first bracketed group is the condition - everything after it is read
        as flags and anything unrecognised is dropped. Writing [A]&&[B] therefore
        silently applied [A] alone. A condition is one bracketed expression: combine
        terms with && / || *inside* it, e.g. [A||B&&C].
        """
        leftover = options_part
        for flag in known_flags:
            leftover = leftover.replace(flag, " ")
        leftover = leftover.strip()

        if not leftover:
            return

        print(
            f"\033[93m[WARNING] Ignoring '{leftover}' in condition line "
            f"'{line.strip()}'\033[0m"
        )
        print(
            "\033[93m   -> Only the first [...] group is the condition. Combine terms "
            "inside one bracket instead, e.g. [A||B&&C].\033[0m"
        )

    @staticmethod
    def parse_condition_line(line):
        """Parse condition line into structured format

        Input: "[man&&suit||casual]"
        Output: [[("man", None, False)], [("suit", None, False), ("casual", None, False)]]

        With tag: "[GENDER:man&&suit]"
        Output: [[("man", "GENDER", False)], [("suit", None, False)]]

        With NOT: "[man&&!young]"
        Output: [[("man", None, False)], [("young", None, True)]]
        """
        if not line.startswith("[") or not line.endswith("]"):
            return None

        content = line[1:-1].strip()

        # Special case: [*] = wildcard all
        if content == "*":
            return [[("*", None, False)]]

        # Split by && (AND/hierarchy)
        and_parts = content.split("&&")

        result = []
        for part in and_parts:
            # Split by || (OR)
            or_values = part.split("||")

            or_group = []
            for value in or_values:
                value = value.strip()

                # Check for NOT operator (!)
                is_negated = False
                if value.startswith("!"):
                    is_negated = True
                    value = value[1:].strip()

                # Check for tag name (GENDER:man)
                if ":" in value:
                    tag, val = value.split(":", 1)
                    or_group.append((val.strip(), tag.strip(), is_negated))
                else:
                    or_group.append((value, None, is_negated))

            result.append(or_group)

        return result

    @staticmethod
    def expand_or_conditions(condition_parts, previous_vars):
        """Expand OR conditions into multiple condition keys

        Input: [[("suit", None, False), ("casual", None, False)]]  # OR condition
        Output: [(("CLOTHING", ("suit", False)),), (("CLOTHING", ("casual", False)),)]

        Input: [[("man", None, False)], [("suit", None, False), ("casual", None, False)]]  # AND + OR
        Output: [
            (("GENDER", ("man", False)), ("CLOTHING", ("suit", False))),
            (("GENDER", ("man", False)), ("CLOTHING", ("casual", False)))
        ]

        Note: Returns tuple of 2-tuples to allow dict() conversion
        """
        import itertools

        # Separate AND parts and OR parts
        and_resolved = []
        or_groups = []

        for or_group in condition_parts:
            if len(or_group) > 1:
                # OR condition - expand later
                or_values = []
                for value, explicit_tag, is_negated in or_group:
                    if value == "*":
                        # Wildcard - skip in OR group (means "any value")
                        continue

                    resolved = CompilerUtils._resolve_condition_term(
                        value, explicit_tag, is_negated, previous_vars
                    )
                    if resolved is not None:
                        or_values.append(resolved)
                if or_values:  # Only add if not empty
                    or_groups.append(or_values)
            else:
                # Single value (AND part)
                value, explicit_tag, is_negated = or_group[0]
                if value == "*":
                    # Wildcard - skip, means "don't filter by this level"
                    continue

                resolved = CompilerUtils._resolve_condition_term(
                    value, explicit_tag, is_negated, previous_vars
                )
                if resolved is not None:
                    and_resolved.append(resolved)

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
    def _resolve_condition_term(value, explicit_tag, is_negated, previous_vars):
        """Resolve one condition term to (tag_name, (value, is_negated)).

        Returns None when the term cannot be resolved at all.

        Diagnostics only - the resolution behaviour is unchanged. An explicit
        [TAG:value] used to be accepted with no checking whatsoever, so a typo, or
        a reference to a variable connected AFTER this one, produced a condition
        that silently never matched.
        """
        if explicit_tag:
            target = None
            for var in previous_vars:
                if var.get("tag_name") == explicit_tag:
                    target = var
                    break

            if target is None:
                print(
                    f"\033[93m[WARNING] Condition [{explicit_tag}:{value}] refers to "
                    f"unknown tag '{explicit_tag}'\033[0m"
                )
                print(
                    "\033[93m   -> Either the name is misspelled, or that variable is "
                    "connected AFTER this one. Conditions can only reference earlier "
                    "variables, so this will never match.\033[0m"
                )
            elif not CompilerUtils._value_exists_in_var(value, target):
                print(
                    f"\033[93m[WARNING] Condition [{explicit_tag}:{value}] - "
                    f"'{value}' is not one of the values of '{explicit_tag}'. "
                    f"This will never match.\033[0m"
                )

            return (explicit_tag, (value, is_negated))

        # Auto-detect which earlier variable owns this value
        for var in previous_vars:
            if CompilerUtils._value_exists_in_var(value, var):
                return (var["tag_name"], (value, is_negated))

        print(
            f"\033[93m[WARNING] Condition value '{value}' was not found in any "
            f"earlier variable. This term is ignored.\033[0m"
        )
        return None

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
    def _weights_for(stored, count):
        """Pad/trim a stored weight list to match a value list. Default weight is 1."""
        if not stored:
            return [1.0] * count
        if len(stored) == count:
            return list(stored)
        out = list(stored[:count])
        out.extend([1.0] * (count - len(out)))
        return out

    @staticmethod
    def _available_pool(var, current_values):
        """(values, weights) this variable can take in the given context.

        Single source of truth for "what can this variable be right now" - the same
        block used to be copy-pasted into enumeration, counting and resolution, so
        they could drift apart.

        Weights travel alongside the values rather than in a {value: weight} map,
        because the same value can appear in both the common list and a matching
        conditional block with a different weight. Keeping them positional lets both
        contribute, which is what "--N means N copies of this line" implies.
        """
        values = var.get("values", [])
        stored_weights = var.get("weights")

        if not isinstance(values, dict):
            pool = list(values) if values else []
            pool_weights = CompilerUtils._weights_for(
                stored_weights if isinstance(stored_weights, list) else None, len(pool)
            )
        else:
            stored_weights = stored_weights if isinstance(stored_weights, dict) else {}
            only_flags = var.get("only_flags", {})
            matching = []
            has_only_match = False

            for cond_key, cond_values in values.get("conditional", {}).items():
                if CompilerUtils.matches_condition(cond_key, current_values):
                    matching.append((cond_key, cond_values))
                    if only_flags.get(cond_key, False):
                        has_only_match = True

            pool = []
            pool_weights = []
            # If any matching condition has --only, common values are skipped
            if not has_only_match:
                common = values.get("common", [])
                pool.extend(common)
                pool_weights.extend(
                    CompilerUtils._weights_for(
                        stored_weights.get("common"), len(common)
                    )
                )
            for cond_key, cond_values in matching:
                pool.extend(cond_values)
                pool_weights.extend(
                    CompilerUtils._weights_for(
                        stored_weights.get("conditional", {}).get(cond_key),
                        len(cond_values),
                    )
                )

        excluded = CompilerUtils._exclusions_for(var, current_values)
        if excluded:
            kept = [(v, w) for v, w in zip(pool, pool_weights) if v not in excluded]
            pool = [v for v, _ in kept]
            pool_weights = [w for _, w in kept]

        return pool, pool_weights

    @staticmethod
    def _available_values(var, current_values):
        """Values this variable can take in the given context, exclusions applied."""
        return CompilerUtils._available_pool(var, current_values)[0]

    @staticmethod
    def _weighted_choice(pool, weights):
        """Pick one value honouring weights. Returns "" if every weight is zero."""
        if not pool:
            return ""
        total = sum(weights)
        if total <= 0:
            # Every candidate was set to --0: treat the pool as empty rather than
            # letting random.choices raise.
            return ""
        return random.choices(pool, weights=weights, k=1)[0]

    @staticmethod
    def _relevant_tags_from(variables):
        """Per position, the tags that any variable from there on actually tests.

        Counting only has to tell contexts apart by these tags. Most variables are
        referenced by nobody downstream, so this is what makes memoisation pay off.
        """
        relevant = [set() for _ in range(len(variables) + 1)]

        for i in range(len(variables) - 1, -1, -1):
            tags = set(relevant[i + 1])

            values = variables[i].get("values", {})
            if isinstance(values, dict):
                for cond_key in values.get("conditional", {}):
                    for tag, _ in cond_key:
                        tags.add(tag)

            exclusions = variables[i].get("exclusions", {})
            if isinstance(exclusions, dict):
                for cond_key in exclusions.get("conditional", {}):
                    for tag, _ in cond_key:
                        tags.add(tag)

            relevant[i] = tags

        return relevant

    @staticmethod
    def _is_countable(variables, limit=COMBINATION_LIMIT):
        """Cheap O(variables) check: is exact counting worth attempting?

        Multiplies a context-independent upper bound of each pool size, so it
        over-estimates and errs towards the cheap path. Returning False never means
        "no combinations", only "too many to count one by one".
        """
        total = 1
        for var in variables:
            if var.get("mode") not in ("Sequential", "Conditional"):
                continue

            values = var.get("values", [])
            if isinstance(values, dict):
                size = len(values.get("common", []))
                for cond_values in values.get("conditional", {}).values():
                    size += len(cond_values)
            else:
                size = len(values)

            if size > 1:
                total *= size
                if total > limit:
                    return False
        return True

    @staticmethod
    def _exclusions_for(var, current_values_dict=None):
        """Values removed by --value syntax in the given context."""
        return CompilerUtils._collect_exclusions(var, current_values_dict)

    @staticmethod
    def _apply_exclusions(values, var, current_values_dict=None):
        """Apply exclusion rules (--value syntax) to filter values

        Args:
            values: List of values to filter
            var: Variable data containing exclusion rules
            current_values_dict: Current context values (for conditional exclusions)

        Returns:
            Filtered list of values
        """
        exclusions_to_apply = CompilerUtils._collect_exclusions(
            var, current_values_dict
        )
        if not exclusions_to_apply:
            return values
        return [v for v in values if v not in exclusions_to_apply]

    @staticmethod
    def _collect_exclusions(var, current_values_dict=None):
        """Gather the --value exclusions that apply in this context."""
        exclusions_data = var.get("exclusions", {})
        if not exclusions_data:
            return []

        # Collect exclusions to apply
        exclusions_to_apply = []

        # Always apply common exclusions
        exclusions_to_apply.extend(exclusions_data.get("common", []))

        # Apply conditional exclusions if context is provided
        if current_values_dict:
            conditional_exclusions = exclusions_data.get("conditional", {})
            for cond_key, excl_list in conditional_exclusions.items():
                if CompilerUtils.matches_condition(cond_key, current_values_dict):
                    exclusions_to_apply.extend(excl_list)

        return exclusions_to_apply

    @staticmethod
    def matches_condition(condition, current_values_dict):
        """Check if condition matches current values

        condition: sequence of (tag, (value, is_negated)) pairs as produced by
            expand_or_conditions, e.g.
            (("CLOTHING", ("naked", True)), ("CLOTHING", ("bikini", True)))
        current_values_dict: {"GENDER": "man", "CLOTHING": "casual"}

        A plain dict {tag: (value, is_negated)} is still accepted for backward
        compatibility, but conditions are kept as sequences because a dict cannot
        hold more than one constraint per tag - which silently dropped constraints
        like [!CLOTHING:naked&&!CLOTHING:bikini] down to just the last one.

        Returns: True only if EVERY constraint holds (including NOT conditions)
        """
        items = condition.items() if isinstance(condition, dict) else condition

        for tag, condition_value in items:
            if tag not in current_values_dict:
                return False

            # Handle both old format (string) and new format (tuple)
            if isinstance(condition_value, tuple):
                expected_value, is_negated = condition_value
            else:
                # Backward compatibility: old format without negation
                expected_value = condition_value
                is_negated = False

            if expected_value == "*":
                # Wildcard for this tag - always matches
                continue

            # Check match with negation support
            matches = current_values_dict[tag] == expected_value
            if is_negated:
                matches = not matches

            if not matches:
                return False

        return True

    @staticmethod
    def calculate_combinations(variables, limit=COMBINATION_LIMIT):
        """Total number of Sequential/Conditional combinations, capped at `limit`.

        Random and ConditionalRandom variables re-roll every execution, so they do
        not multiply the combination count.

        Previously this counted by building the whole combination list in memory and
        taking its length, and it only ran at all when some variable had mode exactly
        "Sequential" - meaning a graph made purely of Conditional variables reported
        1 combination and its index never advanced.
        """
        if not variables:
            return 1

        if not any(v.get("mode") in ("Sequential", "Conditional") for v in variables):
            return 1

        if not CompilerUtils._is_countable(variables, limit):
            return limit

        total = CompilerUtils._count_subsequent_combinations(
            variables, 0, {}, limit=limit
        )
        return max(1, min(total, limit))

    @staticmethod
    def _enumerate_combinations(variables, current_index=0, current_values=None):
        """Lazily enumerate valid combinations, first variable changing slowest.

        This is a generator on purpose: callers must take only what they need. The
        full space is unbounded on conditional graphs.

        Random / ConditionalRandom variables do not expand into combinations - they
        yield a "[RANDOM: a|b|c]" placeholder listing the choices available in the
        current context.
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

        elif mode in ("Sequential", "Conditional"):
            available = CompilerUtils._available_values(var, current_values)

            # Iterate through available values
            if available:
                for value in available:
                    current_values[tag_name] = value
                    yield from CompilerUtils._enumerate_combinations(
                        variables, current_index + 1, dict(current_values)
                    )
            else:
                # No available values - use empty string and continue.
                # This fallback is essential: a variable with an empty value list
                # used to yield nothing at all, which turned it into a dead end.
                # The search then backtracked through every earlier combination
                # without ever producing a single result - an apparent hang.
                current_values[tag_name] = ""
                yield from CompilerUtils._enumerate_combinations(
                    variables, current_index + 1, current_values
                )

        elif mode == "ConditionalRandom":
            # Random within conditional context - show actual choices
            available = CompilerUtils._available_values(var, current_values)

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
        random_values = {}
        for var_idx, var in enumerate(variables):
            if var.get("mode") == "Random":
                values = var.get("values", [])
                if isinstance(values, list) and values:
                    weights = CompilerUtils._weights_for(
                        var.get("weights"), len(values)
                    )
                    var_seed = zlib.crc32(f"{seed}_{var_idx}".encode("utf-8"))
                    random.seed(var_seed)
                    random_values[var["tag_name"]] = CompilerUtils._weighted_choice(
                        values, weights
                    )

        # Mapping an index onto an exact combination needs, at every step, the number
        # of combinations sitting under each candidate value. That costs O(total
        # combinations) - fine for ordinary graphs, impossible for large conditional
        # ones. Decide once which strategy to use.
        exact = CompilerUtils._is_countable(variables)
        relevant = CompilerUtils._relevant_tags_from(variables) if exact else None
        memo = {} if exact else None

        # Build current values context and result
        current_values = {}
        result = []
        remaining_index = index

        for var_idx, var in enumerate(variables):
            tag_name = var["tag_name"]
            mode = var.get("mode", "Sequential")

            if mode == "Random":
                # Use pre-selected random value
                selected = random_values.get(tag_name, "")
                result.append(selected)
                current_values[tag_name] = selected
                continue

            available, weights = CompilerUtils._available_pool(var, current_values)

            if not available:
                result.append("")
                current_values[tag_name] = ""
                continue

            if mode == "ConditionalRandom":
                # Image variables carry their own seed
                base_seed = var.get("seed", seed)
                var_seed = zlib.crc32(f"{base_seed}_{var_idx}".encode("utf-8"))
                random.seed(var_seed)
                selected = CompilerUtils._weighted_choice(available, weights)

            elif exact:
                # Walk the cumulative ranges to find which value owns this index
                cumulative = 0
                selected = available[0]
                for value in available:
                    test_context = dict(current_values)
                    test_context[tag_name] = value
                    count = CompilerUtils._count_subsequent_combinations(
                        variables, var_idx + 1, test_context, relevant, memo
                    )
                    if remaining_index < cumulative + count:
                        selected = value
                        remaining_index -= cumulative
                        break
                    cumulative += count

            else:
                # Mixed-radix fallback: no counting at all. Still deterministic and
                # still varied, but index is no longer a one-to-one map onto the
                # combination space, and the first variable changes fastest.
                selected = available[remaining_index % len(available)]
                remaining_index //= len(available)

            result.append(selected)
            current_values[tag_name] = selected

        return result

    @staticmethod
    def _count_subsequent_combinations(
        variables, start_index, current_context, relevant=None, memo=None, limit=None
    ):
        """Count how many combinations are possible from start_index onwards

        Args:
            variables: list of all variables
            start_index: index to start counting from
            current_context: dict of tag_name -> value for already resolved variables
            relevant: per-position tag sets from _relevant_tags_from (built on demand)
            memo: shared cache; contexts that differ only in tags nobody tests
                downstream collapse onto the same entry
            limit: stop once the running total reaches this. The result is then a
                lower bound - enough to report "more than N", not for index math.

        Returns:
            int: number of combinations
        """
        # Base case: no more variables
        if start_index >= len(variables):
            return 1

        if relevant is None:
            relevant = CompilerUtils._relevant_tags_from(variables)
        if memo is None:
            memo = {}

        memo_key = (
            start_index,
            tuple(
                sorted(
                    (t, current_context[t])
                    for t in relevant[start_index]
                    if t in current_context
                )
            ),
        )
        if memo_key in memo:
            return memo[memo_key]

        var = variables[start_index]
        mode = var.get("mode", "Sequential")

        if mode in ("Random", "ConditionalRandom"):
            # Random modes don't multiply combinations (always 1 choice per execution)
            total = CompilerUtils._count_subsequent_combinations(
                variables, start_index + 1, current_context, relevant, memo, limit
            )
            memo[memo_key] = total
            return total

        available = CompilerUtils._available_values(var, current_context)

        if not available:
            # No available values - use empty string and continue counting
            test_context = dict(current_context)
            test_context[var["tag_name"]] = ""
            total = CompilerUtils._count_subsequent_combinations(
                variables, start_index + 1, test_context, relevant, memo, limit
            )
            memo[memo_key] = total
            return total

        total = 0
        for value in available:
            test_context = dict(current_context)
            test_context[var["tag_name"]] = value
            total += CompilerUtils._count_subsequent_combinations(
                variables, start_index + 1, test_context, relevant, memo, limit
            )
            if limit is not None and total >= limit:
                # Bailing out early leaves `total` a lower bound, so it must not be
                # cached as if it were the real count.
                return total

        memo[memo_key] = total
        return total

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
                        # cond_value is a (value, is_negated) pair
                        if isinstance(cond_value, tuple):
                            value, is_negated = cond_value
                        else:
                            value, is_negated = cond_value, False
                        prefix = "!" if is_negated else ""
                        cond_parts.append(f"{prefix}{cond_tag}:{value}")
                    cond_str = " AND ".join(cond_parts)

                    # Format values
                    values_str = ", ".join(
                        [f'"{v}"' if v else "(empty)" for v in cond_values]
                    )

                    warnings.append(
                        f"Variable '{tag_name}': Condition [{cond_str}] never matched\n"
                        f"  -> Unused values: {values_str}"
                    )

        return warnings

    @staticmethod
    def generate_all_combinations_text(variables, max_display=100):
        """Generate text showing all combinations (for debug output)

        Enumerates lazily and stops at max_display. The full combination space is
        never materialized: on a large graph it is astronomically big, and building
        it was previously enough to exhaust system memory.
        """
        # _enumerate_combinations already emits "[RANDOM: a|b|c]" placeholders for
        # Random / ConditionalRandom variables, resolved against the current context,
        # so no post-processing is needed to rebuild them.
        all_combos = []
        truncated = False
        for combo in CompilerUtils._enumerate_combinations(variables):
            if len(all_combos) >= max_display:
                truncated = True
                break

            # Image variables show a count rather than a list of full paths.
            formatted_combo = []
            for var, value in zip(variables, combo):
                if (
                    var.get("type") in ["Image", "image_folder"]
                    and isinstance(value, str)
                    and value.startswith("[RANDOM:")
                ):
                    choices = value[len("[RANDOM:") : -1].strip()
                    count = len(choices.split("|")) if choices else 0
                    formatted_combo.append(f"[RANDOM: {count} images]")
                else:
                    formatted_combo.append(value)

            all_combos.append(formatted_combo)

        # Unused-condition detection is only meaningful over a complete enumeration.
        # When the list was cut short, skip it instead of reporting false positives.
        if truncated:
            unused_warnings = []
        else:
            unused_warnings = CompilerUtils._check_unused_conditions(
                variables, all_combos
            )

        lines = []

        # Add warnings at the top if any
        if unused_warnings:
            lines.append("=" * 70)
            lines.append("[WARNING] Unused conditional values detected")
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
                        # Note the parentheses: without them this read as
                        # (is_image and "\\" in v) or ("/" in v), which mangled any
                        # text value containing a slash.
                        if var_type in ["Image", "image_folder"] and (
                            "\\" in v_str or "/" in v_str
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

        if truncated:
            lines.append(f"\n... and more combinations (showing first {max_display})")

        return "\n".join(lines)

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
                "output": var.get("output_to_prompt", True),
            }

        # Track which tags are used
        used_tags = set()

        # Replace tags with prefix/suffix handling
        for tag_name, data in tag_data.items():
            tag = f"[{tag_name}]"
            if tag in result:
                # Apply prefix/suffix only if value is not empty.
                # A control-only variable resolves to nothing even when its tag is
                # written explicitly - otherwise "suppressed" would still leak into
                # the prompt whenever the template happens to mention it.
                if data["output"] and data["value"] != "":
                    replacement = f"{data['prefix']}{data['value']}{data['suffix']}"
                else:
                    replacement = ""  # Empty value = no prefix/suffix

                result = result.replace(tag, replacement)
                used_tags.add(tag_name)

        # Collect unused variables with prefix/suffix (filter out empty values)
        unused_values = []
        for tag_name, data in sorted(tag_data.items(), key=lambda x: x[1]["index"]):
            if tag_name not in used_tags and data["value"] != "" and data["output"]:
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
            if value != "" and var.get("output_to_prompt", True):
                formatted = f"{var.get('prefix', '')}{value}{var.get('suffix', '')}"
                formatted_values.append(formatted)
        return separator.join(formatted_values)
