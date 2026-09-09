"""Independent re-measurement of the phi_pi ladder.

Two routes to dC_0/d(transfers_s):
  A) matrix route: G = J_C_tr + sum_u J_C_u @ dU/dZ with dU/dZ = -H_U^{-1} H_Z (as the colleague did)
  B) library route: model.solve_impulse_linear with a unit impulse at date s, read dC[0].
Route B is fully independent of my/their linear algebra. Both are reported.
"""
import os, sys, pickle, json, time
from copy import deepcopy
import numpy as np

JACS = sys.argv[1]; T = int(sys.argv[2]); PHIS = [float(x) for x in sys.argv[3].split(',')]
OUT = sys.argv[4]; SCR = os.path.dirname(OUT)
sys.argv = [sys.argv[0]]
os.environ.setdefault('MPLBACKEND', 'Agg')
HA = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models'
FPC = HA + '/FromPandemicCode'
sys.path.insert(0, HA); sys.path.insert(0, FPC)

J0 = pickle.load(open(JACS, 'rb'))
def tr(d):
    return {k: np.asarray(v)[:T, :T].copy() for k, v in d.items()}
Jt = dict(J0)
Jt['C'] = tr(J0['C']); Jt['A'] = tr(J0['A'])
Jt['C_by_educ'] = {e: tr(v) for e, v in J0['C_by_educ'].items()}
Jt['A_by_educ'] = {e: tr(v) for e, v in J0['A_by_educ'].items()}
tp = os.path.join(SCR, f'jt{T}_{os.path.basename(JACS)}.obj')
pickle.dump(Jt, open(tp, 'wb'))
del J0

os.environ['HAFISCAL_HANK_BIGT'] = str(T)
from step4 import ge
ge.JACS_OBJ = tp
from sequence_jacobian.blocks.block import Block
ORIG = Block.solve_impulse_linear
CAP = {}
class Stop(Exception):
    pass
def pat(self, ss, unknowns, targets, inputs, **kw):
    CAP.update(model=self, ss=ss, unk=list(unknowns), tgt=list(targets))
    raise Stop()
Block.solve_impulse_linear = pat
os.chdir(FPC)
try:
    ge.run()
except Stop:
    pass
Block.solve_impulse_linear = ORIG

model, ss0, unk, tgt = CAP['model'], CAP['ss'], CAP['unk'], CAP['tgt']
C_ss = float(ss0['C']); R = 1.01
print(f"[capture] unknowns={unk} targets={tgt} phi_pi_ss={ss0['phi_pi']} "
      f"phi_b={ss0['phi_b']} phi_w={ss0['phi_w']} rho_r={ss0['rho_r']} phi_y={ss0['phi_y']} T={T}",
      flush=True)

SAMP = [T // 3, T // 2, 2 * T // 3 - 1]
rows = []
for p in PHIS:
    t0 = time.time()
    ssv = deepcopy(ss0); ssv['phi_pi'] = p
    H_U = model.jacobian(ssv, unk, tgt, T).pack(T)
    sv = np.linalg.svd(H_U, compute_uv=False)
    H_Z = model.jacobian(ssv, ['transfers'], tgt, T).pack(T)
    dUdZ = -np.linalg.solve(H_U, H_Z)
    resid = float(np.max(np.abs(H_U @ dUdZ + H_Z)) / max(np.max(np.abs(H_Z)), 1e-300))
    JJ = model.jacobian(ssv, ['transfers'] + unk, ['C'], T)
    G = np.asarray(JJ['C']['transfers']).copy()
    for j, u in enumerate(unk):
        if u in JJ['C']:
            G = G + np.asarray(JJ['C'][u]) @ dUdZ[j * T:(j + 1) * T]
    r0 = G[0]
    lo, hi = T // 3, 2 * T // 3
    mid = float(np.mean(np.abs(r0[lo:hi])))
    # route B: library end-to-end, unit news impulse at s
    libB = {}
    for s in SAMP:
        d = np.zeros(T); d[s] = 1.0
        irf = ORIG(model, ssv, unk, tgt, {'transfers': d})
        libB[s] = float(np.asarray(irf['C'])[0])
    dtr = np.zeros(T); dtr[0] = C_ss * .05
    Cpath = G @ dtr
    mult = float(np.sum(Cpath[:21] / R ** np.arange(21)) / (C_ss * .05))
    rows.append(dict(phi_pi=p, T=T, cond=float(sv[0] / sv[-1]), smin=float(sv[-1]),
                     ge_resid=resid, mid_abs=mid,
                     q2_abs=float(np.mean(np.abs(r0[T//6:T//3]))),
                     q4_abs=float(np.mean(np.abs(r0[2*T//3:]))),
                     g0=float(r0[0]), gmid=float(r0[T//2]), gTm5=float(r0[T-5]),
                     rowmax=float(np.max(np.abs(r0))), mult_tr=mult,
                     A_at=[float(r0[s]) for s in SAMP], B_at=[libB[s] for s in SAMP],
                     secs=time.time() - t0))
    d = rows[-1]
    ab = max(abs(a - b) / max(abs(a), 1e-300) for a, b in zip(d['A_at'], d['B_at']))
    print(f"phi={p:<6} cond={d['cond']:.3e} resid={resid:.1e} g0={d['g0']:.4e} "
          f"gmid={d['gmid']:.3e} mid|g|={mid:.4e} q4|g|={d['q4_abs']:.3e} mult={mult:.4f} "
          f"A/B-maxrel={ab:.2e} ({d['secs']:.1f}s)", flush=True)
    json.dump(rows, open(OUT, 'w'), indent=1)
print('[done]', flush=True)
