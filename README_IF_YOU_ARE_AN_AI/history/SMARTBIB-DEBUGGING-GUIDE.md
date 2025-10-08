# \smartbib System Debugging Guide

## 📋 Problem Context

During the tex4ht compatibility work, we also encountered and fixed issues with the `\smartbib` system incorrectly generating bibliography sections when no citations were present.

## 🔍 \smartbib System Overview

The `\smartbib` system is designed to conditionally include bibliography based on:
1. **Compilation mode**: Standalone vs. integrated
2. **Citation presence**: Whether the file actually contains citations

### Key Components:
- `\citationcount` counter (incremented by redefined `\cite`, `\citet`, `\citep`)
- `\whenstandalone` macro (checks for undefined `\entrypoint`)
- `\whenstandalonewithcitations` macro (combines both conditions)
- `\smartbib` macro (the main conditional bibliography command)

## �� Common \smartbib Issues

### Issue 1: Premature \entrypoint Definition

**Symptom**: `\smartbib` generates bibliography even when no citations are present

**Diagnosis**: 
```latex
% Add debug output to see what's happening
\typeout{DEBUG: citationcount = \arabic{citationcount}}
\makeatletter
\@ifundefined{entrypoint}{%
  \typeout{DEBUG: entrypoint is UNDEFINED - will be treated as standalone}%
}{%
  \typeout{DEBUG: entrypoint is DEFINED - will be treated as integrated}%
}
\makeatother
```

**Root Cause**: `\entrypoint` being defined too early, causing `\whenstandalone` to fail

**Common Sources**:
1. `\newcommand{\entrypoint}{true}` in main document loaded by subfiles
2. Legacy macros like `\onlyinsubfilemakebib` defining `\entrypoint` prematurely

**Fix**: Make `\entrypoint` definition conditional:
```latex
% In main document (e.g., HAFiscal.tex)
\makeatletter
\@ifclassloaded{subfiles}{%
  % Only define entrypoint when actually compiling main document
  \newcommand{\entrypoint}{true}%
}{}
\makeatother
```

### Issue 2: Conflicting Package Definitions

**Symptom**: `LaTeX Error: Command \whenintegrated already defined`

**Root Cause**: Multiple packages defining the same macros (e.g., `local.sty` vs. `econark-ifsubfile.sty`)

**Fix**: Remove duplicate definitions and use a single consistent system

### Issue 3: BibTeX Multiple \bibdata Commands

**Symptom**: `BibTeX: Illegal, another \bibdata command`

**Root Cause**: Each subfile writing its own `\bibdata{system}` to the main `.aux` file

**Fix**: Ensure only integrated compilation runs bibliography commands:
```latex
% In main document
\AtEndDocument{
  \whenintegrated{%
    \clearpage
    \newpage
    \bibliography{\bibfilesfound}
  }%
}
```

## 🛠️ Debugging Protocol

### Step 1: Add Debug Output
```latex
\typeout{DEBUG: citationcount = \arabic{citationcount}}
\makeatletter
\@ifundefined{entrypoint}{%
  \typeout{DEBUG: entrypoint is UNDEFINED - will be treated as standalone}%
}{%
  \typeout{DEBUG: entrypoint is DEFINED - will be treated as integrated}%
}
\makeatother
```

### Step 2: Check Citation Count
```bash
# Compile and check output
pdflatex filename.tex 2>&1 | grep "DEBUG: citationcount"
```

### Step 3: Verify \entrypoint Status
```bash
# Should show UNDEFINED for standalone compilation
pdflatex filename.tex 2>&1 | grep "DEBUG: entrypoint"
```

### Step 4: Trace Macro Definitions
```bash
# Search for premature entrypoint definitions
grep -r "newcommand.*entrypoint" .
grep -r "def.*entrypoint" .
```

## 🔧 Key Fixes Applied

### Fix 1: Conditional \entrypoint in Main Document
```latex
% HAFiscal.tex - make entrypoint definition conditional
\makeatletter
\@ifclassloaded{subfiles}{%
  \newcommand{\entrypoint}{true}%
}{}
\makeatother
```

### Fix 2: Remove Legacy Macros
```latex
% Remove from local.sty:
% \onlyinsubfilemakebib (entire definition removed)
```

### Fix 3: Conditional Bibliography in Main Document
```latex
% HAFiscal.tex - make AtEndDocument bibliography conditional
\AtEndDocument{
  \whenintegrated{%
    \clearpage
    \newpage
    \bibliography{\bibfilesfound}
  }%
}
```

## 🧪 Testing \smartbib

### Test 1: File with No Citations
```bash
pdflatex filename.tex
# Check output PDF - should have NO bibliography section
```

### Test 2: File with Citations
```bash
# Add \cite{something} to file
pdflatex filename.tex
# Check output PDF - should have bibliography section
```

### Test 3: Integration Mode
```bash
# Compile main document
pdflatex HAFiscal.tex
# Should have single bibliography at end with all citations
```

## 🚨 Warning Signs

Watch for these indicators that \smartbib needs debugging:
1. Bibliography sections appearing when no citations are present
2. Multiple bibliography sections in integrated document
3. `BibTeX: Illegal, another \bibdata command` errors
4. Empty bibliography sections in HTML output

## 📈 Success Criteria

After fixing \smartbib issues:
- ✅ Files with no citations produce no bibliography section
- ✅ Files with citations produce appropriate bibliography section
- ✅ Integrated document has single bibliography with all citations
- ✅ No BibTeX errors during compilation
- ✅ HTML output matches PDF output for bibliography presence

---
*The \smartbib system is complex but logical. Most issues stem from premature \entrypoint definition or conflicting package definitions.*
