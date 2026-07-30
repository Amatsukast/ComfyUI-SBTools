# ComfyUI-SBTools - Variable Debug Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0

from .compiler_utils import CompilerUtils, COMBINATION_LIMIT


class SBTools_VariableDebug:
    """Inspect a variable list: the first N combinations and the total count.

    Split out of Variable Builder so it is only paid for when it is wanted. It also
    takes nothing but var_list, so ComfyUI caches it: changing seed or index on the
    Builder does not re-run it, only editing the variables themselves does.

    It can be attached anywhere in the chain, including partway through a Combiner
    tree, to see what a variable can resolve to at that point.

    Connect COMBINATIONS to a preview node to read the listing.
    """

    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "max_display": (
                "How many combinations to list. Enumeration stops there, so this is "
                "also the cost - a large graph is unaffected by its own size."
            ),
            "show_total": (
                "Count the total number of combinations. Off by default: this is the "
                "expensive part, and on a large conditional graph the exact number is "
                f"unreachable anyway (counting stops at {COMBINATION_LIMIT:,})."
            ),
            "var_list": "Variable list from Variable Prompt, Variable Folder, Variable Image Loader, or Variable Combiner",
        }
        return {
            "required": {
                "max_display": (
                    "INT",
                    {
                        "default": 100,
                        "min": 0,
                        "max": 10000,
                        "step": 10,
                        "tooltip": tooltips["max_display"],
                    },
                ),
                "show_total": (
                    "BOOLEAN",
                    {"default": False, "tooltip": tooltips["show_total"]},
                ),
            },
            "optional": {
                "var_list": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("COMBINATIONS", "TOTAL")
    FUNCTION = "inspect"
    CATEGORY = "SBTools/Prompt"
    # Not an OUTPUT_NODE: rendering text on the node itself would need a frontend
    # extension, and this package ships no web assets. Connect COMBINATIONS to a
    # preview node instead.
    OUTPUT_NODE = False

    def inspect(self, max_display, show_total, var_list=None):
        variables = var_list if var_list else []

        if not variables:
            return ("(no variables connected)", 0)

        lines = []

        if show_total:
            total = CompilerUtils.calculate_combinations(variables)
            capped = total >= COMBINATION_LIMIT
            shown = f"{total:,}+" if capped else f"{total:,}"
            lines.append(f"Total combinations: {shown}")
            if capped:
                lines.append(
                    "  (counting stopped at the limit - the real total is larger)"
                )
        else:
            total = 0
            lines.append("Total combinations: (not counted - enable show_total)")

        lines.append(f"Variables: {len(variables)}")
        modes = {}
        for var in variables:
            mode = var.get("mode") or "Image"
            modes[mode] = modes.get(mode, 0) + 1
        lines.append(
            "  " + ", ".join(f"{m}: {n}" for m, n in sorted(modes.items()))
        )
        lines.append("")

        if max_display > 0:
            lines.append(
                CompilerUtils.generate_all_combinations_text(
                    variables, max_display=max_display
                )
            )

        return ("\n".join(lines), total)


NODE_CLASS_MAPPINGS = {"SBTools_VariableDebug": SBTools_VariableDebug}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariableDebug": "Variable Debug (SBTools)"}
