#!/bin/bash
# Git push wrapper that automatically monitors GitHub Actions workflows
# Usage: ./git-push-with-monitor.sh [git push options]

set -e

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor-push.sh"

echo -e "${BLUE}🚀 Git Push with Workflow Monitoring${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Send startup announcement
echo -e "${GREEN}🚀 GitHub Actions monitor starting up...${NC}"
echo ""

# macOS notification for startup
if command -v osascript &> /dev/null; then
    osascript -e "display notification \"Preparing to push and monitor workflows\" with title \"GitHub Actions Monitor 🚀\" sound name \"Glass\"" 2>/dev/null || true
fi

# Terminal bell for startup
echo -e "\a"

# Voice announcement for startup
if command -v say &> /dev/null; then
    say "Preparing to push and monitor GitHub Actions workflows" &
fi

# Perform the git push
echo -e "${YELLOW}📤 Pushing to remote...${NC}"
echo ""

if git push "$@"; then
    echo ""
    echo -e "${GREEN}✅ Push successful!${NC}"
    echo ""
    
    # Launch monitors
    echo -e "${BLUE}🔍 Launching workflow monitors...${NC}"
    echo ""
    
    bash "$MONITOR_SCRIPT"
    
    echo ""
    echo -e "${GREEN}✨ Done! Monitors are running in the background.${NC}"
    echo -e "${BLUE}💡 You'll get macOS notifications when workflows complete.${NC}"
    
else
    echo ""
    echo -e "${RED}❌ Push failed!${NC}"
    echo "Workflow monitors were not started."
    exit 1
fi

