"""Phase B of the SSJ gated ladder: mechanism build-up on the full model.

Plan 20260901-2010h §3. One rung per adopted mechanism, published-shaped →
current default; strictly sequential, cascade-halt. Every rung's children run
under a HERMETIC env: the driver passes value-or-<unset> for EVERY managed
key, so ambient shell state cannot leak into a rung fingerprint.

Rung kinds:
  stamp    — verdict from committed evidence (B0 dual-verified 08-28; B10 the
             splurge 2x2), no compute
  build    — Jacobian obj (scratch, via build_obj) + budget suite + by-educ
             identity + attribution vs the previous rung's obj + GE pass
             (scratch, via run_ge_scratch, HANK_G11=1) + pe_anchor_gate +
             hank_diagnose --no-ss
  ge_only  — GE-side mechanism (obj reused from the previous rung)

Gating tonight (recorded in each verdict):
  HARD (cascade-halt): child failures; the budget-suite floors; the by-educ
  identity ≤1e-12; B1's s≥1 residual vs the PUBLISHED 0.14.1 pickle (C ≤
  3.2e-5, A ≤ 2e-4 — the ghost-differencing budget); B4's null SSTs before
  the flip; B9's exit identity — its GE h20 must reproduce the committed
  production goldens to 1e-3 (taylor 1.189485/1.372442/1.137015).
  RECORDED (directional, never equality): every expected-move note from the
  plan table; pe_anchor drift at rungs whose config deliberately differs
  from the PE (Γ=1 / ψ=1 arms); col-0 vs interior cash rows.

Usage:
  python -m ssj_ladder.phase_b --chain --dir rerun_logs/phase_b_<date>
  python -m ssj_ladder.phase_b B2 --dir ... --prev <B1b dir>   (single rung)
"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np

from . import budget_suite

HERE = os.path.dirname(os.path.abspath(__file__))
HA = os.path.dirname(HERE)                    # Code/HA-Models
REPO = os.path.dirname(os.path.dirname(HA))
PY = sys.executable
QE_CALIB = os.path.join(HA, "rerun_logs", "hank_ladder_20260828", "qe_calib")
PUBLISHED_JACS = os.path.abspath(os.path.join(
    REPO, "..", "HAFiscal-QE", "Code", "HA-Models", "FromPandemicCode",
    "HA_Fiscal_Jacs.obj"))

# Every env key the ladder manages. Children receive value-or-<unset> for
# ALL of these — hermetic fingerprints, no ambient leakage.
MANAGED = [
    # PE side / calibration vintage
    "HAFISCAL_DISCFAC_FILE", "HAFISCAL_SPLURGE_FILE", "HAFISCAL_WORLD",
    "HAFISCAL_INTERPRETATION", "HAFISCAL_T_AGE", "HAFISCAL_PERMGROFAC_FIX",
    "HAFISCAL_PF_DECAY_EXTRAP", "HAFISCAL_PF_DECAY_Q",
    "HAFISCAL_GIC_SHAVE_ON_GPF", "HAFISCAL_LEGACY_TAXCUT_ATOM",
    "HAFISCAL_UI_STATE_ENCODING", "HAFISCAL_UI_EXTENSION_POLICY",
    "HAFISCAL_EARNINGS_PHASE_HAZARD", "HAFISCAL_PERM_GROWTH_SCALE",
    "HAFISCAL_PERM_DURING_UNEMP",
    # engine routing + jac semantics
    "HAFISCAL_QE_FIDELITY", "HAFISCAL_STEP4_ENGINE",
    "HAFISCAL_STEP4_SHOCK_FIX", "HAFISCAL_STEP4_ZEROTH_FIX",
    "HAFISCAL_STEP4_ZEROTH_COLUMN", "HAFISCAL_STEP4_FAKENEWS_INDEX",
    "HAFISCAL_STEP4_TRANMAT_GROWTH", "HAFISCAL_STEP4_TRANMAT_QMETHOD",
    "HAFISCAL_STEP4_FAST_BACKWARD", "HAFISCAL_STEP4_FAST_TRANMAT",
    "HAFISCAL_STEP4_FASTEOP", "HAFISCAL_STEP4_SKIP_INSTRUMENTS",
    # HANK block mechanisms
    "HAFISCAL_HANK_PERMGROFAC", "HAFISCAL_HANK_UNEMP_PSI",
    "HAFISCAL_HANK_INCOME_GUARD", "HAFISCAL_HANK_GRIDS",
    "HAFISCAL_HANK_UNEMP_CHAINS", "HAFISCAL_HANK_INCOME_LEVEL",
    "HAFISCAL_TAU_SS", "HAFISCAL_HANK_SS_SOURCE",
    # GE side
    "HAFISCAL_HANK_SPLURGE", "HAFISCAL_HANK_SPLURGE_BYEDUC",
    "HAFISCAL_HANK_SPLURGE_DIAG", "HAFISCAL_HANK_SPLURGE_RHO",
    "HAFISCAL_HANK_MULT_REGIME", "HAFISCAL_HANK_TAXCUT_FINANCING",
    "HAFISCAL_HANK_BIGT", "HAFISCAL_HANK_PHI_PI_FIXED",
    "HAFISCAL_HANK_KAPPA_P", "HAFISCAL_HANK_PHI_B",
    "HAFISCAL_HANK_PHI_PI_TAYLOR", "HAFISCAL_HANK_G11",
    "HAFISCAL_HANK_MULT_DUMP", "HAFISCAL_HANK_SS_DUMP",
    "HAFISCAL_HANK_DETERMINACY", "HAFISCAL_HANK_DETERMINACY_DUMP",
    "HAFISCAL_HANK_G11_DUMP", "HAFISCAL_HANK_NEWBORN_M",
    "HAFISCAL_HANK_RHO_R",   # IMPROVEMENT-003: unset in rungs -> world default (0.70)
]

# The published-shaped base (transcribed from the dual-verified econ-9
# env_base.sh, 2026-08-28, with the committed qe_calib files), package
# engine, and the ladder pins (§1). This is rung B1's env.
ENV_B1 = {
    # QE calibration + the original-model PE reproduction set
    "HAFISCAL_DISCFAC_FILE": os.path.join(QE_CALIB, "DiscFacEstim_CRRA_2.0_R_1.01.txt"),
    "HAFISCAL_SPLURGE_FILE": os.path.join(QE_CALIB, "Result_AllTarget.txt"),
    "HAFISCAL_WORLD": "as-corrected", "HAFISCAL_INTERPRETATION": "CDC",
    "HAFISCAL_T_AGE": "200", "HAFISCAL_PERMGROFAC_FIX": "0",
    "HAFISCAL_PF_DECAY_EXTRAP": "0", "HAFISCAL_PF_DECAY_Q": "slope",
    "HAFISCAL_GIC_SHAVE_ON_GPF": "0", "HAFISCAL_LEGACY_TAXCUT_ATOM": "1",
    "HAFISCAL_UI_STATE_ENCODING": "legacy", "HAFISCAL_UI_EXTENSION_POLICY": "window",
    "HAFISCAL_EARNINGS_PHASE_HAZARD": "0",
    # engine: the package with the fixed jac semantics + the ladder pins
    "HAFISCAL_QE_FIDELITY": "1", "HAFISCAL_STEP4_ENGINE": "package",
    "HAFISCAL_STEP4_SHOCK_FIX": "1", "HAFISCAL_STEP4_ZEROTH_FIX": "1",
    "HAFISCAL_STEP4_ZEROTH_COLUMN": "unanticipated",
    "HAFISCAL_STEP4_FAKENEWS_INDEX": "legacy",
    # published-shaped mechanisms (the flip axes)
    "HAFISCAL_STEP4_TRANMAT_GROWTH": "0",
    "HAFISCAL_STEP4_TRANMAT_QMETHOD": "bst",
    "HAFISCAL_STEP4_FAST_BACKWARD": "0", "HAFISCAL_STEP4_FAST_TRANMAT": "1",
    "HAFISCAL_STEP4_FASTEOP": "0", "HAFISCAL_STEP4_SKIP_INSTRUMENTS": "",
    "HAFISCAL_HANK_PERMGROFAC": "ones", "HAFISCAL_HANK_UNEMP_PSI": "one",
    "HAFISCAL_HANK_INCOME_GUARD": "warn",
    "HAFISCAL_HANK_GRIDS": "legacy", "HAFISCAL_HANK_UNEMP_CHAINS": "legacy",
    "HAFISCAL_HANK_INCOME_LEVEL": "net", "HAFISCAL_TAU_SS": "legacy",
    "HAFISCAL_HANK_SS_SOURCE": "hardcoded",
    # GE side, published-shaped (overlay OFF until B6)
    "HAFISCAL_HANK_SPLURGE": "0", "HAFISCAL_HANK_SPLURGE_BYEDUC": "0",
    "HAFISCAL_HANK_SPLURGE_DIAG": "cash", "HAFISCAL_HANK_SPLURGE_RHO": "livprb",
    "HAFISCAL_HANK_MULT_REGIME": "consistent",
    "HAFISCAL_HANK_TAXCUT_FINANCING": "incidence_free",
    "HAFISCAL_HANK_BIGT": "300",
    "HAFISCAL_HANK_NEWBORN_M": "unit",   # the published newborn convention
}

# The world-of-record hop (B1b): calibration files -> the tracked chain-D
# defaults; PE side -> today's default world. Everything else inherited.
WOR_HOP = {
    "HAFISCAL_DISCFAC_FILE": None, "HAFISCAL_SPLURGE_FILE": None,
    "HAFISCAL_WORLD": "default", "HAFISCAL_INTERPRETATION": "ESC",
    "HAFISCAL_T_AGE": "none", "HAFISCAL_PERMGROFAC_FIX": "1",
    "HAFISCAL_PF_DECAY_EXTRAP": None, "HAFISCAL_PF_DECAY_Q": None,
    "HAFISCAL_GIC_SHAVE_ON_GPF": None, "HAFISCAL_LEGACY_TAXCUT_ATOM": "0",
    "HAFISCAL_UI_STATE_ENCODING": "calendar",
    "HAFISCAL_PERM_GROWTH_SCALE": "0.44", "HAFISCAL_PERM_DURING_UNEMP": "on",
    "HAFISCAL_QE_FIDELITY": None,
    # 2026-09-02 owner IMPROVEMENT: the world of record's HANK newborns hold
    # their first income draw (see hh_setup's scoped default).
    "HAFISCAL_HANK_NEWBORN_M": "income",
}

RUNGS = [
    dict(name="B0", kind="stamp",
         note="monolith pair on the QE calibration vs the PUBLISHED 0.14.1 "
              "pickle: C 2.03e-8 / A 8.5e-7 rel<=1.2e-5 per leaf; verified "
              "twice (arm0 2026-08-28, Mac; jacobians wall 861 s)",
         evidence="rerun_logs/hank_ladder_20260828/arm0_vs_published_pickle.txt"),
    dict(name="B1", kind="build", env=ENV_B1,
         gate_vs_published=True,
         note="the package at published-shaped settings; col0=unanticipated "
              "(the ladder pin — the monolith cannot express it); s>=1 gated "
              "vs the published pickle at the ghost budget; col0 residual "
              "vs published RECORDED (the BUG-112 content, 5.8e-2..2.9e-1)"),
    dict(name="B1b", kind="build", delta=WOR_HOP,
         note="calibration + PE-env hop: QE (as-corrected/CDC/T_AGE=200/"
              "PGF_FIX=0/UI legacy) -> world of record (default/ESC/uncapped/"
              "chain-D tracked files). Attribution rung; ~4e-4 J-sensitivity "
              "for the calibration alone (econ-9 0c)"),
    dict(name="B2", kind="build",
         delta={"HAFISCAL_HANK_GRIDS": "pe"},
         note="GRIDS legacy->pe; directional: multiplier move <~1%"),
    dict(name="B3", kind="build",
         delta={"HAFISCAL_HANK_UNEMP_CHAINS": "pe"},
         note="CHAINS legacy->pe; eta_ss==job_find tripwire lives in ge.py; "
              "econ-9 QE-vintage directional: -2.5/-1.1/-2.0%"),
    dict(name="B4", kind="build",
         delta={"HAFISCAL_HANK_PERMGROFAC": "main",
                "HAFISCAL_STEP4_TRANMAT_GROWTH": "1"},
         null_ssts=["test_step4_tranmat_growth.py",
                    "test_pweighted_survival.py"],
         budget_floor_scale=20.0,
         note="the Gamma-bundle in ONE rung (the split intermediate IS the "
              "BUG-097 defect config); null SSTs gate byte-inertness at "
              "Gamma==1 BEFORE the flip; econ-9 bundle exit directional: "
              "+18.9/+19.5/+27.5%. TRANSITIONAL budget ceiling 20x: this "
              "config runs Gamma-on with the BST kernel -- the biased "
              "construction BUG-093/108 identified (measured 1.5e-3 vs the "
              "doob-config 9.7e-5, ~15x); B4b's doob flip must RESTORE the "
              "standard floors, making the pair a measured demonstration of "
              "what the Q-construction fixes"),
    dict(name="B4b", kind="build",
         delta={"HAFISCAL_STEP4_TRANMAT_QMETHOD": "doob"},
         note="QMETHOD bst->doob; BUG-108 directional: A_ss +22.97%, "
              "C_ss +1.07%, +30.1% at the cap atom"),
    dict(name="B5", kind="build",
         delta={"HAFISCAL_HANK_UNEMP_PSI": "main",
                "HAFISCAL_HANK_INCOME_GUARD": "raise"},
         note="psi one->main and the income guard restored to raise (the "
              "guard flip IS the gate: it certifies the config is no longer "
              "ill-posed at the cap atoms)"),
    dict(name="B6", kind="ge_only",
         delta={"HAFISCAL_HANK_SPLURGE": "calib",
                "HAFISCAL_HANK_SPLURGE_BYEDUC": "1"},
         overlay_ssts=["step4/test_splurge_overlay.py"],
         note="SPLURGE 0->calib with the pinned cash arm + by-educ tied "
              "(G-SPL: the overlay SSTs gate budget preservation <=1e-12)"),
    dict(name="B7", kind="ge_only",
         delta={"HAFISCAL_HANK_SS_SOURCE": "jacs_c"},
         note="SS hardcoded->jacs_c; recorded <=4e-9 multiplier move "
              "(RECONCILED-003)"),
    dict(name="B8", kind="ge_only",
         delta={"HAFISCAL_HANK_TAXCUT_FINANCING": "household"},
         note="FINANCING incidence_free->household; BUG-074 directional: "
              "tax cut -3.6% fixed-real / -12% Taylor"),
    dict(name="B9", kind="build",
         delta={"HAFISCAL_STEP4_FAST_BACKWARD": "1"},
         exit_goldens={"transfers": 1.135390, "UI_extensions": 1.317568,
                       "tax_cut": 1.073550},   # IMPROVEMENT-003 goldens (rho_r=0.70)
         note="kernels ON (FAST_BACKWARD 0->1); equivalence lanes; EXIT "
              "IDENTITY: the chain's GE h20 must reproduce the committed "
              "production goldens to 1e-3"),
    dict(name="B10", kind="stamp",
         note="the {ZEROTH_COLUMN x SPLURGE_DIAG} 2x2 at full config — "
              "already measured, both rows independently reproduced",
         evidence="rerun_logs/splurge2x2_20260901/"),
]


def env_pairs(env):
    """Full managed-set --env pairs (value or <unset>) for a rung env dict."""
    pairs = []
    for k in MANAGED:
        v = env.get(k)
        pairs += ["--env", f"{k}=<unset>" if v is None else f"{k}={v}"]
    return pairs


def cumulative_envs():
    """Resolve each rung's full env dict by folding deltas onto B1's."""
    envs = {}
    cur = None
    for r in RUNGS:
        if r["kind"] == "stamp":
            continue
        if "env" in r:
            cur = dict(r["env"])
        else:
            cur = dict(cur)
            for k, v in r["delta"].items():
                if v is None:
                    cur.pop(k, None)
                else:
                    cur[k] = v
        envs[r["name"]] = dict(cur)
    return envs


def child_env(rung_env=None):
    """Scrubbed base env (no ambient HAFISCAL_*) + the rung's keys."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith("HAFISCAL_")}
    base["PYTHONUNBUFFERED"] = "1"
    base["MPLBACKEND"] = "Agg"
    if rung_env:
        base.update({k: v for k, v in rung_env.items() if v is not None})
    return base


