#!/bin/bash

# reproduce_html.sh - Standalone HTML reproduction script
# Generated: 2025-09-25
# Purpose: Reproduce HAFiscal.html in docs/ directory using correct make4ht commands

set -e  # Exit on first error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 HAFiscal HTML Reproduction Script${NC}"
echo "Generated: $(date)"
echo ""

# Check prerequisites
if [[ ! -f "HAFiscal.tex" ]]; then
    echo -e "${RED}❌ Error: HAFiscal.tex not found in current directory${NC}"
    exit 1
fi

if [[ ! -f "HAFiscal.bib" ]]; then
    echo -e "${RED}❌ Error: HAFiscal.bib not found in current directory${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites verified${NC}"

# Clean auxiliary files (but preserve config files)
echo -e "${YELLOW}🧹 Cleaning auxiliary files...${NC}"
# List of auxiliary files to clean (FIXED: Do NOT delete configuration files)
aux_files=(
    "*.aux" "*.xref" "*.4tc" "*.4ct" "*.lg" "*.idv" "*.tmp" 
    "*.toc" "*.out" "*.log" "*.bbl" "*.blg" "*.dvi"
    "*.html"
)

for pattern in "${aux_files[@]}"; do
    if ls "$pattern" 1> /dev/null 2>&1; then
        echo "  Removing: $pattern"
        rm -f "$pattern"
    fi
done
echo -e "${GREEN}✓ Auxiliary files cleaned (config files preserved)${NC}"
echo ""

# Full LaTeX -> BibTeX -> LaTeX -> LaTeX cycle for complete HTML generation
echo -e "${BLUE}📝 Starting full HTML compilation cycle...${NC}"

# Pass 1: make4ht (generate HTML and identify citations)
echo -e "${YELLOW}Pass 1: Initial HTML conversion${NC}"
BUILD_MODE=LONG
latex_defs="\\\\newcommand\\\\BuildMode{$BUILD_MODE}"
cmd="make4ht HAFiscal.tex \"html,mathjax\" \"\" \"\" \"$latex_defs\" -a debug \"\" \"\" \"\" \"--interaction=nonstopmode\""
echo "🔧 Executing: $cmd"
if make4ht HAFiscal.tex "html,mathjax" "" "" "$latex_defs" -a debug "" "" "" "--interaction=nonstopmode" > make4ht_pass1.log 2>&1; then
    echo -e "${GREEN}✓ First pass completed successfully${NC}"
else
    echo -e "${RED}❌ First pass failed${NC}"
    echo "Check make4ht_pass1.log for details"
    exit 1
fi

# BibTeX pass: Process bibliography
echo -e "${YELLOW}Pass 2: Bibliography processing${NC}"
cmd="bibtex HAFiscal"
echo "🔧 Executing: $cmd"
if bibtex HAFiscal > bibtex.log 2>&1; then
    echo -e "${GREEN}✓ Bibliography processed successfully${NC}"
else
    echo -e "${YELLOW}⚠ BibTeX warnings (common for complex documents)${NC}"
    # BibTeX warnings are often non-fatal
fi

# Pass 3: make4ht (resolve citations)
echo -e "${YELLOW}Pass 3: Citation resolution${NC}"
cmd="make4ht HAFiscal.tex \"html,mathjax\" \"\" \"\" \"$latex_defs\" -a debug \"\" \"\" \"\" \"--interaction=nonstopmode\""
echo "🔧 Executing: $cmd"
if make4ht HAFiscal.tex "html,mathjax" "" "" "$latex_defs" -a debug "" "" "" "--interaction=nonstopmode" > make4ht_pass2.log 2>&1; then
    echo -e "${GREEN}✓ Citation resolution completed${NC}"
else
    echo -e "${RED}❌ Citation resolution failed${NC}"
    echo "Check make4ht_pass2.log for details"
    exit 1
fi

# Pass 4: make4ht (finalize cross-references)
echo -e "${YELLOW}Pass 4: Cross-reference finalization${NC}"
cmd="make4ht HAFiscal.tex \"html,mathjax\" \"\" \"\" \"$latex_defs\" -a debug \"\" \"\" \"\" \"--interaction=nonstopmode\""
echo "🔧 Executing: $cmd"
if make4ht HAFiscal.tex "html,mathjax" "" "" "$latex_defs" -a debug "" "" "" "--interaction=nonstopmode" > make4ht_pass3.log 2>&1; then
    echo -e "${GREEN}✓ Cross-reference finalization completed${NC}"
else
    echo -e "${RED}❌ Cross-reference finalization failed${NC}"
    echo "Check make4ht_pass3.log for details"
    exit 1
fi

# Copy to index.html for web serving
if [[ -f "HAFiscal.html" ]]; then
    cp HAFiscal.html index.html
    echo -e "${GREEN}✓ Created index.html${NC}"
fi

echo ""

# Add cross-format metadata linking HTML to PDF
echo -e "${BLUE}📝 Adding cross-format metadata...${NC}"
if [[ -f "./README_IF_YOU_ARE_AN_AI/add_html_metadata.sh" ]]; then
    bash ./README_IF_YOU_ARE_AN_AI/add_html_metadata.sh HAFiscal.html
else
    echo -e "${YELLOW}⚠️  Metadata script not found, skipping${NC}"
fi

echo -e "${GREEN}🎉 HTML reproduction completed successfully!${NC}"
echo -e "${BLUE}📊 Generated files:${NC}"
if ls HAFiscal*.html 1> /dev/null 2>&1; then
    echo "  HTML files: $(find . -maxdepth 1 -name 'HAFiscal*.html' -type f | wc -l | tr -d ' ')"
fi
echo "  Main document: HAFiscal.html"
echo "  Web index: index.html"
echo "  CSS styling: HAFiscal.css ($(wc -c < HAFiscal.css 2>/dev/null || echo 'N/A') bytes)"
echo ""
echo -e "${BLUE}✅ Reproduction complete. The HTML should look identical to the original build.${NC}" 