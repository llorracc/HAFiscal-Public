# System Dependencies for HAFiscal

## TL;DR

**System tools (LaTeX, Docker, Git) cannot be installed via `uv` or `pyproject.toml`**

Quick check:
```bash
./check-system-deps.sh           # Check what's installed
./check-system-deps.sh --install # Auto-install missing deps
```

---

## Why System Dependencies Are Separate

| Type | Package Manager | Example Tools |
|------|----------------|---------------|
| **Python packages** | `uv` / `pip` via `pyproject.toml` | numpy, pandas, econ-ark |
| **System binaries** | `apt` / `brew` via install scripts | LaTeX, Docker, Git |

**Why the separation?**
- Python package managers (`uv`, `pip`, `poetry`) only install Python packages
- System binaries are compiled C/C++ programs that need OS-level installation
- This is true for ALL Python projects - not specific to HAFiscal

---

## How to "Require" Docker as a Dependency

Since Docker can't go in `pyproject.toml`, here are the standard approaches:

### 1. ✅ Document in pyproject.toml (Comments)

**What I did:** Added a comment section in `pyproject.toml`:

```toml
# ============================================================================
# SYSTEM DEPENDENCIES (NOT MANAGED BY UV)
# ============================================================================
# REQUIRED:
#   - LaTeX (pdflatex, bibtex, latexmk)
#     Install: ./setup-tex.sh --full
#
# OPTIONAL:
#   - Docker - For DevContainer
#     Install: https://docs.docker.com/get-docker/
# ============================================================================
```

**Pros:** Visible in main config file  
**Cons:** Just documentation, doesn't enforce or install

### 2. ✅ Verification Script (check-system-deps.sh)

**What I created:** Script that checks/installs system deps:

```bash
./check-system-deps.sh           # Check only
./check-system-deps.sh --install # Check + auto-install
```

**Output example:**
```
✅ pdflatex: TeX Live 2022
✅ Docker installed
⚠️  Docker permission denied
   Fix: sudo usermod -aG docker $USER
```

**Pros:** Verifies installation, gives fix instructions  
**Cons:** Users must remember to run it

### 3. ✅ Installation Scripts (setup-tex.sh)

Platform-specific installers:
```bash
./setup-tex.sh --full        # Install LaTeX
```

**Pros:** One command to install  
**Cons:** Requires sudo, platform-specific

### 4. ✅ DevContainer (.devcontainer/)

**Already in your repo!** Automatically installs everything via Docker:

```json
{
  "postCreateCommand": "bash .devcontainer/setup.sh"
}
```

`.devcontainer/setup.sh` installs:
- MiKTeX (LaTeX)
- UV (Python package manager)
- All Python dependencies

**Pros:** Fully reproducible, no manual steps  
**Cons:** Requires Docker already installed on host

### 5. ✅ CI/CD Config (GitHub Actions)

Example `.github/workflows/build.yml`:
```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y texlive-full latexmk
```

**Pros:** Enforced in CI, documents exact versions  
**Cons:** Only for CI, not local development

### 6. ✅ README/INSTALLATION.md

**Already in your repo!** Installation guide:
- Lists system requirements
- Platform-specific instructions
- Troubleshooting

### 7. ❌ What DOESN'T Work

These **DO NOT** work for system dependencies:

```toml
# ❌ WRONG - Docker is not a Python package
[project]
dependencies = [
    "docker",  # This installs docker-py (Python library), not Docker Engine
]
```

```bash
# ❌ WRONG - Can't install in .venv
uv add docker-engine  # No such package on PyPI
```

---

## Recommended Approach (What You Have Now)

**Multi-layered approach** (best practice):

1. **Document in pyproject.toml** ✅ (comments section)
2. **Automated checker** ✅ (`check-system-deps.sh`)
3. **Installation scripts** ✅ (`setup-tex.sh`)
4. **DevContainer** ✅ (`.devcontainer/`)
5. **README** ✅ (`README/INSTALLATION.md`)

This covers:
- 📖 **Discovery**: Users see requirements in `pyproject.toml`
- ✅ **Verification**: `check-system-deps.sh` validates installation
- 🔧 **Installation**: `setup-tex.sh` installs if missing
- 🐳 **Reproducibility**: DevContainer ensures it works
- 📚 **Documentation**: README for manual setup

---

## Comparison to Other Ecosystems

### R Projects
```r
# R can install LaTeX from within R
tinytex::install_tinytex()
```
**Why R can do this:** TinyTeX is a minimal TeX distribution built specifically for R

**Why Python can't:** No equivalent project. Python ecosystem prefers:
- System package managers (apt/brew) for system tools
- Docker/containers for reproducibility

### Node.js Projects
Similar problem - native dependencies can't go in `package.json`:
```json
{
  "engines": {
    "node": ">=14.0.0"
  },
  "os": ["linux", "darwin"],
  "cpu": ["x64"]
}
```

They use:
- Docker (common in Node ecosystem)
- System checks in `scripts/` directory
- README documentation

### Conda Projects
Conda **can** install Docker/LaTeX because it's a **system package manager**, not just Python:
```yaml
dependencies:
  - python=3.9
  - texlive-core  # System package
```

**Why not use Conda for HAFiscal?**
- `uv` is faster for Python deps
- LaTeX is huge (~4 GB), bloats conda envs
- System package managers (apt/brew) better for system tools

---

## Quick Start Guide

### New User Setup

```bash
# 1. Clone repo
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}

# 2. Check system dependencies
./check-system-deps.sh

# 3. Install missing deps (if any)
./setup-tex.sh --full              # LaTeX
sudo usermod -aG docker $USER      # Docker permissions (if needed)

# 4. Install Python dependencies
uv sync --all-groups

# 5. Build
./reproduce.sh --docs main
```

### DevContainer (Easiest)

```bash
# 1. Install Docker on host machine
# 2. Open folder in VS Code
# 3. Click "Reopen in Container"
# Done! Everything auto-installs
```

---

## FAQ

### Q: Can I use pip/conda/poetry instead of uv?
**A:** Yes! But you still need system dependencies separately. The separation exists in ALL Python tools.

### Q: Why not bundle LaTeX in a Python wheel?
**A:** LaTeX is ~4 GB of C/C++ binaries. Python wheels are for Python code or small C extensions with Python API.

### Q: Can GitHub Actions install these automatically?
**A:** Yes! See `.github/workflows/` for CI setup. But local development still needs manual install.

### Q: What if I don't want to install LaTeX?
**A:** Use DevContainer (Docker-based) or Binder (cloud-based). Both include LaTeX pre-installed.

---

## See Also

- `pyproject.toml` - Python dependencies + system dep documentation
- `check-system-deps.sh` - Verify/install system dependencies
- `setup-tex.sh` - Install LaTeX
- `.devcontainer/` - Docker-based complete environment
- `README/INSTALLATION.md` - Detailed installation guide
- `README-UV-SETUP.md` - UV-specific setup guide

