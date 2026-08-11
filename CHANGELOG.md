# Changelog

All notable changes to ComfyUI-SBTools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-08-11

### Changed

- **Save Text: existing `Sequential` numbering continues differently.** The counter no longer depends on `filename_prefix`, so two prefixes saved into the same folder now share one rising sequence (`alpha_0001, alpha_0002, beta_0003`) where they previously each started at `0001`. No node input, output, or widget changed, so saved workflows load unchanged.

### Fixed

- **Save Text: `Sequential` restarted at `0001` on every execution when `filename_prefix` contained a timestamp.** The counter scan built an exact-match pattern from the expanded prefix, so `20260811_141635_(\d+)` never matched the previous run's `20260811_141634_0001.txt`. The prefix is now a wildcard in the scan: the counter is the highest number already present in the folder plus one, independent of the prefix. Two different prefixes saved into the same folder therefore share one rising sequence rather than each starting over at `0001`.
- **Save Text: `Sequential` could silently overwrite an existing file.** The counter was taken as scan-maximum + 1 with no check that the resulting path was free, so any file the scan pattern did not cover was clobbered. The counter now advances past occupied names, making `Sequential` never overwrite as documented.

- **Save Text: `separator` was the only input never sanitized**, and it is concatenated into the filename *after* the path-traversal check has run on the directory. `/`, `\`, `../` and `*` raised `FileNotFoundError`/`OSError` mid-write; `:` created an NTFS alternate data stream, leaving a 0-byte visible file with the text hidden inside it; and `\..\..\..\` wrote outside the ComfyUI output directory entirely. It now goes through the same forbidden-character filter as `filename_prefix`, minus the trim and the fallback — a space and an empty string stay valid separators. Only `Sequential` mode used this input, so `Overwrite` and `Append` were never affected.

The sequence is scoped to the folder, the `extension`, and the `counter_position`. The scan deliberately reads only the configured position: interpreting both layouts would let a digit-bearing prefix pass for a counter — `20260811_142349_0001.txt` reads as counter `20260811` under the `Front` pattern — and push the sequence to eight digits. Switching `Front`/`Back` mid-sequence therefore restarts the numbering, though the existence check still prevents any file from being lost.

## [2.0.0] - 2026-07-30

### ⚠️ Breaking Changes

- **Variable Builder: `MAX_COMBINATIONS` and `ALL_COMBINATIONS` outputs removed**
  - Moved to the new **Variable Debug** node. Connect that instead.
  - They were observation outputs computed on *every* execution whether or not anything was connected to them.
  - They were the last two output slots, so `PROMPT` and `IMAGE1`–`IMAGE4` keep their positions and their links survive. Only links from the two removed slots are dropped.
- **Generated results change for the same seed.** Conditions that were silently dropped now apply (see below), so the pool of available values is different. This is unavoidable — the previous results were produced by conditions that were not fully in effect.

### Added

- **Variable Debug node** (`SBTools/Prompt`)
  - Lists the first N combinations and, optionally, the total count.
  - `max_display` (default 100) — enumeration stops there, so cost does not grow with graph size.
  - `show_total` (default **off**) — counting is the expensive part, and on a large conditional graph the exact number is unreachable anyway.
  - Takes only `var_list`, so ComfyUI caches it: changing `seed`/`index` on the Builder does not re-run it.
  - Can be attached partway through a Combiner tree to inspect an intermediate state.
- **Value weights: `--N` suffix**
  - `naked --3` means "3 copies of this line" — exactly equivalent to writing the line 3 times.
  - Works on `[NONE] --20` too. Decimals allowed (`--0.5`); `--0` disables a value without deleting it.
  - Duplicate lines add up, and a value present in both the common list and a matching conditional block contributes both weights.
  - Applies to **Random / ConditionalRandom** only — Sequential enumerates every value exactly once, so weights have no meaning there.
  - Negative weights raise an error. The marker is positional: `--` at the *start* of a line is still the exclusion syntax.
- **`output_to_prompt` toggle on Variable Prompt** (default on)
  - Turn off to make a control-only variable: it still resolves a value and other variables can still branch on it, but it never reaches the prompt — not even when its `[TAG]` is written in the template.
  - Declared as the last widget, so existing saved workflows load unchanged.
- **Condition diagnostics**
  - `[TAG:value]` was previously accepted with no validation at all. Now warns when the tag does not exist, when the value is not one of that tag's values, or when the tag belongs to a variable connected *after* this one (conditions can only see earlier variables).
  - Warns when a condition line has content past the first `]`, instead of discarding it silently.

### Fixed

- **Conditions could not hold more than one constraint per tag.** `[!CLOTHING:naked&&!CLOTHING:bikini]` kept only the last one, because condition keys were collapsed through a `dict()`. All constraints now apply.
- **Logically identical conditions gave different results depending on the order they were written in.** A side effect of the above: `[A&&C||B&&C]` and `[B&&C||A&&C]` resolved differently, and which one worked depended on alphabetical ordering of the values.
- **Combination counting exhausted memory.** The total was obtained by materializing every combination in a list and taking its length. Counting is now arithmetic, memoised, and capped (`COMBINATION_LIMIT`, 100,000); `resolve_index` falls back to a non-counting strategy above that. A graph with conditional variables can describe more combinations than can ever be enumerated.
- **The debug listing re-derived every entry from scratch.** It called `resolve_index` once per line, and each of those calls counted the whole combination space — the 100-line cap bounded the output but not the work. It now enumerates lazily and stops at the limit.
- **A variable with no values dead-ended enumeration.** Because it yielded nothing instead of resolving to empty, the search backtracked through every earlier combination without ever producing a result, which looked like a hang.
- **A graph made only of Conditional variables reported 1 combination** and its index never advanced. Counting required a variable in `Sequential` mode specifically.
- **Console output crashed on non-UTF-8 terminals.** Warning messages used `⚠️` and `→`, which raise `UnicodeEncodeError` under code pages such as cp932 (Japanese Windows). All console output is now ASCII.
- Text values containing `/` were truncated to their last path segment in the debug listing, due to operator precedence in the image-path check.
- Variable Builder resolved the same values twice per execution.

### Notes on condition syntax

`&&` separates groups and `||` lists alternatives *within* a group, so a condition reads as
`[A||B && C||D]` = (A or B) and (C or D). This was never documented and is unchanged, but it is
worth stating explicitly now that constraints are no longer silently dropped: write
`[COMPOSITION:breast focus||COMPOSITION:upper body&&POSE_CATEGORY:sitting pose]`, not
`[COMPOSITION:breast focus&&POSE_CATEGORY:sitting pose||COMPOSITION:upper body&&POSE_CATEGORY:sitting pose]`.
A condition is a single bracketed expression — `[A]&&[B]` is not valid and now warns.

## [1.6.0] - 2026-05-27

### Added

- **Save Text Node**: Save any text string from a ComfyUI workflow to a local file
  - Three write modes: `Sequential` (numbered files), `Overwrite`, `Append`
  - `folder_path` and `filename_prefix` support Python `strftime` formatting (e.g., `%Y/%m/%d`, `%Y%m%d_%H%M%S`)
  - Sequential mode: zero-padded counter with configurable digits (1–9), position (Front/Back), and separator
  - Append mode: smart newline insertion — prepends `\n` only when the target file already has content
  - Path traversal protection using `os.path.abspath` + `os.path.commonpath`; different-drive paths rejected
  - Fast counter scanning with `os.scandir()` and regex matching (tolerant of digit-length changes)
  - Sanitization per input type: folder separators preserved in `folder_path`, stripped from `filename_prefix`
  - Terminal node (`OUTPUT_NODE = True`) with no output pins; `text` input is connection-only (`forceInput`)
  - Files always written with UTF-8 encoding
  - Example workflow: `Save Text.json` / `Save Text.webp`

## [1.5.1] - 2026-04-27

### Added

- **NOT Condition (`!`)**: Negate conditions to match "everything except" logic
  - Syntax: `[man&&!young]` matches man AND NOT young
  - Works in both Variable Prompt and Variable Folder
  - Example use case: `[man&&!young]` adds "trench coat" only for non-young men
  - Implemented across condition parsing, matching, and combination generation
  - Full support in `parse_condition_line`, `matches_condition`, `_enumerate_combinations`, `resolve_index`
- **Exclusion Syntax (`--value`)**: Remove specific values from inherited common values
  - Syntax: `--t-shirt` (in values list) excludes "t-shirt" from current context
  - Context-aware exclusions: Common exclusions and conditional exclusions
  - Variable Prompt: Exclude text values based on conditions
  - Variable Folder: Exclude folder paths (converted to image path exclusions)
  - New data structure: `exclusions: {"common": [], "conditional": {}}`
  - Applied via `_apply_exclusions` helper function in all combination generation paths
- **Exclusive Mode (`--only`)**: Completely override common values for specific conditions
  - Syntax: `[man&&young] --only` (after condition line)
  - When `--only` is set, common values are ignored for that specific condition
  - Example: Common values (suit, casual) + `[man&&young] --only` → school uniform replaces all
  - New data structure: `only_flags: {condition_key: True}`
  - Applied in conditional value resolution across all modes (Conditional, ConditionalRandom)
- **Example Workflow**: Variable Prompt Conditional_3.json demonstrating all three features
  - man + young: school uniform only (--only)
  - man + middle: suit, ~~t-shirt~~ (excluded), jacket, trench coat
  - man + old: suit, t-shirt, trench coat
  - woman + \*: suit, t-shirt (common values)

### Changed

- **Condition data structure**: Extended from 2-tuple to 3-tuple format
  - Old: `(value, tag)` → New: `(value, tag, is_negated)`
  - Example: `("young", None, True)` represents NOT young
  - Backward compatible: `matches_condition` handles both old and new formats
- **Condition keys in expand_or_conditions**: Modified to support value-negation pairs
  - Old format: `(("GENDER", "man"), ("AGE", "young"))`
  - New format: `(("GENDER", ("man", False)), ("AGE", ("young", True)))`
  - Allows dict() conversion while preserving negation information
- **Variable data structure**: Added `exclusions` and `only_flags` fields
  - Both Variable Prompt and Variable Folder now store exclusion rules and only flags
  - Exclusions applied during value filtering in all combination paths
  - Only flags checked during conditional value resolution
- **\_count_subsequent_combinations**: Now applies exclusions and only_flags
  - Previously didn't account for exclusions, causing incorrect combination counts
  - Fixed duplicate value issues in index resolution
  - Ensures combination count matches actual generated combinations

### Technical

- **NOT condition implementation**:
  - Parse `!` prefix in `parse_condition_line` to extract negation flag
  - Store negation as third element in condition tuple
  - Apply negation in `matches_condition` by inverting match result
- **Exclusion implementation**:
  - Parse `--value` syntax in value/folder parsing
  - Store exclusions separately from values (common and conditional)
  - Apply exclusions via `_apply_exclusions` helper using list comprehension
  - For Variable Folder: Load images from excluded folders, store as exclusion list
- **Exclusive mode implementation**:
  - Parse `--only` flag from condition line options
  - Store flag in `only_flags` dict with condition key
  - Check flag during conditional value resolution: if set, skip common values
  - Applies to both Conditional and ConditionalRandom modes
- **Condition parsing flow**:
  1. `normalize_condition_syntax`: Normalize `AND`/`OR`/full-width to `&&`/`||`
  2. `parse_condition_line`: Parse into structured format with negation flags
  3. `expand_or_conditions`: Expand OR groups, create condition keys with negation
  4. `matches_condition`: Match with negation support
- **Variable Folder specifics**:
  - `_parse_condition_line_with_only`: Extended version that parses `--only` flag
  - Folder exclusions converted to image path exclusions after file loading
  - Exclusions stored as image paths, not folder paths

### Fixed

- **Combination count accuracy**: Fixed duplicate combinations in index resolution
  - `_count_subsequent_combinations` now applies exclusions and only_flags
  - Prevents miscounting when exclusions or only mode are active
  - Example: Without fix, man+middle showed "jacket" twice; now correct

### Notes

- All three features work seamlessly together and can be combined
- NOT condition is most useful for "mature/non-young" type logic
- Exclusion syntax removes specific items while keeping others
- Exclusive mode (`--only`) recommended over exclusion for clearer intent when replacing entire value sets
- Variable Folder exclusion works at folder level, then converts to image paths

## [1.5.0] - 2026-04-24

### Added

- **Variable Folder Node**: Define conditional image folder mappings based on variable context
  - Context-aware image loading: switch folders based on GENDER, CLOTHING, or other conditions
  - Flexible condition syntax: `[man]`, `[man&&suit]`, `[woman||old]`, `[GENDER:man]`, `[*]`
  - Condition options: `--random`, `--sequential` for selection mode control
  - Path options: `--subfolder`, `--pattern=*.png`, `--extension`, `--fill-bg=#FFFFFF`
  - Pre-loads image files from folders and passes to Variable Image Loader
  - Warnings for unmatched conditions to catch configuration errors
  - Auto-naming support (leave `variable_name` empty for `_IMAGE_xxxxxx`)
