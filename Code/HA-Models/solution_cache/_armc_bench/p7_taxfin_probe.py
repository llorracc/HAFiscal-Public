"""P7 (owner question, R-b thread): how much of the tax cut's strong
cumulative multiplier is the FINANCING ASYMMETRY (H5)?

The production tax-cut experiment is spending-financed (phi_G moves G),
and G has NO demand role in this model (the solve never imposes the
goods market), so its financing is demand-free. Checks/UI are
tax-financed (phi_b moves tau), and tau feeds the household Jacobian —
demand-costly. This probe re-runs the FIXED-REAL tax cut TAX-FINANCED:
the exogenous cut dtau_x[:8]=-0.02 plus a phi_b rule response on top,
with the household block seeing the TOTAL tau path. Self-contained
(mirrors step4/ge.py's constants + splurge overlay, legacy 0.3).
"""
import os
import pickle
import sys

import numpy as np
import scipy.sparse as sp

HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))

# ---- SAM chain + calibration (verbatim ge.py constants) ----
job_find = 2 / 3
EU_prob = 0.0306834
job_sep = EU_prob / (1 - job_find)
markov_array_ss = np.array(
    [[1 - job_sep * (1 - job_find), job_find, job_find, job_find, job_find, job_find],
     [job_sep * (1 - job_find), 0., 0., 0, 0, 0],
     [0., (1 - job_find), 0., 0., 0., 0.],
     [0., 0, (1 - job_find), 0., 0., 0.],
     [0., 0, 0., (1 - job_find), 0., 0.],
     [0., 0., 0, 0, (1 - job_find), (1 - job_find)]])
num_mrkv = 6
eig, ss = sp.linalg.eigs(markov_array_ss, k=1, which='LM')
ss_dstn = (ss[:, 0] / ss[:, 0].sum()).real
N_ss = ss_dstn[0]

def create_matrix_U(dx):
    jf = job_find + dx
    return np.array(
        [[1 - job_sep * (1 - jf), jf, jf, jf, jf, jf],
         [job_sep * (1 - jf), 0., 0., 0, 0, 0],
         [0., (1 - jf), 0., 0., 0., 0.],
         [0., 0, (1 - jf), 0., 0., 0.],
         [0., 0, 0., (1 - jf), 0., 0.],
         [0., 0., 0, 0, (1 - jf), (1 - jf)]])

dx = 0.0001
bigT = 300
dstn = ss_dstn
UJAC = np.zeros((num_mrkv, bigT, bigT))
for s in range(bigT):
    for i in range(bigT):
        if i == s:
            dstn = np.dot(create_matrix_U(dx), dstn)
        else:
            dstn = np.dot(markov_array_ss, dstn)
        UJAC[:, i, s] = (dstn - ss_dstn) / dx

alpha = .65
phi_ss = .71
v_ss = N_ss * job_sep / phi_ss
seachers = (1 - N_ss) + N_ss * job_sep
theta_ss = v_ss / seachers
chi_ss = (phi_ss ** (1 / -alpha) / theta_ss) ** (-alpha)
eta_ss = chi_ss * theta_ss ** (1 - alpha)
R = 1.01
r_ss = R - 1
A_ss_sim = 1.4324029855872642
delta = ((R ** 4) * (1 - (1 / 5))) ** (1 / 4)
qb_ss = 1 / (R - delta)
B_ss = A_ss_sim / qb_ss
wage_ss = 1.0
tau_ss = 0.3
UI = (1 - tau_ss) * .5 * wage_ss

JACS = os.path.join(HA, "FromPandemicCode", "HA_Fiscal_Jacs.obj")
with open(JACS, 'rb') as f:
    HA_fiscal_JAC = pickle.load(f)
C_ss = C_ss_sim = float(HA_fiscal_JAC['C_ss_weighted'])  # live default (jacs_c)

