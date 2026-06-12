# Version Comparison Test Suite

Component-level numerical equivalence tests between HARK 0.14.1 and 0.17.0
for all 5 computational steps of `reproduce.sh --comp full`.

## Architecture

Two Docker containers provide isolated Python environments:

- **hafiscal-014-arm** (Python 3.9 + econ-ark==0.14.1): runs the HAFiscal
  codebase at commit `94c02b07` (the 0.14.1-compatible baseline)
- **hafiscal-017** (Python 3.11 + HARK from `ConsAggIndMarkovModel` branch):
  runs the current HAFiscal-Latest codebase

Each test script is mounted into both containers at `/tests/` and imports
from the version-specific HAFiscal code mounted at `/workspace/`. The same
test script runs in both environments because it delegates to the mounted
application code (which handles its own HARK API differences internally).

## Quick Start

```bash
# 1. Prepare the 0.14.1 codebase clone
git clone /path/to/HAFiscal-Latest /tmp/HAFiscal-014
cd /tmp/HAFiscal-014 && git checkout 94c02b07
# Copy converged result files from the current version
cp /path/to/HAFiscal-Latest/Code/HA-Models/Results/DiscFacEstim* Code/HA-Models/Results/
cp /path/to/HAFiscal-Latest/Code/HA-Models/Target_AggMPCX_LiquWealth/Result* \
   Code/HA-Models/Target_AggMPCX_LiquWealth/

# 2. Build Docker images
cd /path/to/HAFiscal-Latest/reproduce/version-comparison
docker build -t hafiscal-014-arm -f Dockerfile.014 .
docker build -t hafiscal-017 -f Dockerfile.017 .

# 3. Run all tests via orchestrator
python orchestrator.py

# Or run a single step
python orchestrator.py --step 1
```

## Test Steps

| Step | Script | What it tests | Runtime |
|------|--------|---------------|---------|
| 1 | `test_step1_splurge.py` | Splurge factor estimation (FagerengObjFunc) | ~5 min |
| 2 | `test_step2_discfac.py` | Discount factor estimation (betas_obj_func_educ) | ~30-60 min |
| 3 | `test_step3_robustness.py` | Robustness with Splurge=0 | ~30-60 min |
| 4 | `test_step4_hank_sam.py` | HANK-SAM Jacobians (reduced grid) | ~10-20 min |
| 5 | `test_step5_policy.py` | Policy simulations (Reduced_Run) | ~15-30 min |

## Expected Results

**Step 1 (Splurge):** Differences of ~10^-6 are expected because this step uses
`multi_thread_commands` (true parallel execution), which causes non-deterministic
thread ordering and RNG state divergence. Both versions use the same parallel
strategy, so the optimizer converges to very similar but not bitwise-identical
results.

**Steps 2-3 (DiscFac):** These use `multi_thread_commands_fake` (serial execution)
with full RNG synchronization patches in the 0.17.0 code. Combined with the
`math.erf` monkey-patch (replacing `scipy.special.erfc`), differences should be
at machine epsilon (~10^-15) or very close.

**Steps 4-5:** Expected to show small differences depending on solver convergence
behavior and parametric grid construction.

## Converged Parameter Values

The test scripts evaluate objectives at known converged values to ensure both
versions start from identical states:

**Splurge estimation:**
- Converged: splurge=0.24611, beta=0.96755, nabla=0.05781

**Discount factor estimation:**
| Education | beta | nabla | GICx |
|-----------|------|-------|------|
| Dropout | 0.7368 | 0.2964 | 6.152 |
| HighSchool | 0.9248 | 0.0779 | 4.191 |
| College | 0.9821 | 0.0147 | 6.278 |

## Files

| File | Purpose |
|------|---------|
| `Dockerfile.014` | Python 3.9 + HARK 0.14.1 environment |
| `Dockerfile.017` | Python 3.11 + HARK 0.17.0 (PR branch) |
| `orchestrator.py` | Master test runner and comparison engine |
| `compare_utils.py` | JSON comparison with configurable tolerances |
| `test_step{1-5}_*.py` | Per-step test scripts |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HAFISCAL_014_IMAGE` | `hafiscal-014-arm` | Docker image for 0.14.1 |
| `WORKSPACE` | `/workspace` | Mount point inside containers |

## Relationship to Other Documentation

- `docs/HARK_UPGRADE_REPORT.md`: technical details of 0.14.1 -> 0.17.0 changes
- `docs/HARK_UPGRADE_LESSONS_LEARNED.md`: process lessons from the upgrade
- `Code/HA-Models/rng_synchronized_consumer.py`: RNG synchronization patches
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`: math.erf monkey-patch
