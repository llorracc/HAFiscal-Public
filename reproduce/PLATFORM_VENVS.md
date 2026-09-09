# Platform and Architecture-Specific Virtual Environments

## Overview

This project uses **platform and architecture-specific virtual environments** to enable seamless cross-platform development across different operating systems and CPU architectures without rebuilding venvs each time.

## How It Works

- **Intel/AMD Linux**: Uses `.venv-linux-x86_64/` directory
- **ARM Linux**: Uses `.venv-linux-aarch64/` directory
- **Intel Mac**: Uses `.venv-darwin-x86_64/` directory
- **Apple Silicon Mac**: Uses `.venv-darwin-arm64/` directory
- **Legacy support**: Falls back to `.venv-linux/`, `.venv-darwin/`, or `.venv/` during migration

Each platform+architecture combination maintains its own venv with correctly compiled Python binaries and binary packages (numpy, pandas, HARK), preventing architecture mismatches.

## Quick Start

### First-Time Setup

**On any platform**:

```bash
./reproduce/reproduce_environment_comp_uv.sh
```

This automatically:
- Detects your platform (Darwin/Linux) and architecture (x86_64/aarch64/arm64)
- Creates the appropriate venv (e.g., `.venv-linux-x86_64/` or `.venv-darwin-arm64/`)
- Migrates any existing platform-only venv (e.g., `.venv-linux/` → `.venv-linux-x86_64/`)
- Removes old `.venv` symlinks (no longer needed)

### Automatic Migration

If you have an existing platform-only venv (`.venv-linux/` or `.venv-darwin/`), the setup script automatically:

1. Detects the architecture of your existing venv
2. Renames it to include architecture (e.g., `.venv-linux/` → `.venv-linux-x86_64/`)
3. Logs the migration with a clear message
4. Continues with normal setup

**No manual intervention required!**

### Using the Environments

The `reproduce.sh` script automatically detects and uses the correct architecture-specific venv:

```bash
./reproduce.sh --envt        # Test environment (auto-detects platform+arch)
./reproduce.sh --docs        # Compile documents
./reproduce.sh --comp min    # Run computations
```

### Shell Auto-Activation

Virtual environments are automatically activated when you open a new shell. The activation logic:

1. Detects your platform (Darwin/Linux) using `uname -s`
2. Detects your architecture (x86_64/aarch64/arm64) using `uname -m`
3. Looks for `.venv-{platform}-{arch}/bin/activate`
4. Activates if found

This happens transparently in `.bashrc`, `.zshrc`, and `.profile`.

## Technical Details

### Architecture Naming

We use **native architecture names** as reported by `uname -m`:

- **Linux ARM**: `aarch64` (not normalized to arm64)
- **macOS ARM**: `arm64` (not normalized to aarch64)
- **Intel/AMD (both)**: `x86_64`

This keeps the naming consistent with system tools and avoids confusion.

### No Symlinks

Previous versions used `.venv -> .venv-{platform}` symlinks. **These are no longer used** because:

- Architecture is now encoded in the directory name
- No ambiguity about which venv to use
- Multiple architectures can coexist in the same workspace
- Simpler, more explicit

The migration script automatically cleans up old symlinks.

### Platform and Architecture Detection

The scripts detect platform and architecture using:

```bash
PLATFORM=$(uname -s)  # Darwin or Linux
ARCH=$(uname -m)      # x86_64, aarch64, or arm64
```

Then build paths like:

- `.venv-linux-x86_64`
- `.venv-darwin-arm64`

### Git Ignore

All architecture-specific venvs are gitignored:

```gitignore
# Current naming scheme
.venv-linux-x86_64/
.venv-linux-aarch64/
.venv-darwin-x86_64/
.venv-darwin-arm64/

# Legacy (migration period)
.venv-darwin/
.venv-linux/
.venv/
```

## Benefits

✅ **No rebuilds**: Switch between platforms/architectures without recreating venvs
✅ **Architecture safety**: Venv name encodes architecture, preventing mismatches
✅ **Multiple architectures**: Multiple venvs can coexist (e.g., Intel and ARM on same Mac)
✅ **Automatic migration**: Old platform-only venvs automatically upgraded
✅ **Clearer naming**: Immediately see which architecture a venv is for
✅ **Auto-activation**: New shells automatically activate the correct venv

## Troubleshooting

### "Virtual Environment Not Found" Error

This usually means you haven't created the venv yet, or are on a different architecture:

```bash
./reproduce/reproduce_environment_comp_uv.sh  # Create/recreate venv
```

### Architecture Mismatch

If you switch between Intel and ARM on the same machine (e.g., Rosetta 2):

```bash
# Both venvs can coexist!
./reproduce/reproduce_environment_comp_uv.sh  # Creates venv for current arch

# Manually activate specific architecture:
source .venv-darwin-x86_64/bin/activate   # Intel
source .venv-darwin-arm64/bin/activate    # ARM
```

### Old Symlink Still Present

If you see a `.venv` symlink or directory after migration:

```bash
rm -rf .venv  # Safe to remove - no longer used
```

### Manual Activation

To manually activate an architecture-specific venv:

```bash
# Intel/AMD Linux
source .venv-linux-x86_64/bin/activate

# ARM Linux
source .venv-linux-aarch64/bin/activate

# Intel Mac
source .venv-darwin-x86_64/bin/activate

# Apple Silicon Mac
source .venv-darwin-arm64/bin/activate
```

### VS Code Python Interpreter

VS Code should auto-detect architecture-specific venvs. If not:

1. Command Palette: `Python: Select Interpreter`
2. Choose the venv matching your architecture (e.g., `.venv-darwin-arm64`)

## Migration from Platform-Only Venvs

If you have an existing `.venv-linux/` or `.venv-darwin/`:

**Option 1: Automatic (Recommended)**

Just run the setup script - it handles migration automatically:

```bash
./reproduce/reproduce_environment_comp_uv.sh
```

**Option 2: Manual**

```bash
# Detect architecture of existing venv
VENV_ARCH=$(.venv-linux/bin/python -c "import platform; print(platform.machine())")

# Rename to include architecture
mv .venv-linux .venv-linux-$VENV_ARCH

# Clean up old symlink
rm -f .venv
```

## Files Modified

This architecture-specific venv implementation touched:

- `reproduce/reproduce_environment_comp_uv.sh` - Core venv creation with migration
- `reproduce/docker/setup.sh` - Shell RC auto-activation
- `Dockerfile` - Container entrypoint
- `reproduce.sh` - Platform+arch detection
- `reproduce/reproduce_data_moments.sh` - Venv path detection
- `.gitignore` - Architecture-specific patterns
- `.vscode/settings.json` - Removed hardcoded path
- `.github/workflows/test-uv-setup.yml` - CI venv detection

## Related Documentation

- Main README: Project overview and installation
- `reproduce/reproduce_environment_comp_uv.sh`: Source of truth for venv creation
- `reproduce/docker/setup.sh`: Source of truth for shell auto-activation
- `README/TROUBLESHOOTING.md`: General troubleshooting guide
