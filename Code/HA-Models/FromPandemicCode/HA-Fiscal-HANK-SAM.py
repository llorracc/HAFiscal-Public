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
init_dropout["mCount"] = mCount
init_dropout["mFac"] = 3
init_dropout["mMin"] = 1e-4
init_dropout["mMax"] = 100000
init_dropout["PermGroFac"] = [np.ones(states)]
init_dropout['aXtraMax'] = aMax
init_dropout['aXtraCount'] = aCount
init_dropout['MrkvArray'] = init_highschool['MrkvArray'] # for now assume only one markov matrix
init_dropout['Rfree'] = Rfree 
init_dropout['LivPrb'] = LivPrb 

init_highschool["mCount"] = mCount
init_highschool["mFac"] = 3
init_highschool["mMin"] = 1e-4
init_highschool["mMax"] = 100000
init_highschool["PermGroFac"] = [np.ones(states)]
init_highschool['aXtraMax'] = aMax
init_highschool['aXtraCount'] = aCount
init_highschool['Rfree'] = Rfree 
init_highschool['LivPrb'] = LivPrb 

init_college["mCount"] = mCount
init_college["mFac"] = 3
init_college["mMin"] = 1e-4
init_college["mMax"] = 100000
init_college["PermGroFac"] = [np.ones(states)]
init_college['aXtraMax'] = aMax
init_college['aXtraCount'] = aCount
init_college['MrkvArray'] = init_highschool['MrkvArray'] # for now assume only one markov matrix
init_college['Rfree'] = Rfree 
init_college['LivPrb'] = LivPrb 

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

