# Figure, Table, and Subfile Compilation Guide

## Overview

Figures, tables, and subfiles in the HAFiscal project are designed to work in **two modes**:

1. **Integrated**: Compiled as part of the main `HAFiscal.tex` document
2. **Standalone**: Compiled individually for debugging and development

This document explains how standalone compilation works and key patterns to follow.

## Quick Reference

### Compiling Figures, Tables, and Subfiles

```bash
# From project root:
./reproduce.sh --docs figures      # Compile all figures
./reproduce.sh --docs tables       # Compile all tables
./reproduce.sh --docs subfiles     # Compile all subfiles
./reproduce.sh --docs all          # Compile everything

# With debugging:
./reproduce.sh --docs figures --stop-on-error   # Stop at first failure

# Individual file (from project root):
cd Figures && latexmk LorenzPts.tex
cd Tables && latexmk calibration.tex
cd Subfiles && latexmk Intro.tex
```

**Important:** Always `cd` into the subdirectory before compiling individual files. The relative paths in `.latexmkrc` and subfile structure require this.

## How It Works

### 1. Directory Structure and Symlinks

```
{{REPO_NAME}}/
├── .latexmkrc                    # Configures latexmk (PDF mode, BibTeX wrapper)
├── HAFiscal.bib                  # Main bibliography
├── @resources/                   # Shared LaTeX resources
│   └── tex-paths.ltx             # Consolidated path configuration (superseded tex-add-search-paths.tex)
├── Figures/
│   ├── .latexmkrc → ../.latexmkrc      # Symlink to parent
│   ├── HAFiscal.bib → ../HAFiscal.bib  # Symlink to bibliography
│   └── LorenzPts.tex                    # Figure file
├── Tables/
│   ├── .latexmkrc → ../.latexmkrc
│   ├── HAFiscal.bib → ../HAFiscal.bib
│   └── calibration.tex
└── Subfiles/
    ├── .latexmkrc → ../.latexmkrc
    └── Intro.tex
```

**Key Points:**

- `.latexmkrc` symlinks ensure consistent latexmk configuration
- `HAFiscal.bib` symlinks allow BibTeX to find bibliography
- All configuration is centralized in the root `.latexmkrc`

### 2. Relative Path Pattern

**Always use relative paths from the subdirectory:**

```latex
% Modern pattern (Oct 2025+):
% In Subfiles/Intro.tex:
\input{./._relpath-to-latexroot.ltx}  % ✅ Loads tex-paths.ltx + metadata automatically
```

```latex
% For images:
\includegraphics{\latexroot/images/myimage}  % ✅ Uses macro
\includegraphics{../images/myimage}          % ✅ Relative path
```

**Common Pattern in Subfiles (Current):**

```latex
\input{./._relpath-to-latexroot.ltx}  % Loads everything needed
\documentclass[\latexroot/\projectname]{subfiles}
\whenstandalone{\externaldocument{\latexroot/\projectname}}
```

### 3. PDF Mode Configuration

The `.latexmkrc` sets PDF mode globally:

```perl
$pdf_mode = 1;  # Use pdflatex (not latex/DVI)
```

**Why This Matters:**

- **PDF mode (pdflatex)**: Can include PDF/PNG/JPG images ✅
- **DVI mode (latex)**: Cannot include modern image formats ❌

This ensures all figures with computational images compile correctly.

### 4. The `cd` Pattern

The reproduction scripts use this pattern:

```bash
# From reproduce/reproduce_documents.sh:
if [[ "$needs_cd" == "true" ]]; then
    (cd "$doc_dir" && latexmk "$doc_file")
else
    latexmk "$doc_path"
fi
```

**Why `cd` is necessary:**

- `.latexmkrc` uses relative path: `./@resources/latexmk/latexmkrc/tools/bibtex_wrapper.sh`
- Symlinks resolve correctly when in the subdirectory
- BibTeX can find `../HAFiscal.bib`

## Debugging Standalone Compilation

### Check Compilation from Subdirectory

```bash
cd /path/to/{{REPO_NAME}}/Figures
latexmk LorenzPts.tex

# Should work! If errors, check:
ls -la .latexmkrc     # Should be symlink to ../.latexmkrc
ls -la HAFiscal.bib   # Should be symlink to ../HAFiscal.bib
```

### Common Issues and Solutions

#### Issue: "File '@resources/tex-paths.ltx' not found"

**Problem:** This shouldn't occur with modern files - `._relpath-to-latexroot.ltx` loads it automatically

**Solution:**

```latex
% Modern pattern (use this):
\input{./._relpath-to-latexroot.ltx}  % Loads tex-paths.ltx + metadata automatically

% Old pattern (deprecated, but if you see it):
\input{../@resources/tex-paths.ltx}  % Direct load with relative path
```

#### Issue: "Undefined control sequence \projectroot"

**Problem:** Using non-existent macro

**Solution:**

```latex
% Change from:
\whenstandalone{\externaldocument{\projectroot/\projectname}}
% To:
\whenstandalone{\externaldocument{\latexroot/\projectname}}
```

#### Issue: "LaTeX Error: File '../images/myimage' not found" (DVI mode)

**Problem:** Compiling in DVI mode which can't include PDF/PNG/JPG

**Solution:** Ensure `.latexmkrc` has:

```perl
$pdf_mode = 1;
```

Or compile with explicit flag:

```bash
latexmk -pdf myfile.tex
```

#### Issue: "Could not open bibtex log file"

**Problem:** BibTeX wrapper script not found

