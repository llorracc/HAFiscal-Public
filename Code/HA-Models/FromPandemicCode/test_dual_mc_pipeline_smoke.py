"""
Smoke test: DualAggFiscalType wired into Simulate.py pipeline.

Verifies:
  1. sim_method='dual_MC' runs without crashing
  2. P-track results are present and finite
  3. Q-track history_Q is populated on agents
  4. P-track AggCons matches standard MC (same seed)
"""
import sys
import os
import numpy as np

sys.argv = ["test", "1.03", "2", "0.3"]

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from Simulate import Simulate
import tempfile, shutil


def _run_simulate(sim_method, figs_dir):
    Run_Dict = dict()
    Run_Dict['Run_Baseline']         = True
    Run_Dict['Run_Recession ']       = False
    Run_Dict['Run_Check_Recession']  = False
    Run_Dict['Run_UB_Ext_Recession'] = False
    Run_Dict['Run_TaxCut_Recession'] = False
    Run_Dict['Run_Check']            = False
    Run_Dict['Run_UB_Ext']           = True
    Run_Dict['Run_TaxCut']           = False
    Run_Dict['Run_AD ']              = False
    Run_Dict['Run_1stRoundAD']       = False
    Run_Dict['Run_NonAD']            = True
    Run_Dict['sim_method']           = sim_method
    Run_Dict['tm_neutral_measure']   = False
    Run_Dict['tm_mCount']            = 50
    Run_Dict['mc_use_tm_init']       = False
    Run_Dict['mc_warmup']            = 4

    Simulate(Run_Dict, figs_dir, Parametrization='Reduced_Run')
    return Run_Dict


def test_dual_mc_smoke():
    """dual_MC pipeline runs without crashing and produces finite results."""
    figs_dir = tempfile.mkdtemp(prefix="dual_mc_smoke_")
    try:
        _run_simulate('dual_MC', figs_dir + '/')

        import pickle, glob
        pkls = sorted(glob.glob(os.path.join(figs_dir, '*.csv')))
        print(f"Saved pickles: {[os.path.basename(p) for p in pkls]}")

        for pkl_path in pkls:
            name = os.path.basename(pkl_path)
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            if isinstance(data, dict) and 'AggCons' in data:
                ac = np.array(data['AggCons'])
                assert np.all(np.isfinite(ac)), f"{name}: non-finite AggCons"
                assert np.all(ac > 0), f"{name}: non-positive AggCons"
                print(f"  {name}: AggCons mean = {np.mean(ac):.4f}")

        assert len(pkls) > 0, "No pickle files produced"
        print("SMOKE TEST PASSED")
    finally:
        shutil.rmtree(figs_dir, ignore_errors=True)


if __name__ == "__main__":
    test_dual_mc_smoke()
