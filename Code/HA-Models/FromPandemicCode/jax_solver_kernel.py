"""JAX EGM solver kernel for HAFiscal's AggFiscalType.

Replaces solve_agg_cons_markov_alt (AggFiscalModel.py:1704-1887) with a pure-JAX
equivalent. Operates on tabulated inputs (vPfuncNext + mNrmMinNext tables
extracted from HARK solution_next at fixed grids).

This is the P2+P3 deliverable: kernel covering full Ccount + multi-Markov-state.
P4 will validate at HAFiscal scale.

Reference math (matches AggFiscalModel.py:1704-1887):

  Loop 1 (per next-state j):
    EndOfPrdvP[j, c, a] = DiscFac * Σ_s pmv[j,s] * R[j] * psi[j,s]^(-rho)
                          * vPfuncNext[j](mNrmNext, Cnext)
    where mNrmNext = R[j]*aNrm/(G[j]*psi[j,s]) + ADF*xi[j,s]
          ADF = Cnext^(RecState[j] * elasticity)
          aNrm = aNrmMin[j,c] + aXtra[a]

  Loop 2 (per current state i):
    EndOfPrdvP_total[i, c, a] = LivPrb[i] * Σ_j MrkvArray[i,j] *
                                EndOfPrdvP_cond[j](aNrm_now, Cnext_ij)
    where Cnext_ij = CFunc[i,j] applied to Cgrid (linear: intercept + slope*(C-1))
          aNrm_now = aNrmMin_current[i,c] + aXtra[a]
          aNrmMin_current[i,c] = max_j (MrkvArray[i,j]>0) BoroCnstNat_cond[j](Cnext_ij)

    EGM: cNrm[i, c, a] = EndOfPrdvP_total^(-1/rho)
         mNrm[i, c, a] = aNrm_now[c, a] + cNrm[i, c, a]
"""
from __future__ import annotations
import jax
import jax.numpy as jnp
from functools import partial
from HARK.interpolation_jax import (linear_interp_1d, bilinear_interp,
                              linear_interp_on_interp_1d_general)


def _evaluate_vPfuncNext_table(table, m_eval, C_eval, m_query, C_query):
    """Bilinear interp into a (m_eval, C_eval) → vP table.

    table: shape (M_eval, C_eval) — vPfunc values at (m_eval[i], C_eval[j])
    m_query, C_query: broadcastable query points
    Returns vP at query points.
    """
    return bilinear_interp(table, m_eval, C_eval, m_query, C_query)


def _ad_factor(Cnext, RecState_int, ADelasticity):
    """ADF = Cnext ** (RecState * elasticity). RecState_int is 0 or 1."""
    return Cnext ** (RecState_int * ADelasticity)


