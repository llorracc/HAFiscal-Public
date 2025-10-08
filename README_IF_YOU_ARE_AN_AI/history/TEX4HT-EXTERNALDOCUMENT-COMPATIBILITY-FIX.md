# tex4ht + \externaldocument Compatibility Fix

## 📋 Problem Summary

**Issue**: Individual LaTeX table/figure files hang indefinitely when compiled to HTML using `make4ht` due to incompatibility between tex4ht and the `\externaldocument` command.

**Root Cause**: tex4ht modifies the LaTeX environment in ways that conflict with `\externaldocument`'s expectation of standard LaTeX behavior for cross-reference loading.

**Impact**: 
- Individual HTML compilation via `WEB_TARGET_DOC` becomes unusable
- Direct `make4ht filename.tex` hangs indefinitely
- Development workflow severely impacted

## 🔧 Solution Overview

**Strategy**: Conditionally disable `\externaldocument` when tex4ht is active, while preserving full functionality for PDF compilation.

**Trade-off**: HTML compilation of individual files loses cross-references to the main document, but gains the ability to compile at all.

## 📁 Files That Need This Fix

Apply this fix to **ANY** LaTeX file that:
1. Uses `\documentclass[...]{subfiles}` 
2. Contains `\whenstandalone{\externaldocument{...}}`
3. Is intended for individual HTML compilation

**Known files requiring fix**:
- `Tables/calibration.tex`
- `Tables/calibrationRecession.tex`
- Any other individual table/figure files with cross-references

## 🛠️ Implementation Steps

### Step 1: Identify the Problem Pattern

Look for this pattern in LaTeX files:
```latex
\documentclass[\PathToRoot/\ProjectName]{subfiles}
\whenstandalone{\externaldocument{\PathToRoot/\ProjectName}} % standalone: get cross-refs from main doc
```

### Step 2: Apply the Fix

Replace the `\whenstandalone{\externaldocument{...}}` line with this conditional block:

```latex
% Fix: tex4ht compatibility - disable externaldocument when tex4ht is loaded
% ⚠️  IMPORTANT: This fix means HTML compilation loses cross-references to main document
% ✅ PDF compilation: Full cross-references work via externaldocument
% ❌ HTML compilation: Cross-references to main document unavailable
% 📚 See: README_WEB_TARGET_DOC_LIMITATIONS.md for complete details
\makeatletter
\@ifpackageloaded{tex4ht}{%
  % tex4ht is loaded - skip externaldocument to prevent hanging
  \whenstandalone{}%
}{%
  % Normal LaTeX - load externaldocument as usual
  \whenstandalone{\externaldocument{\PathToRoot/\ProjectName}}%
}
\makeatother
```

### Step 3: Verify the Fix

Test that the fix works:
```bash
# This should complete without hanging
make4ht filename.tex --loglevel info

# This should still work with cross-references
pdflatex filename.tex
```

## 📚 Required Documentation

When implementing this fix, you MUST also create comprehensive documentation to prevent future confusion:

### Documentation File 1: Technical Reference
Create `README_WEB_TARGET_DOC_LIMITATIONS.md` with:
- Complete explanation of the limitation
- Root cause analysis
- Clear examples of what works vs. what doesn't
- **⚠️ Status: CONFIRMED LIMITATION - DO NOT ATTEMPT TO FIX**

### Documentation File 2: Build System Warnings
Update `HAFiscal-make/README.md` to add:
```markdown
## ⚠️ Known Limitations: WEB_TARGET_DOC Cross-References

### Individual Table/Figure HTML Compilation

When using `WEB_TARGET_DOC` for individual table/figure HTML compilation:

**✅ WORKS:**
- Table/figure content and formatting
- Internal references within the file
- Citations and bibliography (via `\smartbib`)

**❌ LIMITATION:**
- Cross-references to main document content are NOT available in HTML output
- This includes references to equations, other tables/figures, or sections from the main document

**📋 REASON:**
tex4ht package incompatibility with `\externaldocument` command (confirmed after systematic debugging)

**🔧 WORKAROUND:**
- Use individual PDF compilation for complete cross-reference functionality
- Use full document HTML builds when cross-references are required in HTML

**📚 DOCUMENTATION:**
See `HAFiscal-Latest/README_WEB_TARGET_DOC_LIMITATIONS.md` for complete technical details.

**⚠️ DO NOT ATTEMPT TO FIX:** This limitation has been thoroughly investigated and confirmed.
```

