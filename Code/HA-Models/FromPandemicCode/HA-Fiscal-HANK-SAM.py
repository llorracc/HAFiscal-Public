import os
import sys

import numpy as np
from HARK.distributions import DiscreteDistribution
from ConsMarkovModel import MarkovConsumerType
from copy import deepcopy
from Parameters import return_parameters
import scipy.sparse as sp
import matplotlib.pyplot as plt
import time

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from matplotlib_config import show_plot


[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,\
DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,\
convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates, \
data_EducShares, max_recession_duration, num_experiment_periods,\
recession_changes, UI_changes, recession_UI_changes,\
TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes] = \
    return_parameters(Parametrization='Baseline',OutputFor='_Main.py')
      
mCount = 200
bigT = 300
aMax = 1_000_000
aCount = 200
states = 4 + 2

Rfree = np.ones(states)*1.01
LivPrb = [np.ones(states)*0.99375]
# H3 probe (dossier, plan 20260809-0006h): stash the main pipeline's
# education-specific PermGroFac ([G_g, unemp,...] built by
# return_parameters) BEFORE the historical flat-1.0 overwrites below;
# HAFISCAL_HANK_PERMGROFAC=main restores it (flag-gated A/B arm).
_pgf_main = [deepcopy(d.get("PermGroFac")) for d in (init_dropout, init_highschool, init_college)]
init_dropout["mCount"] = mCount
init_dropout["mFac"] = 3
init_dropout["mMin"] = 1e-4
init_dropout["mMax"] = 100000
init_dropout["PermGroFac"] = [np.ones(states)]
init_dropout['aXtraMax'] = aMax
init_dropout['aXtraCount'] = aCount
init_dropout['MrkvArray'] = init_highschool['MrkvArray'] # for now assume only one markov matrix
init_dropout['Rfree'] = [Rfree]  # HARK 0.17: time-vary list of per-state arrays
init_dropout['LivPrb'] = LivPrb 

init_highschool["mCount"] = mCount
init_highschool["mFac"] = 3
init_highschool["mMin"] = 1e-4
init_highschool["mMax"] = 100000
init_highschool["PermGroFac"] = [np.ones(states)]
init_highschool['aXtraMax'] = aMax
init_highschool['aXtraCount'] = aCount
init_highschool['Rfree'] = [Rfree]  # HARK 0.17: time-vary list of per-state arrays
init_highschool['LivPrb'] = LivPrb 

init_college["mCount"] = mCount
init_college["mFac"] = 3
init_college["mMin"] = 1e-4
init_college["mMax"] = 100000
init_college["PermGroFac"] = [np.ones(states)]
init_college['aXtraMax'] = aMax
init_college['aXtraCount'] = aCount
init_college['MrkvArray'] = init_highschool['MrkvArray'] # for now assume only one markov matrix
init_college['Rfree'] = [Rfree]  # HARK 0.17: time-vary list of per-state arrays
init_college['LivPrb'] = LivPrb

# BUG-073 (owner ruling 2026-08-09: "a clear bug"): the historical
# overwrite above discarded the PE calibration's education-specific
# growth structure while keeping beta-hats ESTIMATED UNDER that growth —
# at Gamma=1 the college top atoms sit past the growth-impatience bound
# and the household steady state the Jacobians are differentiated
# around inflates (A_ss 8.51 -> 20.47). Fix default ON (bug-fix class,
# both worlds); HAFISCAL_QE_FIDELITY=1 keeps the published Gamma=1 for
# exact reproduction; explicit "ones" = escape hatch.
_pgf_default = "ones" if os.environ.get("HAFISCAL_QE_FIDELITY", "") == "1" else "main"
if os.environ.get("HAFISCAL_HANK_PERMGROFAC", _pgf_default).strip().lower() in ("main", "1", "on"):
    for _init, _pgf in zip((init_dropout, init_highschool, init_college), _pgf_main):
        _init["PermGroFac"] = deepcopy(_pgf)
    print("[hank-h3] PermGroFac = main-pipeline education-specific values (BUG-073 fix)", flush=True)

num_mrkv = states





#%%



job_find = 2/3
EU_prob = 0.0306834
job_sep = EU_prob/ (1- job_find)


markov_array_ss = np.array([[ 1 - job_sep*(1 - job_find ), job_find, job_find, job_find , job_find , job_find],
       [job_sep*(1-job_find) , 0.        , 0.        , 0 ,  0, 0       ],
       [0.        , (1-job_find), 0.        , 0.  , 0.        , 0.       ],
       [0.        , 0, (1-job_find)        , 0.  , 0.        , 0.       ],
       [0.        , 0, 0.        , (1-job_find)  , 0.        , 0.       ],

       [0.        , 0. , 0 , 0       , (1-job_find), (1-job_find)]  ])

init_dropout['MrkvArray'] = [markov_array_ss.T]
init_highschool['MrkvArray'] = [markov_array_ss.T]

init_college['MrkvArray'] = [markov_array_ss.T]

mrkv_temp_for_will =markov_array_ss


            
eigen, ss_dstn = sp.linalg.eigs(mrkv_temp_for_will , k=1, which='LM')


ss_dstn = ss_dstn[:,0] / np.sum(ss_dstn[:,0]) # Steady state distribution of employed/unemployed 

ss_dstn = ss_dstn.real

U_ss = (1-ss_dstn[0])

N_ss = ss_dstn[0]

# def create_matrix_U(dx):
    
#     job_find_dx = job_find + dx
    

    
#     markov_array = np.array([[ 1 - job_sep*(1 - job_find_dx ), job_find_dx, job_find_dx, job_find_dx],
#            [job_sep*(1-job_find_dx) , 0.        , 0.        , 0.        ],
#            [0.        , (1-job_find_dx), 0.        , 0.        ],
#            [0.        , 0.        , (1-job_find_dx), (1-job_find_dx)]])


#     return markov_array



def create_matrix_U(dx):
    
    job_find_dx = job_find + dx
    

    
    markov_array = np.array([[ 1 - job_sep*(1 - job_find_dx ), job_find_dx, job_find_dx, job_find_dx , job_find_dx , job_find_dx],
           [job_sep*(1-job_find_dx) , 0.        , 0.        , 0 ,  0, 0       ],
           [0.        , (1-job_find_dx), 0.        , 0.  , 0.        , 0.       ],
           [0.        , 0, (1-job_find_dx)        , 0.  , 0.        , 0.       ],
           [0.        , 0, 0.        , (1-job_find_dx)  , 0.        , 0.       ],

           [0.        , 0. , 0 , 0       , (1-job_find_dx), (1-job_find_dx)]  ])


    return markov_array

dx = 0.0001


dstn = ss_dstn
UJAC = np.zeros((num_mrkv,bigT,bigT))

