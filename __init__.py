"""ComfyUI-SBTools - Custom Node Collection"""

__version__ = "1.1.0"

from .nodes.birefnet_node import NODE_CLASS_MAPPINGS as BIREFNET_MAPPINGS
from .nodes.birefnet_node import NODE_DISPLAY_NAME_MAPPINGS as BIREFNET_DISPLAY
from .nodes.alpha_to_chroma_key import NODE_CLASS_MAPPINGS as CHROMAKEY_MAPPINGS
from .nodes.alpha_to_chroma_key import NODE_DISPLAY_NAME_MAPPINGS as CHROMAKEY_DISPLAY

NODE_CLASS_MAPPINGS = {
    **BIREFNET_MAPPINGS,
    **CHROMAKEY_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **BIREFNET_DISPLAY,
    **CHROMAKEY_DISPLAY,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
