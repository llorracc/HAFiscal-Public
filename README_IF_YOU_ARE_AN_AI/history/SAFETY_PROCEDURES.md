# HAFiscal Safety Procedures & Recovery Guide

## 🛡️ Prevention Measures Active

### ✅ Installed Protections
1. **Pre-commit Hook**: Warns about large changes, requires confirmation
2. **Safe Git Aliases**: Use these instead of dangerous git commands
3. **Automated Backup System**: Creates recovery points before major changes

---

## 🚨 Before Making Major Changes

### ALWAYS Do This First:
```bash
# 1. Create backup
bash scripts/backup-before-major-changes.sh

# 2. Check current state
git status-safe

# 3. If many files changed, review carefully:
git diff --stat
```

---

## ⚡ Safe Commands (Use These Instead)

| **DANGEROUS** | **SAFE ALTERNATIVE** | **What It Does** |
|---------------|---------------------|------------------|
| `git reset --hard` | `git safe-reset <commit>` | Resets with confirmation |
| `git clean -fd` | `git safe-clean` | Removes files with preview |
| `git checkout` | `git safe-checkout` | Checks uncommitted changes |
| `git status` | `git status-safe` | Shows warnings for large changes |

### Emergency Backup:
```bash
git backup-state    # Quick stash with timestamp
```

---

## 🚨 If Pre-Commit Hook Blocks You

The hook will block commits with:
- **2000+** lines deleted 
- **30+** files changed
- **Multiple** risky patterns

### To Proceed:
1. **Review carefully**: `git diff --stat`
2. **Type exactly**: `CONFIRM_MASSIVE_CHANGE` when prompted
3. **Override if needed**: `git commit --no-verify` (dangerous!)

---

## 🔄 Recovery Procedures

### If You Accidentally Deleted Important Code:

#### Option 1: From Recent Backups
```bash
# List available backups
ls -la ../HAFiscal-Backups/

# Restore specific backup
git clone ../HAFiscal-Backups/HAFiscal-Latest_YYYY-MM-DD_HH-MM-SS.bundle recovered-repo
```

#### Option 2: From Git History
```bash
# Find when file was last good
git log --oneline --follow -- path/to/missing/file.tex

# Restore specific file from commit
git checkout COMMIT_HASH -- path/to/file.tex

# Or restore everything from a commit
git reset --hard COMMIT_HASH  # ⚠️ DESTRUCTIVE
```

#### Option 3: From Stash
```bash
# List recent backups
git stash list

# Apply specific backup
git stash apply stash@{0}
```

---

## 📊 Common Warning Signs

### 🚨 Red Flags (STOP!)
- "Many files changed (30+ files)"
- "Large deletion detected (2000+ lines)" 
- "Many critical LaTeX files modified"
- Massive `\onlyinsubfile` ↔ `\whenstandalone` changes

### ⚠️ Yellow Flags (Proceed Carefully)
- 500+ lines deleted
- 20+ files changed  
- 10+ LaTeX files modified

---

## 🎯 Quick Recovery Commands

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) - CAREFUL!
git safe-reset HEAD~1

# See what changed in dangerous commit
git show COMMIT_HASH --stat

# Revert specific commit (creates new commit)
git revert COMMIT_HASH

# Emergency stash everything
git backup-state
```

---

## 📋 Pre-Major-Operation Checklist

Before any large operation:

- [ ] Created backup: `bash scripts/backup-before-major-changes.sh`
- [ ] Reviewed changes: `git diff --stat`
- [ ] Checked status: `git status-safe`
- [ ] Confirmed critical files aren't accidentally included
- [ ] Have recovery plan if something goes wrong

---

## 🆘 Emergency Contacts & Resources

- **Last Good State**: Check `../HAFiscal-Backups/` for recent backups
- **Git History**: `git log --oneline --graph -20`
- **File History**: `git log --follow -- filename.tex`
- **Blame/Annotate**: `git blame filename.tex` to see when lines changed

---

## 🔧 Configuration Files

- **Pre-commit Hook**: `.git/hooks/pre-commit`
- **Git Aliases**: `~/.gitconfig` (global) or `.git/config` (local)
- **Backup Script**: `scripts/backup-before-major-changes.sh`

Remember: It's better to be overly cautious than to need another major restoration! 🛡️ # Test comment 