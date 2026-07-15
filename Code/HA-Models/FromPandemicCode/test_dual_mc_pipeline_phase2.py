"""
Phase 2: Recession experiments with dual_MC.

Runs the four recession shock types (recession, recessionCheck,
recessionUI, recessionTaxCut) with sim_method='dual_MC'.

Checks:
  1. All experiments complete without error
  2. P/Q ratio for aggregate consumption
  3. Differenced NPVs are consistent
"""
import sys
import os
import numpy as np

sys.argv = ["test", "1.03", "2", "0.3"]
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from Simulate import Simulate
import tempfile, shutil, pickle, glob


def run_dual_mc_recession():
    figs_dir = tempfile.mkdtemp(prefix="dual_mc_phase2_")
    Run_Dict = dict()
    Run_Dict['Run_Baseline']         = True
    Run_Dict['Run_Recession ']       = True
    Run_Dict['Run_Check_Recession']  = True
    Run_Dict['Run_UB_Ext_Recession'] = True
    Run_Dict['Run_TaxCut_Recession'] = True
    Run_Dict['Run_Check']            = False
    Run_Dict['Run_UB_Ext']           = False
    Run_Dict['Run_TaxCut']           = False
    Run_Dict['Run_AD ']              = False
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


def analyze(figs_dir):
    rec   = load_result(figs_dir, 'recession_results')
    rchk  = load_result(figs_dir, 'recessionCheck_results')
    rui   = load_result(figs_dir, 'recessionUI_results')
    rtc   = load_result(figs_dir, 'recessionTaxCut_results')

    print("\n" + "=" * 78)
    print("Phase 2: Dual MC — Recession Experiments")
    print("=" * 78)

    results = {
        'Recession':     rec,
        'Rec+Check':     rchk,
        'Rec+UI':        rui,
        'Rec+TaxCut':    rtc,
    }

    print(f"\n{'Experiment':<18} {'P mean':>12} {'Q mean':>12} {'P/Q ratio':>10} {'CV_P':>8} {'CV_Q':>8} {'VarRed':>8}")
    print("-" * 78)
    all_ok = True
    for name, res in results.items():
        if res is None:
            print(f"{name:<18} {'MISSING':>12}")
            all_ok = False
            continue
        ac_P = np.array(res['AggCons'])
        ac_Q = res.get('AggCons_Q', None)
        ok = np.all(np.isfinite(ac_P)) and np.all(ac_P > 0)
        if not ok:
            all_ok = False

        if ac_Q is not None:
            ac_Q = np.array(ac_Q)
            ratio = np.mean(ac_P) / np.mean(ac_Q)
            cv_P = np.std(ac_P) / np.mean(ac_P)
            cv_Q = np.std(ac_Q) / np.mean(ac_Q)
            var_red = np.var(ac_P) / max(np.var(ac_Q), 1e-30)
            print(f"{name:<18} {np.mean(ac_P):>12.2f} {np.mean(ac_Q):>12.2f} {ratio:>10.4f} {cv_P:>8.5f} {cv_Q:>8.5f} {var_red:>7.1f}x")
        else:
            print(f"{name:<18} {np.mean(ac_P):>12.2f} {'N/A':>12}")

    if rec is not None:
        rec_P = np.array(rec['AggCons'])
        rec_Q = np.array(rec.get('AggCons_Q', rec_P))
        print(f"\n{'--- Differenced NPVs (policy - recession) ---':}")
        print(f"{'Policy':<18} {'dNPV_P':>12} {'dNPV_Q':>12} {'Q/P ratio':>10}")
        print("-" * 55)
        for label, res in [('Rec+Check', rchk), ('Rec+UI', rui), ('Rec+TaxCut', rtc)]:
            if res is None:
                continue
            exp_P = np.array(res['AggCons'])
            exp_Q = np.array(res.get('AggCons_Q', exp_P))
            dnpv_P = np.sum(exp_P - rec_P)
            dnpv_Q = np.sum(exp_Q - rec_Q)
            qp = dnpv_Q / dnpv_P if abs(dnpv_P) > 1e-10 else float('nan')
            print(f"{label:<18} {dnpv_P:>12.4f} {dnpv_Q:>12.4f} {qp:>10.4f}")

    return all_ok


def main():
    print("Running recession experiments with dual_MC...")
    figs_dir = run_dual_mc_recession()

    try:
        pkls = sorted(glob.glob(os.path.join(figs_dir, '*.csv')))
        print(f"\nProduced files: {[os.path.basename(p) for p in pkls]}")
        ok = analyze(figs_dir)

        if ok:
            print("\n*** PHASE 2 PASSED: All recession experiments produced valid results ***")
        else:
            print("\n*** PHASE 2 FAILED ***")
            sys.exit(1)
    finally:
        shutil.rmtree(figs_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
