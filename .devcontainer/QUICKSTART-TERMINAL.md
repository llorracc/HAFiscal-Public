# Quick Start: Launching DevContainer and Accessing Terminal

## Complete Step-by-Step Guide

### Step 1: Launch Cursor and Open Container

1. **Open Cursor** (or VS Code)

2. **Open Command Palette**:
   - macOS: `Cmd+Shift+P`
   - Windows/Linux: `Ctrl+Shift+P`

3. **Type**: `Dev Containers: Clone Repository in Container Volume`

4. **Select it** from the dropdown

5. **Enter repository URL**:

   ```
   https://github.com/llorracc/HAFiscal-Latest.git
   ```

6. **Press Enter**

7. **Wait for build** (15-20 minutes first time):
   - You'll see: "Starting Dev Container (show log)"
   - Click "show log" to watch progress
   - TeX Live 2025 installation will take ~8-10 minutes
   - Python/UV setup will take ~3-5 minutes

### Step 2: Container Opens Automatically

Once the build completes:

1. **Cursor will automatically reopen** in the container
2. **You'll see** in the bottom-left corner:

   ```
   Dev Container: HAFiscal Development (TeX Live 2025)
   ```

   This confirms you're inside the container!

3. **The file explorer** on the left shows:

   ```
   /workspaces/HAFiscal-Latest/
   ```

### Step 3: Open Integrated Terminal

**Option A: Keyboard Shortcut** (Fastest)

```
macOS: Ctrl+` (control + backtick)
Windows/Linux: Ctrl+` (control + backtick)
```

**Option B: Menu** (Visual)

1. Click **Terminal** in the top menu
2. Select **New Terminal**

**Option C: Command Palette**