- **Variable Image Loader integration**: Accept folder mappings from Variable Folder
  - When Variable Folder is connected, folder mappings from Variable Folder are always used
  - When Variable Folder is disconnected or bypassed, loader's own `folder_path` parameter is used
  - Applies loader settings (randomize, seed, fill_background, etc.) to image folder variables
- **Variable Builder enhancements**: Support for image variables from Variable Folder
  - Resolves conditional image variables based on current context
  - Empty image (64×64 black) when no images match the condition
  - Multiple image variables (IMAGE1-IMAGE4) with independent configuration

### Changed

- **Combination calculation algorithm**: Completely rewritten from modulo-based to cumulative-based approach
  - `resolve_index` now uses cumulative combination counts for accurate resolution
  - New function `_count_subsequent_combinations` calculates combinations for variables after current position
  - More accurate handling of conditional variables with unbalanced value counts
  - Variable change order: first variable now changes slowest (cumulative approach characteristic)
- **Variable order control**: Variables now change in connection order
  - Order is determined by node connection sequence, not alphabetical
  - Allows users to control which variables change faster/slower
- **Empty value handling**: Combinations with no matching values now continue instead of being skipped
  - Text variables: empty string `""` (ignored in prompt)
  - Image variables: empty image 64×64 black placeholder
  - Ensures combination count remains consistent

