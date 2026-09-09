"""Step-2 objective evaluated AT the production per-edType TM_a (beta,nabla,GICx) under the
CURRENT env — config strand + HAFISCAL_AXTRA_COUNT set by the caller. Used for the 2026-07-23
count-convergence sweep (conclusions_private/2026-07-23_solve_grid_count_convergence.md) and
originally for the longlife E3 reference (2026-07-21). One process per env combination."""
import os
import sys

os.environ["HAFISCAL_EDTYPES"] = ""          # import module, skip its estimation loop
os.environ["HAFISCAL_INTERPRETATION"] = "ESC"
os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
os.environ.setdefault("HAFISCAL_GICX_MODE", "hardcoded")

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")
for p in (HAM, FPC):
    sys.path.insert(0, p)
os.chdir(FPC)

_saved = sys.argv
sys.argv = [sys.argv[0]]
try:
    import estim_phase2_tm_a as est
    import adaptive_grid_tm as agt
finally:
    sys.argv = _saved

for e, name in ((0, "dropout"), (1, "highschool"), (2, "college")):
    f = os.path.join(HAM, "Results", f"DiscFacEstim_CRRA_2.0_R_1.01_edType{e}_TM_a_ESC.txt")
    beta, nabla, gicx = None, None, None
    with open(f) as fh:
        for line in fh:
            if f"'EducationGroup': {e}" in line:
                rec = eval(line, {"np": __import__("numpy"), "__builtins__": {}})
                beta, nabla, gicx = float(rec["beta"]), float(rec["nabla"]), float(rec["GICx"])
    print(f"\n===== PRODUCTION REFERENCE {name}: beta={beta:.6f} nabla={nabla:.6f} GICx={gicx:.4f}")
    d = est.betas_obj_func_educ_tm_a(beta, nabla, gicx, educ_type=e, print_mode=True)
    print(f"===== {name} production distance = {d:.6f}", flush=True)
