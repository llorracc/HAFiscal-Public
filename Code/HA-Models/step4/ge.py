"""Step-4 GE/SAM stage (live engine): HANK-SAM models + policy experiments.

Faithful function-wrapped port of the frozen GE monolith
(HA-Fiscal-HANK-SAM-to-python.py): same SAM calibration, same
sequence_jacobian blocks (which close over the calibration exactly as
the monolith's module globals did), same experiment choreography —
including the deliberate historical quirks pending owner rulings:
  * hardcoded steady-state anchors (H4; HAFISCAL_HANK_SS_SOURCE probes),
  * splurge selector (H1; HAFISCAL_HANK_SPLURGE, default legacy 0.3),
  * mixed multiplier regime in the pickle (H2; HAFISCAL_HANK_MULT_REGIME),
  * the UJAC ergodic-advection carry-over between columns (F-5,
    underflow-benign, preserved bit-for-bit).
Output: Results_HANK/multipliers_across_horizon_w_splurge.obj + the
Section-5 figure family (via figures.py, candidate-routed).
"""
import os
import pickle
from copy import deepcopy

import numpy as np
import scipy.sparse as sp

from . import figures
from .common import FPC_DIR, HA_MODELS_DIR, ensure_paths

ensure_paths()

JACS_OBJ = os.path.join(FPC_DIR, 'HA_Fiscal_Jacs.obj')
RESULTS_DIR = os.path.join(HA_MODELS_DIR, 'Results_HANK')
OUTPUT_PICKLE = os.path.join(RESULTS_DIR, 'multipliers_across_horizon_w_splurge.obj')
# S3 knob (2026-08-30): the 'fixed nominal rate' regime is the Taylor block with phi_pi = 0 forever -- indeterminate
# (Leeper passive/passive), so the truncated system's TERMINAL WEALTH entry selects the member. Measured 2026-09-01:
# scaling the single entry J_A[T-1, 0] takes this multiplier through a pole (-140.6 -> +18.7 between alpha 0.58 and
# 0.60) while the Taylor multiplier moves in its 4th decimal. NOT the truncation horizon, which is worth 1.1% over
# bigT 250-550. HAFISCAL_HANK_PHI_PI_FIXED measures the fragility; 0.0 = the published construction.
_PHI_PI_FIXED = float(os.environ.get('HAFISCAL_HANK_PHI_PI_FIXED', '0.0'))


def resolve_hank_splurge(environ=None):
    """The overlay's splurge (R-c, owner ruling 2026-08-09): ``HAFISCAL_HANK_SPLURGE`` =
    ``calib`` (default; the live interpretation-resolved ``EstimParameters.Splurge``, the value
    the block's beta-hats were estimated jointly with) | ``legacy`` (the historical hardcode 0.3,
    Will's 2024 notebook, matching no estimate) | an explicit float.

    BUG-100 (2026-08-28, found by the Econ-9 ladder's arm 5c): ``HAFISCAL_QE_FIDELITY=1`` used to
    force 0.3 even when ``HAFISCAL_HANK_SPLURGE`` was set explicitly, so a QE-fidelity arm could
    not run the calibrated splurge without unsetting QE_FIDELITY (and with it every other
    published default). Now QE_FIDELITY only supplies the DEFAULT (``legacy``); an explicit
    per-flag value wins, the convention everywhere else in the pipeline.
    """
    env = os.environ if environ is None else environ
    raw = env.get("HAFISCAL_HANK_SPLURGE")
    if raw is None or not raw.strip():
        mode = "legacy" if env.get("HAFISCAL_QE_FIDELITY", "") == "1" else "calib"
    else:
        mode = raw.strip().lower()
    if mode == "legacy":
        return 0.3
    if mode == "calib":
        from EstimParameters import Splurge as _calib_splurge
        return float(_calib_splurge)
    return float(mode)


