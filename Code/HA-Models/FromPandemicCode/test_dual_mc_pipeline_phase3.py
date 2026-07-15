"""
Phase 3: TM grid convergence sweep using P-MC as reference.

Runs baseline + one no-recession experiment (TaxCut) with both dual_MC
and TM at multiple grid sizes (mCount = 30, 50, 80).

Compares TM AggCons to P-MC AggCons to assess TM convergence.
"""
import sys
import os
import numpy as np

sys.argv = ["test", "1.03", "2", "0.3"]
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from Simulate import Simulate
import tempfile, shutil, pickle


def run_dual_mc(figs_dir):
    Run_Dict = dict()
    Run_Dict['Run_Baseline']         = True
    Run_Dict['Run_Recession ']       = False
    Run_Dict['Run_Check_Recession']  = False
    Run_Dict['Run_UB_Ext_Recession'] = False
    Run_Dict['Run_TaxCut_Recession'] = False
    Run_Dict['Run_Check']            = False
    Run_Dict['Run_UB_Ext']           = False
    Run_Dict['Run_TaxCut']           = True
    Run_Dict['Run_AD ']              = False
    Run_Dict['Run_1stRoundAD']       = False
    Run_Dict['Run_NonAD']            = True
    Run_Dict['sim_method']           = 'dual_MC'
    Run_Dict['tm_neutral_measure']   = False
    Run_Dict['tm_mCount']            = 50
    Run_Dict['mc_use_tm_init']       = False
    Run_Dict['mc_warmup']            = 4

    Simulate(Run_Dict, figs_dir + '/', Parametrization='Reduced_Run')


def run_tm(figs_dir, mCount):
    Run_Dict = dict()
    Run_Dict['Run_Baseline']         = True
    Run_Dict['Run_Recession ']       = False
    Run_Dict['Run_Check_Recession']  = False
    Run_Dict['Run_UB_Ext_Recession'] = False
    Run_Dict['Run_TaxCut_Recession'] = False
    Run_Dict['Run_Check']            = False
    Run_Dict['Run_UB_Ext']           = False
    Run_Dict['Run_TaxCut']           = True
    Run_Dict['Run_AD ']              = False
    Run_Dict['Run_1stRoundAD']       = False
    Run_Dict['Run_NonAD']            = True
    Run_Dict['sim_method']           = 'TM'
    Run_Dict['tm_neutral_measure']   = False
    Run_Dict['tm_mCount']            = mCount
    Run_Dict['mc_use_tm_init']       = False
    Run_Dict['mc_warmup']            = 4

    Simulate(Run_Dict, figs_dir + '/', Parametrization='Reduced_Run')


def load_result(figs_dir, name):
    path = os.path.join(figs_dir, name + '.csv')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    return None


def main():
    mc_dir = tempfile.mkdtemp(prefix="phase3_mc_")
    tm_dirs = {}
    mCounts = [30, 50, 80]

    try:
        print("=== Running dual_MC reference ===")
        run_dual_mc(mc_dir)
        mc_base = load_result(mc_dir, 'base_results')
        mc_tc   = load_result(mc_dir, 'TaxCut_results')

        for m in mCounts:
            d = tempfile.mkdtemp(prefix=f"phase3_tm{m}_")
            tm_dirs[m] = d
            print(f"\n=== Running TM mCount={m} ===")
            run_tm(d, m)

        print("\n" + "=" * 80)
        print("Phase 3: TM Grid Convergence — TaxCut (no recession)")
        print("=" * 80)

        mc_base_ac = np.array(mc_base['AggCons'])
        mc_tc_ac   = np.array(mc_tc['AggCons'])
        mc_tc_qac  = np.array(mc_tc.get('AggCons_Q', mc_tc_ac))
        mc_dnpv_P = np.sum(mc_tc_ac - mc_base_ac)

        mc_base_qac = np.array(mc_base.get('AggCons_Q', mc_base_ac))
        mc_dnpv_Q = np.sum(mc_tc_qac - mc_base_qac)

        print(f"\nP-MC reference:  dNPV = {mc_dnpv_P:.4f}")
        print(f"Q-MC reference:  dNPV = {mc_dnpv_Q:.4f}")

        print(f"\n{'mCount':>8} {'TM dNPV':>12} {'TM/P-MC':>10} {'TM/Q-MC':>10}")
        print("-" * 45)
        for m in mCounts:
            tm_base = load_result(tm_dirs[m], 'base_results')
            tm_tc   = load_result(tm_dirs[m], 'TaxCut_results')
            if tm_base is None or tm_tc is None:
                print(f"{m:>8} {'MISSING':>12}")
                continue
            tm_base_ac = np.array(tm_base['AggCons'])
            tm_tc_ac   = np.array(tm_tc['AggCons'])
            tm_dnpv = np.sum(tm_tc_ac - tm_base_ac)
            r_p = tm_dnpv / mc_dnpv_P if abs(mc_dnpv_P) > 1e-10 else float('nan')
            r_q = tm_dnpv / mc_dnpv_Q if abs(mc_dnpv_Q) > 1e-10 else float('nan')
            print(f"{m:>8} {tm_dnpv:>12.4f} {r_p:>10.4f} {r_q:>10.4f}")

        print("\n*** PHASE 3 COMPLETE ***")

    finally:
        shutil.rmtree(mc_dir, ignore_errors=True)
        for d in tm_dirs.values():
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
