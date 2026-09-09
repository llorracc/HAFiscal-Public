#!/usr/bin/env python3
"""Gate checks for the phase-gated full-profile install rerun (2026-08-22).

Pre-registration: plans_local/20260822-1400h_full-profile-rerun-preregistration.md
(gates C1-C4; comparator values frozen there BEFORE the seam test ran). Each
subcommand exits 0 on PASS, 2 on FAIL, printing a per-check table either way.
The driver (full_profile_rerun_driver.sh) HALTs the cascade on any nonzero exit.

Anchor provenance (why these numbers, not magic):
- S1 main SoR + Splurge0 SoR: the installed Result_AllTarget_ESC / _Splurge0
  values produced by the cold-rerun program (full 604/238 grid + measured-Q
  attach, no knots) and re-certified by the fresh CTRLF battery whose winner
  reproduced them to <=0.01% (conclusions_private/2026-08-22_s1-default-setup-
  assessment.md, table row CTRLF).
- S2 per-group SoR: the installed DiscFacEstim_CRRA_2.0_R_1.01_edType{e}_TM_a_ESC
  rows (TM-ergodic engine, belief-consistent epoch).
- S5a multiplier anchors: the belief-consistent epoch Baseline multipliers
  (Check 1.236 / UI 1.247 / TaxCut 1.015); gate +-0.005 absolute because nothing
  this week touched the FromPandemicCode solve paths.
- S5b, two modes (2026-09-07): (i) the INTERNAL band = a broken-seed detector,
  each seed's cell within FOUR deviation-SDs of its own band's mean (bars derived
  from the measured per-seed SDs, see S5B_TOL_CELL); (ii) the SEED-PAIRED
  REFERENCE gate, `--reference-band DIR`: the fresh band against this machine's
  blessed reference at the same seed offsets, mean paired difference per cell
  (welfare_band_compare.py), after a pairing probe on the quiet cells. Only (ii)
  can see an error that hits every seed alike (the m-indexed engine, a poisoned
  equilibrium store, the plain-shuffle footgun); (i) is blind to those by
  construction. ui_norec is excluded (0/0 cell, never reported -- standing rule).
"""
import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import welfare_band_compare as wbc  # noqa: E402  (seed pairing, probe, reference loading)


def _seed_count_of_record():
    """The catalog's welfare_seed_count (machine SoT; owner 2026-08-28: S = 5)."""
    from config.catalog import by_name
    return int(by_name("welfare_seed_count").canonical)

# ---- frozen comparators (see module docstring for provenance) ----
S1_MAIN_SOR = {"splurge": 0.3010418817919867, "beta": 0.9797759350641359,
               "nabla": 0.029093359918646273}
S1_MAIN_TOL = {"splurge": 1e-3, "beta": 6e-5, "nabla": 2e-3}          # A3
S1_SPLURGE0_SOR = {"beta": 0.9263754327132292, "nabla": 0.09001127614153807}
S1_SPLURGE0_TOL = {"beta": 1e-4, "nabla": 2e-3}                        # A2
S1_UNANIMITY_TOL = 1e-4                                                # A1
S2_SOR = {0: (0.7481034372470641, 0.29163323232061783),   # Dropout
          1: (0.9387597363325278, 0.07177320535999333),   # Highschool
          2: (0.9929746941368701, 0.014677786363168077)}  # College
