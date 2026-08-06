# Cohort calibration schema (G-07)

**Status:** DRAFT (created by `plans/20260611_doloplus-orchestrator-spec.md` P1)
**Normative owner:** `HAFiscal-doloplus-orchestrator.md` §6 (prose); this file is the
machine-facing schema for (a) the on-disk discount-factor calibration file and
(b) the derived per-cohort calibration that the dolo-plus stage consumes.

---

## 1. Source file: `DiscFacEstim_CRRA_<rho>_R_<R>[_ESC].txt`

Location: `Code/HA-Models/FromPandemicCode/Results/` (legacy-regime copies under
`Results/_pgf_legacy/` when `HAFISCAL_PERMGROFAC_FIX=0`).

Resolution chain (highest precedence first), all in
`Parameters.py::return_parameters`:

1. `HAFISCAL_DISCFAC_FILE` (explicit path override),
2. `_permgrofac.py::permgrofac_calib_path` (regime subdirectory),
3. `_interpretation.py::resolve_path` (appends `_ESC` suffix for ESC runs;
   emits `[ESC calibration HAZARD]` on CDC fallback).

### 1.1 Line format

One Python-dict literal per education group (parsed with `eval` of each line in
`Parameters.py::return_parameters`), groups in order Dropout, Highschool, College,
followed by a free-text `Parameters: ...` provenance line that the parser ignores.

| key | type | meaning | constraint |
|---|---|---|---|
| `EducationGroup` | str | `"Dropout"` \| `"Highschool"` \| `"College"` | order fixed D, H, C |
| `beta` | float | center of the uniform β band | `0 < beta < GICmaxBetas[e]·1.05` (sanity) |
| `nabla` | float | half-width of the band (β ± ∇) | `nabla >= 0` |
| `GICx` | float | logit of the GIC shave factor | `GICfactor = exp(GICx)/(1+exp(GICx))` |

Current ESC production content (`DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt`,
post-BUG-047 re-estimation; verify before relying on copies of these numbers):

```
{'EducationGroup': 'Dropout',    'beta': 0.7383881538621202, 'nabla': 0.3036794349809335,  'GICx': 7.60040233450051}
{'EducationGroup': 'Highschool', 'beta': 0.9356346553255952, 'nabla': 0.07636292909005482, 'GICx': 7.60040233450051}
{'EducationGroup': 'College',    'beta': 0.9920427679956743, 'nabla': 0.02332098850169904, 'GICx': 7.60040233450051}
Parameters: R = 1.01, CRRA = 2.0, IncUnemp = 0.7, IncUnempNoBenefits = 0.5, Splurge = 0.26718066005582686
```

Note: logistic(7.60040233450051) = 0.999500 — the saved `GICx` encodes
`theGICfactor = 0.9995` (`EstimParameters.py`). The saved per-group `GICfactor`
**wins** over the module default at load time.

## 2. Cohort expansion: file → 21 stage problems

Deterministic expansion performed identically in `Simulate.py::Simulate` and
`welfare6_scenario.py::build_and_solve`; the stage (YAML) sees one calibration per
cohort `(e, b)`, `e ∈ {D, H, C}`, `b ∈ {0..DiscFacCount−1}`:

```
DiscFacCount = 7                                  # Parameters.py (1 for reduced runs)
atoms_e   = Uniform(beta_e − nabla_e, beta_e + nabla_e).discretize(DiscFacCount).atoms
beta_cap  = gic_capped_beta(e, GICfactor_e)       # EstimParameters.py::gic_capped_beta
          = GICmaxBetas[e] · GICfactor_e^CRRA     # GPF-shave (BUG-053); env escape
                                                  # HAFISCAL_GIC_SHAVE_ON_GPF=0 → β-shave
beta(e,b) = clip(atoms_e[b], 0.01, beta_cap)
```

### 2.1 Per-cohort fields handed to the stage

| field | varies by | source |
|---|---|---|
| `beta` | (e, b) | expansion above |
| `PermGroFac` (z-indexed, len J) | e (and §9 flag) | `income_process_sst.py::build_PermGroFac_micro(G_e, J, G_unemp)` |
| `MrkvArray` / conditional arrays | e (via Urate_e) | `Parameters.py::small_MrkvArray`, `make_cond_mrkv_arrays_*` |
| `IncShkDstn[z]` | e | manual assembly (`construct=False`), `Simulate.py::Simulate` / `welfare6_scenario.py::build_and_solve` |
| `pLogInitMean`, `pLogInitStd` | e | `EstimParameters.py` (log 6.2/11.1/14.5; 0.32/0.42/0.53) |
| `AgentCount` | (e, b) | `floor(AgentCountTotal·share_e·pmv_b)` (Simulate) or `floor(AgentCountTotal·share_e/DiscFacCount)` (welfare6) |
| `RNG seed` | (e, b) | sequential `n` + `HAFISCAL_SEED_OFFSET` (Simulate); `e·DiscFacCount + d + 10000·seed_offset` (welfare6) |
| shared scalars | — | `Rfree=1.01`, `CRRA=2.0`, `LivPrb=0.99375`, `T_age`, `Splurge` (scalar, NOT per-group; D-06) |

`data_EducShares = [0.093, 0.527, 0.38]` (`EstimParameters.py`).

## 3. Validation rules

A conforming calibration file/expansion MUST satisfy:

1. exactly 3 dict lines, `EducationGroup` order D, H, C;
2. all four keys present and float-parseable (besides the group label);
3. `0 < GICfactor < 1` after the logistic transform;
4. for every cohort, `beta(e,b) ≤ gic_capped_beta(e, GICfactor_e)` (cap atoms
   allowed to sit exactly at the cap — the College cap atom is expected and is the
   GPF = 0.9995 atom that sizes `HAFISCAL_TM_AMAX = 1300`);
5. Σ_b pmv_b = 1 per group; Σ_e share_e = 1;
6. matched-triple consistency: file suffix (`_ESC` or not) must agree with
   `HAFISCAL_INTERPRETATION`, and the directory with the `HAFISCAL_PERMGROFAC_FIX`
   regime (`_permgrofac.py::assert_regime` enforces at run time).

Spot-check command:

```bash
python3 - <<'EOF'
import math
for line in open('Code/HA-Models/FromPandemicCode/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt'):
    if line.startswith('{'):
        d = eval(line)
        print(d['EducationGroup'], d['beta'], 1/(1+math.exp(-d['GICx'])))
EOF
```