for s in range(bigT):
    for i in range(bigT):
        
        
        if i ==s:
            
            tranmat = create_matrix_U(dx)
            
    
            dstn = np.dot(tranmat,dstn)
    
        else:
            dstn = np.dot(mrkv_temp_for_will,dstn)
    
    
        UJAC[:,i,s] = (dstn - ss_dstn) / dx

plt.plot(UJAC[0].T[0])
plt.plot(UJAC[0].T[10])
plt.plot(UJAC[0].T[40])
plt.legend()
plt.xlim(-1,50)
show_plot()


#%%
agent_DO = MarkovConsumerType(**init_dropout)
agent_DO.cycles = 0
agent_HS = MarkovConsumerType(**init_highschool)
agent_HS.cycles = 0
agent_CG = MarkovConsumerType(**init_college)
agent_CG.cycles = 0
AggDemandEconomy = MarkovConsumerType(**init_ADEconomy)


# agent_DO.get_economy_data(AggDemandEconomy)
# agent_HS.get_economy_data(AggDemandEconomy)
# agent_CG.get_economy_data(AggDemandEconomy)


BaseTypeList = [agent_DO, agent_HS, agent_CG]
          




##################################################################################################
# Income distributions
IncShkDstn = []
IncShkDstn_transfers_dx = []

IncShkDstn_wage_dx = []
IncShkDstn_tax_dx = []

IncShkDstn_ui_extend_dx =[]
IncShkDstn_ui_rr_dx = []
tau_ss = 0.3 # steady state tax rate
wage_ss = 1.0

# HAF distributions
for ThisType in BaseTypeList:
    IncShkDstn_emp = deepcopy(ThisType.IncShkDstn[0])
    IncShkDstn_emp.atoms[1]  =IncShkDstn_emp.atoms[1]*wage_ss*(1-tau_ss)
    
    IncShkDstn_emp_dx = deepcopy(ThisType.IncShkDstn[0])
    IncShkDstn_emp_dx.atoms[1] = IncShkDstn_emp_dx.atoms[1] * (wage_ss + dx)* (1-tau_ss)


    IncShkDstn_emp_transfers_dx = deepcopy(ThisType.IncShkDstn[0])
    IncShkDstn_emp_transfers_dx.atoms[1] = IncShkDstn_emp_transfers_dx.atoms[1] * (wage_ss )* (1-tau_ss) + dx


    # quasi HAF unemp
    quasiHAFue = deepcopy(IncShkDstn_emp)
    quasiHAFue.atoms[0] = quasiHAFue.atoms[0] * 0 + 1.0
    quasiHAFue.atoms[1] = quasiHAFue.atoms[1] * 0 + 0.7*wage_ss*(1-tau_ss)
    
    quasiHAFue_dx = deepcopy(quasiHAFue)
    quasiHAFue_dx.atoms[1] = quasiHAFue_dx.atoms[1]  + dx

    # quasi HAF unemp
    quasiHAFue2 = deepcopy(IncShkDstn_emp)
    quasiHAFue2.atoms[0] = quasiHAFue2.atoms[0] * 0 + 1.0
    quasiHAFue2.atoms[1] = quasiHAFue2.atoms[1] * 0 + 0.7*wage_ss*(1-tau_ss)
    
    quasiHAFue2_dx = deepcopy(quasiHAFue2)
    quasiHAFue2_dx.atoms[1] = quasiHAFue2_dx.atoms[1] +dx

    quasiHAFuenb = deepcopy(IncShkDstn_emp)
    quasiHAFuenb.atoms[0] = quasiHAFue.atoms[0] * 0 + 1.0
    quasiHAFuenb.atoms[1] = quasiHAFue.atoms[1] * 0 + 0.5*wage_ss*(1-tau_ss)
    
    
    quasiHAFuenb2 = deepcopy(IncShkDstn_emp)
    quasiHAFuenb2.atoms[0] = quasiHAFuenb2.atoms[0] * 0 + 1.0
    quasiHAFuenb2.atoms[1] = quasiHAFuenb2.atoms[1] * 0 + 0.5*wage_ss*(1-tau_ss)
    
    
    quasiHAFuenb3 = deepcopy(IncShkDstn_emp)
    quasiHAFuenb3.atoms[0] = quasiHAFuenb3.atoms[0] * 0 + 1.0
    quasiHAFuenb3.atoms[1] = quasiHAFuenb3.atoms[1] * 0 + 0.5*wage_ss*(1-tau_ss)
    
    
    quasiHAFuenb_dx = deepcopy(quasiHAFuenb)
    # quasiHAFuenb_dx.atoms[0] = quasiHAFuenb_dx.atoms[0] * 0 + 1.0

    quasiHAFuenb_dx.atoms[1] = quasiHAFuenb_dx.atoms[1] + dx
    
    
    quasiHAFuenb2_dx = deepcopy(quasiHAFuenb)
    # quasiHAFuenb2_dx.atoms[0] = quasiHAFuenb2_dx.atoms[0] * 0 + 1.0

    quasiHAFuenb2_dx.atoms[1] = quasiHAFuenb2_dx.atoms[1] + dx
    
    
    quasiHAFuenb3_dx = deepcopy(quasiHAFuenb)
    # quasiHAFuenb3_dx.atoms[0] = quasiHAFuenb3_dx.atoms[0] * 0 + 1.0

    quasiHAFuenb3_dx.atoms[1] = quasiHAFuenb3_dx.atoms[1] + dx
    
    
    
    quasiHAFuenb1_UI_extend_dx = deepcopy(IncShkDstn_emp)
    quasiHAFuenb1_UI_extend_dx.atoms[0] = quasiHAFuenb1_UI_extend_dx.atoms[0] * 0 + 1.0
    quasiHAFuenb1_UI_extend_dx.atoms[1] = quasiHAFuenb1_UI_extend_dx.atoms[1] * 0 + 0.5*wage_ss*(1-tau_ss) + dx*wage_ss*(1-tau_ss) 
    

        
    quasiHAFuenb2_UI_extend_dx = deepcopy(IncShkDstn_emp)
    quasiHAFuenb2_UI_extend_dx.atoms[0] = quasiHAFuenb2_UI_extend_dx.atoms[0] * 0 + 1.0
    quasiHAFuenb2_UI_extend_dx.atoms[1] = quasiHAFuenb2_UI_extend_dx.atoms[1] * 0 + 0.5*wage_ss*(1-tau_ss) + dx*wage_ss*(1-tau_ss) 
    
    
    
        
    quasiHAFue1_UI_rr_dx = deepcopy(IncShkDstn_emp)
    quasiHAFue1_UI_rr_dx.atoms[0] = quasiHAFue1_UI_rr_dx.atoms[0] * 0 + 1.0
    quasiHAFue1_UI_rr_dx.atoms[1] = quasiHAFue1_UI_rr_dx.atoms[1] * 0 + 0.7*wage_ss*(1-tau_ss) + dx*wage_ss*(1-tau_ss) 
    

        
    quasiHAFue2_UI_rr_dx = deepcopy(IncShkDstn_emp)
    quasiHAFue2_UI_rr_dx.atoms[0] = quasiHAFue2_UI_rr_dx.atoms[0] * 0 + 1.0
    quasiHAFue2_UI_rr_dx.atoms[1] = quasiHAFue2_UI_rr_dx.atoms[1] * 0 + 0.7*wage_ss*(1-tau_ss) + dx*wage_ss*(1-tau_ss) 
    
    
    

    
    
    
    
    # IncShkDstn_emp = deepcopy(ThisType.IncShkDstn[0])
    IncShkDstn_emp_tax_dx = deepcopy(ThisType.IncShkDstn[0]) # tax jacobian 
    IncShkDstn_emp_tax_dx.atoms[1] = IncShkDstn_emp_tax_dx.atoms[1]*wage_ss*(1- ( tau_ss +dx))

    

    IncShkDstn.append([deepcopy(IncShkDstn_emp), deepcopy(quasiHAFue), deepcopy(quasiHAFue2), deepcopy(quasiHAFuenb), deepcopy(quasiHAFuenb2), deepcopy(quasiHAFuenb3)])
    
    
    IncShkDstn_transfers_dx.append([deepcopy(IncShkDstn_emp_transfers_dx), deepcopy(quasiHAFue_dx), deepcopy(quasiHAFue_dx), deepcopy(quasiHAFuenb_dx), deepcopy(quasiHAFuenb2_dx), deepcopy(quasiHAFuenb3_dx)])

    IncShkDstn_wage_dx.append([deepcopy(IncShkDstn_emp_dx), deepcopy(quasiHAFue), deepcopy(quasiHAFue2), deepcopy(quasiHAFuenb), deepcopy(quasiHAFuenb2), deepcopy(quasiHAFuenb3)])
    IncShkDstn_tax_dx.append([deepcopy(IncShkDstn_emp_tax_dx), deepcopy(quasiHAFue), deepcopy(quasiHAFue2), deepcopy(quasiHAFuenb), deepcopy(quasiHAFuenb2), deepcopy(quasiHAFuenb3)])


    IncShkDstn_ui_extend_dx.append([deepcopy(IncShkDstn_emp), deepcopy(quasiHAFue), deepcopy(quasiHAFue2), deepcopy(quasiHAFuenb1_UI_extend_dx), deepcopy(quasiHAFuenb2_UI_extend_dx), deepcopy(quasiHAFuenb3)])


    IncShkDstn_ui_rr_dx.append([deepcopy(IncShkDstn_emp), deepcopy(quasiHAFue1_UI_rr_dx), deepcopy(quasiHAFue2_UI_rr_dx), deepcopy(quasiHAFuenb), deepcopy(quasiHAFuenb2), deepcopy(quasiHAFuenb3)])


