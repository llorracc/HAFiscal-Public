#!/usr/bin/env python3
"""Compare two Step-5a arms of the BUG-122 Step-0 measurement (the onset-spike t=0 exemption).

Usage:  compare_arms.py <suffixA> <suffixB> [--horizon 40]

Reads Figures/<param><suffix>/ and Tables/<param><suffix>/ for both arms and reports, per
recession scenario, the quantities the timing fix is expected to move:

  * aggregate income in the FIRST FEW recorded quarters -- where the second ordinary benefit
    quarter of the onset-spiked cohort shows up, if it shows up at all;
  * the policy OUTLAY, NPV(income | policy) - NPV(income | plain recession), which is the
    multiplier's denominator;
  * the multiplier table itself, number for number.

The arms are named by HAFISCAL_FIGS_SUFFIX, so `_off` vs `_on` is the measurement and `_off` vs
a rerun of the same code is the reproduction check.
"""

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
FPC = HERE.parents[2] / "FromPandemicCode"

SCENARIOS = ["recession", "recessionCheck", "recessionUI", "recessionTaxCut"]
POLICY_OF = {"recessionCheck": "stimulus check", "recessionUI": "UI extension",
             "recessionTaxCut": "tax cut"}


def _load(param, suffix, name):
    p = FPC / "Figures" / f"{param}{suffix}" / name
    if not p.exists():
        return None
    with open(p, "rb") as fh:
        return pickle.load(fh)


# ------------------------------------------------------------------ the arms must differ in ONE thing
# Added 2026-09-07 after a night in which two arms were compared that differed in the MULTIPLIER
# ENGINE as well as the policy under test, and the difference presented as a model bug (BUG-123,
# withdrawn): a UI policy appearing to move the stimulus-check and tax-cut multipliers, which no UI
# policy can do. Every result directory carries a provenance sidecar naming the configuration that
# produced it, so a comparison can check its own premise instead of assuming it.
CONFIG_KEYS = (
    "HAFISCAL_TM_A_INDEXED", "HAFISCAL_STEP5_ATI", "HAFISCAL_WORLD",
    "HAFISCAL_UI_STATE_ENCODING", "HAFISCAL_UI_EXTENSION_POLICY",
    "HAFISCAL_ONSET_SPIKE_T0_EXEMPT", "HAFISCAL_PERM_DURING_UNEMP",
    "HAFISCAL_INTERPRETATION", "HAFISCAL_TM_AMAX", "HAFISCAL_AD_EQUILIBRIUM_SHARE",
    "HAFISCAL_MC_SHUFFLE", "HAFISCAL_SHUFFLE_MRKV_TRANSITION",
)


def _sidecar_config(param, suffix):
    """The configuration the newest run in this arm's directory recorded, or None."""
    d = FPC / "Figures" / f"{param}{suffix}"
    cands = sorted(d.glob("RUN_*.prov.json"), key=lambda p: p.stat().st_mtime, reverse=True) \
        if d.is_dir() else []
    if not cands:
        return None, (None, True)
    with open(cands[0]) as fh:
        doc = json.load(fh)
    rc = doc.get("resolved_config") or {}
    env = rc.get("env") or {}
    # BUG-124: sidecars written before 2026-09-06 report the CATALOG's value for entry-point-owned
    # settings (notably HAFISCAL_TM_A_INDEXED), not the run's. The fix added this field, so its
    # absence dates the sidecar and marks that field untrustworthy.
    trustworthy = "env_entry_point_unset" in rc
    return {k: env.get(k) for k in CONFIG_KEYS}, (cands[0].name, trustworthy)


def check_arms_differ_in_one_thing(param, sa, sb, axis=None):
    """Report the configuration difference between two arms; return the differing keys."""
    ca, ia = _sidecar_config(param, sa)
    cb, ib = _sidecar_config(param, sb)
    if ca is None or cb is None:
        print("# CONFIG CHECK: no provenance sidecar for "
              f"{'A' if ca is None else ''}{'B' if cb is None else ''} — cannot verify the arms "
              "differ in one thing\n")
        return None
    diff = sorted(k for k in CONFIG_KEYS if ca.get(k) != cb.get(k))
    stale = [n for n, (f, t) in (("A", ia), ("B", ib)) if not t]
    print("# CONFIG CHECK (from each arm's provenance sidecar)")
    for k in diff:
        print(f"#   {k}: A={ca.get(k)!r}  B={cb.get(k)!r}")
    if not diff:
        print("#   no recorded configuration difference")
    if stale:
        print(f"#   WARNING: sidecar(s) {', '.join(stale)} predate the BUG-124 fix; their "
              "HAFISCAL_TM_A_INDEXED is the catalog's value, not the run's — do not trust it")
    if axis is not None:
        if ca.get(axis) is None and cb.get(axis) is None:
            # The sidecar reports CATALOG settings. A flag that was not a catalog row when the run
            # happened is absent from both sides, which looks identical but is really invisible.
            # Say which it is rather than passing or failing on nothing.
            print(f"#   ? NEITHER sidecar records {axis} — it was probably not a catalog row when")
            print("#     these arms ran, so this check cannot see the axis. Verify it another way")
            print("#     (the run logs, or the AD-equilibrium store's producer conventions).")
            if diff:
                print(f"#   and the arms DO differ in: {diff}")
            print()
            return diff
        if diff == [axis]:
            print(f"#   OK: the arms differ in {axis} and nothing else\n")
        else:
            print(f"#   ✗ EXPECTED the arms to differ ONLY in {axis}, but the difference is "
                  f"{diff or 'nothing'}")
            print("#   A comparison whose arms differ in more than the axis under test measures "
                  "the wrong thing.\n")
            raise SystemExit(9)
    else:
        print()
    return diff


