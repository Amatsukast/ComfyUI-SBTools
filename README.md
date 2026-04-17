# ComfyUI-SBTools

**Version 1.2.0**

Custom node collection for ComfyUI. Background removal, color analysis, and dynamic prompt generation tools.

## Nodes

| Node                          | Category        | Description                                                          |
| ----------------------------- | --------------- | -------------------------------------------------------------------- |
| BiRefNet RemoveBG (SBTools)   | SBTools/Image   | Advanced background removal with 5 model variants                    |
| Alpha to Chroma Key (SBTools) | SBTools/Image   | Find safe chroma key colors and fill transparent areas automatically |
| Prompt Variable (SBTools)     | SBTools/Prompt  | Define variables with sequential or random selection modes           |
| Variable Combiner (SBTools)   | SBTools/Prompt  | Combine multiple variable lists for unlimited expansion              |
| Prompt Compiler (SBTools)     | SBTools/Prompt  | Generate prompts from variables with template replacement            |

## Installation

### Method 1: ComfyUI Manager (Recommended)

Search for "SBTools" in ComfyUI Manager and click Install.

### Method 2: Manual Installation

**Step 1: Open your ComfyUI custom nodes folder**

- Windows Portable: `ComfyUI_windows_portable\ComfyUI\custom_nodes`
- Standard: `ComfyUI\custom_nodes`

**Step 2: Open terminal in this folder and clone the repository**

```bash
git clone https://github.com/Amatsukast/ComfyUI-SBTools.git
```

**Step 3: Install dependencies**

**For Windows Portable:**

```bash
cd ComfyUI-SBTools
..\..\..\python_embeded\python.exe -m pip install -r requirements.txt
```

**For Standard Installation (venv/conda):**

```bash
cd ComfyUI-SBTools
pip install -r requirements.txt
```

**Step 4: Restart ComfyUI**

## Updating

### From v1.0.0 to v1.1.0

**Important:** Node names have changed in v1.1.0. After updating:

1. Run the update command (or use `install_sbtools.bat` if you have it)
2. **Restart ComfyUI completely**
3. **Clear browser cache** (Ctrl+Shift+R or Ctrl+F5)
4. Old nodes (`BiRefNet`, `Find Unused Color`) will be automatically removed

**Note:** The update script automatically cleans Python cache to prevent conflicts.

### General Update

**Step 1: Open the ComfyUI-SBTools folder**

- Windows Portable: `ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-SBTools`
- Standard: `ComfyUI\custom_nodes\ComfyUI-SBTools`

**Step 2: Open terminal in this folder and pull updates**

```bash
git pull
```

**Step 3: Update dependencies**

**For Windows Portable:**

```bash
..\..\..\python_embeded\python.exe -m pip install -r requirements.txt
```

**For Standard Installation (venv/conda):**

```bash
pip install -r requirements.txt
```

**Step 4: Restart ComfyUI**

## Usage

### Prompt Generation Nodes

Located under `SBTools/Prompt` category. These nodes create a flexible prompt generation system optimized for FLUX.2 and other modern image generation models.

#### System Overview

The prompt generation system consists of three nodes that work together:

1. **Prompt Variable** - Define individual variables with their values
2. **Variable Combiner** - Combine multiple variables into lists (optional, for complex workflows)
3. **Prompt Compiler** - Generate final prompts from variables

#### Quick Start

**Simple Example (2-3 variables):**
```
Variable 1 (GENDER: man, woman) → Compiler
Variable 2 (AGE: young, old)    ↗
```

**Complex Example (7+ variables):**
```
Variables 1-3 → Combiner A ┐
Variables 4-6 → Combiner B ├→ Compiler
Variable 7    ──────────────┘
```

---

### Prompt Variable

Define a single variable with multiple values. Variables can operate in two modes:

#### Parameters

**Required:**
- `tag_name` - Variable name for template replacement (e.g., `GENDER`, `CLOTHING`)
- `values` - List of values, one per line
  - Use empty line or `[NONE]` for "no value" option
