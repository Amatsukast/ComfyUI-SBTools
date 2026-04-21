# ComfyUI-SBTools - Variable Combiner Node
#
# Copyright (c) Amatsukast
# Licensed under GPL-3.0


class SBTools_VariableCombiner:
    @classmethod
    def INPUT_TYPES(cls):
        tooltips = {
            "var_list": "Variable list from Variable node or another Combiner",
        }
        return {
            "optional": {
                "var_list1": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
                "var_list2": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
                "var_list3": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
                "var_list4": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
                "var_list5": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
                "var_list6": ("VARIABLE_LIST", {"tooltip": tooltips["var_list"]}),
            }
        }

    RETURN_TYPES = ("VARIABLE_LIST",)
    RETURN_NAMES = ("var_list",)
    FUNCTION = "combine_variables"
    CATEGORY = "SBTools/Prompt"
    OUTPUT_NODE = False

    def combine_variables(self, **kwargs):
        combined_list = []
        seen_tags = {}  # {tag_name: (values, mode)} for duplicate detection

        # Collect and expand all lists (var_list1-var_list6)
        for key in [
            "var_list1",
            "var_list2",
            "var_list3",
            "var_list4",
            "var_list5",
            "var_list6",
        ]:
            if key in kwargs and kwargs[key] is not None:
                for var in kwargs[key]:
                    tag_name = var["tag_name"]

                    # Skip auto-generated tags (always allow duplicates)
                    if tag_name.startswith("_VAR_"):
                        combined_list.append(var)
                        continue

                    # Check for duplicates in named tags
                    if tag_name in seen_tags:
                        # Same tag name - check if it's truly the same variable
                        prev_var = seen_tags[tag_name]
                        curr_key = (str(var["values"]), var["mode"])
                        prev_key = (str(prev_var["values"]), prev_var["mode"])

                        if curr_key == prev_key:
                            # Exact duplicate - skip with info message
                            print(f"\033[90m[INFO] Skipping duplicate variable '{tag_name}' (same definition)\033[0m")
                        else:
                            # Same name, different definition - ERROR
                            error_msg = (
                                f"Variable name conflict: '{tag_name}' is defined multiple times with different values.\n"
                                f"Please rename one of the variables or leave tag_name empty for auto-naming."
                            )
                            print(f"\033[91m❌ ERROR: {error_msg}\033[0m")
                            raise ValueError(error_msg)
                    else:
                        # First occurrence
                        seen_tags[tag_name] = var
                        combined_list.append(var)

        return (combined_list,)


NODE_CLASS_MAPPINGS = {"SBTools_VariableCombiner": SBTools_VariableCombiner}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariableCombiner": "Variable Combiner (SBTools)"}
