# Single Source of Truth (SST) for Paper Metadata

## Problem Statement

HAFiscal has two document variants:

- **HAFiscal-Latest** (working paper) - uses `econark` documentclass
- **HAFiscal-QE** (journal submission) - uses `econsocart` documentclass

These document classes have **different syntaxes** for specifying metadata (title, authors, affiliations, keywords, etc.):

| Aspect | econark | econsocart |
|--------|---------|------------|
| Title | `\title{...}` | `\title{...}` ✓ same |
| Authors | `\author{A \and B \and C}` | `\author[affil]{...}` with `\fnms`/`\snm` |
| Affiliations | In `\thanks{}` | Separate `\address[label]{...}` |
| Keywords | `\keywords{...}` or custom | `\begin{keyword}...\kwd{}\end{keyword}` |
| Abstract | `\begin{abstract}` | `\begin{abstract}` ✓ same |

Without SST, metadata must be duplicated in:

- `Subfiles/HAFiscal-titlepage.tex` (for econark)
- `qe/HAFiscal-QE-template.tex` (for econsocart)

This leads to:

- ❌ Duplication and drift
- ❌ Maintenance burden
- ❌ Risk of inconsistency

## Solution: Compatibility Layer

### Architecture

```
@local/metadata.ltx (SST)
  ↓
  Defines metadata in econsocart format
  ↓
  ├─→ econsocart class → Uses natively
  └─→ econark class → @local/econark-econsocart-compat.sty translates
```

### Components

1. **`@local/metadata.ltx`** - Single source of truth
   - Defines `\MetadataApply` command
   - Uses econsocart syntax (more structured)
   - Works for both document classes

2. **`@local/econark-econsocart-compat.sty`** - Compatibility layer
   - Detects document class
   - If `econark`: Defines econsocart commands, captures metadata
   - If `econsocart`: Does nothing (uses native commands)

3. **Document files** use `\MetadataApply`
   - Same command works in both contexts
   - Automatically adapts to document class

## Usage

### In HAFiscal.tex (econark)

```latex
\documentclass{econark}

% Load compatibility layer BEFORE metadata
\usepackage{@local/econark-econsocart-compat}

% Other packages
\usepackage{local}

% Load metadata (defines \MetadataApply)
\input{@local/metadata.ltx}

\begin{document}

% Apply metadata (compatibility layer translates to econark format)
\MetadataApply

% ... rest of document
```

### In qe/HAFiscal-QE-template.tex (econsocart)

```latex
\documentclass[qe,draft]{econsocart}

% Load metadata (defines \MetadataApply)
\input{@local/metadata.ltx}

% Apply metadata (uses econsocart commands natively)
\MetadataApply

\begin{document}

% ... rest of document
```

### In @local/metadata.ltx (SST)

```latex
% Define base metadata
\newcommand{\QEtitle}{Welfare and Spending Effects...}
\newcommand{\PDFTitle}{\QEtitle}
\newcommand{\PDFAuthor}{Carroll, Crawley, Du, Frankovic, Tretvoll}

% Define structured metadata
\newcommand{\MetadataApply}{%
  \title{\QEtitle}
  
  \begin{aug}
    \author[jhu-econ]{\fnms{Christopher D.}~\snm{Carroll}\ead{...}}
    \author[fed]{\fnms{Edmund}~\snm{Crawley}\ead{...}}
    % ... more authors
    
    \address[jhu-econ]{Johns Hopkins University}
    \address[fed]{Federal Reserve Board}
    % ... more addresses
  \end{aug}
  
  \begin{keyword}
    \kwd{Fiscal Policy}
    \kwd{Heterogeneous Agents}
    % ... more keywords
  \end{keyword}
  
  % Apply to econark if using compatibility layer
  \@ifundefined{ApplyCompatMetadata}{}{\ApplyCompatMetadata}
}
```

## How It Works

### For econsocart (native)

1. `econsocart` class provides `\author[label]{...}`, `\address[label]{...}`, etc.
2. `\MetadataApply` uses these commands directly
3. `econsocart` processes them according to journal style

