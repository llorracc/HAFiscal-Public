# GitHub Actions Workflow Monitors

This directory contains scripts to monitor GitHub Actions workflows in the background after pushing code.

## 📋 Scripts

### 1. `monitor-workflow.sh` - Single Workflow Monitor
Monitors a specific GitHub Actions workflow and reports when it completes.

**Usage:**

```bash
./monitor-workflow.sh <workflow-name> [branch] [commit-sha] [poll-interval]
```

**Example:**

```bash
./monitor-workflow.sh "Push Document Build" "main" "abc1234" 20
```

**Features:**

- ✅ Tracks workflow status (queued → in_progress → completed)
- ✅ Reports success/failure with clickable URLs
- ✅ Shows elapsed time
- ✅ Sends macOS notifications when complete
- ✅ Color-coded terminal output

### 2. `monitor-push.sh` - Multi-Workflow Monitor
Launches background monitors for all workflows triggered by a push.

**Usage:**

```bash
./monitor-push.sh
```

**Monitors:**

- PDF Build Workflow (`Push Document Build`)
- LaTeX Test Workflow (`Test LaTeX Document Compilation`)
- GitHub Pages (if `docs/` changes detected)

**Features:**

- ✅ Runs monitors in background with `nohup`
- ✅ Creates log files in `/tmp/github-actions-monitor-$$`
- ✅ Generates status check script
- ✅ Provides commands to view logs and control monitors

### 3. `git-push-with-monitor.sh` - Push + Monitor Wrapper
Combines git push with automatic workflow monitoring.

**Usage:**

```bash
./git-push-with-monitor.sh [git push options]
```

**Examples:**

```bash
./git-push-with-monitor.sh                    # Push current branch
./git-push-with-monitor.sh -u origin mybranch # Push and set upstream
./git-push-with-monitor.sh --force-with-lease # Force push safely
```

## 🚀 Quick Start

### Option 1: Manual Monitoring (After Push)

```bash
# After you've already pushed
cd .github/scripts
./monitor-push.sh
```

### Option 2: Push with Automatic Monitoring

```bash
# Push and automatically start monitoring
cd .github/scripts
./git-push-with-monitor.sh
```

### Option 3: Create a Git Alias (Recommended)
Add to your `~/.gitconfig`:

```ini
[alias]
    pushm = "!bash .github/scripts/git-push-with-monitor.sh"
```

Then use:

```bash
git pushm                    # Push and monitor
git pushm -u origin mybranch # Push, set upstream, and monitor
```

## 📊 Monitoring Workflow

1. **Push your code** (or run the wrapper script)
2. **Monitors launch automatically** in the background
3. **Check status anytime** using the generated status script:

   ```bash
   /tmp/github-actions-monitor-<pid>/show-status.sh
   ```

4. **View live logs**:

   ```bash
   tail -f /tmp/github-actions-monitor-<pid>/pdf-build.log
   tail -f /tmp/github-actions-monitor-<pid>/latex-test.log
   ```

5. **Get notified** when workflows complete (macOS notification)

## 🔧 Requirements

- **GitHub CLI** (`gh`) - [Install here](https://cli.github.com/)
- **Git** (obviously)
- **macOS** - For desktop notifications (optional)
- **jq** - JSON processor (usually pre-installed)

### Check if you have the tools:

```bash
which gh     # Should show: /usr/local/bin/gh
which jq     # Should show path to jq
gh --version # Should show version 2.0+
```

## 📝 Log Files

Logs are stored in temporary directories:

```
/tmp/github-actions-monitor-<pid>/
├── pdf-build.log          # PDF build workflow output
├── latex-test.log         # LaTeX test workflow output
├── show-status.sh         # Quick status checker
└── monitor-info.txt       # Monitor metadata
```

## 🎯 Example Output

```
🚀 GitHub Actions Monitor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌿 Branch: 20250612_finish-latexmk-fixes
📝 Commit: abc1234
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Starting workflow monitors...

1️⃣  Monitoring: Push Document Build (PDF)
   Process ID: 12345
   Log file: /tmp/github-actions-monitor-12345/pdf-build.log

2️⃣  Monitoring: Test LaTeX Compilation
   Process ID: 12346
   Log file: /tmp/github-actions-monitor-12345/latex-test.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Monitors launched successfully!
```

When a workflow completes:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WORKFLOW COMPLETED SUCCESSFULLY!
🎉 Status: Success
⏱️  Duration: 5m 32s
🔗 View details: https://github.com/owner/repo/actions/runs/123456
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🛠️ Troubleshooting

### Monitors don't start

1. **Check GitHub CLI authentication**:

   ```bash
   gh auth status
   ```

   If not authenticated: `gh auth login`

2. **Verify workflow names** match exactly:

   ```bash
   gh workflow list
   ```

### No notifications

- Notifications require macOS
- Check System Preferences → Notifications → Script Editor/Terminal
- Notifications may not show if you're in full-screen mode

### Workflows not found

- GitHub may take 5-10 seconds to create the workflow run
- The monitor waits up to 60 seconds by default
- Check if the workflow is actually triggered for your branch

### Kill stuck monitors

```bash
# List background monitor processes
ps aux | grep monitor-workflow

# Kill specific PID
kill <PID>

# Or kill all monitors
pkill -f monitor-workflow
```

## 🔄 Alternative Approaches

If you encounter issues with background processes on macOS:

### Option 1: Use Terminal Tabs/Windows

```bash
# Terminal 1: Main work
git push

# Terminal 2: Monitor PDF build
.github/scripts/monitor-workflow.sh "Push Document Build"

# Terminal 3: Monitor LaTeX test
.github/scripts/monitor-workflow.sh "Test LaTeX Document Compilation"
```

### Option 2: Use tmux/screen

```bash
# Start tmux session
tmux new -s github-monitors

# Split windows (Ctrl+b %)
.github/scripts/monitor-workflow.sh "Push Document Build"

# Create new pane and monitor second workflow
.github/scripts/monitor-workflow.sh "Test LaTeX Document Compilation"

# Detach: Ctrl+b d
# Reattach: tmux attach -t github-monitors
```

### Option 3: Use the GitHub Website/CLI directly

```bash
# View workflows in terminal
gh run list --limit 5

# Watch a specific run
gh run watch <run-id>

# Or just open in browser
gh run list --web
```

### Option 4: Create a LaunchAgent (Advanced)
For persistent monitoring across terminal sessions, you could create a macOS LaunchAgent. See `launchd` documentation.

## 📚 Additional Resources

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions API](https://docs.github.com/en/rest/actions)

## 🤝 Contributing

These scripts are specific to the HAFiscal project but can be adapted for other repositories. Feel free to customize the workflow names, polling intervals, and notification preferences.
