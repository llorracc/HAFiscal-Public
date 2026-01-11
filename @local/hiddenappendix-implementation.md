# Hidden Appendix: Implementation Details

This document describes the changes made to implement the working "External Label Harvesting" approach for the hidden appendix functionality.

## Summary of Changes

| File | Change Type | Purpose |
|------|-------------|---------|
| `@local/hiddenappendix.sty` | Modified | Complete rewrite using comment package |
| `@local/hiddenappendix-labels.tex` | Created | Pre-defined labels for Appendix B |
| `reproduce/docker/setup.sh` | Modified | Add `comment` package to TeX Live |
| `HAFiscal.tex` | Modified | Remove duplicate `\label{eq:model}` |

---

## File: `@local/hiddenappendix.sty`

### Before (Broken)
The previous implementation attempted to process content in an invisible box:

```latex
\RequirePackage{environ}
\NewEnviron{hiddencontent}[1][Online]{%
  \begingroup
    \def\thepage{#1}%
    \setbox0=\vbox{\BODY}%
  \endgroup
}
```

This failed because econsocart's TOC machinery was triggered during content processing.

### After (Working)

```latex
\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{hiddenappendix}[2025/09/20 v2.0 Hidden appendices via label harvesting]

\RequirePackage{comment}   % For truly skipping content

\makeatletter

% CRITICAL FIX: Make econsocart's \ignorenumberline safe globally
\def\ignorenumberline{%
  \@ifundefined{numberline}{}{%
    \let\sv@numberline\numberline
    \let\numberline\@gobble
  }%
}
\def\restorenumberline{%
  \@ifundefined{sv@numberline}{}{%
    \let\numberline\sv@numberline
  }%
}

% Re-apply after document begins (in case econsocart overwrites)
\AtBeginDocument{%
  \def\ignorenumberline{%
    \@ifundefined{numberline}{}{%
      \let\sv@numberline\numberline
      \let\numberline\@gobble
    }%
  }%
}

% Load pre-defined labels
\AtBeginDocument{%
  \InputIfFileExists{@local/hiddenappendix-labels.tex}{%
    \typeout{hiddenappendix: Loaded labels from hiddenappendix-labels.tex}%
  }{%
    \PackageWarning{hiddenappendix}{Labels file not found}%
  }%
}

% HIDDENCONTENT: completely skip body content
\excludecomment{hiddencontent}

\makeatother
\endinput
```

### Key Changes

1. **Replaced `environ` with `comment` package**: The `comment` package's `\excludecomment` truly skips content without tokenizing it.

2. **Global `\ignorenumberline` fix**: Redefines econsocart's problematic macro to check if `\numberline` exists before trying to save it. This fixes errors from Appendix A (which IS rendered) as well as any deferred writes.

3. **External label loading**: Labels are loaded from `hiddenappendix-labels.tex` at `\AtBeginDocument`.

---

## File: `@local/hiddenappendix-labels.tex` (New)

This file contains pre-defined `\newlabel` commands for all cross-references in the hidden appendix.

### Format
```latex
\newlabel{label-name}{{display}{page}{title}{hyperref-anchor}{}}
```

- `display`: What `\ref{}` shows (e.g., "B" for Appendix B)
- `page`: What `\pageref{}` shows (e.g., "Online")
- `title`: Section title (for hyperref)
- `hyperref-anchor`: PDF destination name

### Contents
```latex
\makeatletter

% Main appendix section
\newlabel{app:Model-without-splurge}{{B}{Online}{Results in a model without the splurge}{appendix.B}{}}

% Subsections
\newlabel{app:Model-without-splurge-intro}{{B.1}{Online}{Introduction}{subsection.B.1}{}}
\newlabel{app:nosplurge-matching-impcs}{{B.2}{Online}{Matching the iMPCs without the splurge}{subsection.B.2}{}}
\newlabel{app:nosplurge-estimating-betas}{{B.3}{Online}{Estimating discount factor distributions}{subsection.B.3}{}}
\newlabel{app:nosplurge-multipliers}{{B.4}{Online}{Multipliers in the absence of the splurge}{subsection.B.4}{}}

% Figures
\newlabel{fig:splurge0_Norwayestimation}{{B.1}{Online}{Model performance comparison}{figure.B.1}{}}
% ... additional figures ...

% Tables  
\newlabel{tab:Comparison-Splurge-Table}{{B.1}{Online}{Comparison with and without splurge}{table.B.1}{}}
% ... additional tables ...

\makeatother
```

### Maintenance
When the structure of `Subfiles/Appendix-NoSplurge.tex` changes:
1. Add/remove/modify `\newlabel` entries in this file
2. Ensure counter values (B.1, B.2, etc.) match the actual content

---

## File: `reproduce/docker/setup.sh`

### Change
Added `comment` package to the TeX Live installation list:

```bash
# Line ~147 in tlmgr install command
    changepage \
    cm-super \
    comment \       # <-- ADDED
    courier \
```

### Purpose
The `comment` package provides `\excludecomment` which is essential for completely skipping the hidden content without tokenizing it.

---

## File: `HAFiscal.tex`

### Change
Removed duplicate `\label{eq:model}` that was causing "multiply defined labels" warning.

```latex
% Line 504: Removed duplicate label
% (The label is already defined earlier in the document)
```

---

## Build Workflow

The implementation requires no changes to the build workflow:

```bash
# Standard compilation works
pdflatex HAFiscal.tex
bibtex HAFiscal
pdflatex HAFiscal.tex
pdflatex HAFiscal.tex

# Or with latexmk
latexmk -pdf HAFiscal.tex

# Or via reproduce.sh
./reproduce.sh --docs main
```

### What Happens During Compilation

1. `HAFiscal.tex` loads `@local/local-qe.sty`
2. `local-qe.sty` loads `@local/hiddenappendix.sty`
3. `hiddenappendix.sty`:
   - Defines safe `\ignorenumberline` (fixes econsocart issue)
   - Registers `\AtBeginDocument` hook to load labels
   - Defines `hiddencontent` as a comment environment
4. At `\begin{document}`:
   - Labels from `hiddenappendix-labels.tex` are loaded
   - `\ref{app:Model-without-splurge}` now resolves to "B"
5. At `\begin{hiddencontent}...\end{hiddencontent}`:
   - Content is completely skipped (not even tokenized)
   - No errors, no TOC writes, no hyperref destinations

---

## Verification

### Compilation Output
```
hiddenappendix: Loaded labels from hiddenappendix-labels.tex
...
Output written on HAFiscal.pdf (44 pages, ...)
```

### Cross-Reference Check
- `\ref{app:Model-without-splurge}` → "B"
- `\pageref{app:Model-without-splurge}` → "Online"
- No "undefined reference" warnings for hidden appendix labels

### Known Limitation
One pdfTeX warning is expected:
```
pdfTeX warning (dest): name{appendix.B} has been referenced but does not exist
```

This occurs because hyperref links reference `appendix.B` as a PDF destination, but that destination doesn't exist in this PDF (it's in the online supplement). The warning is harmless.

---

## Future Improvements

1. **Automated label extraction**: A script could parse `Appendix-NoSplurge.aux` after standalone compilation and generate `hiddenappendix-labels.tex` automatically.

2. **Build system integration**: `latexmk` or Makefile could manage the label file as a dependency.

3. **Validation**: A pre-commit hook could verify that labels in `hiddenappendix-labels.tex` match those defined in the appendix source.
