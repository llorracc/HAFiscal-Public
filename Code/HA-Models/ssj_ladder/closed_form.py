"""Package-free reconstruction of the fixed-real GE (the C2 gate's substance).

Adapted from the adversarial pass's independent reproduction (wf2/R3
recon_ikc.py, 2026-09-01): numpy + pickle only — no sequence_jacobian, no
step4 import. Inputs: the jacs obj, the chains dict (from
``hh_setup.unemployment_chains()``, pickled by a separate child), the splurge
value, and the overlay arm. Recomputes ergodic distributions (direct linear
solve — no ARPACK randomness), the published F-5 UJAC loop, every calibration
scalar from ge.py's formulas, the splurge overlay (production: ``cash`` with
rho = R*LivPrb), the fixed-real H_U, and the three experiments' multipliers.

The audit measured this reconstruction against the packed GE at 9.0e-17 (H_U,
same-UJAC tier) and <=1 ulp (multipliers, within-run). Run cross-process
against a GE dump, the ARPACK-start jitter bounds agreement at the ~1e-11
class — G-IKC gates at 1e-6 and records the achieved gap.

Also provides the G-ETA arithmetic (chain-implied dY for the eta column vs
the budget-implied dY) and the G-UJAC spot identity
dD(t,s) = Pi^(t-s-1) (Pi_eta - Pi) D_ss / dx.
"""
import pickle

import numpy as np

# R * LivPrb at the production SS — a LITERAL on purpose. This module is the package-free
# reconstruction (numpy + pickle only: no step4, no EstimParameters), so it must not resolve
# its constants through the code it checks. It is bound to the single source instead:
# ssj_ladder/test_gate_constants_parity.py asserts this equals budget_suite.RHO_LIVPRB,
# which is resolved from EstimParameters (Rfree_base * LivPrb_base). If the calibration
# moves, update this literal to the new value. Q9, dual-path sweep 2026-09-02 §4 /
# Phase-2 brief 2026-09-03.
RHO_LIVPRB = 1.01 * 0.99375
DX = 0.0001
R = 1.01


def ergodic(M_cs):
    n = M_cs.shape[0]
    A = M_cs - np.eye(n)
    A[-1, :] = 1.0
    b = np.zeros(n)
    b[-1] = 1.0
    return np.linalg.solve(A, b)


def perturbed_chain(base_rs, dx=DX):
    """create_matrix_U(dx) semantics: the 6-state chain with jf+dx."""
    jf = float(base_rs[1, 0])
    sep = float(base_rs[0, 1]) / (1.0 - jf)
    j = jf + dx
    return np.array(
        [[1 - sep * (1 - j), j, j, j, j, j],
         [sep * (1 - j), 0., 0., 0., 0., 0.],
         [0., (1 - j), 0., 0., 0., 0.],
         [0., 0., (1 - j), 0., 0., 0.],
         [0., 0., 0., (1 - j), 0., 0.],
         [0., 0., 0., 0., (1 - j), (1 - j)]])


def build_ujac(chains_cs, shares, ss_dstn_by_educ, T, dx=DX):
    UJAC = np.zeros((6, T, T))
    for w_e, m_cs, v_e in zip(shares, chains_cs, ss_dstn_by_educ):
        tran_dx = perturbed_chain(m_cs.T, dx)
        UJ = np.zeros((6, T, T))
        for s in range(T):
            dstn = v_e
            for i in range(T):
                dstn = np.dot(tran_dx if i == s else m_cs, dstn)
                UJ[:, i, s] = (dstn - v_e) / dx
        UJAC += w_e * UJ
    return UJAC


def ujac_spot_identity(chains_cs, shares, ss_dstn_by_educ, spots, dx=DX):
    """G-UJAC: the closed-form advection at (t, s), vs the F-5 loop column.

    dD_t = Pi^(t-s-1) (Pi_dx - Pi) D_ss / dx for t > s (and
    dD_s = (Pi_dx - Pi) D_ss / dx at t = s)."""
    worst = 0.0
    for (t, s) in spots:
        loop_col = np.zeros(6)
        closed = np.zeros(6)
        for w_e, m_cs, v_e in zip(shares, chains_cs, ss_dstn_by_educ):
            tran_dx = perturbed_chain(m_cs.T, dx)
            # loop semantics
            dstn = v_e
            for i in range(t + 1):
                dstn = np.dot(tran_dx if i == s else m_cs, dstn)
            loop_col += w_e * (dstn - v_e) / dx
            # closed form
            base = np.dot(tran_dx - m_cs, v_e) / dx
            closed += w_e * np.dot(np.linalg.matrix_power(m_cs, t - s), base)
        worst = max(worst, float(np.max(np.abs(loop_col - closed))))
    return worst


