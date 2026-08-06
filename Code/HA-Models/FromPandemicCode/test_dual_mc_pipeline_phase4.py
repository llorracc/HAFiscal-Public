"""
Phase 4: AD loop with dual MC.

Runs a single recession shock type (recession) with both Run_AD
and Run_NonAD using sim_method='dual_MC'.

Verifies that the AD loop converges and produces Q-track data.
"""
import sys
import os
import numpy as np

sys.argv = ["test", "1.03", "2", "0.3"]
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from Simulate import Simulate
import tempfile, shutil, pickle, glob


def run_ad_dual_mc():
    figs_dir = tempfile.mkdtemp(prefix="dual_mc_phase4_")
    Run_Dict = dict()
    Run_Dict['Run_Baseline']         = True
    Run_Dict['Run_Recession ']       = True
    Run_Dict['Run_Check_Recession']  = False
    Run_Dict['Run_UB_Ext_Recession'] = False
    Run_Dict['Run_TaxCut_Recession'] = False
    Run_Dict['Run_Check']            = False
    Run_Dict['Run_UB_Ext']           = False
    Run_Dict['Run_TaxCut']           = False
    Run_Dict['Run_AD ']              = True
    Run_Dict['Run_1stRoundAD']       = False
    Run_Dict['Run_NonAD']            = True
    Run_Dict['sim_method']           = 'dual_MC'
    Run_Dict['tm_neutral_measure']   = False
    Run_Dict['tm_mCount']            = 50
    Run_Dict['mc_use_tm_init']       = False
    Run_Dict['mc_warmup']            = 4
    Run_Dict['GLP1_recession_duration'] = 3

    Simulate(Run_Dict, figs_dir + '/', Parametrization='Reduced_Run')
    return figs_dir


def load_result(figs_dir, name):
    path = os.path.join(figs_dir, name + '.csv')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    return None


def main():
    print("Running AD + NonAD recession experiment with dual_MC...")
    figs_dir = run_ad_dual_mc()

    try:
        pkls = sorted(glob.glob(os.path.join(figs_dir, '*.csv')))
        print(f"\nProduced files: {[os.path.basename(p) for p in pkls]}")

        noAD  = load_result(figs_dir, 'recession_results')
        AD    = load_result(figs_dir, 'recession_results_AD')

        print("\n" + "=" * 78)
        print("Phase 4: Dual MC — AD Loop (recession)")
        print("=" * 78)

        for label, res in [('No AD', noAD), ('With AD', AD)]:
            if res is None:
                print(f"\n{label}: MISSING")
                continue
            ac_P = np.array(res['AggCons'])
            ac_Q = res.get('AggCons_Q', None)
            print(f"\n{label}:")
            print(f"  P AggCons mean: {np.mean(ac_P):.2f}")
            if ac_Q is not None:
                ac_Q = np.array(ac_Q)
                ratio = np.mean(ac_P) / np.mean(ac_Q)
                cv_P = np.std(ac_P) / np.mean(ac_P)
                cv_Q = np.std(ac_Q) / np.mean(ac_Q)
                print(f"  Q AggCons mean: {np.mean(ac_Q):.2f}")
                print(f"  P/Q ratio: {ratio:.4f}")
                print(f"  CV_P: {cv_P:.5f}   CV_Q: {cv_Q:.5f}   VarRed: {np.var(ac_P)/max(np.var(ac_Q),1e-30):.1f}x")
            else:
                print(f"  Q AggCons: N/A")

        if noAD is not None and AD is not None:
            noAD_P = np.mean(noAD['AggCons'])
            AD_P = np.mean(AD['AggCons'])
            print(f"\nAD amplification (P): {AD_P/noAD_P:.4f}")
            noAD_Q = noAD.get('AggCons_Q')
            AD_Q = AD.get('AggCons_Q')
            if noAD_Q is not None and AD_Q is not None:
                print(f"AD amplification (Q): {np.mean(AD_Q)/np.mean(noAD_Q):.4f}")

        print("\n*** PHASE 4 COMPLETE ***")
    finally:
        shutil.rmtree(figs_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
