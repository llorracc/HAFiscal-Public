import glob, re, numpy as np
rows = {}
for f in sorted(glob.glob("p4_d*.out")):
    for line in open(f):
        m = re.match(r"ROW (\d) (\d) ([abc]) ([\d.]+) ([-\d.e]+) ([-\d.e]+)", line)
        if m:
            e, d, tag = int(m.group(1)), int(m.group(2)), m.group(3)
            rows[(e, d, tag)] = (float(m.group(4)), float(m.group(5)), float(m.group(6)))
w = [0.093, 0.527, 0.38]; nd = 7
print(f"{len(rows)} rows of 63")
for tag, name in (("a", "published: Gamma=1 solve, R transition"), ("b", "BUG-073 fix as built: Gamma_e solve, R transition"),
                  ("c", "consistent: Gamma_e solve, R/Gamma_e transition")):
    have = [(e, d) for e in range(3) for d in range(nd) if (e, d, tag) in rows]
    if len(have) < 21:
        print(f"[{tag}] incomplete: {len(have)}/21"); continue
    C = sum(w[e] * rows[(e, d, tag)][1] / nd for e in range(3) for d in range(nd))
    A = sum(w[e] * rows[(e, d, tag)][2] / nd for e in range(3) for d in range(nd))
    print(f"[{tag}] {name:55s} C_ss_agg={C:.10f} A_ss_agg={A:.10f}")
    if tag == "a":
        print(f"      GE script literals: C_ss_sim=0.6910496136078721 A_ss_sim=1.4324029855872642 -> "
              f"dC={C-0.6910496136078721:+.3e} dA={A-1.4324029855872642:+.3e}")
print("\nper-cell A_ss (rows e=dropout/HS/college; columns beta index 0..6):")
for tag in "abc":
    print(f" [{tag}]")
    for e in range(3):
        print("   ", " ".join(f"{rows[(e,d,tag)][2]:8.4f}" if (e, d, tag) in rows else "   ---  " for d in range(nd)))
print("\nper-cell C_ss:")
for tag in "abc":
    print(f" [{tag}]")
    for e in range(3):
        print("   ", " ".join(f"{rows[(e,d,tag)][1]:8.5f}" if (e, d, tag) in rows else "   ---  " for d in range(nd)))
