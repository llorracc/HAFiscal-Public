# LaTeX Compilation System Architecture

This document provides comprehensive documentation of HAFiscal's sophisticated multi-layer conditional compilation system, which enables flexible document generation from single source files.

## System Overview

The HAFiscal LaTeX compilation system implements three independent layers of conditional compilation that work together to provide maximum flexibility:

1. **BUILD_MODE Layer**: Controls document length (SHORT/LONG)
2. **Smart Bibliography Layer**: Intelligent bibliography inclusion based on context
3. **PDF/HTML Dual Output Layer**: Format-specific content control

This architecture allows single `.tex` files to generate multiple output formats and document versions automatically.

## Layer 1: BUILD_MODE Control

### Environment Variable Control
```bash
BUILD_MODE=SHORT ./reproduce.sh --docs   # Quick debugging version
BUILD_MODE=LONG ./reproduce.sh --docs    # Complete version (default)
```

### LaTeX Implementation
The system uses `\ifdefined\ShortVersion` conditionals throughout the codebase:

```latex
\ifdefined\ShortVersion
  % Content for SHORT mode only
\else  
  % Content for LONG mode (default)
\fi
```

### Usage Patterns
- **SHORT Mode**: Ideal for debugging, quick builds, and development iteration
- **LONG Mode**: Complete content for final output, journal submissions, and full reproduction

## Layer 2: Smart Bibliography System

### The `\smartbib` Macro
The smart bibliography system automatically detects compilation context and includes appropriate bibliographies:

```latex
\smartbib  % Automatically includes relevant bibliography files
```

### Context Detection
- **Standalone Compilation**: When a subfile is compiled independently
- **Integrated Compilation**: When a subfile is included in the main document  
- **Citation Analysis**: Only includes bibliography entries for citations actually used

### Benefits
- Eliminates bibliography duplication
- Handles complex cross-references between main document and subfiles
- Reduces compilation time by including only necessary bibliography entries

## Layer 3: PDF/HTML Dual Output

### Web Boolean System
The system uses a `Web` boolean variable that's automatically set based on compilation type:

```latex
% In @local/private/local-packages.sty
\ifdvi
  \setboolean{Web}{true}   % HTML/web compilation detected
\else
  \setboolean{Web}{false}  % PDF compilation detected  
\fi
```

### Conditional Macros
Defined in `@local/webpdf-macros.sty`:

```latex
\pdfonly{content}                    % Execute only for PDF
\webonly{content}                    % Execute only for HTML/web  
\weborpdf{web-content}{pdf-content}  % Format-specific alternatives
```

### Subfile Standalone Pattern
All subfiles use this pattern for dual compilation mode compatibility:

```latex
\documentclass[../HAFiscal.tex]{subfiles}
\begin{document}

% Document content here

\pdfonly{\end{document}}  % Terminates early for PDF standalone compilation
% For HTML compilation, continues to process remaining content
\end{document}
```

## Enhanced Build System

### Core Scripts

#### `reproduce_documents.sh`
The main document compilation script with enhanced features:

```bash
# Scope control
./reproduce_documents.sh --scope main        # Root directory only
./reproduce_documents.sh --scope all         # Include subdirectories
./reproduce_documents.sh --scope figures     # Root + Figures/
./reproduce_documents.sh --scope tables      # Root + Tables/
./reproduce_documents.sh --scope subfiles    # Root + Subfiles/

# Build options
./reproduce_documents.sh --clean             # Clean auxiliary files first
./reproduce_documents.sh --quick             # Single-pass compilation  
./reproduce_documents.sh --dry-run           # Show commands without execution
./reproduce_documents.sh --verbose           # Detailed output
```

### Enhanced Cleanup System
The build system includes sophisticated auxiliary file cleanup:

- **Standard LaTeX Files**: `.aux`, `.log`, `.out`, `.toc`, `.lof`, `.lot`, `.bbl`, `.blg`
- **Extended Cleanup**: `.txt`, `.dep` files for non-root documents
- **Conditional Cleanup**: Only removes files when safe to do so
- **Directory-Aware**: Different cleanup strategies for root vs. subdirectory documents

### Package Management System

#### Centralized Package Loading
- **`@local/local.sty`**: Development and full-feature packages
- **`@local/local-qe.sty`**: Minimal packages for journal submissions
- **`@local/webpdf-macros.sty`**: PDF/HTML conditional compilation macros

#### Benefits
- Eliminates package duplication and conflicts
- Provides context-specific package loading
- Simplifies maintenance and debugging
- Supports multiple compilation targets (QE submission, full paper, etc.)

## Compilation Contexts

### Main Document Compilation
```bash
BUILD_MODE=LONG ./reproduce.sh --docs --scope main
```
- Compiles `HAFiscal.tex` and `HAFiscal-Slides.tex`
- Uses complete package set from `@local/local.sty`
- Includes full bibliography via `\smartbib`
- Generates PDF output with `\pdfonly` content

### Subfile Standalone Compilation
```bash
cd Subfiles/
pdflatex Introduction.tex
```
- Compiles individual subfile independently
- Uses `\pdfonly{\end{document}}` to terminate early
- Loads packages via parent document reference
- Generates standalone PDF for the specific section

### HTML/Web Compilation  
```bash
make4ht HAFiscal.tex
```
- Automatically sets `Web` boolean to `true`
- Skips `\pdfonly` content, processes `\webonly` content
- Generates HTML output suitable for web deployment
- Uses same source files as PDF compilation

### QE Journal Submission
```bash
# Uses @local/local-qe.sty for minimal package set
./build-qe-submission.sh
```
- Minimal package loading to meet journal requirements
- Specific formatting for Quarterly Journal of Economics
- Automated package copying and template generation

## Advanced Features

### Circular Reference Handling
The `.latexmkrc` configuration provides robust handling of circular references common in academic papers with complex cross-referencing.

### Multi-Directory Support
The build system can compile documents across multiple directories (`Figures/`, `Tables/`, `Subfiles/`) while maintaining proper dependency tracking.

### Error Recovery
Enhanced error handling with informative messages and automatic cleanup on compilation failure.

### Development Support
- Dry-run capability for debugging compilation commands
- Verbose output for detailed build process visibility
- Quick compilation modes for rapid development iteration

## Integration with Reproduction Workflow

The compilation system integrates seamlessly with the broader reproduction workflow:

1. **Interactive Mode**: `./reproduce.sh` → Document compilation option
2. **Non-Interactive**: `REPRODUCE_TARGETS=docs ./reproduce.sh`  
3. **Automated CI/CD**: Environment variables control compilation behavior
4. **GitHub Pages**: HTML output automatically deployed via static site generation

This multi-layer architecture provides the flexibility needed for academic paper workflows while maintaining simplicity for end users through the unified `./reproduce.sh` interface. 