kappa = .07 * (wage_ss * phi_ss)
HC_ss = ((kappa / phi_ss) * (1 - (1 / R) * (1 - job_sep)) + wage_ss)
epsilon_p = 6
MC_ss = (epsilon_p - 1) / epsilon_p
Z_ss = HC_ss / MC_ss
Y_ss = Z_ss * N_ss
G_ss = tau_ss * wage_ss * ss_dstn[0] - (UI * (ss_dstn[1] + ss_dstn[2])
                                        + (1 + delta * qb_ss) * B_ss - qb_ss * B_ss)
pi_ss = 0.0
phi_pi = 1.5
phi_y = 0.0
varphi = 96.9
rho_r = 0.0
kappa_p_ss = epsilon_p / varphi
phi_b = .1
phi_w = 1.0

import sequence_jacobian as sj  # noqa: E402
from sequence_jacobian.classes import JacobianDict, SteadyStateDict  # noqa: E402
from sequence_jacobian import create_model  # noqa: E402

Jacobian_Dict = JacobianDict({'C': HA_fiscal_JAC['C'], 'A': HA_fiscal_JAC['A']})

# splurge overlay, legacy 0.3 (verbatim semantics)
from copy import deepcopy  # noqa: E402
old_JD = deepcopy(Jacobian_Dict)
periods = old_JD['C']['transfers'].shape[0]
splurge = 0.3
for ji in ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w']:
    pv = np.sum((old_JD['C'][ji] / R ** np.arange(periods)), axis=0)
    comp = np.diag(pv * R ** np.arange(periods))
    Jacobian_Dict['C'][ji] = splurge * comp + (1 - splurge) * old_JD['C'][ji]
    Jacobian_Dict['A'][ji] = (1 - splurge) * old_JD['A'][ji]

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

@sj.simple
def matching(theta, chi):
    eta = chi * theta ** (1 - alpha)
    phi = chi * theta ** (-alpha)
    return eta, phi

@sj.simple
def production(Z, N):
    Y = Z * N
    return Y

@sj.simple
def vacancies(N, phi, job_sep):
    v = (N - (1 - job_sep(-1)) * N(-1)) / phi
    return v

@sj.simple
def mkt_clearing(C, G, A, qb, B, w, N, U1, U2, U3, U4, U5):
    Y_priv = (1 - tau_ss) * wage_ss * .5 * (U3 + U4 + U5) + (1 - tau_ss) * wage_ss * .2 * (U1 + U2)
    goods_mkt = C + G - w * N - Y_priv
    asset_mkt = A - qb * B
    return goods_mkt, asset_mkt, Y_priv

@sj.simple
def fisher_clearing_fixed_real_rate(pi):
    i = (1 + pi(+1)) * (1 + r_ss) - 1
    return i

# --- SPENDING-financed tax cut, fixed real (the production block) ---
@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_G_fixed_real_rate(B, N, w, v, pi, UI, U1, U2, transfers, phi_G, tau, deficit_T):
    fiscal_resid = (1 + delta * qb_ss) * B(-1) + G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss \
        + transfers + UI * (U1 + U2) + - qb_ss * B - (tau) * w * N
    tax_cost = (tau) * 1.0 * N_ss
    return fiscal_resid, tax_cost

@sj.simple
def fiscal_rule_G(B, phi_G, deficit_T):
    G = G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    return G

# --- TAX-financed tax cut, fixed real (the probe block): the exogenous
# cut dtau_x rides on TOP of the phi_b tax rule; the household Jacobian
# consumes the TOTAL tau path; G stays at G_ss. ---
@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_taxfin_fixed_real_rate(B, N, w, v, pi, UI, U1, U2, transfers, dtau_x, phi_b, deficit_T):
    tau = tau_ss + dtau_x + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    fiscal_resid = (1 + delta * qb_ss) * B(-1) + G_ss + transfers + UI * (U1 + U2) \
        + - qb_ss * B - tau * w * N
    tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss  # mechanical cost concept, as production
    G = G_ss + 0 * B
    return fiscal_resid, tau, tax_cost, G

