"""p10b: the truly-UNFINANCED arm (phi=0: constant G, constant tau, debt
permanently rolled) vs the incidence-free G-rule arm — does stabilizing
the bond path at nobody's expense differ from not stabilizing it at all?
(The PE-comparability arm: PE modeled no repayment.)"""
import runpy
import numpy as np
from copy import deepcopy
import io, contextlib

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g = runpy.run_path(
        '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/'
        'solution_cache/_armc_bench/p10_financing_matrix.py')
M, SS, npv, dW_of = g['M'], g['SS'], g['npv'], g['dW_of']
shock_paths, COSTK, up_pop = g['shock_paths'], g['COSTK'], g['up_pop']
res_prev = g['results']

print(f"{'policy':>14s} {'regime':>11s} {'unfin spend':>11s} {'G-rule spend':>12s} "
      f"{'unfin W':>8s} {'G-rule W':>9s}")
for pol in ("transfers", "UI_extensions", "tax_cut"):
    var, path = shock_paths[pol]
    for reg in ("taylor", "fixed_real"):
        mkey = ("G", "fixed_real" if reg == "fixed_real" else "taylor")
        ssd = deepcopy(SS)
        ssd['phi_w'] = 0.837; ssd['deficit_T'] = -1
        ssd['phi_b'] = 0.015; ssd['phi_G'] = 0.0; ssd['phi_pi'] = 1.5
        unk = ['theta'] if reg == "fixed_real" else ['theta', 'r_ante']
        tgt = ['asset_mkt'] if reg == "fixed_real" else ['asset_mkt', 'fisher_resid']
        irf = M[mkey].solve_impulse_linear(ssd, unk, tgt, {var: path})
        cost = abs(npv(irf[COSTK[pol]], 300))
        sp = abs(npv(irf['C'], 20)) / cost
        w = abs(npv(dW_of(irf), 20)) / (up_pop * cost)
        gsp, gw = res_prev[(pol, "G", reg)]
        print(f"{pol:>14s} {reg:>11s} {sp:11.3f} {gsp:12.3f} {w:8.3f} {gw:9.3f}")
