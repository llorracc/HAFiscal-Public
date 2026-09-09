"""T4 (C3.5, plan 20260807-0919h): Step-2 estimation objective evaluated
at the FIXED installed (beta, nabla, GICx) per education type — standing
no-re-estimation rule. Run once per arm (flag-off vs newton2d+numba via
env); the gate is per-educ objective agreement within tolerance.

Usage:  <env flags>  python t4_step2_objective.py <tag>
"""
import os
import re
import sys

TAG = sys.argv[1] if len(sys.argv) > 1 else "arm"
FP = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
sys.path.insert(0, FP)
os.chdir(FP)
os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")
sys.argv = sys.argv[:1]

import EstimAggFiscalMAIN as E  # noqa: E402  (builds economies, skips NM)

res = os.path.join(FP, E.res_dir) if not os.path.isabs(E.res_dir) else E.res_dir
fn = os.path.join(res, f"DiscFacEstim_CRRA_{E.CRRA}_R_{E.Rfree_base[0]}.txt")
txt = open(fn).read()
trips = re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", txt)
print(f"[t4:{TAG}] estimates file: {fn}")
print(f"[t4:{TAG}] parsed floats: {trips[:12]}")

# The file lists (beta, nabla[, GICx]) per education type in order
# dropout, highschool, college — betas_obj_func_educ signature order.
vals = [float(x) for x in trips]
per = 3 if len(vals) >= 9 else 2
for ed, name in enumerate(("Dropout", "Highschool", "College")):
    chunk = vals[ed * per:(ed + 1) * per]
    if len(chunk) < 2:
        print(f"[t4:{TAG}] educ={ed} PARSE-MISS ({chunk})")
        continue
    b, s = chunk[0], chunk[1]
    g = chunk[2] if per == 3 else E._GICx_for_factor_0999
    d = E.betas_obj_func_educ(b, s, g, educ_type=ed)
    print(f"[t4:{TAG}] educ={ed} {name}: beta={b:.6f} nabla={s:.6f} "
          f"GICx={g:.6f} objective={d:.12e}", flush=True)
print(f"[t4:{TAG}] DONE", flush=True)