##################################################################################################

# BUG-071 fix (default OFF — adopting changes Section-5 outputs; owner
# ruling pending): the deepcopy-then-mutate-atoms pattern above leaves
# each distribution's xarray dataset STALE (deepcopy severs the
# atoms<->dataset aliasing), and HARK's labeled expected() — every
# household solve — reads the DATASET, i.e. the PRE-scaling shocks.
# Re-labeling rebuilds each distribution from its mutated atoms so both
# views carry the intended (net-wage-scaled, quasi-HAF) values.
def _relabel_dstn(d):
    from HARK.distributions import DiscreteDistributionLabeled
    return DiscreteDistributionLabeled(
        pmv=np.asarray(d.pmv), atoms=np.asarray(d.atoms),
        var_names=["PermShk", "TranShk"])


# H3 probe (dossier): main-pipeline unemployment permanent shocks — the
# historical construction kills psi during unemployment (atoms[0]=1),
# while the main pipeline's default keeps the employed psi marginal.
# Flag-gated A/B arm; applied in place BEFORE the BUG-071 relabel pass
# so the labeled views rebuild from the mutated atoms.
if os.environ.get("HAFISCAL_HANK_UNEMP_PSI", "one").strip().lower() in ("main", "1", "on"):
    for _lst in (IncShkDstn, IncShkDstn_transfers_dx, IncShkDstn_wage_dx,
                 IncShkDstn_tax_dx, IncShkDstn_ui_extend_dx, IncShkDstn_ui_rr_dx):
        for _e in range(len(_lst)):
            _emp_psi = np.asarray(IncShkDstn[_e][0].atoms[0], dtype=np.float64).copy()
            for _s in range(1, len(_lst[_e])):
                _lst[_e][_s].atoms[0][:] = _emp_psi
    print("[hank-h3] unemployment psi = employed marginal (main-pipeline semantics)", flush=True)

# Owner ruling R1 (2026-08-08): BUG-071 fix ADOPTED as the default — it is
# a bug-fix-class change (the solves now see the calibration the script
# and Section 5 specify), so it is ON in the default AND as-corrected
# worlds. RECLASSIFIED 2026-08-28: BUG-071 is a bug of the NEW machinery
# (on HARK 0.14.1 the published code solved on the correct, rescaled
# shocks -- the stale xarray view is a 0.17 property), so exact published
# reproduction needs the fix ON as well: QE-fidelity no longer defaults it
# off (it did until 2026-08-28; the Econ-9 ladder overrode it explicitly).
# HAFISCAL_STEP4_SHOCK_FIX=0 is the explicit historical-0.17-arm escape.
_shock_fix_default = "1"
if os.environ.get("HAFISCAL_STEP4_SHOCK_FIX",
                  _shock_fix_default).strip().lower() in ("1", "on", "true"):
    print("[step4-shock-fix] BUG-071 fix ON: re-labeling mutated income "
          "distributions so solves see the intended (scaled) shocks",
          flush=True)
    for _lst in (IncShkDstn, IncShkDstn_transfers_dx, IncShkDstn_wage_dx,
                 IncShkDstn_tax_dx, IncShkDstn_ui_extend_dx,
                 IncShkDstn_ui_rr_dx):
        for _i in range(len(_lst)):
            _lst[_i] = [_relabel_dstn(_d) for _d in _lst[_i]]


_FASTBACK_MODS = None


def _fast_backward_mods():
    """L3b lazy loader (plan 20260808-1638h): returns (backward_kernel,
    fast_tranmat) when HAFISCAL_STEP4_FAST_BACKWARD is enabled and the
    modules import; None otherwise (python path). Default ON by the
    2026-08-09 flip ruling — EXCEPT under HAFISCAL_QE_FIDELITY=1 (L4
    freeze, 2026-08-09): the kernel lane is equivalence-class (~1e-15
    reduction order), not bitwise, so the QE-fidelity engine defaults to
    the certified python path to keep published reproduction
    bit-for-bit. Explicit HAFISCAL_STEP4_FAST_BACKWARD always wins."""
    global _FASTBACK_MODS
    _fb_default = "0" if os.environ.get("HAFISCAL_QE_FIDELITY", "") == "1" else "1"
    if os.environ.get("HAFISCAL_STEP4_FAST_BACKWARD", _fb_default).strip().lower() in ("0", "off", "false"):
        return None
    if _FASTBACK_MODS is None:
        try:
            import sys as _s
            _p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            if _p not in _s.path:
                _s.path.insert(0, _p)
            import step4_backward_kernel as _bk
            import step4_fast_tranmat as _ft
            _FASTBACK_MODS = (_bk, _ft)
            print("[fast_backward] L3b compiled backward pass ACTIVE")
        except Exception as _e:
            print(f"[fast_backward] unavailable ({type(_e).__name__}: {_e}); python path")
            _FASTBACK_MODS = False
    return _FASTBACK_MODS or None