def _loop1_one_next_state(
    vPfuncNext_table_j,      # (M_eval, C_eval) — tabulated vPfunc[j]
    mNrmMinNext_table_j,     # (C_eval,) — tabulated mNrmMin[j] as func of C
    mNrmMinNext_is_callable_j, # bool: True if mNrmMin[j] varies with C; False if scalar
    mNrmMinNext_scalar_j,    # scalar fallback if not callable
    m_eval, C_eval,          # eval grids for vPfunc lookup
    IncShk_pmv_j,            # (ShkCount,)
    IncShk_perm_j,           # (ShkCount,)
    IncShk_tran_j,           # (ShkCount,)
    Rfree_j, PermGroFac_j,   # scalars
    DiscFac, CRRA,           # scalars
    aXtraGrid,               # (aCount,)
    Cgrid,                   # (Ccount,)
    RecState_j_int,          # int (0 or 1)
    ADelasticity,
):
    """Compute EndOfPrdvP[c, a] for one next-state j. Returns (EndOfPrdvP, BoroCnstNat_vec_j).

    EndOfPrdvP shape: (Ccount, aCount)
    BoroCnstNat_vec_j shape: (Ccount,)
    """
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]
    ShkCount = IncShk_pmv_j.shape[0]

    # Tile arrays to (Ccount, aCount, ShkCount)
    aXtra_t = jnp.broadcast_to(aXtraGrid[None, :, None], (Ccount, aCount, ShkCount))
    pmv_t = jnp.broadcast_to(IncShk_pmv_j[None, None, :], (Ccount, aCount, ShkCount))
    perm_t = jnp.broadcast_to(IncShk_perm_j[None, None, :], (Ccount, aCount, ShkCount))
    tran_noAD_t = jnp.broadcast_to(IncShk_tran_j[None, None, :], (Ccount, aCount, ShkCount))
    Cnext_t = jnp.broadcast_to(Cgrid[:, None, None], (Ccount, aCount, ShkCount))

    # AD factor on tran shocks
    ADF = _ad_factor(Cnext_t, RecState_j_int, ADelasticity)
    tran_t = ADF * tran_noAD_t

    # Borrowing constraint candidate at each (c, s): pick max over s within each c
    # Tile reduces to (Ccount, ShkCount) here (no aXtra needed since aXtra=0 for boundary)
    Cnext_cs = jnp.broadcast_to(Cgrid[:, None], (Ccount, ShkCount))
    perm_cs = jnp.broadcast_to(IncShk_perm_j[None, :], (Ccount, ShkCount))
    ADF_cs = _ad_factor(Cnext_cs, RecState_j_int, ADelasticity)
    tran_cs = ADF_cs * jnp.broadcast_to(IncShk_tran_j[None, :], (Ccount, ShkCount))

    mNrmMinNext_at_Cnext_cs = jnp.where(
        mNrmMinNext_is_callable_j,
        # Tabulated mNrmMinNext_table_j is shape (C_eval,). Evaluate via 1-D interp at Cnext.
        jax.vmap(lambda C: linear_interp_1d(C_eval, mNrmMinNext_table_j, C, lower_extrap=True))(
            Cnext_cs.flatten()).reshape(Cnext_cs.shape),
        # Scalar fallback: mNrmMinNext * Cnext
        mNrmMinNext_scalar_j * Cnext_cs,
    )

    aNrmMin_cand_cs = (PermGroFac_j * perm_cs / Rfree_j
                       * (mNrmMinNext_at_Cnext_cs - tran_cs))
    aNrmMin_vec = jnp.max(aNrmMin_cand_cs, axis=1)  # (Ccount,)

    # Tile aNrmMin to (Ccount, aCount, ShkCount)
    aNrmMin_t = jnp.broadcast_to(aNrmMin_vec[:, None, None], (Ccount, aCount, ShkCount))
    aNrmNow_t = aNrmMin_t + aXtra_t

    # Next-period market resources
    mNrmNext_t = Rfree_j * aNrmNow_t / (PermGroFac_j * perm_t) + tran_t

    # Next-period marginal value via tabulated vPfunc lookup (bilinear interp on (m_eval, C_eval))
    # BUG-047: include PermGroFac_j^(-CRRA) in the marginal-value factor. The standard
    # Carroll / HARK form is (PermGroFac*PermShk)^(-CRRA), consistent with the mNrmNext
    # transition above which divides by PermGroFac_j*perm_t. This JAX kernel previously
    # omitted PermGroFac^(-CRRA) (the same bug fixed in AggFiscalModel.py:1813) — leaving
    # the GPU solver in the legacy regime, ~5% off the now-default fixed HARK solver.
    vPnext_t = (Rfree_j * PermGroFac_j ** (-CRRA) * perm_t ** (-CRRA)
                * _evaluate_vPfuncNext_table(
                    vPfuncNext_table_j, m_eval, C_eval,
                    mNrmNext_t.flatten(), Cnext_t.flatten()
                ).reshape(mNrmNext_t.shape))

    # End-of-period marginal value
    EndOfPrdvP = DiscFac * jnp.sum(vPnext_t * pmv_t, axis=2)  # (Ccount, aCount)

    return EndOfPrdvP, aNrmMin_vec


