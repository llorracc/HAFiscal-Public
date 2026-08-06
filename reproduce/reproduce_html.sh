#!/bin/bash

# reproduce_html.sh - Standalone HTML reproduction script
# Generated: 2025-09-25
# Purpose: Reproduce HAFiscal.html using the correct make4ht commands.
#
# RUN FROM: the repo root. The prerequisite checks below look for HAFiscal.tex
# and HAFiscal.bib in the current directory.
#
# OUTPUT LOCATION: the repo ROOT -- not docs/, which this header claimed until
# 2026-08-03 without ever matching behaviour. make4ht writes beside the source,
# and the generated pages reference HAFiscal.css and images/ by relative path,
# so relocating the output would need a link-rewriting step rather than a move.
# The root-level artifacts are gitignored; see the /HAFiscal*.html block in
# .gitignore.

set -e  # Exit on first error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Document base name. Everything this script deletes or preserves is scoped to
# it, so a run cannot disturb HAFiscal-Slides or any other root document.
DOC="HAFiscal"

# Artifacts the PDF pipeline owns which a tex4ht run would otherwise rewrite:
#   .dep  snapshot manifest -- tex4ht records ITS toolchain over pdfTeX's
#   .aux  rewritten by every htlatex pass
#   .bbl  rewritten by the bibtex pass below
#   .toc/.out  rewritten alongside .aux
# They are saved before the build and restored on exit (success OR failure), so
# a later PDF build starts from the same state it would have without this run.
PRESERVE_EXTS=(dep aux bbl toc out)
PRESERVE_DIR=""

preserve_pdf_state() {
    PRESERVE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/${DOC}-pdfstate.XXXXXX")"
    local ext
    for ext in "${PRESERVE_EXTS[@]}"; do
        if [[ -f "${DOC}.${ext}" ]]; then
            cp "${DOC}.${ext}" "$PRESERVE_DIR/"
        fi
    done
    return 0
}

restore_pdf_state() {
    if [[ -z "$PRESERVE_DIR" || ! -d "$PRESERVE_DIR" ]]; then
        return 0
    fi
    local ext
    local restored=()
    for ext in "${PRESERVE_EXTS[@]}"; do
        if [[ -f "$PRESERVE_DIR/${DOC}.${ext}" ]]; then
            cp "$PRESERVE_DIR/${DOC}.${ext}" "${DOC}.${ext}"
            restored+=("${DOC}.${ext}")
        fi
    done
    rm -rf "$PRESERVE_DIR"
    PRESERVE_DIR=""
    if [[ ${#restored[@]} -gt 0 ]]; then
        echo -e "${GREEN}✓ Restored PDF-pipeline state: ${restored[*]}${NC}"
    fi
    return 0
}
trap restore_pdf_state EXIT

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

preserve_pdf_state
echo -e "${GREEN}✓ Preserved PDF-pipeline state (${PRESERVE_EXTS[*]}) for restore on exit${NC}"

# Clean stale tex4ht output so a rerun cannot inherit a half-built page set.
echo -e "${YELLOW}🧹 Cleaning tex4ht artifacts...${NC}"
# Two bugs fixed here on 2026-08-03:
#   1. The patterns were bare globs (*.aux, *.log, *.bbl, *.toc, *.out, *.dvi,
#      *.html) covering EVERY document in the repo root, not just this one.
#   2. They were quoted at the point of use -- `ls "*.aux"` tests for a file
#      literally named "*.aux", so the guard never passed and `rm -f "*.aux"`
#      never matched. The loop had silently deleted nothing since it was
#      written. Fixing (2) without (1) would have made it destructive.
# Scope is now this document's tex4ht-owned outputs only. Files shared with the
# PDF pipeline (.aux/.bbl/.toc/.out/.dep) are deliberately absent: make4ht and
# bibtex regenerate what they need, and preserve/restore protects the rest.
aux_files=(
    "${DOC}.4ct" "${DOC}.4tc" "${DOC}.xref" "${DOC}.lg"
    "${DOC}.idv" "${DOC}.tmp" "${DOC}.dvi" "${DOC}.css"
    "${DOC}*.html" "index.html"
)

for pattern in "${aux_files[@]}"; do
    if compgen -G "$pattern" > /dev/null; then
        echo "  Removing: $pattern"
        # shellcheck disable=SC2086  # unquoted on purpose: the glob must expand
        rm -f $pattern
    fi
done
echo -e "${GREEN}✓ tex4ht artifacts cleaned (scoped to ${DOC}; other documents untouched)${NC}"
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
echo "  Output directory: $(pwd)"
echo "                    (the repo root -- NOT docs/; see header note)"
echo "  Main document: HAFiscal.html"
echo "  Web index: index.html"
echo "  CSS styling: HAFiscal.css ($(wc -c < HAFiscal.css 2>/dev/null || echo 'N/A') bytes)"
echo ""
echo -e "${BLUE}✅ Reproduction complete. The HTML should look identical to the original build.${NC}" 