def prepare_type_base(agent, dict, DiscFac, IncDist):
    """L1 hoist (plan 20260808-1638h): everything here depends only on
    (educ-type agent, DiscFac, IncDist) — never on the shock param — so it
    is computed ONCE per (educ, beta) and shared across all 8 params: the
    SS solve, the finite-horizon params dict, and the baseline-solved
    zeroth-column agent (its SOLVE is param-independent; only its
    transition matrices vary by param and are rebuilt per param)."""
    agent_SS = deepcopy(agent)
    agent_SS.IncShkDstn = deepcopy(IncDist)
    agent_SS.DiscFac = DiscFac
    agent_SS.compute_steady_state()

    params = deepcopy(dict)
    params["T_cycle"] = bigT
    params["LivPrb"] = params["T_cycle"] * [agent_SS.LivPrb[0]]
    params["PermGroFac"] = params["T_cycle"] * [agent_SS.PermGroFac[0]]
    params["PermShkStd"] = params["T_cycle"] * [agent_SS.PermShkStd[0]]
    params["TranShkStd"] = params["T_cycle"] * [agent_SS.TranShkStd[0]]
    params["Rfree"] = params["T_cycle"] * [agent_SS.Rfree[0]]  # [0]: same time-vary idiom as the neighboring lines
    params["MrkvArray"] = params["T_cycle"] * agent_SS.MrkvArray
    params["DiscFac"] = DiscFac
    params["cycles"] = 1

    Zeroth_col_agent = MarkovConsumerType(**deepcopy(params))
    Zeroth_col_agent.solution_terminal = deepcopy(agent_SS.solution[0])
    Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
    zeroth_policies = None
    _fbm = _fast_backward_mods()
    if _fbm is not None:
        Zeroth_col_agent.neutral_measure = True
        Zeroth_col_agent.define_distribution_grid()
        zeroth_policies = _fbm[0].fast_backward(Zeroth_col_agent)
    if zeroth_policies is None:
        Zeroth_col_agent.solve()

    # L1b: the finite-horizon agent's CONSTRUCTION is also param-independent
    # (the constructor rebuilds 300 income dstns, ~1.6 s) — construct once,
    # snapshot the fields the per-param branches rebind or mutate in place
    # (time_inv/time_vary via del_from_time_inv/add_to_time_vary), and
    # restore per param before applying that param's perturbation.
    FinHorizonAgent = MarkovConsumerType(**deepcopy(params))
    FinHorizonAgent.solution_terminal = deepcopy(agent_SS.solution[0])
    fh_snap = (list(FinHorizonAgent.time_inv), list(FinHorizonAgent.time_vary),
               FinHorizonAgent.MrkvArray, FinHorizonAgent.Rfree,
               FinHorizonAgent.DiscFac)

    return {"agent": agent, "agent_SS": agent_SS, "params": params,
            "Zeroth_col_agent": Zeroth_col_agent,
            "zeroth_policies": zeroth_policies,
            "FinHorizonAgent": FinHorizonAgent, "fh_snap": fh_snap,
            "DiscFac": DiscFac}


def compute_type_jacobian(agent, dict, DiscFac, IncDist, IncDist_dx, param):
    """Legacy single-call API: prepare + one param (pre-L1 equivalent)."""
    base = prepare_type_base(agent, dict, DiscFac, IncDist)
    return compute_type_jacobian_for_param(base, IncDist, IncDist_dx, param)


def _zeroth_direct_column(base, IncDist, IncDist_dx, param, agent_inc_dx):
    """BUG-072 fix (dossier H6, plan 20260809-0006h): the historical
    zeroth-column agent SOLVED AT BASELINE and put the perturbation only
    into the slot-0 transition matrices, omitting the date-0 behavioral
    response for every instrument (probe: DiscFac column identically 0
    vs true 0.105; Rfree missing >half; transfers off by 26.6% of
    J-scale — and the GE transfers experiment is a date-0-only shock).
    This computes the TRUE direct s=0 column: solve WITH the slot-0
    perturbation (dated policies), dated transitions, and aggregation
    under the pipeline convention J[t,0] = direct_pre[t+1]. Columns
    s>=1 are unaffected (the fake-news recursion seeds from its own
    internal column, not this overwrite)."""
    agent = base["agent"]
    agent_SS = base["agent_SS"]
    DiscFac = base["DiscFac"]
    params = deepcopy(base["params"])
    T = params["T_cycle"]
    dxv = 0.0001

    fd = MarkovConsumerType(**params)
    fd.dist_pGrid = T * [np.array([1])]
    fd.solution_terminal = deepcopy(agent_SS.solution[0])
    fd.del_from_time_inv("IncShkDstn")
    fd.IncShkDstn = T * deepcopy(IncDist)
    fd.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        fd.IncShkDstn = deepcopy(IncDist_dx) + (T - 1) * deepcopy(IncDist)
    elif param == "Rfree":
        fd.del_from_time_inv("Rfree")
        fd.add_to_time_vary("Rfree")
        fd.Rfree = [agent.Rfree[0] + dxv] + (T - 1) * [agent.Rfree[0]]
    elif param == "job_find":
        fd.MrkvArray = [create_matrix_U(dxv).T] + (T - 1) * agent.MrkvArray
    elif param == "DiscFac":
        fd.del_from_time_inv("DiscFac")
        fd.add_to_time_vary("DiscFac")
        fd.DiscFac = [DiscFac + dxv] + (T - 1) * [DiscFac]
    # Z2 of plan 20260809-0936h: route this helper through the L3b
    # compiled stack when available (it originally python-solved,
    # costing ~10 min/run); certified python fallback preserved.
    _fbm_z = _fast_backward_mods()
    _solve_dstn_z = fd.IncShkDstn
    if _fbm_z is None:
        fd.solve()

    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        fd.IncShkDstn = (deepcopy(agent_inc_dx.IncShkDstn)
                         + (T - 1) * deepcopy(agent_SS.IncShkDstn))
    else:
        fd.IncShkDstn = T * deepcopy(agent_SS.IncShkDstn)
    fd.neutral_measure = True
    fd.define_distribution_grid()
    _done_fast = False
    if _fbm_z is not None:
        _pol_z = _fbm_z[0].fast_backward(fd, shk_dstn=_solve_dstn_z)
        _tm_z = (_fbm_z[1].finite_tranmat_from_policies(
                     fd, fd.IncShkDstn, _pol_z[0], _pol_z[1])
                 if _pol_z is not None else None)
        if _tm_z is not None:
            tran_t = np.array(_tm_z)
            c_t = _pol_z[0].reshape(T, -1)
            a_t = _pol_z[1].reshape(T, -1)
            _done_fast = True
        else:
            print("[fast_backward] zeroth-direct fallback to certified python path")
            _neutral_z = fd.IncShkDstn
            fd.IncShkDstn = _solve_dstn_z
            fd.solve()
            fd.IncShkDstn = _neutral_z
    if not _done_fast:
        fd.calc_transition_matrix()
        tran_t = np.array(fd.tran_matrix)
        c_t = np.array([np.asarray(fd.cPol_Grid[t]).flatten() for t in range(T)])
        a_t = np.array([np.asarray(fd.aPol_Grid[t]).flatten() for t in range(T)])
    C_pre = np.zeros(T)
    A_pre = np.zeros(T)
    d = agent_SS.vec_erg_dstn
    for t in range(T):
        C_pre[t] = np.dot(c_t[t], d)[0]
        A_pre[t] = np.dot(a_t[t], d)[0]
        d = np.dot(tran_t[t], d)
    dC = (C_pre - agent_SS.C_ss) / dxv
    dA = (A_pre - agent_SS.A_ss) / dxv
    colC = np.empty(T); colC[:T - 1] = dC[1:]; colC[T - 1] = 0.0
    colA = np.empty(T); colA[:T - 1] = dA[1:]; colA[T - 1] = 0.0
    return colC, colA


