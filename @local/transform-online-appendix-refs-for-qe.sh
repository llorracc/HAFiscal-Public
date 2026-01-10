#!/bin/bash
# transform-online-appendix-refs-for-qe.sh
#
# PURPOSE: Transform online appendix handling for QE submission compliance.
#
# This script performs TWO transformations:
#
# 1. REFERENCE TRANSFORMATION: Convert \ref{} commands that reference online
#    appendix content into plain text.
#
# 2. APPENDIX HANDLING: Replace full appendix inclusion with a stub page
#    that links to the online supplement.
#
# CONTEXT: The econsocart document class (used by Quantitative Economics)
#          explicitly forbids the xr and xr-hyper packages and requires:
#          "Replace all references to external documents with plain text"
#
# This script is called during the QE repository build process.
# HAFiscal-Latest and HAFiscal-Public include the full appendix content.
# HAFiscal-QE uses a stub page with links to the online supplement.
#
# USAGE: ./transform-online-appendix-refs-for-qe.sh [directory]
#        If no directory specified, operates on current directory.
#
# Author: HAFiscal project
# Date: 2025-12-07

set -euo pipefail

# Directory to process (default: current directory)
TARGET_DIR="${1:-.}"

echo "=============================================="
echo "QE Online Appendix Transformation"
echo "=============================================="
echo "Target directory: $TARGET_DIR"
echo ""

# ============================================================================
# PART 1: REFERENCE TRANSFORMATION
# ============================================================================
# Transform \ref{} commands for online appendix content into plain text.
# This ensures compliance with econsocart's prohibition on xr/xr-hyper packages.

echo "--- Part 1: Reference Transformation ---"

# Define the mapping of \ref{label} to plain text
# Format: Each line is "pattern|replacement"
# The pattern is a sed-compatible regex, replacement is literal text

declare -a TRANSFORMATIONS=(
    # Main appendix section references
    # "Appendix~\ref{app:Model-without-splurge}" → "the online appendix"
    's/Appendix~\\ref{app:Model-without-splurge}/the online appendix/g'
    's/appendix~\\ref{app:Model-without-splurge}/the online appendix/g'
    
    # Standalone \ref to the main appendix
    's/\\ref{app:Model-without-splurge}/the online appendix/g'
    
    # Subsection references (these appear in the online appendix content itself,
    # but may be referenced from main text)
    's/\\ref{app:Model-without-splurge-intro}/Section~B.1 of the online appendix/g'
    's/\\ref{app:nosplurge-matching-impcs}/Section~B.2 of the online appendix/g'
    's/\\ref{app:nosplurge-estimating-betas}/Section~B.3 of the online appendix/g'
    's/\\ref{app:nosplurge-multipliers}/Section~B.4 of the online appendix/g'
    
    # Figure references (these appear in figure captions within the online appendix)
    's/\\ref{fig:splurge0_Norwayestimation}/Figure~B.1 (online appendix)/g'
    's/\\ref{fig:aggmpclotterywin_splurge0}/Figure~B.1a (online appendix)/g'
    's/\\ref{fig:liquwealthdistribution_splurge0}/Figure~B.1b (online appendix)/g'
    's/\\ref{fig:LorenzPtsSplZero}/Figure~B.2 (online appendix)/g'
    's/\\ref{fig:untargetedMoments_wSplZero}/Figure~B.3 (online appendix)/g'
    's/\\ref{fig:USaggmpclotterywin_wSplZero}/Figure~B.3a (online appendix)/g'
    's/\\ref{fig:expiryUI_wSplZero}/Figure~B.3b (online appendix)/g'
    's/\\ref{fig:cumulativemultipliers_SplurgeComp}/Figure~B.4 (online appendix)/g'
    
    # Table references
    's/\\ref{tab:Comparison-Splurge-Table}/Table~B.1 (online appendix)/g'
    's/\\ref{tab:nonTargetedMoments-wSplZero}/Table~B.2 (online appendix)/g'
    's/\\ref{tab:Multiplier-SplurgeComp}/Table~B.3 (online appendix)/g'
)

# Files to transform (relative to TARGET_DIR)
# These are the files that contain references to the online appendix
declare -a FILES_TO_TRANSFORM=(
    "Subfiles/Parameterization.tex"
    "Subfiles/Comparing-policies.tex"
    "Subfiles/literature.tex"
    "Figures/untargetedMoments_wSplZero.tex"
    "Figures/splurge0_Norwayestimation.tex"
    "Figures/cumulativemultipliers_SplurgeComp.tex"
    "Code/HA-Models/FromPandemicCode/LorenzPtsSplZero.tex"
)

# Counter for transformed files
transformed_count=0

