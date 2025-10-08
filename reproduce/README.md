# Reproduce Scripts Directory

This directory contains all scripts for reproducing HAFiscal paper results. These scripts are typically called by the main `../reproduce.sh` controller script, but can also be invoked directly for development or debugging.

## Quick Reference

```bash
# Typical usage (from project root):
./reproduce.sh                      # Interactive menu
./reproduce.sh --docs               # Compile documents
./reproduce.sh --comp min           # Minimal computation (~1 hour)
./reproduce.sh --comp all           # Full computation (1-2 days)

# Direct script usage (advanced):
./reproduce/reproduce_documents.sh          # LaTeX compilation
./reproduce/reproduce_computed_min.sh       # Minimal computation
./reproduce/reproduce_computed.sh           # Full computation
./reproduce/reproduce_environment_texlive.sh  # Test LaTeX environment
```

## Main Reproduction Scripts

### `reproduce_documents.sh` - LaTeX Document Compilation

**Purpose**: Compiles all LaTeX documents (main paper, slides, appendices, subfiles).

**Called by**: `../reproduce.sh --docs`

**Key Features**:
- **Scope control**: Compile different subsets of documents
  - `main`: Only repo root files (HAFiscal.tex, HAFiscal-Slides.tex)
  - `all`: Root + Figures/ + Tables/ + Subfiles/
  - `figures`: Root + Figures/
  - `tables`: Root + Tables/
  - `subfiles`: Root + Subfiles/
- **Build modes**: Via `BUILD_MODE` environment variable
  - `SHORT`: Quick debugging builds with reduced content
  - `LONG`: Complete versions (default)
- **Advanced options**:
  - `--clean`: Clean auxiliary files before compilation
  - `--quick`: Single-pass compilation (faster, may miss cross-references)
  - `--dry-run`: Show commands without executing
  - `--verbose`: Detailed output
- **Enhanced error reporting**: Parses LaTeX logs and provides helpful suggestions
- **Automatic cleanup**: Removes auxiliary files after compilation

**Direct Usage Examples**:
```bash
# Compile all root documents
./reproduce/reproduce_documents.sh --scope main

# Quick debug build
BUILD_MODE=SHORT ./reproduce/reproduce_documents.sh --quick

# See what would be executed
./reproduce/reproduce_documents.sh --dry-run

# Compile with verbose output
./reproduce/reproduce_documents.sh --verbose

# Compile everything including subdirectories
./reproduce/reproduce_documents.sh --scope all

# Clean and rebuild
./reproduce/reproduce_documents.sh --clean
```

**Environment Variables Used**:
- `BUILD_MODE`: SHORT or LONG (default: LONG)
- `ONLINE_APPENDIX_HANDLING`: LINK_ONLY or INCLUDE (default: LINK_ONLY)
- `PDFLATEX_QUIET`: quiet or verbose (affects LaTeX output)
- `VERBOSITY_LEVEL`: quiet, normal, or verbose (affects script messages)

**Error Handling**:
- Validates LaTeX environment before compilation
- Parses error logs for common issues
- Provides specific fix suggestions for:
  - Undefined control sequences
  - Missing files
  - Bibliography issues
  - Package errors

---

### `reproduce_computed.sh` - Full Computational Reproduction

**Purpose**: Runs all computational steps to reproduce paper results.

**Runtime**: ⚠️ **1-2 days** on modern laptop

**Called by**: `../reproduce.sh --comp all`

**What it does**:
1. Sources `reproduce_environment.sh` to validate Python environment
2. Changes to `Code/HA-Models/` directory
3. Creates empty `version` file (signals full reproduction, not minimal)
4. Runs `python do_all.py` with all steps enabled

**Direct Usage**:
```bash
./reproduce/reproduce_computed.sh
```

**Script Contents**:
```bash
#!/bin/bash
source ./reproduce/reproduce_environment.sh
cd Code/HA-Models || exit
rm -f version
touch version
python do_all.py
```

**Note**: Step selection is controlled by flags in `Code/HA-Models/do_all.py`, not by this script.

---

### `reproduce_computed_min.sh` - Minimal Computational Reproduction

**Purpose**: Runs subset of computations for quick validation.

**Runtime**: ~1 hour

**Called by**: `../reproduce.sh --comp min`

