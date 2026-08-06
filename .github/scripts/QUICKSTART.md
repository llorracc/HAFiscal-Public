# 🚀 Quick Start: GitHub Actions Monitoring

## TL;DR - Fastest Way to Monitor Your Workflows

### Method 1: Automatic (Recommended)

```bash
# From project root, run:
.github/scripts/git-push-with-monitor.sh

# Or create a git alias and use it anywhere:
git config alias.pushm '!bash .github/scripts/git-push-with-monitor.sh'
git pushm
```

### Method 2: Manual (After you've already pushed)

```bash
# From project root:
.github/scripts/monitor-push.sh
```

## What You'll Get

✅ **Automatic background monitoring** of:

- PDF Build Workflow (`Push Document Build`)
- LaTeX Test Workflow (`Test LaTeX Document Compilation`)
- GitHub Pages (if `docs/` changes)

✅ **macOS notifications** when workflows complete

✅ **Live status** with clickable URLs to GitHub Actions

✅ **Separate log files** for each workflow

## Example Session

```bash
$ .github/scripts/git-push-with-monitor.sh

🚀 Git Push with Workflow Monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📤 Pushing to remote...

To github.com:llorracc/HAFiscal.git
   abc1234..def5678  20250612_finish-latexmk-fixes -> 20250612_finish-latexmk-fixes

✅ Push successful!

🔍 Launching workflow monitors...

🚀 GitHub Actions Monitor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌿 Branch: 20250612_finish-latexmk-fixes
📝 Commit: def5678
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Starting workflow monitors...

1️⃣  Monitoring: Push Document Build (PDF)
   Process ID: 45123
   Log file: /tmp/github-actions-monitor-45123/pdf-build.log

2️⃣  Monitoring: Test LaTeX Compilation
   Process ID: 45124
   Log file: /tmp/github-actions-monitor-45123/latex-test.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Monitors launched successfully!

💡 Tip: Run this command to check status:
  /tmp/github-actions-monitor-45123/show-status.sh

✨ Done! Monitors are running in the background.
💡 You'll get macOS notifications when workflows complete.
```

## Checking Status Later

```bash
# View live log of PDF build
tail -f /tmp/github-actions-monitor-*/pdf-build.log

# View live log of LaTeX test
tail -f /tmp/github-actions-monitor-*/latex-test.log

# Quick status check (uses the generated script)
/tmp/github-actions-monitor-*/show-status.sh

# List all monitor processes
ps aux | grep monitor-workflow
```

## When Workflows Complete

You'll see output like this in the log:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WORKFLOW COMPLETED SUCCESSFULLY!
🎉 Status: Success
⏱️  Duration: 8m 45s
🔗 View details: https://github.com/llorracc/HAFiscal/actions/runs/123456
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Plus a macOS notification! 🔔

## Stopping Monitors

```bash
# Kill specific monitor (use PID from startup output)
kill 45123 45124

# Or kill all monitors
pkill -f monitor-workflow
```

## Troubleshooting

### "Workflow run not found"

- Your branch may not trigger this workflow (check branch filters)
- Path filters may exclude your changes  
- Wait a bit longer - GitHub can be slow

### No notifications showing

- Check System Preferences → Notifications → Terminal/Script Editor
- Notifications may not show in full-screen mode

### GitHub CLI not authenticated

```bash
gh auth status    # Check status
gh auth login     # Login if needed
```

## Alternative: Use Separate Terminal Windows

If background processes are problematic:

```bash
# Terminal 1: Main work
git push

# Terminal 2: Monitor PDF build
.github/scripts/monitor-workflow.sh "Push Document Build"

# Terminal 3: Monitor LaTeX test  
.github/scripts/monitor-workflow.sh "Test LaTeX Document Compilation"
```

## See Full Documentation

📖 Read [README.md](./.README.md) for complete documentation and advanced options.