- `randomize` - Toggle between modes:
  - **OFF (Sequential)**: Cycle through all values systematically
  - **ON (Random)**: Pick one value randomly each execution

**Optional:**
- `prefix` - Text added before the value (only in template mode)
- `suffix` - Text added after the value (only in template mode)

#### Output

- `var_list` - Variable data (connect to Combiner or Compiler)

#### Examples

**Basic variable:**
```
tag_name: "GENDER"
values: "man\nwoman"
randomize: OFF
```

**With prefix/suffix:**
```
tag_name: "ACCESSORY"
values: "glasses\nhat\n[NONE]"
prefix: " wearing "
randomize: ON
```

---

### Variable Combiner

Combine multiple variable lists into one. Useful for organizing complex prompts with many variables.

#### Parameters

**Optional:**
- `var_list1` to `var_list6` - Variable lists from Variable nodes or other Combiners

#### Output

- `var_list` - Combined variable list

#### Usage

**Organize by category:**
```
Character variables (3) → Combiner A ┐
Clothing variables (3)  → Combiner B ├→ Combiner C → Compiler
Scene variables (2)     → Combiner C ┘
```

**Chain for unlimited expansion:**
- Each Combiner supports 6 inputs
- Connect Combiner outputs to other Combiners
- No limit on total number of variables

---

### Prompt Compiler

Generate final prompts from variables. Supports two modes automatically:

#### Parameters

**Required:**
- `template` - Template text with `[TAG_NAME]` placeholders
  - Leave empty for simple join mode
  - Example: `"A [AGE] [GENDER] wearing [CLOTHING]."`
- `index` - Which sequential combination to use (loops automatically)
- `seed` - Seed for random variables (use Primitive node with increment for batch randomization)
- `separator` - Character(s) to join values (default: `", "`)

**Optional:**
- `var_list` - Variable list from Variable or Combiner node

#### Outputs

- `prompt` - Generated prompt text
- `max_combinations` - Total number of sequential combinations
- `all_combinations` - Debug output showing all patterns (use with Show Text node)

#### Modes

**Template Mode** (template not empty):
```
Template: "A [AGE] [GENDER] portrait."
Variables: AGE="young", GENDER="man", CLOTHING="suit"
→ Output: "A young man portrait., suit"
          (CLOTHING appended because no [CLOTHING] tag)
```

**Simple Join Mode** (template empty):
```
Template: ""
Variables: AGE="young", GENDER="man", CLOTHING="suit"
→ Output: "young, man, suit"
```

#### Sequential vs Random

**Sequential variables:**
- All combinations calculated with `itertools.product`
- `index` parameter selects which combination
- Use Primitive node with `increment` to cycle through all

**Random variables:**
- One value selected randomly per execution
- `seed` parameter controls randomness
- Use Primitive node with `increment` on seed for variation

**Example:**
```
2 Sequential vars (man/woman × young/old) = 4 combinations
1 Random var (3 accessories) = random each time
→ Total: 4 sequential patterns × infinite random variations
```

#### Tips

**For FLUX.2 JSON-style prompts:**
```json
{
  "subject": "[SUBJECT]",
  "background": "[BACKGROUND]",
  "lighting": "[LIGHTING]",
  "style": "[STYLE]"
}
```

**For natural language:**
```
"A [AGE] [GENDER] [CLOTHING][ACCESSORY], [BACKGROUND], [LIGHTING]"
```

**Batch processing:**
- Connect Primitive (INT, increment) to `index` for sequential patterns
- Connect Primitive (INT, increment) to `seed` for random variations
- Use `max_combinations` to know total patterns

---

### Image Processing Nodes

All image nodes are located under `SBTools/Image` category in ComfyUI.

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

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

### Latest Release: v1.2.0 (2026-04-17)

**New Features:**
- Dynamic prompt generation system with 3 new nodes
- Template-based prompt replacement with `[TAG_NAME]` syntax
- Sequential and Random variable combination modes
- Flexible variable management with Combiner node
- Optimized for FLUX.2 natural language prompts

**Example workflow included in `examples/` folder.**

---

**Note:** This is a personal custom node collection. Use at your own discretion.