### For econark (translated)

1. `econark-econsocart-compat.sty` defines stub versions of econsocart commands
2. These stubs capture the metadata into internal storage
3. `\ApplyCompatMetadata` extracts and formats for econark:

   ```
   \author[jhu]{Alice} + \author[mit]{Bob}
   → \author{Alice \and Bob}
   ```

4. Affiliations can be added to `\thanks{}` or handled separately

## Benefits

✅ **Single Source of Truth** - Metadata defined once in `@local/metadata.ltx`

✅ **DRY Principle** - No duplication between econark and econsocart versions

✅ **Maintainability** - Update metadata in one place

✅ **Consistency** - Impossible for versions to drift

✅ **Flexibility** - Can enhance translation layer as needed

✅ **Backwards Compatible** - Existing documents continue to work

## Limitations

### Structural Differences

Some `econsocart` features don't have direct `econark` equivalents:

- **Structured affiliations** → Can be extracted but econark has no native support
- **Email addresses** → Can be added to `\thanks{}` manually
- **Funding environment** → Can be added to acknowledgments

### Workaround: Hybrid Approach

For econark-specific formatting, you can still use:

```latex
\begin{document}

\MetadataApply  % Apply SST metadata

% Econark-specific additions
\thanks{
  Carroll: Johns Hopkins, \texttt{ccarroll@jhu.edu}.
  Crawley: Federal Reserve Board, \texttt{edmund.s.crawley@frb.gov}.
  % ... rest
}
```

## Migration Path

### Phase 1: Create Infrastructure ✅

- [x] Create `@local/econark-econsocart-compat.sty`
- [x] Update `@local/metadata.ltx` with `\MetadataApply`
- [x] Document the system

### Phase 2: Test with HAFiscal-QE

- [ ] Update `qe/HAFiscal-QE-template.tex` to use `\MetadataApply`
- [ ] Verify compilation in draft and final modes
- [ ] Verify line numbering in draft mode

### Phase 3: Integrate with HAFiscal.tex (optional)

- [ ] Add `\usepackage{econark-econsocart-compat}` to `HAFiscal.tex`
- [ ] Potentially update `Subfiles/HAFiscal-titlepage.tex` to use `\MetadataApply`
  - Or keep current titlepage (more elaborate) and only use SST for basic metadata
- [ ] Test compilation

### Phase 4: Use for hyperref (done)

- [x] Use `\PDFTitle`, `\PDFAuthor`, etc. in `\hypersetup`
- [x] Single source for PDF metadata

## Testing

### Test Cases

1. **QE draft mode** - Verify line numbers work
2. **QE final mode** - Verify headers, no line numbers
3. **Econark** - Verify title/authors render correctly
4. **PDF metadata** - Verify `\PDFTitle` etc. work in both
5. **Compilation** - Both documents compile without errors

### Commands to Test

```bash
# Test QE version
cd qe/
latexmk -pdf HAFiscal-QE.tex

# Test econark version
cd ..
latexmk -pdf HAFiscal.tex
```

## Future Enhancements

### Possible Improvements

1. **Extract affiliations to econark \thanks{}** automatically
2. **Generate plain-text author list** for other uses
3. **Generate BibTeX entry** from metadata
4. **Validate metadata** (ensure all required fields present)
5. **Support for multiple document variants** (slides, etc.)

### Example: Auto-generate \thanks{}

```latex
% In econark-econsocart-compat.sty
\newcommand{\GenerateThanks}{%
  Carroll: \GetAddress{jhu-econ}, \GetEmail{1}.
  Crawley: \GetAddress{fed}, \GetEmail{2}.
  % ...
}
```

## See Also

- `@local/metadata.ltx` - The SST metadata definition
- `@local/econark-econsocart-compat.sty` - The compatibility layer
- `Subfiles/HAFiscal-titlepage.tex` - Current econark titlepage
- `qe/HAFiscal-QE-template.tex` - Current econsocart template

---

**Version:** 1.0  
**Date:** 2025-11-20  
**Status:** Infrastructure complete, ready for testing