S2_TOL_BETA, S2_TOL_NABLA = 6e-4, 1e-2                                 # C2 (TM==MC precedent)
# D1 re-anchor (owner 2026-08-23): the 2026-08-22/23 install rerun is the
# epoch-defining run — its multipliers are the anchors. The previous anchors
# (check 1.236 / ui 1.247 / taxcut 1.015, July epoch; installed candidate
# 1.239/1.249/1.017, 08-07) were PROVEN stale: they predate the 08-14 GIC-cap
# ruling (FVAC dropped) and the 08-19 run-13 calibration install.
S5A_ANCHORS = {"check": 1.258, "ui": 1.258, "taxcut": 1.027}
S5A_TOL_ABS = 0.005                                                    # C3
S5B_TOL_REL = 5e-3                                                     # C4 (quiet cells)
# RE-TUNED 2026-09-07 (owner): the internal band is a BROKEN-SEED DETECTOR at four deviation-SDs.
# Per-seed SD measured on the 2026-09-07 bands of record (S=5, N=9,982 households, default /
# as-corrected): ui_rec 3.5 / 4.3 %, ui_rec_AD 3.9 / 3.9 %, check_rec_AD 0.55 / 0.54 %, check_rec
# 0.32 / 0.27 %, the tax-cut and no-recession cells <= 0.12 %. A seed's deviation from its OWN
# band's mean has SD sqrt(1 - 1/S) x that = 0.894 x at S=5; four of those: UI 4 x 0.894 x 3.9 %
# = 14 %, check_rec_AD 2.0 %, check_rec 1.15 % -> 1.2 %, quiet cells <= 0.43 % -> the 0.5 % bar
# stands. The previous bars (UI 3 %, check_rec_AD 1 %) sat INSIDE one SD: both bands of record
# failed them, and at 5 % eight bands in ten would still trip. A bar this wide catches only a
# seed that went wrong on its own; errors that move every seed are the paired gate's job below.
# Dilution: the deviation is from the band's OWN mean, which a bad seed pulls toward itself by
# 1/S, so the raw excursion that trips a bar is tol x S/(S-1) = 17.5 % on UI at S=5.
# Derivation and the paired-vs-unpaired measurements: conclusions_private/2026-09-07_* (pairing).
# 2026-09-07 evening the bar was narrowed to 0.09 for the income-strata engine's 2.11 / 2.37 % scatter; the owner
# REVERTED that engine 2026-09-08 (conclusions_private/2026-09-08_strata-shuffle-revert-to-plain-hamilton_decision.md),
# so the bar is back on the plain Hamilton engine's measured UI scatter, 3.49 / 3.93 % per seed (strata A/B record arm,
# S=5): four deviation-SDs = 4 x 0.894 x 3.9 % = 14 % -> 0.14.
S5B_TOL_CELL = {"ui_rec": 0.14, "ui_rec_AD": 0.14,
                "check_rec_AD": 0.02, "check_rec": 0.012}
# SEED-PAIRED REFERENCE GATE (2026-09-07): |mean paired difference| per cell, fresh band vs the
# blessed reference band at the same seed offsets. The paired SE of that mean measured <= 0.8 %
# on the UI cells across same-engine code changes (0.7 % across the 08-28 strata A/B, 0 for an
# identical engine) and <= 0.1 % on check_rec_AD, so these bars are >= 6 sigma while the pairing
# holds. Two pairing checks guard that premise: the quiet-cell PROBE (per seed within
# PAIRING_PROBE_TOL = 0.2 %; catches a model change that moves everything) and the per-cell
# RESOLUTION rule (the bar must be >= S5B_PAIRED_MIN_SIGMA paired SEs; catches a re-drawn panel or
# a changed AD path, which the quiet cells do not see). Either failing means adjudicate the change
# and re-bless the reference, never widen these bars. Bars are the owner's 2026-09-07 numbers.
S5B_PAIRED_TOL = {"ui_rec": 5e-2, "ui_rec_AD": 5e-2, "check_rec_AD": 1.5e-2, "check_rec": 1e-2}
S5B_PAIRED_TOL_REL = 5e-3                                              # quiet cells
S5B_PAIRED_MIN_SIGMA = 4.0   # a bar narrower than 4 paired SEs cannot be judged: the cell is unpaired
S5B_SKIP = {"ui_norec"}                                                # 0/0 cell


def _read_result_dict(path):
    with open(path) as f:
        return ast.literal_eval(f.read().strip())


def _rel(a, b):
    return abs(a - b) / abs(b)


class Report:
    def __init__(self, name):
        self.name, self.rows, self.ok = name, [], True

    def check(self, label, value, ref, tol, kind="rel"):
        d = _rel(value, ref) if kind == "rel" else abs(value - ref)
        ok = d <= tol
        self.ok &= ok
        self.rows.append((label, value, ref, d, tol, kind, ok))

    def fail(self, label, msg):
        self.ok = False
        self.rows.append((label, msg, "", "", "", "", False))

    def emit(self):
        print(f"\n=== GATE {self.name}: {'PASS' if self.ok else 'FAIL'} ===")
        for label, v, ref, d, tol, kind, ok in self.rows:
            if ref == "" and d == "":
                print(f"  [{'ok' if ok else 'XX'}] {label}: {v}")
            else:
                print(f"  [{'ok' if ok else 'XX'}] {label}: value={v!r} ref={ref!r} "
                      f"delta={d:.3e} ({kind}) tol={tol:.1e}")
        return 0 if self.ok else 2