def _build_BoroCnst_table(BoroCnstNat_vec_per_j, Cgrid):
    """Pack per-j BoroCnstNat as a callable via 1-D linear interp on Cgrid.

    Returns (StateCount, Ccount) → (StateCount, Cquery) function.
    """
    # Just return the array; evaluation handled per-call with linear_interp_1d.
    return BoroCnstNat_vec_per_j  # shape (StateCount, Ccount)


#: Memory budget for the dominant Loop-2 temporary. SPARSE-J is chosen only if
#: its projected buffer fits this; otherwise SCAN-J (which removes the j axis
#: entirely) is used. Tied to the ACTUAL failure mode rather than a density
#: fraction: a fraction misjudges both ends (it would refuse sparsity at small
#: StateCount where memory is irrelevant, and could accept it at large
#: StateCount where S*K is still enormous). 4 GB leaves ample room inside a
#: 16 GB GPU alongside the other live buffers.
_SPARSE_J_BUDGET_BYTES = 4.0e9


def _loop2_buffer_bytes(S, K, Ccount, aCount):
    """Bytes of ONE dominant Loop-2 temporary: f64[S_i, K, Ccount*aCount, aCount+1].

    K = StateCount reproduces the ORIGINAL dense-vmap cost (the S^2 blowup);
    K = 1 reproduces SCAN-J. This one formula therefore prices all three paths.
    """
    return 8.0 * S * K * (Ccount * aCount) * (aCount + 1)


def _mrkv_nonzero_table(MrkvArray, Ccount, aCount,
                        budget_bytes=_SPARSE_J_BUDGET_BYTES):
    """Host-side (numpy) nonzero-successor table for SPARSE-J, or None.

    Returns (nz_idx, nz_w, K):
      nz_idx (StateCount, K) int32 — column indices of the nonzero entries of
        each row, padded by REPEATING that row's first nonzero (never a bogus
        index, so the padded lane evaluates something well-posed);
      nz_w   (StateCount, K) float64 — the matching MrkvArray weights, padded
        with EXACT 0.0 so padded lanes contribute nothing to the sum.

    Returns None when the matrix is too dense for sparsity to pay, so the caller
    takes the SCAN-J fallback. Computed once per solve on the host: `i` is
    traced inside the vmap and cannot index host data, so the table must be
    dense and passed in.
    """
    import numpy as _np
    M = _np.asarray(MrkvArray, dtype=float)
    S = M.shape[0]
    counts = (M > 0).sum(axis=1)
    K = int(counts.max()) if S else 0
    # Choose SPARSE-J only if it (a) actually reduces work vs the dense vmap and
    # (b) fits the budget. Otherwise SCAN-J, which is correct for ANY matrix.
    if K == 0 or K >= S or _loop2_buffer_bytes(S, K, Ccount, aCount) > budget_bytes:
        return None, None, K
    nz_idx = _np.zeros((S, K), dtype=_np.int32)
    nz_w = _np.zeros((S, K), dtype=_np.float64)
    for r in range(S):
        cols = _np.flatnonzero(M[r] > 0)
        n = cols.size
        if n == 0:
            # A zero row: no successors. Pad with index 0 and weight 0 — the
            # expectation is then exactly 0, which is what summing an empty row
            # of MrkvArray would have given before.
            continue
        nz_idx[r, :n] = cols
        nz_w[r, :n] = M[r, cols]
        if n < K:
            nz_idx[r, n:] = cols[0]      # repeat a VALID successor
            nz_w[r, n:] = 0.0            # ...with zero weight
    return nz_idx, nz_w, K


