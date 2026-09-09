"""L3 P-1 gate: dispatch-share decomposition of the post-L1 per-param
residual (~7.3 s). The fasteop lesson: cum-time is NOT the prize — only
removable python dispatch pays under compilation. Categories:
  - solve: FinHorizonAgent.solve() (300-period backward pass)
  - tranmat: calc_transition_matrix (FinHorizon + Zeroth)
  - compile: compile_JAC
and within each, tottime split python-frames vs numpy-builtins.
"""
import cProfile, io, os, pstats, sys, time
import numpy as np

FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
OUT = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
sys.argv = ["l3_p1"]
os.chdir(FPC)
sys.path.insert(0, FPC)
SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
ns = {"__name__": "hank_setup_l3", "__file__": SRC}
exec(compile(text[: text.index("for e in range(num_educ_types): #education type")], SRC, "exec"), ns)

E, DFI = 0, 3
beta = ns["DiscFacDstns"][E].atoms[0][DFI]
base = ns["prepare_type_base"](ns["BaseTypeList"][E], ns["dicts"][E], beta, [ns["IncShkDstn"][E]])
IncDist = [ns["IncShkDstn"][E]]
IncDist_dx = [ns["IncShkDstn_transfers_dx"][E]]

pr = cProfile.Profile()
t0 = time.time()
pr.enable()
ns["compute_type_jacobian_for_param"](base, IncDist, IncDist_dx, "transfers")
pr.disable()
wall = time.time() - t0
print(f"[l3] profiled call wall {wall:.1f}s (cProfile overhead included)")
pr.dump_stats(os.path.join(OUT, "l3_p1_transfers.pstats"))

st = pstats.Stats(pr)
total_tt = sum(v[2] for v in st.stats.values())
print(f"[l3] total tottime {total_tt:.2f}s")

# category split by file/function
cats = {}
ncalls_total = 0
for (fn, line, name), (cc, nc, tt, ct, callers) in st.stats.items():
    ncalls_total += nc
    if "~" in fn:  # builtins
        key = "builtin:" + name.strip("<>")
        base_cat = "numpy/builtin" if ("numpy" in name or "method" in name or "built-in" in name) else "builtin"
    elif "site-packages/numpy" in fn or "numpy/" in fn:
        base_cat = "numpy-py"
    elif "interpolation" in fn or "econforgeinterp" in fn:
        base_cat = "HARK-interp"
    elif "LegacyOOsolvers" in fn:
        base_cat = "HARK-LegacyOOsolvers"
    elif "site-packages/HARK/distributions" in fn:
        base_cat = "HARK-distributions"
    elif "site-packages/HARK" in fn:
        base_cat = "HARK-other"
    elif "ConsMarkovModel" in fn:
        base_cat = "local-ConsMarkovModel"
    elif "HA-Fiscal-HANK-SAM" in fn:
        base_cat = "script"
    elif "xarray" in fn or "pandas" in fn:
        base_cat = "xarray/pandas"
    else:
        base_cat = "other"
    cats[base_cat] = cats.get(base_cat, 0.0) + tt
print(f"[l3] total function calls: {ncalls_total/1e6:.1f}M")
for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
    print(f"[l3] cat {k:26s} {v:7.2f}s  {v/total_tt:5.1%}")

buf = io.StringIO()
st.stream = buf
st.sort_stats("cumulative").print_stats(28)
print("\n=== top cumulative ===")
print("\n".join(buf.getvalue().splitlines()[4:40]))
buf2 = io.StringIO(); st.stream = buf2
st.sort_stats("tottime").print_stats(22)
print("\n=== top tottime ===")
print("\n".join(buf2.getvalue().splitlines()[4:34]))
