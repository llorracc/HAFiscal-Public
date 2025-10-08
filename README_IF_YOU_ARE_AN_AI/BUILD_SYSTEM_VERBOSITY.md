# Build System Verbosity Controls

## Overview

The HAFiscal build system implements **two independent verbosity control systems** that work together to provide flexible output management:

1. **`PDFLATEX_QUIET`** - Controls LaTeX compilation output (package loading, compilation details)
2. **`VERBOSITY_LEVEL`** - Controls build script messages (INFO, progress, status messages)

Understanding and using these controls appropriately can significantly improve your build experience, especially for debugging or when you want cleaner output.

## System 1: PDFLATEX_QUIET (LaTeX Output Filtering)

### Purpose
Controls the verbosity of LaTeX/pdflatex compilation output. This affects what you see from the LaTeX engine itself (package loading messages, compilation details, etc.).

### Environment Variable
```bash
export PDFLATEX_QUIET=quiet    # Suppress verbose LaTeX output (default)
export PDFLATEX_QUIET=verbose  # Show all LaTeX compilation details
```

### Behavior

#### `PDFLATEX_QUIET=quiet` (Default)
- **Suppresses**: Package loading messages, verbose LaTeX internals
- **Shows**: Errors, warnings, latexmk summary messages
- **Implementation**: Sets `$silent = 1` in latexmk configuration
- **Use case**: Normal builds, production use, cleaner output

#### `PDFLATEX_QUIET=verbose`
- **Shows**: All LaTeX output including package loading details
- **Implementation**: Sets `$silent = 0` in latexmk configuration  
- **Use case**: Debugging package loading issues, understanding compilation flow

### Implementation Details

Controlled in: `@resources/latexmk/latexmkrc/latexmkrc_for-projects-with-circular-crossrefs`

```perl
# Lines 52-62 of latexmkrc_for-projects-with-circular-crossrefs
my $pdflatex_quiet = $ENV{'PDFLATEX_QUIET'} || 'quiet';
if ($pdflatex_quiet eq 'verbose') {
    $silent = 0;              # Show all latex output
    $quiet = 0;               # Show latexmk's own messages
} else {
    $silent = 1;              # Suppress verbose latex output
    $quiet = 0;               # Show latexmk's own summary messages
}
```

### Usage Examples

```bash
# Quiet compilation (default) - clean output
latexmk HAFiscal.tex

# Verbose LaTeX output - for debugging
PDFLATEX_QUIET=verbose latexmk HAFiscal.tex

# Using with reproduce script
PDFLATEX_QUIET=verbose ./reproduce.sh --docs
```

## System 2: VERBOSITY_LEVEL (Script Output Control)

### Purpose
Controls the verbosity of build script messages (bash scripts like `makePDF-Portable-Latest.sh`, `makeWeb-Paper.sh`, etc.). This affects script-level INFO messages, progress indicators, and status reports.

### Environment Variable
```bash
export VERBOSITY_LEVEL=quiet    # Suppress INFO messages
export VERBOSITY_LEVEL=normal   # Standard script output (default)
export VERBOSITY_LEVEL=verbose  # Detailed script progress
export VERBOSITY_LEVEL=debug    # Maximum verbosity with debug info
```

### Behavior

#### `VERBOSITY_LEVEL=quiet`
- **Suppresses**: INFO messages from build scripts
- **Shows**: Errors, warnings, final results
- **Use case**: Automated builds, CI/CD pipelines, minimal output

#### `VERBOSITY_LEVEL=normal` (Default)
- **Shows**: Standard script progress messages
- **Includes**: INFO messages, section headers, completion status
- **Use case**: Normal interactive use

#### `VERBOSITY_LEVEL=verbose`
- **Shows**: Detailed script progress, file operations
- **Includes**: All normal output plus detailed steps
- **Use case**: Understanding build process, troubleshooting

#### `VERBOSITY_LEVEL=debug`
- **Shows**: Maximum verbosity including debug information
- **May include**: Variable values, decision points, trace information
- **Use case**: Deep debugging, development

### Script Support

Scripts that honor `VERBOSITY_LEVEL`:
- `makePDF-Portable-Latest.sh` - PDF build wrapper
- `makeWeb-Paper.sh` - Web/HTML generation
- `reproduce.sh` - Main reproduction script
- Various other build utilities in `HAFiscal-make/`

### Usage Examples

```bash
# Quiet script output - minimal messages
VERBOSITY_LEVEL=quiet ./reproduce.sh --docs

# Normal output (default)
./reproduce.sh --docs

# Verbose script output - detailed progress
VERBOSITY_LEVEL=verbose ./reproduce.sh --docs

# Debug mode - maximum information
VERBOSITY_LEVEL=debug ./reproduce.sh --docs
```

## Combined Usage

The two systems work independently and can be combined for precise output control:

```bash
# Quiet everything - minimal output
PDFLATEX_QUIET=quiet VERBOSITY_LEVEL=quiet ./reproduce.sh --docs

# Quiet scripts, verbose LaTeX - for LaTeX debugging
PDFLATEX_QUIET=verbose VERBOSITY_LEVEL=quiet latexmk HAFiscal.tex

# Verbose scripts, quiet LaTeX - for script debugging
PDFLATEX_QUIET=quiet VERBOSITY_LEVEL=verbose ./reproduce.sh --docs

# Maximum verbosity - all output
PDFLATEX_QUIET=verbose VERBOSITY_LEVEL=debug ./reproduce.sh --docs
```

## Additional Debug Mode Control