def sh(cmd, log_path, timeout=5400, env=None):
    t0 = time.time()
    with open(log_path, "w") as f:
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT,
                             cwd=HA, timeout=timeout, env=env)
    return rc, time.time() - t0


def load_obj(p):
    with open(p, "rb") as f:
        return pickle.load(f)


def attribution(prev_obj, obj):
    rows = {}
    for top in ("C", "A"):
        for k in sorted(obj[top]):
            d = float(np.max(np.abs(np.asarray(obj[top][k], float)
                                    - np.asarray(prev_obj[top][k], float))))
            rows[f"{top}.{k}"] = d
    return rows


def published_gate(obj):
    """B1: s>=1 residual vs the published pickle; col0 recorded."""
    pub = load_obj(PUBLISHED_JACS)
    out = {"s_ge_1": {}, "col0": {}, "budgets": {}, "pass": True}
    # C budget = the measured ghost-differencing residual (3.2e-5); the A
    # budget is the plan's flat 6x (max|J_A| ~ 6 max|J_C|). The ghost error
    # is a COMMON-MODE term — the first chain run measured an IDENTICAL
    # 1.76e-4 on every A leaf including DiscFac, so a per-input |A|/|C|
    # scaling (the first design) wrongly tightens small-J inputs.
    C_BUDGET = 3.2e-5
    A_BUDGET = 6.0 * C_BUDGET
    for top in ("C", "A"):
        for k in sorted(set(obj[top]) & set(pub[top])):
            a = np.asarray(obj[top][k], float)
            b = np.asarray(pub[top][k], float)
            T = min(a.shape[1], b.shape[1])
            d1 = float(np.max(np.abs(a[:T, 1:T] - b[:T, 1:T])))
            d0 = float(np.max(np.abs(a[:T, 0] - b[:T, 0])))
            budget = C_BUDGET if top == "C" else A_BUDGET
            out["s_ge_1"][f"{top}.{k}"] = d1
            out["col0"][f"{top}.{k}"] = d0
            out["budgets"][f"{top}.{k}"] = budget
            if d1 > budget:
                out["pass"] = False
    return out


