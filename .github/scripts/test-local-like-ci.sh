#!/bin/bash
# Local CI Testing Script
# Mimics the GitHub Actions environment for local testing
# Run this to test your changes before pushing

set -e

echo "🧪 =================================================="
echo "   Testing Like GitHub Actions CI (Local)"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# === Check Prerequisites ===
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

if ! command -v pdflatex &> /dev/null; then
    echo -e "${RED}❌ pdflatex not found. Please install TeX Live.${NC}"
    exit 1
fi

if ! command -v latexmk &> /dev/null; then
    echo -e "${RED}❌ latexmk not found. Please install latexmk.${NC}"
    exit 1
fi

if ! command -v bibtex &> /dev/null; then
    echo -e "${RED}❌ bibtex not found. Please install BibTeX.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites found${NC}"
echo ""

# === Set up Environment (mimic GitHub Actions) ===
echo -e "${BLUE}🔧 Setting up environment (mimicking GitHub Actions)...${NC}"

# Set TEXINPUTS like GitHub Actions does
export TEXINPUTS="${PWD}/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS:-}"
echo "TEXINPUTS=${TEXINPUTS}"

# Set LaTeX options like GitHub Actions
export LATEX_OPTS="-interaction=nonstopmode"
export LATEX_INTERACTION_MODE="nonstopmode"

echo -e "${GREEN}✅ Environment configured${NC}"
echo ""

# === Verify LaTeX Installation ===
echo -e "${BLUE}🔍 Verifying LaTeX installation...${NC}"
echo "pdflatex version:"
pdflatex --version | head -2
echo ""
echo "bibtex version:"
bibtex --version | head -1
echo ""
echo "latexmk version:"
latexmk --version | head -1
echo ""

# === Build PDFs (exactly like GitHub Actions) ===
echo -e "${BLUE}🏗️  Building PDFs (like GitHub Actions)...${NC}"
echo ""

if [ ! -f "reproduce/reproduce_documents.sh" ]; then
    echo -e "${RED}❌ reproduce/reproduce_documents.sh not found${NC}"
    exit 1
fi

# Run the same command GitHub Actions runs
bash reproduce/reproduce_documents.sh

BUILD_EXIT_CODE=$?

echo ""
if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ PDF build completed successfully${NC}"
else
    echo -e "${RED}❌ PDF build failed (exit code: $BUILD_EXIT_CODE)${NC}"
    echo ""
    echo -e "${YELLOW}💡 Check the logs above for errors${NC}"
    exit $BUILD_EXIT_CODE
fi

# === Check Generated PDFs ===
echo ""
echo -e "${BLUE}📄 Checking generated PDFs...${NC}"

EXPECTED_PDFS=("HAFiscal.pdf" "HAFiscal-Slides.pdf")
ALL_FOUND=true

for pdf in "${EXPECTED_PDFS[@]}"; do
    if [ -f "$pdf" ]; then
        SIZE=$(stat -f"%z" "$pdf" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✅ $pdf${NC} ($SIZE)"
    else
        echo -e "${YELLOW}⚠️  $pdf not found${NC}"
        ALL_FOUND=false
    fi
done

# === Check for Critical LaTeX Errors ===
echo ""
echo -e "${BLUE}🔍 Checking for critical LaTeX errors...${NC}"

if ls ./*.log 1> /dev/null 2>&1; then
    CRITICAL_ERRORS=$(grep -i "! LaTeX Error\|! Emergency stop\|! Fatal error" ./*.log || true)
    
    if [ -n "$CRITICAL_ERRORS" ]; then
        echo -e "${RED}❌ Critical LaTeX errors found:${NC}"
        echo "$CRITICAL_ERRORS"
        exit 1
    else
        echo -e "${GREEN}✅ No critical LaTeX errors found${NC}"
    fi
    
    # Count warnings (informational)
    WARNING_COUNT=$(grep -c "LaTeX Warning\|Package.*Warning" ./*.log || echo "0")
    echo -e "ℹ️  LaTeX warnings: $WARNING_COUNT (warnings are generally OK)"
else
    echo "No log files to check"
fi

# === Final Summary ===
echo ""
echo "=================================================="
echo -e "${GREEN}🎉 LOCAL CI TEST: SUCCESS${NC}"
echo "=================================================="
echo ""
echo "Your changes should work in GitHub Actions! ✅"
echo ""
echo "Next steps:"
echo "  1. Review any warnings above (usually safe to ignore)"
echo "  2. Commit your changes: git commit -am 'Your message'"
echo "  3. Push: git push"
echo ""
echo "If GitHub Actions still fails, compare this output"
echo "with the GitHub Actions logs to find differences."
echo ""

exit 0
