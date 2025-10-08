# 🔔 GitHub Actions Notification Setup Guide

## Why Didn't I See Notifications?

macOS requires explicit permission for Terminal (or any app) to display notifications. Here's how to fix it:

## ✅ Enable macOS Notification Center Permissions

### Quick Way:
```bash
open "x-apple.systempreferences:com.apple.preference.notifications"
```

### Manual Way:
1. Open **System Settings** (or System Preferences)
2. Go to **Notifications**
3. Scroll down and find **"Terminal"** (or **"Script Editor"** if using that)
4. Click on **Terminal**
5. Enable these settings:
   - ✅ **Allow Notifications**
   - ✅ **Show in Notification Center**  
   - ✅ **Play sound for notifications**
   - Set alert style to: **Banners** or **Alerts** (NOT "None")

### Test After Enabling:
```bash
osascript -e 'display notification "Test notification!" with title "GitHub Actions ✅" sound name "Glass"'
```

You should see a notification pop up in the top-right corner!

## 🔊 Multi-Method Notification System

The monitoring script now uses **4 different notification methods** to ensure you never miss a completion:

### 1. 📱 macOS Notification Center (Most Visual)
- **Requires:** Permission setup (see above)
- **Pros:** Most visible, stays in Notification Center
- **Cons:** Needs one-time setup
- **Example:** Pop-up banner in top-right corner

### 2. 🔔 Terminal Bell (Always Works)
- **Requires:** Nothing
- **Pros:** Works immediately, no permissions needed
- **Cons:** Just a beep sound, easy to miss
- **How it works:** `echo -e "\a"` sends bell character

### 3. 🗣️ Voice Announcement (Most Noticeable)
- **Requires:** Nothing (macOS built-in)
- **Pros:** Very noticeable, works even if display is off
- **Cons:** Might startle you in quiet environments
- **What you'll hear:** 
  - Success: "GitHub Actions workflow completed successfully"
  - Failure: "GitHub Actions workflow failed"

### 4. 📄 Visual Log Markers (Most Reliable)
- **Requires:** Nothing
- **Pros:** Always works, permanent record
- **Cons:** Need to check log files manually
- **Look for:** `🔔🔔🔔 WORKFLOW COMPLETED - CHECK ABOVE FOR DETAILS 🔔🔔🔔`

## 🧪 Test All Notification Methods

Run this test script:

```bash
.github/scripts/test-notifications.sh
```

Or manually:
```bash
# Test 1: Notification Center
osascript -e 'display notification "Test" with title "Test" sound name "Glass"'

# Test 2: Terminal Bell
echo -e "\a"

# Test 3: Voice
say "This is a test"

# Test 4: Visual (check terminal output)
echo "🔔🔔🔔 TEST NOTIFICATION 🔔🔔🔔"
```

## 🔧 Troubleshooting

### "I still don't see notifications"

1. **Check Do Not Disturb:**
   - Look at Menu Bar (top-right)
   - If you see a moon icon 🌙, DND is enabled
   - Click it to disable

2. **Check Focus Modes:**
   - macOS Monterey+ has "Focus" modes
   - Make sure none are active

3. **Restart Terminal:**
   - After changing permissions, quit and reopen Terminal
   - Permissions sometimes don't take effect until restart

4. **Check Terminal is the active app:**
   - Some notification settings only show for the frontmost app
   - Make sure Terminal is running (doesn't need to be frontmost)

### "Voice notifications are too loud/annoying"

Edit `.github/scripts/monitor-workflow.sh` and comment out lines 176-185:

```bash
# Method 3: Voice announcement (macOS text-to-speech)
# if command -v say &> /dev/null; then
#     case "$CONCLUSION" in
#         "success")
#             say "GitHub Actions workflow completed successfully" &
#             ;;
#         "failure")
#             say "GitHub Actions workflow failed" &
#             ;;
#     esac
# fi
```

### "I want a dialog box instead (blocking but very visible)"

Uncomment this line in the script (around line 193):

```bash
open "$RUN_URL"  # Opens the GitHub Actions page in browser
```

Or add this for a dialog box:
```bash
osascript -e 'display dialog "Workflow completed!" buttons {"OK"} default button 1'
```

## 📊 Best Practices

### For Daytime Work (Notifications Visible):
- Enable Notification Center permissions
- Keep voice notifications enabled
- Monitor logs occasionally: `tail -f /tmp/github-actions-monitor-*/`

### For Background/Long Builds:
- Voice notifications are most reliable
- Check logs periodically
- Consider opening GitHub Actions URL automatically

### For Quiet Environments:
- Disable voice (comment out in script)
- Use only visual notifications
- Enable Notification Center with sound off

## 🎯 Quick Reference

| Method | Setup Required | Visibility | Always Works? |
|--------|----------------|------------|---------------|
| Notification Center | ✅ Permissions | ⭐⭐⭐⭐⭐ | ❌ (needs setup) |
| Voice (`say`) | ❌ None | ⭐⭐⭐⭐ | ✅ Yes |
| Terminal Bell | ❌ None | ⭐⭐ | ✅ Yes |
| Log Markers | ❌ None | ⭐⭐⭐ | ✅ Yes |

## 📚 Additional Resources

- [Apple: Notifications User Guide](https://support.apple.com/guide/mac-help/change-notifications-settings-mh40583/mac)
- [macOS osascript Documentation](https://ss64.com/osx/osascript.html)
- [Terminal Bell Character](https://en.wikipedia.org/wiki/Bell_character)