def _loop2_one_current_state(
    i,                              # int — current state
    EndOfPrdvP_cond,                # (StateCount, Ccount, aCount)
    BoroCnstNat_per_j,              # (StateCount, Ccount)
    EndOfPrdvP_aGrids,              # (StateCount, Ccount, aCount+1) — aXtra prepended with 0
    EndOfPrdvP_nvrs,                # (StateCount, Ccount, aCount+1) — nvrs(EndOfPrdvP) prepended with 0
    MrkvArray,                      # (StateCount, StateCount)
    LivPrb_i,                       # scalar
    CRRA,
    CFunc_slope, CFunc_intercept,   # (StateCount, StateCount)
    Cgrid, aXtraGrid,
    nz_idx=None,                    # (StateCount, K) int — nonzero successors, padded
    nz_w=None,                      # (StateCount, K) float — their MrkvArray weights, 0-padded
):
    """For current state i: compute cNrm and mNrm tables (Ccount, aCount).

    Returns (cNrm, mNrm, BoroCnstNat_vec_i) where:
      cNrm shape (Ccount, aCount)
      mNrm shape (Ccount, aCount)
      BoroCnstNat_vec_i shape (Ccount,) — the natural constraint for current state i
    """
    StateCount = MrkvArray.shape[0]
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]

    # Cnext_ij[j, c] = CFunc[i,j](Cgrid[c]) = intercept[i,j] + slope[i,j]*(Cgrid[c] - 1)
    Cnext_ij = (CFunc_intercept[i][:, None]
                + CFunc_slope[i][:, None] * (Cgrid[None, :] - 1.0))  # (StateCount, Ccount)

    # BoroCnstNat_at_Cnext[j, c] = BoroCnstNat_cond[j](Cnext_ij[j, c])
    def per_j_BoroCnstNat(j):
        return jax.vmap(
            lambda C: linear_interp_1d(Cgrid, BoroCnstNat_per_j[j], C, lower_extrap=True)
        )(Cnext_ij[j])  # (Ccount,)

    BoroCnstNat_at_Cnext = jax.vmap(per_j_BoroCnstNat)(jnp.arange(StateCount))
    # shape (StateCount, Ccount)

    # Mask infeasible transitions (MrkvArray[i,j] == 0)
    mask = (MrkvArray[i] > 0)[:, None]  # (StateCount, 1)
    BoroCnstNat_masked = jnp.where(mask, BoroCnstNat_at_Cnext, -jnp.inf)
    aNrmMin_vec_i = jnp.max(BoroCnstNat_masked, axis=0)  # (Ccount,)

    aNrmMin_t = jnp.broadcast_to(aNrmMin_vec_i[:, None], (Ccount, aCount))
    aNrmNow_t = aNrmMin_t + aXtraGrid[None, :]  # (Ccount, aCount)

    # For each j, evaluate EndOfPrdvP_cond[j] at (aNrmNow_t, Cnext_ij[j])
    # HARK's VariableLowerBoundFunc2D shifts query: inner_fn(x - lb(y), y).
    # So we must compute (aNrmNow - BoroCnstNat_cond[j](Cnext)) before the bilinear lookup.
    def per_j_EndOfPrdvP(j):
        Cnext_jc_a = jnp.broadcast_to(Cnext_ij[j][:, None], (Ccount, aCount))

        # Compute BoroCnstNat_cond[j] at each Cnext_ij[j, c] (varies by c, broadcast over a)
        BoroCnstNat_cond_j_at_Cnext = jax.vmap(
            lambda C: linear_interp_1d(Cgrid, BoroCnstNat_per_j[j], C, lower_extrap=True)
        )(Cnext_ij[j])  # (Ccount,)
        BoroCnstNat_shift = jnp.broadcast_to(
            BoroCnstNat_cond_j_at_Cnext[:, None], (Ccount, aCount))

        # Shifted query points
        aNrm_query_shifted = aNrmNow_t - BoroCnstNat_shift  # (Ccount, aCount)

        nvrs_value = linear_interp_on_interp_1d_general(
            EndOfPrdvP_aGrids[j],          # (Ccount, aCount+1)
            Cgrid,                          # (Ccount,)
            EndOfPrdvP_nvrs[j],             # (Ccount, aCount+1)
            aNrm_query_shifted.flatten(),
            Cnext_jc_a.flatten(),
        ).reshape((Ccount, aCount))
        # Convert nvrs → vP: vP = nvrs ^ (-CRRA), handle nvrs=0 → vP=inf safely
        nvrs_safe = jnp.maximum(nvrs_value, 1e-12)
        vP = nvrs_safe ** (-CRRA)
        return vP

    # ---- Expectation over next states j -------------------------------------
    # MEMORY-CRITICAL. The dominant temporary of the whole kernel is created
    # here: this function is itself inside jax.vmap over CURRENT state i (see
    # solve_one_period_jax), and `linear_interp_on_interp_1d_general` gathers a
    # whole (aCount+1)-long row per query, so a plain vmap over j materialises
    #     f64[S_i, S_j, Ccount*aCount, aCount+1]
    # = 8*S^2*(C*a)*(a+1) bytes -> 24.6 GB PER BUFFER at S=132, C=3, a=242, and
    # ~77 GB peak (~3 live). That OOM-killed the P4 harness. Note it is
    # QUADRATIC in aCount, which is why the count-basis 48->192 promotion
    # (aCount 50 -> 242, 23x on a*(a+1)) turned a latent design into a fatal one
    # while the legacy grid ran fine (~4.6 GB).
    #
    # SPARSE-J (default). MrkvArray is ~2.3% dense at S=132 and 1.19% at S=252:
    # EVERY row has at most K=4 nonzero successors (mean exactly 3.00), by
    # construction of the (macro x micro) product chain. The old code evaluated
    # all S_j and then multiplied ~128/132 of them by zero at the weighting
    # step. We instead visit only the nonzero successors, so the j axis shrinks
    # S -> K: ~33x less memory AND ~33x less arithmetic, with full parallelism
    # kept. nz_idx/nz_w are built ONCE host-side (see _mrkv_nonzero_table) and
    # passed in dense, because `i` is traced here and cannot index host data.
    #
    # SCAN-J (guarded fallback). If the sparsity assumption ever fails (a dense
    # or restructured MrkvArray), _mrkv_nonzero_table returns None and we fall
    # back to lax.scan over ALL j, which removes the S_j axis entirely (132x
    # memory) at the cost of serialising the loop (~1.34x slower, measured).
    # Correct for any transition matrix; chosen only when sparsity cannot help.
    if nz_idx is not None:
        # nz_idx (StateCount, K) int; nz_w (StateCount, K) float, zero-padded.
        j_list = nz_idx[i]                                   # (K,) traced gather
        w_list = nz_w[i]                                     # (K,)
        vP_per_k = jax.vmap(per_j_EndOfPrdvP)(j_list)        # (K, Ccount, aCount)
        # Padding lanes carry w = 0. per_j_EndOfPrdvP is finite for them because
        # of the nvrs clamp at `jnp.maximum(nvrs_value, 1e-12)` above (vP <=
        # 1e12^CRRA, never inf/nan), so 0 * vP == 0 exactly — the same argument
        # that made the original all-j masking safe.
        weighted = w_list[:, None, None] * vP_per_k          # (K, Ccount, aCount)
        EndOfPrdvP_total = LivPrb_i * jnp.sum(weighted, axis=0)
    else:
        MrkvRow_i = MrkvArray[i]

        def _accumulate(acc, j):
            return acc + MrkvRow_i[j] * per_j_EndOfPrdvP(j), None

        EndOfPrdvP_sum, _ = jax.lax.scan(
            _accumulate,
            jnp.zeros((Ccount, aCount), dtype=aNrmNow_t.dtype),
            jnp.arange(StateCount),
            unroll=1,   # MUST stay 1: unroll>1 re-materialises that many j at
                        # once (peak linear in unroll) for zero measured gain.
        )
        EndOfPrdvP_total = LivPrb_i * EndOfPrdvP_sum

    # EGM step
    cNrm = EndOfPrdvP_total ** (-1.0 / CRRA)
    mNrm = aNrmNow_t + cNrm

    return cNrm, mNrm, aNrmMin_vec_i


