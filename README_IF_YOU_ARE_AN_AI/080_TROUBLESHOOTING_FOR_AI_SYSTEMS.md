# Troubleshooting Guide for AI Systems

## Quick Diagnostic Commands

Run these first to identify common issues:

```bash
# Environment Check
python -c "import numpy, pandas, matplotlib; print('✅ Basic packages OK')" || echo "❌ Package import error"

# Repository Structure Check  
ls -la reproduce.sh README.md Code/ || echo "❌ Repository structure issue"

# Permissions Check
touch test_write.txt && rm test_write.txt && echo "✅ Write permissions OK" || echo "❌ Permission error"

# Git Status (if applicable)
git status 2>/dev/null | head -3 || echo "Not a git repository or git not available"
```

## Common Error Categories & Solutions

### 1. Environment Setup Issues

#### Error: `ModuleNotFoundError: No module named 'econ_ark'`
**Cause**: Python environment not properly configured
**Solutions**:
```bash
# Option 1: Use conda environment
conda env create -f binder/environment.yml
conda activate hafiscal-env

# Option 2: Use pip installation  
pip install -r binder/requirements.txt

# Option 3: Install core dependencies manually
pip install econ_ark numpy pandas matplotlib scipy jupyter
```

#### Error: `Command not found: stata`
**Cause**: Stata not available for empirical analysis
**Impact**: Empirical components will fail, but Python models should work
**Solutions**:
- Install Stata if available
- Focus on Python-only analysis (`Code/HA-Models/`)
- Use pre-computed results in repository

### 2. Computational Execution Issues

#### Error: Memory errors during Step 2 or Step 5
**Cause**: Insufficient RAM for large model estimation
**Solutions**:
```bash
# Reduce computational intensity
# Edit Code/HA-Models/do_all.py:
run_step_2 = False  # Skip memory-intensive step
run_step_5 = False  # Skip longest computation

# Alternative: Run steps individually with breaks
```

#### Error: `KeyboardInterrupt` or timeout
**Cause**: Computation taking longer than expected
**Solutions**:
- Be patient (Step 2: ~21 hours, Step 5: ~65 hours)
- Use partial execution strategy
- Monitor system resources (CPU, memory usage)

### 3. File Access & Permission Issues

#### Error: `Permission denied` when writing files
**Cause**: Insufficient write permissions
**Solutions**:
```bash
# Check directory permissions
ls -la Code/HA-Models/
chmod -R u+w Code/HA-Models/  # Fix write permissions

# Alternative: Run in user directory
cp -r Code/HA-Models ~/hafiscal_models
cd ~/hafiscal_models && python do_all.py
```

#### Error: Missing input files or data
**Cause**: Repository incomplete or corrupted
**Solutions**:
```bash
# Verify repository integrity
find . -name "*.py" | wc -l    # Should find multiple Python files
find . -name "*.dta" | wc -l   # Should find Stata data files

# Re-clone repository if necessary
git status  # Check for missing files
```

### 4. Reproduction Script Issues

#### Error: `./reproduce.sh: command not found`
**Cause**: Script not executable or not in PATH
**Solutions**:
```bash
# Make script executable
chmod +x reproduce.sh

# Run with explicit bash
bash reproduce.sh --docs
```

#### Error: Reproduction fails with "missing computational results"
**Cause**: Computational steps not yet completed
**Solutions**:
```bash
# Run computational steps first
cd Code/HA-Models && python do_all.py

# Or use minimal computational reproduction
./reproduce.sh --comp min
```

## AI-Specific Debugging Strategies

### Strategy 1: Incremental Validation
```bash
# Test environment first
python -c "import sys; print(sys.version)"

# Test basic imports
python -c "from HARK import ConsIndShockModel; print('HARK OK')"

# Test individual steps
cd Code/HA-Models
python Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py
```

### Strategy 2: Dry-run Mode
```bash
# See commands without executing (if supported)
./reproduce.sh --dry-run --docs
```

### Strategy 3: Log Analysis
```bash
# Create detailed logs
python do_all.py > computation.log 2>&1

# Monitor progress
tail -f computation.log

# Search for errors
grep -i error computation.log
```

## Known Issues & Workarounds

### Issue 1: Long computation times
**Expected**: Steps 2 and 5 take many hours
**Workaround**: Use testing strategy with selective step execution
```python
# In do_all.py - Quick testing configuration:
run_step_1 = True   # Fast validation
run_step_2 = False  # Skip longest step
run_step_3 = False  # Skip robustness
run_step_4 = True   # Medium-length validation
run_step_5 = False  # Skip policy comparison
```

### Issue 2: Platform compatibility
**Expected**: Developed and tested on Windows
**Workaround**: Mac/Linux users may need dependency adjustments
```bash
# Linux-specific package installs
apt-get install python3-dev libatlas-base-dev

# Mac-specific (with Homebrew)
brew install python3 numpy scipy
```

### Issue 3: Stata integration
**Expected**: Empirical analysis requires Stata
**Workaround**: Focus on Python components
- Skip `Code/Empirical/` analysis
- Use included data files (.dta format)
- Convert to Python if needed using pandas

## Validation Checksums & Expected Outputs

### File Size Validation
```bash
# Key output file sizes (approximate):
ls -lh Code/HA-Models/Target_AggMPCX_LiquWealth/Figures/*.pdf
ls -lh Code/HA-Models/FromPandemicCode/Figures/*.pdf  
ls -lh Code/HA-Models/FromPandemicCode/Tables/*.tex
```

### Success Indicators
- **Step 1 Complete**: Files in `Target_AggMPCX_LiquWealth/Figures/`
- **Step 4 Complete**: Files in `FromPandemicCode/Figures/` (HANK results)
- **Full Success**: Complete figure and table sets

## Emergency Recovery Procedures

### If computation hangs:
1. Check system resources (`top`, `htop`)
2. Look for infinite loops in log files
3. Restart with reduced scope (fewer steps)

### If files corrupted:
1. Backup any successful intermediate results
2. Clean workspace: `git clean -fd`
3. Restart from clean state

### If environment broken:
1. Create fresh conda environment
2. Reinstall dependencies from scratch
3. Test with minimal example first

## AI Performance Optimization

### Memory Management
```bash
# Monitor memory usage
watch -n 1 'free -h'

# For large datasets, consider:
export OMP_NUM_THREADS=1  # Reduce parallelization
ulimit -m 30000000        # Set memory limits
```

### CPU Optimization  
```bash
# Use all available cores for Python
export MKL_NUM_THREADS=$(nproc)
export NUMEXPR_NUM_THREADS=$(nproc)
```

## AI Support Resources

### Self-Diagnosis Tools
```bash
# Environment report
python -c "import platform, sys; print(f'OS: {platform.system()}'); print(f'Python: {sys.version}')"

# Dependency report
pip list | grep -E "(numpy|pandas|scipy|matplotlib|econ-ark)"
```

### Debug Information Collection
```bash
# Collect system info for debugging
uname -a > debug_info.txt
python --version >> debug_info.txt  
pip list >> debug_info.txt
echo "=== Error Log ===" >> debug_info.txt
tail -50 computation.log >> debug_info.txt
```

---

**AI Debugging Philosophy**: Start small, validate incrementally, and use selective execution to isolate issues. The computational workflow is robust but resource-intensive, so plan accordingly. 