**What it does**:
1. Sources `reproduce_environment.sh` to validate environment
2. Changes to `Code/HA-Models/` directory
3. Creates `version` file with `_min` marker (signals minimal reproduction)
4. **Backs up existing tables** (if any) using `table_renamer.py`
5. Runs `python reproduce_min.py` (minimal computation script)
6. **Renames new tables** with `_min` suffix (e.g., `Table.tex` → `Table_min.tex`)
7. **Restores original tables** so paper continues to use full results

**Table Management**:
The script manages these tables:
- `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex`
- `FromPandemicCode/Tables/CRRA2/Multiplier.tex`
- `FromPandemicCode/Tables/CRRA2/welfare6.tex`
- `FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex`
- `FromPandemicCode/Tables/Splurge0/Multiplier_SplurgeComp.tex`

**Known Issue**: ⚠️ **References missing `table_renamer.py`** - script will fail if this file doesn't exist.

**Direct Usage**:
```bash
./reproduce/reproduce_computed_min.sh
```

**Workaround if table_renamer.py missing**:
```bash
cd Code/HA-Models
rm -f version
echo "_min" > version
python reproduce_min.py
# Note: Will overwrite existing tables without backup
```

---

## Environment Validation Scripts

### `reproduce_environment.sh` - Python/Conda Environment Check

**Purpose**: Validates Python environment has required packages for computation.

**Usage**: Sourced (not executed) by computational scripts

**Checks for**:
- Python 3.8+ (tested with 3.11.7)
- NumPy, SciPy, Matplotlib, Pandas
- econ-ark package (HARK)
- sequence-jacobian (via pip)
- Numba (for performance)

**How to use directly**:
```bash
source ./reproduce/reproduce_environment.sh
# If successful, environment is ready
# If fails, install missing packages

# Check individual packages:
python -c "import numpy; print('NumPy:', numpy.__version__)"
python -c "import HARK; print('HARK OK')"
python -c "import sequence_jacobian; print('sequence-jacobian OK')"
```

**Installation if packages missing**:
```bash
# Using conda (recommended):
conda env create -f ../binder/environment.yml
conda activate hafiscal

# Using pip:
pip install econ-ark==0.14.1 numpy pandas matplotlib scipy numba
pip install sequence-jacobian
```

---

### `reproduce_environment_texlive.sh` - LaTeX Environment Check

**Purpose**: Validates LaTeX installation and required packages.

**Called by**: `reproduce_documents.sh` during startup

**Checks for**:
- TeX Live installation
- latexmk, pdflatex, bibtex commands
- Required LaTeX packages (from `required_latex_packages.txt`)

**How to use directly**:
```bash
./reproduce/reproduce_environment_texlive.sh
# Exit code 0 = environment OK
# Exit code 1 = missing components
```

**Common Issues**:

**Missing latexmk**:
```bash
# macOS:
brew install mactex
# or
brew install basictex
brew install latexmk

# Ubuntu/Debian:
sudo apt-get install latexmk

# Other systems:
# Install from your package manager or CTAN
```

**Missing LaTeX packages**:
```bash
# Most packages come with full TeX Live distribution
# For minimal installations, use tlmgr:
sudo tlmgr install subfiles amsmath hyperref natbib ifthen

# Or install texlive-full:
sudo apt-get install texlive-full  # Ubuntu/Debian
```

---

## Utility Scripts

### `reproduce_html.sh` - HTML Generation (Experimental)

**Purpose**: Generates HTML version of paper using tex4ht/make4ht.

**Status**: Experimental, not part of main reproduction workflow

**Usage**:
```bash
./reproduce/reproduce_html.sh
```

**Requirements**:
- make4ht command available
- tex4ht LaTeX package

**Note**: May require adjustments to work correctly. The paper is primarily designed for PDF output.

---

### `reproduce-standalone-files.sh` - Subfiles Compilation

**Purpose**: Compiles all individual LaTeX subfiles in `../Subfiles/` directory.

**Usage**:
```bash
./reproduce/reproduce-standalone-files.sh
```

**What it does**:
- Finds all `.tex` files in `Subfiles/` directory
- Compiles each independently
- Reports success/failure for each
- Generates individual PDFs for each subfile

**Use case**: When you want to compile individual sections separately from main document.

---

### `setup-latexmk.sh` - Historical LaTeX Setup

**Purpose**: Historical script for latexmk configuration.

**Status**: Largely superseded by `.latexmkrc` in project root

