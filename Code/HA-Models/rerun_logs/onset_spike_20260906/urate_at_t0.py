#!/usr/bin/env python3
"""What the onset spike does to the RECORDED unemployment rate at the first quarter.

The spike is calibrated so that the unemployment rate is `Urate_recession` immediately after
households are relabelled. But the recorded period 0 comes one transition later, so what the
model actually reports at t = 0 depends on the ORDER of the spike and that transition. This
script computes the recorded rate under each ordering, analytically from the chains themselves
(no simulation), for every education group.

    published   spike, then transition   -- the QE code's ordering
    exempt      spike, then hold the spiked for one period (HAFISCAL_ONSET_SPIKE_T0_EXEMPT)
    after       transition, then spike    -- lay off from the POST-transition employed

`published` and `after` both hit the target rate at t = 0 when job-finding does not depend on
the benefit state; `exempt` overshoots it by the job-finding flow it withholds from the spiked
cohort. That overshoot is the price of an honest benefit-quarter label, and this prints it.
"""

import sys
from pathlib import Path

import numpy as np

FPC = Path(__file__).resolve().parents[2] / "FromPandemicCode"
sys.path.insert(0, str(FPC))
sys.argv = ["urate_at_t0"]

from Parameters import return_parameters  # noqa: E402

(make_macro_mrkv_array_recession, make_cond_mrkv_arrays_recession, make_full_mrkv_array,
 T_sim, make_cond_mrkv_arrays_base, make_cond_mrkv_arrays_recession_ui) = return_parameters(
    OutputFor="_Model.py")

import EstimParameters as EP  # noqa: E402


def ergodic(mat):
    vals, vecs = np.linalg.eig(np.asarray(mat, dtype=float).T)
    v = np.real(vecs[:, int(np.argmin(np.abs(np.abs(vals) - 1.0)))])
    return v / v.sum()


def report(label, Un, Ur, Uspell_n, Uspell_r, UBspell_n, n_exp):
    base = make_cond_mrkv_arrays_base(Un, Uspell_n, UBspell_n)[0]
    rec = make_cond_mrkv_arrays_recession(Un, Uspell_n, UBspell_n, Ur, Uspell_r, n_exp)
    T = np.asarray(rec[1], dtype=float)          # macro state 1 = the recession's own chain
    pi = ergodic(base)

    f = (Ur - Un) / (1.0 - Un)
    pi_hit = pi.copy()
    pi_hit[1] += pi_hit[0] * f
    pi_hit[0] *= (1.0 - f)

    u_published = 1.0 - (pi_hit @ T)[0]

    row0 = (1.0 - f) * T[0, :] + f * np.eye(T.shape[0])[1]
    T_ex = T.copy(); T_ex[0, :] = row0
    u_exempt = 1.0 - (pi @ T_ex)[0]

    pi_T = pi @ T
    u_T = 1.0 - pi_T[0]
    f_after = (Ur - u_T) / (1.0 - u_T) if u_T < Ur else 0.0
    u_after = u_T + f_after * (1.0 - u_T)

    # where the spiked cohort SITS at t = 0 (its benefit-quarter label), each ordering
    spiked_mass = pi[0] * f
    lab_pub = T[1, :] * spiked_mass          # transitioned out of the first benefit state
    lab_ex = np.zeros_like(T[0, :]); lab_ex[1] = spiked_mass

    print(f"## {label}")
    print(f"   target recession rate Ur      {Ur:.6f}   (normal {Un:.6f}, spike fraction {f:.6f})")
    print(f"   recorded u(0), published      {u_published:.6f}   ({u_published - Ur:+.6f} vs target)")
    print(f"   recorded u(0), exempt         {u_exempt:.6f}   ({u_exempt - Ur:+.6f} vs target)")
    print(f"   recorded u(0), spike after    {u_after:.6f}   ({u_after - Ur:+.6f} vs target)")
    print(f"   spiked cohort at t=0, published: " +
          " ".join(f"s{j}={v/spiked_mass:.3f}" for j, v in enumerate(lab_pub) if v > 1e-12))
    print(f"   spiked cohort at t=0, exempt   : " +
          " ".join(f"s{j}={v/spiked_mass:.3f}" for j, v in enumerate(lab_ex) if v > 1e-12))
    print()


def main():
    n_exp = int(getattr(EP, "num_experiment_periods", 20))  # Uspell_recession = 4 (Parameters.py:325)
    for tag, un in (("dropout", EP.Urate_normal_d), ("high school", EP.Urate_normal_h),
                    ("college", EP.Urate_normal_c)):
        report(tag, float(un), 2.0 * float(un), float(EP.Uspell_normal), 4.0,
               int(EP.UBspell_normal), n_exp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
