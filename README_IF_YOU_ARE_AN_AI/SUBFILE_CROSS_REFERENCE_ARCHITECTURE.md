# Subfile Cross-Reference Architecture

## Overview

The HAFiscal LaTeX project uses a **dual-mode compilation system** that allows each subfile (in `Subfiles/`, `Figures/`, `Tables/`) to be compiled either:

1. **Standalone**: Independently for development/debugging
2. **Integrated**: As part of the main `HAFiscal.tex` document

This system requires sophisticated cross-reference handling to preserve references between different subfiles, appendices, and the main text.

## ⚠️ CRITICAL: Do NOT "Fix" the `\whenintegrated{}` Wrappers

Labels wrapped in `\whenintegrated{}` like:

```latex
\whenintegrated{\label{sec:calib}}
```

Are **intentional and essential** to the architecture. **DO NOT remove these wrappers** or "simplify" them to bare `\label{}` commands. This would **BREAK** the entire cross-reference system.

## The `\whenintegrated{}` / `\whenstandalone{}` System

### Purpose

These macros enable conditional execution based on compilation mode:

| Macro | Executes When | Use Case |
|-------|---------------|----------|
| `\whenintegrated{content}` | Compiling main document | Define labels that go into main `.aux` |
| `\whenstandalone{content}` | Compiling subfile alone | Load cross-references from main `.aux` |

### How It Works

The system uses an `\entrypoint` flag defined in `@local/local.sty`:

```latex
% From @local/local.sty (lines 391-397):
\makeatletter
\@ifclassloaded{subfiles}{%
  % Subfiles class is loaded - we're loading preamble for a subfile, don't define entrypoint
}{%
  % Normal class - we're compiling the main document, define entrypoint
  \newcommand{\entrypoint}{true}%
}
\makeatother
```

The `\whenintegrated{}` and `\whenstandalone{}` macros check this flag:

```latex
% From @local/local.sty (lines 320-341):
\newcommand{\whenintegrated}[1]{%
  \@ifundefined{entrypoint}{%
    % \entrypoint undefined - this file is standalone, don't execute
  }{%
    % \entrypoint defined - this file is integrated, execute content
    #1%
  }%
}

\newcommand{\whenstandalone}[1]{%
  \@ifundefined{entrypoint}{%
    % \entrypoint undefined - this file is standalone, execute content
    #1%
  }{%
    % \entrypoint defined - this file is integrated, don't execute
  }%
}
```

## Cross-Reference Flow

### When Compiling Main Document (`latexmk HAFiscal.tex`)

```
HAFiscal.tex
    ├── \subfile{Subfiles/Model}
    │       ├── \ref{sec:calib}  ← Uses label from same compilation
    │       └── (no \whenstandalone content executed)
    │
    └── \subfile{Subfiles/Parameterization}
            └── \whenintegrated{\label{sec:calib}}  ← Label IS defined
                                                       Written to HAFiscal.aux
```

**Result**: All labels defined, all references resolved. HAFiscal.aux contains all labels.

### When Compiling Subfile Standalone (`cd Subfiles && latexmk Model.tex`)

```
Model.tex (standalone)
    ├── \input{./relpath-to-latexroot.ltx}
    ├── \documentclass[\latexroot/\projectname]{subfiles}
    ├── \input{\latexroot/@resources/subfile-setup.ltx}
    │       └── \whenstandalone{
    │             \externaldocument{\latexroot/\projectname}  ← Load HAFiscal.aux
    │           }
    │
    └── \ref{sec:calib}  ← Found in imported HAFiscal.aux
```

**Prerequisites**: HAFiscal.tex must have been compiled previously to generate HAFiscal.aux.

## Why Labels Are Wrapped in `\whenintegrated{}`

### The Problem

Without the wrapper, labels would be defined TWICE when compiling the main document:

1. Once when the subfile is processed as part of the main document
2. Once when `\externaldocument` imports the `.aux` file

This causes LaTeX errors: "Label 'sec:calib' multiply defined"

### The Solution

- **Integrated mode**: `\whenintegrated{\label{sec:calib}}` → Label IS defined
- **Standalone mode**: `\whenintegrated{\label{sec:calib}}` → Label is NOT defined locally
  - Instead, `\externaldocument` imports labels from HAFiscal.aux

This ensures each label is defined exactly once, regardless of compilation mode.

## Expected Warnings and Errors

### "Reference 'sec:calib' undefined" During Main Document Compilation

**This can occur on the FIRST compilation pass** because:

1. LaTeX processes files in order
2. `Model.tex` (line 3 in Subfiles.ltx) references `sec:calib`
3. `Parameterization.tex` (line 4 in Subfiles.ltx) defines `sec:calib`
4. The reference is encountered BEFORE the label is defined

