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
                # All inputs are VARIABLE_LIST, extend them
                combined_list.extend(kwargs[key])

        return (combined_list,)


NODE_CLASS_MAPPINGS = {"SBTools_VariableCombiner": SBTools_VariableCombiner}

NODE_DISPLAY_NAME_MAPPINGS = {"SBTools_VariableCombiner": "Variable Combiner (SBTools)"}
