# Changelog

All notable changes to ComfyUI-SBTools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-04-17

### Added

- **Image Variable Loader Node**: Load images from folder with flexible control
  - Folder path specification with glob pattern matching (e.g., `*.png`, `body_*.jpg`)
  - Sequential and Random selection modes with index/seed control
  - Natural sort order (Windows Explorer compatible) for human-friendly numbering
  - Subfolder search support with recursive option
  - RGBA preservation by default with optional background fill
  - Custom background color specification in hex format (e.g., `#FFFFFF`)
  - Filename output with optional extension toggle (default: without extension)
  - Dual output: direct `IMAGE` output for standalone use + `VARIABLE_LIST` for Variable Combiner
  - EXIF orientation handling for correct image display
  - Support for PNG, JPG, JPEG, WebP, BMP, GIF formats
  - Multibyte character (Japanese) support for file paths and names
- **Multi Compiler Node**: Extended Prompt Compiler with image support
  - Support for up to 4 images simultaneously (for FLUX.2 Reference workflow)
  - Combined text + image variable compilation with full combination calculation
  - Independent seed control for each image variable
  - 2-line debug output format (prompt line + image info line)
  - All Sequential and Random combinations across text and image variables
  - Same template system as Prompt Compiler with `[TAG_NAME]` replacement
  - Empty image slots filled automatically for unused outputs

### Changed

- Image Variable Loader: Default filename output without extension for cleaner display

### Technical

- Natural sort implementation using regex-based numeric detection
- Hex color parsing with validation and fallback to white
- Image loading with PIL including RGBA to RGB conversion with alpha compositing
- Multibyte-safe file operations with UTF-8 encoding

## [1.2.0] - 2026-04-17

### Added

- **Prompt Variable Node**: Define variables with sequential or random selection modes
  - Support for tag-based template replacement with `[TAG_NAME]` syntax
  - prefix/suffix support for flexible text formatting
  - Empty value support with empty line or `[NONE]` notation
  - Randomize toggle for easy mode switching
- **Variable Combiner Node**: Combine multiple variable lists
  - Support for 6 variable lists per node
  - Chainable for unlimited variable expansion
  - Unified `var_list` naming convention
- **Prompt Compiler Node**: Generate prompts from variables
  - Automatic template tag replacement mode
  - Simple join mode when template is empty
  - Sequential combination calculation with `itertools.product`
  - Random variable selection with seed control
  - Debug output showing all combinations
  - Automatic appending of unused variables
  - Warning system for unmatched tags

### Changed

- Improved architecture: Variables output as `VARIABLE_LIST` for direct connection to Compiler
- Optimized for FLUX.2 prompt generation with natural language templates

## [1.1.0] - 2026-04-13

### Breaking Changes

- **Node names updated for uniqueness**
  - `BiRefNet` → `SBTools_BiRefNet` (display: "BiRefNet RemoveBG (SBTools)")
  - `Find Unused Color` → `SBTools_AlphaToChromaKey` (display: "Alpha to Chroma Key (SBTools)")
- **Alpha to Chroma Key output changed**
  - Old: `hex_color`, `R`, `G`, `B` (4 outputs)
  - New: `hex_color`, `filled_image` (2 outputs)

### Added

- Alpha to Chroma Key: `filled_image` output - automatically fills transparent areas with the detected safe chroma key color
- Alpha channel detection with informative console logging

### Changed

- Simplified `requirements.txt` - only `huggingface_hub>=0.19.0` needed
- All nodes now use `SBTools_` prefix in class names to prevent naming conflicts
- Node display names include "(SBTools)" branding for easy identification

### Technical

- BiRefNet: Refactored to use explicit function parameters instead of `**kwargs`
- Improved code maintainability and IDE support
- Better parameter type checking and documentation

## [1.0.0] - 2026-04-13

### Added

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

### Optimizations

- Reduced model selection from 11 to 5 carefully chosen variants
- Improved aspect ratio handling for BiRefNet_dynamic
- Optimized processing resolution based on input size

### Technical

- Modular package structure
- English-only codebase
- Comprehensive README documentation
- Version tracking in `__init__.py`
