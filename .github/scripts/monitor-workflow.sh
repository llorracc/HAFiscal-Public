#!/bin/bash
# GitHub Actions Workflow Monitor
# Monitors a specific workflow run and reports when it completes

# Usage: monitor-workflow.sh <workflow-name> <branch> <commit-sha> [poll-interval]

set -e

WORKFLOW_NAME="${1:-}"
BRANCH="${2:-$(git branch --show-current)}"
COMMIT_SHA="${3:-$(git rev-parse HEAD)}"
POLL_INTERVAL="${4:-20}"  # seconds

if [ -z "$WORKFLOW_NAME" ]; then
    echo "❌ Error: Workflow name is required"
    echo "Usage: $0 <workflow-name> [branch] [commit-sha] [poll-interval]"
    exit 1
fi

# Color codes for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

echo -e "${BLUE}🔍 Monitoring GitHub Actions Workflow${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Repository: $REPO"
echo "🏷️  Workflow: $WORKFLOW_NAME"
echo "🌿 Branch: $BRANCH"
echo "📝 Commit: ${COMMIT_SHA:0:7}"
echo "⏱️  Poll interval: ${POLL_INTERVAL}s"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Send startup announcement
echo -e "${GREEN}🚀 GitHub Actions monitor started!${NC}"
echo ""

# macOS notification for startup
if command -v osascript &> /dev/null; then
    osascript -e "display notification \"Monitoring $WORKFLOW_NAME workflow\" with title \"GitHub Actions Monitor 🚀\" sound name \"Glass\"" 2>/dev/null || true
fi

# Terminal bell for startup
echo -e "\a"

# Voice announcement for startup
if command -v say &> /dev/null; then
    say "GitHub Actions monitor started for $WORKFLOW_NAME" &
fi

# Function to get the latest run for this workflow and commit
get_latest_run() {
    gh run list \
        --workflow "$WORKFLOW_NAME" \
        --branch "$BRANCH" \
        --limit 10 \
        --json databaseId,status,conclusion,headSha,createdAt,url,displayTitle \
        --jq "[.[] | select(.headSha == \"$COMMIT_SHA\")] | .[0]" 2>/dev/null || echo ""
}

# Wait for the workflow run to appear (GitHub may take a few seconds)
echo -e "${YELLOW}⏳ Waiting for workflow to start...${NC}"
MAX_WAIT=60  # Wait up to 60 seconds for workflow to appear
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    RUN_DATA=$(get_latest_run)
    
    if [ -n "$RUN_DATA" ]; then
        echo -e "${GREEN}✅ Workflow run detected!${NC}"
        break
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo -n "."
done

echo ""

if [ -z "$RUN_DATA" ]; then
    echo -e "${RED}❌ Workflow run not found after ${MAX_WAIT}s${NC}"
    echo "This could mean:"
    echo "  • The workflow is not triggered for this branch"
    echo "  • The workflow has path filters that exclude your changes"
    echo "  • GitHub Actions is experiencing delays"
    echo ""
    echo "Check manually: https://github.com/$REPO/actions"
    exit 1
fi

# Extract run details
RUN_ID=$(echo "$RUN_DATA" | jq -r '.databaseId')
RUN_URL=$(echo "$RUN_DATA" | jq -r '.url')
RUN_TITLE=$(echo "$RUN_DATA" | jq -r '.displayTitle')

echo -e "${BLUE}📊 Run Details:${NC}"
echo "  ID: $RUN_ID"
echo "  Title: $RUN_TITLE"
echo "  URL: $RUN_URL"
echo ""
echo -e "${YELLOW}⏳ Monitoring workflow progress...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Monitor the workflow run
LAST_STATUS=""
START_TIME=$(date +%s)