def solve_one_period_jax(
    # vPfuncNext as tabulated bilinear on (m_eval, C_eval), shape (StateCount, M_eval, C_eval)
    vPfuncNext_table,
    m_eval, C_eval,
    # mNrmMinNext: (StateCount, C_eval) table if callable, plus per-state callable flag
    mNrmMinNext_table,                 # (StateCount, C_eval)
    mNrmMinNext_is_callable,           # (StateCount,) bool
    mNrmMinNext_scalar,                # (StateCount,) — used when not callable
    # IncShkDstn arrays
    IncShk_pmv,                        # (StateCount, ShkCount)
    IncShk_perm,                       # (StateCount, ShkCount)
    IncShk_tran,                       # (StateCount, ShkCount)
    LivPrb,                            # (StateCount,)
    DiscFac, CRRA,                     # scalars
    Rfree,                             # (StateCount,)
    PermGroFac,                        # (StateCount,)
    MrkvArray,                         # (StateCount, StateCount)
    BoroCnstArt,                       # scalar
    aXtraGrid,                         # (aCount,)
    Cgrid,                             # (Ccount,)
    CFunc_slope, CFunc_intercept,      # (StateCount, StateCount)
    ADelasticity,
    RecState_per_state,                # (StateCount,) int — 0/1 per state for ADFunc
):
    """One backward-induction step. Returns cNrm/mNrm tables and BoroCnstNat per (state, c).

    Returns dict with:
      cNrm: (StateCount, Ccount, aCount)
      mNrm: (StateCount, Ccount, aCount)
      BoroCnstNat_per_j: (StateCount, Ccount) — natural constraint from Loop 1
      BoroCnstNat_per_i: (StateCount, Ccount) — natural constraint from Loop 2 (cFunc usage)
    """
    StateCount = Rfree.shape[0]
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]

    # === Loop 1: per next-state j, compute EndOfPrdvP_cond + BoroCnstNat ===
    def per_next_state(j):
        return _loop1_one_next_state(
            vPfuncNext_table[j], mNrmMinNext_table[j],
            mNrmMinNext_is_callable[j], mNrmMinNext_scalar[j],
            m_eval, C_eval,
            IncShk_pmv[j], IncShk_perm[j], IncShk_tran[j],
            Rfree[j], PermGroFac[j], DiscFac, CRRA,
            aXtraGrid, Cgrid,
            RecState_per_state[j], ADelasticity,
        )

    # vmap over next-state j. Returns (StateCount, Ccount, aCount), (StateCount, Ccount)
    EndOfPrdvP_cond_all, BoroCnstNat_per_j = jax.vmap(per_next_state)(jnp.arange(StateCount))

    # Prepend 0 to aXtra grid and to nvrs(EndOfPrdvP) for boundary handling
    # aGrid_with_0[j, c, :] = [0, aNrmMin[j,c]+aXtra[0], aNrmMin[j,c]+aXtra[1], ...]
    # Actually HARK does: BilinearInterp(np.transpose(EndOfPrdvPnvrs), np.insert(aXtraGrid, 0, 0.0), Cgrid)
    # So the underlying grid is np.insert(aXtraGrid, 0, 0.0) — NOT aNrmMin+aXtra.
    # The "VariableLowerBoundFunc2D" wrapper SHIFTS query points by BoroCnstNat(C) before lookup.
    # So the EndOfPrdvP_nvrs values are indexed by aXtra (relative to aNrmMin), not absolute aNrm.
    aXtra_with_0 = jnp.concatenate([jnp.zeros(1), aXtraGrid])  # (aCount+1,)
    EndOfPrdvP_nvrs = EndOfPrdvP_cond_all ** (-1.0 / CRRA)
    EndOfPrdvP_nvrs_with_0 = jnp.concatenate(
        [jnp.zeros((StateCount, Ccount, 1)), EndOfPrdvP_nvrs], axis=2)  # (StateCount, Ccount, aCount+1)
    EndOfPrdvP_aGrids = jnp.broadcast_to(
        aXtra_with_0[None, None, :], (StateCount, Ccount, aCount + 1))

    # === Loop 2: per current state i, compute cNrm/mNrm ===
    # SPARSE-J table, built ONCE on the host (see _mrkv_nonzero_table and the
    # memory note in _loop2_one_current_state). None => SCAN-J fallback.
    _nz_idx, _nz_w, _K = _mrkv_nonzero_table(MrkvArray, Ccount, aCount)
    if _nz_idx is not None:
        _nz_idx = jnp.asarray(_nz_idx)
        _nz_w = jnp.asarray(_nz_w)

    def per_current_state(i):
        return _loop2_one_current_state(
            i, EndOfPrdvP_cond_all, BoroCnstNat_per_j,
            EndOfPrdvP_aGrids, EndOfPrdvP_nvrs_with_0,
            MrkvArray, LivPrb[i], CRRA,
            CFunc_slope, CFunc_intercept, Cgrid, aXtraGrid,
            nz_idx=_nz_idx, nz_w=_nz_w,
        )

    cNrm_all, mNrm_all, BoroCnstNat_per_i = jax.vmap(per_current_state)(jnp.arange(StateCount))

    return {
        'cNrm': cNrm_all,                       # (StateCount, Ccount, aCount)
        'mNrm': mNrm_all,                       # (StateCount, Ccount, aCount)
        'BoroCnstNat_per_j': BoroCnstNat_per_j, # (StateCount, Ccount) — from Loop 1
        'BoroCnstNat_per_i': BoroCnstNat_per_i, # (StateCount, Ccount) — from Loop 2
    }


