#!/usr/bin/env python3
"""probe_pf_guard_bug080_phase.py -- diagnose the PF-decay concavity-guard trip on the ESTIMATION surface's
per-education AD "print" pass under the earnings phase (2026-08-29; plan 20260828-2030h, post2 OPEN item).

What it reproduces, in isolation and instrumented, is the exact failing call chain
    EstimAggFiscalMAIN.calcAllResults
      -> betas_obj_func_educ(beta, nabla, GICx, educ_type=0, print_mode=True)     (HAFISCAL_NM_IN_PLACE=1 default)
        -> agent.DiscFac = <estimated atom>  on the EXISTING economy agents (in place)
        -> AggDemandEconomy.solve()  (warm-start gate: from_solution = agent.solution[0] whenever S matches)
          -> HARK.solve_agent(..., from_solution=<policy solved under the PREVIOUS DiscFac>)
            -> solve_agg_cons_markov_alt  ->  the BUG-062 guard raises on the first sweep.
for the ONE agent that trips: the Dropout top DiscFac atom (index 6 of the 7 dropout types). The estimation
module solves its 21 types once at the HARD-CODED initial atoms (EstimParameters DiscFacMeanD = 0.9647 +/- 0.025,
top atom beta = 0.986129) and the print pass then re-assigns the ESTIMATED atoms on the same agent objects and
re-solves warm from the previous beta's policy. This is BUG-080 (BUGS_private/HAFiscal_BUG-080_*.md, OPEN --
GUARDED by HAFISCAL_NM_IN_PLACE=0), which the spine5 driver's post2 stage did not carry.

Sections (all numbers printed; nothing is asserted silently):
  A  identity: agent / atoms / economy configuration; which atoms move to a MORE patient beta (the trip condition)
  B  the seed: cold solve of the atom at its module-level beta through the production router (store/ATI/EGM)
  C  the reproduction: in-place re-assignment to the estimated beta, terminal-vs-attach h_AD, the seed's top knot
     against both PF lines, the one-sweep trip (verbatim), and the full economy.solve() trip (verbatim)
  D  hand derivation of the PF human wealth under the phase (independent of mom_bounds) vs compute_pf_decay_limits
  E  (optional --descent) guard-free warm descent from the seed: the above-line knot is a transient that converges
     to the same policy a cold solve gives;  (--cold-egm) a cold guard-ON EGM solve at the new beta from the
     constrained-PF terminal (the guard's premise) for the converged top knot vs the line.
Usage (from Code/HA-Models/FromPandemicCode, with the failing run's env):
  HAFISCAL_EARNINGS_PHASE_HAZARD=1/120 HAFISCAL_SPLURGE_FILE=... HAFISCAL_DISCFAC_FILE=<estimated atoms file> \
    python ../probe_pf_guard_bug080_phase.py [--descent] [--cold-egm] [--atom 6]
  HAFISCAL_EARNINGS_PHASE_HAZARD=0 ... --discfac-file Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt   (the spine4 trip)
"""
import argparse
import os
import sys
import time
import traceback
from copy import deepcopy

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))            # Code/HA-Models
FPC = os.path.join(HERE, 'FromPandemicCode')
for _p in (FPC, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(FPC)

ap = argparse.ArgumentParser()
ap.add_argument('--discfac-file', default=os.environ.get('HAFISCAL_DISCFAC_FILE')
                or os.path.join(HERE, 'Results', 'DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt'),
                help='the estimated (beta, nabla, GICx) file the print pass re-assigns from')
ap.add_argument('--atom', type=int, default=6, help='dropout DiscFac atom index (0..6); 6 = the most patient')
ap.add_argument('--descent', action='store_true',
                help='guard-free (HAFISCAL_PF_DECAY_EXTRAP=0) warm descent from the seed policy, sweep by sweep')
ap.add_argument('--cold-egm', action='store_true',
                help='cold guard-ON EGM solve at the new beta from the constrained-PF terminal (slow: 10-30 min)')
ap.add_argument('--max-sweeps', type=int, default=6000)
args = ap.parse_args()
sys.argv = sys.argv[:1]   # EstimParameters parses sys.argv[1:] as (Rfree, CRRA, IncUnemp): keep the probe's flags out of it

t_start = time.time()
def say(*a):
    print(*a, flush=True)

say('=' * 100)
say(f'probe_pf_guard_bug080_phase  {time.strftime("%Y-%m-%d %H:%M:%S")}  host={os.uname().nodename}  cwd={os.getcwd()}')
for k in ('HAFISCAL_EARNINGS_PHASE_HAZARD', 'HAFISCAL_SPLURGE_FILE', 'HAFISCAL_DISCFAC_FILE', 'HAFISCAL_STEP5_ATI',
          'HAFISCAL_POLICY_STORE', 'HAFISCAL_PF_DECAY_EXTRAP', 'HAFISCAL_PF_DECAY_Q', 'HAFISCAL_NM_IN_PLACE',
          'HAFISCAL_CHECK_MARKOV_INPUTS', 'HAFISCAL_FTI_REPO', 'HAFISCAL_WORLD', 'HAFISCAL_UI_STATE_ENCODING'):
    say(f'  env {k}={os.environ.get(k)!r}')
say('=' * 100)

import EstimParameters as EP                      # noqa: E402  (prints [grid_sizing] etc.)
from AggFiscalModel import (AggFiscalType, AggregateDemandEconomy,   # noqa: E402
                            compute_pf_decay_limits)
import earnings_phase as _ep                      # noqa: E402
from mom_bounds import compute_mpc_min, solve_markov_human_wealth   # noqa: E402
from income_process_sst import build_unemployed_inc_shk_dstn        # noqa: E402
from HARK.distributions import Uniform            # noqa: E402
from HARK.core import solve_one_cycle, solve_agent  # noqa: E402
from HARK.metric import distance_metric           # noqa: E402

h_haz = _ep.hazard()
R = float(EP.Rfree_base[0]); L = float(EP.LivPrb_base[0]); rho = float(EP.CRRA)
G_d = float(EP.PermGroFac_base_d[0]); G_u = float(EP.PermGroFac_unemp)

def mpc_min_hand(beta):
    return 1.0 - (R * beta * L) ** (1.0 / rho) / R

# ----------------------------------------------------------------------------------------------- A: identity
say('\n[A] identity of the failing solve')
say('  ' + _ep.describe())
J4 = int(EP.CondMrkvArrays_base_d[0].shape[0])
say(f'  estimation base chain: J={J4} employment states (2 + UBspell_normal={EP.UBspell_normal}); '
    f'S = n_phases*J*n_macro = {_ep.n_states(J4, 1)}; init_dropout num_base_MrkvStates={EP.init_dropout["num_base_MrkvStates"]}; '
    f'module-level num_base_MrkvStates (production count)={EP.num_base_MrkvStates}')
say(f'  R={R} LivPrb={L:.6f} CRRA={rho} G_d(employed, growing)={G_d:.6f} G_unemp={G_u} matured growth={_ep.MATURED_GROWTH}')
cap_old_world = EP._beta_AGG_by_edu[0] * EP.theGICfactor ** rho
say(f'  GIC cap (dropout): GICmaxBetas[0]={EP.GICmaxBetas[0]:.6f}  gic_capped_beta(0, {EP.theGICfactor})={EP.gic_capped_beta(0, EP.theGICfactor):.6f} '
    f'(cap growth={EP._cap_growth_by_edu[0]:.6f}; = (Gamma/L)^rho/R * shave^rho)')

# the module-level (hard-coded initial) dropout atoms, exactly as EstimParameters built + clipped them
old_atoms = np.asarray(EP.DiscFacDstns[0].atoms[0], float).copy()
say(f'  module-level dropout atoms (EstimParameters DiscFacMeanD={EP.DiscFacMeanD} +/- {EP.DiscFacSpreadD}, '
    f'_approx_equiprobable({EP.DiscFacCount}), GIC-clipped): {np.array2string(old_atoms, precision=6)}')

# the print-pass atoms, exactly as betas_obj_func_educ builds + clips them from the estimated file
say(f'  estimated-atoms file: {args.discfac_file}')
est = None
with open(args.discfac_file) as f:
    for line in f:
        line = line.strip()
        if not line or not line.startswith('{'):   # the file carries a 'Parameters: ...' header line since 2026-09
            continue
        d = eval(line)
        if d['EducationGroup'] == 0:
            est = d
assert est is not None, 'no EducationGroup 0 row in the file'
beta_c, nabla, GICx = est['beta'], est['nabla'], est['GICx']
GICfactor = np.exp(GICx) / (1 + np.exp(GICx))
dfs_new = Uniform(beta_c - nabla, beta_c + nabla).discretize(EP.DiscFacCount)
new_atoms = np.asarray(dfs_new.atoms[0], float).copy()
cap_pass = EP.gic_capped_beta(0, GICfactor)
n_clipped = int(np.sum(new_atoms > cap_pass))
new_atoms = np.minimum(new_atoms, cap_pass)
new_atoms = np.maximum(new_atoms, EP.minBeta)
say(f'  print-pass dropout atoms: Uniform({beta_c:.6f} +/- {nabla:.6f}).discretize({EP.DiscFacCount}) clipped at '
    f'gic_capped_beta(0, GICfactor={GICfactor:.6f})={cap_pass:.6f} ({n_clipped} atom(s) clipped): '
    f'{np.array2string(new_atoms, precision=6)}')
say('  per atom: beta_old -> beta_new, MPCmin_old -> MPCmin_new, ratio (>1 means the seed policy lies ABOVE the new '
    'PF line at high m: the guard trips)')
for b in range(EP.DiscFacCount):
    ko, kn = mpc_min_hand(old_atoms[b]), mpc_min_hand(new_atoms[b])
    flag = 'TRIP candidate (beta raised in place)' if new_atoms[b] > old_atoms[b] + 1e-12 else 'ok (beta lowered/equal)'
    say(f'    atom {b}: {old_atoms[b]:.6f} -> {new_atoms[b]:.6f}   MPCmin {ko:.6f} -> {kn:.6f}   ratio {ko / kn:.4f}   {flag}')

b = args.atom
beta_old, beta_new = float(old_atoms[b]), float(new_atoms[b])

# build the dropout base type exactly as EstimAggFiscalMAIN does (lines ~741-770)
base_d = AggFiscalType(**EP.init_dropout)
base_d.cycles = 0
eco = AggregateDemandEconomy(**EP.init_ADEconomy)
base_d.get_economy_data(eco)
_emp0 = base_d.IncShkDstn[0]
_p_on = getattr(base_d, 'perm_shocks_during_unemployment', False)
_t_on = getattr(base_d, 'tran_shocks_during_unemployment', False)
_u = build_unemployed_inc_shk_dstn(_emp0, base_d.IncUnemp, _p_on, _t_on)
_unb = build_unemployed_inc_shk_dstn(_emp0, base_d.IncUnempNoBenefits, _p_on, _t_on)
_u.seed = 763607780; _u.reset(); _unb.seed = 763607780; _unb.reset()
base_d.IncShkDstn = [_ep.wrap_list([_emp0] + [_u] * EP.UBspell_normal + [_unb])]
base_d.IncShkDstn_base = base_d.IncShkDstn
S = int(np.asarray(base_d.MrkvArray[0]).shape[0])
Cgrid = np.asarray(base_d.Cgrid, float)
say(f'  economy: S={S} (MrkvArray[0] {np.asarray(base_d.MrkvArray[0]).shape}); num_macro_states={getattr(base_d, "num_macro_states", "<unset>")}; '
    f'Cgrid={Cgrid.tolist()} ({Cgrid.size} C-slices); eco.ADelasticity={eco.ADelasticity} (demand_ADelasticity={eco.demand_ADelasticity}); '
    f'ADFunc(0.9,True)={float(base_d.ADFunc(0.9, True))} ADFunc(1.1,True)={float(base_d.ADFunc(1.1, True))}')
say(f'  solve grid: aXtraMax={base_d.aXtraMax} aXtraCount={base_d.aXtraCount} aXtraGrid[-1]={float(base_d.aXtraGrid[-1]):.6f} '
    f'BoroCnstArt={base_d.BoroCnstArt}; len(IncShkDstn[0])={len(base_d.IncShkDstn[0])}')
PGF_full = np.asarray(base_d.PermGroFac[0], float).ravel()
say(f'  PermGroFac[0]: len={PGF_full.size} (first S used by the solver): {np.array2string(PGF_full[:S], precision=6)}  '
    f'[rest: {np.array2string(PGF_full[S:], precision=6)}]')
say(f'  Rfree[:S]={np.array2string(np.asarray(base_d.Rfree, float).ravel()[:S], precision=4)}  '
    f'LivPrb[0][:S]={np.array2string(np.asarray(base_d.LivPrb[0], float).ravel()[:S], precision=6)}')
E_state = np.array([float(np.sum(np.asarray(d.pmv) * np.asarray(d.atoms[0]) * np.asarray(d.atoms[1])))
                    for d in base_d.IncShkDstn[0]])
say(f'  E[psi*theta] per state: {np.array2string(E_state, precision=6)}')

def make_atom(beta, idx, pmv):
    a = deepcopy(base_d)
    a.AgentCount = int(np.floor(EP.AgentCountTotal * EP.data_EducShares[0] * pmv))
    a.DiscFac = float(beta)
    a.seed = idx
    a.pop_rescale_factor = 1.0
    return a

M_TRIP = 475.572   # the failing run's m_top (state 0, C-slice 0)
m_eval = np.array([1.0, 5.0, 20.0, 40.0, 100.0, 200.0, 300.0, 400.0, M_TRIP, 600.0])

def line(beta, hvec, m):
    return mpc_min_hand(beta) * (m + hvec)

# ----------------------------------------------------------------------------------------------- B: the seed
say(f'\n[B] the seed: cold solve of dropout atom {b} at its MODULE-LEVEL beta_old={beta_old:.6f} through the production router')
agent = make_atom(beta_old, b, EP.DiscFacDstns[0].pmv[b])
eco.agents = [agent]
t0 = time.time()
eco.solve()
say(f'  cold solve wall={time.time() - t0:.2f}s  _step5_ati_used={getattr(agent, "_step5_ati_used", False)}  '
    f'completed_cycles={getattr(agent, "completed_cycles", None)}  cFunc[0] class={type(agent.solution[0].cFunc[0]).__name__}')
sol_old = agent.solution[0]
MPC_old, hAD_old = compute_pf_decay_limits(np.asarray(agent.MrkvArray[-1], float), agent.Rfree, agent.PermGroFac,
                                           agent.IncShkDstn[0], Cgrid, agent.ADFunc, agent.num_base_MrkvStates,
                                           float(agent.DiscFac), float(agent.CRRA), agent.LivPrb)
say(f'  beta_old line: MPCmin={MPC_old:.6f} (hand {mpc_min_hand(beta_old):.6f}); h_AD[0] (all slices) = {np.array2string(hAD_old[:, 0], precision=4)}')
c_seed = np.array([float(sol_old.cFunc[0](m, Cgrid[0])) for m in m_eval])
say('  seed policy (state 0, C=%.1f):' % Cgrid[0])
say('      m        c_seed    line_old   c/line_old   line_new(beta_new)   c/line_new')
for m, c in zip(m_eval, c_seed):
    lo = line(beta_old, hAD_old[0, 0], m); ln = line(beta_new, hAD_old[0, 0], m)
    say(f'   {m:8.3f}   {c:9.5f}   {lo:9.5f}   {c / lo:8.4f}       {ln:9.5f}        {c / ln:8.4f}')

# ----------------------------------------------------------------------------------------------- C: reproduction
say(f'\n[C] the reproduction: in-place re-assignment beta {beta_old:.6f} -> {beta_new:.6f} (as betas_obj_func_educ does), then solve')
agent.AgentCount = int(np.floor(EP.AgentCountTotal * EP.data_EducShares[0] * dfs_new.pmv[b]))
agent.DiscFac = beta_new
agent.seed = b
Cgrid_before, ADFunc_before = agent.Cgrid, agent.ADFunc
agent.pre_solve()                       # what economy.solve() does first: rebuilds the constrained-PF terminal
say(f'  after pre_solve: Cgrid same object={agent.Cgrid is Cgrid_before}  ADFunc same object={agent.ADFunc is ADFunc_before}')
# h_AD as the TERMINAL computes it (self.PermGroFac list, self.LivPrb list, self.MrkvArray[-1], self.IncShkDstn[0])
MPC_t, hAD_t = compute_pf_decay_limits(np.asarray(agent.MrkvArray[-1], float), agent.Rfree, agent.PermGroFac,
                                       agent.IncShkDstn[0], Cgrid, agent.ADFunc, agent.num_base_MrkvStates,
                                       float(agent.DiscFac), float(agent.CRRA), agent.LivPrb)
# h_AD as the SOLVER computes it (the period-0 time-varying entries HARK hands solve_agg_cons_markov_alt)
MPC_s, hAD_s = compute_pf_decay_limits(np.asarray(agent.MrkvArray[0], float), agent.Rfree, agent.PermGroFac[0],
                                       agent.IncShkDstn[0], Cgrid, agent.ADFunc, agent.num_base_MrkvStates,
                                       float(agent.DiscFac), float(agent.CRRA), agent.LivPrb[0])
say(f'  MPCmin terminal={MPC_t:.8f} solver={MPC_s:.8f} hand={mpc_min_hand(beta_new):.8f}   '
    f'max|h_AD_terminal - h_AD_solver|={float(np.max(np.abs(hAD_t - hAD_s))):.3e}   h_AD C-flat: max over slices |h_AD[n]-h_AD[0]|={float(np.max(np.abs(hAD_s - hAD_s[0:1]))):.3e}')
say(f'  h_AD (solver) by current state, slice 0: {np.array2string(hAD_s[0], precision=4)}')
say('  constrained-PF terminal vs the line MPCmin*(m+h_AD[n][0]) at state 0 (must coincide -> the terminal start IS the line):')
for n in range(Cgrid.size):
    for m in (100.0, M_TRIP, 1000.0):
        ct = float(agent.solution_terminal.cFunc[0](m, Cgrid[n]))
        say(f'     slice {n} C={Cgrid[n]:.1f} m={m:8.3f}: terminal c={ct:.6f}  line={MPC_s * (m + hAD_s[n, 0]):.6f}  diff={ct - MPC_s * (m + hAD_s[n, 0]):+.2e}')
line_new_top = MPC_s * (M_TRIP + hAD_s[0, 0])
c_seed_top = float(sol_old.cFunc[0](M_TRIP, Cgrid[0]))
say(f'  SEED top-knot test at m_top={M_TRIP}: seed c={c_seed_top:.5f}  new line={line_new_top:.5f}  '
    f'seed/line={c_seed_top / line_new_top:.4f}  (old line {MPC_old * (M_TRIP + hAD_old[0, 0]):.5f}; MPCmin_old/MPCmin_new={MPC_old / MPC_s:.4f})')

say('  -- one backward sweep of the agent\'s own solver from the seed (solve_one_cycle(agent, seed, None)):')
try:
    swept = solve_one_cycle(agent, sol_old, None)[0]
    c1 = float(swept.cFunc[0](M_TRIP, Cgrid[0]))
    say(f'     no raise: c(m_top)={c1:.5f} vs line {line_new_top:.5f} (ratio {c1 / line_new_top:.4f})')
except ValueError as e:
    say('     RAISED ValueError (verbatim):')
    say('     ' + str(e))

say('  -- the full failing path: eco.agents=[agent]; eco.solve()  (warm-start gate -> solve_agent(from_solution=seed)):')
eco.agents = [agent]
try:
    eco.solve()
    say('     no raise -- EXPECTED since the BUG-080 fix (2026-09-09): the warm-start gate declines the less-patient seed and the solve cold-starts')
except ValueError as e:
    tb = traceback.extract_tb(sys.exc_info()[2])
    say('     RAISED ValueError (verbatim):')
    say('     ' + str(e))
    say('     frames: ' + ' -> '.join(f'{os.path.basename(fr.filename)}:{fr.lineno}:{fr.name}' for fr in tb))

# ----------------------------------------------------------------------------------------------- D: h by hand
say('\n[D] PF human wealth of the growing-employed state by hand (independent of mom_bounds), growth INTO the destination state')
M4 = np.asarray(EP.CondMrkvArrays_base_d[0], float)
if h_haz > 0:
    M_hand = np.block([[(1.0 - h_haz) * M4, h_haz * M4], [np.zeros((J4, J4)), M4]])
    E_hand = np.r_[E_state[:J4], E_state[:J4]]
    G_hand = np.r_[[G_d] + [G_u] * (J4 - 1), [_ep.MATURED_GROWTH] * J4]
else:
    M_hand, E_hand, G_hand = M4, E_state[:J4], np.array([G_d] + [G_u] * (J4 - 1))
say(f'  chain check: agent.MrkvArray[0] == [[(1-h)M4, hM4],[0, M4]] -> {np.allclose(np.asarray(agent.MrkvArray[0], float), M_hand)}; '
    f'agent PermGroFac[:S] == G_hand -> {np.allclose(PGF_full[:S], G_hand)}; E per state == wrapped -> {np.allclose(E_state, E_hand)}')
say(f'  4-state employment chain M4 (rows: e, u1, u2, u_nb):\n{np.array2string(M4, precision=6)}')
Dm = M_hand * (G_hand / R)[None, :]
h_lin = np.linalg.solve(np.eye(M_hand.shape[0]) - Dm, Dm @ E_hand)
# brute-force PDV: y_t[j] = E[ prod_{s<=t} Gamma_s ; state_t = j ], income at t = E_j; discount R^-t
T = 40000
y = np.zeros(M_hand.shape[0]); y[0] = 1.0
pdv = 0.0; disc = 1.0
MG = M_hand * G_hand[None, :]
for t in range(1, T + 1):
    y = y @ MG
    disc /= R
    pdv += disc * float(y @ E_hand)
say(f'  linear system (I - M diag(G/R)) h = M diag(G/R) E  ->  h[0]={h_lin[0]:.6f}; forward PDV sum to T={T}: {pdv:.6f}')
say(f'  code: solve_markov_human_wealth(...)[0]={solve_markov_human_wealth(M_hand, np.full(M_hand.shape[0], R), E_hand, PermGroFac_by_state=G_hand)[0]:.6f}; '
    f'compute_pf_decay_limits h_AD[0][0]={hAD_s[0, 0]:.6f}')
say(f'  by state (hand): {np.array2string(h_lin, precision=4)}')
x_m = 1.0 / (R - 1.0)
if h_haz > 0:
    x_g = ((1 - h_haz) * G_d / R + h_haz / R * (1.0 + x_m)) / (1.0 - (1 - h_haz) * G_d / R)
    say(f'  no-unemployment closed forms: matured x_m=1/(R-1)={x_m:.3f}; growing x_g=((1-h)G/R + (h/R)(1+x_m))/(1-(1-h)G/R)={x_g:.3f}; '
        f'growth-for-life (G/R)/(1-G/R)={(G_d / R) / (1 - G_d / R):.3f}')
else:
    say(f'  no-unemployment closed form: growth-for-life (G/R)/(1-G/R)={(G_d / R) / (1 - G_d / R):.3f}')
# alternative convention check: growth indexed by the CURRENT state (what the code does NOT do)
Dc = (G_hand / R)[:, None] * M_hand
h_cur = np.linalg.solve(np.eye(M_hand.shape[0]) - Dc, Dc @ E_hand)
say(f'  (if growth were indexed by the CURRENT state instead: h[0]={h_cur[0]:.6f} -- not what the solver does: '
    f'loop 1 uses PermGroFac[j] of the NEXT state j in mNrmNext and in PermGroFac[j]**(-CRRA))')

# ----------------------------------------------------------------------------------------------- E: descent / cold
if args.descent:
    say(f'\n[E1] guard-free warm descent from the seed at beta_new={beta_new:.6f} (HAFISCAL_PF_DECAY_EXTRAP=0: no attach, no guard)')
    os.environ['HAFISCAL_PF_DECAY_EXTRAP'] = '0'
    a2 = deepcopy(agent)
    a2.pre_solve()
    sol = sol_old
    t0 = time.time()
    tol = float(getattr(a2, 'tolerance', 1e-6))
    last = None
    for k in range(1, args.max_sweeps + 1):
        new = solve_one_cycle(a2, sol, None)[0]
        dist = float(distance_metric(new, sol))
        c_top = float(new.cFunc[0](M_TRIP, Cgrid[0]))
        if k <= 10 or k % 100 == 0 or dist <= tol:
            say(f'   sweep {k:5d}: c(m_top)={c_top:.5f}  c/line_new={c_top / line_new_top:.4f}  dist={dist:.3e}')
        sol = new
        last = (k, c_top, dist)
        if dist <= tol:
            break
    say(f'   converged: sweeps={last[0]} c(m_top)={last[1]:.5f} (line {line_new_top:.5f}, ratio {last[1] / line_new_top:.4f}) dist={last[2]:.3e} '
        f'tol={tol:g} wall={time.time() - t0:.1f}s')
    sol_warm = sol
    os.environ['HAFISCAL_PF_DECAY_EXTRAP'] = '1'
    # reference: a COLD solve at beta_new through the router (store/ATI/EGM), guard ON
    say(f'[E2] cold reference at beta_new={beta_new:.6f} through the production router (guard ON)')
    ref = make_atom(beta_new, b, dfs_new.pmv[b])
    eco.agents = [ref]
    t0 = time.time()
    eco.solve()
    say(f'   wall={time.time() - t0:.2f}s _step5_ati_used={getattr(ref, "_step5_ati_used", False)} completed_cycles={getattr(ref, "completed_cycles", None)}')
    sol_ref = ref.solution[0]
    c_ref_top = float(sol_ref.cFunc[0](M_TRIP, Cgrid[0]))
    say(f'   reference c(m_top)={c_ref_top:.5f} vs line {line_new_top:.5f} (ratio {c_ref_top / line_new_top:.4f})')
    try:
        sw = solve_one_cycle(ref, sol_ref, None)[0]
        say(f'   one guard-ON sweep from the reference: no raise; c(m_top)={float(sw.cFunc[0](M_TRIP, Cgrid[0])):.5f}')
    except ValueError as e:
        say('   one guard-ON sweep from the reference RAISED: ' + str(e)[:200])
    say('   warm-descent policy vs cold reference (state 0, C=1.0):')
    say('        m       c_warm      c_ref     rel.diff')
    for m in m_eval:
        cw = float(sol_warm.cFunc[0](m, 1.0)); cr = float(sol_ref.cFunc[0](m, 1.0))
        say(f'   {m:8.3f}  {cw:10.6f}  {cr:10.6f}  {(cw - cr) / cr:+.2e}')

if args.cold_egm:
    say(f'\n[E3] cold guard-ON EGM solve at beta_new={beta_new:.6f} from the constrained-PF terminal (the guard\'s premise)')
    a3 = make_atom(beta_new, b, dfs_new.pmv[b])
    a3.pre_solve()
    t0 = time.time()
    try:
        a3.solution = solve_agent(a3, False)
        c3 = float(a3.solution[0].cFunc[0](M_TRIP, Cgrid[0]))
        say(f'   converged: sweeps={a3.completed_cycles} distance={a3.solution_distance:.3e} wall={time.time() - t0:.1f}s; '
            f'c(m_top)={c3:.5f} vs line {line_new_top:.5f} (ratio {c3 / line_new_top:.4f})')
    except ValueError as e:
        say(f'   RAISED after {time.time() - t0:.1f}s: ' + str(e))

say(f'\n[done] total wall {time.time() - t_start:.1f}s')