def ge_h20(dump_path):
    d = load_obj(dump_path)
    out = {}
    for pol in ("transfers", "UI_extensions", "tax_cut"):
        for reg in ("taylor", "fixed_real"):
            v = np.atleast_1d(np.asarray(d[pol][reg], float))
            out[f"{pol}.{reg}"] = float(v[min(19, v.size - 1)])
    return out


def run_rung(r, envs, outdir, prev_obj_path, halt):
    name = r["name"]
    rd = os.path.join(outdir, name)
    os.makedirs(rd, exist_ok=True)
    verdict = {"rung": name, "kind": r["kind"], "note": r["note"],
               "start": time.strftime("%F %T"), "gates": {}, "walls": {}}
    if r["kind"] == "stamp":
        verdict["evidence"] = r["evidence"]
        verdict["pass"] = True
        return verdict, prev_obj_path

    env = envs[name]
    # env.txt: SET keys only (hank_diagnose applies it verbatim onto a
    # scrubbed base); fingerprint.txt: the full managed set incl. unsets.
    with open(os.path.join(rd, "env.txt"), "w") as f:
        for k in MANAGED:
            if env.get(k) is not None and k in env:
                f.write(f"{k}={env[k]}\n")
    with open(os.path.join(rd, "fingerprint.txt"), "w") as f:
        for k in MANAGED:
            f.write(f"{k}={env.get(k, '<unset>')}\n")
    ok = True

    # B4-style null SSTs run BEFORE the flip (under the PREVIOUS env — the
    # nulls certify byte-inertness at the not-yet-flipped config).
    for sst in r.get("null_ssts", []):
        rc, w = sh([PY, "-m", "pytest", sst, "-q", "--no-header"],
                   os.path.join(rd, f"null_{os.path.basename(sst)}.log"),
                   env=child_env())
        verdict["gates"][f"null:{sst}"] = (rc == 0)
        verdict["walls"][f"null:{sst}"] = round(w, 1)
        ok = ok and rc == 0
    for sst in r.get("overlay_ssts", []):
        rc, w = sh([PY, "-m", "pytest", sst, "-q", "--no-header"],
                   os.path.join(rd, f"sst_{os.path.basename(sst)}.log"),
                   env=child_env())
        verdict["gates"][f"sst:{sst}"] = (rc == 0)
        verdict["walls"][f"sst:{sst}"] = round(w, 1)
        ok = ok and rc == 0
    if halt and not ok:
        verdict["pass"] = False
        return verdict, prev_obj_path

    obj_path = prev_obj_path
    if r["kind"] == "build":
        obj_path = os.path.join(rd, "jacs.obj")
        if os.path.exists(obj_path) and os.path.getsize(obj_path) > 1000:
            # resume: the expensive build survived a gate-code fix — reuse
            # the obj and re-evaluate every gate.
            verdict["gates"]["build"] = True
            verdict["walls"]["build"] = 0.0
            verdict["build_reused"] = True
        else:
            rc, w = sh([PY, "-m", "ssj_ladder.build_obj", "--out", obj_path]
                       + env_pairs(env), os.path.join(rd, "build.log"),
                       env=child_env())
            verdict["gates"]["build"] = (rc == 0)
            verdict["walls"]["build"] = round(w, 1)
            if rc != 0:
                verdict["pass"] = False
                return verdict, prev_obj_path

        obj = load_obj(obj_path)
        _fscale = float(r.get("budget_floor_scale", 1.0))
        _floors = {k: v * _fscale for k, v in budget_suite.FLOORS.items()}
        bs_ok, rows = budget_suite.run_suite(obj, floors=_floors)
        verdict["gates"]["budget_suite"] = bs_ok
        verdict["budget"] = {k: {kk: vv for kk, vv in v.items()}
                             for k, v in rows.items()}
        be_ok, worst = budget_suite.by_educ_identity(obj)
        verdict["gates"]["by_educ_identity"] = be_ok
        verdict["by_educ_worst"] = worst
        ok = ok and bs_ok and be_ok

        if r.get("gate_vs_published"):
            if os.path.exists(PUBLISHED_JACS):
                pg = published_gate(obj)
                verdict["published_gate"] = pg
                verdict["gates"]["published_s_ge_1"] = pg["pass"]
                ok = ok and pg["pass"]
            else:
                verdict["published_gate"] = f"MISSING {PUBLISHED_JACS}"
                verdict["gates"]["published_s_ge_1"] = False
                ok = False
        if prev_obj_path and os.path.exists(prev_obj_path):
            verdict["attribution_vs_prev"] = attribution(load_obj(prev_obj_path), obj)
        del obj

    # GE pass (every non-stamp rung): scratch pickle + dump, G11 on.
    ge_env = dict(env)
    ge_env["HAFISCAL_HANK_G11"] = "1"
    ge_env["HAFISCAL_HANK_MULT_DUMP"] = os.path.join(rd, "mult_dump.pkl")
    rc, w = sh([PY, "-m", "ssj_ladder.run_ge_scratch",
                "--jacs", obj_path,
                "--pickle", os.path.join(rd, "mult_pickle.obj"),
                "--figdir", os.path.join(rd, "figs")]
               + env_pairs(ge_env), os.path.join(rd, "ge.log"),
               env=child_env())
    verdict["gates"]["ge"] = (rc == 0)
    verdict["walls"]["ge"] = round(w, 1)
    if rc == 0:
        verdict["h20"] = ge_h20(os.path.join(rd, "mult_dump.pkl"))
        g11 = [ln for ln in open(os.path.join(rd, "ge.log"))
               if "g11" in ln.lower()]
        verdict["g11_lines"] = g11[:6]
    ok = ok and rc == 0

    if rc == 0 and "exit_goldens" in r:
        eg_ok = True
        for pol, want in r["exit_goldens"].items():
            got = verdict["h20"].get(f"{pol}.taylor")
            eg_ok = eg_ok and got is not None and abs(got - want) < 1e-3
        verdict["gates"]["exit_identity_vs_production"] = eg_ok
        ok = ok and eg_ok

    # standing diagnostics (recorded, not gated at deliberate-delta rungs)
    rc_a, w = sh([PY, os.path.join(HA, "step4", "pe_anchor_gate.py"),
                  "--out", os.path.join(rd, "pe_anchor.json")],
                 os.path.join(rd, "pe_anchor.log"), env=child_env(env))
    verdict["walls"]["pe_anchor"] = round(w, 1)
    verdict["pe_anchor_rc"] = rc_a
    rc_d, w = sh([PY, "-m", "step4.hank_diagnose", "--env-file",
                  os.path.join(rd, "env.txt"), "--no-ss",
                  "--out", os.path.join(rd, "diagnose.json")],
                 os.path.join(rd, "diagnose.log"), env=child_env())
    verdict["walls"]["diagnose"] = round(w, 1)
    verdict["diagnose_rc"] = rc_d

    verdict["pass"] = ok
    verdict["end"] = time.strftime("%F %T")
    return verdict, obj_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rung", nargs="?", help="single rung name")
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--prev", default="", help="previous rung's jacs.obj")
    a = ap.parse_args()
    outdir = os.path.abspath(a.dir)
    os.makedirs(outdir, exist_ok=True)
    envs = cumulative_envs()

    todo = RUNGS if a.chain else [r for r in RUNGS if r["name"] == a.rung]
    if not todo:
        raise SystemExit(f"unknown rung {a.rung!r}")
    prev = a.prev or None
    results = []
    for r in todo:
        vf = os.path.join(outdir, f"verdict_{r['name']}.json")
        if a.chain and os.path.exists(vf):
            old = json.load(open(vf))
            if old.get("pass"):
                results.append((r["name"], True))
                if r["kind"] == "build":
                    prev = os.path.join(outdir, r["name"], "jacs.obj")
                print(f"[phase-b] {r['name']} SKIP (green verdict exists)",
                      flush=True)
                continue
        print(f"[phase-b] {r['name']} start {time.strftime('%T')}", flush=True)
        v, prev = run_rung(r, envs, outdir, prev, halt=True)
        with open(os.path.join(outdir, f"verdict_{r['name']}.json"), "w") as f:
            json.dump(v, f, indent=1, default=str)
        results.append((r["name"], v["pass"]))
        print(f"[phase-b] {r['name']} {'PASS' if v['pass'] else 'FAIL'}",
              flush=True)
        if a.chain and not v["pass"]:
            print(f"[phase-b] CASCADE-HALT at {r['name']}", flush=True)
            break
    with open(os.path.join(outdir, "chain_summary.json"), "w") as f:
        json.dump({"results": results, "end": time.strftime("%F %T")}, f,
                  indent=1)
    print("[phase-b] summary:", results, flush=True)
    sys.exit(0 if all(p for _, p in results) else 1)


if __name__ == "__main__":
    main()
