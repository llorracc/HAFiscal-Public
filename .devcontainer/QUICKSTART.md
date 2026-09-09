# DevContainer Quick Start Guide

## Simple Usage (After Container Starts)

Just run the reproduction script directly:

```bash
./reproduce.sh --docs main
```

That's it! No need to:

- ❌ Manually activate virtual environment
- ❌ Set TERM variable
- ❌ Run different commands for different platforms

## Common Commands

### Reproduce Documents

```bash
./reproduce.sh --docs main       # Main paper + slides
./reproduce.sh --docs all        # All documents including appendix
```

### Run Computational Results

```bash
./reproduce.sh --comp min        # Minimal/quick computation
./reproduce.sh --comp            # Full computation
```

### Combined (Everything)

```bash
./reproduce.sh --all             # All computation + all documents
```

### Environment Testing

```bash
./reproduce.sh --envt comp_uv    # Test Python environment
./reproduce.sh --envt texlive    # Test LaTeX environment
```

## What Happens Automatically

1. **TERM variable** - Set to `xterm-256color` for proper terminal output
2. **Virtual environment** - Automatically activated from `.venv/`
3. **LaTeX environment** - Configured with minimal TeX Live + local packages
4. **Python packages** - All dependencies from `pyproject.toml` installed via UV

## First-Time Setup

The devcontainer automatically runs setup on first launch. If you need to re-run:

```bash
# Re-setup Python environment
./reproduce/reproduce_environment_comp_uv.sh

# Re-setup LaTeX (if needed)
@resources/environment/setup-latex-minimal.sh
```

## Jupyter Lab (Optional)

Start Jupyter Lab for interactive notebooks:

```bash
jupyter lab --ip=0.0.0.0 --port=8888
```

Access at: <http://localhost:8888>

## Troubleshooting

### Environment Issues

```bash
# Force re-verification of LaTeX
rm reproduce/reproduce_environment_texlive_*.verified
./reproduce.sh --envt texlive

# Rebuild Python environment
rm -rf .venv
uv sync --all-groups
```

### LaTeX Compatibility Error
If you get errors like "LaTeX kernel too old" or "Undefined control sequence \IfFormatAtLeastT":

```bash
# Run the compatibility fix script
reproduce/docker/fix-latex-compatibility.sh
```

This moves packages incompatible with LaTeX 2021 out of the way. See `.devcontainer/LATEX-COMPATIBILITY-FIX.md` for details.

### PDF Not Generated
Check the log files for LaTeX errors:

```bash
cat HAFiscal.log
cat HAFiscal-Slides.log
```

### Docker/Container Issues
Rebuild the container:

1. Press `Cmd/Ctrl + Shift + P`
2. Select: "Dev Containers: Rebuild Container"

## File Locations

- **Main paper:** `HAFiscal.tex` → `HAFiscal.pdf`
- **Slides:** `HAFiscal-Slides.tex` → `HAFiscal-Slides.pdf`
- **Code:** `Code/HA-Models/do_all.py`
- **Python env:** `.venv/`
- **LaTeX packages:** `@local/texlive/texmf-local/`
- **Benchmarks:** `reproduce/benchmarks/results/`

## Platform Compatibility

This same command works on:

- ✅ MacOS (Docker Desktop)
- ✅ Linux (native Docker)
- ✅ Windows WSL2
- ✅ CI/CD pipelines
- ✅ Cursor automation

See `DEVCONTAINER-SETUP.md` for technical details.
