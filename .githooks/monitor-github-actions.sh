#!/bin/bash
# Monitor GitHub Actions workflows after push
# Usage: ./monitor-github-actions.sh <branch> <commit_sha>

set -euo pipefail

BRANCH="${1:-}"
COMMIT_SHA="${2:-}"
TIMEOUT=600  # 10 minutes in seconds
POLL_INTERVAL=15  # Check every 15 seconds

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[GitHub Actions Monitor]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[GitHub Actions Monitor]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[GitHub Actions Monitor]${NC} $*"
}

log_error() {
    echo -e "${RED}[GitHub Actions Monitor]${NC} $*"
}

# Check if gh CLI is available
if ! command -v gh >/dev/null 2>&1; then
    log_error "GitHub CLI (gh) not found. Please install it:"
    log_error "  brew install gh"
    log_error "  gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status >/dev/null 2>&1; then
    log_error "Not authenticated with GitHub. Run: gh auth login"
    exit 1
fi

log_info "Monitoring GitHub Actions workflows for commit ${COMMIT_SHA:0:7} on branch '$BRANCH'"
log_info "Will report after 10 minutes or when workflows complete..."
echo ""

START_TIME=$(date +%s)
REPORTED_10MIN=false

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    # Get workflow runs for this commit
    RUNS=$(gh run list --commit "$COMMIT_SHA" --json status,conclusion,name,databaseId,url 2>/dev/null || echo "[]")
    
    if [ "$RUNS" = "[]" ] || [ -z "$RUNS" ]; then
        if [ $ELAPSED -gt 60 ]; then
            log_warning "No workflow runs found yet for commit ${COMMIT_SHA:0:7}"
            log_warning "Workflows may not have started. Continuing to monitor..."
        fi
    else
        # Parse status
        TOTAL=$(echo "$RUNS" | jq '. | length')
        IN_PROGRESS=$(echo "$RUNS" | jq '[.[] | select(.status == "in_progress" or .status == "queued")] | length')
        COMPLETED=$(echo "$RUNS" | jq '[.[] | select(.status == "completed")] | length')
        SUCCESSFUL=$(echo "$RUNS" | jq '[.[] | select(.conclusion == "success")] | length')
        FAILED=$(echo "$RUNS" | jq '[.[] | select(.conclusion == "failure")] | length')
        
        # Check if we should report at 10 minutes
        if [ $ELAPSED -ge $TIMEOUT ] && [ "$REPORTED_10MIN" = "false" ]; then
            REPORTED_10MIN=true
            log_warning "⏰ 10-minute status report:"
            echo ""
            echo "$RUNS" | jq -r '.[] | "  • \(.name): \(.status) \(if .conclusion then "(\(.conclusion))" else "" end)"'
            echo ""
            log_info "Summary: $COMPLETED/$TOTAL workflows completed"
            if [ "$IN_PROGRESS" -gt 0 ]; then
                log_info "Still running: $IN_PROGRESS workflow(s)"
                log_info "Continuing to monitor..."
                echo ""
            fi
        fi
        
        # Check if all workflows are complete
        if [ "$IN_PROGRESS" -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
            log_success "✅ All workflows completed!"
            echo ""
            echo "$RUNS" | jq -r '.[] | "  • \(.name): \(.conclusion) - \(.url)"'
            echo ""
            
            if [ "$FAILED" -gt 0 ]; then
                log_error "❌ $FAILED workflow(s) failed"
                exit 1
            else
                log_success "✅ All $TOTAL workflow(s) succeeded"
                exit 0
            fi
        fi
    fi
    
    # Timeout after 30 minutes total
    if [ $ELAPSED -gt 1800 ]; then
        log_warning "⏰ Monitor timeout after 30 minutes"
        log_warning "Workflows may still be running. Check GitHub for status."
        exit 0
    fi
    
    sleep $POLL_INTERVAL
done