### Fixed

- **Conditional variable handling**: Fixed issues with unbalanced value counts
  - Previous modulo-based approach caused incorrect value selection when conditions had different counts
  - Example: `[man]:3 values, [woman]:5 values` now correctly cycles through all values
- **Combination skipping**: Fixed bug where combinations were lost when no values matched conditions
  - Empty values are now preserved instead of removing the combination entirely
- **Space in condition values**: Improved parsing for condition values containing spaces
  - Example: `[man&&casual wear]` now correctly parsed
- **ConditionalRandom mode**: Excluded from unused condition warnings
  - `_check_unused_conditions` now skips ConditionalRandom variables
  - Avoids false warnings for intentionally random conditional variables

### Technical

- **Cumulative combination algorithm**:
  - For each variable position, calculate total combinations of all subsequent variables
  - Divide current index by subsequent combinations to get current variable's index
  - More mathematically sound than modulo-based approach
  - Slightly different performance characteristics but generally equivalent speed
- **Image folder variable type**: New `type: "image_folder"` for variables from Variable Folder
  - Stores folder paths and options before image loading
  - Variable Image Loader converts to actual image paths
- **Natural sort order**: Consistent file ordering across Variable Folder and Variable Image Loader
  - Windows Explorer-like ordering (file1, file2, ..., file10)

