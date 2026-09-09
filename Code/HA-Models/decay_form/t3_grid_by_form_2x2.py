"""T3 of the exp->powerlaw switch test plan: {solve grid} x {decay form} 2x2 on the
College GIC-cap atom (the binding production atom).

Question: how much does the decay-form choice still matter once BUG-061's
endogenous grid (HAFISCAL_ENDOGENOUS_GRID=1) extends the solve grid past the
legacy aXtraMax=40? And: does powerlaw-at-grid40 approximate the extended-grid
solve better than exp-at-grid40 (the extrapolator as a cheap grid substitute)?

Mechanics: HAFISCAL_ENDOGENOUS_GRID is read at EstimParameters IMPORT time, so
each grid config runs in a fresh SUBPROCESS (child mode) that solves the atom
under all three flag states (off/'1'/'powerlaw' -- solve-time env) and dumps
cFunc evaluations; the parent assembles the 2x2 tables. The extended-grid solve
is the closest-to-truth reference on (41, m_top_endo] (in-sample there).

Usage:
    PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
    $PY Code/HA-Models/decay_form/t3_grid_by_form_2x2.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

_HA = Path(__file__).resolve().parents[1]
_FPC = _HA / "FromPandemicCode"
LAD_IN = np.linspace(0.5, 39.5, 160)
LAD_TAIL = np.array([50.0, 100.0, 200.0, 400.0, 700.0, 1000.0, 1300.0])


def child(out_path):
    for _p in (str(_HA), str(_FPC)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    import test_pf_asymptote_decay as tpd
    res = {}
    for tag, kw in (("off", dict(decay_on=False)),
                    ("exp", dict(decay_on=True)),
                    ("pl", dict(decay_on=True, flag_value="powerlaw"))):
        ag, MPCmin, hNrm, h_AD, Cgrid = tpd._build_and_solve_college_cap(**kw)
        cf = ag.solution[0].cFunc
        S = len(cf)
        c_in = np.array([cf[i](LAD_IN, np.full(LAD_IN.shape, 1.0)) for i in range(S)])
        c_tail = np.array([cf[i](LAD_TAIL, np.full(LAD_TAIL.shape, 1.0)) for i in range(S)])
        qs = []
        for i in range(S):
            for f in tpd._decay_slices(cf[i]):
                q = getattr(f, "decay_extrap_Q", None)
                if q is not None:
                    qs.append(float(q))
        res[tag] = dict(c_in=c_in.tolist(), c_tail=c_tail.tolist(), Q=qs)
        if tag == "pl":
            res["meta"] = dict(MPCmin=float(MPCmin), hNrm=np.asarray(hNrm).tolist(),
                               m_top=float(np.max(tpd._decay_slices(cf[0])[0].x_list))
                               if tpd._decay_slices(cf[0]) else None,
                               S=S)
    with open(out_path, "w") as f:
        json.dump(res, f)


def main():
    scratch = Path(os.environ.get("T3_SCRATCH", "/tmp")) / "t3_children"
    scratch.mkdir(parents=True, exist_ok=True)
    out = []

    def say(s=""):
        print(s)
        out.append(s)

    data = {}
    for gtag, genv in (("grid40", "0"), ("endo", "1")):
        j = scratch / f"t3_{gtag}.json"
        env = dict(os.environ, HAFISCAL_ENDOGENOUS_GRID=genv, PYTHONUNBUFFERED="1")
        env.pop("HAFISCAL_PF_DECAY_EXTRAP", None)
        subprocess.run([sys.executable, __file__, "--child", str(j)],
                       env=env, check=True, capture_output=True)
        with open(j) as f:
            data[gtag] = json.load(f)
        say(f"[{gtag}] solved (m_top={data[gtag]['meta']['m_top']:.2f}, "
            f"S={data[gtag]['meta']['S']}, "
            f"Q_emp range [{min(data[gtag]['pl']['Q']):.3f}, {max(data[gtag]['pl']['Q']):.3f}])")

    say("\n== T3: {solve grid} x {decay form} on the College GIC-cap atom, C=1 ==")
    # (1) within-grid form effect
    for gtag in ("grid40", "endo"):
        ci_e = np.array(data[gtag]["exp"]["c_in"]); ci_p = np.array(data[gtag]["pl"]["c_in"])
        ct_e = np.array(data[gtag]["exp"]["c_tail"]); ct_p = np.array(data[gtag]["pl"]["c_tail"])
        d_in = float(np.max(np.abs(ci_p - ci_e) / np.abs(ci_e)))
        d_tail = np.max(np.abs(ct_p - ct_e) / np.abs(ct_e), axis=0)  # per tail point
        say(f"\n  [{gtag}] exp-vs-powerlaw:  in-sample max|dC/C| = {d_in:.3e}")
        say("    tail max-over-states |dC/C|: " + "  ".join(
            f"m={int(m)}:{d:.2e}" for m, d in zip(LAD_TAIL, d_tail)))
    # (2) cross-grid: which grid40 form tracks the endo solve better?
    #     (endo solve = in-sample truth on (41, m_top_endo]; use its 'pl' variant
    #      -- identical to 'exp' in-sample up to the tiny feedback)
    ref = np.array(data["endo"]["pl"]["c_tail"])
    say(f"\n  grid40 forms vs the extended-grid solve (reference, in-sample to "
        f"m={data['endo']['meta']['m_top']:.0f}):")
    say(f"    {'m':>6} {'|exp40-endo|/c':>15} {'|pl40-endo|/c':>15} {'ratio':>7}")
    for k, m in enumerate(LAD_TAIL):
        if m > data["endo"]["meta"]["m_top"]:
            break
        ee = np.max(np.abs(np.array(data["grid40"]["exp"]["c_tail"])[:, k] - ref[:, k]) / ref[:, k])
        ep = np.max(np.abs(np.array(data["grid40"]["pl"]["c_tail"])[:, k] - ref[:, k]) / ref[:, k])
        say(f"    {int(m):6d} {ee:15.3e} {ep:15.3e} {ee/ep if ep>0 else float('inf'):7.1f}")
    text = "\n".join(out)
    with open(Path(__file__).with_name("t3_out.txt"), "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()
