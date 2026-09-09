#!/usr/bin/env python
"""Assemble the HANK ladder tables (markdown) from per-arm summary.json / wall.txt.
usage: make_ladder.py <root> arm[:label[:ref]] ...   ref = arm whose values the Δ% refer to (default: previous row)"""
import json, os, re, sys
root = sys.argv[1]
POLS = (("transfers", "check"), ("UI_extensions", "UI"), ("tax_cut", "tax cut"))
rows = []
for spec in sys.argv[2:]:
    parts = spec.split(":"); name = parts[0]; lab = parts[1] if len(parts) > 1 and parts[1] else name
    ref = parts[2] if len(parts) > 2 and parts[2] else (rows[-1]["name"] if rows else None)
    d = os.path.join(root, name); sj = json.load(open(os.path.join(d, "summary.json")))
    wall = open(os.path.join(d, "wall.txt")).read()
    wj = re.search(r"jacobians rc=(\d+) wall_s=(\d+)", wall); wg = re.search(r"ge rc=(\d+) wall_s=(\d+)", wall)
    rss = re.search(r"(\d+)\s+maximum resident", wall)
    rows.append({"name": name, "lab": lab, "ref": ref, "sj": sj,
                 "wall": (f"{int(wj.group(2))/60:.1f} min" if wj else "GE only") + (f" + {int(wg.group(2))} s" if wg else ""),
                 "rss": f"{int(rss.group(1))/2**30:.1f} GB" if rss else "—"})
byname = {r["name"]: r for r in rows}

def cell(r, key, pol, reg):
    v = r["sj"]["cells"][f"{pol}/{reg}"][key]
    if r["ref"] and r["ref"] in byname:
        v0 = byname[r["ref"]]["sj"]["cells"][f"{pol}/{reg}"][key]
        return f"{v:.4f} ({(v/v0-1)*100:+.1f} %)"
    return f"{v:.4f}"

for reg, regname in (("taylor", "active Taylor rule"), ("fixed_real", "fixed real rate"), ("fixed_nominal", "fixed nominal rate")):
    print(f"\n#### {regname}: IRF peak (max over quarters 1–12 of 100·ΔC_t/C_ss) and cumulative consumption multiplier at h = 20 (NPV(ΔC, 20q)/NPV(cost, 300q)); Δ % vs the row's reference arm")
    print("| arm | ref | check IRF pk | UI IRF pk | tax IRF pk | check cum20 | UI cum20 | tax cum20 |"); print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        c = [cell(r, "irf_peak_pct", p, reg) for p, _ in POLS] + [cell(r, "cum_h20", p, reg) for p, _ in POLS]
        print(f"| {r['lab']} | {byname[r['ref']]['lab'] if r['ref'] in byname else '—'} | " + " | ".join(c) + " |")

print("\n#### As emitted: the multiplier pickle (`multipliers_across_horizon_w_splurge.obj`, the `Cumulative_multipliers_withHank` feed) — value at h = 20 (= the series' peak in every arm) and its regime; the GE's printed NPV output multipliers NPV(ΔY)/NPV(cost); steady state; wall")
print("| arm | pickle check | pickle UI | pickle tax | output mult. check T/FN/FR | UI T/FN/FR | tax T/FN/FR | C_ss | A_ss | Jac wall + GE | peak RSS |"); print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    sj = r["sj"]; pk = sj["pickle"]; n = sj["npv_output_multipliers"]
    def g(k): return f"{n[k]:.3f}" if k in n else "—"
    def regof(p):
        v = pk[p]["series"]; 
        for reg in ("taylor", "fixed_nominal", "fixed_real"):
            if all(abs(a - b) < 1e-8 for a, b in zip(v, sj["cells"][f"{p}/{reg}"]["cum_20h"])): return {"taylor": "T", "fixed_nominal": "FN", "fixed_real": "FR"}[reg]
        return "?"
    tr = "/".join(g(k) for k in ("transfers (active taylor rule)", "transfers (fixed nominal rate)", "transfers (fixed real rate)"))
    ui = "/".join(g(k) for k in ("2Q UI extension (active taylor rule)", "2Q UI extension (fixed nominal rate)", "2Q UI extension (fixed real rate)"))
    tx = "/".join(g(k) for k in ("tax cut", "tax cut (fixed nominal rate)", "tax cut (fixed real rate)"))
    ss = sj["ss"]
    print(f"| {r['lab']} | {pk['transfers']['h20']:.4f} ({regof('transfers')}) | {pk['UI_extensions']['h20']:.4f} ({regof('UI_extensions')}) | {pk['tax_cut']['h20']:.4f} ({regof('tax_cut')}) | {tr} | {ui} | {tx} | {ss.get('C_ss', float('nan')):.5f} | {ss.get('A_ss', float('nan')):.4f} | {r['wall']} | {r['rss']} |")