### Notes

- **Variable change order**: Due to cumulative algorithm, first variable changes slowest
  - This is different from previous modulo-based approach where first variable changed fastest
  - Users can control order by adjusting node connection sequence
- **Backward compatibility**: Existing workflows continue to work
  - Node interfaces unchanged
  - Only internal calculation logic changed
  - Combination order may differ from previous versions

## [1.4.1] - 2026-04-21

### Changed

- **Code organization**: Refactored file names and class names to align with node registration IDs
  - `prompt_variable.py` → `variable_prompt.py` (class: `SBTools_VariablePrompt`)
  - `image_variable.py` → `variable_image_loader.py` (class: `SBTools_VariableImageLoader`)
  - `multi_compiler.py` → `variable_builder.py` (class: `SBTools_VariableBuilder`)
  - All file names now match their node registration IDs for better code readability
  - Updated `__init__.py` imports to reflect new file names

### Technical

- Node registration IDs remain unchanged, ensuring full backward compatibility
- Existing workflow JSON files continue to work without modification
- Improved codebase maintainability and consistency

## [1.4.0] - 2026-04-20

### Breaking Changes

- **Node naming update**: All variable-related nodes renamed for better organization
  - `Prompt Variable` → `Variable Prompt`
  - `Image Variable Loader` → `Variable Image Loader`
  - `Multi Compiler` → `Variable Builder`
  - `Variable Combiner` → (unchanged)
  - All nodes now start with "Variable" prefix for alphabetical grouping in node lists
