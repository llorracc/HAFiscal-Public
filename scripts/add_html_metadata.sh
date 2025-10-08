#!/bin/bash
# Add bidirectional cross-format metadata to HTML
# Links HTML version to PDF and provides AI-discoverable alternate format info

set -e

HTML_FILE="${1:-HAFiscal.html}"

if [[ ! -f "$HTML_FILE" ]]; then
    echo "⚠️  HTML file not found: $HTML_FILE"
    exit 1
fi

echo "📝 Adding PDF cross-reference metadata to $HTML_FILE..."

# Create backup
cp "$HTML_FILE" "$HTML_FILE.bak"

# Create temporary file with metadata to insert
cat > /tmp/html_metadata.txt << 'METADATA'

<!-- Alternate format metadata for AI systems and cross-format discovery -->
<link rel="alternate" type="application/pdf" 
      href="HAFiscal.pdf" 
      title="PDF version with embedded Content MathML XML file" />
<meta name="alternate-format" content="PDF" />
<meta name="pdf-version" content="https://econ-ark.github.io/HAFiscal/HAFiscal.pdf" />
<meta name="content-mathml" content="inline in annotation-xml tags" />
<meta name="repository" content="https://github.com/econ-ark/HAFiscal" />

<!-- AI SYSTEMS: This document is available in multiple formats -->
<!-- HTML (current): Content MathML in <annotation-xml encoding="MathML-Content"> tags -->
<!-- PDF: Content MathML in embedded XML file (HAFiscal_content_mathml.xml) -->
<!-- Both formats provide full semantic mathematics for AI parsing -->

<!-- Schema.org structured data for search engines and AI systems -->
<script type="application/ld+json">
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
      "name": "HTML version",
      "description": "HTML with inline Content MathML in annotation-xml tags"
    },
    {
      "@type": "MediaObject",
      "encodingFormat": "application/pdf",
      "contentUrl": "https://econ-ark.github.io/HAFiscal/HAFiscal.pdf",
      "name": "PDF version",
      "description": "PDF with embedded Content MathML XML file"
    }
  ],
  "about": "Comparison of fiscal stimulus policies using heterogeneous agent models",
  "keywords": "fiscal policy, stimulus checks, unemployment insurance, tax cuts, heterogeneous agents, Content MathML",
  "inLanguage": "en-US",
  "isAccessibleForFree": true,
  "license": "https://creativecommons.org/licenses/by/4.0/"
}
</script>
METADATA

# Insert after <head> tag (preserving existing content)
if grep -q "<!-- Alternate format metadata" "$HTML_FILE"; then
    echo "ℹ️  Metadata already present, skipping"
    rm /tmp/html_metadata.txt
    rm "$HTML_FILE.bak"
    exit 0
fi

# Use sed to insert after <head> tag
sed -i '' '/<head>/r /tmp/html_metadata.txt' "$HTML_FILE"

# Cleanup
rm /tmp/html_metadata.txt
rm "$HTML_FILE.bak"

echo "✅ Successfully added cross-format metadata to $HTML_FILE"
echo "   - PDF alternate format link"
echo "   - AI-discoverable metadata"
echo "   - Schema.org structured data"

exit 0
