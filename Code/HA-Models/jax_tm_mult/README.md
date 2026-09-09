# jax_tm_mult — JAX-GPU TM multiplier kernel (dev)

Plan: ../../../plans/20260604_jax_gpu_tm_multiplier_kernel_plan.md

## Workflow segregation rules (while the BUG-047 re-est + A/B multiplier comparison runs)
- **GPU-only compute** here; the current workflow is CPU-only. Don't add CPU-heavy steps that
  starve the live Baseline runs — validate at HS_Only scale, `nice`, cap workers.
- **New files only.** Do NOT edit tm_methods.py / AggFiscalMAIN_reduced.py / Simulate.py /
  Parameters.py (the current workflow imports them) until A/B is done. No branch switch.
- **Never touch** Results/DiscFacEstim_*_ESC.txt (live calib) or Figures/Baseline_perm*/.
  Read a frozen calib snapshot; write /tmp/jaxtm_dev/ + FIGS_SUFFIX=_jaxdev + HS_Only/Reduced_Run.
- Logs/scratch: /tmp/jaxtm_dev/.