**Solution**: Run `latexmk` which automatically performs multiple passes, or manually run `pdflatex` 2-3 times.

### "Reference 'sec:calib' undefined" During Standalone Compilation

**This is expected if**:

1. `HAFiscal.aux` doesn't exist (main document never compiled)
2. `HAFiscal.aux` doesn't contain the label (label definition changed)

**Solution**: Compile the main document first:

```bash
cd /path/to/HAFiscal-Latest
latexmk HAFiscal.tex
```

Then compile the standalone subfile:

```bash
cd Subfiles
latexmk Model.tex
```

### Warning After First Pass is NORMAL

From `EXPECTED_WARNINGS.md`:

> **Undefined References on First Pass**
>
> **Warning**: `LaTeX Warning: There were undefined references.`
>
> **Expected during**: First compilation pass
>
> **Resolution**: The build system runs multiple passes automatically. These warnings should resolve after full compilation.

## Compilation Order Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPILATION ORDER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Compile main document:                                       │
│     latexmk HAFiscal.tex                                        │
│     └── Generates HAFiscal.aux with ALL labels                  │
│                                                                  │
│  2. Now standalone subfiles can access cross-references:         │
│     cd Subfiles && latexmk Model.tex                            │
│     └── Imports labels from ../HAFiscal.aux                     │
│                                                                  │
│  ⚠️  If you skip step 1, standalone compilation will show       │
│     "undefined reference" warnings (this is expected!)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## File Reference

### Core Files

| File | Purpose |
|------|---------|
| `@local/local.sty` | Defines `\whenintegrated{}`, `\whenstandalone{}`, `\entrypoint` |
| `@resources/subfile-setup.ltx` | Standard post-documentclass setup, calls `\externaldocument` |
| `Subfiles/relpath-to-latexroot.ltx` | Defines `\latexroot`, loads paths |

### Label Pattern in Subfiles

```latex
% In Subfiles/Parameterization.tex:
\subsubsection{Calibrated parameters --- Normal times}
\whenintegrated{\label{sec:calib}}   % ← Label wrapped in \whenintegrated
```

### Reference Pattern in Subfiles

```latex
% In Subfiles/Model.tex:
In our baseline calibration, discussed in detail in section~\ref{sec:calib}, ...
```

## Common Mistakes to Avoid

### ❌ DON'T: Remove `\whenintegrated{}` wrappers

```latex
% WRONG - will cause "Label multiply defined" errors
\label{sec:calib}
```

### ✅ DO: Keep labels wrapped

```latex
% CORRECT - enables dual-mode compilation
\whenintegrated{\label{sec:calib}}
```

### ❌ DON'T: Panic about first-pass warnings

The warning "Reference 'sec:calib' undefined" on first pass is **normal**.

### ✅ DO: Run multiple passes or use `latexmk`

```bash
latexmk HAFiscal.tex   # Automatically runs multiple passes
```

### ❌ DON'T: Compile standalone before main document

```bash
# WRONG ORDER - will have undefined references
cd Subfiles && latexmk Model.tex
```

### ✅ DO: Compile main document first

```bash
# CORRECT ORDER
latexmk HAFiscal.tex
cd Subfiles && latexmk Model.tex
```

## Debugging Cross-Reference Issues

### Check if HAFiscal.aux exists

```bash
ls -la HAFiscal.aux
```

### Check if label is in HAFiscal.aux

```bash
grep "sec:calib" HAFiscal.aux
```

**Expected output** (if label is defined):

```
\newlabel{sec:calib}{{3.1.1}{5}{Calibrated parameters --- Normal times}{subsection.3.1.1}{}}
```

### Add debug output to trace `\entrypoint`

```latex
% Temporarily add to subfile preamble:
\makeatletter
\@ifundefined{entrypoint}{%
  \typeout{DEBUG: entrypoint is UNDEFINED - standalone mode}%
}{%
  \typeout{DEBUG: entrypoint is DEFINED - integrated mode}%
}
\makeatother
```

## Related Documentation

- [`FIGURE_TABLE_SUBFILE_COMPILATION.md`](FIGURE_TABLE_SUBFILE_COMPILATION.md) - Compilation patterns and cd requirements
- [`EXPECTED_WARNINGS.md`](EXPECTED_WARNINGS.md) - Which warnings are normal vs. problematic
- [`history/SMARTBIB-DEBUGGING-GUIDE.md`](history/SMARTBIB-DEBUGGING-GUIDE.md) - Bibliography-specific cross-reference issues

---

**Summary**: The `\whenintegrated{}` wrapper on labels is **essential architecture**, not a bug. Undefined reference warnings on first pass are **expected behavior**. Always compile the main document first before standalone subfiles.