def compute_type_jacobian_for_param(base, IncDist, IncDist_dx, param):
    dx = 0.0001

    agent = base["agent"]
    agent_SS = base["agent_SS"]
    DiscFac = base["DiscFac"]

    C_ss_ThisType = deepcopy(agent_SS.C_ss)
    A_ss_ThisType = deepcopy(agent_SS.A_ss)
    
    c = agent_SS.cPol_Grid
    a = agent_SS.aPol_Grid

    ##################################################################################################
    # Finite Horizon

    params = deepcopy(base["params"])  # per-param isolation, as the legacy per-call rebuild had

    # L1b: persistent finite-horizon agent — restore the fresh-construction
    # state the branches below perturb, then proceed exactly as before.
    FinHorizonAgent = base["FinHorizonAgent"]
    _ti0, _tv0, _mrkv0, _rfree0, _discfac0 = base["fh_snap"]
    FinHorizonAgent.time_inv = list(_ti0)
    FinHorizonAgent.time_vary = list(_tv0)
    FinHorizonAgent.MrkvArray = _mrkv0
    FinHorizonAgent.Rfree = _rfree0
    FinHorizonAgent.DiscFac = _discfac0
    FinHorizonAgent.neutral_measure = False
    FinHorizonAgent.dist_pGrid = params["T_cycle"] * [np.array([1])]
    FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)

    if param == "transfers":
        agent_inc_dx = deepcopy(agent)
        agent_inc_dx.DiscFac = DiscFac
        agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
        agent_inc_dx.neutral_measure = True
        agent_inc_dx.harmenberg_income_process()
        FinHorizonAgent.del_from_time_inv(
            "IncShkDstn",
        )
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(IncDist) + deepcopy(IncDist_dx)
        FinHorizonAgent.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
        
        
    elif param =='wage' or param =='tax' or param =='UI_extend' or param =='UI_rr':
        
        agent_inc_dx = deepcopy(agent)
        agent_inc_dx.DiscFac = DiscFac
        agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
        agent_inc_dx.neutral_measure = True
        agent_inc_dx.harmenberg_income_process()
        FinHorizonAgent.del_from_time_inv(
            "IncShkDstn",
        )
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(IncDist) + deepcopy(IncDist_dx)
        FinHorizonAgent.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
        
        
    elif param == "job_find":
        Mrkv_dx = deepcopy(agent.MrkvArray[0])
        
        
        
        # Mrkv_dx[0][0] = Mrkv_dx[0][0] + dx
        # Mrkv_dx[1][0] = Mrkv_dx[1][0] + dx
        # Mrkv_dx[2][0] = Mrkv_dx[2][0] + dx
        # Mrkv_dx[3][0] = Mrkv_dx[3][0] + dx

        # Mrkv_dx[0][1] = Mrkv_dx[0][1] - dx
        # Mrkv_dx[1][2] = Mrkv_dx[1][2] - dx
        # Mrkv_dx[2][3] = Mrkv_dx[2][3] - dx
        # Mrkv_dx[3][3] = Mrkv_dx[3][3] - dx
        
        Mrkv_dx = create_matrix_U(dx).T
        
        
        FinHorizonAgent.MrkvArray = (params["T_cycle"] - 1) * agent.MrkvArray + [Mrkv_dx]
    elif param == "Rfree":
        FinHorizonAgent.del_from_time_inv(
            "Rfree",
        )  # delete Rfree from time invariant list since it varies overtime
        FinHorizonAgent.add_to_time_vary("Rfree")
        FinHorizonAgent.Rfree = (params["T_cycle"] - 1) * [agent.Rfree[0]] + [agent.Rfree[0] + dx] + [agent.Rfree[0]]  # [0]: per-state array per period (HARK 0.17 time-vary)
    elif param == "DiscFac":
        FinHorizonAgent.del_from_time_inv(
            "DiscFac",
        )  # delete Rfree from time invariant list since it varies overtime
        FinHorizonAgent.add_to_time_vary("DiscFac")
        FinHorizonAgent.DiscFac = (params["T_cycle"] - 1) * [DiscFac] + [DiscFac + dx]

    _fbm = _fast_backward_mods()
    if _fbm is not None:
        _solve_dstn = FinHorizonAgent.IncShkDstn  # raw solve-arm dstns (dx slot placement)
    else:
        FinHorizonAgent.solve()

    if param == "transfers" or param =='wage' or param =='tax'or param =='UI_extend' or param =='UI_rr':
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(agent_SS.IncShkDstn) + deepcopy(agent_inc_dx.IncShkDstn)


    else:
        FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)

    # Calculate Transition Matrices
    FinHorizonAgent.neutral_measure = True
    # FinHorizonAgent.harmenberg_income_process()
    FinHorizonAgent.define_distribution_grid()
    if _fbm is not None:
        _pol = _fbm[0].fast_backward(FinHorizonAgent, shk_dstn=_solve_dstn)
        _tm = (_fbm[1].finite_tranmat_from_policies(
                   FinHorizonAgent, FinHorizonAgent.IncShkDstn, _pol[0], _pol[1])
               if _pol is not None else None)
        if _tm is None:
            print("[fast_backward] FH fallback to certified python path")
            _neutral = FinHorizonAgent.IncShkDstn
            FinHorizonAgent.IncShkDstn = _solve_dstn
            FinHorizonAgent.solve()
            FinHorizonAgent.IncShkDstn = _neutral
            FinHorizonAgent.calc_transition_matrix()
        else:
            FinHorizonAgent.cPol_Grid = _pol[0]
            FinHorizonAgent.aPol_Grid = _pol[1]
            FinHorizonAgent.tran_matrix = _tm
    else:
        FinHorizonAgent.calc_transition_matrix()

    ##################################################################################################
    # period zero shock agent — L1: SOLVED once in prepare_type_base (the
    # solve is baseline for every param). Reset the perturbable fields
    # that fresh construction used to provide (state must not leak across
    # params: job_find sets MrkvArray, Rfree/DiscFac set theirs, and every
    # branch below assigns IncShkDstn), then rebuild this param's
    # transition matrices.

    Zeroth_col_agent = base["Zeroth_col_agent"]
    Zeroth_col_agent.MrkvArray = params["MrkvArray"]
    Zeroth_col_agent.Rfree = params["Rfree"]
    Zeroth_col_agent.DiscFac = params["DiscFac"]

    if param == "transfers" or param =='wage' or param =='tax' or param =='UI_extend' or param =='UI_rr':
        Zeroth_col_agent.IncShkDstn = deepcopy(agent_inc_dx.IncShkDstn) + (params["T_cycle"]) * deepcopy(agent_SS.IncShkDstn)
    elif param == "job_find":
        Zeroth_col_agent.MrkvArray = [Mrkv_dx] + (params["T_cycle"] - 1) * agent.MrkvArray
    elif param == "Rfree":
        Zeroth_col_agent.Rfree = [agent.Rfree[0] + dx] + (params["T_cycle"] - 1) * [agent.Rfree[0]]  # [0]: per-state array per period (HARK 0.17 time-vary)
    elif param == "DiscFac":
        Zeroth_col_agent.DiscFac = [DiscFac + dx] + (params["T_cycle"] - 1) * [DiscFac]
        
        
    # if param != "IncShkDstn" or param =! "wage" or param =!"tax":
    #     Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)
  
            
    if param == "DiscFac" or param == "Rfree" or param =="job_find":
        Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)
  


    Zeroth_col_agent.neutral_measure = True
    Zeroth_col_agent.define_distribution_grid()
    if _fbm is not None and base.get("zeroth_policies") is not None:
        _zc, _za = base["zeroth_policies"]
        _tmz = _fbm[1].finite_tranmat_from_policies(
            Zeroth_col_agent, Zeroth_col_agent.IncShkDstn, _zc, _za)
        if _tmz is None:
            print("[fast_backward] zeroth fallback to certified python path")
            if not getattr(Zeroth_col_agent, "solution", None):
                _cur = Zeroth_col_agent.IncShkDstn
                Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
                Zeroth_col_agent.solve()
                Zeroth_col_agent.IncShkDstn = _cur
            Zeroth_col_agent.calc_transition_matrix()
        else:
            Zeroth_col_agent.tran_matrix = _tmz
    else:
        Zeroth_col_agent.calc_transition_matrix()

    #################################################################################################
    # calculate Jacobian

    D_ss = agent_SS.vec_erg_dstn

    c_ss = agent_SS.cPol_Grid.flatten()
    a_ss = agent_SS.aPol_Grid.flatten()

    c_t_unflat = FinHorizonAgent.cPol_Grid
    a_t_unflat = FinHorizonAgent.aPol_Grid

    A_ss = agent_SS.A_ss
    C_ss = agent_SS.C_ss
    
    transition_matrices = FinHorizonAgent.tran_matrix

    c_t_flat = np.zeros((params["T_cycle"], int(params["mCount"] * states)))
    a_t_flat = np.zeros((params["T_cycle"], int(params["mCount"] * states)))

    for t in range( params["T_cycle"] ):
        c_t_flat[t] = c_t_unflat[t].flatten()
        a_t_flat[t] = a_t_unflat[t].flatten()

    tranmat_ss = agent_SS.tran_matrix

    # L1b: preallocate instead of np.insert — the insert materialized a
    # second (T+1, N, N) copy (~1.2 GB at mCount*states=720) per param.
    tranmat_t = np.empty((params["T_cycle"] + 1,) + np.shape(tranmat_ss),
                         dtype=np.asarray(tranmat_ss).dtype)
    tranmat_t[:params["T_cycle"]] = transition_matrices
    tranmat_t[params["T_cycle"]] = tranmat_ss

    c_t = np.empty((params["T_cycle"] + 1, c_t_flat.shape[1]), dtype=c_t_flat.dtype)
    c_t[:params["T_cycle"]] = c_t_flat
    c_t[params["T_cycle"]] = c_ss
    a_t = np.empty((params["T_cycle"] + 1, a_t_flat.shape[1]), dtype=a_t_flat.dtype)
    a_t[:params["T_cycle"]] = a_t_flat
    a_t[params["T_cycle"]] = a_ss

    CJAC_perfect, AJAC_perfect = compile_JAC(a_ss, c_ss, a_t, c_t, tranmat_ss, tranmat_t, D_ss, C_ss, A_ss, Zeroth_col_agent, bigT)

    # BUG-072 fix (owner-adopted 2026-08-09): replace the s=0 column with
    # the direct dated-policy experiment — the historical zeroth agent
    # solved at baseline and omitted the date-0 behavioral response
    # (DiscFac column identically zero; Rfree missing more than half).
    # Columns s>=1 are provably unaffected. Default ON (bug-fix class,
    # both worlds); HAFISCAL_QE_FIDELITY=1 keeps the historical column
    # for exact published reproduction; explicit 0 = escape hatch.
    _zeroth_default = "0" if os.environ.get("HAFISCAL_QE_FIDELITY", "") == "1" else "1"
    if os.environ.get("HAFISCAL_STEP4_ZEROTH_FIX", _zeroth_default).strip().lower() in ("1", "on", "true"):
        _inc_dx = agent_inc_dx if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr") else None
        _colC, _colA = _zeroth_direct_column(base, IncDist, IncDist_dx, param, _inc_dx)
        CJAC_perfect.T[0] = _colC
        AJAC_perfect.T[0] = _colA

    return CJAC_perfect, AJAC_perfect, C_ss_ThisType, A_ss_ThisType