def reconstruct(obj_path, chains, splurge, T=300, arm="cash",
                rho_mode="livprb", phi_b=0.015):
    with open(obj_path, "rb") as f:
        RAW = pickle.load(f)

    shares = list(chains["shares"])
    chains_cs = [np.asarray(c, float) for c in chains["chains"]]
    seps = chains["seps"]
    job_find = float(chains["jf"])

    ss_dstn_by_educ = [ergodic(m) for m in chains_cs]
    ss_dstn = sum(w * v for w, v in zip(shares, ss_dstn_by_educ))
    N_ss = ss_dstn[0]
    _sep_flow = sum(w * v[0] * s_e
                    for w, v, s_e in zip(shares, ss_dstn_by_educ, seps))
    job_sep = _sep_flow / float(sum(w * v[0]
                                    for w, v in zip(shares, ss_dstn_by_educ)))

    UJAC = build_ujac(chains_cs, shares, ss_dstn_by_educ, T)

    # ---- calibration scalars (ge.py formulas) ------------------------
    alpha = .65
    phi_ss = .71
    v_ss = N_ss * job_sep / phi_ss
    searchers = (1 - N_ss) + N_ss * job_sep
    theta_ss = v_ss / searchers
    chi_ss = (phi_ss ** (1 / -alpha) / theta_ss) ** (-alpha)
    A_ss = float(RAW.get("A_ss_weighted", 1.4324029855872642))
    C_ss = float(RAW["C_ss_weighted"])
    delta = ((R ** 4) * (1 - (1 / 5))) ** (1 / 4)
    qb_ss = 1 / (R - delta)
    wage_ss = 1.0
    tau_ss = 0.3
    UI_ss = (1 - tau_ss) * .5 * wage_ss
    kappa = .07 * (wage_ss * phi_ss)
    HC_ss = ((kappa / phi_ss) * (1 - (1 / R) * (1 - job_sep)) + wage_ss)
    epsilon_p = 6
    MC_ss = (epsilon_p - 1) / epsilon_p
    Z_ss = HC_ss / MC_ss
    Y_ss = Z_ss * N_ss
    phi_w = 0.837

    # ---- splurge overlay --------------------------------------------
    rho = RHO_LIVPRB if rho_mode == "livprb" else None
    INPUTS6 = ["transfers", "tau", "UI_extend", "UI_rr", "eta", "w"]
    JC, JA = {}, {}
    for inp in INPUTS6:
        oC = np.asarray(RAW["C"][inp], float)[:T, :T]
        oA = np.asarray(RAW["A"][inp], float)[:T, :T]
        if arm == "cash":
            dY = np.zeros_like(oC)
            dY[0] = oC[0] + oA[0]
            dY[1:] = oC[1:] + oA[1:] - rho * oA[:-1]
            comp = dY
        elif arm == "legacy":
            pv = np.sum(oC / R ** np.arange(T)[:, None], axis=0)
            comp = np.diag(pv * R ** np.arange(T))
        else:
            raise ValueError(arm)
        JC[inp] = splurge * comp + (1 - splurge) * oC
        JA[inp] = (1 - splurge) * oA

    # ---- operators ---------------------------------------------------
    I = np.eye(T)
    L = np.eye(T, k=-1)
    m_eta = chi_ss * (1 - alpha) * theta_ss ** (-alpha)
    U0, U1, U2, U3, U4, U5 = (UJAC[i] for i in range(6))
    Ww = np.linalg.solve(I - phi_w * L, (1 - phi_w) / N_ss * I)
    a_B = (1 + delta * qb_ss) - phi_b * qb_ss * wage_ss * N_ss / Y_ss
    Bop = np.linalg.inv(qb_ss * I - a_B * L)

    dN_dtheta = U0 * m_eta
    dw_dtheta = Ww @ dN_dtheta
    dU12_dtheta = (U1 + U2) * m_eta
    F_theta = (UI_ss * dU12_dtheta
               - tau_ss * (N_ss * dw_dtheta + wage_ss * dN_dtheta))
    dB_dtheta = Bop @ F_theta
    dtau_dtheta = (phi_b * qb_ss / Y_ss) * (L @ dB_dtheta)
    HU = (JA["eta"] * m_eta + JA["w"] @ dw_dtheta + JA["tau"] @ dtau_dtheta
          - qb_ss * dB_dtheta)

    def NPV(irf, length):
        return float(np.sum(np.asarray(irf)[:length]
                            / R ** np.arange(length)))

    results = {}

    def solve_experiment(dH, dZ_cost, JC_own=None, dZ=None, extra_tau=None):
        dtheta = -np.linalg.solve(HU, dH)
        deta = m_eta * dtheta
        dN = U0 @ deta
        dw = Ww @ dN
        # tau path: re-derive from the full B path
        return dtheta, deta, dN, dw

    # 1) transfers
    dZ = np.zeros(T); dZ[0] = C_ss * .05
    dB_Z = Bop @ dZ
    dtau_Z = (phi_b * qb_ss / Y_ss) * (L @ dB_Z)
    dH = JA["transfers"] @ dZ + JA["tau"] @ dtau_Z - qb_ss * dB_Z
    dtheta, deta, dN, dw = solve_experiment(dH, dZ)
    dB = dB_Z + dB_dtheta @ dtheta
    dtau = (phi_b * qb_ss / Y_ss) * (L @ dB)
    dC = (JC["transfers"] @ dZ + JC["tau"] @ dtau + JC["eta"] @ deta
          + JC["w"] @ dw)
    results["transfers"] = dict(
        mult_h20=NPV(dC, 20) / NPV(dZ, T),
        mult_path=[NPV(dC, i + 1) / NPV(dZ, T) for i in range(20)])

    # 2) UI extension
    dZ = np.zeros(T); dZ[:4] = .2
    coef_ext = wage_ss * (1 - tau_ss) * (ss_dstn[3] + ss_dstn[4])
    dB_Z = Bop @ (coef_ext * dZ)
    dtau_Z = (phi_b * qb_ss / Y_ss) * (L @ dB_Z)
    dH = JA["UI_extend"] @ dZ + JA["tau"] @ dtau_Z - qb_ss * dB_Z
    dtheta, deta, dN, dw = solve_experiment(dH, None)
    dB = dB_Z + dB_dtheta @ dtheta
    dtau = (phi_b * qb_ss / Y_ss) * (L @ dB)
    dC = (JC["UI_extend"] @ dZ + JC["tau"] @ dtau + JC["eta"] @ deta
          + JC["w"] @ dw)
    dcost = coef_ext * dZ
    results["UI_extensions"] = dict(
        mult_h20=NPV(dC, 20) / NPV(dcost, T),
        mult_path=[NPV(dC, i + 1) / NPV(dcost, T) for i in range(20)])

    # 3) tax cut, household-financed
    dZ = np.zeros(T); dZ[:8] = -.02
    dB_Z = Bop @ (-wage_ss * N_ss * dZ)
    dtau_Z = dZ + (phi_b * qb_ss / Y_ss) * (L @ dB_Z)
    dH = JA["tau"] @ dtau_Z - qb_ss * dB_Z
    dtheta, deta, dN, dw = solve_experiment(dH, None)
    dB = dB_Z + dB_dtheta @ dtheta
    dtau = dZ + (phi_b * qb_ss / Y_ss) * (L @ dB)
    dC = JC["tau"] @ dtau + JC["eta"] @ deta + JC["w"] @ dw
    dcost = wage_ss * N_ss * dZ
    results["tax_cut"] = dict(
        mult_h20=-NPV(dC, 20) / NPV(dcost, T),
        mult_path=[-NPV(dC, i + 1) / NPV(dcost, T) for i in range(20)])

    scalars = dict(N_ss=N_ss, job_sep=job_sep, job_find=job_find,
                   theta_ss=theta_ss, m_eta=m_eta, A_ss=A_ss, C_ss=C_ss,
                   qb_ss=qb_ss, Y_ss=Y_ss, a_B=a_B, a_B_over_qb=a_B / qb_ss,
                   UI_ss=UI_ss, tau_ss=tau_ss, delta=delta, splurge=splurge)
    return dict(results=results, HU=HU, UJAC=UJAC, scalars=scalars,
                ss_dstn=ss_dstn)