def gate_s1(args):
    r = Report("S1 (A1-A3, C1)")
    d = args.dir
    # C1: the install shape requires the continuation to hold (fallback => halt).
    # Under --allow-fallback (owner-ruled battery-shape install), the fallback is
    # the SANCTIONED path: A1 is then definitionally failed and Splurge0.txt is
    # correctly withheld by the protocol, so A1/A2 are reported informationally
    # and only A3 (endpoint vs SoR, on the battery min-f winner) gates.
    fallback_fired = False
    if args.log and os.path.exists(args.log):
        log = open(args.log, errors="replace").read()
        if "FAILED unanimity" in log:
            fallback_fired = True
            if args.allow_fallback:
                r.rows.append(("C1 continuation fallback fired (ALLOWED by flag; "
                               "A1/A2 informational, A3 gates)",
                               "battery fallback", "", "", "", "", True))
            else:
                r.fail("C1 continuation", "stage-1 unanimity fallback fired "
                       "(dispersed battery ran); install shape requires continuation")
    waived = fallback_fired and args.allow_fallback
    # A1 unanimity across the 4 cold sigma=0 starts.
    sps = []
    for i in (1, 2, 3, 4):
        p = os.path.join(d, f"Result_AllTarget_Splurge0_startpoint{i}.txt")
        if os.path.exists(p):
            sps.append(_read_result_dict(p))
    if len(sps) == 4:
        for k in ("beta", "nabla"):
            vals = [s[k] for s in sps]
            spread = (max(vals) - min(vals)) / abs(sum(vals) / 4)
            if waived:
                ok = spread <= S1_UNANIMITY_TOL
                r.rows.append((f"A1 unanimity spread {k} (informational; waived)",
                               f"{spread:.3e}", "", "", "", "", True))
            else:
                r.check(f"A1 unanimity spread {k}", spread, 0.0, S1_UNANIMITY_TOL,
                        kind="abs")
    else:
        r.fail("A1", f"found {len(sps)}/4 stage-1 startpoint files in {d}")
    # A2 stage-1 result vs Splurge0 SoR.
    p0 = os.path.join(d, "Result_AllTarget_Splurge0.txt")
    if os.path.exists(p0):
        s0 = _read_result_dict(p0)
        for k in ("beta", "nabla"):
            r.check(f"A2 splurge0 {k}", s0[k], S1_SPLURGE0_SOR[k], S1_SPLURGE0_TOL[k])
    elif waived:
        r.rows.append(("A2 Splurge0.txt withheld by protocol on fallback "
                       "(correct behavior; waived)", "absent", "", "", "", "", True))
    else:
        r.fail("A2", f"missing {p0}")
    # A3 stage-2 endpoint vs main SoR.
    pe = os.path.join(d, "Result_AllTarget_ESC.txt")
    if os.path.exists(pe):
        e = _read_result_dict(pe)
        for k in ("splurge", "beta", "nabla"):
            r.check(f"A3 endpoint {k}", e[k], S1_MAIN_SOR[k], S1_MAIN_TOL[k])
    else:
        r.fail("A3", f"missing {pe}")
    return r.emit()