**Note**: Modern setup uses the Perl-based `.latexmkrc` configuration file which provides:
- Circular cross-reference handling
- BibTeX wrapper integration
- Environment variable injection (BUILD_MODE, etc.)
- PDF viewer management

---

## Configuration Files

### `required_latex_packages.txt`

Lists LaTeX packages required for compilation. Used by `reproduce_environment_texlive.sh` to validate installation.

**Key packages**:
- econark (custom document class, included in repo)
- subfiles (modular document structure)
- amsmath, amsfonts, amssymb (mathematics)
- hyperref (cross-references and links)
- natbib (bibliography)
- ifthen (conditional compilation)
- graphicx (figures)
- booktabs (tables)

### `required_latex_packages_fixed.txt`

Alternate version of package requirements, possibly with fixes or modifications.

---

## Relationship to Main `reproduce.sh`

The main `../reproduce.sh` script is a **user-friendly wrapper** around these scripts. It provides:

### Additional Functionality:
1. **Interactive menu**: User-friendly selection interface
2. **Environment testing**: Validates setup before attempting reproduction
3. **Unified interface**: Single entry point for all reproduction tasks
4. **Non-interactive mode**: Via `REPRODUCE_TARGETS` environment variable
5. **Progress tracking**: Clear reporting of multi-step processes
6. **Error handling**: Graceful failure with helpful messages

### Call Flow Example:

```
User runs: ./reproduce.sh --docs
    ↓
reproduce.sh performs environment checks
    ↓
reproduce.sh calls: reproduce/reproduce_documents.sh --quick --verbose --scope main
    ↓
reproduce_documents.sh validates LaTeX environment via reproduce_environment_texlive.sh
    ↓
reproduce_documents.sh discovers .tex files in repo root
    ↓
reproduce_documents.sh calls latexmk for each document
    ↓
reproduce_documents.sh cleans up auxiliary files
    ↓
reproduce_documents.sh reports success/failure
    ↓
reproduce.sh displays summary
```

### When to Use Which:

**Use `../reproduce.sh` when**:
- You want interactive menu
- You're new to the repository
- You want environment validation first
- You're doing standard reproduction

**Use scripts directly when**:
- You're developing/debugging
- You need fine-grained control
- You're automating with other tools
- You understand what each script does

---

## Advanced Direct Usage

All scripts support being called from either project root or reproduce directory:

```bash
# From project root:
./reproduce/reproduce_documents.sh --scope main

# From reproduce directory:
cd reproduce
./reproduce_documents.sh --scope main
cd ..
```

Scripts detect their location and adjust paths automatically using:
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
```

---

## Known Issues and Limitations

### 1. Missing `table_renamer.py`

**Problem**: `reproduce_computed_min.sh` references this script but it doesn't exist in the repository.

**Impact**: Minimal computational reproduction will fail.

**Workarounds**:
```bash
# Option 1: Run reproduce_min.py directly (will overwrite tables)
cd Code/HA-Models
rm -f version; echo "_min" > version
python reproduce_min.py

# Option 2: Create minimal table_renamer.py stub
# (Contact repository maintainers for proper implementation)
```

**Recommended fix**: Either create the missing script or update `reproduce_computed_min.sh` to remove the dependency.

### 2. Environment Validation Strictness

**Problem**: Scripts may fail if optional dependencies are missing.

**Example**: Stata is optional (only for empirical data processing) but might cause warnings/errors if not present.

**Workaround**: Comment out strict checks if you know you don't need certain components.

### 3. Path Assumptions

**Problem**: Some scripts assume specific directory structures.

**Impact**: Moving files or reorganizing directories may break scripts.

**Mitigation**: Scripts use relative paths and path resolution, but test after any structural changes.

---

## Development Guidelines

### Adding a New Reproduction Script

When creating a new reproduction script in this directory:

1. **Follow naming convention**: `reproduce_<aspect>.sh`

2. **Add help message**:
   ```bash
   show_help() {
       cat << 'EOF'
   Script Name - Brief Description
   
   USAGE:
       ./reproduce_script.sh [OPTIONS]
   
   OPTIONS:
       --help, -h    Show this help
       # ... other options
   EOF
   }
   ```

3. **Include environment validation**:
   ```bash
   # Source appropriate environment script
   source ./reproduce/reproduce_environment.sh
   # or
   source ./reproduce/reproduce_environment_texlive.sh
   ```

4. **Use consistent logging**:
   ```bash
   log_info() { echo "📋 $*"; }
   log_success() { echo "✅ $*"; }
   log_error() { echo "❌ ERROR: $*" >&2; }
   log_warning() { echo "⚠️  WARNING: $*"; }
   ```

5. **Make callable from multiple directories**:
   ```bash
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
   cd "$PROJECT_ROOT" || exit 1
   ```

6. **Set bash strict mode**:
   ```bash
   set -eo pipefail
   ```

7. **Update documentation**:
   - Add section to this README
   - Update main `../reproduce.sh` if user-facing
   - Update `../README.md` if appropriate

---

## Testing Scripts

### Unit Testing Individual Scripts

```bash
# Test document compilation (dry-run mode)
./reproduce/reproduce_documents.sh --dry-run
# Should show latexmk commands without executing

