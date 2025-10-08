# Utopia Font Fix - Minimal Working Examples

This directory contains minimal working examples (MWEs) that demonstrate the Utopia font problem and its solution.

## Files

### `font-fix-problem.tex`
**Demonstrates the problem**: This file will FAIL to compile with `pdflatex` because it uses `\subsection` commands, which the `econsocart` class tries to render in small caps + italic (a font variant that doesn't exist in Utopia).

**To reproduce the error**:
```bash
cd /Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-Latest/qe/font-fix/
pdflatex font-fix-problem.tex
```

**Expected output**:
```
LaTeX Error: Font T1/put/m/scit/12 not found.
l.XX \subsection{This Subsection Will Cause an Error}
```

### `font-fix-solution.tex`
**Demonstrates the solution**: This file compiles successfully by replacing `\subsection` commands with custom formatting that uses bold text instead of small caps + italic.

**To verify the solution works**:
```bash
cd /Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-Latest/qe/font-fix/
pdflatex font-fix-solution.tex
```

**Expected output**: PDF successfully created with properly formatted subsections.

## The Problem

The `econsocart` document class (required for Quantitative Economics journal submissions) defines subsections to use:
- Small caps (`\scshape`)
- + Italic (`\itshape`)

Combined, this requests the `scit` font variant.

**Utopia font** (the base font for the QE class) has these variants separately:
- ✓ Normal, Bold, Italic, Small Caps

But does NOT have:
- ✗ Small caps + Italic combined (`scit`)
- ✗ Small caps + Slanted combined (`scsl`)

## The Solution

Replace:
```latex
\subsection{Title}
```

With:
```latex
\noindent{\large\bfseries Title}\par\vspace{0.5em}
```

This uses only bold (`\bfseries`), which exists in Utopia.

## Implementation in HAFiscal

In the actual HAFiscal QE build system (`HAFiscal-make/`), this replacement is done automatically:

1. **Generate** `HAFiscal-QE.tex` with normal `\subsection` commands
2. **Post-process** using `scripts/qe/fix-subsections.py` (Python script)
3. **Compile** the modified file (no font errors!)

The Python script handles complex cases like:
- Nested braces: `\subsection{\href{url}{text}}`
- Multiple levels of nesting
- Special characters and commands

## References

- **Full explanation**: `HAFiscal-make/scripts/qe/qe_README.md`
- **Python implementation**: `HAFiscal-make/scripts/qe/fix-subsections.py`
- **Build integration**: `HAFiscal-make/scripts/qe/build-qe-submission.sh`

## Why These MWEs Exist

These minimal examples serve as:
1. **Documentation** - Clear demonstration of the problem and solution
2. **Testing** - Quick way to verify the issue and fix
3. **Reference** - Template for testing similar font issues
4. **Proof** - Concrete evidence that the problem exists and the solution works

---

**Created**: October 7, 2025  
**Part of**: HAFiscal QE submission build system
