"""ComfyUI-SBTools - Custom Node Collection"""

__version__ = "1.4.0"

from .nodes.birefnet_node import NODE_CLASS_MAPPINGS as BIREFNET_MAPPINGS
from .nodes.birefnet_node import NODE_DISPLAY_NAME_MAPPINGS as BIREFNET_DISPLAY
from .nodes.alpha_to_chroma_key import NODE_CLASS_MAPPINGS as CHROMAKEY_MAPPINGS
from .nodes.alpha_to_chroma_key import NODE_DISPLAY_NAME_MAPPINGS as CHROMAKEY_DISPLAY
from .nodes.prompt_variable import NODE_CLASS_MAPPINGS as VARPROMPT_MAPPINGS
from .nodes.prompt_variable import NODE_DISPLAY_NAME_MAPPINGS as VARPROMPT_DISPLAY
from .nodes.variable_combiner import NODE_CLASS_MAPPINGS as VARCOMB_MAPPINGS
from .nodes.variable_combiner import NODE_DISPLAY_NAME_MAPPINGS as VARCOMB_DISPLAY
from .nodes.image_variable import NODE_CLASS_MAPPINGS as VARIMGLOADER_MAPPINGS
from .nodes.image_variable import NODE_DISPLAY_NAME_MAPPINGS as VARIMGLOADER_DISPLAY
from .nodes.multi_compiler import NODE_CLASS_MAPPINGS as VARBUILDER_MAPPINGS
from .nodes.multi_compiler import NODE_DISPLAY_NAME_MAPPINGS as VARBUILDER_DISPLAY

NODE_CLASS_MAPPINGS = {
    **BIREFNET_MAPPINGS,
    **CHROMAKEY_MAPPINGS,
    **VARPROMPT_MAPPINGS,
    **VARCOMB_MAPPINGS,
    **VARIMGLOADER_MAPPINGS,
    **VARBUILDER_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **BIREFNET_DISPLAY,
    **CHROMAKEY_DISPLAY,
    **VARPROMPT_DISPLAY,
    **VARCOMB_DISPLAY,
    **VARIMGLOADER_DISPLAY,
    **VARBUILDER_DISPLAY,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
