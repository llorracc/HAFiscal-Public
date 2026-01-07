# Hidden Appendix: High-Concept Alternative Approaches

This document describes the high-level architectural alternatives considered for solving the hidden appendix cross-reference problem.

## Problem Statement

**Goal**: Enable `\ref{app:Model-without-splurge}` to show "B" and `\pageref{}` to show "Online" in the main document, while the actual appendix content is NOT rendered (it exists only in a separate online supplement PDF).

**Constraint**: Cannot modify `econsocart.cls` or `econsocart.cfg` (publisher-provided files).

---

## Approach 1: External Aux File Harvesting

### Concept
Completely skip the hidden content during main document compilation, and instead read label definitions from a pre-generated external file.

### How It Works
1. **Build Phase**: Compile the standalone appendix (`Appendix-NoSplurge.tex`) to generate its `.aux` file
2. **Extract Phase**: Parse the `.aux` file to extract `\newlabel` commands
3. **Transform Phase**: Modify page references to show "Online" instead of page numbers
4. **Inject Phase**: Load these labels in the main document via `\AtBeginDocument`

### Advantages
- Complete isolation from econsocart's TOC machinery
- No content processing means no errors from complex content
- Works regardless of what's inside the hidden appendix

### Disadvantages
- **Manual maintenance**: Label file must be updated when appendix structure changes
- Requires a build step or manual process to regenerate labels
- Two-file synchronization risk

### Implementation Complexity: Low
Just need `\excludecomment{hiddencontent}` and `\InputIfFileExists{labels.tex}`.

---

## Approach 2: Invisible Rendering (Zero-Height Box)

### Concept
Process the hidden content normally (defining labels, incrementing counters) but render it in a zero-height box so it doesn't appear in the output.

### How It Works
```latex
\NewEnviron{hiddencontent}[1][Online]{%
  \begingroup
    \def\thepage{#1}%
    \vbox to 0pt{\BODY\vss}%  % Process but don't show
  \endgroup
}
```

### Advantages
- Labels are defined automatically from the actual content
- No separate label file to maintain
- Single source of truth

### Disadvantages
- **Hyperref destination conflicts**: PDF destinations are created for invisible content
- Content is fully processed, so any errors in content cause build failures
- Counters increment (section numbers, figure numbers) even for invisible content
- econsocart's TOC machinery still triggers, causing `\ignorenumberline` errors

### Implementation Complexity: High
Requires disabling hyperref destinations, TOC writes, float processing, etc.

---

## Approach 3: Conditional Compilation with Shared Labels

### Concept
Use a two-pass build system where labels are shared between standalone and integrated builds.

### How It Works
1. **Pass 1**: Compile standalone appendix, generating `appendix.aux`
2. **Pass 2**: Compile main document with `\externaldocument{appendix}` (xr package)

### Advantages
- Standard LaTeX mechanism for cross-document references
- Labels always in sync with actual content

### Disadvantages
- **xr/xr-hyper packages**: econsocart v1.0.6 explicitly forbids these packages
- Requires coordinated multi-file build process
- Hyperref compatibility issues across documents

### Implementation Complexity: Medium (but blocked by econsocart)

---

## Approach 4: Compile-Time Label Extraction

### Concept
During the main document build, shell out to extract labels from the appendix source.

### How It Works
```latex
\immediate\write18{extract-labels.sh Subfiles/Appendix-NoSplurge.tex > labels.tex}
\input{labels.tex}
\excludecomment{hiddencontent}
```

### Advantages
- Labels always derived from actual source
- Single build command for user
- No manual synchronization

### Disadvantages
- Requires `--shell-escape` (security concern)
- External script dependency
- Parsing LaTeX source to find labels is fragile
- Won't work in restricted build environments

### Implementation Complexity: Medium

---

## Approach 5: Build System Integration

### Concept
Use `latexmk` or a Makefile to manage the label extraction as a build dependency.

### How It Works
```makefile
hiddenappendix-labels.tex: Subfiles/Appendix-NoSplurge.tex
    pdflatex Appendix-NoSplurge.tex
    ./extract-labels.py Appendix-NoSplurge.aux > hiddenappendix-labels.tex

HAFiscal.pdf: HAFiscal.tex hiddenappendix-labels.tex
    latexmk HAFiscal.tex
```

### Advantages
- Automatic label synchronization
- Standard build tooling
- Reproducible builds

### Disadvantages
- More complex build setup
- Users must use the provided build system
- Doesn't work with simple `pdflatex HAFiscal.tex`

### Implementation Complexity: Medium

---

## Approach 6: Runtime Label Definition via Lua

### Concept
Use LuaLaTeX to programmatically define labels by parsing the appendix source at compile time.

### How It Works
```latex
\directlua{
  local f = io.open("Subfiles/Appendix-NoSplurge.tex")
  for line in f:lines() do
    local label = line:match("\\label{(.-)}")
    if label then
      tex.print("\\newlabel{" .. label .. "}{{B}{Online}{}{}{}}")
    end
  end
}
```

### Advantages
- No external tools needed
- Automatic synchronization
- Single-pass compilation

### Disadvantages
- Requires LuaLaTeX (not pdflatex)
- Fragile parsing of LaTeX source
- Won't find labels inside macros or conditional code

### Implementation Complexity: Medium

---

## Chosen Solution: Approach 1 (External Label Harvesting)

After evaluating all approaches, **Approach 1** was selected because:

1. **Simplest implementation**: Just skip content and load a file
2. **Most robust**: No interaction with econsocart's machinery
3. **No special requirements**: Works with standard pdflatex
4. **Acceptable trade-off**: Manual label maintenance is manageable for a stable appendix

The implementation uses:
- `comment` package for `\excludecomment{hiddencontent}`
- `hiddenappendix-labels.tex` with pre-defined `\newlabel` commands
- Global `\ignorenumberline` fix for econsocart compatibility

See `hiddenappendix-implementation.md` for the complete implementation details.
