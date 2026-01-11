# Hidden Appendix: Failed Approaches

This document chronicles the various approaches attempted to solve the hidden appendix problem before arriving at the working solution.

## The Core Problem

The `hiddencontent` environment needed to:
1. **NOT render** content in the main PDF (it belongs in an online supplement)
2. **Define labels** so `\ref{app:Model-without-splurge}` → "B" and `\pageref{}` → "Online"
3. **Work with econsocart.cls** - the Quantitative Economics journal document class

The fundamental challenge: econsocart's TOC machinery writes `\ignorenumberline` to the `.toc` file, which fails when `\numberline` is undefined during page output.

---

## Approach 1: Invisible Box Rendering (Initial Attempt)

### Concept
Process the content inside a TeX box, extract labels, then discard the box.

```latex
\NewEnviron{hiddencontent}[1][Online]{%
  \begingroup
    \def\thepage{#1}%
    \setbox0=\vbox{\BODY}%  % Process content, define labels
  \endgroup
  % Box is discarded, but labels persist
}
```

### Why It Failed
- econsocart's `\section` commands write `\@writefile{toc}{\ignorenumberline}` 
- These writes are **deferred** until page output
- When the `.toc` file is read later, `\ignorenumberline` tries to redefine `\numberline`
- But `\numberline` doesn't exist in the output routine context
- **Error**: `Undefined control sequence \sv@numberline`

### Attempted Fixes
1. **`\providecommand{\ignorenumberline}{}`** - Failed because econsocart uses `\def`, which overwrites
2. **`\gdef\ignorenumberline{...}` at package load** - Failed because econsocart redefines it later
3. **`\AtBeginDocument` hook** - Failed because econsocart's hook runs after ours

---

## Approach 2: Disable TOC Writes Inside Environment

### Concept
Prevent TOC-related commands from executing inside `hiddencontent`.

```latex
\NewEnviron{hiddencontent}[1][Online]{%
  \begingroup
    \let\addcontentsline\@gobbletwo
    \let\addtocontents\@gobbletwo
    \def\@writefile##1##2{}%  % Disable all file writes
    \setbox0=\vbox{\BODY}%
  \endgroup
}
```

### Why It Failed
- The `\@writefile{toc}{\ignorenumberline}` was being written by content **outside** `hiddencontent`
- Specifically, Appendix A (which IS rendered) also uses econsocart's appendix machinery
- The error originated from the main document's appendices, not the hidden content
- Local overrides inside the environment couldn't affect global document behavior

---

## Approach 3: Patch econsocart's `\econsocart@imstoc`

### Concept
The problematic `\ignorenumberline` is defined in `econsocart@imstoc`. Patch it to be safe.

```latex
\let\orig@econsocart@imstoc\econsocart@imstoc
\def\econsocart@imstoc{%
  \orig@econsocart@imstoc
  \gdef\ignorenumberline{%
    \@ifundefined{numberline}{}{\let\sv@numberline\numberline\let\numberline\@gobble}%
  }%
}
```

### Why It Failed
- `\econsocart@imstoc` is defined in `econsocart.cfg`, which is loaded during class processing
- Our package loads after the class, so `\econsocart@imstoc` has already been called
- The `\let\orig@...` captured an already-executed macro
- Timing issue: class hooks run before package hooks

---

## Approach 4: Zero-Height Invisible Rendering

### Concept
Render content in a zero-height box so it's processed but invisible.

```latex
\NewEnviron{hiddencontent}[1][Online]{%
  \begingroup
    \def\thepage{#1}%
    % Disable hyperref to avoid destination conflicts
    \let\hyper@anchor\@gobble
    \let\pdfbookmark\@gobbletwo
    \let\Hy@writebookmark\@gobblefive
    % Render in zero-height box
    \vbox to 0pt{\BODY\vss}%
  \endgroup
}
```

### Why It Failed
- Even with zero height, the content is **fully processed**
- LaTeX's output routine still runs, triggering deferred writes
- `\ignorenumberline` error persisted
- Additional errors appeared: `\@@BOOKMARK` undefined, `\GTS@...` errors
- Hyperref destinations caused PDF structure issues

---

## Approach 5: Selective `\@writefile` Filtering

### Concept
Allow most file writes but filter out TOC-specific ones.

```latex
\let\orig@writefile\@writefile
\def\@writefile#1#2{%
  \def\@tempa{#1}\def\@tempb{toc}%
  \ifx\@tempa\@tempb\else\orig@writefile{#1}{#2}\fi
}
```

### Why It Failed
- The filtering worked inside the environment
- But `\ignorenumberline` writes came from **deferred** operations
- The actual `\@writefile` call happened during `\shipout`, outside our filtered context
- TeX's asynchronous output routine defeated our synchronous filtering

---

## Approach 6: Global Safe `\ignorenumberline` (Partial Success)

### Concept
Make `\ignorenumberline` globally safe by checking if `\numberline` exists.

```latex
\def\ignorenumberline{%
  \@ifundefined{numberline}{}{%
    \let\sv@numberline\numberline
    \let\numberline\@gobble
  }%
}
\AtBeginDocument{%
  % Re-apply in case econsocart overwrites
  \def\ignorenumberline{...same...}%
}
```

### Result
- **This fixed the `\ignorenumberline` error!**
- But the hidden content was still being processed
- Labels were defined, but so was all the problematic TOC/hyperref machinery
- New errors appeared from hyperref destinations

### Lesson Learned
The `\ignorenumberline` fix was necessary but not sufficient. We still needed a way to completely skip the hidden content.

---

## Why Processing Content At All Was Problematic

Even with `\ignorenumberline` fixed, processing the hidden content caused:

1. **Hyperref destination conflicts** - PDF destinations for hidden sections
2. **Float processing** - Figures/tables trying to be placed
3. **Counter increments** - Section/figure/table counters advancing
4. **Complex macro expansion** - Any bug in the content would crash the build

The fundamental insight: **We needed to NOT process the content at all**, but still have working labels.

---

## The Solution: External Label Harvesting

The working approach completely separates label definition from content processing:

1. Use `comment` package to **truly skip** the `hiddencontent` body
2. Define labels in a separate file (`hiddenappendix-labels.tex`)
3. Load the labels at `\AtBeginDocument`

This avoids ALL the problems above because the content is never tokenized, expanded, or processed in any way.

See `hiddenappendix-implementation.md` for details of the working solution.
