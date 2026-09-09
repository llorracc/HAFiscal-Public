"""L1 cell gate: run all 8 shock params for one (educ, beta) cell through
the CURRENT (or edited) compute_type_jacobian machinery and stash the
Jacobians for byte-comparison across the hoist edit.

Usage: python l1_cell_gate.py <tag>   -> writes l1_cell_<tag>.npz
After the edit, the script auto-detects the hoisted API (prepare_type_base
+ compute_type_jacobian_for_param) and uses it; otherwise the legacy
single function. Byte-compare with l1_cell_compare.py.
"""
import os, sys, time
import numpy as np

tag = sys.argv[1] if len(sys.argv) > 1 else "baseline"
FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
OUT = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
sys.argv = ["l1_cell_gate"]
os.chdir(FPC)
sys.path.insert(0, FPC)

SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
CUT = "for e in range(num_educ_types): #education type"
ns = {"__name__": "hank_setup_l1", "__file__": SRC}
t0 = time.time()
exec(compile(text[: text.index(CUT)], SRC, "exec"), ns)
print(f"[l1] setup {time.time()-t0:.1f}s  arm=SHOCK_FIX:{os.environ.get('HAFISCAL_STEP4_SHOCK_FIX','(default 1)')}")

E, DFI = 0, 3
beta = ns["DiscFacDstns"][E].atoms[0][DFI]
dct = ns["dicts"][E]
agent = ns["BaseTypeList"][E]
IncDist = [ns["IncShkDstn"][E]]
shock_params = ["transfers", "Rfree", "wage", "tax", "job_find", "DiscFac", "UI_extend", "UI_rr"]

def dx_for(param):
    m = {"wage": "IncShkDstn_wage_dx", "tax": "IncShkDstn_tax_dx",
         "transfers": "IncShkDstn_transfers_dx", "UI_extend": "IncShkDstn_ui_extend_dx",
         "UI_rr": "IncShkDstn_ui_rr_dx"}
    return [ns[m[param]][E]] if param in m else [ns["IncShkDstn"][E]]

out = {}
hoisted = "prepare_type_base" in ns
print(f"[l1] API: {'hoisted' if hoisted else 'legacy'}")
t_all = time.time()
if hoisted:
    base = ns["prepare_type_base"](agent, dct, beta, IncDist)
    for param in shock_params:
        t0 = time.time()
        CJac, AJac, C_ss, A_ss = ns["compute_type_jacobian_for_param"](
            base, IncDist, dx_for(param), param)
        out[f"C_{param}"], out[f"A_{param}"] = CJac, AJac
        out[f"Css_{param}"], out[f"Ass_{param}"] = C_ss, A_ss
        print(f"[l1] {param}: {time.time()-t0:.1f}s")
else:
    for param in shock_params:
        t0 = time.time()
        CJac, AJac, C_ss, A_ss = ns["compute_type_jacobian"](
            agent, dct, beta, IncDist, dx_for(param), param)
        out[f"C_{param}"], out[f"A_{param}"] = CJac, AJac
        out[f"Css_{param}"], out[f"Ass_{param}"] = C_ss, A_ss
        print(f"[l1] {param}: {time.time()-t0:.1f}s")

print(f"[l1] cell total {time.time()-t_all:.1f}s")
np.savez_compressed(os.path.join(OUT, f"l1_cell_{tag}.npz"), **out)
print(f"[l1] stashed l1_cell_{tag}.npz")
