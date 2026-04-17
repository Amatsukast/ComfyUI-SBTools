# Changelog

All notable changes to ComfyUI-SBTools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [1.1.0] - Previous Release

### Added
- BiRefNet background removal node
- Alpha to Chroma Key node

## [1.0.0] - Initial Release

### Added
- Initial release of ComfyUI-SBTools