while true; do
    # Get current run status
    RUN_INFO=$(gh run view "$RUN_ID" --json status,conclusion,url,displayTitle 2>/dev/null || echo "")
    
    if [ -z "$RUN_INFO" ]; then
        echo -e "${RED}❌ Failed to fetch run status${NC}"
        sleep "$POLL_INTERVAL"
        continue
    fi
    
    STATUS=$(echo "$RUN_INFO" | jq -r '.status')
    CONCLUSION=$(echo "$RUN_INFO" | jq -r '.conclusion')
    
    # Show status updates
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        CURRENT_TIME=$(date +%s)
        ELAPSED_TIME=$((CURRENT_TIME - START_TIME))
        ELAPSED_MIN=$((ELAPSED_TIME / 60))
        ELAPSED_SEC=$((ELAPSED_TIME % 60))
        
        case "$STATUS" in
            "queued")
                echo -e "⏸️  [${ELAPSED_MIN}m ${ELAPSED_SEC}s] Workflow queued..."
                ;;
            "in_progress")
                echo -e "🔄 [${ELAPSED_MIN}m ${ELAPSED_SEC}s] Workflow running..."
                ;;
            "completed")
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                case "$CONCLUSION" in
                    "success")
                        echo -e "${GREEN}✅ WORKFLOW COMPLETED SUCCESSFULLY!${NC}"
                        echo -e "🎉 Status: Success"
                        ;;
                    "failure")
                        echo -e "${RED}❌ WORKFLOW FAILED!${NC}"
                        echo -e "💥 Status: Failure"
                        ;;
                    "cancelled")
                        echo -e "${YELLOW}⚠️  WORKFLOW CANCELLED${NC}"
                        echo -e "🚫 Status: Cancelled"
                        ;;
                    "skipped")
                        echo -e "${YELLOW}⏭️  WORKFLOW SKIPPED${NC}"
                        echo -e "⏩ Status: Skipped"
                        ;;
                    *)
                        echo -e "${YELLOW}⚠️  WORKFLOW COMPLETED${NC}"
                        echo -e "📊 Status: $CONCLUSION"
                        ;;
                esac
                
                echo "⏱️  Duration: ${ELAPSED_MIN}m ${ELAPSED_SEC}s"
                echo "🔗 View details: $RUN_URL"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                
                # Multi-method notifications
                
                # Method 1: macOS Notification Center (if permissions allow)
                if command -v osascript &> /dev/null; then
                    case "$CONCLUSION" in
                        "success")
                            osascript -e "display notification \"$WORKFLOW_NAME completed successfully\" with title \"GitHub Actions ✅\" sound name \"Glass\"" 2>/dev/null || true
                            ;;
                        "failure")
                            osascript -e "display notification \"$WORKFLOW_NAME failed\" with title \"GitHub Actions ❌\" sound name \"Basso\"" 2>/dev/null || true
                            ;;
                        *)
                            osascript -e "display notification \"$WORKFLOW_NAME: $CONCLUSION\" with title \"GitHub Actions\" sound name \"Pop\"" 2>/dev/null || true
                            ;;
                    esac
                fi
                
                # Method 1b: Audio file playback (always works, no permissions needed)
                case "$CONCLUSION" in
                    "success")
                        afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &
                        ;;
                    "failure")
                        afplay /System/Library/Sounds/Basso.aiff 2>/dev/null &
                        ;;
                    *)
                        afplay /System/Library/Sounds/Pop.aiff 2>/dev/null &
                        ;;
                esac
                
                # Method 2: Terminal bell (always works)
                echo -e "\a"  # Bell sound
                
                # Method 3: Voice announcement (macOS text-to-speech)
                if command -v say &> /dev/null; then
                    case "$CONCLUSION" in
                        "success")
                            say "GitHub Actions workflow completed successfully" &
                            ;;
                        "failure")
                            say "GitHub Actions workflow failed" &
                            ;;
                    esac
                fi
                
                # Method 4: Visual separator for log scanning
                echo ""
                echo "🔔🔔🔔 WORKFLOW COMPLETED - CHECK ABOVE FOR DETAILS 🔔🔔🔔"
                echo ""
                
                # Open URL in browser (optional, commented out by default)
                # open "$RUN_URL"
                
                exit 0
                ;;
        esac
        
        LAST_STATUS="$STATUS"
    else
        # Show progress dots
        echo -n "."
    fi
    
    sleep "$POLL_INTERVAL"
done