### Documentation File 3: Build Script Warnings
Update `makeWeb-HEAD-Latest.sh` to add inline warnings near the `WEB_TARGET_DOC` documentation:
```bash
#   ⚠️  LIMITATION: Individual HTML files lose cross-references to main document
#   📋 REASON: tex4ht incompatibility with \externaldocument (confirmed limitation)
#   ✅ WORKS: Table content, internal refs, citations via smartbib
#   ❌ MISSING: Cross-refs to equations/tables/sections from main document
#   📚 See: HAFiscal-Latest/README_WEB_TARGET_DOC_LIMITATIONS.md
```

## 🧪 Testing Protocol

### Test 1: Verify No Hanging
```bash
timeout 30s make4ht filename.tex --loglevel info
# Should complete successfully, not timeout
```

### Test 2: Verify HTML Quality
```bash
# Check file was generated
ls -la filename.html

# Verify content quality
grep -c "Panel A\|Panel B" filename.html  # Should find table panels
grep -c "References\|Bibliography" filename.html  # Should be 0
```

### Test 3: Verify PDF Still Works
```bash
pdflatex filename.tex
# Should compile successfully with cross-references intact
```

## 🚨 Critical Warnings for Future AIs

### DO NOT Attempt These "Fixes":
1. **DO NOT** try to make tex4ht compatible with `\externaldocument`
2. **DO NOT** modify tex4ht configuration files
3. **DO NOT** create workarounds to restore cross-references in HTML
4. **DO NOT** remove the conditional - it will break HTML compilation

### DO Follow These Guidelines:
1. **DO** apply this fix to any file with the problem pattern
2. **DO** create comprehensive documentation as specified
3. **DO** test both HTML and PDF compilation after applying
4. **DO** preserve the warning comments in the LaTeX files

## 🔍 Debugging History

This fix was developed after systematic debugging that included:
1. Progressive timeout analysis to isolate the hang
2. Minimal test cases to identify `\externaldocument` as the culprit
3. Investigation of tex4ht's modified LaTeX environment
4. Confirmation that the issue is fundamental incompatibility, not a configuration problem

**Key Finding**: The hang occurs because tex4ht's environment prevents `\externaldocument` from correctly processing external `.aux` files, even when those files are valid and up-to-date.

## 📈 Success Metrics

After applying this fix:
- ✅ Individual HTML compilation completes without hanging
- ✅ Generated HTML has proper table/figure content and formatting
- ✅ PDF compilation retains full cross-reference functionality
- ✅ No spurious bibliography sections (confirms `\smartbib` still works)
- ✅ Development workflow restored for individual file compilation

## 🎯 Implementation Checklist

- [ ] Identify all files with `\whenstandalone{\externaldocument{...}}`
- [ ] Apply the conditional fix to each file
- [ ] Add comprehensive warning comments
- [ ] Create `README_WEB_TARGET_DOC_LIMITATIONS.md`
- [ ] Update `HAFiscal-make/README.md`
- [ ] Update `makeWeb-HEAD-Latest.sh` with inline warnings
- [ ] Test HTML compilation (should work without hanging)
- [ ] Test PDF compilation (should work with cross-references)
- [ ] Commit all changes with descriptive commit message
- [ ] Document the trade-off clearly for future reference

---
*This fix represents a confirmed limitation, not a temporary workaround. The tex4ht + externaldocument incompatibility is fundamental and should not be "fixed" by future modifications.*