- **Node consolidation**: Removed Prompt Compiler and Compiler Debug nodes
  - All functionality merged into Variable Builder
  - Variable Builder now includes `max_combinations` and `all_combinations` outputs
  - Old nodes backed up in `backups/`

### Added

- **Conditional Variable System**: Define variables that change based on previous variable values
  - Flexible condition syntax: `[man&&suit]`, `[suit||casual]`, `[*&&suit]`
  - Multiple syntax support: `&&`, `AND` (uppercase) for AND conditions, `||`, `OR` (uppercase) for OR conditions
  - Full-width support: `＆＆`, `｜｜`, `：` for Japanese input compatibility
  - Wildcard support: `[*&&suit]` for "any value + suit", `[*]` to return to common values
  - Tag name specification: `[GENDER:man&&CLOTHING:suit]` to handle duplicate values across tags
  - ConditionalRandom mode: Random selection within conditional context
  - `var_list` input on Prompt Variable node enables conditional logic based on previous variables
- **Variable Builder enhancements**: All compiler functionality unified in one node
  - `max_combinations` output: Total number of combinations (INT)
  - `all_combinations` output: Debug text listing all patterns with index numbers (STRING)
  - Random variables show available choices: `[RANDOM: watch|glasses|cap]`
  - Conditional random shows context-aware choices: `[RANDOM: glasses|watch|tie]` (for man+suit)
  - Empty values displayed as `(none)` for clarity
  - Template mode and simple join mode support
  - Works for text-only, image-only, or combined workflows
  - Performance: 10,000+ combinations enumerate quickly (under 1 second)
- **Auto-naming for tag_name**: Leave tag_name empty for automatic unique naming
  - Default changed from "TAG" to empty string
  - Empty tag names automatically assigned unique IDs (`_VAR_xxxxxx`)
  - Auto-named variables bypass duplicate checking (always allowed)
  - Useful for simple workflows without template replacement
- **Variable Combiner duplicate detection**:
  - Exact duplicates (same name, values, mode) automatically skipped with info message
  - Conflicting duplicates (same name, different values) throw error and stop execution
  - Auto-named variables (`_VAR_*`) exempt from duplicate checking
- **Conditional variable warnings**:
  - Warns when condition syntax doesn't match any previous variable values
  - Shows which values will be ignored due to unmatched conditions
  - Helps catch typos and configuration errors early

### Changed

- `compiler_utils.py` centralized: All compilation logic unified in single module
- Variable Prompt now accepts optional `var_list` input for conditional variable support
- Node names updated: all variable nodes now start with "Variable" for better organization

### Technical

- Condition parsing with normalization of multiple syntaxes (`&&`, `AND`, `＆＆` → `&&`, `||`, `OR`, `｜｜` → `||`)
- Case-sensitive keyword matching (uppercase `AND`/`OR` only) to avoid conflicts with natural language
- Full-width character support for Japanese input (`＆＆`, `｜｜`, `：`)
- OR condition expansion into multiple condition keys using `itertools.product`
- Lazy evaluation for conditional variable resolution based on current context
- Recursive combination enumeration for accurate total calculation

### Fixed

- Fixed typo in Compiler Debug node image conversion (`convert` → `img.convert`)

## [1.3.0] - 2026-04-17

### Added

- **Variable Image Loader Node**: Load images from folder with flexible control
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

- Variable Image Loader: Default filename output without extension for cleaner display

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