1. `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
2. Type: `Terminal: Create New Terminal`
3. Press Enter

### Step 4: You're Now in the Container Terminal!

You'll see a prompt like:

```bash
vscode@a1b2c3d4e5f6:/workspaces/HAFiscal-Latest$
```

Breaking this down:

- `vscode` = your username inside container
- `a1b2c3d4e5f6` = container ID
- `/workspaces/HAFiscal-Latest` = current directory

**You are now inside the container!** This terminal is NOT your host machine.

### Step 5: Run the Commands

Now you can execute the commands:

```bash
# You're already in /workspaces/HAFiscal-Latest
# Build the PDF
./reproduce.sh --docs main
```

This will build the HAFiscal PDF, generating all figures and tables. Output will be in `Deliverables/`.

To see all reproduction options:

```bash
./reproduce.sh --help
```

---

## Visual Guide: What You'll See

### Before Container Launch

```
┌─────────────────────────────────────┐
│ Cursor (regular window)             │
│                                     │
│  Bottom-left corner: (empty)        │
└─────────────────────────────────────┘
```

### During Container Build

```
┌─────────────────────────────────────┐
│ Cursor                              │
│                                     │
│  Bottom-left: Dev Container:        │
│               Starting...           │
│               (show log)            │
└─────────────────────────────────────┘
```

### After Container Opened

```
┌─────────────────────────────────────┐
│ Cursor - /workspaces/HAFiscal-Latest│
│                                     │
│  File Explorer:                     │
│  📁 /workspaces/HAFiscal-Latest     │
│     📁 .devcontainer/               │
│     📁 Code/                        │
│     📁 Figures/                     │
│     📄 HAFiscal.tex                 │
│                                     │
│  Bottom-left:                       │
│  🐳 Dev Container: HAFiscal...      │
│                                     │
│  Terminal (Ctrl+`):                 │
│  vscode@abc123:/workspaces/.../$   │
└─────────────────────────────────────┘
```

---

## Common Questions

### Q: How do I know I'm inside the container?

**A:** Check the bottom-left corner of Cursor. You'll see:

```
🐳 Dev Container: HAFiscal Development (TeX Live 2025)
```

If you see this, you're in the container!

### Q: What if I don't see the terminal?

**A:** Press `Ctrl+`` (control + backtick) to toggle the terminal panel.

### Q: Can I open multiple terminals?

**A:** Yes! Click the `+` button in the terminal panel or press `Cmd+Shift+`` (macOS) /`Ctrl+Shift+`` (Windows/Linux).

### Q: How do I exit the container?

**A:**

- **Option 1**: Close Cursor (container stops automatically)
- **Option 2**: `Cmd+Shift+P` → "Dev Containers: Reopen Folder Locally"
- **Option 3**: Click the bottom-left "Dev Container" badge → "Reopen Folder Locally"

### Q: How do I get back into the container later?

**A:**

1. Open Cursor
2. `Cmd+Shift+P` → "Dev Containers: Open Folder in Container"
3. Select the container from the list
4. Or: Click "Recent" and select the HAFiscal-Latest container

---

## Alternative: Use Docker Desktop Terminal

If you prefer Docker Desktop's interface:

1. **Open Docker Desktop**
2. **Click "Containers"** in left sidebar
3. **Find**: `hafiscal-latest-...` (your container)
4. **Click** the container name
5. **Click "Terminal"** tab
6. **You're now in the container terminal!**

Run your commands here:

```bash
cd /workspaces/HAFiscal-Latest
./reproduce.sh --docs main
```

---

## Troubleshooting

### Terminal Shows Host Machine Path

**Problem**: Terminal shows `/Users/yourname/...` or `C:\Users\...`

**Solution**: You're not in the container!

1. Check bottom-left corner for "Dev Container" badge
2. If missing, reopen folder in container:
   - `Cmd+Shift+P` → "Dev Containers: Reopen in Container"

### Terminal Commands Not Found

**Problem**: `git: command not found` or `python: command not found`

**Solution**: You're not in the container!

1. Verify bottom-left shows "Dev Container"
2. Close and reopen terminal: `Cmd+Shift+P` → "Terminal: Kill Terminal"
3. Open new terminal: `Ctrl+``

### Container Build Failed

**Problem**: Build stops with errors

**Solution**: Rebuild without cache

1. `Cmd+Shift+P` → "Dev Containers: Rebuild Container Without Cache"
2. Wait for complete rebuild

---

## Summary: The Complete Workflow

```
1. Open Cursor
   ↓
2. Cmd+Shift+P → "Clone Repository in Container Volume"
   ↓
3. Enter: https://github.com/llorracc/HAFiscal-Latest.git
   ↓
4. Wait 15-20 minutes (TeX Live 2025 + Python installation)
   ↓
5. Cursor reopens in container automatically
   ↓
6. Press Ctrl+` to open terminal
   ↓
7. You see: vscode@containerID:/workspaces/HAFiscal-Latest$
   ↓
8. Run commands:
   ./reproduce.sh --docs main
   ↓
9. PDF builds! (first time: 10-15 min, subsequent: 3-5 min)
```

---

## Video Walkthrough (Text Description)

If you were watching over my shoulder, here's what you'd see:

1. **I open Cursor** - normal Cursor window
2. **I press `Cmd+Shift+P`** - command palette appears at top
3. **I type "clone repo"** - autocomplete shows "Clone Repository in Container Volume"
4. **I press Enter** - new input box appears
5. **I paste URL** `https://github.com/llorracc/HAFiscal-Latest.git`
6. **I press Enter** - Cursor shows "Starting Dev Container (show log)"
7. **I click "show log"** - terminal appears showing build progress:

   ```
   Installing TeX Live 2025...
   Configuring LaTeX environment...
   Installing UV...
   Setting up Python...
   ```

8. **15-20 minutes later** - Cursor reopens with file explorer showing `/workspaces/HAFiscal-Latest`
9. **Bottom-left shows** - "🐳 Dev Container: HAFiscal Development"
10. **I press `Ctrl+``** - terminal panel appears at bottom
11. **Terminal shows** - `vscode@abc123:/workspaces/HAFiscal-Latest$`
12. **I type command**:

    ```bash
    ./reproduce.sh --docs main
    ```

13. **Build starts** - LaTeX output streaming in terminal
14. **5-10 minutes later** - "✅ SUCCESS: Created HAFiscal.pdf"

Done!

---

## Key Takeaway

**The terminal automatically opens INSIDE the container** when you press `Ctrl+``. You don't need to do anything special to "enter" the container - Cursor handles that for you when you reopen the folder in the container.

The indicator that you're in the container is:

1. Bottom-left corner shows "Dev Container"
2. Terminal prompt shows `vscode@...:/workspaces/...`
3. File paths start with `/workspaces/` not `/Users/` or `C:\`