**Solution:** Ensure you're compiling from within the subdirectory:

```bash
cd Figures    # Important!
latexmk myfile.tex
```

### Stop-on-Error Debugging

When developing or debugging, use `--stop-on-error`:

```bash
./reproduce.sh --docs figures --stop-on-error
```

This will:

- Stop immediately at the first compilation failure
- Show exactly which file failed
- Display progress (e.g., "Compiled 5/12 documents")
- Skip remaining files to save time

**Example output:**

```
========================================
📄 Document 6/12: problematic_file.tex
========================================
ℹ️  Compiling: Figures/problematic_file.tex
❌ problematic_file compilation failed
========================================
❌ Stopping due to compilation failure (STOP_ON_ERROR=true)
❌ Failed on: Figures/problematic_file.tex
ℹ️  Compiled successfully: 5/12 documents
========================================
```

## Expected Warnings

### Standalone Subfiles

Subfiles compiled standalone **may show warnings** about:

- Missing `../HAFiscal.aux` (cross-references from main document)
- Undefined references (references to sections in main document)
- Missing citations (citations only in main bibliography)

**These are expected** and don't prevent PDF generation. The subfiles compile successfully and can be viewed standalone.

When integrated into the main document, all cross-references and citations resolve correctly.

### Reference Resolution

```
Latexmk: Missing input file '../HAFiscal.aux' (or dependence on it)
LaTeX Warning: Reference `sec:intro' on page 1 undefined
```

**Status:** ✅ Expected for standalone compilation  
**Impact:** PDF still generates, references show as "??" in standalone mode  
**Resolution:** Works correctly when compiled as part of main document

## Best Practices

### 1. Always Use Relative Paths

```latex
✅ \input{./._relpath-to-latexroot.ltx}  % Loads paths automatically
✅ \includegraphics{\latexroot/images/myimage}
✅ \whenstandalone{\externaldocument{\latexroot/\projectname}}

❌ \input{@resources/tex-paths.ltx}  % Missing ../
❌ \input{/absolute/path/to/resources}
❌ \whenstandalone{\externaldocument{\projectroot/\projectname}}
```

### 2. Test Both Modes

When creating new figures/tables/subfiles:

```bash
# Test standalone:
cd Figures && latexmk mynewfigure.tex

# Test integrated:
./reproduce.sh --docs main
```

### 3. Use Standard Patterns

Follow existing file patterns for new files:

```latex
% Standard figure/table pattern:
\input{./._relpath-to-latexroot.ltx}
\documentclass[\latexroot/\projectname]{subfiles}
\whenstandalone{\externaldocument{\latexroot/\projectname}}

\begin{document}
\begin{figure}
  % Figure content
\end{figure}
\end{document}
```

```latex
% Standard subfile pattern (current):
\input{./._relpath-to-latexroot.ltx}  % Loads tex-paths.ltx + metadata
\documentclass[\latexroot/\projectname]{subfiles}
\whenstandalone{\externaldocument{\latexroot/\projectname}}

\begin{document}
\section{My Section}
% Content
\end{document}
```

### 4. Check Symlinks

Before committing new subdirectory files:

```bash
cd Figures  # or Tables, Subfiles
ls -la .latexmkrc    # Should point to ../.latexmkrc
ls -la HAFiscal.bib  # Should point to ../HAFiscal.bib (for Figures/Tables)
```

## Viewing Benchmark Results

After compilation, view performance data:

```bash
cd reproduce/benchmarks
./benchmark_results.sh           # All benchmarks
./benchmark_results.sh docs      # Document compilations only
./benchmark_results.sh --help    # Show help
```

**Output includes:**

- Date/time of compilation
- Mode (docs, comp, data, envt)
- Scope (main, figures, tables, subfiles, all)
- Hardware platform (e.g., "Apple M4 Max")
- RAM available
- Duration in seconds
- Success/failure status

## Technical Reference

### Files Modified in 2025-10-30 Session

**Configuration:**

- `.latexmkrc` - Added `$pdf_mode = 1`

**Scripts:**

- `reproduce/reproduce_documents.sh` - Added `cd` pattern, progress indicators, `--stop-on-error`
- `reproduce.sh` - Added `--stop-on-error` flag support
- `reproduce/benchmarks/benchmark_results.sh` - Added hardware column, seconds display

**Subfiles Fixed:**

- `Subfiles/Appendix-Robustness.tex` - Fixed `@resources/` path
- `Subfiles/Comparing-policies.tex` - Fixed `@resources/` path and `\projectroot` → `\latexroot`
- `Subfiles/Parameterization.tex` - Fixed `@resources/` path
- `Subfiles/Model.tex` - Fixed `@resources/` path

### Compilation Statistics

**Current Performance (as of 2025-10-30):**

- Figures: 12 files, ~50 seconds
- Tables: 12 files, ~45 seconds
- Subfiles: 13 files, ~68 seconds
- All documents: 39 files, ~190 seconds (3m 10s)

**Platform:** Apple M4 Max, 64GB RAM, macOS 15

## See Also

- `README_IF_YOU_ARE_AN_AI/history/20251030-figure-compilation-fixes.md` - Detailed session history
- `README_IF_YOU_ARE_AN_AI/COMPILATION.md` - LaTeX compilation system architecture
- `reproduce/README.md` - Reproduction scripts overview
- `README/TROUBLESHOOTING.md` - General troubleshooting guide

---

**Last Updated:** 2025-10-30  
**Status:** All 39 documents compile successfully ✅
