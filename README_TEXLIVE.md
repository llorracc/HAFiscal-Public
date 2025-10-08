# TeX Live Package Management

## Unified Package List

All TeX Live package installations use the **same canonical list** defined in `texlive-packages.txt`.

### Locations Using This List:

1. **Binder**: `binder/apt.txt` (for MyBinder.org environments)
2. **GitHub Actions**: `.github/workflows/push-build-docs.yml` 
3. **GitHub Actions**: `.github/workflows/test-latex-compilation.yml`

### Current Packages:

```
latexmk
texlive-latex-base
texlive-latex-recommended
texlive-latex-extra
texlive-fonts-recommended
texlive-fonts-extra
texlive-science
texlive-bibtex-extra
biber
ghostscript
```

### To Add a New Package:

1. Add it to `texlive-packages.txt`
2. Copy to `binder/apt.txt` (for Binder)
3. Update CI workflows' apt-get install commands

### Why Not texlive-full?

We use specific collections (~800 MB) instead of `texlive-full` (2-3 GB) for:
- Faster CI builds
- Faster Binder environment startup
- Same functionality for our needs

### Vendored Packages

Some packages are vendored directly in the repo root:
- `accents.sty` - Vendored because Ubuntu TeX Live 2023 can't install via tlmgr
