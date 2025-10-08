# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

HAFiscal is a research paper repository studying welfare and spending effects of consumption stimulus policies using heterogeneous agent models. The project combines LaTeX document compilation with computational reproduction of economic models.

## Key Build Commands

### Document Compilation
```bash
# Interactive reproduction menu
./reproduce.sh

# Specific targets
./reproduce.sh --docs          # Compile LaTeX documents (~few minutes)
./reproduce.sh --subfiles      # Compile all subfiles
./reproduce.sh --min           # Minimal computational results (~1 hour)
./reproduce.sh --all           # Full computational results (1-2 days)

# Non-interactive mode using environment variables
REPRODUCE_TARGETS=docs ./reproduce.sh
REPRODUCE_TARGETS=min,docs ./reproduce.sh
```

### LaTeX Version Management
```bash
# Build specific document versions using BUILD_MODE
BUILD_MODE=SHORT ./reproduce.sh --docs   # Quick build for debugging  
BUILD_MODE=LONG ./reproduce.sh --docs    # Complete version (default)

# Advanced compilation options
./reproduce.sh --docs --scope all        # Include Figures/, Tables/, Subfiles/
./reproduce.sh --docs --clean            # Clean auxiliary files first
./reproduce.sh --docs --dry-run          # Show commands without execution
./reproduce.sh --docs --quick            # Single-pass compilation
```

### Python Environment
```bash
# Set up development environment
make setup

# Sync dependency files from pyproject.toml
make sync

# Run tests
make test

# Clean build files
make clean          # Python cache files
make clean-pdf      # LaTeX build files
```

### Computational Reproduction
```bash
# Step-by-step execution (from Code/HA-Models/)
python do_all.py    # Control flags in file determine which steps run

# Individual steps (requires changing flags in do_all.py):
# Step 1: Splurge factor estimation (~20 minutes)
# Step 2: Discount factor distributions (~21 hours)
# Step 3: Robustness with Splurge=0 (~21 hours)
# Step 4: HANK model (~1 hour)
# Step 5: Policy comparisons (~65 hours)
```

## Architecture

### Project Structure
- **HAFiscal.tex**: Main paper document with version-controlled compilation
- **Subfiles/**: Individual sections that can be compiled standalone
- **Code/HA-Models/**: Core computational models and reproduction scripts
- **Code/Empirical/**: Stata scripts for data analysis
- **@local/**: Project-specific configuration files
- **@resources/**: Shared LaTeX resources and tools

### Multi-Layer Conditional Compilation System
The project implements a sophisticated three-layer conditional compilation system:

1. **BUILD_MODE Layer**: Environment variable controls document length
   - `BUILD_MODE=SHORT`: Quick debugging builds with reduced content
   - `BUILD_MODE=LONG`: Complete versions (default)
   - Uses `\ifdefined\ShortVersion` LaTeX conditionals

2. **Smart Bibliography Layer**: `\smartbib` system provides intelligent bibliography inclusion
   - Automatically detects standalone vs. integrated compilation contexts
   - Includes only citations actually used in the document
   - Handles cross-references between main document and subfiles

3. **PDF/HTML Dual Output Layer**: Web boolean controls format-specific content
   - `\pdfonly{content}`: Executes only for PDF compilation
   - `\webonly{content}`: Executes only for HTML/web compilation  
   - `\weborpdf{web-content}{pdf-content}`: Format-specific alternatives
   - Enables single source files to generate multiple output formats

### Computational Pipeline
The economic models follow a 5-step process controlled by `Code/HA-Models/do_all.py`:
1. Estimate splurge factor using Norwegian lottery data
2. Estimate discount factor distributions (computationally intensive)
3. Robustness checks with different parameters
4. HANK model solving and analysis
5. Policy comparison and welfare analysis

### Bibliography Management
- **HAFiscal.bib**: Main bibliography with Paperpile integration
- **system.bib**: System-wide bibliography with crossref compatibility
- All bibliographies synchronized and alphabetically sorted

## Important Notes

### LaTeX Compilation
- Uses `latexmk` with custom `.latexmkrc` for circular reference handling and enhanced cleanup
- Multi-layer conditional compilation system supports multiple document versions from single source
- All subfiles can compile standalone or as part of the main document using `\pdfonly{\end{document}}` pattern
- Enhanced auxiliary file cleanup including `.txt`, `.dep`, and standard LaTeX build artifacts
- Sophisticated package management with `@local/local.sty` and `@local/local-qe.sty` for different compilation contexts
- PDF/HTML dual compilation support through `@local/webpdf-macros.sty` conditional macros

### Dependencies
- Python 3.11.7 with specific package versions (see `binder/environment.yml`)
- Key packages: econ-ark=0.14.1, sequence-jacobian (pip)
- Stata required for empirical data processing

### File Patterns
- Computational results output to `Code/HA-Models/Results/`
- LaTeX tables generated in `Code/HA-Models/FromPandemicCode/Tables/`
- Figures generated in source locations (`Code/HA-Models/`) and symlinked to `Figures/`
- Portable path system via `\FigsDir` macro for environment-independent figure referencing
- PDFs compiled to root directory with version suffixes
- Enhanced auxiliary file cleanup (`.txt`, `.dep`, standard LaTeX files)

### Additional Documentation

For detailed information about specific systems:
- **COMPILATION.md**: Comprehensive guide to the multi-layer LaTeX compilation system
- **FIGURE-MANAGEMENT.md**: Complete documentation of symlink-based figure organization and portable path system

### Testing
- Test computational scripts via `make test` or `pytest tests/`
- Test document compilation via `./reproduce.sh --docs`
- Test individual subfiles via `./reproduce.sh --subfiles`  
- Test figure system: `./reproduce.sh --docs --scope figures`
- Test with different build modes: `BUILD_MODE=SHORT ./reproduce.sh --docs`