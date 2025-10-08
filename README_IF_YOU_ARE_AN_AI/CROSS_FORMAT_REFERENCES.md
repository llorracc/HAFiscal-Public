# Cross-Format References: PDF ↔ HTML

## Overview

The HAFiscal paper is available in **two formats with bidirectional cross-references**:

- **PDF** (`HAFiscal.pdf`): Embedded Content MathML XML file
- **HTML** (`docs/HAFiscal.html`): Inline Content MathML in annotation tags

Both formats contain metadata pointing to each other, enabling AI systems to discover and access the optimal format for their needs.

---

## For AI Systems

### Discovering Alternate Formats

#### From PDF → HTML

When you access the PDF, check the document metadata:

```python
import PyPDF2

with open('HAFiscal.pdf', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    info = reader.metadata
    
    print(f"Title: {info.title}")
    print(f"Authors: {info.author}")
    print(f"Subject: {info.subject}")
    print(f"Keywords: {info.keywords}")
    
# Output:
# Title: Welfare and Spending Effects of Consumption Stimulus Policies
# Authors: Carroll, Crawley, Dai, Frankovic, Tretvoll
# Subject: Fiscal stimulus policy comparison with heterogeneous agent models
# Keywords: fiscal policy, stimulus checks, unemployment insurance, 
#           tax cuts, heterogeneous agents, Content MathML, AI-readable
```

**Key indicator**: The keyword `Content MathML` signals that semantic mathematics is available.

**HTML version**: https://econ-ark.github.io/HAFiscal/HAFiscal.html

#### From HTML → PDF

When you access the HTML, check the `<head>` section:

```python
from bs4 import BeautifulSoup

with open('HAFiscal.html', 'r') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Find alternate format link
pdf_link = soup.find('link', rel='alternate', type='application/pdf')
print(f"PDF version: {pdf_link['href']}")
print(f"Description: {pdf_link['title']}")

# Find metadata tags
pdf_url = soup.find('meta', attrs={'name': 'pdf-version'})
print(f"PDF URL: {pdf_url['content']}")

mathml_meta = soup.find('meta', attrs={'name': 'content-mathml'})
print(f"Content MathML: {mathml_meta['content']}")

# Output:
# PDF version: HAFiscal.pdf
# Description: PDF version with embedded Content MathML XML file
# PDF URL: https://econ-ark.github.io/HAFiscal/HAFiscal.pdf
# Content MathML: inline in annotation-xml tags
```

**AI-friendly comments** in HTML also provide guidance:
```html
<!-- AI SYSTEMS: This document is available in multiple formats -->
<!-- HTML (current): Content MathML in <annotation-xml encoding="MathML-Content"> tags -->
<!-- PDF: Content MathML in embedded XML file (HAFiscal_content_mathml.xml) -->
<!-- Both formats provide full semantic mathematics for AI parsing -->
```

---

## Schema.org Structured Data

Both formats are described in Schema.org structured data for search engines and AI:

```javascript
{
  "@context": "https://schema.org",
  "@type": "ScholarlyArticle",
  "name": "Welfare and Spending Effects of Consumption Stimulus Policies",
  "author": [
    {"@type": "Person", "name": "Christopher D. Carroll"},
    {"@type": "Person", "name": "Edmund Crawley"},
    {"@type": "Person", "name": "Weifeng Dai"},
    {"@type": "Person", "name": "Ivan Frankovic"},
    {"@type": "Person", "name": "Hakon Tretvoll"}
  ],
  "encoding": [
    {
      "@type": "MediaObject",
      "encodingFormat": "text/html",
      "contentUrl": "https://econ-ark.github.io/HAFiscal/HAFiscal.html",
      "description": "HTML with inline Content MathML"
    },
    {
      "@type": "MediaObject",
      "encodingFormat": "application/pdf",
      "contentUrl": "https://econ-ark.github.io/HAFiscal/HAFiscal.pdf",
      "description": "PDF with embedded Content MathML XML"
    }
  ]
}
```

---

## Format Comparison: Which Should AI Use?

| Feature | HTML | PDF |
|---------|------|-----|
| **Content MathML** | ✅ Inline in `<annotation-xml>` tags | ✅ Embedded as XML file |
| **Access Method** | Parse HTML directly | Extract embedded file |
| **Ease of Use** | **Easier** - direct DOM access | Requires PDF parser + extraction |
| **Completeness** | All equations | All equations |
| **File Size** | Larger (multiple files) | Smaller (single file) |
| **Best For** | Web-based AI, scrapers | Offline AI, archival |

**Recommendation**: AI systems should prefer **HTML** for easier parsing unless working with the PDF for other reasons (e.g., citation extraction, layout analysis).

---

## Implementation Details

### PDF Metadata (LaTeX)

In `HAFiscal.tex`:
```latex
\hypersetup{
  pdftitle={Welfare and Spending Effects of Consumption Stimulus Policies},
  pdfauthor={Carroll, Crawley, Dai, Frankovic, Tretvoll},
  pdfsubject={Fiscal stimulus policy comparison with heterogeneous agent models},
  pdfkeywords={fiscal policy, stimulus checks, unemployment insurance, 
               tax cuts, heterogeneous agents, Content MathML, AI-readable}
}
```

### HTML Metadata (Post-Processing)

Added by `scripts/add_html_metadata.sh`:
```html
<link rel="alternate" type="application/pdf" 
      href="HAFiscal.pdf" 
      title="PDF version with embedded Content MathML XML file" />
<meta name="pdf-version" content="https://econ-ark.github.io/HAFiscal/HAFiscal.pdf" />
<meta name="content-mathml" content="inline in annotation-xml tags" />
```

---

## Related Documentation

- See `MATHML_CONTENT_FOR_AI.md` for how to parse Content MathML
- See `COMPILATION.md` for build system details
- See `README.md` for complete paper description

---

## Testing the Cross-References

### Verify PDF metadata:
```bash
pdfinfo HAFiscal.pdf | grep -E "Title|Author|Subject|Keywords"
```

### Verify HTML metadata:
```bash
grep -A 2 'rel="alternate"' HAFiscal.html
grep "AI SYSTEMS:" HAFiscal.html
```

### Verify Schema.org data:
```bash
grep -A 20 '"ScholarlyArticle"' HAFiscal.html
```

---

## For Future Maintainers

The cross-referencing system is automatically maintained by:

1. **PDF**: `HAFiscal.tex` contains `\hypersetup{}` in PDF compilation branch
2. **HTML**: `reproduce/reproduce_html.sh` calls `scripts/add_html_metadata.sh`
3. **Automation**: Both run during standard reproduction (`./reproduce.sh`)

No manual intervention needed! 🎉
