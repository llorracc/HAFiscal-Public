"""P5c (Econ-9 step 0c): compare the per-cell 0.14.1 committed-calibration transfers blocks (p5b) with the pickle's
education-group blocks (p5a; the pickle's C_by_educ[e] = mean over the 7 beta atoms of that group)."""
import glob, os, sys, numpy as np
OUT = sys.argv[1]; S = 10
pk = np.load(os.path.join(OUT, "p5a_pickle_blocks.npz"))
cells = {}
for f in sorted(glob.glob(os.path.join(OUT, "p5b_cell_e*_d*.npz"))):
    z = np.load(f); cells[(int(z["e"]), int(z["d"]))] = z
names = {0: "dropout", 1: "highschool", 2: "college"}
np.set_printoptions(precision=7, linewidth=220, suppress=True)
print(f"{len(cells)} cells computed: {sorted(cells)}")
for e in range(3):
    have = sorted(d for (ee, d) in cells if ee == e)
    if not have: continue
    print(f"\n=== {names[e]}: per-cell transfers J_C[0,0] (committed calibration, HARK 0.14.1, bigT=300 semantics)")
    for d in have:
        z = cells[(e, d)]
        print(f"  d={d} beta={float(z['beta']):.6f} C_ss={float(z['C_ss']):.7f} A_ss={float(z['A_ss']):.5f}  J_C[0,0]={z['JC'][0,0]:.7f} "
              f"J_C[1,0]={z['JC'][1,0]:.7f} J_C[0,1]={z['JC'][0,1]:.7f} J_C[1,1]={z['JC'][1,1]:.7f} J_C[9,9]={z['JC'][9,9]:.7f} J_A[0,0]={z['JA'][0,0]:.7f}")
        if "JC_verbatim10" in z.files:
            print(f"     validation: max|mine(T10)-verbatim(bigT=10)| C={np.max(np.abs(z['JC_T10']-z['JC_verbatim10'])):.3e} "
                  f"A={np.max(np.abs(z['JA_T10']-z['JA_verbatim10'])):.3e}; max|mine(T300)-mine(T10)| C={np.max(np.abs(z['JC']-z['JC_T10'])):.3e}")
    for tag in ("QE_d38bf6be", "OLD_ca079869"):
        PC = pk[f"{tag}_C_{names[e]}"]; PA = pk[f"{tag}_A_{names[e]}"]
        if len(have) == 7:
            MC = np.mean([cells[(e, d)]["JC"] for d in have], axis=0); MA = np.mean([cells[(e, d)]["JA"] for d in have], axis=0)
            dC = MC - PC; dA = MA - PA
            print(f"  [{tag}] 7-atom MEAN vs pickle {names[e]} block (10x10): J_C[0,0] mine={MC[0,0]:.9f} pickle={PC[0,0]:.9f} "
                  f"diff={dC[0,0]:+.3e} rel={dC[0,0]/PC[0,0]:+.3e}")
            print(f"       max|dC|={np.max(np.abs(dC)):.3e} (at {np.unravel_index(np.argmax(np.abs(dC)), dC.shape)}), "
                  f"max rel|dC|/|pickle| (|pickle|>1e-3) = {np.max(np.abs(dC)[np.abs(PC) > 1e-3] / np.abs(PC)[np.abs(PC) > 1e-3]):.3e}; "
                  f"max|dA|={np.max(np.abs(dA)):.3e}, J_A[0,0] mine={MA[0,0]:.9f} pickle={PA[0,0]:.9f}")
            print(f"       row0 mine   {MC[0,:6]}\n       row0 pickle {PC[0,:6]}\n       col0 mine   {MC[:6,0]}\n       col0 pickle {PC[:6,0]}")
        else:
            vals = [cells[(e, d)]["JC"][0, 0] for d in have]
            print(f"  [{tag}] pickle {names[e]} J_C[0,0]={PC[0,0]:.7f}; computed cells d={have} give {np.round(vals,7).tolist()} "
                  f"(a 7-atom mean cannot be formed; single cells bound/locate the mean only)")
print("P5c DONE")
# aggregate check (needs all 21 cells): C == sum_e w_e * mean_d J[e,d]
if len(cells) == 21:
    w = [0.093, 0.527, 0.38]
    for tag in ("QE_d38bf6be", "OLD_ca079869"):
        MC = sum(w[e] * np.mean([cells[(e, d)]["JC"] for d in range(7)], axis=0) for e in range(3))
        MA = sum(w[e] * np.mean([cells[(e, d)]["JA"] for d in range(7)], axis=0) for e in range(3))
        PC = pk[f"{tag}_C_agg"]; PA = pk[f"{tag}_A_agg"]
        print(f"\n=== AGGREGATE (21 cells, weights 0.093/0.527/0.38) vs pickle [{tag}] transfers 10x10 block: "
              f"J_C[0,0] mine={MC[0,0]:.9f} pickle={PC[0,0]:.9f} diff={MC[0,0]-PC[0,0]:+.3e}; max|dC|={np.max(np.abs(MC-PC)):.3e} "
              f"max|dA|={np.max(np.abs(MA-PA)):.3e}; J_A[0,0] mine={MA[0,0]:.9f} pickle={PA[0,0]:.9f}")
    # 21-cell weighted SS (same weights, /7) for the GE-script literals
    C = sum(w[e] * float(cells[(e, d)]["C_ss"]) / 7 for e in range(3) for d in range(7))
    A = sum(w[e] * float(cells[(e, d)]["A_ss"]) / 7 for e in range(3) for d in range(7))
    print(f"=== 21-cell weighted SS (this run): C_ss_agg={C:.10f} A_ss_agg={A:.10f} vs GE-script literals C_ss_sim=0.6910496136078721 "
          f"A_ss_sim=1.4324029855872642 (dC={C-0.6910496136078721:+.3e}, dA={A-1.4324029855872642:+.3e}); p4 (2026-08-28) had 0.6985735834 / 1.7792840541")