def _multiplier_table(param, suffix):
    p = FPC / "Tables" / f"{param}{suffix}" / "Multiplier_candidate.tex"
    if not p.exists():
        return {}
    rows = {}
    for line in p.read_text().splitlines():
        if "&" not in line or "\\toprule" in line:
            continue
        cells = [c.strip() for c in line.split("&")]
        label = cells[0].strip()
        if not label or label.startswith("\\"):
            continue
        vals = []
        for c in cells[1:]:
            m = re.search(r"-?\d+\.?\d*", c.replace("\\%", ""))
            vals.append(float(m.group()) if m else float("nan"))
        rows[label] = vals
    return rows


def _fmt(x, w=12, p=6):
    return f"{x:>{w}.{p}f}" if np.isfinite(x) else " " * (w - 3) + "nan"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suffix_a")
    ap.add_argument("suffix_b")
    ap.add_argument("--param", default="HS_Only")
    ap.add_argument("--horizon", type=int, default=40, help="quarters in the NPV horizon (10y = 40)")
    ap.add_argument("--quarters", type=int, default=6, help="how many early quarters to print")
    ap.add_argument("--axis", default=None,
                    help="the ONE setting the arms are meant to differ in (e.g. "
                         "HAFISCAL_UI_EXTENSION_POLICY); exits 9 if they differ in anything else")
    a = ap.parse_args()

    print(f"# arms: A = {a.param}{a.suffix_a}   B = {a.param}{a.suffix_b}   (B - A)")
    print(f"# horizon for NPV lines: t = {a.horizon} quarters\n")
    check_arms_differ_in_one_thing(a.param, a.suffix_a, a.suffix_b, a.axis)

    any_data = False
    max_rel = 0.0
    for sc in SCENARIOS:
        da = _load(a.param, a.suffix_a, f"{sc}_results.csv")
        db = _load(a.param, a.suffix_b, f"{sc}_results.csv")
        if da is None or db is None:
            print(f"## {sc}: MISSING ({'A' if da is None else ''}{'B' if db is None else ''})")
            continue
        any_data = True
        ia, ib = np.asarray(da["AggIncome"]), np.asarray(db["AggIncome"])
        ca, cb = np.asarray(da["AggCons"]), np.asarray(db["AggCons"])
        print(f"## {sc}")
        print("   q  " + "  ".join(f"{'income A':>14}{'income B':>16}{'rel diff':>12}"
                                   for _ in [0]))
        for t in range(min(a.quarters, len(ia))):
            rel = (ib[t] - ia[t]) / ia[t] if ia[t] else float("nan")
            max_rel = max(max_rel, abs(rel))
            print(f"  {t:2d}  {ia[t]:>14.4f}{ib[t]:>16.4f}{rel:>12.3e}")
        for key, arr_a, arr_b in (("NPV income", da["NPV_AggIncome"], db["NPV_AggIncome"]),
                                  ("NPV cons  ", da["NPV_AggCons"], db["NPV_AggCons"])):
            h = min(a.horizon, len(arr_a) - 1)
            va, vb = float(arr_a[h]), float(arr_b[h])
            rel = (vb - va) / va if va else float("nan")
            max_rel = max(max_rel, abs(rel))
            print(f"      {key} @ t={h}: {va:>16.4f}{vb:>18.4f}{rel:>12.3e}")
        print()

    # outlays: the multiplier's denominator, policy minus the plain recession
    base_a = _load(a.param, a.suffix_a, "recession_results.csv")
    base_b = _load(a.param, a.suffix_b, "recession_results.csv")
    if base_a is not None and base_b is not None:
        print("## policy outlay = NPV(income | policy) - NPV(income | plain recession)")
        for sc, name in POLICY_OF.items():
            da, db = _load(a.param, a.suffix_a, f"{sc}_results.csv"), _load(a.param, a.suffix_b, f"{sc}_results.csv")
            if da is None or db is None:
                continue
            h = min(a.horizon, len(da["NPV_AggIncome"]) - 1)
            oa = float(da["NPV_AggIncome"][h]) - float(base_a["NPV_AggIncome"][h])
            ob = float(db["NPV_AggIncome"][h]) - float(base_b["NPV_AggIncome"][h])
            rel = (ob - oa) / oa if oa else float("nan")
            print(f"   {name:<16}{oa:>16.4f}{ob:>18.4f}{rel:>12.3e}")
        print()

    ta, tb = _multiplier_table(a.param, a.suffix_a), _multiplier_table(a.param, a.suffix_b)
    if ta and tb:
        print("## multiplier table (check / UI / tax cut)")
        for label in ta:
            if label not in tb:
                continue
            va, vb = ta[label], tb[label]
            cells = "  ".join(f"{x:>8.3f}->{y:>8.3f}" for x, y in zip(va, vb))
            print(f"   {label[:52]:<54}{cells}")
        print()

    if any_data:
        print(f"# largest relative difference on any printed series: {max_rel:.3e}")
        print("# (an arm pair that differs only in code refactoring must read 0.000e+00)")
    else:
        print("# no data found -- check the suffixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
