"""Proper sequence-space determinacy test (Auclert-Bardoczy-Rognlie-Straub winding number)
alongside the colleague's far-news metric, on one grid of phi_pi.

H_U is asymptotically Toeplitz; read its symbol off a middle row, form the 2x2 matrix
symbol H(z) on |z|=1, and count the winding number of det H(z).  Determinate <=> winding 0
and det never 0 on the circle.
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
Jt = dict(J0); Jt['C'] = tr(J0['C']); Jt['A'] = tr(J0['A'])
Jt['C_by_educ'] = {e: tr(v) for e, v in J0['C_by_educ'].items()}
Jt['A_by_educ'] = {e: tr(v) for e, v in J0['A_by_educ'].items()}
tp = os.path.join(SCR, f'jt{T}_{os.path.basename(JACS)}.obj')
pickle.dump(Jt, open(tp, 'wb')); del J0
os.environ['HAFISCAL_HANK_BIGT'] = str(T)
from step4 import ge
ge.JACS_OBJ = tp
from sequence_jacobian.blocks.block import Block
ORIG = Block.solve_impulse_linear
CAP = {}
class Stop(Exception):
    pass
def pat(self, ss, unknowns, targets, inputs, **kw):
    CAP.update(model=self, ss=ss, unk=list(unknowns), tgt=list(targets)); raise Stop()
Block.solve_impulse_linear = pat
os.chdir(FPC)
try:
    ge.run()
except Stop:
    pass
Block.solve_impulse_linear = ORIG
model, ss0, unk, tgt = CAP['model'], CAP['ss'], CAP['unk'], CAP['tgt']
C_ss = float(ss0['C']); R = 1.01
nU = len(unk)
print(f"[capture] T={T} unk={unk} tgt={tgt}", flush=True)

NTH = 2048
th = 2 * np.pi * np.arange(NTH) / NTH
z = np.exp(1j * th)

def winding(H_U, T, nU, half=None):
    t0 = T // 2
    half = half if half is not None else T // 2 - 1
    ks = np.arange(-half, half + 1)
    # symbol matrix on the circle
    S = np.zeros((NTH, nU, nU), dtype=complex)
    for i in range(nU):
        for j in range(nU):
            B = H_U[i*T:(i+1)*T, j*T:(j+1)*T]
            coef = np.array([B[t0, t0 - k] for k in ks])       # H_k, k = t-s
            S[:, i, j] = (coef[None, :] * z[:, None] ** ks[None, :]).sum(1)
    d = np.linalg.det(S)
    ang = np.unwrap(np.angle(d))
    w = (ang[-1] - ang[0] + (ang[1] - ang[0])) / (2 * np.pi)   # close the loop
    return float(w), float(np.min(np.abs(d))), float(np.max(np.abs(d)))

rows = []
for p in PHIS:
    t0_ = time.time()
    ssv = deepcopy(ss0); ssv['phi_pi'] = p
    H_U = model.jacobian(ssv, unk, tgt, T).pack(T)
    sv = np.linalg.svd(H_U, compute_uv=False)
    w, dmin, dmax = winding(H_U, T, nU)
    w2, _, _ = winding(H_U, T, nU, half=T // 4)     # robustness to symbol truncation
    H_Z = model.jacobian(ssv, ['transfers'], tgt, T).pack(T)
    dUdZ = -np.linalg.solve(H_U, H_Z)
    JJ = model.jacobian(ssv, ['transfers'] + unk, ['C'], T)
    G = np.asarray(JJ['C']['transfers']).copy()
    for j, u in enumerate(unk):
        if u in JJ['C']:
            G = G + np.asarray(JJ['C'][u]) @ dUdZ[j*T:(j+1)*T]
    r0 = G[0]
    mid = float(np.mean(np.abs(r0[T//3:2*T//3])))
    dtr = np.zeros(T); dtr[0] = C_ss * .05
    mult = float(np.sum((G @ dtr)[:21] / R ** np.arange(21)) / (C_ss * .05))
    rows.append(dict(phi_pi=p, T=T, cond=float(sv[0]/sv[-1]), smin=float(sv[-1]),
                     wind=w, wind_half=w2, detmin=dmin, detmax=dmax,
                     mid_abs=mid, mult_tr=mult, secs=time.time()-t0_))
    d = rows[-1]
    print(f"phi={p:<6} wind={w:+.4f} (half {w2:+.4f}) |det|min={dmin:.3e} ratio={dmin/dmax:.2e} "
          f"cond={d['cond']:.2e} mid|g|={mid:.4e} mult={mult:.4f} ({d['secs']:.1f}s)", flush=True)
    json.dump(rows, open(OUT, 'w'), indent=1)
print('[done]', flush=True)