def gate_s2(args):
    r = Report("S2 (C2)")
    # The full 3-group run writes ONE combined file (one dict-line per group +
    # a Parameters footer); per-edType files are artifacts of single-group
    # invocations only (lesson 2026-08-23: the first version read those and saw
    # stale mtimes while the fresh combined file sat beside them).
    combined = os.path.join(args.results, "DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC.txt")
    rows = {}
    if os.path.exists(combined):
        for line in open(combined):
            line = line.strip()
            if line.startswith("{"):
                d = ast.literal_eval(line)
                rows[d["EducationGroup"]] = d
    else:
        for e in S2_SOR:
            p = os.path.join(args.results,
                             f"DiscFacEstim_CRRA_2.0_R_1.01_edType{e}_TM_a_ESC.txt")
            if os.path.exists(p):
                rows[e] = _read_result_dict(p)
    for e, (b_ref, n_ref) in sorted(S2_SOR.items()):
        if e not in rows:
            r.fail(f"C2 edType{e}", f"no row (combined={os.path.exists(combined)})")
            continue
        r.check(f"C2 edType{e} beta", rows[e]["beta"], b_ref, S2_TOL_BETA)
        r.check(f"C2 edType{e} nabla", rows[e]["nabla"], n_ref, S2_TOL_NABLA)
    return r.emit()


def gate_s5a(args):
    r = Report("S5a (C3)")
    path = args.table
    if not os.path.exists(path):
        r.fail("C3", f"missing {path}")
        return r.emit()
    row = None
    for line in open(path):
        if "Multiplier (AD effect)" in line:
            row = line
            break
    if row is None:
        r.fail("C3", f"no '(AD effect)' row in {path}")
        return r.emit()
    nums = [float(x) for x in re.findall(r"(\d+\.\d+)", row)]
    if len(nums) < 3:
        r.fail("C3", f"could not parse 3 multipliers from: {row.strip()}")
        return r.emit()
    check, ui, taxcut = nums[1:4] if len(nums) >= 4 and nums[0] == 10.0 else nums[:3]
    for name, val in (("check", check), ("ui", ui), ("taxcut", taxcut)):
        r.check(f"C3 multiplier {name}", val, S5A_ANCHORS[name], S5A_TOL_ABS,
                kind="abs")
    return r.emit()


