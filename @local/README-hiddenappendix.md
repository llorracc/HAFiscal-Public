# Hidden Appendix Package

## Overview

The `hiddenappendix.sty` package enables cross-references to content that is **processed** for labels but **not rendered** in the PDF output. This is essential for online appendices where the main document needs working `\ref{}` and `\pageref{}` commands pointing to content published separately.

## How It Works

The package uses the `environ` package to:

1. **Capture** the content inside `\begin{hiddencontent}...\end{hiddencontent}`
2. **Process** the content in a `\vbox{}` (so `\label{}` commands execute and write to `.aux`)
3. **Override** `\thepage` to "Online" (so `\pageref{}` returns "Online")
4. **Discard** the vbox (so nothing appears in the PDF)

```latex
\NewEnviron{hiddencontent}[1][Online]{%
  \setbox0\vbox{%
    \def\thepage{#1}%  % Override page number
    \BODY              % Process the content
  }%
  % Box is discarded - content doesn't appear
}
```

## Usage

In the main document:

```latex
\begin{hiddencontent}[Online]
  \section{Results in a Model Without the Splurge}
  \label{app:Model-without-splurge}
  
  ... content with figures, tables, equations ...
\end{hiddencontent}
```

Cross-references work automatically:
- `\ref{app:Model-without-splurge}` → "B" (section number)
- `\pageref{app:Model-without-splurge}` → "Online"

## Key Benefits

- **No extra files needed** - labels are defined automatically by processing content
- **Standard LaTeX** - uses familiar `\label{}` and `\ref{}` commands
- **Accurate numbering** - section/figure/table counters increment correctly

## Repository Versions

| Repository | Behavior |
|------------|----------|
| **-Latest** | Content processed for labels, discarded from PDF |
| **-Public** | Content processed for labels, discarded from PDF |
| **-QE** | May require additional handling for econsocart compliance |

## Files

| File | Purpose |
|------|---------|
| `hiddenappendix.sty` | Main package (environ-based approach) |
| `local-qe.sty` | Loads hiddenappendix via `\RequirePackage{@local/hiddenappendix}` |

## Documentation Files

Historical documentation of design decisions:
- `hiddenappendix-implementation.md` - Implementation details
- `hiddenappendix-high-concept-alternatives.md` - Alternative approaches considered
- `hiddenappendix-failed-approaches.md` - What didn't work and why
