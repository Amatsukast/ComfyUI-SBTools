# ComfyUI-SBTools

**Version 1.1.0**

Custom node collection for ComfyUI. Background removal and color analysis tools.

## Nodes

| Node                             | Category      | Description                                                           |
| -------------------------------- | ------------- | --------------------------------------------------------------------- |
| BiRefNet RemoveBG (SBTools)      | SBTools/Image | Advanced background removal with 5 model variants                    |
| Alpha to Chroma Key (SBTools)    | SBTools/Image | Find safe chroma key colors and fill transparent areas automatically |

## Installation

1. Navigate to your ComfyUI custom nodes directory:

```bash
cd ComfyUI/custom_nodes
```

2. Clone this repository:

```bash
git clone https://github.com/Amatsukast/ComfyUI-SBTools.git
```

3. Install dependencies:

```bash
cd ComfyUI-SBTools
pip install -r requirements.txt
```

4. Restart ComfyUI

## Updating

### From v1.0.0 to v1.1.0

**Important:** Node names have changed in v1.1.0. After updating:

1. Run the update command (or use `install_sbtools.bat` if you have it)
2. **Restart ComfyUI completely**
3. **Clear browser cache** (Ctrl+Shift+R or Ctrl+F5)
4. Old nodes (`BiRefNet`, `Find Unused Color`) will be automatically removed

**Note:** The update script automatically cleans Python cache to prevent conflicts.

### General Update

Navigate to the custom node directory and pull the latest changes:

```bash
cd ComfyUI/custom_nodes/ComfyUI-SBTools
git pull
pip install -r requirements.txt
```

Then restart ComfyUI.

## Usage

All nodes are located under `SBTools/Image` category in ComfyUI.

### BiRefNet (RemoveBG)

Advanced background removal using BiRefNet models. Supports multiple model variants optimized for different use cases.

#### Available Models

| Model                 | Best For                  | Resolution            | Notes                       |
| --------------------- | ------------------------- | --------------------- | --------------------------- |
| **BiRefNet-general**  | Everyday use              | 1024×1024             | Fast, balanced performance  |
| **BiRefNet-HR**       | High quality              | 2048×2048             | Best detail preservation    |
| **BiRefNet-portrait** | People/portraits          | 1024×1024             | Trained on human subjects   |
| **BiRefNet_dynamic**  | Aspect ratio preservation | Variable (256-2304px) | No image distortion         |
| **BiRefNet_toonout**  | Outline extraction        | 1024×1024             | Creates toon-style outlines |

#### Parameters

**Required:**

- `image` - Input image
- `model` - Model selection

**Optional:**

