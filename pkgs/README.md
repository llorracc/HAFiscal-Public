# MiKTeX Package Discovery System

This directory contains tools for discovering and managing LaTeX package dependencies for the HAFiscal project.

## Overview

The HAFiscal project uses many standalone `.tex` files (in `Tables/`, `Figures/`, `Subfiles/`) that can be compiled independently. Each file may require different LaTeX packages. This system automatically discovers all package dependencies by compiling each file and recording what MiKTeX installs.

## How It Works

### 1. Package Discovery (`discover-packages.sh`)

This script:

1. Scans `Tables/`, `Figures/`, and `Subfiles/` directories for `.tex` files
2. Compiles each file with `pdflatex` in standalone mode
3. Parses compilation logs to extract three types of dependencies:
   - **Installed packages** - LaTeX packages installed via MiKTeX Package Manager (mpm)
   - **Generated fonts** - Fonts generated on-demand by METAFONT
   - **Loaded packages** - Packages referenced in the document
4. Saves dependencies for each file to a `.pkgs` file
5. Creates an aggregate list of all unique dependencies

### 2. Output Files

After running `discover-packages.sh`, you'll get:

```
pkgs/
├── Tables_calibration.pkgs           # Dependencies for Tables/calibration.tex
├── Tables_estimBetas.pkgs            # Dependencies for Tables/estimBetas.tex
├── Figures_HANK_IRFs.pkgs            # Dependencies for Figures/HANK_IRFs.tex
├── Subfiles_Conclusion.pkgs          # Dependencies for Subfiles/Conclusion.tex
├── aggregate-packages.txt            # Combined list of ALL dependencies
└── logs/
    ├── Tables_calibration.log        # Full compilation log
    └── ...
```

### 3. Package File Format (`.pkgs`)

Each `.pkgs` file contains a list of dependencies in this format:

```
# Package dependencies extracted from compilation
# Format: package_name (source: installation|font-generation|loaded)

amsmath (loaded)
cm (loaded)
cmr10 (font-generation)
tikz (installation)
```

## Usage

### Discover All Package Dependencies (Interactive Mode)

By default, the script runs in **interactive mode**, pausing after each file that triggers installations:

```bash
cd ~/GitHub/llorracc/HAFiscal-Latest
./pkgs/discover-packages.sh
```

After each file compiles, you'll see:

```
════════════════════════════════════════════════════════════
  Dependencies for: Tables/calibration.tex
════════════════════════════════════════════════════════════
Installed packages (3):
  • booktabs
  • multirow
  • tabularx
Generated fonts (2):
  • cmr10
  • cmmi10
Loaded packages (15):
  • amsmath
  • graphicx
  ... and 13 more
════════════════════════════════════════════════════════════

Press ENTER to continue to next file (or Ctrl+C to stop)...
```

### Non-Interactive Mode (No Pausing)

To run without pausing (useful for CI/CD or batch processing):

**Option 1: Command-line flag**

```bash
./pkgs/discover-packages.sh --no-pause
```

**Option 2: Environment variable**

```bash
MIKTEX_NO_PAUSE=1 ./pkgs/discover-packages.sh
```

Both methods will:

- Compile all standalone `.tex` files
- Generate `.pkgs` files for each
- Create `aggregate-packages.txt` with all unique dependencies
- Skip the interactive pauses

### Install All Discovered Packages

After discovering packages, install them all at once:

```bash
# Extract package names and install
grep '(installation)' pkgs/aggregate-packages.txt | \
  cut -d' ' -f1 | \
  xargs -I {} sudo mpm --admin --install={}
```

### Check Dependencies for a Specific File

```bash
# See what packages Tables/calibration.tex needs
cat pkgs/Tables_calibration.pkgs
```

### View Compilation Logs

If a file fails to compile, check the detailed log:

```bash
cat pkgs/logs/Tables_calibration.log
```

## Integration with Docker/CI

The discovered packages can be pre-installed in Docker containers or CI pipelines:

```dockerfile
# In .devcontainer/Dockerfile
COPY pkgs/aggregate-packages.txt /tmp/aggregate-packages.txt
RUN grep '(installation)' /tmp/aggregate-packages.txt | \
    cut -d' ' -f1 | \
    xargs -I {} mpm --admin --install={}
```

## Workflow

### Initial Setup (First Time)

1. Install minimal MiKTeX:

   ```bash
   sudo ~/GitHub/llorracc/HAFiscal-dev/build/reinstall-miktex-essential.sh
   ```

2. Discover all package dependencies:

   ```bash
   cd ~/GitHub/llorracc/HAFiscal-Latest
   ./pkgs/discover-packages.sh
   ```

3. Install all discovered packages:

   ```bash
   grep '(installation)' pkgs/aggregate-packages.txt | \
     cut -d' ' -f1 | \
     xargs -I {} sudo mpm --admin --install={}
   ```

### When Adding New Files

If you add new `.tex` files to `Tables/`, `Figures/`, or `Subfiles/`:

1. Re-run package discovery:

   ```bash
   ./pkgs/discover-packages.sh
   ```

2. Check if any new packages were discovered:

   ```bash
   diff pkgs/aggregate-packages.txt pkgs/aggregate-packages.txt.old
   ```

3. Install any new packages:

   ```bash
   # Install only new packages
   comm -13 <(sort pkgs/aggregate-packages.txt.old) \
            <(sort pkgs/aggregate-packages.txt) | \
     grep '(installation)' | \
     cut -d' ' -f1 | \
     xargs -I {} sudo mpm --admin --install={}
   ```

## Understanding Dependency Types

### Installed Packages `(installation)`
LaTeX packages that MiKTeX downloaded and installed via `mpm`. These are the packages you need to pre-install for fast compilation.

Example: `tikz`, `booktabs`, `hyperref`

### Generated Fonts `(font-generation)`
Fonts that METAFONT generated on-demand. These don't need explicit installation - MiKTeX generates them automatically.

Example: `cmr10`, `cmmi10`, `cmsy10`

### Loaded Packages `(loaded)`
Packages referenced in the document (via `\usepackage` or `\RequirePackage`). These may already be installed or may need installation.

Example: `amsmath`, `graphicx`, `babel`

## Troubleshooting

### Compilation Failures

If a file fails to compile:

1. Check the log: `cat pkgs/logs/Dirname_filename.log`
2. The script continues even if some files fail
3. Dependencies are still extracted from failed compilations

### Missing Packages

If the aggregate list seems incomplete:

1. Some packages may already be pre-installed
2. Check `pkgs/logs/*.log` for warnings about missing files
3. Re-run after installing missing packages

### Permission Errors

The script needs write access to `pkgs/` and `pkgs/logs/`:

```bash
chmod +x pkgs/discover-packages.sh
chmod -R u+w pkgs/
```

## Files in This Directory

- `discover-packages.sh` - Main package discovery script
- `README.md` - This file
- `*.pkgs` - Individual dependency files (generated)
- `aggregate-packages.txt` - Combined dependency list (generated)
- `logs/` - Compilation logs (generated)

## Related Documentation

- HAFiscal-make: `~/GitHub/llorracc/HAFiscal-make/`
- MiKTeX setup: `~/GitHub/llorracc/HAFiscal-dev/build/reinstall-miktex-essential.sh`
- Docker setup: `~/GitHub/llorracc/HAFiscal-dev/.devcontainer/Dockerfile`