### DEBUG Environment Variable

Some scripts also support a separate `DEBUG` environment variable:

```bash
export DEBUG=true   # Enable debug mode
export DEBUG=false  # Disable debug mode (default)
```

When `VERBOSITY_LEVEL=verbose` and `DEBUG=true`, scripts may run `set -v` after syntax checking to show detailed execution traces.

## Best Practices

### For Normal Use
```bash
# Use defaults - balanced output
./reproduce.sh --docs
```

### For Debugging LaTeX Issues
```bash
# Show all LaTeX compilation details
PDFLATEX_QUIET=verbose latexmk HAFiscal.tex
```

### For Debugging Build Scripts
```bash
# Show detailed script progress
VERBOSITY_LEVEL=verbose ./reproduce.sh --docs
```

### For Automated/CI Builds
```bash
# Minimize output, capture errors
PDFLATEX_QUIET=quiet VERBOSITY_LEVEL=quiet ./reproduce.sh --docs 2>&1 | tee build.log
```

### For Deep Debugging
```bash
# Maximum verbosity everywhere
PDFLATEX_QUIET=verbose VERBOSITY_LEVEL=debug DEBUG=true ./reproduce.sh --docs
```

## Output Filtering Details

### What Gets Suppressed in Quiet Mode

**`PDFLATEX_QUIET=quiet` suppresses**:
- Package loading messages: `(/usr/local/texlive/.../article.cls)`
- Font loading: `Font \OT1/cmr/m/n/10=cmr10`
- File inclusions: `(./HAFiscal.aux)`
- Verbose LaTeX internals

**`PDFLATEX_QUIET=quiet` preserves**:
- Error messages: `! LaTeX Error:`
- Warning messages: `LaTeX Warning:`
- Important status: Undefined references, overfull boxes
- Latexmk summary and final status

**`VERBOSITY_LEVEL=quiet` suppresses**:
- `[INFO]` messages from scripts
- Progress indicators
- Non-essential status messages

**`VERBOSITY_LEVEL=quiet` preserves**:
- Error messages
- Warning messages  
- Final build results
- Critical status information

## Warning Summary System

Even in quiet mode, latexmk provides a **warning summary** at the end of compilation:

```perl
$logfile_warning_list=1;  # Always provide a summary of warnings
```

This ensures you never miss important warnings even when verbose output is suppressed.

## Post-Compilation Status

The latexmkrc includes a post-compilation hook that checks for undefined references:

```
================= LATEXMK POST-CHECK ==================
STATUS: ✅  SUCCESS: No undefined references detected.
=====================================================
```

Or if references remain unresolved:

```
================= LATEXMK POST-CHECK ==================
STATUS: ⚠️  WARNING: Undefined references remain.
          This is expected if compiling one part of a cycle.
          Run the main compilation script to resolve them.
=====================================================
```

This status message appears regardless of verbosity settings.

## Troubleshooting

### Problem: Too much output, hard to find errors
**Solution**: Use `PDFLATEX_QUIET=quiet VERBOSITY_LEVEL=quiet`

### Problem: Build seems to hang, want to see progress
**Solution**: Use `VERBOSITY_LEVEL=verbose` to see detailed progress

### Problem: Package loading issues or LaTeX errors
**Solution**: Use `PDFLATEX_QUIET=verbose` to see full LaTeX output

### Problem: Script behavior seems wrong
**Solution**: Use `VERBOSITY_LEVEL=debug` to trace script execution

### Problem: Want to save output for later analysis
**Solution**: 
```bash
PDFLATEX_QUIET=verbose VERBOSITY_LEVEL=verbose ./reproduce.sh --docs 2>&1 | tee build.log
```

## Related Documentation

- **Latexmk Configuration**: `.latexmkrc` and `@resources/latexmk/latexmkrc/latexmkrc_for-projects-with-circular-crossrefs`
- **Expected Warnings**: See `@local/local.sty` lines 123-131 for hyperref warning documentation
- **Build System**: See `COMPILATION.md` for overall build system architecture
- **Troubleshooting**: See `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` for common issues

## Technical Implementation Notes

### For Script Developers

If you're creating new build scripts that should respect these conventions:

```bash
# Check VERBOSITY_LEVEL in your scripts
if [ "${VERBOSITY_LEVEL}" != "quiet" ]; then
    echo "[INFO] Starting build process..."
fi

# Pass environment variables to subsidiary scripts
VERBOSITY_LEVEL="${VERBOSITY_LEVEL}" \
PDFLATEX_QUIET="${PDFLATEX_QUIET}" \
    ./subsidiary_script.sh
```

### For Latexmk Configuration

The `PDFLATEX_QUIET` variable is read by the latexmkrc files. To add support in custom configurations:

```perl
my $pdflatex_quiet = $ENV{'PDFLATEX_QUIET'} || 'quiet';
if ($pdflatex_quiet eq 'verbose') {
    $silent = 0;
} else {
    $silent = 1;
}
```

## Summary

| Control | Values | Affects | Default |
|---------|--------|---------|---------|
| `PDFLATEX_QUIET` | `quiet`, `verbose` | LaTeX compilation output | `quiet` |
| `VERBOSITY_LEVEL` | `quiet`, `normal`, `verbose`, `debug` | Build script messages | `normal` |
| `DEBUG` | `true`, `false` | Additional debug features | `false` |

**Key Takeaway**: Use `PDFLATEX_QUIET` for LaTeX output control, `VERBOSITY_LEVEL` for script message control. They work independently and can be combined for precise output management. 