##################################################################################################

def compile_JAC(a_ss, c_ss, a_t, c_t, tranmat_ss, tranmat_t, D_ss, C_ss, A_ss, Zeroth_col_agent, bigT):

    T = bigT

    # Expectation vectors
    exp_vecs_a_e = []
    exp_vec_a_e = a_ss
    
    exp_vecs_c_e = []
    exp_vec_c_e = c_ss
    
    for i in range(T):
        
        exp_vecs_a_e.append(exp_vec_a_e)
        exp_vec_a_e = np.dot(tranmat_ss.T, exp_vec_a_e)
        
        exp_vecs_c_e.append(exp_vec_c_e)
        exp_vec_c_e = np.dot(tranmat_ss.T, exp_vec_c_e)
    
    
    exp_vecs_a_e = np.array(exp_vecs_a_e)
    exp_vecs_c_e = np.array(exp_vecs_c_e)

    
    da0_s = []
    dc0_s = []

    for i in range(T):
        da0_s.append(a_t[T - i] - a_ss)
        dc0_s.append(c_t[T - i] - c_ss)
    
        
    da0_s = np.array(da0_s)
    dc0_s = np.array(dc0_s)

    dA0_s = []
    dC0_s = []

    for i in range(T):
        dA0_s.append(np.dot(da0_s[i], D_ss))
        dC0_s.append(np.dot(dc0_s[i], D_ss))
    
    dA0_s = np.array(dA0_s)
    A_curl_s = dA0_s/dx
    
    dC0_s = np.array(dC0_s)
    C_curl_s = dC0_s/dx
    
    # Step-4 cure Lane A (plan 20260808-1030h): identical per-element
    # arithmetic to the historical two-loop form ((tranmat_t - tranmat_ss)
    # then @ D_ss), but WITHOUT materializing the (T, N, N) dlambda0_s
    # array it fed — ~1.5 GB per call whose only consumer was this dot.
    dD0_s = []

    for i in range(T):
        dD0_s.append(np.dot(tranmat_t[T - i] - tranmat_ss, D_ss))

    dD0_s = np.array(dD0_s)
    D_curl_s = dD0_s/dx
    
    Curl_F_A = np.zeros((T , T))
    Curl_F_C = np.zeros((T , T))
    
    # WARNING: SWAPPED THESE LINES TO MAKE DEMO RUN
    # Curl_F_A[0] = A_curl_s
    # Curl_F_C[0] = C_curl_s
    Curl_F_A[0] = A_curl_s.T[0]
    Curl_F_C[0] = C_curl_s.T[0]

    # Step-4 cure Lane A: the historical (T-1)xT python loop of scalar
    # np.dot calls (~90k interpreter dispatches, ~1.3 s/call) is ONE
    # matrix product: Curl_F[i+1, j] = exp_vecs[i] . D_curl_s[j].
    D_curl_mat = D_curl_s.reshape(T, -1)              # (T, N)
    Curl_F_A[1:, :] = exp_vecs_a_e.reshape(T, -1)[:T - 1] @ D_curl_mat.T
    Curl_F_C[1:, :] = exp_vecs_c_e.reshape(T, -1)[:T - 1] @ D_curl_mat.T

    # L1b: the fake-news recursion J[t,s] = J[t-1,s-1] + F[t,s] runs down
    # each diagonal independently, so it IS a cumsum along diagonals —
    # np.cumsum accumulates in the same sequential order as the old 90k-
    # iteration python double loop (bitwise-identical results, ~1 s/param
    # of interpreter dispatch removed).
    J_A = np.empty((T, T))
    J_C = np.empty((T, T))
    for k in range(T):  # diagonals starting at (0, k)
        idx = np.arange(T - k)
        J_A[idx, idx + k] = np.cumsum(Curl_F_A[idx, idx + k])
        J_C[idx, idx + k] = np.cumsum(Curl_F_C[idx, idx + k])
    for k in range(1, T):  # diagonals starting at (k, 0)
        idx = np.arange(T - k)
        J_A[idx + k, idx] = np.cumsum(Curl_F_A[idx + k, idx])
        J_C[idx + k, idx] = np.cumsum(Curl_F_C[idx + k, idx])
     
    # Zeroth Column of the Jacobian
    Zeroth_col_agent.tran_matrix = np.array(Zeroth_col_agent.tran_matrix)
    
    C_t = np.zeros(T)
    A_t = np.zeros(T)
    
    dstn_dot = D_ss
    
    for t in range(T):
        tran_mat_t = Zeroth_col_agent.tran_matrix[t]

        dstn_all = np.dot(tran_mat_t, dstn_dot)

        C = np.dot(c_ss, dstn_all)
        A = np.dot(a_ss, dstn_all)
        
        C_t[t] = C[0]
        A_t[t] = A[0]

        dstn_dot = dstn_all
        
    J_A.T[0] = (A_t - A_ss) / dx
    J_C.T[0] = (C_t - C_ss) / dx

    return J_C, J_A

