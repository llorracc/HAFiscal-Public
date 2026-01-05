# Testing Locally Before GitHub Actions

This guide helps you test your changes locally in an environment similar to GitHub Actions, so you can catch errors **before pushing**.

---

## Quick Start (Recommended)

### Run the Local CI Test Script

This mimics the GitHub Actions environment:

```bash
bash .github/scripts/test-local-like-ci.sh
```

✅ **This runs the exact same command** that GitHub Actions runs: `reproduce/reproduce_documents.sh`  
✅ **Sets the same environment variables** (TEXINPUTS, LATEX_OPTS)  
✅ **Checks for the same errors** GitHub Actions looks for

**Time savings**: ~2-5 minutes locally vs 10-30 minutes waiting for GitHub Actions

---

## What's Different: GitHub Actions vs Your Local Machine

| Aspect | GitHub Actions | Your Mac |
|--------|---------------|----------|
| **OS** | Ubuntu 22.04 LTS | macOS 14 (Sonoma) |
| **TeX Distribution** | TeX Live 2023 (Ubuntu) | TeX Live 2023 (MacTeX) |
| **Shell** | bash (Ubuntu) | bash (your configured shell) |
| **Filesystem** | Case-sensitive | Case-insensitive (usually) |
| **Line endings** | LF (Unix) | LF (Unix) - OK ✅ |
| **Python** | Not used for docs | Your conda env |

### Key Point: LaTeX Differences

The main differences are:
1. **Package paths**: GitHub Actions uses `texlive-full`, you use MacTeX
2. **TEXINPUTS**: GitHub Actions sets this to find `@resources/texlive/`
3. **tlmgr**: GitHub Actions runs `tlmgr install` for missing packages

---

## Three Approaches to Local Testing

### 1. **Quick Test (Recommended)** ⚡

Just run the CI test script:
```bash
./.github/scripts/test-local-like-ci.sh
```

**Pros**: Fast, no setup  
**Cons**: Not 100% identical to Ubuntu (but close enough)

### 2. **Docker Test (Most Accurate)** 🐳

Use Docker to get exact Ubuntu environment:

```bash
# Create Dockerfile
cat > .github/docker/Dockerfile.ci-test << 'DOCKER'
FROM ubuntu:22.04

# Install TeX Live
RUN apt-get update && \
    apt-get install -y latexmk texlive-full git && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /workspace

# Copy everything
COPY . .

# Set environment
ENV TEXINPUTS="/workspace/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS}"
ENV LATEX_OPTS="-interaction=nonstopmode"

# Default command
CMD ["bash", "reproduce/reproduce_documents.sh"]
DOCKER

# Build and run
docker build -f .github/docker/Dockerfile.ci-test -t hafiscal-ci-test .
docker run --rm -v $(pwd):/workspace hafiscal-ci-test
```

**Pros**: Exact Ubuntu environment  
**Cons**: Slower first build (~10 min), requires Docker

### 3. **Act Tool (Run GitHub Actions Locally)** 🎬

[Act](https://github.com/nektos/act) runs GitHub Actions workflows locally:

```bash
# Install act (if not already installed)
brew install act

# Run the workflow locally
act push -j build-docs
```

**Pros**: Runs actual workflow file  
**Cons**: Requires Docker, can be slow

---

## Debugging Workflow

If GitHub Actions fails but local tests pass:

### 1. Compare LaTeX Packages

**Local:**
```bash
tlmgr list --only-installed > local-packages.txt
```

**GitHub Actions** (from logs):
Check the "Initialize tlmgr" step output

### 2. Check TEXINPUTS

**Local:**
```bash
echo $TEXINPUTS
```

Should include: `./@resources/texlive/texmf-local/tex/latex//`

**Fix if needed:**
```bash
export TEXINPUTS="${PWD}/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS:-}"
```

### 3. Check for Missing Files

GitHub Actions shows files it can't find:
```bash
! LaTeX Error: File 'somepackage.sty' not found.
```

**Solution**: Install missing package locally:
```bash
tlmgr install somepackage
```

### 4. Review GitHub Actions Logs

1. Go to: https://github.com/llorracc/HAFiscal-Latest/actions
2. Click failed workflow run
3. Click "build-docs" job
4. Expand failing step
5. Compare error with local run

---

## Quick Checklist Before Pushing

```bash
# 1. Run local CI test
./.github/scripts/test-local-like-ci.sh

# 2. Check PDFs were generated
ls -lh HAFiscal.pdf HAFiscal-Slides.pdf

# 3. Check for critical errors in logs
grep -i "! LaTeX Error" *.log

# 4. If all clear, push!
git push
```

---

## Understanding the GitHub Actions Workflow

Your workflow does this (in order):

```yaml
1. Checkout code
2. Install TeX Live + latexmk (texlive-full)
3. Initialize tlmgr & install packages (latex-bin, lm, ec, cm-super, accents)
4. Set TEXINPUTS="$WORKSPACE/@resources/texlive/texmf-local/tex/latex//:..."
5. Run: bash reproduce/reproduce_documents.sh
6. Upload PDFs as artifacts
7. Deploy docs/ to GitHub Pages (if docs/ changed)
```

**Your local script replicates steps 4-5** (the critical build steps).

---

## Advanced: Running Individual Steps

If you want to test specific parts:

### Just compile main document:
```bash
export TEXINPUTS="${PWD}/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS:-}"
pdflatex -interaction=nonstopmode HAFiscal.tex
bibtex HAFiscal
pdflatex -interaction=nonstopmode HAFiscal.tex
pdflatex -interaction=nonstopmode HAFiscal.tex
```

### Just run latexmk:
```bash
latexmk -pdf -interaction=nonstopmode HAFiscal.tex
```

### Test with verbose errors:
```bash
pdflatex -interaction=errorstopmode HAFiscal.tex
```

---

## Common Issues

### "Package X not found"

**On Mac:**
```bash
sudo tlmgr install package-name
```

**In GitHub Actions**: Add to workflow under "Initialize tlmgr":
```yaml
sudo tlmgr install package-name
```

### "TEXINPUTS not set"

Run before testing:
```bash
export TEXINPUTS="${PWD}/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS:-}"
```

### "shell-escape needed"

GitHub Actions doesn't allow shell-escape for security.  
If you need it, you'll need to modify the workflow.

---

## Time Comparison

| Method | Setup Time | Test Time | Total | Accuracy |
|--------|------------|-----------|-------|----------|
| **Local script** | 0 min | 2-5 min | **2-5 min** | 95% |
| **Docker** | 10 min (first) | 3-5 min | 13-15 min (first) | 99% |
| **Act** | 5 min setup | 5-10 min | 10-15 min | 99% |
| **GitHub Actions** | 0 min | 10-30 min | **10-30 min** | 100% |

**Recommendation**: Start with the local script. If it passes but GitHub Actions fails, use Docker.

---

## Need Help?

1. Check GitHub Actions logs: https://github.com/llorracc/HAFiscal-Latest/actions
2. Compare local vs CI output
3. Check this guide's "Debugging Workflow" section
