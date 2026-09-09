"""Owner Q 2026-08-07: JAX as the compiled-matvec substrate for the parked
SoA layout. Micro-benchmark on the real 132-state snapshot parts:
dict/numpy vs soa/numpy vs soa/jax.jit (x64, CPU), correctness-checked."""
import os, sys, time, pickle
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_ENABLE_X64", "1")
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]

from hark_fti.consumed_block_core import (residual_parts_generic,
                                          apply_jacobian_generic)
from HARK.interpolation import LinearInterp
cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
N = len(hb)
X0 = np.array([np.maximum(MPCmin * (aG + hb[b]), 1e-10) for b in range(N)])
kw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
          cFuncCnst=cnst, CRRA=meta["CRRA"], DiscFacEff=meta["DiscFacEff"],
          tail_form="powerlaw", tail_Q=None)
pd_ = residual_parts_generic(X0, pairs_layout="dict", **kw)
ps_ = residual_parts_generic(X0, pairs_layout="soa", **kw)
J = ps_["J"]
U = np.random.default_rng(3).standard_normal(X0.shape)

import jax
import jax.numpy as jnp
print(f"[jaxmv] jax {jax.__version__} devices={jax.devices()} "
      f"x64={jax.config.jax_enable_x64}", flush=True)

groups = [{k: jnp.asarray(g[k]) for k in
           ("src", "tgt", "gcol", "gdata", "dec_p", "dec_q")}
          for g in ps_["pairs"]]
diag = jnp.asarray(ps_["diag_own"])

@jax.jit
def jax_matvec(Uj):
    out = diag * Uj
    u = Uj.ravel()
    for g in groups:  # unrolled at trace time (few K-groups)
        contrib = jnp.einsum('pjk,pjk->pj', g["gdata"], u[g["gcol"]])
        base = g["tgt"].astype(jnp.int64) * J
        contrib += g["dec_p"] * u[base + J - 1][:, None]
        contrib += g["dec_q"] * u[base + J - 2][:, None]
        out = out.at[g["src"]].add(contrib)
    return out

Uj = jnp.asarray(U)
t0 = time.time(); y_jax = np.asarray(jax_matvec(Uj)); compile_s = time.time() - t0
y_dict = apply_jacobian_generic(U, pd_)
dev = np.max(np.abs(y_jax - y_dict)) / (np.max(np.abs(y_dict)) + 1.0)
print(f"[jaxmv] compile+first-call {compile_s:.2f}s  vs-dict dev={dev:.2e}",
      flush=True)

for tag, fn in (("dict/numpy", lambda: apply_jacobian_generic(U, pd_)),
                ("soa/numpy", lambda: apply_jacobian_generic(U, ps_)),
                ("soa/jax.jit", lambda: jax_matvec(Uj).block_until_ready())):
    fn()
    t0 = time.time()
    for _ in range(50):
        fn()
    print(f"[jaxmv] {tag}: {(time.time()-t0)/50*1000:.1f} ms", flush=True)

# with numpy->jax input conversion per call (the GMRES-integration cost)
t0 = time.time()
for _ in range(50):
    jax_matvec(jnp.asarray(U)).block_until_ready()
print(f"[jaxmv] soa/jax.jit incl. np->jax per call: "
      f"{(time.time()-t0)/50*1000:.1f} ms", flush=True)
print("[jaxmv] DONE", flush=True)