def eta_chain_dy_gate(obj_path, chains, ss_income, T=300, rho=RHO_LIVPRB):
    """G-ETA: the eta column's budget-implied dY vs the chain-implied dY.

    budget side: dY = J_C + J_A - rho*lag(J_A) on the RAW eta Jacobians.
    chain side: dY[t,s] = y_state . UJAC[:, t, s] with the ss income vector
    (employed net wage; U1/U2 the UI level; U3..U5 the exhausted level) plus
    the direct t==s delivery of nothing (eta pays through states only).
    Returns (whole-matrix Frobenius rel gap, chain norm, per-column rel gaps)."""
    with open(obj_path, "rb") as f:
        RAW = pickle.load(f)
    oC = np.asarray(RAW["C"]["eta"], float)[:T, :T]
    oA = np.asarray(RAW["A"]["eta"], float)[:T, :T]
    dY_budget = np.zeros_like(oC)
    dY_budget[0] = oC[0] + oA[0]
    dY_budget[1:] = oC[1:] + oA[1:] - rho * oA[:-1]

    shares = list(chains["shares"])
    chains_cs = [np.asarray(c, float) for c in chains["chains"]]
    ss_by_educ = [ergodic(m) for m in chains_cs]
    UJAC = build_ujac(chains_cs, shares, ss_by_educ, T)
    y = np.asarray(ss_income, float)          # per-state income levels
    dY_chain = np.tensordot(y, UJAC, axes=(0, 0))
    gap = (np.linalg.norm(dY_budget - dY_chain)
           / max(np.linalg.norm(dY_chain), 1e-300))
    # PER-COLUMN as well as whole-matrix (2026-09-05). One Frobenius number over a
    # 300x300 matrix is the statistic LEAST able to see a defect confined to a single
    # column -- and column 0 (the unanticipated, no-earlier-date-to-respond column) is
    # exactly where the eta construction differs from every other, so it is exactly
    # where a defect would sit. The timing-conventions survey named this as the one
    # real gap in eta's gating. Reported, not gated: the threshold is the owner's to
    # set once the numbers are on the record.
    denom = np.maximum(np.linalg.norm(dY_chain, axis=0), 1e-300)
    per_col = np.linalg.norm(dY_budget - dY_chain, axis=0) / denom
    return float(gap), float(np.linalg.norm(dY_chain)), per_col
