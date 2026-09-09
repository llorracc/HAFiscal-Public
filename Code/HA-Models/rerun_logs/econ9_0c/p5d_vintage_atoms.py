"""P5d: the 7 beta atoms per education group implied by each DiscFacEstim vintage in the Latest repo's history
(QE Parameters.py:265-272 rule: Uniform(b-n, b+n).discretize(7), capped at GICmaxBetas[e]*GICfactor(GICx), floored
at minBeta), so the pickle-vs-pickle and cell-vs-pickle differences can be attributed. Read-only."""
import subprocess, numpy as np, sys, os
os.chdir("/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"); sys.path.insert(0, os.getcwd()); sys.argv = sys.argv[:1]
from HARK.distribution import Uniform
import EstimParameters as EP
GICmaxBetas, minBeta = EP.GICmaxBetas, EP.minBeta
print("GICmaxBetas", GICmaxBetas, "minBeta", minBeta)
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"; F = "Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt"
hs = subprocess.run(["git", "-C", REPO, "log", "--format=%h %ad", "--date=short", "--", F], capture_output=True, text=True).stdout.split("\n")
def atoms(b, n, gicx, e):
    dfs = Uniform(b - n, b + n).discretize(7); gf = np.exp(gicx) / (1 + np.exp(gicx)); a = dfs.atoms[0].copy()
    for i in range(7):
        if a[i] > GICmaxBetas[e] * gf: a[i] = GICmaxBetas[e] * gf
        elif a[i] < minBeta: a[i] = minBeta
    return a
ref = None
QE_HASH = "93a22a3e"
rows_all = []
for line in [h for h in hs if h.strip()]:
    h, date = line.split()
    txt = subprocess.run(["git", "-C", REPO, "show", f"{h}:{F}"], capture_output=True, text=True).stdout
    rows = {}
    for l in txt.split("\n"):
        if l.startswith("{"):
            d = eval(l, {"np": np}); rows[d["EducationGroup"]] = (float(d["beta"]), float(d["nabla"]), float(d.get("GICx", np.nan)))
    if len(rows) < 3 or any(np.isnan(rows[e][2]) for e in rows):
        print(f"{h} {date}: no GICx (pre-2023 format) -> skipped"); continue
    A = {e: atoms(*rows[e], e) for e in range(3)}
    rows_all.append((h, date, rows, A))
for (h, date, rows, A) in rows_all:
    if h == QE_HASH: ref = A
print(f"REFERENCE for max|atom-QEatom| = {QE_HASH} (2025-11-17, the committed QE calibration)")
for (h, date, rows, A) in rows_all:
    for e, nm in enumerate(("dropout", "HS", "college")):
        print(f"   {h} {date} {nm:8s} beta={rows[e][0]:.6f} nabla={rows[e][1]:.6f} atoms={np.round(A[e],5).tolist()} "
              f"max|atom-QEatom|={np.max(np.abs(A[e]-ref[e])):.2e} capped={int(np.sum(A[e] >= GICmaxBetas[e]*np.exp(rows[e][2])/(1+np.exp(rows[e][2])) - 1e-12))}")
