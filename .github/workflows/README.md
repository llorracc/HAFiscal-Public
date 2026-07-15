# GitHub Actions Workflows for Docker Testing

This directory contains automated workflows for testing the HAFiscal Docker container builds.

## Workflows

### 1. `docker-quick-test.yml` - Fast Validation ⚡

**Purpose:** Quick feedback for every commit/PR  
**Duration:** ~5-8 minutes  
**Triggers:**

- Every push to `master`/`main`
- Every pull request
- Manual dispatch

**Tests:**

- ✅ Docker image builds successfully
- ✅ Basic LaTeX commands available
- ✅ Architecture detection working
- ✅ Critical packages installed (microtype, datetime2, beamer, catchfile)
- ✅ Python environment functional
- ✅ Environment test (`./reproduce.sh --envt`) passes

**Use this for:** Rapid validation of changes before full testing

---

### 2. `docker-build-test.yml` - Full Validation 🔍

**Purpose:** Comprehensive testing including document compilation  
**Duration:** ~10-15 minutes  
**Triggers:**

- Push to `master`/`main` that modifies:
  - `Dockerfile`
  - `.devcontainer/**`
  - `reproduce/required_latex_packages.txt`
  - Workflow files
- Pull requests modifying above files
- Manual dispatch

**Tests:**

- ✅ All quick tests (see above)
- ✅ Document compilation (`./reproduce.sh --docs main`)
- ✅ PDFs generated (HAFiscal.pdf, HAFiscal-Slides.pdf)

**Use this for:** Final validation before merging Docker changes

---

## Build Caching

Both workflows use **GitHub Actions Cache** to speed up builds:

- First build: ~4-5 minutes
- Cached builds: ~2-3 minutes (if only small changes)

Caching saves:

- TeX Live installation (~2 minutes)
- Python packages (~1 minute)
- Docker layers (varies)

---

## Manual Triggering

You can manually trigger either workflow:

1. Go to **Actions** tab in GitHub
2. Select the workflow (Quick Test or Build and Test)
3. Click **Run workflow**
4. Choose branch
5. Click **Run workflow**

---

## Monitoring Test Results

### View Test Status

**On Pull Requests:**

- Status checks appear automatically
- ✅ Green checkmark = tests passed
- ❌ Red X = tests failed

**On Commits:**

- Badge appears next to commit message
- Click badge to see detailed logs

### View Test Logs

1. Go to **Actions** tab
2. Click on the workflow run
3. Click on the job name (`quick-test` or `build-and-test`)
4. Expand individual steps to see detailed output

---

## Architecture Notes

### Current Testing Platform

- **OS:** Ubuntu Latest (Linux)
- **Architecture:** x86_64 (AMD64)

### Multi-Architecture Support

The Dockerfile supports both architectures:

- `x86_64-linux` (Intel/AMD)
- `aarch64-linux` (ARM64/Apple Silicon)

GitHub Actions currently tests on x86_64 only. For ARM64 testing, you would need:

- Self-hosted runners on ARM64
- Or build multi-arch with QEMU (slower)

---

## Performance Expectations

### Quick Test Workflow ⚡

```
Setup:           ~30 seconds
Docker Build:    ~2-3 minutes (cached) / ~4-5 minutes (fresh)
Tests:           ~2-3 minutes
Total:           ~5-8 minutes
```

### Full Build Test Workflow 🔍

```
Setup:           ~30 seconds
Docker Build:    ~2-3 minutes (cached) / ~4-5 minutes (fresh)
Environment Test: ~2 seconds
Document Build:  ~1 minute
Total:           ~8-12 minutes
```

---

## Troubleshooting

### Test Failures

**If Quick Test fails:**

1. Check the step that failed
2. Common issues:
   - Missing LaTeX packages → Update `required_latex_packages.txt` and `Dockerfile`
   - Python import errors → Check `pyproject.toml` and `uv sync`
   - Architecture detection → Check `.devcontainer/texlive-2025/detect-arch.sh`

**If Full Build Test fails:**

1. Quick test passes but document compilation fails:
   - Missing packages in actual LaTeX compilation
   - Check `.tex` files for new package requirements
   - Review compilation logs in test output

### Timeout Issues

Tests have timeouts to prevent hanging:

- Environment test: 60 seconds (quick) / 120 seconds (full)
- Document compilation: 300 seconds (5 minutes)

If legitimate operations exceed these, adjust in workflow file:

```yaml
timeout 300 ./reproduce.sh --docs main
#       ^^^
#       Increase if needed
```

---

## Customization

### Add More Tests

Edit the workflow files to add steps:

```yaml
- name: Test - Custom Check
  run: |
    echo "Running custom test..."
    docker run --rm ${{ env.IMAGE_NAME }}:test bash -c \
      "your-test-command-here"
```

### Change Trigger Conditions

Modify the `on:` section:

```yaml
on:
  push:
    branches: [ master, main, dev ]  # Add 'dev' branch
    paths:
      - 'Dockerfile'
      - 'your-custom-path/**'        # Add custom paths
```

### Skip CI on Specific Commits

Add to commit message:

```
git commit -m "docs: update README [skip ci]"
```

---

## Cost Considerations

### GitHub Actions Limits

**Free tier (public repos):**

- ✅ Unlimited minutes
- ✅ 20 concurrent jobs

**Free tier (private repos):**

- 2,000 minutes/month
- Each workflow run: ~10-15 minutes
- ~130-200 test runs per month

### Optimization Tips

1. **Use Quick Test for most commits**
   - Only 5-8 minutes
   - Catches most issues

2. **Full Test only when needed**
   - Only triggers on Dockerfile/package changes
   - Or manual trigger when ready

3. **Cache is your friend**
   - First build: slow
   - Subsequent builds: fast (2-3x speedup)

---

## Best Practices

### For Contributors

1. **Before committing Dockerfile changes:**
   - Test locally if possible
   - Let Quick Test run first
   - Wait for Full Test before merging

2. **When adding LaTeX packages:**
   - Update `reproduce/required_latex_packages.txt` first
   - Then update `Dockerfile`
   - Commit both together

3. **For large refactors:**
   - Create draft PR
   - Let tests run
   - Iterate based on results

### For Maintainers

1. **Review test logs** for warnings
2. **Update workflows** when requirements change
3. **Monitor build times** and optimize if needed
4. **Keep cache fresh** by rebuilding occasionally

---

## Future Enhancements

Potential improvements:

- [ ] Multi-architecture testing (ARM64 + x86_64)
- [ ] Artifact upload (save PDFs from test builds)
- [ ] Test matrix (multiple Ubuntu versions)
- [ ] Scheduled builds (weekly full test)
- [ ] Slack/email notifications on failure
- [ ] Performance benchmarking across commits

---

## Support

For issues with workflows:

1. Check workflow logs in Actions tab
2. Review this README
3. Check `.github/workflows/*.yml` files
4. Open an issue with logs attached

---

**Last Updated:** 2025-12-03  
**Workflow Version:** 1.0.0  
**Tested On:** GitHub Actions Ubuntu Latest
