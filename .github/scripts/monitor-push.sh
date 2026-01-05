#!/bin/bash
# Monitor all GitHub Actions workflows triggered by a push
# This script launches background monitors for each workflow

set -e

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor-workflow.sh"

# Get current git info
BRANCH=$(git branch --show-current)
COMMIT_SHA=$(git rev-parse HEAD)
SHORT_SHA="${COMMIT_SHA:0:7}"

echo -e "${BLUE}🚀 GitHub Actions Monitor${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌿 Branch: $BRANCH"
echo "📝 Commit: $SHORT_SHA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Send startup announcement
echo -e "${GREEN}🚀 GitHub Actions monitor started!${NC}"
echo ""

# macOS notification for startup
if command -v osascript &> /dev/null; then
    osascript -e "display notification \"Starting workflow monitoring for $BRANCH\" with title \"GitHub Actions Monitor 🚀\" sound name \"Glass\"" 2>/dev/null || true
fi

# Terminal bell for startup
echo -e "\a"

# Voice announcement for startup
if command -v say &> /dev/null; then
    say "GitHub Actions monitor started for branch $BRANCH" &
fi

# Create logs directory
LOG_DIR="/tmp/github-actions-monitor-$$"
mkdir -p "$LOG_DIR"

echo -e "${GREEN}📊 Starting workflow monitors...${NC}"
echo ""

# Monitor PDF Build Workflow
echo -e "1️⃣  ${YELLOW}Monitoring: Push Document Build (PDF)${NC}"
PDF_LOG="$LOG_DIR/pdf-build.log"
nohup bash "$MONITOR_SCRIPT" "Push Document Build" "$BRANCH" "$COMMIT_SHA" 20 > "$PDF_LOG" 2>&1 &
PDF_PID=$!
echo "   Process ID: $PDF_PID"
echo "   Log file: $PDF_LOG"
echo ""

# Monitor LaTeX Test Workflow  
echo -e "2️⃣  ${YELLOW}Monitoring: Test LaTeX Compilation${NC}"
LATEX_LOG="$LOG_DIR/latex-test.log"
nohup bash "$MONITOR_SCRIPT" "Test LaTeX Document Compilation" "$BRANCH" "$COMMIT_SHA" 20 > "$LATEX_LOG" 2>&1 &
LATEX_PID=$!
echo "   Process ID: $LATEX_PID"
echo "   Log file: $LATEX_LOG"
echo ""

# Check if there were docs changes for GitHub Pages
DOCS_CHANGED=false
if git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -q '^docs/'; then
    DOCS_CHANGED=true
    echo -e "3️⃣  ${YELLOW}Monitoring: GitHub Pages Deployment${NC}"
    echo "   (Triggered by changes in docs/)"
    PAGES_LOG="$LOG_DIR/github-pages.log"
    # Note: Pages deployment happens within the push-build-docs workflow
    echo "   Monitoring via PDF Build workflow"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Monitors launched successfully!${NC}"
echo ""
echo "📁 Monitor logs are in: $LOG_DIR"
echo ""
echo -e "${BLUE}📋 Useful Commands:${NC}"
echo ""
echo "  # View PDF build log:"
echo "  tail -f $PDF_LOG"
echo ""
echo "  # View LaTeX test log:"
echo "  tail -f $LATEX_LOG"
echo ""
echo "  # View all logs:"
echo "  tail -f $LOG_DIR/*.log"
echo ""
echo "  # Stop all monitors:"
echo "  kill $PDF_PID $LATEX_PID"
echo ""
echo "  # Check monitor status:"
echo "  ps -p $PDF_PID $LATEX_PID"
echo ""

# Create a summary script for easy access
SUMMARY_SCRIPT="$LOG_DIR/show-status.sh"
cat > "$SUMMARY_SCRIPT" << EOF
#!/bin/bash
# Quick status check for GitHub Actions monitors

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "GitHub Actions Monitor Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if processes are still running
if ps -p $PDF_PID > /dev/null 2>&1; then
    echo "✅ PDF Build Monitor: Running (PID: $PDF_PID)"
else
    echo "🏁 PDF Build Monitor: Completed"
fi

if ps -p $LATEX_PID > /dev/null 2>&1; then
    echo "✅ LaTeX Test Monitor: Running (PID: $LATEX_PID)"
else
    echo "🏁 LaTeX Test Monitor: Completed"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Recent Log Output:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📄 PDF Build (last 5 lines):"
tail -5 "$PDF_LOG" 2>/dev/null || echo "  No output yet"
echo ""

echo "📄 LaTeX Test (last 5 lines):"
tail -5 "$LATEX_LOG" 2>/dev/null || echo "  No output yet"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Commands:"
echo "  tail -f $PDF_LOG    # Follow PDF build"
echo "  tail -f $LATEX_LOG  # Follow LaTeX test"
echo "  kill $PDF_PID $LATEX_PID  # Stop monitors"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
EOF
chmod +x "$SUMMARY_SCRIPT"

echo -e "${GREEN}💡 Tip: Run this command to check status:${NC}"
echo "  $SUMMARY_SCRIPT"
echo ""

# Save PIDs and info for cleanup
INFO_FILE="$LOG_DIR/monitor-info.txt"
cat > "$INFO_FILE" << EOF
PDF_PID=$PDF_PID
LATEX_PID=$LATEX_PID
PDF_LOG=$PDF_LOG
LATEX_LOG=$LATEX_LOG
BRANCH=$BRANCH
COMMIT_SHA=$COMMIT_SHA
SHORT_SHA=$SHORT_SHA
LOG_DIR=$LOG_DIR
SUMMARY_SCRIPT=$SUMMARY_SCRIPT
EOF

echo -e "${BLUE}ℹ️  Monitor info saved to: $INFO_FILE${NC}"
echo ""

# Optionally watch logs (uncomment to enable auto-watching)
# echo -e "${YELLOW}👀 Watching logs... (Ctrl+C to stop)${NC}"
# tail -f "$LOG_DIR"/*.log