def evaluate_cFunc(cNrm_table, mNrm_table, BoroCnstNat_per_i, BoroCnstArt,
                   Cgrid, state_i, m_query, C_query):
    """Evaluate the unconstrained cFunc for state i at (m_query, C_query).

    Uses linear_interp_on_interp_1d_general with per-Cgrid x_grids = (mNrm[i, c, :] - BoroCnstNat[i, c]).

    NOTE: this is the UNCONSTRAINED component (cFuncBase). For full cFuncNow you'd
    apply LowerEnvelope2D with cFuncCnst. For interior points well above BoroCnstArt,
    this matches HARK's cFunc.
    """
    cNrm_i = cNrm_table[state_i]     # (Ccount, aCount)
    mNrm_i = mNrm_table[state_i]     # (Ccount, aCount)
    BoroCnstNat_i = BoroCnstNat_per_i[state_i]  # (Ccount,)

    # Per-C: x_grid = [0, mNrm[c, 0] - BoroCnstNat[c], mNrm[c, 1] - BoroCnstNat[c], ...]
    aCount = cNrm_i.shape[1]
    Ccount = Cgrid.shape[0]
    m_shifted = mNrm_i - BoroCnstNat_i[:, None]  # (Ccount, aCount)
    x_grids = jnp.concatenate([jnp.zeros((Ccount, 1)), m_shifted], axis=1)  # (Ccount, aCount+1)
    f_values = jnp.concatenate([jnp.zeros((Ccount, 1)), cNrm_i], axis=1)    # (Ccount, aCount+1)

    # Shift query m by BoroCnstNat at the query C
    BoroCnstNat_at_C = jax.vmap(
        lambda C: linear_interp_1d(Cgrid, BoroCnstNat_i, C, lower_extrap=True)
    )(jnp.atleast_1d(C_query))
    m_query_shifted = jnp.atleast_1d(m_query) - BoroCnstNat_at_C

    cFuncBase = linear_interp_on_interp_1d_general(
        x_grids, Cgrid, f_values,
        m_query_shifted, jnp.atleast_1d(C_query))
    return cFuncBase
