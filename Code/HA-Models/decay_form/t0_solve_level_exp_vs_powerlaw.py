"""T0 of the exp->powerlaw switch test plan (plans/2026-07-05_powerlaw-switch-test-plan.md):
deterministic solve-level comparison of HAFISCAL_PF_DECAY_EXTRAP forms.

Part 1 — IDENTITY: the HAFiscal-local ``powerlaw_decay.PowerLawDecayLinearInterp``
(pinned venv HARK) must match the HARK-PR ``LinearInterp(decay_extrap_form='powerlaw')``
(worktree) to ~1e-12 on the same knots/limits — value AND derivative. The worktree
side runs in a subprocess (two HARKs cannot share a process).

Part 2 — SOLVE-LEVEL: the most-patient College GIC-cap atom (the binding
production atom: smallest MPCmin, slowest decay; harness borrowed from
``test_pf_asymptote_decay``), solved three ways: flag OFF / '1' (exponential) /
'powerlaw'. Reports, per current Markov state at the C=1 slice:
  - in-sample |dC/C| (m in [0.5, grid-top]) exp-vs-powerlaw and OFF-vs-exp.
    NOTE: in-sample deltas are NOT identically zero by construction — the top
    EGM nodes' expectations query m' above the grid top, so the tail form feeds
    back into the converged knots (tiny, top-weighted);
  - the tail table on the production TM-a integration range m in (grid-top, 1300]:
    c_OFF, c_exp, c_powerlaw, the PF line, and each form's remaining gap;
  - Q_emp per powerlaw slice; engaged-slice counts; HALT count (solves completing
    == 0 HALTs).

Usage:
    PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
    $PY Code/HA-Models/decay_form/t0_solve_level_exp_vs_powerlaw.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

_HA = Path(__file__).resolve().parents[1]          # Code/HA-Models
_FPC = _HA / "FromPandemicCode"
for _p in (str(_HA), str(_FPC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

WORKTREE = "/home/shared/github/econ-ark/HARK-pr-aggshock-pf-decay"
OUT = []


def say(s=""):
    print(s)
    OUT.append(s)


# --------------------------------------------------------------------------- #
# Part 1: local subclass == worktree HARK powerlaw (subprocess npz exchange)
# --------------------------------------------------------------------------- #
def part1_identity():
    say("== T0 part 1: local PowerLawDecayLinearInterp vs worktree HARK powerlaw ==")
    b, s = 1.0, 0.5                       # limiting line 1 + 0.5*x, h = 2
    x = np.linspace(1.0, 21.0, 201)
    y = b + s * x - 4.0 * (x + 2.0) ** (-1.5)
    lad = np.geomspace(21.5, 5000.0, 50)
    npz = Path(tempfile.gettempdir()) / "t0_worktree_powerlaw.npz"
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import numpy as np\n"
        "from HARK.interpolation import LinearInterp\n"
        "assert %r in LinearInterp.__module__ or True\n"
        "import HARK; assert HARK.__file__.startswith(%r), HARK.__file__\n"
        "x = np.linspace(1.0, 21.0, 201)\n"
        "y = 1.0 + 0.5*x - 4.0*(x + 2.0)**(-1.5)\n"
        "f = LinearInterp(x, y, 1.0, 0.5, decay_extrap_form='powerlaw')\n"
        "lad = np.geomspace(21.5, 5000.0, 50)\n"
        "np.savez(%r, v=f(lad), d=f.derivative(lad), Q=f.decay_extrap_Q,\n"
        "         piv=f.decay_extrap_pivot)\n"
    ) % (WORKTREE, "HARK", WORKTREE, str(npz))
    subprocess.run([sys.executable, "-c", code], check=True)
    ref = np.load(npz)

    from powerlaw_decay import PowerLawDecayLinearInterp
    g = PowerLawDecayLinearInterp(x, y, 1.0, 0.5)
    dv = np.max(np.abs(g(lad) - ref["v"]))
    dd = np.max(np.abs(g.derivative(lad) - ref["d"]))
    dQ = abs(g.decay_extrap_Q - float(ref["Q"]))
    say(f"   Q local={g.decay_extrap_Q:.12f} worktree={float(ref['Q']):.12f} (|dQ|={dQ:.2e})")
    say(f"   max|value diff|      = {dv:.3e}   (ladder m in [21.5, 5000])")
    say(f"   max|derivative diff| = {dd:.3e}")
    ok = dv < 1e-12 and dd < 1e-12 and dQ < 1e-12
    say(f"   IDENTITY: {'PASS' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------- #
# Part 2: College GIC-cap atom, three solves
# --------------------------------------------------------------------------- #
def _eval_state(cf_i, m, C=1.0):
    return np.asarray(cf_i(np.asarray(m, float), np.full(len(m), float(C))))


def part2_solves():
    say("\n== T0 part 2: College GIC-cap atom — flag OFF vs '1' (exp) vs 'powerlaw' ==")
    import test_pf_asymptote_decay as tpd
    from powerlaw_decay import PowerLawDecayLinearInterp

    sols = {}
    for tag, kw in (("off", dict(decay_on=False)),
                    ("exp", dict(decay_on=True)),
                    ("pl", dict(decay_on=True, flag_value="powerlaw"))):
        ag, MPCmin, hNrm, h_AD, Cgrid = tpd._build_and_solve_college_cap(**kw)
        sols[tag] = dict(ag=ag, MPCmin=MPCmin, hNrm=hNrm)
        say(f"   solved [{tag:8s}]  MPCmin={MPCmin:.6f}  (HALT count: 0 — solve completed)")

    MPCmin = sols["pl"]["MPCmin"]
    hNrm = sols["pl"]["hNrm"]
    cf = {t: sols[t]["ag"].solution[0].cFunc for t in sols}
    S = len(cf["pl"])
    m_top = None

    # engaged slices + Q_emp + grid top (from the pl solve)
    say(f"\n   per-state decay slices (pl solve): count engaged, Q_emp range")
    q_all = []
    for i in range(S):
        slices = tpd._decay_slices(cf["pl"][i])
        qs = [f.decay_extrap_Q for f in slices
              if isinstance(f, PowerLawDecayLinearInterp)
              and getattr(f, "decay_extrap_form", "") == "powerlaw"]
        n_pl = len(qs)
        q_all += qs
        if slices and m_top is None:
            m_top = float(np.max(slices[0].x_list))
        say(f"     state {i}: engaged={len(slices)}  powerlaw={n_pl}  "
            f"Q_emp in [{min(qs):.4f}, {max(qs):.4f}]" if qs else
            f"     state {i}: engaged={len(slices)}  powerlaw=0")
    say(f"   grid top (endogenous m at aXtra top) ~ {m_top:.3f}; "
        f"Q_emp overall [{min(q_all):.4f}, {max(q_all):.4f}]")

    # in-sample deltas at C=1
    m_in = np.linspace(0.5, min(m_top - 0.5, 39.5), 160)
    say(f"\n   in-sample |dC/C| on m in [{m_in[0]:.1f}, {m_in[-1]:.1f}] at C=1 "
        f"(max over states):")
    for a, bt, lab in (("exp", "pl", "exp vs powerlaw"),
                       ("off", "exp", "OFF vs exp")):
        worst = 0.0
        for i in range(S):
            ca = _eval_state(cf[a][i], m_in)
            cb = _eval_state(cf[bt][i], m_in)
            worst = max(worst, float(np.max(np.abs(cb - ca) / np.abs(ca))))
        say(f"     {lab:18s}: max|dC/C| = {worst:.3e}")

    # tail table at C=1, state 0 (employed) + worst state, production TM range
    lad = np.array([50.0, 100.0, 200.0, 400.0, 700.0, 1000.0, 1300.0])
    say(f"\n   tail (production TM-a range), state 0, C=1:  PFline = MPCmin*(m+h), h={hNrm[0]:.2f}")
    line = MPCmin * (lad + hNrm[0])
    c_off = _eval_state(cf["off"][0], lad)
    c_exp = _eval_state(cf["exp"][0], lad)
    c_pl = _eval_state(cf["pl"][0], lad)
    say(f"     {'m':>6} {'c_OFF':>10} {'c_exp':>10} {'c_pl':>10} {'PFline':>10} "
        f"{'gap_exp/ln':>10} {'gap_pl/ln':>10} {'d(exp,pl)%':>10}")
    for k in range(len(lad)):
        say(f"     {lad[k]:6.0f} {c_off[k]:10.4f} {c_exp[k]:10.4f} {c_pl[k]:10.4f} "
            f"{line[k]:10.4f} {(line[k]-c_exp[k])/line[k]:10.2e} "
            f"{(line[k]-c_pl[k])/line[k]:10.2e} "
            f"{100*(c_exp[k]-c_pl[k])/c_pl[k]:10.4f}")
    say(f"\n   tail summary across ALL states at C=1 (m=1300): "
        f"max |c_exp-c_pl|/c = "
        + format(max(float(np.max(np.abs(
            _eval_state(cf['exp'][i], lad[-1:]) - _eval_state(cf['pl'][i], lad[-1:])
        ) / _eval_state(cf['pl'][i], lad[-1:]))) for i in range(S)), ".3e"))
    return True


def main():
    ok1 = part1_identity()
    part2_solves()
    text = "\n".join(OUT)
    with open(Path(__file__).with_name("t0_out.txt"), "w") as f:
        f.write(text + "\n")
    if not ok1:
        sys.exit(1)


if __name__ == "__main__":
    main()
