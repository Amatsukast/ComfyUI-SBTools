"""ComfyUI-SBTools - Custom Node Collection"""

__version__ = "1.0.0"

from .nodes.birefnet_node import NODE_CLASS_MAPPINGS as BIREFNET_MAPPINGS
from .nodes.birefnet_node import NODE_DISPLAY_NAME_MAPPINGS as BIREFNET_DISPLAY
from .nodes.find_unused_color import NODE_CLASS_MAPPINGS as FINDCOLOR_MAPPINGS
from .nodes.find_unused_color import NODE_DISPLAY_NAME_MAPPINGS as FINDCOLOR_DISPLAY

NODE_CLASS_MAPPINGS = {
    **BIREFNET_MAPPINGS,
    **FINDCOLOR_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **BIREFNET_DISPLAY,
    **FINDCOLOR_DISPLAY,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
