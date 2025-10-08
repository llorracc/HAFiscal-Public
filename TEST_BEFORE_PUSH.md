# 🧪 Test Before Pushing

Avoid waiting 10-30 minutes for GitHub Actions to tell you something failed!

## Quick Command

```bash
./.github/scripts/test-local-like-ci.sh
```

This runs in **2-5 minutes** and tests if your changes will pass GitHub Actions.

---

## What It Does

✅ Sets up GitHub Actions environment variables  
✅ Runs the same build command: `reproduce/reproduce_documents.sh`  
✅ Checks for critical LaTeX errors  
✅ Reports success or failure  

If it passes locally, it will **probably** pass on GitHub Actions!

---

## Full Documentation

See [`.github/scripts/TESTING_LOCALLY.md`](.github/scripts/TESTING_LOCALLY.md) for:
- Detailed comparison of local vs GitHub Actions
- Docker option for 100% identical environment
- Debugging guide
- Common issues and solutions

---

## Quick Workflow

```bash
# 1. Make your changes
vim HAFiscal.tex

# 2. Test locally (2-5 min)
./.github/scripts/test-local-like-ci.sh

# 3. If it passes, push with confidence!
git add .
git commit -m "My changes"
git push

# GitHub Actions should succeed! ✅
```

**Time savings**: Skip 10-30 minute wait cycles for every failed build iteration.
