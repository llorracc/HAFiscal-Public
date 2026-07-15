"""
GLP-1 mode with AD enabled (TM only) — tests the new run_ad_tm wiring.
"""
import os, sys

cwd = os.getcwd()
folders = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    os.chdir(Abs_Path)
sys.path.append(Abs_Path)

from time import time
from Simulate import Simulate

Run_Dict = dict()
Run_Dict['Run_Baseline']            = True
Run_Dict['Run_Recession ']          = True
Run_Dict['Run_Check_Recession']     = True
Run_Dict['Run_UB_Ext_Recession']    = True
Run_Dict['Run_TaxCut_Recession']    = True
Run_Dict['Run_Check']               = False   # skip no-recession shocks for speed
Run_Dict['Run_UB_Ext']              = False
Run_Dict['Run_TaxCut']              = False
Run_Dict['Run_AD ']                 = True    # <-- ENABLE AD
Run_Dict['Run_1stRoundAD']          = False
Run_Dict['Run_NonAD']               = True
Run_Dict['sim_method']              = 'TM'
Run_Dict['GLP1']                    = True
Run_Dict['GLP1_recession_duration'] = 3

figs_dir = Abs_Path + '/Figures/Reduced_Run/'
os.makedirs(figs_dir, exist_ok=True)

t0 = time()
Simulate(Run_Dict, figs_dir, Parametrization='Reduced_Run')
t1 = time()
print(f'\nTotal time: {(t1-t0)/60:.2f} min')

# --- Print comparison of non-AD vs AD multipliers ---
import pickle, numpy as np

def load_pkl(name):
    with open(figs_dir + name + '.csv', 'rb') as f:
        return pickle.load(f)

Rfree = 1.01**(1/4)  # quarterly
act_T = 400  # default

print("\n" + "=" * 60)
print("GLP-1 + AD RESULTS (TM only)")
print("=" * 60)

for shock in ['recession', 'recessionCheck', 'recessionUI', 'recessionTaxCut']:
    try:
        r_noAD = load_pkl(shock + '_results')
        r_AD   = load_pkl(shock + '_results_AD')
        mult_noAD = r_noAD['NPV_AggCons'] / r_noAD['NPV_AggIncome']
        mult_AD   = r_AD['NPV_AggCons'] / r_AD['NPV_AggIncome']
        ratio = mult_AD / mult_noAD if mult_noAD != 0 else float('nan')
        print(f"  {shock:25s}  nonAD={mult_noAD:.4f}  AD={mult_AD:.4f}  ratio={ratio:.3f}")
    except Exception as e:
        print(f"  {shock:25s}  ERROR: {e}")