SteadyState_Dict = SteadyStateDict({
    "asset_mkt": 0.0, "goods_mkt": 0.0, "fiscal_resid": 0.0, "nkpc_resid": 0.0,
    "epsilon_p": epsilon_p,
    "U": (1 - N_ss), "U1": ss_dstn[1], "U2": ss_dstn[2], "U3": ss_dstn[3],
    "U4": ss_dstn[4], "U5": ss_dstn[5],
    "HC": MC_ss * Z_ss, "MC": MC_ss, "C": C_ss_sim, "r": r_ss, "r_ante": r_ss,
    "Y": Y_ss, "B": B_ss, "G": G_ss, "A": A_ss_sim, "tau": tau_ss,
    "eta": eta_ss, "phi_b": phi_b, "phi_w": phi_w, "N": N_ss, "phi": phi_ss,
    "v": v_ss, "ev": 0.0, "Z": Z_ss, "job_sep": job_sep, "w": wage_ss,
    "pi": pi_ss, "i": r_ss, "qb": qb_ss, "varphi": varphi, "rho_r": rho_r,
    "kappa_p": kappa_p_ss, "phi_pi": phi_pi, "phi_y": phi_y, "chi": chi_ss,
    "theta": theta_ss, "UI": UI, "transfers": 0.0, "UI_extend": 0.0,
    "deficit_T": -1, "UI_rr": 0.0, "tax_cost": tau_ss * wage_ss * N_ss,
    "dtau_x": 0.0, "lag": -1,
})

common = [Jacobian_Dict, production, matching, Phillips_Curve, marginal_cost,
          UJAC, hiring_cost, wage_, vacancies, unemployment1,
          fisher_clearing_fixed_real_rate, mkt_clearing]
UJAC_dict = JacobianDict({
    'N': {'eta': UJAC[0]}, 'U1': {'eta': UJAC[1]}, 'U2': {'eta': UJAC[2]},
    'U3': {'eta': UJAC[3]}, 'U4': {'eta': UJAC[4]}, 'U5': {'eta': UJAC[5]}})
common = [Jacobian_Dict, production, matching, Phillips_Curve, marginal_cost,
          UJAC_dict, hiring_cost, wage_, vacancies, unemployment1,
          fisher_clearing_fixed_real_rate, mkt_clearing]

model_G = create_model(common + [fiscal_G_fixed_real_rate, fiscal_rule_G], name="taxcut_Gfin")
model_T = create_model(common + [fiscal_taxfin_fixed_real_rate], name="taxcut_taxfin")

def NPV(irf, length):
    out = 0
    for i in range(length):
        out += irf[i] / R ** i
    return out

dtau = np.zeros(bigT)
dtau[:8] = -.02

ssd_G = deepcopy(SteadyState_Dict)
ssd_G['phi_G'] = -0.015
ssd_G['phi_w'] = 0.837
ssd_G['deficit_T'] = -1
irf_G = model_G.solve_impulse_linear(ssd_G, ['theta'], ['asset_mkt'], {'tau': dtau})

ssd_T = deepcopy(SteadyState_Dict)
ssd_T['phi_b'] = 0.015
ssd_T['phi_w'] = 0.837
ssd_T['deficit_T'] = -1
irf_T = model_T.solve_impulse_linear(ssd_T, ['theta'], ['asset_mkt'], {'dtau_x': dtau})

print(f"{'h':>4s} {'G-financed (production)':>24s} {'TAX-financed (probe)':>22s}")
for h in (1, 4, 8, 12, 20):
    mG = -NPV(irf_G['C'], h) / NPV(irf_G['tax_cost'], 300)
    mT = -NPV(irf_T['C'], h) / NPV(irf_T['tax_cost'], 300)
    print(f"{h:>4d} {mG:24.4f} {mT:22.4f}")
mG20 = np.array([-NPV(irf_G['C'], i + 1) / NPV(irf_G['tax_cost'], 300) for i in range(20)])
mT20 = np.array([-NPV(irf_T['C'], i + 1) / NPV(irf_T['tax_cost'], 300) for i in range(20)])
print(f"peak: G-financed {mG20.max():.4f}   tax-financed {mT20.max():.4f}")
print(f"[check] G-financed h=20 vs production fixed_real 1.4290: {mG20[19]:.4f}")
