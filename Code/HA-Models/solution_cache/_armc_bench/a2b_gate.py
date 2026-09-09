"""A2b GO/NO-GO (plan 20260807-0919h): numba lite residual on the real
132-state snapshot vs the python lite path. GO requires numba lite
<= 0.30 s (python reference 0.64); gray zone 0.30-0.40 per §AUTONOMY.
Also reports snapshot-scale parity (recorded gate <= 1e-13 rel) and the
per-iterate pack overhead."""
import sys, time, pickle
import numpy as np

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"

with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"]
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]

from HARK.interpolation import LinearInterp
from hark_fti.consumed_block_core import (_state_continuation,
                                          residual_parts_generic)
from hark_fti.consumed_numba_lite import (lite_residual, pack_iterate,
                                          pack_static)

cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
N = len(hb)
X0 = np.array([np.maximum(MPCmin * (aG + hb[b]), 1e-10) for b in range(N)])
kw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
          cFuncCnst=cnst, CRRA=CRRA, DiscFacEff=DFE,
          tail_form="powerlaw", tail_Q=None)

t0 = time.time()
ref = residual_parts_generic(X0, want_jac=False, **kw)
t_py1 = time.time() - t0
assert ref is not None
t0 = time.time()
NPY = 5
for _ in range(NPY):
    residual_parts_generic(X0, want_jac=False, **kw)
t_py = (time.time() - t0) / NPY
print(f"[a2b] python lite: {t_py:.3f} s/eval (first {t_py1:.3f}; ref 0.64)",
      flush=True)

conts = [_state_continuation(X0[b], aG, hb[b], MPCmin, cnst,
                             tail_form="powerlaw", tail_Q=None)
         for b in range(N)]
t0 = time.time()
sp = pack_static(edges, rb, DFE)
t_pack = time.time() - t0
nat = sp["atG"].size
print(f"[a2b] static pack: {t_pack:.3f} s  (edges={sp['eg_src'].size} "
      f"tes={sp['te_b'].size} atoms={nat})", flush=True)

t0 = time.time()
F = lite_residual(X0, aG, conts, sp, CRRA)   # includes JIT compile
t_first = time.time() - t0
assert F is not None
dev = float(np.max(np.abs(F - ref["F"]) / (1.0 + np.abs(ref["F"]))))
print(f"[a2b] numba first call (incl. compile): {t_first:.2f} s  "
      f"snapshot parity dev={dev:.2e} (gate 1e-13)", flush=True)

NB = 20
t0 = time.time()
for _ in range(NB):
    lite_residual(X0, aG, conts, sp, CRRA)
t_nb = (time.time() - t0) / NB
t0 = time.time()
for _ in range(NB):
    pack_iterate(X0, aG, conts)
t_pi = (time.time() - t0) / NB
verdict = ("GO" if t_nb <= 0.30 else
           "GRAY" if t_nb <= 0.40 else "NO-GO")
print(f"[a2b] numba lite: {t_nb:.3f} s/eval (iterate-pack {t_pi:.3f} of it)"
      f"  speedup {t_py/t_nb:.1f}x  => {verdict} (GO<=0.30, gray<=0.40)",
      flush=True)
print("[a2b] DONE", flush=True)
