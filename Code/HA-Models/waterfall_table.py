#!/usr/bin/env python3
"""Waterfall table (owner-approved 2026-08-26): published -> + bug fixes -> + certified numerics -> + improvements ->
+ discretionary, one change per column, multipliers (3 decimals, from Multiplier tables) and welfare-6 cells (S-seed
means +- SE from welfare6_parallel_summary.json). Arms are directories under FromPandemicCode/Tables/.

Usage:
  python waterfall_table.py [--order ORDER] [--out FILE.md] [--tex FILE.tex] [--tables DIR]
  python waterfall_table.py --format memo [--out FILE.md] [--tables DIR]    # the revision memo's section 1.2 block
Columns (defaults; override with --arm NAME=5a_dir:welfare_glob):
  published        ../HAFiscal-QE tables (welfare: the published cells; no seeds)
  +bug fixes       Baseline_ac_legacy (5a) : Baseline_ac_legacy_nshuf_seed*      (as-corrected, paper's engine)
  +numerics        Baseline_ac_pkg   (5a) : Baseline_ac_pkg_seed*                (as-corrected, certified package)
  +improvements & modifications  Baseline_uiA (5a) : Baseline_uiA_seed*  (default world, paper's UI policy; the age
                   cap and perm-shocks modifications are in this column until the improvements-only column exists)
  +the UI policy   Baseline_uiB      (5a) : Baseline_uiB_seed*                   (default world, history policy)

--order method-first (owner re-framing 2026-08-26 22:50: model changes that ENABLE the exact solution first, then the
solution method; plans/20260826-2100h_presenting-the-revision_plan.md §5d):
  published -> +corrections (paper's numerics) -> [+no age wall (matched calibration; perm shocks still off)] ->
  +model changes (paper's numerics) -> +certified package -> +improvements -> +the UI policy
  "paper's numerics" = legacy 4-state encoding, non-shuffled HARK MC, own AD loops, equal-weight panel (Baseline_uiL*).
  --split-model-changes adds the bracketed column (Baseline_uiL_permoff*, m5 + xubuntark P10; MATCHED to the committed
  betas, which BUG-095 showed are perm-off estimates -- the default-world columns are the unmatched pair).
  Multipliers are the exact TM evolution's in EVERY column (the revision's stratified-MC engine reproduced them within 0.5 % no-AD / 1-3 % AD
  in the capped world at the Reduced_Run scale -- Test C2, 2026-08-26, plans_local/20260824-1530h_shared-solved-policy-
  store_plan.md -- and cannot resolve the uncapped E[p] at feasible N: BUG-092, sampler-limit E[p] ~ N^-0.2).

--format memo (C6 of plans/20260828-1130h_infrastructure-lessons-implementation_plan.md, as reshaped by the prior-art
review of 2026-08-28: the format rulings live HERE and in the presenting plan's section 5e -- there is no style doc):
prints EXACTLY the fenced block of section 1.2 of conclusions_private/2026-08-27_revision-memo_v3_original-code.md
(order original-code). Code/HA-Models/memo_tables.py injects it between the memo's
`<!-- BEGIN generated: chain-table -->` / `<!-- END generated: chain-table -->` markers and test_memo_tables.py fails
the suite when the memo's block and the regenerated one differ. Owner rulings of 2026-08-28 morning (memo commits
bd8f30b3 06:59, d7ae62a9 07:31, aedd084c 07:45):
  * one monospaced ```text block: a label column plus one column per chain step under a short header;
  * rows = the three 10-year AD multipliers (the exact TM evolution has no draws, so no SE row), then the three
    recession AD welfare cells (check_rec_AD / ui_rec_AD / taxcut_rec_AD), each followed by an UNLABELED row carrying
    the across-seed SE in parentheses (std over the S seeds / sqrt(S)); then, set apart by a second rule line, the
    entire-run wall clock;
  * THREE decimals for every estimate and every SE (supersedes the "two decimals" note of section 5e's 08:30 entry);
  * numeric cells right-justified to the header's width; an estimate carries one pad space on its right and an SE
    none, so the decimal points of an estimate and of its SE sit in the same character column; a column with no SE
    (published: one panel) leaves the SE cell blank, not "n/a".
  Cells with no machine source in this repo -- the published column, the entire-run walls -- come from the explicit
  tables PUBLISHED_* and WALL_* below, each naming the record it was taken from.
"""
import argparse, glob, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FPC = os.path.join(HERE, "FromPandemicCode")
T = os.path.join(FPC, "Tables")
QE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "HAFiscal-QE", "Code", "HA-Models", "FromPandemicCode", "Tables", "CRRA2"))
CELLS = ["check_norec", "ui_norec", "taxcut_norec", "check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]
MROWS = [("no AD", "10y-horizon Multiplier (no AD effect)"), ("AD", "10y-horizon Multiplier (AD effect)"),
         ("1st-round AD", "10y-horizon (1st round AD effect only)"), ("outlay share in recession", "Share of policy expenditure during recession"),
         ("cons.-stimulus share in recession", "Share of policy cons. stimulus during recession")]
ORDERS = {}
ORDERS["category"] = DEFAULT_ARMS = [("published", None, None),
                ("+bug fixes (paper's engine)", "Baseline_ac_legacy", "Baseline_ac_legacy_nshuf_seed*"),
                ("+certified numerics", "Baseline_ac_pkg", "Baseline_ac_pkg_seed*"),
                ("+improvements", "Baseline_ac_impr", "Baseline_ac_impr_seed*"),           # as-corrected + every improvement (P9)
                ("+modifications (age cap, perm shocks; paper's UI policy)", "Baseline_uiA", "Baseline_uiA_seed*"),
                # 2026-08-29 (owner ruling 2026-08-28): the earnings-phase state -- growth ends with hazard 1/120
                # (Gini 0.71 -> 0.48 = the SCF), re-estimated (S1 -> S2 under the Gamma = 1 cap), BUG-102 fixed in
                # the battery's replay path. The column of record of the default world since the install.
                ("+earnings phase (re-estimated)", "Baseline_phase", "Baseline_phase_seed*"),
                ("+the UI policy (history)", "Baseline_uiB", "Baseline_uiB_seed*")]
# Method-first order (§5d). The two optional columns are inserted by flags (see main()).
ORDERS["method-first"] = [("published", None, None),
                          ("+corrections (paper's numerics)", "Baseline_ac_legacy", "Baseline_ac_legacy_nshuf_seed*"),
                          ("+model changes (paper's numerics)", "Baseline_uiL", "Baseline_uiL_nshuf_seed*"),
                          ("+certified package", "Baseline_uiA", "Baseline_uiA_nshare_seed*"),
                          ("+improvements", "Baseline_uiA", "Baseline_uiA_seed*"),
                          ("+earnings phase (re-estimated)", "Baseline_phase", "Baseline_phase_seed*"),   # 2026-08-29
                          ("+the UI policy (history)", "Baseline_uiB", "Baseline_uiB_seed*")]
# BUG-095 (2026-08-26 23:50): the committed default-world betas ARE perm-off estimates (the production Step-2 engine
# hard-coded the point mass), so the runtime perm-off arm is the MATCHED one and the default-world columns are the
# unmatched pair until the owner rules on re-estimation. The former "matched" arm (a re-estimation under perm off) was
# a no-op and is withdrawn.
SPLIT_COL = ("+no age wall (perm shocks still off; matched -- BUG-095)", "Baseline_uiL_permoff", "Baseline_uiL_permoff_nshuf_seed*")
# OWNER PROTOCOL 2026-08-27 (plan section 5e): changes relative to the ORIGINAL code and model, each on the current
# certified machinery (exact TM evolution, ATI, the certified package; own AD loops, HARK engine, equal-weight panel until
# the improvements column). Start column = the QE calibration + conventions (CDC, legacy PermGroFac solver regime,
# published tail extrapolation AND solve grid 40/48 (HAFISCAL_PF_DECAY_Q=slope; BUG-061/062), the QE beta-atom clip rule (HAFISCAL_GIC_SHAVE_ON_GPF=0 -- today's rule moves the QE
# high-school top atom 0.99045 -> 0.98195, BUG-053 addendum), the published tax-cut construction
# (HAFISCAL_LEGACY_TAXCUT_ATOM=1, BUG-023), cap 200, shocks off, the paper's UI window) run by today's code.
# OWNER RULING 2026-08-27 16:30: the age cap's removal is a CORRECTION (the published code estimated without a cap and
# simulated with one -- inconsistent), reported after its re-estimation; so the corrections column is the uncapped
# re-estimated world (5a Baseline_uiL_permoff, battery Baseline_nocap_pkg). The capped as-corrected arm (ac_pkg) is now an
# intermediate row of the breakdown table ("corrections other than the cap").
ORDERS["original-code"] = [("published", None, None),
                           # 2026-08-29 (owner ~10:45): the original model RE-ESTIMATED on the current machinery -- its Step 1, Step 2
                           # and Step 4 run by the revision's estimators under the paper's conventions (CDC, the published solver
                           # factor / extrapolation / clip / grid, shocks off), then 5a + 5b with T_age = 200 and the BUG-023
                           # construction (spine8, rerun_logs/orig_reest_20260829). The paper-calibration arm Baseline_orig_typo
                           # (the 0.3 % reproduction of the published numbers) stays in the record as the machinery validation.
                           ("original model, re-estimated on the current certified machinery", "Baseline_orig_reest", "Baseline_orig_reest_seed*"),
                           # 2026-08-29 (owner ruling 08:35, plan 20260829-0845h): the corrections column carries the BUNDLE --
                           # no maximum age WITH the growth rates rescaled by lambda = 0.44 (the SCF Gini 0.50) and re-estimated;
                           # every later column sits on the same lambda calibration. The earnings-phase column (installed 06:16,
                           # demoted 08:35) stays in the record (artifacts_20260826_uiAB/waterfall_original-code_20260829-phase.md).
                           ("+corrections to the original code (incl. no age cap + growth rescaled to the SCF Gini, re-estimated)", "Baseline_lam_ac", "Baseline_lam_ac_seed*"),
                           ("+permanent shocks in unemployment", "Baseline_lam", "Baseline_lam_nshare_seed*"),
                           ("+improvements (welfare method)", "Baseline_lam", "Baseline_lam_seed*")]
# OWNER RULING 2026-08-27 17:00: the UI policy is reported SEPARATELY at the end (not a chain column; no outlay-share row).
# The chain shows only the three multiplier rows; `--order ui-policy` gives the separate two-column report.
# 2026-09-04: the window row reads the PRODUCTION Baseline (Tables/Baseline{,_seed*}). `Baseline_uiA`
# was the 2026-08-26 A/B experiment's name for the window arm; under "window everywhere" (owner
# 2026-08-28) the production Baseline is that arm, and it is the one kept on the current calibration.
ORDERS["ui-policy"] = [("the revised model under the paper's UI policy", "Baseline", "Baseline_seed*"),
                       ("the revised model under the history-consistent UI policy", "Baseline_uiB", "Baseline_uiB_seed*")]
ORDER_MROWS = {"original-code": ("no AD", "AD", "1st-round AD")}
# 2026-08-30 (owner charge 2026-08-29 19:25, plan 20260829-1935h): the ergodic-conversion chain. Every column on the last-and-best
# machinery; the columns differ only in the PAPER's content. A = the original model re-estimated by the paper's OWN procedure (MC
# objectives, the paper's read-outs/arithmetic/tolerances; its bugs in; the MC multiplier engine, three seeds -> the 5a dir is a
# per-seed GLOB averaged by memo_inputs); B = + the ergodic/infinite-horizon conversion (no wall, lambda 0.44, permanent shocks,
# the ergodic toolkit, stratified MC; the paper's bugs still in); C = + the paper's bugs fixed; D = + the improvements (default world,
# history-consistent UI policy). Tables: Baseline_orig_reest_mc_s<seed> (5a per seed), Baseline_chain{B,C,D}[_seed*].
ORDERS["ergodic-conversion"] = [("published", None, None),
                                ("original model, the paper's own procedure (MC)", "Baseline_orig_reest_mc_s*", "Baseline_orig_reest_mc_seed*"),
                                ("+ the ergodic/infinite-horizon conversion", "Baseline_chainB", "Baseline_chainB_seed*"),
                                ("+ the paper's bugs fixed", "Baseline_chainC", "Baseline_chainC_seed*"),
                                ("+ improvements", "Baseline_chainD", "Baseline_chainD_seed*")]
# Appendix table (owner-approved, condensed): the three AD multipliers + the six recession welfare cells.
APPX_MULT = "AD"
APPX_CELLS = ["check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]
CELL_LABEL = {"check_rec": r"$\mathcal{W}$(check, Rec)", "ui_rec": r"$\mathcal{W}$(UI, Rec)", "taxcut_rec": r"$\mathcal{W}$(tax cut, Rec)",
              "check_rec_AD": r"$\mathcal{W}$(check, Rec, AD)", "ui_rec_AD": r"$\mathcal{W}$(UI, Rec, AD)", "taxcut_rec_AD": r"$\mathcal{W}$(tax cut, Rec, AD)"}


def appendix_tex(arms, mt, wt):
    """LaTeX booktabs table: columns = the chain's steps; rows = AD multipliers (Check / UI / TaxCut) + six welfare cells."""
    cols = [n for n, _, _ in arms]
    L = [r"\begin{tabular}{@{}l" + "c" * len(cols) + r"@{}}", r"\toprule",
         "row & " + " & ".join(cols) + r" \\ \midrule",
         r"\multicolumn{%d}{@{}l}{\emph{10-year multiplier with AD effects}} \\" % (len(cols) + 1)]
    for j, pol in enumerate(("Stimulus check", "UI extension", "Tax cut")):
        vals = []
        for n in cols:
            v = mt[n].get(APPX_MULT, ["—", "—", "—"])
            vals.append(v[j] if j < len(v) else "—")
        L.append(f"\\quad {pol} & " + " & ".join(vals) + r" \\")
    L.append(r"\multicolumn{%d}{@{}l}{\emph{welfare-6 cells (mean over seeds; SE in parentheses)}} \\" % (len(cols) + 1))
    for c in APPX_CELLS:
        vals = []
        for n in cols:
            m, se, S = wt[n].get(c, (float("nan"), float("nan"), 0))
            vals.append("—" if not np.isfinite(m) else (f"{m:.2f}" if S == 0 else f"{m:.3f} ({se:.3f})"))
        L.append(f"\\quad {CELL_LABEL[c]} & " + " & ".join(vals) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def mult_rows(path):
    out = {}
    if not path or not os.path.exists(path):
        return out
    for line in open(path):
        for key, label in MROWS:
            if line.strip().startswith(label):
                nums = re.findall(r"([0-9]+\.[0-9]+)", line)
                out[key] = nums[:3]
    return out


def mult_rows_avg(td, d5):
    """mult_rows over a 5a dir pattern: a literal dir as before; a GLOB (column A's per-seed MC multiplier tables) -> the across-seed
    mean per row key (three decimals), with the seed count in ['n']. Empty when nothing matches."""
    if "*" not in d5:
        return mult_rows(os.path.join(td, d5, "Multiplier_candidate.tex"))
    tabs = [mult_rows(os.path.join(d, "Multiplier_candidate.tex")) for d in sorted(glob.glob(os.path.join(td, d5)))]
    tabs = [t for t in tabs if len(t.get("AD", [])) >= 3]
    if not tabs:
        return {}
    out = {"n": len(tabs)}
    for key in set().union(*[t.keys() for t in tabs]):
        cols = [t[key] for t in tabs if key in t and len(t[key]) >= 3]
        if cols:
            out[key] = [f"{np.mean([float(c[j]) for c in cols]):.3f}" for j in range(3)]
    return out


def welfare(globpat, tables_dir=None):
    files = sorted(glob.glob(os.path.join(tables_dir or T, globpat, "welfare6_parallel_summary.json"))) if globpat else []
    rows = [json.load(open(f))["welfare6"] for f in files]
    res = {}
    for c in CELLS:
        v = np.array([float(r[c]) for r in rows if r.get(c) is not None], float)
        v = v[np.isfinite(v)]
        res[c] = (v.mean(), v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else float("nan"), len(v)) if len(v) else (float("nan"), float("nan"), 0)
    return res


def published_welfare(qe_dir=None):
    p = os.path.join(qe_dir or QE, "welfare6.tex")
    cells = {}
    if os.path.exists(p):
        rows = [re.findall(r"([0-9]+\.[0-9]+)", l) for l in open(p) if "mathcal" in l]
        order = [["check_norec", "ui_norec", "taxcut_norec"], ["check_rec", "ui_rec", "taxcut_rec"], ["check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]]
        for r, names in zip(rows, order):
            for name, val in zip(names, r):
                cells[name] = (float(val), float("nan"), 0)
    return cells


# ---------------------------------------------------------------------------------------------------------------
# --format memo: the revision memo's section 1.2 chain table (layout rulings: module docstring).
MEMO_ORDER = "original-code"
MEMO_HEADERS = ["published", "new machinery", "+ corrections", "+ perm. shocks", "+ welfare method"]   # one per ORDERS[MEMO_ORDER] arm
MEMO_LABEL_WIDTH = 28    # the memo's label column: its longest label ("Multiplier: stimulus check", 26) + 2
MEMO_POLICIES = [("stimulus check", 0, "check_rec_AD"), ("UI extension", 1, "ui_rec_AD"), ("tax cut", 2, "taxcut_rec_AD")]
MEMO_WALL_LABEL = "Wall clock, entire run"
# The published column has no source inside this repo: QE 17(3), the sibling checkout HAFiscal-QE/Code/HA-Models/
# FromPandemicCode/Tables/CRRA2/ -- Multiplier.tex row "10y-horizon Multiplier (AD effect)" and welfare6.tex row
# W(policy, Rec=1, AD=1) (two decimals in the paper, printed at three). check_published() verifies these constants
# against that checkout whenever one is found (resolve_qe_dir()).
PUBLISHED_AD_MULT = ("1.228", "1.209", "0.975")                                        # check / UI / tax cut
PUBLISHED_WELFARE_AD = {"check_rec_AD": 1.35, "ui_rec_AD": 2.13, "taxcut_rec_AD": 1.11}
# The entire-run wall clock -- the memo's row of record (commit bd8f30b3, 2026-08-28 06:59) -- as minutes per stage:
# (Steps 1 + 2 + 4, Step 5a, Step 5b per seed, seeds). Sources: Code/HA-Models/README.md, the "2026-08-26 measured
# (dell, sharing default, ...)" runtime bullets -- Step 1 23, Step 2 40, Step 4 10, Step 5a 43 (warm policy store),
# Step 5b 13 min/seed for an own-AD-loop battery and 9.4 under sharing -- at the memo's S = 5 seeds. The new-machinery
# column runs on the paper's calibration (no estimation steps) and carries the original-model arm's dell launcher
# stamps from conclusions_private/artifacts_20260826_uiAB/timing_20260827.md (timing_table.py's output, row `orig`:
# 5a 30 min + five seeds x 13 min -- the pre-bd8f30b3 row's own words, "multipliers 30 min + five welfare seeds x 13
# min"). C6 (2026-08-28) found that column's NUMBERS are the later `orig_typo` arm (P28r), whose own stamps read 5a 47 min
# + five welfare seeds 26+13+13+14+13 = 79 min = 2.1 h; OWNER RULING 2026-08-28 12:20: "use 2.1 h" -- the row now carries
# the orig_typo arm's stamps (47 min + 5 x 15.8 min).
WALL_STAGES_MIN = {# ONE convention (owner question 2026-08-29 14:05 -- "why does + perm. shocks increase the time?": it does not; the
                   # 13:44 row had mixed three machines and a cold policy store): dell-equivalent stage minutes, the SAME battery cost
                   # for the same battery. Estimation: each column's own stamps (dell). 5a: the dell stamp of the column's 5a where it
                   # ran on dell (the lambda 5a, 61 min; the as-corrected 5a took 45 on the M5 and is carried at dell's 61), else the
                   # measured one (the re-estimated original's 5a: 55 min on ccarroll). 5b per seed, WARM store (the first seed's cold
                   # fill is a one-off): own-AD-loop battery 13.0 (dell, 2026-08-26 runtime bullet; today's warm Mac seeds 8-9 min),
                   # sharing 10.4 (dell today: 12 + 10 + 10 + 10 + 10). The "+ perm. shocks" step changes no computation.
                   "new machinery":    (4 + 51 + 11,  55, 13.0, 5),
                   "+ corrections":    (14 + 30 + 10, 61, 13.0, 5),
                   "+ perm. shocks":   (14 + 30 + 10, 61, 13.0, 5),
                   "+ welfare method": (14 + 30 + 10, 61, 10.4, 5)}
WALL_PUBLISHED = "4–5 d"   # QE README: "full computation 4-5 days" on the paper's Apple M2 (timing_20260827.md, record section)
# --format memo --order ergodic-conversion: its headers and its wall row (measured stage stamps; the box named when not dell).
MEMO_HEADERS_EC = ["published", "original (MC)", "+ conversion", "+ bug fixes", "+ improvements"]
WALL_MEASURED_EC = {"original (MC)": "≈ 30 h/seed (MC)", "+ conversion": "1.7 h (m5)", "+ bug fixes": "2.8 h (ccarroll)", "+ improvements": "1.1 h (m5, on C's estimation)"}
def wall_clock_cell_ec(header):
    return WALL_PUBLISHED if header == "published" else WALL_MEASURED_EC.get(header, "—")


class MissingInputs(RuntimeError):
    """An arm table the memo block needs is absent from the resolved Tables root (the arm tables are untracked results)."""


def _main_checkout():
    """Root of the main working tree (None outside git); differs from REPO_ROOT inside a linked worktree."""
    try:
        out = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None
    return os.path.dirname(os.path.abspath(os.path.join(HERE, out)))


def resolve_tables_dir(explicit=None, arms=None):
    """Tables root holding the arms: --tables; else this checkout's FromPandemicCode/Tables; else -- from a linked
    worktree -- the main checkout's, since the arm tables are untracked results that live where the runs were made."""
    if explicit:
        return explicit
    need = [d for _, d, _ in (arms if arms is not None else ORDERS[MEMO_ORDER]) if d]
    cands = [T]
    main_root = _main_checkout()
    if main_root and os.path.normpath(main_root) != REPO_ROOT:
        cands.append(os.path.join(main_root, "Code", "HA-Models", "FromPandemicCode", "Tables"))
    for c in cands:
        if need and all(os.path.isdir(os.path.join(c, d)) for d in need):
            return c
    return T


def resolve_qe_dir():
    """The sibling HAFiscal-QE checkout's CRRA2 tables, next to this checkout or to the main one; None if absent."""
    cands = [QE]
    main_root = _main_checkout()
    if main_root:
        cands.append(os.path.join(os.path.dirname(main_root), "HAFiscal-QE", "Code", "HA-Models", "FromPandemicCode", "Tables", "CRRA2"))
    return next((c for c in cands if os.path.isdir(c)), None)


def check_published(qe_dir=None):
    """Verify PUBLISHED_* against the QE checkout's tables: False when no checkout is found, raises on a mismatch."""
    qe = qe_dir or resolve_qe_dir()
    if not qe:
        return False
    got_m = tuple(mult_rows(os.path.join(qe, "Multiplier.tex")).get("AD", ()))
    got_w = {c: published_welfare(qe).get(c, (float("nan"),))[0] for c in PUBLISHED_WELFARE_AD}
    if got_m != PUBLISHED_AD_MULT or any(got_w[c] != v for c, v in PUBLISHED_WELFARE_AD.items()):
        raise RuntimeError(f"PUBLISHED_* constants disagree with the QE tables in {qe}: multipliers {got_m} vs "
                           f"{PUBLISHED_AD_MULT}; welfare {got_w} vs {PUBLISHED_WELFARE_AD}")
    return True


def memo_arms(overrides=()):
    """ORDERS[MEMO_ORDER] with --arm NAME=5a_dir:welfare_glob overrides applied IN PLACE (the column order is the memo's)."""
    arms = list(ORDERS[MEMO_ORDER])
    for spec in overrides:
        name, rest = spec.split("=", 1); d5, wg = rest.split(":", 1)
        at = [i for i, x in enumerate(arms) if x[0] == name]
        if not at:
            raise SystemExit(f"--arm {name!r}: not a column of order {MEMO_ORDER}: {[x[0] for x in arms]}")
        arms[at[0]] = (name, d5, wg)
    return arms


def memo_inputs(tables_dir=None, arms=None, headers=None, allow_missing=False):
    """The chain's cells by memo header: {"mult": [check, UI, tax cut] (the AD row's strings), "welfare": {cell: (mean,
    SE, S)}}. Raises MissingInputs naming every absent table -- the memo never renders a placeholder."""
    arms = list(arms if arms is not None else ORDERS[MEMO_ORDER])
    headers = list(headers or MEMO_HEADERS)
    if len(arms) != len(headers):
        raise ValueError(f"the memo format has {len(headers)} columns, got {len(arms)} arms")
    td = resolve_tables_dir(tables_dir, arms)
    data, missing = {}, []
    for hdr, (name, d5, wg) in zip(headers, arms):
        if d5 is None:
            check_published()
            data[hdr] = {"mult": list(PUBLISHED_AD_MULT),
                         "welfare": {c: (v, float("nan"), 0) for c, v in PUBLISHED_WELFARE_AD.items()}}
            continue
        p = os.path.join(td, d5, "Multiplier_candidate.tex")
        m = mult_rows_avg(td, d5).get("AD", [])
        if len(m) < 3:
            missing.append(p)
        if not glob.glob(os.path.join(td, wg, "welfare6_parallel_summary.json")):
            missing.append(os.path.join(td, wg, "welfare6_parallel_summary.json"))
        data[hdr] = {"mult": m if len(m) >= 3 else ["nan"] * 3, "welfare": welfare(wg, td)}
    if missing and not allow_missing:
        raise MissingInputs(f"memo chain table: inputs missing under {td}:\n  " + "\n  ".join(missing))
    return data


def wall_clock_cell(header):
    """The entire-run wall for one column, hours to one decimal from WALL_STAGES_MIN (the published column is text)."""
    if header == "published":
        return WALL_PUBLISHED
    est, a5, per_seed, seeds = WALL_STAGES_MIN[header]
    return f"{(est + a5 + per_seed * seeds) / 60:.1f} h"


MEMO_SCHEMES = {"original-code": (MEMO_HEADERS, wall_clock_cell), "ergodic-conversion": (MEMO_HEADERS_EC, wall_clock_cell_ec)}


def render_memo(data, headers=MEMO_HEADERS, wall=wall_clock_cell):
    """The fenced block from memo_inputs()-shaped data (layout: module docstring). Pure -- unit-tested on synthetic data."""
    widths = [len(h) for h in headers]

    def row(label, cells):
        return "| " + label.ljust(MEMO_LABEL_WIDTH) + " |" + "|".join(" " + c.rjust(w) + " " for c, w in zip(cells, widths)) + "|"
    rule = "|" + "-" * (MEMO_LABEL_WIDTH + 2) + "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    L = ["```text", row("", headers), rule]
    for pol, j, _ in MEMO_POLICIES:
        L.append(row(f"Multiplier: {pol}", [("—" if data[h]['mult'][j] in ("nan", None) else f"{float(data[h]['mult'][j]):.3f}") + " " for h in headers]))
    for pol, _, cell in MEMO_POLICIES:
        L.append(row(f"Welfare: {pol}", [f"{data[h]['welfare'][cell][0]:.3f} " for h in headers]))
        L.append(row("", ["" if data[h]["welfare"][cell][2] == 0 else f"({data[h]['welfare'][cell][1]:.3f})" for h in headers]))
    L += [rule, row(MEMO_WALL_LABEL, [wall(h) for h in headers]), "```"]
    return "\n".join(L) + "\n"


def memo_block(tables_dir=None, arms=None, order=None, allow_missing=False):
    """The memo's section 1.2 block regenerated from the arm tables (MissingInputs when they are absent unless allow_missing)."""
    headers, wall = MEMO_SCHEMES[order or MEMO_ORDER]
    return render_memo(memo_inputs(tables_dir, arms, headers, allow_missing), headers, wall)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--arm", action="append", default=[], help="NAME=5a_dir:welfare_glob (adds/overrides a column)")
    ap.add_argument("--allow-missing", action="store_true", help="memo format: render columns whose tables are absent as nan instead of raising")
    ap.add_argument("--tex", default=None, help="also write the condensed appendix table (LaTeX) to this path")
    ap.add_argument("--order", choices=sorted(ORDERS), default=None,
                    help="column chain (see module docstring; default category, or original-code under --format memo)")
    ap.add_argument("--split-model-changes", action="store_true", help="method-first: insert the matched no-age-wall column")
    ap.add_argument("--format", choices=("waterfall", "memo"), default="waterfall",
                    help="memo = the revision memo's section 1.2 fenced block, byte-exact (module docstring)")
    ap.add_argument("--tables", default=None,
                    help="Tables root holding the arms (default: this checkout's FromPandemicCode/Tables, else the main checkout's)")
    a = ap.parse_args()
    if a.format == "memo":
        if a.order not in (None, *MEMO_SCHEMES):
            ap.error(f"--format memo renders orders {sorted(MEMO_SCHEMES)} only")
        order = a.order or MEMO_ORDER
        arms = memo_arms(a.arm) if order == MEMO_ORDER else list(ORDERS[order])
        text = memo_block(a.tables, arms, order, a.allow_missing)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(text)
        sys.stdout.write(text)
        return
    order = a.order or "category"
    arms = list(ORDERS[order])
    td = resolve_tables_dir(a.tables, arms)
    qe = resolve_qe_dir() or QE
    if order == "method-first":
        at = [i for i, x in enumerate(arms) if x[1] == "Baseline_uiL"][0]
        if a.split_model_changes:
            arms.insert(at, SPLIT_COL)
    for spec in a.arm:
        name, rest = spec.split("=", 1); d5, wg = rest.split(":", 1)
        arms = [x for x in arms if x[0] != name] + [(name, d5, wg)]
    L = [f"# Waterfall — one change per column (Baseline; order: {order})", ""]
    L.append("| multiplier row (Check / UI / TaxCut) | " + " | ".join(n for n, _, _ in arms) + " |")
    L.append("|---|" + "---|" * len(arms))
    mt = {}
    for name, d5, _ in arms:
        mt[name] = mult_rows(os.path.join(qe, "Multiplier.tex") if d5 is None else os.path.join(td, d5, "Multiplier_candidate.tex"))
    # The TRUE original (Baseline_orig_typo) carries the published tax-cut construction (BUG-023): the published code
    # SOLVED with the typo but its Monte Carlo PAID the real 2 %. Since 2026-08-27 evening (owner ruling) the exact TM
    # reproduces that experiment under HAFISCAL_LEGACY_TAXCUT_ATOM=1 (run-time transitory rescaling + the paper's
    # simulated process in kernel and aggregator), so the tax-cut column is computed like the others (footnote below).
    def _cells(n, d5, key):
        return " / ".join(list(mt[n].get(key, ["—"])))
    for key, _ in MROWS:
        if order in ORDER_MROWS and key not in ORDER_MROWS[order]:
            continue
        L.append(f"| {key} | " + " | ".join(_cells(n, d5, key) for n, d5, _ in arms) + " |")
    L += ["", "| welfare-6 cell | " + " | ".join(f"{n} (mean ± SE, S)" for n, _, _ in arms) + " |", "|---|" + "---|" * len(arms)]
    wt = {}
    for name, d5, wg in arms:
        wt[name] = published_welfare(qe) if d5 is None else welfare(wg, td)
    for c in CELLS:
        cells = []
        for n, d5, _ in arms:
            m, se, S = wt[n].get(c, (float("nan"), float("nan"), 0))
            cells.append("—" if not np.isfinite(m) else (f"{m:.3f}" if S == 0 else f"{m:.4f} ± {se:.4f} ({S})"))
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    if any(d5 == "Baseline_orig_typo" for _, d5, _ in arms):
        L += ["", "Original model, tax-cut cells: the paper's experiment reproduced on the exact TM (households solved under the published",
              "construction, the real 2 % paid; HAFISCAL_LEGACY_TAXCUT_ATOM=1, 2026-08-27). HS_Only gate vs the fixed arm: 0.984/1.150 vs",
              "0.991/1.209 (no-AD/AD); Baseline: 0.882/0.999 vs 0.897/1.031 (published 0.975 AD)."]
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w").write(text)
    print(text)
    if a.tex:
        open(a.tex, "w").write(appendix_tex(arms, mt, wt))
        print(f"appendix table -> {a.tex}")


if __name__ == "__main__":
    main()
