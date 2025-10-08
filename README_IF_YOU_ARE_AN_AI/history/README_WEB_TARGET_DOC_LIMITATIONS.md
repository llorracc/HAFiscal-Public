# WEB_TARGET_DOC Individual Table/Figure HTML Compilation - Known Limitations

## 📋 Summary

Individual table and figure HTML compilation via `WEB_TARGET_DOC` works with important limitations regarding cross-references.

## ✅ What Works

### PDF Compilation (Individual Files)
- **Full functionality**: Cross-references, citations, bibliography all work perfectly
- **Command**: `pdflatex Tables/calibrationRecession.tex`
- **Cross-references**: Complete access to main document labels via `\externaldocument`

### HTML Compilation (Individual Files)  
- **Table/figure content**: Renders perfectly with proper formatting
- **Internal references**: Work within the individual file
- **Citations/Bibliography**: Handled correctly by `\smartbib` system
- **Command**: `WEB_TARGET_DOC="Tables/calibrationRecession" ./makeWeb-HEAD-Latest.sh`

## ❌ Known Limitations

### HTML Compilation Cross-References
- **Cross-references to main document**: NOT available in HTML output
- **Reason**: tex4ht incompatibility with `\externaldocument` command
- **Examples of what doesn't work**:
  - References to equations in main document
  - References to other tables/figures not in the same file
  - Section references to main document content

## 🔧 Technical Details

### Root Cause
The `\externaldocument{\PathToRoot/\ProjectName}` command that enables cross-references:
1. **Works perfectly** with regular LaTeX (`pdflatex`)
2. **Causes hanging** with tex4ht due to modified LaTeX environment
3. **Solution**: Conditionally disabled when tex4ht is loaded

### Implementation
```latex
% Applied to individual table/figure files
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

## 📚 Recommended Workflow

### For Development/Review
1. **Individual PDF compilation**: Use for complete cross-reference checking
2. **Individual HTML compilation**: Use for web preview of table/figure formatting

### For Production
1. **Full document builds**: Use `makeWeb-HEAD-Latest.sh` for complete HTML with all cross-references
2. **Individual HTML**: Use only when cross-references to main document are not needed

## ⚠️ Important Notes

- **Do NOT expect cross-references to main document to work in individual HTML files**
- **Do NOT attempt to "fix" the tex4ht + externaldocument incompatibility** - this has been thoroughly investigated
- **DO use full document builds when cross-references are required in HTML**

## 🎯 Status: CONFIRMED LIMITATION - DO NOT ATTEMPT TO FIX

This limitation has been systematically diagnosed and confirmed. The tex4ht package fundamentally conflicts with the `\externaldocument` mechanism. Any future attempts to resolve this should first review this documentation and the associated debugging history.

---
*Documentation created: September 11, 2025*  
*Last confirmed: After systematic debugging with progressive timeout analysis* 