def gate_s5b(args):
    r = Report("S5b (C4)")
    min_seeds = args.min_seeds if getattr(args, "min_seeds", None) else _seed_count_of_record()
    if getattr(args, "reference_band", None):
        # Seed-paired reference gate (2026-09-07). Fresh seeds are paired with the reference's
        # like-numbered seeds; the pairing probe comes first because every bar below is
        # calibrated on a PAIRED standard error.
        fresh = wbc.load_band(list(args.fresh))
        ref = wbc.load_band(args.reference_band)
        common = sorted(set(fresh) & set(ref))
        if len(common) < min_seeds:
            r.fail("C4 paired", f"only {len(common)} common seeds {common} (need {min_seeds}); "
                                f"fresh {sorted(fresh)}, reference {sorted(ref)}")
            return r.emit()
        if set(fresh) != set(ref):
            r.fail("C4 paired", f"seed sets differ: fresh {sorted(fresh)} vs reference {sorted(ref)}")
        ok, worst = wbc.pairing_probe(ref, fresh)
        if not ok:
            r.fail("C4 pairing probe",
                   f"streams DECOUPLED: {worst[0]} seed {worst[1]} differs {100 * worst[2]:.2f} % "
                   f"(> {100 * wbc.PAIRING_PROBE_TOL:.1f} %). A model/sampler change, not seed noise: "
                   f"adjudicate it, then re-bless the reference (make welfare-reference).")
        rows = wbc.compare_bands(ref, fresh)
        print(wbc.format_table(rows, f"C4 paired: fresh vs reference {args.reference_band} (seeds {common})"))
        for row in rows:
            if row.get("pairing") == "n/a":
                continue
            tol = S5B_PAIRED_TOL.get(row["cell"], S5B_PAIRED_TOL_REL)
            se = row["paired_se"]
            # RESOLUTION rule: every bar is calibrated on a PAIRED SE, so the bar must sit at
            # >= S5B_PAIRED_MIN_SIGMA paired SEs or the cell cannot be judged. The quiet-cell
            # probe above does not see a re-drawn PANEL (the quiet cells are insensitive to it,
            # measured default-vs-as-corrected 2026-09-07: probe silent, UI paired SE 2.2 %), so
            # this per-cell check is what catches a decoupled sampler / AD path.
            if se > 0 and tol / se < S5B_PAIRED_MIN_SIGMA:
                r.fail(f"C4 paired {row['cell']}",
                       f"UNPAIRED on this cell: paired SE {100 * se:.2f}% puts the {100 * tol:.1f}% bar at "
                       f"{tol / se:.1f} sigma (need >= {S5B_PAIRED_MIN_SIGMA:g}); per-seed differences scatter "
                       f"like independent draws ({row['pairing']}: SD {100 * row['sd_diff']:.2f}% vs unpaired "
                       f"{100 * row['unpaired_per_seed']:.2f}%). The panel sampler or AD path changed: "
                       f"adjudicate, then re-bless the reference.")
                continue
            z = abs(row["diff"]) / se if se > 0 else float("inf")
            r.check(f"C4 paired {row['cell']} (paired SE {100 * se:.2f}%, z={z:.1f})",
                    row["diff"], 0.0, tol, kind="abs")
        return r.emit()
    if args.ref is None:
        # INTERNAL band (reformulated D2, owner 2026-08-23; re-tuned 2026-09-07 to four
        # deviation-SDs, see S5B_TOL_CELL): each seed's cell against its own band's mean.
        # A broken-seed detector only; ui_norec excluded (0/0 cell).
        cells = {}
        for fp in args.fresh:
            if not os.path.exists(fp):
                r.fail("C4", f"missing {fp}")
                continue
            w = json.load(open(fp))["welfare6"]
            tag = os.path.basename(os.path.dirname(fp))
            for k, v in w.items():
                if k in S5B_SKIP:
                    continue
                cells.setdefault(k, []).append((tag, v))
        for k, vals in sorted(cells.items()):
            if len(vals) < min_seeds:
                r.fail(f"C4 {k}", f"only {len(vals)} seeds present (band of record is S={min_seeds})")
                continue
            mean = sum(v for _, v in vals) / len(vals)
            tol = S5B_TOL_CELL.get(k, S5B_TOL_REL)
            for tag, v in vals:
                r.check(f"C4 band {k} [{tag}]", v, mean, tol)
        return r.emit()
    ref = json.load(open(args.ref))["welfare6"]
    for fresh_path in args.fresh:
        if not os.path.exists(fresh_path):
            r.fail("C4", f"missing {fresh_path}")
            continue
        fresh = json.load(open(fresh_path))["welfare6"]
        tag = os.path.basename(os.path.dirname(fresh_path))
        shared = sorted((set(ref) & set(fresh)) - S5B_SKIP)
        if len(shared) < 8:
            r.fail(f"C4 {tag}", f"only {len(shared)} shared cells: {shared}")
            continue
        for k in shared:
            r.check(f"C4 {tag} {k}", fresh[k], ref[k], S5B_TOL_REL)
    return r.emit()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("s1")
    p1.add_argument("--dir", required=True,
                    help="Target_AggMPCX_LiquWealth dir holding Result_* files")
    p1.add_argument("--log", default=None, help="phase-1 log (fallback detection)")
    p1.add_argument("--allow-fallback", action="store_true")
    p1.set_defaults(fn=gate_s1)
    p2 = sub.add_parser("s2")
    p2.add_argument("--results", required=True, help="Code/HA-Models/Results dir")
    p2.set_defaults(fn=gate_s2)
    p3 = sub.add_parser("s5a")
    p3.add_argument("--table", required=True,
                    help="Multiplier_candidate.tex (or Multiplier.tex) path")
    p3.set_defaults(fn=gate_s5a)
    p4 = sub.add_parser("s5b")
    p4.add_argument("--ref", default=None,
                    help="one reference summary JSON (single-summary mode, quiet tolerance on every "
                         "cell); omit for the internal band (C4 as reformulated 2026-08-23, re-tuned "
                         "2026-09-07)")
    p4.add_argument("--reference-band", default=None,
                    help="blessed reference band dir (welfare_reference/<world>/, see "
                         "welfare_band_compare.py bless): the SEED-PAIRED gate (2026-09-07)")
    p4.add_argument("--min-seeds", type=int, default=None,
                    help="seeds a band must carry (default: the catalog's welfare_seed_count)")
    p4.add_argument("--fresh", nargs="+", required=True,
                    help="fresh per-seed summary JSONs (parent dirs end in seed<k>)")
    p4.set_defaults(fn=gate_s5b)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