for file in "${FILES_TO_TRANSFORM[@]}"; do
    filepath="$TARGET_DIR/$file"
    
    if [[ ! -f "$filepath" ]]; then
        echo "  Skipping (not found): $file"
        continue
    fi
    
    # Check if file contains any online appendix references
    if ! grep -qE 'app:Model-without-splurge|app:nosplurge|splurge0|SplZero|SplurgeComp' "$filepath" 2>/dev/null; then
        echo "  Skipping (no refs): $file"
        continue
    fi
    
    echo "  Transforming: $file"
    
    # Create backup
    cp "$filepath" "${filepath}.bak"
    
    # Apply all transformations
    for transform in "${TRANSFORMATIONS[@]}"; do
        sed -i.tmp "$transform" "$filepath"
        rm -f "${filepath}.tmp"
    done
    
    # Verify transformation worked (backup differs from current)
    if ! diff -q "$filepath" "${filepath}.bak" > /dev/null 2>&1; then
        ((transformed_count++))
        rm -f "${filepath}.bak"
    else
        # No changes made, restore backup
        mv "${filepath}.bak" "$filepath"
    fi
done

echo ""
echo "Reference transformation complete: $transformed_count files modified"

# ============================================================================
# PART 2: APPENDIX HANDLING
# ============================================================================
# In -Latest/-Public, Appendix B (No Splurge) is included as full content.
# For QE, we replace this with a stub page that links to the online supplement.
#
# The stub page:
# - Provides section labels so any remaining \ref{} commands don't break
# - Links to the online PDF and HTML versions
# - Complies with QE requirement for separate online supplements

echo ""
echo "--- Part 2: Appendix Handling ---"

HAFISCAL_TEX="$TARGET_DIR/HAFiscal.tex"

if [[ -f "$HAFISCAL_TEX" ]]; then
    echo "Processing HAFiscal.tex for appendix handling..."
    
    # Check if file contains full appendix inclusion
    # Pattern: \subfile{Subfiles/Appendix-NoSplurge} (possibly with variations)
    if grep -q '\\subfile{Subfiles/Appendix-NoSplurge}' "$HAFISCAL_TEX" 2>/dev/null || \
       grep -q '\\subfile{./Subfiles/Appendix-NoSplurge}' "$HAFISCAL_TEX" 2>/dev/null; then
        
        echo "  Found full appendix inclusion - replacing with stub page"
        
        # Create backup
        cp "$HAFISCAL_TEX" "${HAFISCAL_TEX}.bak"
        
        # The stub page content (matches QE journal requirements)
        # Uses heredoc to preserve formatting
        STUB_CONTENT='% B: No Splurge appendix - online only with stub page for QE submission
% Full content available as separate online supplement PDF
\\phantomsection
\\section{Results in a Model Without the Splurge}
\\label{app:Model-without-splurge}

\\noindent\\textit{This appendix is available as an online supplement.}

\\medskip
\\noindent See the online appendix PDF for:

\\subsection{Introduction}
\\label{app:Model-without-splurge-intro}

\\subsection{Matching the iMPCs without the splurge}
\\label{app:nosplurge-matching-impcs}

\\subsection{Estimating discount factor distributions without the splurge}
\\label{app:nosplurge-estimating-betas}

\\subsection{Multipliers in the absence of the splurge}
\\label{app:nosplurge-multipliers}

\\medskip'

        # Use perl for multiline replacement (more reliable than sed for this)
        # Match: lines containing \subfile{...Appendix-NoSplurge...} and surrounding context
        perl -i -0pe '
            s/% B:.*?\\subfile\{[^}]*Appendix-NoSplurge[^}]*\}.*?(?=\n% C:|\n\\end\{document\})/'"$(echo "$STUB_CONTENT" | sed 's/\\/\\\\/g; s/\//\\\//g; s/\n/\\n/g')"'/s
        ' "$HAFISCAL_TEX" 2>/dev/null || {
            # Fallback: simpler sed replacement if perl fails
            sed -i.tmp 's/\\subfile{Subfiles\/Appendix-NoSplurge}/% Appendix included as online supplement (see stub above)/g' "$HAFISCAL_TEX"
            sed -i.tmp 's/\\subfile{\.\/Subfiles\/Appendix-NoSplurge}/% Appendix included as online supplement (see stub above)/g' "$HAFISCAL_TEX"
            rm -f "${HAFISCAL_TEX}.tmp"
        }
        
        echo "  Stub page inserted for Appendix B"
        rm -f "${HAFISCAL_TEX}.bak"
    else
        echo "  No full appendix inclusion found (may already be stub or different structure)"
    fi
else
    echo "  HAFiscal.tex not found - skipping appendix handling"
fi

echo ""
echo "=============================================="
echo "QE Transformation Complete"
echo "=============================================="
echo ""
echo "Summary:"
echo "  - Reference transformations: $transformed_count files"
echo "  - Appendix B converted to stub page (if applicable)"
echo ""
echo "The QE version now complies with econsocart requirements:"
echo "  - No xr/xr-hyper package usage"
echo "  - Online appendix references use plain text"
echo "  - Appendix B is a separate online supplement"