def compute_type_jacobian(agent, dict, DiscFac, IncDist, IncDist_dx, param):
    dx = 0.0001

    agent_SS = deepcopy(agent)
    agent_SS.IncShkDstn = deepcopy(IncDist)
    agent_SS.DiscFac = DiscFac
    agent_SS.compute_steady_state()

    C_ss_ThisType = deepcopy(agent_SS.C_ss)
    A_ss_ThisType = deepcopy(agent_SS.A_ss)
    
    c = agent_SS.cPol_Grid
    a = agent_SS.aPol_Grid

    ##################################################################################################
    # Finite Horizon

    params = deepcopy(dict)
    params["T_cycle"] = bigT
    params["LivPrb"] = params["T_cycle"] * [agent_SS.LivPrb[0]]
    params["PermGroFac"] = params["T_cycle"] * [agent_SS.PermGroFac[0]]
    params["PermShkStd"] = params["T_cycle"] * [agent_SS.PermShkStd[0]]
    params["TranShkStd"] = params["T_cycle"] * [agent_SS.TranShkStd[0]]
    params["Rfree"] = params["T_cycle"] * [agent_SS.Rfree]
    params["MrkvArray"] = params["T_cycle"] * agent_SS.MrkvArray
    params["DiscFac"] = DiscFac
    params["cycles"] = 1

    FinHorizonAgent = MarkovConsumerType(**params)
    FinHorizonAgent.dist_pGrid = params["T_cycle"] * [np.array([1])]
    FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
    FinHorizonAgent.solution_terminal = deepcopy(agent_SS.solution[0])

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
        FinHorizonAgent.Rfree = (params["T_cycle"] - 1) * [agent.Rfree] + [agent.Rfree + dx] + [agent.Rfree]
    elif param == "DiscFac":
        FinHorizonAgent.del_from_time_inv(
            "DiscFac",
        )  # delete Rfree from time invariant list since it varies overtime
        FinHorizonAgent.add_to_time_vary("DiscFac")
        FinHorizonAgent.DiscFac = (params["T_cycle"] - 1) * [DiscFac] + [DiscFac + dx]

    FinHorizonAgent.solve()

    if param == "transfers" or param =='wage' or param =='tax'or param =='UI_extend' or param =='UI_rr':
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(agent_SS.IncShkDstn) + deepcopy(agent_inc_dx.IncShkDstn)
        
        
    else:
        FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)

    # Calculate Transition Matrices
    FinHorizonAgent.neutral_measure = True
    # FinHorizonAgent.harmenberg_income_process()
    FinHorizonAgent.define_distribution_grid()
    FinHorizonAgent.calc_transition_matrix() 

    ##################################################################################################
    # period zero shock agent

    Zeroth_col_agent = MarkovConsumerType(**params)
    Zeroth_col_agent.solution_terminal = deepcopy(agent_SS.solution[0])
    Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
    Zeroth_col_agent.solve()

    if param == "transfers" or param =='wage' or param =='tax' or param =='UI_extend' or param =='UI_rr':
        Zeroth_col_agent.IncShkDstn = deepcopy(agent_inc_dx.IncShkDstn) + (params["T_cycle"]) * deepcopy(agent_SS.IncShkDstn)
    elif param == "job_find":
        Zeroth_col_agent.MrkvArray = [Mrkv_dx] + (params["T_cycle"] - 1) * agent.MrkvArray
    elif param == "Rfree":
        Zeroth_col_agent.Rfree = [agent.Rfree + dx] + (params["T_cycle"] - 1) * [agent.Rfree]
    elif param == "DiscFac":
        Zeroth_col_agent.DiscFac = [DiscFac + dx] + (params["T_cycle"] - 1) * [DiscFac]
        
        
    # if param != "IncShkDstn" or param =! "wage" or param =!"tax":
    #     Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)
  
            
    if param == "DiscFac" or param == "Rfree" or param =="job_find":
        Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)
  


    Zeroth_col_agent.neutral_measure = True
    Zeroth_col_agent.define_distribution_grid()
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

    tranmat_t = np.insert(transition_matrices, params["T_cycle"], tranmat_ss, axis = 0)

    c_t = np.insert(c_t_flat, params["T_cycle"] , c_ss , axis = 0)
    a_t = np.insert(a_t_flat, params["T_cycle"] , a_ss , axis = 0)

    CJAC_perfect, AJAC_perfect = compile_JAC(a_ss, c_ss, a_t, c_t, tranmat_ss, tranmat_t, D_ss, C_ss, A_ss, Zeroth_col_agent, bigT)

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
    
    dlambda0_s = []
    
    for i in range(T):
        dlambda0_s.append(tranmat_t[T - i] - tranmat_ss)
    
    dlambda0_s = np.array(dlambda0_s)
    
    dD0_s = []
    
    for i in range(T):
        dD0_s.append(np.dot(dlambda0_s[i], D_ss))
    
    dD0_s = np.array(dD0_s)
    D_curl_s = dD0_s/dx
    
    Curl_F_A = np.zeros((T , T))
    Curl_F_C = np.zeros((T , T))
    
    # WARNING: SWAPPED THESE LINES TO MAKE DEMO RUN
    # Curl_F_A[0] = A_curl_s
    # Curl_F_C[0] = C_curl_s
    Curl_F_A[0] = A_curl_s.T[0]
    Curl_F_C[0] = C_curl_s.T[0]

    for i in range(T-1):
        for j in range(T):
            Curl_F_A[i + 1][j] = np.dot(exp_vecs_a_e[i], D_curl_s[j])[0]
            Curl_F_C[i + 1][j] = np.dot(exp_vecs_c_e[i], D_curl_s[j])[0]

    J_A = np.zeros((T, T))
    J_C = np.zeros((T, T))

    for t in range(T):
        for s in range(T):
            if (t ==0) or (s==0):
                J_A[t][s] = Curl_F_A[t][s]
                J_C[t][s] = Curl_F_C[t][s]
                
            else:
                J_A[t][s] = J_A[t - 1][s - 1] + Curl_F_A[t][s]
                J_C[t][s] = J_C[t - 1][s - 1] + Curl_F_C[t][s]
     
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

            CJac, AJac, C_ss, A_ss = compute_type_jacobian(BaseTypeList[e], dict, beta, IncDist, IncDist_dx, param)
            
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

Obj = {'C' :CJAC_dict_temp , 'A': AJAC_dict_temp , 'C_by_educ':  CJAC_dict_educ_temp , 'A_by_educ':  AJAC_dict_educ_temp  }
                
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
