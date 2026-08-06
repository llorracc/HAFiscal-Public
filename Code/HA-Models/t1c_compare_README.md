# T1c decay-form comparison harness (`t1c_compare_decay_forms.py`)

Baseline rung of the `HAFISCAL_PF_DECAY_EXTRAP` exp -> powerlaw switch cascade
(`plans/2026-07-05_powerlaw-switch-test-plan.md`; RECONCILED-002). Compares the
Step-5a Baseline TM-a multiplier outputs written under the two perfect-foresight
decay-extrapolation forms:

| form | dir |
|---|---|
| `exp` (legacy exponential) | `FromPandemicCode/{Figures,Tables}/Baseline_pfexp/` |
| `powerlaw` (`PowerLawDecayLinearInterp`) | `FromPandemicCode/{Figures,Tables}/Baseline_pfpl/` |

The Baseline **College GIC-cap discount-factor atom** (the type with the largest
ergodic wealth tail, `agg.A_nrm` ~ 22) is the only subpopulation that can
non-vacuously feel the tail form — it is the point of this leg.

## Invoke (once `Baseline_pfpl` completes)

```bash
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
cd /home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models
$PY t1c_compare_decay_forms.py \
    FromPandemicCode/Figures/Baseline_pfexp \
    FromPandemicCode/Figures/Baseline_pfpl
```

With no positional args it defaults to exactly those two Figures dirs. The
sibling `Tables` dir for each is auto-derived (`Figures` -> `Tables`); override
with `--tables-a` / `--tables-b`. Exit code 0 = PASS, 1 = FAIL.

**Self-compare validation** (mechanics check, safe to run now — pure file reads,
no heavy compute): pass the same dir twice. Because `dir_a == dir_b` the script
switches on a STRICT-ZERO assertion — every numeric leaf diff must be exactly
`0.0`. Verified 2026-07-07: all 29 result files load as pickles, all leaf diffs
`0.000e+00`, verdict PASS, exit 0.

```bash
$PY t1c_compare_decay_forms.py \
    FromPandemicCode/Figures/Baseline_pfexp \
    FromPandemicCode/Figures/Baseline_pfexp
```

## What it checks

1. **Recursive numeric-leaf diff** over every result file present in both Figures
   dirs. The `*.csv` files are Python **pickles** (magic byte `0x80`), not text —
   the loader detects this per file and falls back to pandas/`genfromtxt` for any
   genuine text CSV. Handles scipy-sparse `TranMatrix` (`.toarray()`), HARK
   distribution objects (`.pmv`/`.atoms`), nested dict/list/object trees, treats
   `NaN==NaN` as a zero diff (the all-NaN UI multiplier column), and **skips
   non-numeric leaves** (str/None/bool/object-dtype). Reports **absolute and
   relative** max diffs (relative guards catastrophic cancellation on tiny values).
2. **Per-type `TranMatrix` decomposition** from `base_results.csv` `_type_results`
   (21 cohorts): `nnz(D)`, `max|Dp|`, exp-chain **stationary mass on the differing
   columns** (power iteration, column-stochastic `pi = T@pi`), and `max|Dpi|`
   (stationary-dist diff). The GIC-cap College atom (max `A_nrm`) is flagged.
3. **Multiplier gate (AUTHORITATIVE)** `|Delta| > 0.001` on the **last-element**
   AD cumulative multiplier (the 10y-horizon headline value) from
   `C_Multiplier_Baseline_Results.csv` — `C_Multiplier_Rec_Check_AD` and
   `C_Multiplier_Rec_TaxCut_AD`. `C_Multiplier_UI_Rec_AD` is all-NaN by
   construction (missing `NPV_AddInc_UI`) and is **excluded**. The exp leg's
   verified last-element values are Check=1.224638, TaxCut=1.007551. The
   whole-array `max|Delta|` is also reported per key as a superset diagnostic (a
   warning fires if it trips on a non-final quarter while the headline stays ok).
   This pickle is written at `Output_Results.py:308`, BEFORE the crash (see below),
   so it exists for both legs. It is the sole gate.
4. **Tex — INFORMATIONAL ONLY, never part of the verdict.** The exp/pl legs
   **crash at `Output_Results.py:346`** (missing `Results_HANK` object) BEFORE
   `Multiplier.tex` is written at line 482, so `Tables/Baseline_pf{exp,pl}/` are
   empty and no tex is emitted for either leg. The harness therefore does **not**
   build the gate on the tex (that was the T1/T1b pattern; it does not apply here).
   If some later run ever emits the tex, the harness prints a diff for information
   but it never affects PASS/FAIL.

## Output columns

Per-file table: `file`, `fmt` (`pickle`/`text-csv`), `leaves` (numeric leaves
compared), `max|abs|`, `max|rel|`, path `at` the worst leaf.
TranMatrix table: `type` (0..20), `A_nrm`, `nnz(D)`, `max|Dp|`, `statmass@D`
(stationary mass on differing cols), `max|Dpi|`.

## Expected a-priori result

**PASS.** From the cascade (T1b Reduced_Run: College beta=0.98 differed on ~1e4
transition entries carrying ~all its stationary mass, integrated multiplier
effect >10 orders below the gate), the Baseline GIC-cap atom's tail mass
(<= ~1e-4) times a ~1-2% cFunc delta gives a multiplier shift on the order of
**~1e-6 — three orders under the 0.001 gate**. If the gate TRIPS, escalate to the
owner immediately: the 2026-07-05 flip (commit `e5c0b602`, RECONCILED-002) would
need revisiting.