dicts = [init_dropout, init_highschool, init_college]
shock_params = ["transfers", "Rfree", "wage" , "tax", "job_find", "DiscFac", "UI_extend" , "UI_rr"]

CJacs = []
AJacs = []
C_sss = []
A_sss = []


num_educ_types = 3
num_discfacs = 7
num_education_types = 3



CJAC_all = np.zeros((num_educ_types,  len(DiscFacDstns[0].atoms[0]) , len(shock_params) , bigT , bigT ))
AJAC_all = np.zeros((num_educ_types,  len(DiscFacDstns[0].atoms[0]) , len(shock_params) , bigT , bigT ))

C_ss_all = np.zeros((num_educ_types,  len(DiscFacDstns[0].atoms[0]) , len(shock_params)))
A_ss_all = np.zeros((num_educ_types,  len(DiscFacDstns[0].atoms[0]) , len(shock_params)))

start = time.time()

for e in range(num_educ_types): #education type
    betas = DiscFacDstns[e].atoms[0]
    dict = dicts[e]
    IncDist = [IncShkDstn[e]]
    # IncDist_dx = [IncShkDstn_dx[e]]
    for d,beta in enumerate(betas):
        base = prepare_type_base(BaseTypeList[e], dict, beta, IncDist)  # L1 hoist: 1 SS + 1 zeroth solve per (e,beta), not 8
        for s,param in enumerate(shock_params):
            
            if param=='wage':
                IncDist_dx = [IncShkDstn_wage_dx[e]]
                
            elif param =='tax':
                IncDist_dx = [IncShkDstn_tax_dx[e]]
            
            elif param=='transfers':
                
                IncDist_dx = [IncShkDstn_transfers_dx[e]]
            elif param =='UI_extend':
                
                IncDist_dx = [IncShkDstn_ui_extend_dx[e]]
                
            elif param =='UI_rr':
                
                IncDist_dx = [IncShkDstn_ui_rr_dx[e]]


            else:    
                IncDist_dx = [IncShkDstn[e]]

                
                
                

            print(BaseTypeList[e])

            CJac, AJac, C_ss, A_ss = compute_type_jacobian_for_param(base, IncDist, IncDist_dx, param)
            
            # if d == 6:
                
            #     plt.plot(CJac.T[30])
            #     plt.show()
            
            
            # if  param == "UI_extend" or param == 'UI_rr':
                
            #     plt.plot(CJac.T[0])
            #     plt.plot(CJac.T[30])
            #     plt.title(param)
            #     plt.show()
                
            CJAC_all[e,d,s] = CJac
            AJAC_all[e,d,s] = AJac
            
            C_ss_all[e,d,s] = C_ss
            A_ss_all[e,d,s] = A_ss
            


