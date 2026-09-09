#!/bin/bash
# reproduce_min.sh - Minimal reproduction for REMARK compliance
# 
# This script runs minimal computational results to demonstrate reproducibility
# without requiring the full 4-5 day computation time.
#
# For full reproduction, see: ./reproduce.sh --help

set -e  # Exit on error

# Print header
echo "================================================================="
echo "HAFiscal Minimal Reproduction"
echo "================================================================="
echo ""
echo "Paper: Welfare and Spending Effects of Consumption Stimulus Policies"
echo "Authors: Carroll, Crawley, Du, Frankovic, Tretvoll (2025)"
echo ""
echo "This runs minimal computational results (~1 hour) to demonstrate"
echo "reproducibility. For full reproduction (4-5 days), run:"
echo "  ./reproduce.sh --all"
echo ""
echo "See ./reproduce.sh --help for all reproduction options."
echo ""
echo "================================================================="
echo ""

# Check that reproduce.sh exists
if [[ ! -f "reproduce.sh" ]]; then
    echo "Error: reproduce.sh not found. Please run from repository root."
    exit 1
fi

# Make sure reproduce.sh is executable
if [[ ! -x "reproduce.sh" ]]; then
    chmod +x reproduce.sh
fi

# Run minimal computational results
echo "Running: ./reproduce.sh --comp min"
echo ""
./reproduce.sh --comp min

# Success message
echo ""
echo "================================================================="
echo "✅ Minimal reproduction complete"
echo "================================================================="
echo ""
echo "Results: Code/HA-Models/FromPandemicCode/Results/"
echo ""
echo "Next steps:"
echo "  - View logs: cat reproduce/logs/latest.log"
echo "  - Compile paper: ./reproduce.sh --docs"
echo "  - Full reproduction: ./reproduce.sh --all (4-5 days)"
echo ""