def run():
    os.makedirs(figures.figures_dir, exist_ok=True)

    # ---- SAM employment chain + ergodic state -------------------------
    # BUG-076 (owner-ruled 2026-08-10; stage A of the tax-alignment plan
    # 20260810-1030h): the chains are consumed from ONE source —
    # hh_setup.unemployment_chains() — retiring this file's duplicate
    # literals. "pe" (DEFAULT): the education-specific PE base chains
    # (Urate_normal_{d,h,c} = 0.085/0.044/0.027). "legacy": the single
    # shared chain (the PE Highschool process — EU_prob 0.0306834 is the
    # HS separation rate rounded to 7 digits) on the single-chain code
    # path below, with NO population weighting, so the escape stays
    # byte-identical to the historical construction.
    from .hh_setup import create_matrix_U, unemployment_chains
    _uc = unemployment_chains()
    job_find = _uc["jf"]

    dx = 0.0001
    bigT = int(os.environ.get("HAFISCAL_HANK_BIGT", "300"))   # S3 knob (2026-08-30); must equal hh_setup.bigT (same env)

    if _uc["mode"] == "legacy":
        markov_array_ss = _uc["chains_cs"][0]
        job_sep = _uc["seps"][0]
        mrkv_temp_for_will = markov_array_ss
        num_mrkv = len(markov_array_ss)

        eigen, ss_dstn = sp.linalg.eigs(mrkv_temp_for_will, k=1, which='LM')
        ss_dstn = ss_dstn[:, 0] / np.sum(ss_dstn[:, 0])
        ss_dstn = ss_dstn.real

        dstn = ss_dstn

        # Unemployment-rate Jacobian. F-5 (dossier): dstn deliberately NOT
        # reset between s columns — after each 300-period column the chain
        # has re-mixed to ergodic, so the carry-over is underflow-class;
        # preserved bit-for-bit from the monolith.
        # Dating: the perturbed push is recorded AT row s of column s (`if i == s`),
        # i.e. eta_s is the probability of the draw INTO date s -- the same
        # convention the household block uses.  If these two ever disagreed, every
        # GE experiment would mix two datings.  See jacobians.py, "THE DATING OF eta".
        UJAC = np.zeros((num_mrkv, bigT, bigT))
        for s in range(bigT):
            for i in range(bigT):
                if i == s:
                    tranmat = create_matrix_U(dx)
                    dstn = np.dot(tranmat, dstn)
                else:
                    dstn = np.dot(mrkv_temp_for_will, dstn)
                UJAC[:, i, s] = (dstn - ss_dstn) / dx

        ss_dstn_by_educ = [ss_dstn] * 3
        print(f"[ge-chains] LEGACY shared chain: u_ss = {1 - ss_dstn[0]:.4f} "
              "(the HS process for all groups)", flush=True)
    else:
        # The SAM chain's count from the chains themselves (the EMPLOYMENT
        # chain: 6 with or without the household block's earnings phase —
        # hh_setup.unemployment_chains extracts the employment block). The
        # blocks below name U1..U5 explicitly, so 6 is asserted, not assumed.
        num_mrkv = len(_uc["chains_cs"][0])
        assert num_mrkv == 6, f"GE SAM blocks are written for 6 employment states, got {num_mrkv}"
        _shares = _uc["shares"]

        # Per-group ergodic distributions; the AGGREGATE state shares are
        # the population-weighted mixture (NOT the ergodic of a weighted
        # matrix — shares are per-capita masses, so mixing is exact).
        ss_dstn_by_educ = []
        for _m_cs in _uc["chains_cs"]:
            _eig, _v = sp.linalg.eigs(_m_cs, k=1, which='LM')
            _v = (_v[:, 0] / np.sum(_v[:, 0])).real
            ss_dstn_by_educ.append(_v)
        ss_dstn = sum(w * v for w, v in zip(_shares, ss_dstn_by_educ))

        # Per-group unemployment-rate Jacobians, aggregated with the
        # population shares (state shares are population-weighted, so the
        # aggregate eta-response IS the weighted sum; the +dx job-find
        # shock is the SAME instrument for every group — common jf=2/3
        # base, group-specific separations — so units are consistent).
        # The F-5 carry-over semantics (dstn not reset between s columns)
        # are replicated per chain.
        UJAC = np.zeros((num_mrkv, bigT, bigT))
        for _w, _m_cs, _v_e in zip(_shares, _uc["chains_cs"], ss_dstn_by_educ):
            _rs = _m_cs.T
            _dstn = _v_e
            _UJ = np.zeros((num_mrkv, bigT, bigT))
            for s in range(bigT):
                for i in range(bigT):
                    if i == s:
                        tranmat = create_matrix_U(dx, base_rs=_rs)
                        _dstn = np.dot(tranmat, _dstn)
                    else:
                        _dstn = np.dot(_m_cs, _dstn)
                    _UJ[:, i, s] = (_dstn - _v_e) / dx
            UJAC += _w * _UJ

        # Firm-side separation rate = the employment-weighted aggregate:
        # ONE matching market (common job-finding moved by tightness),
        # education-specific separations — total separations flow over
        # total employment.
        _sep_flow = sum(w * v[0] * s_e for w, v, s_e in
                        zip(_shares, ss_dstn_by_educ, _uc["seps"]))
        job_sep = _sep_flow / float(sum(w * v[0] for w, v in
                                        zip(_shares, ss_dstn_by_educ)))
        print("[ge-chains] PE per-education chains (BUG-076): u by educ = "
              + "/".join(f"{1 - v[0]:.4f}" for v in ss_dstn_by_educ)
              + f"; weighted u_ss = {1 - ss_dstn[0]:.4f}; "
              + f"job_sep(agg) = {job_sep:.6f}", flush=True)

    U_ss = (1 - ss_dstn[0])
    N_ss = ss_dstn[0]

    # ---- General-equilibrium calibration ------------------------------
    alpha = .65        # matching elasticity
    phi_ss = .71       # vacancy filling probability
    v_ss = N_ss * job_sep / phi_ss

    unemployed_searchers = (ss_dstn[1] + ss_dstn[2] + ss_dstn[3] + ss_dstn[4] + ss_dstn[5])
    seachers = unemployed_searchers + N_ss * job_sep
    theta_ss = v_ss / seachers                                  # labor market tightness
    chi_ss = (phi_ss ** (1 / -alpha) / theta_ss) ** (-alpha)    # matching efficiency
    eta_ss = chi_ss * theta_ss ** (1 - alpha)                   # job finding probability
    # BUG-076 tripwire: eta_ss = hires/searchers must equal the common
    # job-finding probability EXACTLY (each group's flow identity
    # U_e = N_e*sep_e*(1-jf)/jf makes hires_e = jf*searchers_e, so the
    # aggregate ratio is jf under any population weighting); a violation
    # means the chains/weights are inconsistent.
    assert abs(eta_ss - job_find) < 1e-9, (eta_ss, job_find)

    R = 1.01
    r_ss = R - 1

    # Asset-market calibration (R-d ADOPTED 2026-08-09; closure appendix
    # in conclusions_private/2026-08-09_appendix-draft_ge-asset-market-
    # closure.md; guarded by RECONCILED-003): the GE asset market is the
    # DOMESTIC GOVERNMENT BOND market, and its steady-state market value
    # qb_ss*B_ss is CALIBRATED TO DATA — 1.4324 in quarterly-PI units =
    # 31% of annual GDP (privately-held federal debt, SCF-2004 vintage).
    # It is deliberately NOT the household block's total wealth A_hh
    # (~8.5): that aggregate is non-identified (unconverged in the
    # distribution grid, 26x across estimation vintages, ~57% held by
    # the single GPF-capped College atom — probes in
    # 2026-08-09_rd-closure-probes.md). The household block's excess
    # wealth is outside (world) assets earning the same R; only bonds
    # enter the linearized dynamics, and the fixed-real-rate results
    # are exactly invariant to this level.
    qbB_ss_data = 1.4324029855872642  # market value of household bond holdings
    A_ss = A_ss_sim = qbB_ss_data

    # Steady-state consumption: the household block's own aggregate,
    # read from the Jacobian stage's emission (flow-identity-verified to
    # 1.9e-4; effect of the update on every multiplier <= 4e-9).
    # HAFISCAL_HANK_SS_SOURCE: "jacs_c" (DEFAULT since the R-d ruling),
    # "hardcoded" = the frozen September-2024 literal (historical
    # escape; the QE-fidelity monolith's construction), "jacs" = the
    # full-consistency counterfactual (feeds A_hh into the bond slot) —
    # an INTERNAL ROBUSTNESS arm only, rejected as a calibration by the
    # closure appendix (184%-of-GDP debt; -4.7%-of-Y goods identity).
    _ss_src = os.environ.get("HAFISCAL_HANK_SS_SOURCE", "jacs_c").strip().lower()
    if _ss_src in ("jacs", "jacs_c"):
        with open(JACS_OBJ, 'rb') as _f:
            _jacs_ss = pickle.load(_f)
        C_ss = C_ss_sim = float(_jacs_ss['C_ss_weighted'])
        if _ss_src == "jacs":
            A_ss = A_ss_sim = float(_jacs_ss['A_ss_weighted'])
            print(f"[hank-ss] FULL-CONSISTENCY ROBUSTNESS ARM: "
                  f"C_ss={C_ss:.6f} A_ss={A_ss:.6f}", flush=True)
        else:
            print(f"[hank-ss] C_ss={C_ss:.6f} from the household block; "
                  f"bond market qb*B={A_ss:.6f} (data-calibrated)", flush=True)
        del _jacs_ss
    else:
        C_ss = C_ss_sim = 0.6910496136078721  # September-2024 vintage literal
        print("[hank-ss] C_ss = historical 2024 literal (hardcoded escape)", flush=True)

    delta = ((R ** 4) * (1 - (1 / 5))) ** (1 / 4)   # long-bond decay
    qb_ss = (1) / (R - delta)                       # real price of bonds
    B_ss = A_ss / qb_ss                             # steady state bonds
    wage_ss = 1.0

    inc_ui_exhaust = 0.5
    # BUG-077 stage B: tau_ss from the ONE shared source (retires this
    # file's 0.3 literal; hh_setup's twin is retired the same way).
    from .common import resolve_tau_ss
    tau_ss, _tau_mode = resolve_tau_ss()

    # Government UI basket (owner 2026-08-10, "importing the PE income
    # spec into HANK-SAM"): under the derived tau* the ledger books the
    # FULL 0.7 net-indexed benefit for the eligible (the PE spec's UI
    # program — what the extension experiment extends); only the
    # exhausted 0.5 floor stays private. legacy keeps the historical
    # 0.5-core booking (whose implied "private top-up to the
    # benefit-eligible" had no economic reading) byte-for-byte.
    if _tau_mode == "legacy":
        _ui_rr_booked = .5
        _ypriv_topup = .2
    else:
        _ui_rr_booked = .7
        _ypriv_topup = 0.0
    UI = (1 - tau_ss) * _ui_rr_booked * wage_ss

    # private/passive spousal income (module-scope value in the monolith;
    # computed but not consumed by any block — mkt_clearing recomputes its
    # own Y_priv from U-states)
    Y_priv = inc_ui_exhaust * (1 - tau_ss) * wage_ss * (ss_dstn[3] + ss_dstn[4] + ss_dstn[5]) \
        + _ypriv_topup * (1 - tau_ss) * wage_ss * (ss_dstn[1] + ss_dstn[2])

    G_ss = tau_ss * wage_ss * ss_dstn[0] - (UI * (ss_dstn[1] + ss_dstn[2])
                                            + (1 + delta * qb_ss) * B_ss - qb_ss * B_ss)
    print(f"[hank-tau] tau_ss={tau_ss:.6f} ({_tau_mode}); UI booked at "
          f"{_ui_rr_booked} net-indexed; G_ss residual = {G_ss:.3e}"
          + (" (machine-zero under tau*)" if _tau_mode == "derived" else ""),
          flush=True)

    kappa = .07 * (wage_ss * phi_ss)  # vacancy posting cost: 7% of the real wage
    HC_ss = ((kappa / phi_ss) * (1 - (1 / R) * (1 - job_sep)) + wage_ss)

    epsilon_p = 6
    MC_ss = (epsilon_p - 1) / epsilon_p
    Z_ss = HC_ss / MC_ss
    Y_ss = Z_ss * N_ss

    pi_ss = 0.0
    phi_pi = 1.5
    phi_y = 0.0
    varphi = 96.9
    rho_r = 0.0
    kappa_p_ss = epsilon_p / varphi
    print('slope of phillips curve', kappa_p_ss)
    phi_b = .1

    # Phase-C dials (ladder plan 20260901-2010h §5.5): the production values
    # are the literals used below (kappa_p_ss; phi_b=0.015; Taylor phi_pi=1.5).
    # The env knobs exist so the gated ladder can dial kappa_p (the G-KP
    # collapse gate and the kappa_p ramp), phi_b (the G-PHIB sweep) and the
    # Taylor phi_pi (the F5 / G-COND sigma_min profile) without editing this
    # file. HAFISCAL_HANK_PHI_PI_FIXED is a DIFFERENT knob (the excluded peg
    # regime's coefficient), untouched by these.
    _KAPPA_P = float(os.environ.get("HAFISCAL_HANK_KAPPA_P", "") or kappa_p_ss)
    _PHI_B = float(os.environ.get("HAFISCAL_HANK_PHI_B", "") or 0.015)
    _PHI_PI_TAYLOR = float(os.environ.get("HAFISCAL_HANK_PHI_PI_TAYLOR", "") or 1.5)
    # HAFISCAL_HANK_RHO_R — interest smoothing in the SAME taylor block the
    # production rule uses (i = rho_r*i(-1) + (1-rho_r)*(phi_pi*pi + phi_y*Y)
    # + ev). DEFAULT-WORLD DEFAULT = 0.70 (IMPROVEMENT-003, owner ruling
    # 2026-09-02: the corrected household block puts the published un-smoothed
    # rule at/past its upper determinacy boundary — the period-2 mode's
    # modulus reaches 1 under wealth-grid refinement — and rho_r = 0.7, the
    # middle of the empirical range, cuts the rule's gain at the alternating
    # frequency ~5.7x, restoring a well-posed Taylor arm at every grid).
    # The paper's own rule (rho_r = 0) is kept under HAFISCAL_QE_FIDELITY=1
    # and in the as-corrected world (the specification change is an adopted
    # improvement, not a bug fix). Explicit env always wins. rho_r enters
    # the solved blocks only through derivatives, so no SS re-anchoring is
    # needed; the fixed-real DAG never composes the taylor block, so it is
    # structurally invariant. Record: conclusions_private/2026-09-02_taylor-
    # arm-zigzag-…md + IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-003_….md.
    _rr_qe_fid = os.environ.get("HAFISCAL_QE_FIDELITY", "").strip().lower() in ("1", "on", "true")
    _rr_world_ac = os.environ.get("HAFISCAL_WORLD", "default").strip().lower() == "as-corrected"
    _RHO_R_DEFAULT = 0.0 if (_rr_qe_fid or _rr_world_ac) else 0.70
    _rr_raw = os.environ.get("HAFISCAL_HANK_RHO_R", "").strip()
    _RHO_R = float(_rr_raw) if _rr_raw else _RHO_R_DEFAULT
    print(f"[hank-rho-r] rho_r = {_RHO_R:g} "
          f"({'explicit env' if _rr_raw else 'default: ' + ('paper rule (QE-fidelity/as-corrected)' if _RHO_R_DEFAULT == 0.0 else 'IMPROVEMENT-003, default world')})",
          flush=True)
    if _KAPPA_P != kappa_p_ss or _PHI_B != 0.015 or _PHI_PI_TAYLOR != 1.5:
        print(f"[hank-dials] kappa_p={_KAPPA_P} phi_b={_PHI_B} "
              f"phi_pi_taylor={_PHI_PI_TAYLOR} (env-dialed; production = "
              f"{kappa_p_ss:.6f}/0.015/1.5)", flush=True)

    # ---- sequence_jacobian blocks (close over the calibration above) --
    import sequence_jacobian as sj
    from sequence_jacobian.classes import JacobianDict, SteadyStateDict
    from sequence_jacobian import create_model

    @sj.simple
    def unemployment1(U1, U2, U3, U4, U5):
        U = U1 + U2 + U3 + U4 + U5
        return U

    @sj.simple
    def marginal_cost(HC, Z):
        MC = HC / Z
        return MC

    @sj.solved(unknowns={'HC': (-10, 10.0)}, targets=['HC_resid'], solver="brentq")
    def hiring_cost(HC, Z, phi, job_sep, r_ante, w):
        HC_resid = HC - ((w + (kappa / (phi)) - (1 / (1 + r_ante)) * (1 - job_sep) * (kappa / (phi(+1)))))
        return HC_resid

    phi_w = 1.0

    @sj.solved(unknowns={'w': (-10, 10.0)}, targets=['wage_resid'], solver="brentq")
    def wage_(w, N, phi_w):
        wage_resid = (w / wage_ss).apply(np.log) - (phi_w * (w(-1) / wage_ss).apply(np.log)
                                                    + (1 - phi_w) * (N / N_ss).apply(np.log))
        return wage_resid

    @sj.solved(unknowns={'pi': (-0.1, 0.1)}, targets=['nkpc_resid'], solver="brentq")
    def Phillips_Curve(pi, MC, Y, r_ante, epsilon_p, kappa_p):
        nkpc_resid = (1 + pi).apply(np.log) - (kappa_p * (MC - MC_ss)
                                               + (1 / (1 + r_ante)) * (Y(+1) / Y) * (1 + pi(+1)).apply(np.log))
        return nkpc_resid

    @sj.solved(unknowns={'i': (-.5, 0.4)}, targets=['taylor_resid'], solver="brentq")
    def taylor(i, pi, Y, ev, rho_r, phi_y, phi_pi):
        taylor_resid = i - rho_r * i(-1) - (1 - rho_r) * (phi_pi * pi + phi_y * Y) - ev
        return taylor_resid

    @sj.solved(unknowns={'i': (-.5, 0.4)}, targets=['taylor_resid'], solver="brentq")
    def taylor_lagged(i, pi, Y, ev, rho_r, phi_y, phi_pi, lag):
        taylor_resid = i - rho_r * i(-1) - (1 - rho_r) * (phi_pi * pi(-lag) + phi_y * Y(-lag)) - ev
        return taylor_resid

    @sj.simple
    def matching(theta, chi):
        # eta_t = the probability of entering employment AT date t (matches form at
        # the start of the period; households consume after they form).  The dating
        # is the paper's -- Appendix-HANK.tex, the "Timing" paragraph under Matching --
        # and it is what makes the household block's eta column 0 compositional; the
        # single statement lives in jacobians.py, "THE DATING OF eta".
        eta = chi * theta ** (1 - alpha)
        phi = chi * theta ** (-alpha)
        return eta, phi

    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal(B, N, qb, G, w, v, pi, phi_b, UI, U1, U2, U3, U4, transfers, UI_extend, deficit_T, UI_rr):
        fiscal_resid = (1 + delta * qb) * B(-1) + G + transfers + UI * (U1 + U2) \
            + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
            + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
            + - qb * B - (tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss) * w * N
        UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
        UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
        debt = qb * B
        return fiscal_resid, UI_extension_cost, debt, UI_rr_cost

    @sj.simple
    def fiscal_rule(B, phi_b, deficit_T):
        tau = tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
        return tau

    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal_G(B, N, qb, w, v, pi, UI, U1, U2, transfers, phi_G, tau, deficit_T):
        fiscal_resid = (1 + delta * qb) * B(-1) + G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss \
            + transfers + UI * (U1 + U2) + - qb * B - (tau) * w * N
        tax_cost = (tau) * 1.0 * N_ss
        return fiscal_resid, tax_cost

    @sj.simple
    def fiscal_rule_G(B, phi_G, deficit_T):
        G = G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
        return G

    @sj.simple
    def production(Z, N):
        Y = Z * N
        return Y

    @sj.simple
    def ex_post_longbonds_rate(qb):
        r = (1 + delta * qb) / qb(-1) - 1
        return r

    @sj.solved(unknowns={'qb': (0.1, 30.0)}, targets=['lbp_resid'], solver="brentq")
    def longbonds_price(qb, r_ante):
        lbp_resid = qb - (1 + delta * qb(+1)) / (1 + r_ante)
        return lbp_resid

    @sj.simple
    def vacancies(N, phi, job_sep):
        v = (N - (1 - job_sep(-1)) * N(-1)) / phi
        return v

    @sj.simple
    def mkt_clearing(C, G, A, qb, B, w, N, U1, U2, U3, U4, U5):
        Y_priv = (1 - tau_ss) * wage_ss * .5 * (U3 + U4 + U5) + (1 - tau_ss) * wage_ss * _ypriv_topup * (U1 + U2)
        goods_mkt = C + G - w * N - Y_priv
        asset_mkt = A - qb * B
        return goods_mkt, asset_mkt, Y_priv

    @sj.simple
    def fisher_clearing(r_ante, pi, i):
        fisher_resid = 1 + r_ante - ((1 + i) / (1 + pi(+1)))
        return fisher_resid

    @sj.simple
    def fisher_clearing_fixed_real_rate(pi):
        i = (1 + pi(+1)) * (1 + r_ss) - 1
        return i

    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal_fixed_real_rate(B, N, G, w, v, pi, phi_b, UI, U1, U2, U3, U4, transfers, UI_extend, deficit_T, UI_rr):
        fiscal_resid = (1 + delta * qb_ss) * B(-1) + G + transfers + UI * (U1 + U2) \
            + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
            + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
            + - qb_ss * B - (tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss) * w * N
        UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
        UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
        return fiscal_resid, UI_extension_cost, UI_rr_cost

    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal_G_fixed_real_rate(B, N, w, v, pi, UI, U1, U2, transfers, phi_G, tau, deficit_T):
        fiscal_resid = (1 + delta * qb_ss) * B(-1) + G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss \
            + transfers + UI * (U1 + U2) + - qb_ss * B - (tau) * w * N
        tax_cost = (tau) * 1.0 * N_ss
        return fiscal_resid, tax_cost

    # BUG-074 fix arm (flag-gated, default = published spending-financing):
    # the tax cut rides the SAME phi_b tax rule as transfers/UI via an
    # additive exogenous shifter — tau_t = tau_ss + dtau_x_t + rule.
    # Symmetric financing across all three experiments.
    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal_taxcut_taufin(B, N, qb, G, w, v, pi, phi_b, UI, U1, U2, deficit_T, dtau_x):
        tau = tau_ss + dtau_x + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
        fiscal_resid = (1 + delta * qb) * B(-1) + G + UI * (U1 + U2) \
            + - qb * B - tau * w * N
        tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
        tau_rule = tau - tau_ss - dtau_x
        return fiscal_resid, tau, tax_cost, tau_rule

    @sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
    def fiscal_taxcut_taufin_fixed_real(B, N, G, w, v, pi, phi_b, UI, U1, U2, deficit_T, dtau_x):
        tau = tau_ss + dtau_x + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
        fiscal_resid = (1 + delta * qb_ss) * B(-1) + G + UI * (U1 + U2) \
            + - qb_ss * B - tau * w * N
        tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
        tau_rule = tau - tau_ss - dtau_x
        return fiscal_resid, tau, tax_cost, tau_rule

    # ---- Steady-state dictionary --------------------------------------
    SteadyState_Dict = SteadyStateDict({
        "asset_mkt": 0.0,
        "goods_mkt": 0.0,
        "arg_fisher_resid": 0.0,
        "lbp_resid": 0.0,
        "fiscal_resid": 0.0,
        "labor_evo_resid": 0.0,
        "taylor_resid": 0.0,
        "nkpc_resid": 0.0,

        "epsilon_p": epsilon_p,
        "U": (1 - N_ss),
        "U1": ss_dstn[1],
        "U2": ss_dstn[2],
        "U3": ss_dstn[3],
        "U4": ss_dstn[4],
        "U5": ss_dstn[5],

        "HC": MC_ss * Z_ss,

        "MC": MC_ss,
        "C": C_ss_sim,
        "r": r_ss,
        "r_ante": r_ss,
        "Y": Y_ss,
        "B": B_ss,
        "G": G_ss,
        "A": A_ss_sim,
        "tau": tau_ss,
        "eta": eta_ss,
        "phi_b": phi_b,
        "phi_w": phi_w,

        "N": N_ss,

        "phi": phi_ss,
        "v": v_ss,
        "ev": 0.0,
        "Z": Z_ss,
        "job_sep": job_sep,
        "w": wage_ss,
        "pi": pi_ss,
        "i": r_ss,
        "qb": qb_ss,

        "varphi": varphi,
        "rho_r": _RHO_R,
        "kappa_p": _KAPPA_P,
        "phi_pi": phi_pi,
        "phi_y": phi_y,

        "chi": chi_ss,
        "theta": theta_ss,
        "UI": UI,
        "transfers": 0.0,
        "UI_extend": 0.0,
        "deficit_T": -1,
        "UI_extension_cost": 0.0,
        "UI_rr": 0.0,
        "debt": qb_ss * B_ss,
        "tax_cost": tau_ss * wage_ss * N_ss,
        "dtau_x": 0.0,
        "tau_rule": 0.0,

        "lag": -1
    })

    # ---- Household Jacobians from the Jacobian stage ------------------
    with open(JACS_OBJ, 'rb') as obj:
        HA_fiscal_JAC = pickle.load(obj)

    # Ingestion hardening (ladder plan §5.6): the obj and this GE pass must
    # agree on the horizon (both read HAFISCAL_HANK_BIGT, but at DIFFERENT
    # times — a stale obj under a changed env would otherwise be sliced
    # silently) and on the FD step (compile_JAC divided by the jacs-stage
    # dx; the UJAC below divides by this file's dx).
    _jshape = np.asarray(HA_fiscal_JAC['C']['transfers']).shape
    if _jshape != (bigT, bigT):
        raise RuntimeError(
            f"HA_Fiscal_Jacs.obj carries J of shape {_jshape} but this GE "
            f"pass runs bigT={bigT} (HAFISCAL_HANK_BIGT mismatch between "
            f"the Jacobian build and the GE pass — rebuild the obj or set "
            f"the env to its horizon)")
    _obj_dx = HA_fiscal_JAC.get('dx')
    if _obj_dx is not None and float(_obj_dx) != dx:
        raise RuntimeError(
            f"HA_Fiscal_Jacs.obj was built with dx={_obj_dx} but ge.py's "
            f"UJAC uses dx={dx} — the two FD steps must be identical")

    # name= on each JacobianDict: sequence_jacobian keys its Js cache by
    # block name, and three anonymous dicts all named 'NestedDict' are a
    # latent cache collision (ladder plan §5.6).
    Jacobian_Dict = JacobianDict({'C': HA_fiscal_JAC['C'],
                                  'A': HA_fiscal_JAC['A']},
                                 name='hh_aggregate')
    CJACs_by_educ = HA_fiscal_JAC['C_by_educ']
    AJACs_by_educ = HA_fiscal_JAC['A_by_educ']

    Jacobian_Dict_by_educ = JacobianDict({
        'C_dropout': CJACs_by_educ['dropout'],
        'C_highschool': CJACs_by_educ['highschool'],
        'C_college': CJACs_by_educ['college'],
        'A_dropout': AJACs_by_educ['dropout'],
        'A_highschool': AJACs_by_educ['highschool'],
        'A_college': AJACs_by_educ['college']},
        name='hh_by_educ')

    UJAC_dict = JacobianDict({
        'N': {'eta': UJAC[0]},
        'U1': {'eta': UJAC[1]},
        'U2': {'eta': UJAC[2]},
        'U3': {'eta': UJAC[3]},
        'U4': {'eta': UJAC[4]},
        'U5': {'eta': UJAC[5]}},
        name='hh_ujac')

    # ---- Splurge overlay (H1) -----------------------------------------
    old_Jacobian_Dict = deepcopy(Jacobian_Dict)
    periods = old_Jacobian_Dict['C']['transfers'].shape[0]

    do_splurge = True
    if do_splurge:
        # R-c ADOPTED (owner ruling 2026-08-09 late eve): the overlay's
        # splurge is single-sourced from the calibration — DEFAULT
        # "calib" = the live interpretation-resolved EstimParameters.
        # Splurge (ESC 0.2703537...), the value the block's beta-hats
        # were estimated jointly with (matched-pair coherence). The
        # historical hardcode 0.3 (Will's 2024 notebook; matches no
        # estimate) survives as the "legacy" escape and in the frozen
        # QE-fidelity monolith. Explicit float still honored.
        splurge = resolve_hank_splurge()  # BUG-100: explicit env wins over QE_FIDELITY
        print(f"[hank-splurge] splurge = {splurge}", flush=True)

        # BUG-111 arms — formulas single-homed in step4/splurge_overlay.py (the SST;
        # extracted 2026-09-01 so the GE stage and the PE-reproduction gate apply
        # identical arithmetic).  `legacy` reproduces the shipped construction byte for
        # byte; `pv` is the broadcasting correction; `cash` is the paper's rule
        # c_sp = varsigma*y — the unique budget-consistent pair (BUG-111 record).
        # Inside `cash`, HAFISCAL_HANK_SPLURGE_RHO selects the return operator:
        # `livprb` = the model constant rho = R*LivPrb (default; removes the estimate
        # arm's one-signed +0.4-0.9% drizzle identically), `estimate` = the shipped
        # DiscFac-column identification, kept as the reproduction reference.
        from . import splurge_overlay as _sov
        from .hh_setup import LIVPRB_SS as _LIVPRB
        _sdiag = _sov.resolve_diag_arm()
        _rho_mode = _sov.resolve_rho_mode()
        if _sdiag != "legacy":
            print(f"[hank-splurge] diag arm = {_sdiag}"
                  + (f" (rho = {_rho_mode})" if _sdiag == "cash" else "")
                  + " (BUG-111)", flush=True)
        _sov.apply_aggregate(Jacobian_Dict, old_Jacobian_Dict, _sdiag, splurge, R,
                             _LIVPRB, periods, rho_mode=_rho_mode)

        # By-educ consistency: the SAME arm as the aggregate (the branch used to
        # hardcode the legacy formula — under a cash aggregate that overstated the
        # education incidence decomposition's impact C by +12.6% transfers/Taylor;
        # exact to ~1e-16 when tied).  Default ON with the R-c adoption; the by-educ
        # outputs feed no live equation (proven latent ≤1.3e-8) — this keeps
        # education decompositions of the aggregate exact.
        if os.environ.get("HAFISCAL_HANK_SPLURGE_BYEDUC", "1").strip().lower() in ("1", "on", "true"):
            _old_by_educ = deepcopy(Jacobian_Dict_by_educ)
            _sov.apply_by_educ(Jacobian_Dict_by_educ, _old_by_educ, _sdiag, splurge, R,
                               _LIVPRB, periods, rho_mode=_rho_mode)
            print("[hank-splurge] by-educ Jacobians splurge-adjusted", flush=True)

    # ---- Models -------------------------------------------------------
    HANK_SAM = create_model(
        [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal, longbonds_price,
         ex_post_longbonds_rate, fiscal_rule, production, matching, taylor,
         Phillips_Curve, marginal_cost, UJAC_dict, hiring_cost, wage_,
         vacancies, unemployment1, fisher_clearing, mkt_clearing],
        name="HARK_HANK")

    HANK_SAM_tax_rate_shock = create_model(
        [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal_G, longbonds_price,
         ex_post_longbonds_rate, fiscal_rule_G, production, matching, taylor,
         Phillips_Curve, marginal_cost, UJAC_dict, hiring_cost, wage_,
         vacancies, unemployment1, fisher_clearing, mkt_clearing],
        name="HARK_HANK")

    HANK_SAM_lagged_taylor_rule = create_model(
        [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal, longbonds_price,
         ex_post_longbonds_rate, fiscal_rule, production, matching,
         taylor_lagged, Phillips_Curve, marginal_cost, UJAC_dict, hiring_cost,
         wage_, vacancies, unemployment1, fisher_clearing, mkt_clearing],
        name="HARK_HANK")

    HANK_SAM_fixed_real_rate = create_model(
        [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal_fixed_real_rate,
         fiscal_rule, production, matching, Phillips_Curve, marginal_cost,
         UJAC_dict, hiring_cost, wage_, vacancies, unemployment1,
         fisher_clearing_fixed_real_rate, mkt_clearing],
        name="HARK_HANK")

    HANK_SAM_tax_cut_fixed_real_rate = create_model(
        [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal_G_fixed_real_rate,
         fiscal_rule_G, production, matching, Phillips_Curve, marginal_cost,
         UJAC_dict, hiring_cost, wage_, vacancies, unemployment1,
         fisher_clearing_fixed_real_rate, mkt_clearing],
        name="HARK_HANK")

    # ---- G11: the GE-suppressed wiring gate ---------------------------
    # HAFISCAL_HANK_G11=1. The owner's "turn AD off" gate, in its achievable form
    # (plans/20260830-1710h_hank-pe-gate-architecture_plan.md).
    #
    # `impulse_linear` does NOT solve for the unknowns, so theta and r_ante stay at their steady
    # state: the aggregate-demand feedback that theta carries is off. The mechanical blocks still
    # propagate, so the household block receives a whole VECTOR of dated inputs (transfers, tau,
    # UI_extend, UI_rr, eta, w), not just the shocked one. The gate is therefore not "C equals the
    # shocked column" -- it is that C equals OUR household Jacobian applied to exactly the inputs
    # the DAG delivers, and that nothing else contributes:
    #
    #     C  ==  sum_input  Jacobian_Dict['C'][input] @ impulse[input]        (machine precision)
    #
    # That is a wiring check with zero tolerance: it proves the Jacobians the fake-news stage
    # emitted are the object the GE actually applies, through the inputs it actually applies them
    # to. It is the class of gate BUG-072 (the zeroth column) failed, and nothing has re-asked it
    # since the block was rebuilt. Runs inside the production `run()` on the production models, so
    # it tests the built object rather than a reconstruction.
    if os.environ.get("HAFISCAL_HANK_G11", "").strip().lower() in ("1", "on", "true"):
        _g11_inputs = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w']
        _g11_shocks = {
            'transfers': {'transfers': np.concatenate(([C_ss * .05], np.zeros(bigT - 1)))},
            'UI_extend': {'UI_extend': np.concatenate((np.full(4, .2), np.zeros(bigT - 4)))},
        }
        _g11 = {}
        for _name, _shk in _g11_shocks.items():
            for _mdl_name, _mdl, _ss in (("taylor", HANK_SAM, SteadyState_Dict),
                                         ("fixed_real", HANK_SAM_fixed_real_rate, SteadyState_Dict)):
                _outs = list(dict.fromkeys(_g11_inputs + ['C', 'A', 'theta', 'r_ante']))
                try:
                    _imp = _mdl.impulse_linear(_ss, _shk, outputs=_outs)
                except Exception as _e:                      # noqa: BLE001 - reported, not swallowed
                    _g11[f"{_name}/{_mdl_name}"] = {"error": repr(_e)}
                    continue
                _rec = {'C': np.zeros(bigT), 'A': np.zeros(bigT)}
                for _o in ('C', 'A'):
                    for _i in _g11_inputs:
                        if _i in Jacobian_Dict[_o] and _i in _imp:
                            _rec[_o] = _rec[_o] + Jacobian_Dict[_o][_i] @ np.asarray(_imp[_i])
                _row = {}
                for _o in ('C', 'A'):
                    _got = np.asarray(_imp[_o])
                    _scale = max(1.0, float(np.max(np.abs(_got))))
                    _row[f"max_abs_dev_{_o}"] = float(np.max(np.abs(_got - _rec[_o])))
                    _row[f"max_rel_dev_{_o}"] = float(np.max(np.abs(_got - _rec[_o])) / _scale)
                # AD really is off: the unknowns must not have moved. `impulse_linear` does not
                # solve for them, so this is structural -- but record it when sj returns them, and
                # record WHICH inputs actually moved, since a channel that is silently dead would
                # otherwise make the reconstruction agree for the wrong reason.
                for _u in ('theta', 'r_ante'):
                    _row[f"unknown_{_u}_max_abs"] = (
                        float(np.max(np.abs(np.asarray(_imp[_u])))) if _u in _imp else -1.0)
                _row["live_inputs"] = sorted(
                    _i for _i in _g11_inputs
                    if _i in _imp and float(np.max(np.abs(np.asarray(_imp[_i])))) > 0.0)
                # NEGATIVE CONTROL: drop each live input in turn from the reconstruction. If the
                # deviation stays 0 the channel contributes nothing and the gate is not testing it;
                # a nonzero value is proof the check can bite on that input.
                _bite = {}
                for _drop in _row["live_inputs"]:
                    _alt = np.zeros(bigT)
                    for _i in _g11_inputs:
                        if _i != _drop and _i in Jacobian_Dict['C'] and _i in _imp:
                            _alt = _alt + Jacobian_Dict['C'][_i] @ np.asarray(_imp[_i])
                    _bite[_drop] = float(np.max(np.abs(np.asarray(_imp['C']) - _alt)))
                _row["drop_one_input_dev_C"] = _bite
                _g11[f"{_name}/{_mdl_name}"] = _row
                print(f"[hank-g11] {_name}/{_mdl_name}: "
                      + "  ".join(f"{k}={v:.3e}" for k, v in _row.items()
                                  if isinstance(v, float))
                      + f"  live={_row['live_inputs']}"
                      + "  drop-one bite="
                      + str({k: f"{v:.3e}" for k, v in _row['drop_one_input_dev_C'].items()}),
                      flush=True)
        _g11_out = os.environ.get("HAFISCAL_HANK_G11_DUMP", "")
        if _g11_out:
            import json as _json
            with open(_g11_out, "w") as _f:
                _json.dump(_g11, _f, indent=1)
            print(f"[hank-g11] dump -> {_g11_out}", flush=True)

    # ---- Policy experiments -------------------------------------------
    def NPV(irf, length):
        # BUG-109: the cost denominators used to hardcode 300 while the
        # numerators followed bigT.  Below bigT=300 that was an IndexError;
        # above it, it silently discounted over a different horizon than the
        # numerator.  Assert rather than index off the end, so a horizon
        # mismatch is reported as one instead of crashing obscurely.
        if len(irf) < length:
            raise ValueError(
                f"NPV asked for {length} periods from an IRF of length "
                f"{len(irf)}; numerator/denominator horizons disagree "
                f"(see BUG-109)")
        NPV = 0
        for i in range(length):
            NPV += irf[i] / R ** i
        return NPV

    unknowns = ['theta', 'r_ante']
    targets = ['asset_mkt', 'fisher_resid']

    # UI extension: 2Q extension of benefits (states U3/U4 receive 0.2
    # replacement-rate points, denominated like the UI_extend Jacobian)
    dUI_extension = np.zeros(bigT)
    dUI_extension[:4] = .2
    shocks_UI_extension = {'UI_extend': dUI_extension}

    SteadyState_Dict_UI_extend = deepcopy(SteadyState_Dict)
    SteadyState_Dict_UI_extend['phi_b'] = _PHI_B   # fiscal adjustment parameter
    SteadyState_Dict_UI_extend['phi_w'] = 0.837   # wage rigidity parameter
    SteadyState_Dict_UI_extend['rho_r'] = _RHO_R
    SteadyState_Dict_UI_extend['phi_y'] = 0.0
    SteadyState_Dict_UI_extend['phi_pi'] = _PHI_PI_TAYLOR
    SteadyState_Dict_UI_extend['deficit_T'] = -1

    SteadyState_Dict_UI_extend_fixed_nominal_rate = deepcopy(SteadyState_Dict_UI_extend)
    SteadyState_Dict_UI_extend_fixed_nominal_rate['phi_pi'] = _PHI_PI_FIXED

    irfs_UI_extend = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_extend, unknowns, targets, shocks_UI_extension)
    irfs_UI_extend_fixed_nominal_rate = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_extend_fixed_nominal_rate, unknowns, targets, shocks_UI_extension)

    SteadyState_Dict_UI_extend_lagged_nominal_rate = deepcopy(SteadyState_Dict_UI_extend)
    monetary_policy_lag = 2
    SteadyState_Dict_UI_extend_lagged_nominal_rate['lag'] = monetary_policy_lag
    irfs_UI_extend_lagged_nominal_rate = HANK_SAM_lagged_taylor_rule.solve_impulse_linear(
        SteadyState_Dict_UI_extend_lagged_nominal_rate, unknowns, targets, shocks_UI_extension)

    unknowns_fixed_real_rate = ['theta']
    targets_fixed_real_rate = ['asset_mkt']

    irfs_UI_extension_fixed_real_rate = HANK_SAM_fixed_real_rate.solve_impulse_linear(
        SteadyState_Dict_UI_extend, unknowns_fixed_real_rate, targets_fixed_real_rate,
        shocks_UI_extension)

    print('multiplier out of 2Q UI extension (active taylor rule)',
          NPV(irfs_UI_extend['Y'], bigT) / NPV(irfs_UI_extend['UI_extension_cost'], bigT))
    print('multiplier out of 2Q UI extension (fixed nominal rate)',
          NPV(irfs_UI_extend_fixed_nominal_rate['Y'], bigT) / NPV(irfs_UI_extend_fixed_nominal_rate['UI_extension_cost'], bigT))
    print('multiplier out of 2Q UI extension (fixed real rate)',
          NPV(irfs_UI_extension_fixed_real_rate['Y'], bigT) / NPV(irfs_UI_extension_fixed_real_rate['UI_extension_cost'], bigT))

    # Transfers (stimulus check)
    dtransfers = np.zeros(bigT)
    dtransfers[:1] = C_ss * .05  # approximate aggregate stimulus check outlay
    shocks_transfers = {'transfers': dtransfers}

    SteadyState_Dict_transfer = deepcopy(SteadyState_Dict)
    SteadyState_Dict_transfer['phi_b'] = _PHI_B
    SteadyState_Dict_transfer['phi_w'] = 0.837
    SteadyState_Dict_transfer['rho_r'] = _RHO_R
    SteadyState_Dict_transfer['phi_y'] = 0.0
    SteadyState_Dict_transfer['phi_pi'] = _PHI_PI_TAYLOR
    SteadyState_Dict_transfer['deficit_T'] = -1

    SteadyState_Dict_UI_transfer_fixed_nominal_rate = deepcopy(SteadyState_Dict_transfer)
    SteadyState_Dict_UI_transfer_fixed_nominal_rate['phi_pi'] = _PHI_PI_FIXED

    irfs_transfer = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_transfer, unknowns, targets, shocks_transfers)
    irfs_transfer_fixed_nominal_rate = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_transfer_fixed_nominal_rate, unknowns, targets, shocks_transfers)

    # ---- S3 determinacy diagnostic (HAFISCAL_HANK_DETERMINACY=1) --------
    # WHY the fixed-nominal regime misbehaves. The GE stage solves H_U dU = -H_Z dZ
    # for the unknowns; if the model is INDETERMINATE the underlying operator has a
    # non-trivial null space, so the truncated H_U is near-singular and the terminal
    # condition at T silently picks one member of the continuum. Dump the singular
    # values of H_U at a range of phi_pi to show that directly: the Taylor principle
    # (phi_pi > 1, active money) should give a well-conditioned H_U, and phi_pi < 1
    # with passive fiscal (phi_b > 0) should not.
    _det = os.environ.get("HAFISCAL_HANK_DETERMINACY", "").strip().lower()
    if _det and _det not in ("0", "off", "false"):
        import json as _json
        # "1"/"on"/"true" = the standard profile; a comma list of floats
        # (e.g. "1.6,1.7,1.8,1.9") sweeps those phi_pi values instead —
        # added 2026-09-02 for the F5 bisection (the sigma_min cliff
        # between 1.5 and 2.0).
        if _det in ("1", "on", "true"):
            _pps = (0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.01, 1.1, 1.25, 1.5, 2.0)
        else:
            _pps = tuple(float(x) for x in _det.split(","))
        _rows = []
        for _pp in _pps:
            _ss = deepcopy(SteadyState_Dict_transfer)
            _ss['phi_pi'] = _pp
            try:
                _HU = HANK_SAM.jacobian(_ss, unknowns, outputs=targets, T=bigT)
                _M = _HU[targets, unknowns].pack(bigT) if hasattr(_HU, 'pack') else np.asarray(_HU)
                _U_sv, _sv, _Vt = np.linalg.svd(np.asarray(_M))
                # the near-null right singular vector: which unknown-path
                # direction degenerates (F5 diagnosis; theta block first,
                # r_ante second, in the pack order of `unknowns`)
                _vmin = _Vt[-1]
                _half = _vmin.size // 2
                _rows.append({"phi_pi": _pp, "smin": float(_sv[-1]), "smax": float(_sv[0]),
                              "cond": float(_sv[0]/_sv[-1]) if _sv[-1] > 0 else float('inf'),
                              "n_below_1e-8": int((_sv < 1e-8*_sv[0]).sum()),
                              "vmin_norm_block1": float(np.linalg.norm(_vmin[:_half])),
                              "vmin_norm_block2": float(np.linalg.norm(_vmin[_half:])),
                              "vmin_block1_argmax": int(np.argmax(np.abs(_vmin[:_half]))),
                              "vmin_block2_argmax": int(np.argmax(np.abs(_vmin[_half:])))})
                print(f"[hank-determinacy] phi_pi={_pp:<5} smin={_sv[-1]:.4e} "
                      f"smax={_sv[0]:.4e} cond={_sv[0]/_sv[-1]:.4e}", flush=True)
            except Exception as _e:                    # noqa: BLE001 - reported, not swallowed
                print(f"[hank-determinacy] phi_pi={_pp}: {_e!r}", flush=True)
                _rows.append({"phi_pi": _pp, "error": repr(_e)})
        _dout = os.environ.get("HAFISCAL_HANK_DETERMINACY_DUMP", "")
        if _dout:
            with open(_dout, "w") as _f:
                _json.dump(_rows, _f, indent=1)

    print('multiplier out of transfers',
          NPV(irfs_transfer['Y'], bigT) / NPV(irfs_transfer['transfers'], bigT))
    print('multiplier out of transfers (fixed nominal rate)',
          NPV(irfs_transfer_fixed_nominal_rate['Y'], bigT) / NPV(irfs_transfer_fixed_nominal_rate['transfers'], bigT))

    SteadyState_Dict_transfers_lagged_nominal_rate = deepcopy(SteadyState_Dict_transfer)
    monetary_policy_lag = 2
    SteadyState_Dict_transfers_lagged_nominal_rate['lag'] = monetary_policy_lag
    irfs_transfers_lagged_nominal_rate = HANK_SAM_lagged_taylor_rule.solve_impulse_linear(
        SteadyState_Dict_transfers_lagged_nominal_rate, unknowns, targets, shocks_transfers)

    irfs_transfer_fixed_real_rate = HANK_SAM_fixed_real_rate.solve_impulse_linear(
        SteadyState_Dict_transfer, unknowns_fixed_real_rate, targets_fixed_real_rate,
        shocks_transfers)

    print('multiplier out of transfers (active taylor rule)',
          NPV(irfs_transfer['Y'], bigT) / NPV(irfs_transfer['transfers'], bigT))
    print('multiplier out of transfers (fixed nominal rate)',
          NPV(irfs_transfer_fixed_nominal_rate['Y'], bigT) / NPV(irfs_transfer_fixed_nominal_rate['transfers'], bigT))
    print('multiplier out of transfers (fixed real rate)',
          NPV(irfs_transfer_fixed_real_rate['Y'], bigT) / NPV(irfs_transfer_fixed_real_rate['transfers'], bigT))

    # Tax cut. HAFISCAL_HANK_TAXCUT_FINANCING selects the financing
    # (terminology per the owner, 2026-08-09 — name the INCIDENCE, not
    # the instrument):
    #   "household" (alias "tax"; DEFAULT — BUG-074 ADOPTED with the
    #     R-b ruling 2026-08-09): the cut rides the SAME phi_b tax rule
    #     as transfers/UI via the additive shifter dtau_x; repayment
    #     falls on households — symmetric financing across all three
    #     experiments.
    #   "incidence_free" (aliases "spending"/"G") — the published
    #     construction: the phi_G rule stabilizes the debt path by
    #     adjusting G, which enters no agent's budget or utility under
    #     the adopted closure — financed in accounting, free in
    #     incidence. (Distinct from truly UNFINANCED phi=0: the
    #     bond-path stabilization itself does real work — p10b.)
    # Materiality: fixed-real h=20 1.429->1.378 (-3.6%), taylor
    # 1.732->1.531 (-12%); rankings invariant (p10 matrix, 2026-08-09).
    # QE-fidelity reproduces the published construction via the frozen
    # monolith.
    dtau = np.zeros(bigT)
    dtau[:8] = -.02

    _taxfin = os.environ.get("HAFISCAL_HANK_TAXCUT_FINANCING", "household").strip().lower()

    SteadyState_Dict_tax_shock = deepcopy(SteadyState_Dict)
    SteadyState_Dict_tax_shock['phi_G'] = -0.015  # fiscal adjustment parameter
    SteadyState_Dict_tax_shock['phi_b'] = _PHI_B   # used by the taufin arm
    SteadyState_Dict_tax_shock['phi_w'] = 0.837
    SteadyState_Dict_tax_shock['rho_r'] = _RHO_R
    SteadyState_Dict_tax_shock['phi_y'] = 0.0
    SteadyState_Dict_tax_shock['phi_pi'] = _PHI_PI_TAYLOR
    SteadyState_Dict_tax_shock['deficit_T'] = -1

    SteadyState_Dict_tax_shock_fixed_rate = deepcopy(SteadyState_Dict_tax_shock)
    SteadyState_Dict_tax_shock_fixed_rate['phi_pi'] = _PHI_PI_FIXED

    if _taxfin in ("tax", "household"):
        print("[hank-taxfin] tax-cut financing = HOUSEHOLD (symmetric phi_b "
              "rule; BUG-074 fix arm)", flush=True)
        shocks_tau = {'dtau_x': dtau}
        HANK_SAM_taxcut_taufin = create_model(
            [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal_taxcut_taufin,
             longbonds_price, ex_post_longbonds_rate, production, matching,
             taylor, Phillips_Curve, marginal_cost, UJAC_dict, hiring_cost,
             wage_, vacancies, unemployment1, fisher_clearing, mkt_clearing],
            name="HARK_HANK")
        HANK_SAM_taxcut_taufin_fr = create_model(
            [Jacobian_Dict, Jacobian_Dict_by_educ, fiscal_taxcut_taufin_fixed_real,
             production, matching, Phillips_Curve, marginal_cost, UJAC_dict,
             hiring_cost, wage_, vacancies, unemployment1,
             fisher_clearing_fixed_real_rate, mkt_clearing],
            name="HARK_HANK")
        irfs_tau = HANK_SAM_taxcut_taufin.solve_impulse_linear(
            SteadyState_Dict_tax_shock, unknowns, targets, shocks_tau)
        irfs_tau_fixed_nominal_rate = HANK_SAM_taxcut_taufin.solve_impulse_linear(
            SteadyState_Dict_tax_shock_fixed_rate, unknowns, targets, shocks_tau)
        irfs_tau_fixed_real_rate = HANK_SAM_taxcut_taufin_fr.solve_impulse_linear(
            SteadyState_Dict_tax_shock, unknowns_fixed_real_rate,
            targets_fixed_real_rate, shocks_tau)
    else:
        shocks_tau = {'tau': dtau}
        irfs_tau = HANK_SAM_tax_rate_shock.solve_impulse_linear(
            SteadyState_Dict_tax_shock, unknowns, targets, shocks_tau)
        irfs_tau_fixed_nominal_rate = HANK_SAM_tax_rate_shock.solve_impulse_linear(
            SteadyState_Dict_tax_shock_fixed_rate, unknowns, targets, shocks_tau)
        irfs_tau_fixed_real_rate = HANK_SAM_tax_cut_fixed_real_rate.solve_impulse_linear(
            SteadyState_Dict_tax_shock, unknowns_fixed_real_rate,
            targets_fixed_real_rate, shocks_tau)

    print('multiplier out of tax cut',
          NPV(irfs_tau['Y'], bigT) / NPV(irfs_tau['tax_cost'], bigT))
    print('multiplier out of tax cut (fixed real rate)',
          NPV(irfs_tau_fixed_real_rate['Y'], bigT) / NPV(irfs_tau_fixed_real_rate['tax_cost'], bigT))
    print('multiplier out of tax cut (fixed nominal rate)',
          NPV(irfs_tau_fixed_nominal_rate['Y'], bigT) / NPV(irfs_tau_fixed_nominal_rate['tax_cost'], bigT))

    # ---- Multipliers across the horizon -------------------------------
    horizon_length = 20

    multipliers_transfers = np.zeros(horizon_length)
    multipliers_UI_extensions = np.zeros(horizon_length)
    multipliers_tax_cut = np.zeros(horizon_length)

    for i in range(horizon_length):
        multipliers_transfers[i] = NPV(irfs_transfer_fixed_real_rate['C'], i + 1) / NPV(irfs_transfer_fixed_real_rate['transfers'], bigT)
        multipliers_UI_extensions[i] = NPV(irfs_UI_extension_fixed_real_rate['C'], i + 1) / NPV(irfs_UI_extension_fixed_real_rate['UI_extension_cost'], bigT)
        multipliers_tax_cut[i] = -NPV(irfs_tau_fixed_real_rate['C'], i + 1) / NPV(irfs_tau_fixed_real_rate['tax_cost'], bigT)

    figures.render_across_horizon(multipliers_transfers, multipliers_UI_extensions,
                                  multipliers_tax_cut, horizon_length)

    # Second pass: all three regimes (overwrites multipliers_transfers /
    # multipliers_tax_cut with the ACTIVE-Taylor series — the historical
    # choreography behind the H2 mixed-regime pickle).
    multipliers_transfers_fixed_nominal_rate = np.zeros(horizon_length)
    multipliers_UI_extensions_fixed_nominal_rate = np.zeros(horizon_length)
    multipliers_tax_cut_fixed_nominal_rate = np.zeros(horizon_length)

    multipliers_transfers = np.zeros(horizon_length)
    multipliers_UI_extend = np.zeros(horizon_length)
    multipliers_tax_cut = np.zeros(horizon_length)

    multipliers_transfers_fixed_real_rate = np.zeros(horizon_length)
    multipliers_UI_extensions_fixed_real_rate = np.zeros(horizon_length)
    multipliers_tax_cut_fixed_real_rate = np.zeros(horizon_length)

    for i in range(horizon_length):
        multipliers_transfers_fixed_nominal_rate[i] = NPV(irfs_transfer_fixed_nominal_rate['C'], i + 1) / NPV(irfs_transfer_fixed_nominal_rate['transfers'], bigT)
        multipliers_UI_extensions_fixed_nominal_rate[i] = NPV(irfs_UI_extend_fixed_nominal_rate['C'], i + 1) / NPV(irfs_UI_extend_fixed_nominal_rate['UI_extension_cost'], bigT)
        multipliers_tax_cut_fixed_nominal_rate[i] = -NPV(irfs_tau_fixed_nominal_rate['C'], i + 1) / NPV(irfs_tau_fixed_nominal_rate['tax_cost'], bigT)

        multipliers_transfers[i] = NPV(irfs_transfer['C'], i + 1) / NPV(irfs_transfer['transfers'], bigT)
        multipliers_UI_extend[i] = NPV(irfs_UI_extend['C'], i + 1) / NPV(irfs_UI_extend['UI_extension_cost'], bigT)
        multipliers_tax_cut[i] = -NPV(irfs_tau['C'], i + 1) / NPV(irfs_tau['tax_cost'], bigT)

        multipliers_transfers_fixed_real_rate[i] = NPV(irfs_transfer_fixed_real_rate['C'], i + 1) / NPV(irfs_transfer_fixed_real_rate['transfers'], bigT)
        multipliers_UI_extensions_fixed_real_rate[i] = NPV(irfs_UI_extension_fixed_real_rate['C'], i + 1) / NPV(irfs_UI_extension_fixed_real_rate['UI_extension_cost'], bigT)
        multipliers_tax_cut_fixed_real_rate[i] = -NPV(irfs_tau_fixed_real_rate['C'], i + 1) / NPV(irfs_tau_fixed_real_rate['tax_cost'], bigT)

    # R-b RULED 2026-08-09 ("I hereby adopt your recommendation"): the
    # pickle regime DEFAULT is now "fixed_real" — all three policies
    # under the fixed-real-rate rule, which is what the published
    # caption and body text state ("under a fixed real rate rule"),
    # the SOE-exact arm (closure appendix X.4), and the level-invariant
    # one. The historical H2 mix (transfers/tax active-Taylor, UI
    # fixed-real — an accidental naming slip) is the "mixed" escape;
    # "consistent" = all active-Taylor (the earlier fix arm).
    # QE-fidelity reproduces the published mix via the frozen monolith.
    # FEATURED-REGIME ruling (owner 2026-08-10, "mainly — Taylor
    # featured, fixed-real as the robustness companion"): the pickle
    # defaults to the all-active-Taylor series ("consistent"; alias
    # "taylor"). The fixed-real arm remains fully emitted through the
    # MULT_DUMP 3x3 and is the reported level-invariant companion (the
    # Taylor arm's interest-income channel scales with the
    # non-identified asset level — RECONCILED-003 — so its LEVELS carry
    # the measured sensitivity band; incidence-inversion trace in the
    # co-author note sec. 8).
    # Regime-pure snapshots for the MULT_DUMP below. The H2 selection
    # overwrites the working names (the fixed_real escape rebinds
    # multipliers_transfers / multipliers_tax_cut), so before 2026-09-01
    # the dump's "taylor" entries under HAFISCAL_HANK_MULT_REGIME=
    # fixed_real actually carried the fixed-real series (the regime-label
    # aliasing bug, ladder plan §5.8). Snapshot first; the dump reads these.
    _pure_taylor = {
        "transfers": multipliers_transfers.copy(),
        "UI_extensions": multipliers_UI_extend.copy(),
        "tax_cut": multipliers_tax_cut.copy(),
    }

    _regime = os.environ.get("HAFISCAL_HANK_MULT_REGIME", "consistent").strip().lower()
    if _regime in ("consistent", "taylor"):
        multipliers_UI_extensions = multipliers_UI_extend.copy()
        print("[hank-h2] multiplier pickle regime = consistent (all three active "
              "Taylor — FEATURED per the 2026-08-10 ruling; fixed-real = the "
              "reported robustness companion)", flush=True)
    elif _regime == "fixed_real":
        multipliers_transfers = multipliers_transfers_fixed_real_rate.copy()
        multipliers_UI_extensions = multipliers_UI_extensions_fixed_real_rate.copy()
        multipliers_tax_cut = multipliers_tax_cut_fixed_real_rate.copy()
        print("[hank-h2] multiplier pickle regime = fixed_real (all three; "
              "R-b ruling 2026-08-09)", flush=True)

    # Diagnostic (R-b deliberation): dump ALL nine regime-pure horizon
    # series (3 policies x {taylor, fixed_nominal, fixed_real}) — the
    # stage computes them every run but the production pickle stores
    # only the 3-series H2 selection. Default off; additive.
    _dump = os.environ.get("HAFISCAL_HANK_MULT_DUMP", "").strip()
    if _dump:
        with open(_dump, "wb") as _f:
            pickle.dump({
                "transfers": {
                    "taylor": _pure_taylor["transfers"].copy(),
                    "fixed_nominal": multipliers_transfers_fixed_nominal_rate.copy(),
                    "fixed_real": multipliers_transfers_fixed_real_rate.copy()},
                "UI_extensions": {
                    "taylor": _pure_taylor["UI_extensions"].copy(),
                    "fixed_nominal": multipliers_UI_extensions_fixed_nominal_rate.copy(),
                    "fixed_real": multipliers_UI_extensions_fixed_real_rate.copy()},
                "tax_cut": {
                    "taylor": _pure_taylor["tax_cut"].copy(),
                    "fixed_nominal": multipliers_tax_cut_fixed_nominal_rate.copy(),
                    "fixed_real": multipliers_tax_cut_fixed_real_rate.copy()},
                # raw IRFs incl. the by-education consumption paths
                # (computed by every model, consumed by nothing in
                # production) + the cost series, for incidence tables
                "irfs": {
                    pol: {reg: {k: np.asarray(irf[k]).copy()
                                for k in ("C", "C_dropout", "C_highschool",
                                          "C_college", cost_key,
                                          # equilibrium instrument paths
                                          # (for welfare-Jacobian assembly)
                                          "tau", "w", "eta", "transfers",
                                          "UI_extend", "UI_rr", "r",
                                          # accounting paths (ladder §5.8:
                                          # makes G-WAL/G-BB/G-PHIB free on
                                          # production runs)
                                          "goods_mkt", "A", "B", "theta",
                                          "N", "pi", "r_ante", "qb", "Y",
                                          "U", "U1", "U2", "U3", "U4", "U5",
                                          "MC", "i", "ev")
                                if k in irf}
                          for reg, irf in regs.items()}
                    for pol, cost_key, regs in (
                        ("transfers", "transfers",
                         {"taylor": irfs_transfer,
                          "fixed_nominal": irfs_transfer_fixed_nominal_rate,
                          "fixed_real": irfs_transfer_fixed_real_rate}),
                        ("UI_extensions", "UI_extension_cost",
                         {"taylor": irfs_UI_extend,
                          "fixed_nominal": irfs_UI_extend_fixed_nominal_rate,
                          "fixed_real": irfs_UI_extension_fixed_real_rate}),
                        ("tax_cut", "tax_cost",
                         {"taylor": irfs_tau,
                          "fixed_nominal": irfs_tau_fixed_nominal_rate,
                          "fixed_real": irfs_tau_fixed_real_rate}),
                    )},
            }, _f)
        print(f"[hank-mult-dump] 3x3 regime-pure series + by-educ irfs -> {_dump}", flush=True)

    # R-h (owner ruling 2026-08-10): dump the resolved steady-state
    # calibration so HA_Fiscal_calibration.json has a real producer again
    # (writer: step4/write_calibration_json.py). Additive, default off —
    # mirrors the MULT_DUMP pattern above. This is the SINGLE SOURCE for
    # the json: every value here is the live one this run actually used.
    _ss_dump = os.environ.get("HAFISCAL_HANK_SS_DUMP", "").strip()
    if _ss_dump:
        with open(_ss_dump, "wb") as _f:
            pickle.dump({
                "labor_market": {
                    "job_find": float(job_find),
                    # EU_prob = separation x (1 - within-quarter refinding):
                    # the flow probability employed -> measured-unemployed
                    "EU_prob": float(job_sep * (1 - job_find)),
                    "job_sep": float(job_sep),
                    "seps_by_educ": [float(s) for s in _uc["seps"]],
                    "N_ss": float(N_ss), "U_ss": float(U_ss),
                    "ss_dstn": [float(x) for x in ss_dstn],
                    "ss_dstn_by_educ": [[float(x) for x in v]
                                        for v in ss_dstn_by_educ]},
                "matching": {"alpha": float(alpha), "phi_ss": float(phi_ss),
                             "v_ss": float(v_ss), "theta_ss": float(theta_ss),
                             "chi_ss": float(chi_ss), "eta_ss": float(eta_ss)},
                "household": {"R": float(R), "r_ss": float(r_ss),
                              "C_ss": float(C_ss), "A_ss": float(A_ss),
                              "ss_source": _ss_src},
                "bonds": {"delta": float(delta), "qb_ss": float(qb_ss),
                          "B_ss": float(B_ss)},
                "wages_taxes": {"wage_ss": float(wage_ss),
                                "tau_ss": float(tau_ss),
                                "tau_mode": _tau_mode,
                                "inc_ui_exhaust": float(inc_ui_exhaust),
                                "UI": float(UI),
                                "ui_rr_booked": float(_ui_rr_booked)},
                "government": {"G_ss": float(G_ss), "Y_priv": float(Y_priv)},
                "firms": {"kappa": float(kappa), "HC_ss": float(HC_ss),
                          "epsilon_p": float(epsilon_p),
                          "MC_ss": float(MC_ss), "Z_ss": float(Z_ss),
                          "Y_ss": float(Y_ss)},
                "inflation": {"pi_ss": float(pi_ss), "varphi": float(varphi),
                              "kappa_p_ss": float(kappa_p_ss)},
                "policy_defaults": {
                    "phi_pi": float(phi_pi), "phi_y": float(phi_y),
                    "rho_r": float(_RHO_R),
                    # experiment-layer overrides (applied per experiment
                    # via the SteadyState dicts, NOT model-block values)
                    "phi_b": float(SteadyState_Dict_transfer['phi_b']),
                    "phi_w": float(phi_w),
                    "real_wage_rigidity":
                        float(SteadyState_Dict_transfer['phi_w'])},
                "fiscal_experiments": {
                    "UI_extension_length": int(np.count_nonzero(dUI_extension)),
                    "stimulus_check_length": int(np.count_nonzero(dtransfers)),
                    "tax_cut_length": int(np.count_nonzero(dtau))},
                "computation": {"bigT": int(bigT)},
            }, _f)
        print(f"[hank-ss-dump] resolved SS calibration -> {_ss_dump}",
              flush=True)

    # ---- Figures ------------------------------------------------------
    # Which monetary arms the FIGURES draw (the solves and the multiplier pickle above are
    # unaffected). HAFISCAL_HANK_FIGURE_ARMS: `taylor,fixed_real` (DEFAULT -- owner ruling
    # 2026-09-05: the constant-nominal-rate peg is dropped from the revision's figures; the
    # regime is nearly indeterminate because fiscal policy is nearly passive too, and its
    # multiplier has a pole in a single Jacobian entry -- the Taylor rule with 0.7 persistence
    # is shown instead) | `all` (the published three-arm layout; the default under
    # HAFISCAL_QE_FIDELITY=1). An explicit value wins over the QE_FIDELITY default, the
    # convention everywhere else in the pipeline (BUG-100).
    _arms_raw = os.environ.get("HAFISCAL_HANK_FIGURE_ARMS", "").strip().lower()
    if not _arms_raw:
        _arms_raw = "all" if os.environ.get("HAFISCAL_QE_FIDELITY", "").strip().lower() in ("1", "on", "true") else "taylor,fixed_real"
    _draw_peg = _arms_raw == "all" or "fixed_nominal" in _arms_raw
    print(f"[hank-figures] HAFISCAL_HANK_FIGURE_ARMS={_arms_raw} -> fixed-nominal (peg) arm "
          f"{'drawn' if _draw_peg else 'OMITTED (owner ruling 2026-09-05: nearly indeterminate)'}", flush=True)
    _peg = (lambda x: x) if _draw_peg else (lambda x: None)

    figures.plot_consumption_irfs_three_experiments(
        irfs_UI_extend, _peg(irfs_UI_extend_fixed_nominal_rate), irfs_UI_extension_fixed_real_rate,
        irfs_transfer, _peg(irfs_transfer_fixed_nominal_rate), irfs_transfer_fixed_real_rate,
        irfs_tau, _peg(irfs_tau_fixed_nominal_rate), irfs_tau_fixed_real_rate, C_ss)

    # OWNER RULING 2026-09-05: the shared y-axis is fixed by the EXPERIMENT THAT
    # GENERATES THE HIGHEST VALUE, plus 5 percent -- taken over every arm actually
    # drawn, in all three policy panels, not just the tax cut's.  The three panels
    # MUST share it: the UI extension's near-flat line low in its panel is the point
    # of the figure (UI outlays are small, so the response is small), and giving that
    # panel its own scale would destroy the comparison the figure exists to make.
    # (Before this it was computed from the tax-cut panel alone, which happened to be
    # the tallest in both the published and the current model, so the value is
    # unchanged -- but the rule now says what it means.)
    _drawn = [
        arms for arms in (
            [irfs_transfer, irfs_transfer_fixed_real_rate] + ([irfs_transfer_fixed_nominal_rate] if _draw_peg else []),
            [irfs_UI_extend, irfs_UI_extension_fixed_real_rate] + ([irfs_UI_extend_fixed_nominal_rate] if _draw_peg else []),
            [irfs_tau, irfs_tau_fixed_real_rate] + ([irfs_tau_fixed_nominal_rate] if _draw_peg else []),
        )
    ]
    y_max = max(max(100 * irf['C'][:12] / C_ss) for arms in _drawn for irf in arms) * 1.05
    print(f"[hank-figures] IRF y-axis = 1.05 x the highest drawn experiment = {y_max:.4f}"
          f" (peg {'drawn' if _draw_peg else 'dropped'})", flush=True)
    figures.plot_consumption_irf(irfs_transfer, _peg(irfs_transfer_fixed_nominal_rate),
                                 irfs_transfer_fixed_real_rate, C_ss, y_max,
                                 "HANK_transfer_IRF", legend=True)
    figures.plot_consumption_irf(irfs_UI_extend, _peg(irfs_UI_extend_fixed_nominal_rate),
                                 irfs_UI_extension_fixed_real_rate, C_ss, y_max,
                                 "HANK_UI_IRF")
    figures.plot_consumption_irf(irfs_tau, _peg(irfs_tau_fixed_nominal_rate),
                                 irfs_tau_fixed_real_rate, C_ss, y_max,
                                 "HANK_tax_IRF")

    # Same rule for the cumulative-multiplier panels (owner 2026-09-05): the highest
    # drawn experiment, plus 5 percent.  It replaces a hardcoded 1.9, which was that
    # value computed once when the peg was still drawn (the peg's UI multiplier, 1.799,
    # x 1.05 = 1.889).  With the peg dropped the rule gives a smaller axis; under the
    # published-axes lock (HAFISCAL_FIG_AXES_LOCK, default on) the shipped figures keep
    # the published limits either way, so this governs only an unlocked build.
    _drawn_m = [
        [multipliers_transfers, multipliers_transfers_fixed_real_rate] + ([multipliers_transfers_fixed_nominal_rate] if _draw_peg else []),
        [multipliers_UI_extensions, multipliers_UI_extensions_fixed_real_rate] + ([multipliers_UI_extensions_fixed_nominal_rate] if _draw_peg else []),
        [multipliers_tax_cut, multipliers_tax_cut_fixed_real_rate] + ([multipliers_tax_cut_fixed_nominal_rate] if _draw_peg else []),
    ]
    y_max = max(max(np.asarray(m)[:12]) for arms in _drawn_m for m in arms) * 1.05
    print(f"[hank-figures] multiplier y-axis = 1.05 x the highest drawn experiment = {y_max:.4f}", flush=True)
    figures.plot_consumption_multipliers(
        multipliers_transfers, _peg(multipliers_transfers_fixed_nominal_rate),
        multipliers_transfers_fixed_real_rate, y_max, "HANK_transfer_multiplier")
    figures.plot_consumption_multipliers(
        multipliers_UI_extend, _peg(multipliers_UI_extensions_fixed_nominal_rate),
        multipliers_UI_extensions_fixed_real_rate, y_max, "HANK_UI_multiplier")
    figures.plot_consumption_multipliers(
        multipliers_tax_cut, _peg(multipliers_tax_cut_fixed_nominal_rate),
        multipliers_tax_cut_fixed_real_rate, y_max, "HANK_tax_multiplier")

    # ---- Emit the multiplier pickle -----------------------------------
    Obj = {'transfers': multipliers_transfers,
           'UI_extensions': multipliers_UI_extensions,
           'tax_cut': multipliers_tax_cut}

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUTPUT_PICKLE, 'wb') as fileObj:
        pickle.dump(Obj, fileObj)
    print(f"[step4-ge] wrote {OUTPUT_PICKLE}", flush=True)

    # ---- Provenance sidecar (schema v2; best-effort, never aborts) ----
    try:
        import provenance as _prov
        import sys as _prov_sys
        _prov.emit([OUTPUT_PICKLE], command=" ".join(_prov_sys.argv),
                   argv=_prov_sys.argv,
                   label="step4-hank-sam-ge-experiments", register=True)
    except Exception as _prov_e:
        print(f"[provenance] sidecar emit skipped (non-fatal): {_prov_e}")

    return Obj
