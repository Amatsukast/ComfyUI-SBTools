"""ComfyUI-SBTools - Custom Node Collection"""

__version__ = "1.2.0"

from .nodes.birefnet_node import NODE_CLASS_MAPPINGS as BIREFNET_MAPPINGS
from .nodes.birefnet_node import NODE_DISPLAY_NAME_MAPPINGS as BIREFNET_DISPLAY
from .nodes.alpha_to_chroma_key import NODE_CLASS_MAPPINGS as CHROMAKEY_MAPPINGS
from .nodes.alpha_to_chroma_key import NODE_DISPLAY_NAME_MAPPINGS as CHROMAKEY_DISPLAY
from .nodes.prompt_variable import NODE_CLASS_MAPPINGS as PROMPTVAR_MAPPINGS
from .nodes.prompt_variable import NODE_DISPLAY_NAME_MAPPINGS as PROMPTVAR_DISPLAY
from .nodes.variable_combiner import NODE_CLASS_MAPPINGS as VARCOMB_MAPPINGS
from .nodes.variable_combiner import NODE_DISPLAY_NAME_MAPPINGS as VARCOMB_DISPLAY
from .nodes.prompt_compiler import NODE_CLASS_MAPPINGS as PROMPTCOMP_MAPPINGS
from .nodes.prompt_compiler import NODE_DISPLAY_NAME_MAPPINGS as PROMPTCOMP_DISPLAY

NODE_CLASS_MAPPINGS = {
    **BIREFNET_MAPPINGS,
    **CHROMAKEY_MAPPINGS,
    **PROMPTVAR_MAPPINGS,
    **VARCOMB_MAPPINGS,
    **PROMPTCOMP_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **BIREFNET_DISPLAY,
    **CHROMAKEY_DISPLAY,
    **PROMPTVAR_DISPLAY,
    **VARCOMB_DISPLAY,
    **PROMPTCOMP_DISPLAY,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