print('time taken to compute all jacobians' , time.time() - start)


#%%
plt.plot(CJAC_all[1,-1,1].T[30])
plt.plot(np.zeros(bigT))
show_plot()

#%%
weights_of_educ_types = [0.093, 0.527, 0.38]


def compute_average_aggregates(C_ss_all, A_ss_all):
    
    C_ss_final = 0
    A_ss_final = 0

    
    
    for d in range(len(DiscFacDstns[0].atoms[0])): # discount factor
        
        for e in range(num_educ_types): # education type
            
            C_ss_final += weights_of_educ_types[e]*C_ss_all[e,d,0]/num_discfacs
            A_ss_final += weights_of_educ_types[e]*A_ss_all[e,d,0]/num_discfacs
            
    return C_ss_final,A_ss_final


def compute_average_JAC(CJAC,AJAC):
    
    CJAC_weighted_avg = np.zeros((len(shock_params),bigT,bigT))
    AJAC_weighted_avg = np.zeros((len(shock_params),bigT,bigT))
    

    
    
    for s in range(len(shock_params)): # shock type
            
        for d in range(len(DiscFacDstns[0].atoms[0])): # discount factor
            
            for e in range(num_educ_types): # education type
                                
                CJAC_weighted_avg[s] += weights_of_educ_types[e]*CJAC[e,d,s]/num_discfacs
                AJAC_weighted_avg[s] += weights_of_educ_types[e]*AJAC[e,d,s]/num_discfacs

                
    return CJAC_weighted_avg,AJAC_weighted_avg 
           


            

CJACs_weighted, AJACs_weighted = compute_average_JAC(CJAC_all,AJAC_all)
C_ss_sim , A_ss_sim = compute_average_aggregates(C_ss_all , A_ss_all)
    
print(C_ss,A_ss)

#%%

def compute_average_JAC_by_educ(CJAC,AJAC):
    
    CJAC_weighted_avg = np.zeros((len(shock_params),num_educ_types,bigT,bigT))
    AJAC_weighted_avg = np.zeros((len(shock_params),num_educ_types,bigT,bigT))
    

    
    
    for s in range(len(shock_params)): # shock type
            
        for d in range(len(DiscFacDstns[0].atoms[0])): # discount factor
            
            for e in range(num_educ_types): # education type
                                
                CJAC_weighted_avg[s,e] += CJAC[e,d,s]/num_discfacs
                AJAC_weighted_avg[s,e] += AJAC[e,d,s]/num_discfacs

                
    return CJAC_weighted_avg,AJAC_weighted_avg 
            

CJACs_weighted_by_educ, AJACs_weighted_by_educ  = compute_average_JAC_by_educ(CJAC_all,AJAC_all)
#%%
    

    

    
    
plt.plot(CJACs_weighted[1].T[30])
show_plot()


shock_params = ["transfers" , "r", "w" , "tau", "eta","DiscFac" , "UI_extend", "UI_rr" ]


CJAC_dict_temp = {}
AJAC_dict_temp = {}

CJAC_dict_educ_temp = {}
AJAC_dict_educ_temp = {}

for i,shk in enumerate(shock_params):
    
    CJAC_dict_temp[shk] = deepcopy(CJACs_weighted[i])
    AJAC_dict_temp[shk] = deepcopy(AJACs_weighted[i])

education_groups = ['dropout' , 'highschool',  'college']

for e,educ in enumerate(education_groups):
    
    
    CJAC_dict_temp_i = {}
    AJAC_dict_temp_i = {}

    
    

    for i,shk in enumerate(shock_params):
    
        
        CJAC_dict_temp_i[shk] = deepcopy(CJACs_weighted_by_educ[i,e])
        AJAC_dict_temp_i[shk] = deepcopy(AJACs_weighted_by_educ[i,e])
    

    CJAC_dict_educ_temp[educ] = deepcopy(CJAC_dict_temp_i)
    AJAC_dict_educ_temp[educ] = deepcopy(AJAC_dict_temp_i)


#%%

import pickle

Obj = {'C' :CJAC_dict_temp , 'A': AJAC_dict_temp , 'C_by_educ':  CJAC_dict_educ_temp , 'A_by_educ':  AJAC_dict_educ_temp ,
       # H4 (plan 20260809-0006h): emit the education-and-beta-weighted
       # steady-state aggregates this stage already computes (previously
       # discarded) so the GE stage can consume them instead of its
       # hardcoded C_ss_sim/A_ss_sim literals. Schema-ADDITIVE: every
       # existing consumer hard-indexes only the four keys above.
       'C_ss_weighted': C_ss_sim, 'A_ss_weighted': A_ss_sim}
                
fileObj = open('HA_Fiscal_Jacs.obj', 'wb')
pickle.dump(Obj,fileObj)
fileObj.close()     

   
os.chdir("../")


# obj = open('HA_Fiscal_Jacs.obj', 'rb')
# HA_fiscal_JAC = pickle.load(obj)
# obj.close()

# ──────────────────────────────────────────────────────────────────────────────
# Dead scratch removed 2026-06-23: ~940 lines of old plotting + a macro-model
# prototype that lived in triple-quoted string literals and never executed (the
# stale varphi=120 lived here). The LIVE HANK-SAM macro model + GE solve is in
# HA-Fiscal-HANK-SAM-to-python.py (varphi=96.9). This file's job is the household
# Jacobians, pickled above as HA_Fiscal_Jacs.obj.
# ──────────────────────────────────────────────────────────────────────────────


# ---- Provenance sidecar (schema v2; best-effort, never aborts) -------------
try:
    import os as _prov_os, sys as _prov_sys
    _prov_ha = _prov_os.path.abspath(_prov_os.path.join(
        _prov_os.path.dirname(_prov_os.path.abspath(__file__)), '..'))
    if _prov_ha not in _prov_sys.path:
        _prov_sys.path.insert(0, _prov_ha)
    import provenance as _prov
    # 2026-08-09 (dossier S3.5): declare the ACTUAL output instead of
    # hashing "." — which, after the os.chdir('../') above, silently
    # pointed at Code/HA-Models rather than FromPandemicCode — and
    # register like every other pipeline emitter.
    _prov_obj = _prov_os.path.join(
        _prov_os.path.dirname(_prov_os.path.abspath(__file__)),
        "HA_Fiscal_Jacs.obj")
    _prov.emit([_prov_obj], command=" ".join(_prov_sys.argv),
               argv=_prov_sys.argv,
               label="step4-hank-sam-jacobians", register=True)
except Exception as _prov_e:
    print(f"[provenance] sidecar emit skipped (non-fatal): {_prov_e}")
