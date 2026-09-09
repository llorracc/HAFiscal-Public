"""P5a (Econ-9 step 0c): fingerprint the PUBLISHED HANK Jacobian pickle (HAFiscal-QE HA_Fiscal_Jacs.obj == Latest
blob 63c6c111 at d38bf6be 2025-11-17 'edmunds full run') and the PRIOR tracked blob (3c68804f at ca079869 2025-11-16).
Reports the top-left entries of the transfers Jacobian per education group and in aggregate, checks the pickle's
internal aggregation (C == sum_e w_e C_by_educ[e], weights 0.093/0.527/0.38 as in the QE script), and saves the
10x10 transfers blocks for the per-cell comparison (p5c). Read-only."""
import pickle, numpy as np, sys, os
OUT = sys.argv[1]
P_QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj"
P_OLD = os.path.join(OUT, "HA_Fiscal_Jacs_20251116_3c68804f.obj")
S = 10; w = {"dropout": 0.093, "highschool": 0.527, "college": 0.38}
ents = [(0,0),(1,0),(2,0),(5,0),(0,1),(0,2),(0,5),(0,9),(1,1),(2,2),(5,5),(9,9)]
np.set_printoptions(precision=6, linewidth=200)
save = {}
for tag, P in (("QE_d38bf6be", P_QE), ("OLD_ca079869", P_OLD)):
    J = pickle.load(open(P, "rb"))
    print(f"\n===== {tag}: {P}\nkeys {list(J.keys())}; instruments {list(J['C'].keys())}; shape {np.asarray(J['C']['transfers']).shape}")
    for educ in ("dropout", "highschool", "college"):
        M = np.asarray(J["C_by_educ"][educ]["transfers"]); A = np.asarray(J["A_by_educ"][educ]["transfers"])
        save[f"{tag}_C_{educ}"] = M[:S, :S]; save[f"{tag}_A_{educ}"] = A[:S, :S]
        print(f"  [{educ:10s} transfers] J_C: " + "  ".join(f"[{t},{s}]={M[t,s]:.7f}" for t, s in ents))
        print(f"  [{educ:10s} transfers] J_A: " + "  ".join(f"[{t},{s}]={A[t,s]:.7f}" for t, s in ents[:5]))
    M = np.asarray(J["C"]["transfers"]); A = np.asarray(J["A"]["transfers"])
    save[f"{tag}_C_agg"] = M[:S, :S]; save[f"{tag}_A_agg"] = A[:S, :S]
    print(f"  [aggregate  transfers] J_C: " + "  ".join(f"[{t},{s}]={M[t,s]:.7f}" for t, s in ents))
    # internal aggregation check, every instrument
    print("  aggregation check max|C[k] - sum_e w_e C_by_educ[e][k]| per instrument:")
    for k in J["C"]:
        agg = sum(w[e] * np.asarray(J["C_by_educ"][e][k]) for e in w)
        print(f"    {k:10s} {np.max(np.abs(np.asarray(J['C'][k]) - agg)):.3e}   (max|C[k]| = {np.max(np.abs(np.asarray(J['C'][k]))):.4e};"
              f" DiscFac col0 max = {np.max(np.abs(np.asarray(J['C'][k])[:,0])):.3e})" if k == "DiscFac" else
              f"    {k:10s} {np.max(np.abs(np.asarray(J['C'][k]) - agg)):.3e}   (max|C[k]| = {np.max(np.abs(np.asarray(J['C'][k]))):.4e})")
    save[f"{tag}_other_C00"] = {k: float(np.asarray(J["C"][k])[0, 0]) for k in J["C"]}
    print("  aggregate J_C[0,0] by instrument: " + "  ".join(f"{k}={v:.6f}" for k, v in save[f"{tag}_other_C00"].items()))
print("\n===== QE vs OLD pickle: max|diff| of C_by_educ transfers, per education, and of aggregate C per instrument")
for educ in w:
    print(f"  {educ:10s} {np.max(np.abs(save['QE_d38bf6be_C_'+educ] - save['OLD_ca079869_C_'+educ])):.3e} (10x10 block);"
          f" [0,0] QE={save['QE_d38bf6be_C_'+educ][0,0]:.7f} OLD={save['OLD_ca079869_C_'+educ][0,0]:.7f}")
Jq = pickle.load(open(P_QE, "rb")); Jo = pickle.load(open(P_OLD, "rb"))
for k in Jq["C"]:
    print(f"  agg {k:10s} max|QE-OLD| = {np.max(np.abs(np.asarray(Jq['C'][k]) - np.asarray(Jo['C'][k]))):.3e}")
np.savez(os.path.join(OUT, "p5a_pickle_blocks.npz"), **{k: v for k, v in save.items() if isinstance(v, np.ndarray)})
print("P5a DONE")
