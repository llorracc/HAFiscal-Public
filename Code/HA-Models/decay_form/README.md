# decay_form — numerical evidence: the buffer-stock consumption-function gap decays as a POWER LAW

Reproducible numerics behind the derivation in
`conclusions_private/2026-06-24_buffer-stock-decay-power-law-derivation.md`.

The gap `g(m) = κ̲·(m+h) − c(m)` between the infinite-horizon buffer-stock consumption function and its
linear perfect-foresight asymptote decays as a **power law** `m^(−q)` (sub-exponential), NOT
exponentially. Two-channel structure, validated by two independent solvers:

    g(m) = A·m^(−q*) + B·m^(−1) + (faster),    leading exponent = min(1, q*),

- `q* = ln(R/Γ)/ln(1/Þ_Γ)` (no permanent shock), the Kesten–Goldie root of `E[ψ^(1+q)] = (R/Γ)·Þ_Γ^q`.
- `m^(−1)`: the income-lower-tail channel (exponent robust; amplitude income-discretization-dependent).

## Scripts (run with the HAFiscal venv)

- **`nail_hark.py`** — HARK 0.17.1 `IndShockConsumerType`, deep grid; two-term decomposition (q\* fixed)
  + local log-log slope + σ-sweep. `nail_hark_out.txt` is a saved run.
- **`egm_independent.py`** — independent from-scratch numpy EGM (no HARK); cross-check.
- **`harness_powerlaw_extrap.py`** — validation harness for the HARK-PR power-law extrapolator
  (`LinearInterp(decay_extrap_form='powerlaw')`, worktree `HARK-pr-aggshock-pf-decay`): per-calibration
  `Q_emp = B·(m_top+h)` vs theory `q*`/`min(1,q*)` across grid depths (shows the crossover migration),
  plus depth-40 exp-vs-powerlaw error tables against deep-grid truth. `harness_powerlaw_extrap_out.txt`
  is a saved run (2026-07-05): power-law beats exponential in every case; the exponential destroys
  88–100% of the true gap at 20× the grid top, the power law keeps 43–99% of it.

Key result (both solvers agree): leading exponent `min(1, q*)` — case `Γ=1.01` → m⁻¹ (q\*=2.72>1,
crossover m≈89); impatient `Γ=1.0,R=1.01,β=0.90` → m^(−q\*)=m^(−0.21) (q\*<1), measured −0.209 vs
predicted 0.2086 (0.2%). Local log-log slope CONVERGES (power law); does not diverge (exponential).

```bash
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
$PY Code/HA-Models/decay_form/nail_hark.py
$PY Code/HA-Models/decay_form/egm_independent.py
```