- `mask_blur` (0-64) - Softens mask edges. Use for smoother transitions.
- `mask_offset` (-20 to +20) - Expands (+) or shrinks (-) the mask boundary
- `invert_output` - Swaps foreground/background
- `background` - Alpha (transparent) or Color (custom color)
- `background_color` - Custom background color (hex code, e.g., #222222)

#### Outputs

- `IMAGE` - Processed image with transparent or colored background
- `MASK` - Black & white mask data
- `MASK_IMAGE` - Visualization of the mask (RGB)

#### Which Model Should I Use?

**For most cases:** Use `BiRefNet-general`

- Fast processing
- Good quality
- Works well for general objects

**For high-quality results:** Use `BiRefNet-HR`

- 4x larger processing area
- Better detail preservation
- Ideal for final outputs

**For people/portraits:** Use `BiRefNet-portrait`

- Optimized for human subjects
- Better hair/skin detection
- Trained on portrait datasets

**For wide/tall images:** Use `BiRefNet_dynamic`

- Preserves aspect ratio (no squashing/stretching)
- Automatically scales to fit
- Best for non-square images

**For creative effects:** Use `BiRefNet_toonout`

- Extracts outlines instead of removing background
- Creates line art/edge detection
- Useful for stylized effects

#### Tips

**Processing Resolution:**

- **Square models** (general, HR, portrait, toonout) resize images to a fixed square
- **Dynamic model** preserves aspect ratio by resizing the longest side only

**Mask Refinement:**

- Start with `mask_blur: 0` and `mask_offset: 0`
- Use `mask_blur: 2-5` for softer, more natural edges
- Use `mask_offset: +2 to +5` if edges are too tight
- Use `mask_offset: -2 to -5` if edges include too much background

**Performance:**

- Smaller images process faster
- BiRefNet-general is fastest
- BiRefNet-HR takes ~4x longer but produces better results

---

### Find Unused Color

Finds a color in your image that is maximally different from all existing colors. Useful for chroma keying, masking, or creating selection areas.

#### Use Cases

- **Chroma key backgrounds** - Find a color that won't interfere with your subject
- **Mask generation** - Create temporary backgrounds for selection tools
- **Color coding** - Identify safe colors for overlays or annotations

#### Parameters

**Required:**

- `image` - Input image to analyze

**Optional:**

- `min_distance` (0-255, default: 30) - Minimum color distance required
  - Higher values = more different from existing colors
  - Lower values = easier to find but may be similar to image colors
- `sample_size` (1000-50000, default: 5000) - Number of pixels to sample
  - Higher values = more accurate but slower
  - Lower values = faster but may miss similar colors

#### Outputs

- `hex_color` - Color in hex format (e.g., #00FF00)
- `R` - Red component (0-255)
- `G` - Green component (0-255)
- `B` - Blue component (0-255)

#### How It Works

1. Samples random pixels from your image
2. Tests common pure colors (green, blue, magenta, cyan, yellow, red)
3. Returns the color with the maximum distance from all sampled pixels
4. If no candidate meets the criteria, performs a coarse grid search

#### Tips

**For chroma keying:**

- Use `min_distance: 40-60` for safe separation
- Pure green (0, 255, 0) is usually selected for typical images

**For quick results:**

- Use `sample_size: 5000` (default)
- Increase to 10000-20000 for images with complex color palettes

**Distance metric:**

- Distance is calculated as Euclidean distance in RGB space
- A distance of 30 means the color differs by ~30 units per channel on average

---

## Model Storage

BiRefNet models are automatically downloaded and stored in:

```
ComfyUI/models/sbtools/BiRefNet/
```

Models are downloaded on first use and cached for future sessions.

## Credits

**BiRefNet Node** is based on [ComfyUI-RMBG](https://github.com/AILab-AI/ComfyUI-RMBG) by AILab-AI

**BiRefNet Models** by ZhengPeng7 - [HuggingFace](https://huggingface.co/ZhengPeng7/BiRefNet) | [GitHub](https://github.com/ZhengPeng7/BiRefNet)

## License

### Code License

This project is licensed under **GNU General Public License v3.0 (GPL-3.0)**.

- **BiRefNet node** is based on [ComfyUI-RMBG](https://github.com/AILab-AI/ComfyUI-RMBG) by AILab-AI (GPL-3.0)
- **Find Unused Color node** is original work by Amatsukast

See [LICENSE](LICENSE) for details.

### Model License

BiRefNet models by ZhengPeng7 are licensed under **Apache License 2.0**.

- Model repository: [ZhengPeng7/BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet)
- You can use the models freely for commercial and non-commercial purposes

### Summary

- ✅ You can use, modify, and distribute this code
- ✅ You can use the models commercially
- ⚠️ Modifications must also be GPL-3.0
- ⚠️ You must provide source code when distributing

---

## Changelog

### [1.1.0] - 2026-04-13

#### Breaking Changes

- **Node names updated for uniqueness**
  - `BiRefNet` → `SBTools_BiRefNet` (display: "BiRefNet RemoveBG (SBTools)")
  - `Find Unused Color` → `SBTools_AlphaToChromaKey` (display: "Alpha to Chroma Key (SBTools)")
- **Alpha to Chroma Key output changed**
  - Old: `hex_color`, `R`, `G`, `B` (4 outputs)
  - New: `hex_color`, `filled_image` (2 outputs)

#### Added

- Alpha to Chroma Key: `filled_image` output - automatically fills transparent areas with the detected safe chroma key color
- Alpha channel detection with informative console logging

#### Changed

- Simplified `requirements.txt` - only `huggingface_hub>=0.19.0` needed (torch, torchvision, pillow, numpy, safetensors are provided by ComfyUI)
- All nodes now use `SBTools_` prefix in class names to prevent naming conflicts
- Node display names include "(SBTools)" branding for easy identification

#### Technical

- BiRefNet: Refactored to use explicit function parameters instead of `**kwargs`
- Improved code maintainability and IDE support
- Better parameter type checking and documentation

---

### [1.0.0] - 2026-04-13

#### Added

- BiRefNet (RemoveBG) node with 5 model variants
  - BiRefNet-general: 1024px, balanced performance
  - BiRefNet-HR: 2048px, high quality
  - BiRefNet-portrait: 1024px, optimized for human subjects
  - BiRefNet_dynamic: variable resolution with aspect ratio preservation
  - BiRefNet_toonout: 1024px, outline extraction
- Find Unused Color node for chroma key color detection
- Automatic model download from HuggingFace
- Custom model storage in `models/sbtools/BiRefNet/`
- Support for transparent and colored backgrounds
- Mask refinement options (blur, offset, invert)

#### Optimizations

- Reduced model selection from 11 to 5 carefully chosen variants
- Improved aspect ratio handling for BiRefNet_dynamic
- Optimized processing resolution based on input size

#### Technical

- Modular package structure
- English-only codebase
- Comprehensive README documentation
- Version tracking in `__init__.py`

---

**Note:** This is a personal custom node collection. Use at your own discretion.
