"""BUG-093 B-vs-C harvest: welfare6 cells (S=3 mean ± SE) for the two consistent constructions vs the
pre-fix sharing battery (eq: Doob start + plain kernel) and the own-loop MC battery (r2), Baseline default
world. Reads Tables/Baseline_<arm>_seed<K>/welfare6_parallel_summary.json (full precision)."""
import json, os, sys, numpy as np
T = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Tables"
ARMS = [("r2", "own-loop MC (r2)"), ("eq", "sharing, PRE-fix"), ("qbst", "C: bst (plain)"), ("qdoob", "B: doob (true)")]
if len(sys.argv) > 1:      # extra arms, e.g. wtK200 (the weighted-tail panel on the doob equilibria)
    ARMS += [(a, a) for a in sys.argv[1:]]
CELLS = ["check_norec", "taxcut_norec", "check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]
data = {}
for arm, _ in ARMS:
    rows = []
    for k in range(3):
        p = f"{T}/Baseline_{arm}_seed{k}/welfare6_parallel_summary.json"
        if os.path.exists(p): rows.append(json.load(open(p))["welfare6"])
    data[arm] = rows
def stat(arm, c):
    v = np.array([r[c] for r in data[arm]], float); return v.mean(), v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else np.nan, len(v)
print(f"{'cell':14s}" + "".join(f"{lab:>26s}" for _, lab in ARMS))
for c in CELLS:
    line = f"{c:14s}"
    for arm, _ in ARMS:
        m, se, n = stat(arm, c); line += f"{m:14.4f} ±{se:6.4f} (S={n})"
    print(line)
print("\nrelative differences on the AD cells (S=3 means):")
for c in ["check_rec_AD", "ui_rec_AD", "taxcut_rec_AD", "check_rec", "check_norec"]:
    r2, eq, cb, cd = (stat(a, c)[0] for a in ("r2", "eq", "qbst", "qdoob"))
    extra = "".join(f" | {a} vs B {stat(a, c)[0]/cd-1:+.2%} (vs own-loop {stat(a, c)[0]/r2-1:+.2%})" for a, _ in ARMS[4:] if data[a])
    print(f"  {c:14s} B/C-1 = {cd/cb-1:+.2%} | B vs own-loop {cd/r2-1:+.2%} | C vs own-loop {cb/r2-1:+.2%} | pre-fix sharing vs own-loop {eq/r2-1:+.2%}{extra}")
