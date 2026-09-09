"""P1: fingerprint the PUBLISHED Jacobian pickle (HAFiscal-QE/.../HA_Fiscal_Jacs.obj) for the BUG-072 and BUG-075
mechanisms. Read-only. BUG-072: the zeroth-column agent is solved at baseline and DiscFac is not read by the
transition matrices => J[:,0] for DiscFac must be identically ZERO in the shipped artifact if the published code
carried the defect. BUG-075: the fake-news rows are differenced against the static SS; any convergence drift of the
unshocked backward chain shows up as an INSTRUMENT-INDEPENDENT offset in F[0,s]=J[0,s] at large s (where the true
anticipation response is negligible)."""
import pickle, numpy as np, sys
P = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj"
with open(P, "rb") as f:
    J = pickle.load(f)
print("keys:", list(J.keys()))
print("C instruments:", list(J["C"].keys()))
np.set_printoptions(precision=5, linewidth=160, suppress=False)
for k in J["C"]:
    M = np.asarray(J["C"][k]); A = np.asarray(J["A"][k])
    print(f"\n[{k}] shape {M.shape}")
    print(f"  col 0 (J[:,0]) max|.| C={np.max(np.abs(M[:,0])):.3e} A={np.max(np.abs(A[:,0])):.3e}; "
          f"J_C[0,0]={M[0,0]:.5f} J_C[1,0]={M[1,0]:.5f} J_C[5,0]={M[5,0]:.5f}")
    cols = [0, 1, 2, 5, 10, 20, 50, 100, 200, 250, 290, 299]
    print("  row 0 J_C[0,s] at s=", cols)
    print("   ", np.array([M[0, s] for s in cols]))
    print("  diag J_C[s,s] at s=", cols)
    print("   ", np.array([M[s, s] for s in cols]))
# instrument-independence of the far-column row-0 entries (drift fingerprint)
print("\nrow-0 tail across instruments (s=200,250,290,299):")
for k in J["C"]:
    M = np.asarray(J["C"][k]); print(f"  {k:10s}", np.array([M[0, s] for s in (200, 250, 290, 299)]))
print("\nby-educ college, row 0 tail:")
for k in J["C_by_educ"]["college"]:
    M = np.asarray(J["C_by_educ"]["college"][k]); print(f"  {k:10s}", np.array([M[0, s] for s in (0, 1, 10, 100, 200, 299)]),
                                                        " col0 max", f"{np.max(np.abs(M[:,0])):.3e}")
print("\nby-educ dropout, row 0 tail:")
for k in J["C_by_educ"]["dropout"]:
    M = np.asarray(J["C_by_educ"]["dropout"][k]); print(f"  {k:10s}", np.array([M[0, s] for s in (0, 1, 10, 100, 200, 299)]),
                                                        " col0 max", f"{np.max(np.abs(M[:,0])):.3e}")
print("P1 DONE")