# Test LaTeX environment validation
./reproduce/reproduce_environment_texlive.sh
# Exit code 0 = OK, 1 = missing components

# Test Python environment
source ./reproduce/reproduce_environment.sh && echo "Python environment OK"
# Should source successfully if environment is good

# Test minimal computation (if table_renamer.py exists)
./reproduce/reproduce_computed_min.sh
# Should complete in ~1 hour
```

### Integration Testing

Use the main reproduction workflow for complete testing:

```bash
# Interactive test with environment validation
./reproduce.sh

# Non-interactive document reproduction
REPRODUCE_TARGETS=docs ./reproduce.sh

# Complete workflow test (WARNING: 1-2 days)
REPRODUCE_TARGETS=all ./reproduce.sh
```

---

## Script Dependencies

### Dependency Graph

```
reproduce.sh (main controller)
  ├─→ reproduce_environment_texlive.sh
  ├─→ reproduce_documents.sh
  │    └─→ reproduce_environment_texlive.sh
  ├─→ reproduce_computed_min.sh
  │    ├─→ reproduce_environment.sh
  │    └─→ table_renamer.py (MISSING)
  └─→ reproduce_computed.sh
       └─→ reproduce_environment.sh
```

### External Dependencies

**System commands used**:
- `latexmk`, `pdflatex`, `bibtex` (LaTeX compilation)
- `python`, `python3` (computational reproduction)
- `conda` (optional, for environment management)
- `find`, `sed`, `grep`, `stat` (shell utilities)

**Files referenced**:
- `../Code/HA-Models/do_all.py` (computational orchestrator)
- `../Code/HA-Models/reproduce_min.py` (minimal computation)
- `../.latexmkrc` (LaTeX configuration)
- `../binder/environment.yml` (Python dependencies)
- `./table_renamer.py` (**MISSING** - causes issues)

---

## Additional Resources

- **Main README**: `../README.md` - Complete project documentation
- **Code Documentation**: `../Code/README.md` - Computational workflow details
- **AI Documentation**: `../README_IF_YOU_ARE_AN_AI/` - AI-optimized guides
  - `000_AI_QUICK_START_GUIDE.md` - Entry point for AI systems
  - `030_COMPUTATIONAL_WORKFLOWS.md` - Detailed computational guide
  - `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` - AI-specific troubleshooting
- **LaTeX Configuration**: `../.latexmkrc` - Multi-layer compilation system
- **Build System**: `../README_IF_YOU_ARE_AN_AI/COMPILATION.md` - LaTeX architecture

---

## Quick Command Reference

```bash
# Document compilation
./reproduce/reproduce_documents.sh                 # All root documents
./reproduce/reproduce_documents.sh --scope all     # Including subdirs
BUILD_MODE=SHORT ./reproduce/reproduce_documents.sh --quick  # Debug build
./reproduce/reproduce_documents.sh --dry-run       # Preview commands

# Computational reproduction
./reproduce/reproduce_computed_min.sh              # Minimal (~1 hour)
./reproduce/reproduce_computed.sh                  # Full (1-2 days)

# Environment validation
./reproduce/reproduce_environment_texlive.sh       # LaTeX check
source ./reproduce/reproduce_environment.sh        # Python check

# Subfiles
./reproduce/reproduce-standalone-files.sh          # Compile all subfiles

# Via main controller (recommended)
./reproduce.sh                                      # Interactive menu
./reproduce.sh --docs                               # Documents
./reproduce.sh --comp min                           # Minimal computation
./reproduce.sh --comp all                           # Full computation
```

---

**Last Updated**: 2025-10-05  
**Maintainer**: See main repository documentation  
**Issues**: Report via repository issue tracker (if available)
