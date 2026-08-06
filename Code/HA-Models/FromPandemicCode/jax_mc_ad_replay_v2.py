"""
Replay kernel v2: full HARK alignment.

Difference vs v1 (jax_mc_ad_replay.py): instead of using a fixed newborn pool
indexed by `arange(N) % pool_size`, take HARK's captured per-period post-
sim_birth state (aNrm_init, pLvl_init) and use those values for dead slots.

This eliminates the second RNG-related error source (newborn-replacement
realization mismatch). Combined with shock_history replay (v1 already does
this), should bring JAX-vs-HARK agreement to FP precision.

Inputs vs v1:
  newborn_aNrm_path: (T, N) — HARK's post-sim_birth aNrm at each period
  newborn_pLvl_path: (T, N) — HARK's post-sim_birth pLvl at each period
  (replaces newborn_aNrm, newborn_pLvl which were just 1D pool)
"""
from __future__ import annotations
import os, numpy as np
import jax, jax.numpy as jnp
from jax import lax
from functools import partial


def _mc_step_replay_v2(carry, scan_in, *,
                        m_grid,
                        Rfree_macro, PermGroFac_macro,
                        Splurge, J, esc_assets=False, restricted=False):
    aNrm_prev, pLvl_prev = carry
    (AggDemandFac_t, cfunc_table_t, mrkv_t, tran_t, perm_t, who_dies_t,
     nb_aNrm_t, nb_pLvl_t) = scan_in
    N = aNrm_prev.shape[0]

    alive_mask = ~who_dies_t
    # NEW v2: use HARK's per-period captured newborn values directly
    aNrm_carry = jnp.where(alive_mask, aNrm_prev, nb_aNrm_t)
    pLvl_carry = jnp.where(alive_mask, pLvl_prev, nb_pLvl_t)

    mrkv_micro = mrkv_t % J
    mrkv_combined = mrkv_t

    R_now = Rfree_macro[mrkv_combined]
    psi_eff = perm_t  # already includes G

    bNrm = R_now * aNrm_carry / psi_eff
    mNrm = bNrm + tran_t * AggDemandFac_t

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    # R2 state-restricted tables (2026-08-02): the deterministic macro path
    # occupies ONE macro state per period, so the per-period table carries
    # only that macro's J micro rows — gather by the micro index. The caller
    # guards the one-macro-per-period invariant loudly before entering.
    _row = mrkv_micro if restricted else mrkv_combined
    c_lo = cfunc_table_t[_row, i_lo]
    c_hi = cfunc_table_t[_row, i_lo + 1]
    cNrm = c_lo + w_hi * (c_hi - c_lo)

    pLvl_now = pLvl_carry * psi_eff
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * tran_t * AggDemandFac_t
    # Interpretation-dependent asset law (found 2026-08-01, BUG-051 sibling):
    # ESC (production default): a = m - cFunc(m) -- the splurge is the
    # Splurger's separate ledger and never touches optimizer assets
    # (AggFiscalModel.get_poststates ESC branch). CDC: a = m - total
    # realized consumption. This kernel historically hardcoded the CDC law;
    # under the ESC world that is a per-step asset wedge of
    # Splurge*(cNrm - tran*ADF) ~ 1e-2/agent -- the free-run carry
    # divergence and replay-v2's historical 0.28-0.62% residuals.
    aNrm_next = mNrm - (cNrm if esc_assets else cLvl_sp / pLvl_now)

    # Aggregate reductions promoted to float64 REGARDLESS of the panel dtype:
    # under the fp32 tolerance arm (HAFISCAL_REPLAY_FP32) the per-agent panel
    # runs float32, but naively summing ~2e5 fp32 values loses digits the
    # welfare cells cannot spare (the 1-2e-5 differential ruler). Mixed
    # precision: fp32 storage/compute, fp64 accumulate. No-op under fp64.
    AggInc_t = jnp.sum((pLvl_now * tran_t * AggDemandFac_t).astype(jnp.float64))
    AggCons_t = jnp.sum(cLvl_sp.astype(jnp.float64))

    new_carry = (aNrm_next, pLvl_now)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'J', 'esc_assets', 'restricted'))
def _simulate_replay_v2_core(carry0, AggDemandFac_path, cfunc_table_per_period,
                              mrkv_path, tran_path, perm_path, who_dies_path,
                              nb_aNrm_path, nb_pLvl_path,
                              m_grid, Rfree_macro, PermGroFac_macro,
                              Splurge, act_T, J, esc_assets=False,
                              restricted=False):
    def step(carry, scan_in):
        return _mc_step_replay_v2(
            carry, scan_in,
            m_grid=m_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            Splurge=Splurge, J=J, esc_assets=esc_assets,
            restricted=restricted,
        )
    scan_inputs = (AggDemandFac_path, cfunc_table_per_period,
                   mrkv_path, tran_path, perm_path, who_dies_path,
                   nb_aNrm_path, nb_pLvl_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_replay_v2(aNrm0, pLvl0,
                            AggDemandFac_path,
                            cfunc_table_per_period, m_grid,
                            mrkv_path, tran_path, perm_path, who_dies_path,
                            nb_aNrm_path, nb_pLvl_path,
                            Rfree_macro, PermGroFac_macro,
                            Splurge, act_T, J, esc_assets=None,
                            restricted=False):
    """Fully RNG-aligned replay. Should match HARK to FP precision.

    esc_assets: None (default) resolves from HAFISCAL_INTERPRETATION
    (production default ESC -> True: a = m - cFunc(m), the Splurger ledger
    never touches optimizer assets). False = the historical CDC law
    (a = m - total consumption). See the step's comment (BUG-051 sibling).
    """
    if esc_assets is None:
        import os as _os
        esc_assets = (_os.environ.get("HAFISCAL_INTERPRETATION", "ESC")
                      .upper() == "ESC")
    # fp32 tolerance arm (GPU-roadmap gate G0, 2026-08-02): run the per-agent
    # panel in float32 while the step's aggregate reductions stay float64.
    # Diagnostic, default off; the A/B vs the fp64 arm measures precision
    # effects alone (the replay kernel is deterministic given the panel).
    if os.environ.get("HAFISCAL_REPLAY_FP32", "").lower() in ("1", "on", "true"):
        fp = jnp.float32
    else:
        fp = jnp.asarray(aNrm0).dtype
    carry0 = (jnp.asarray(aNrm0, dtype=fp),
              jnp.asarray(pLvl0, dtype=fp))
    outs = _simulate_replay_v2_core(
        carry0,
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(cfunc_table_per_period, dtype=fp),
        jnp.asarray(mrkv_path, dtype=jnp.int32),
        jnp.asarray(tran_path, dtype=fp),
        jnp.asarray(perm_path, dtype=fp),
        jnp.asarray(who_dies_path, dtype=jnp.bool_),
        jnp.asarray(nb_aNrm_path, dtype=fp),
        jnp.asarray(nb_pLvl_path, dtype=fp),
        jnp.asarray(m_grid, dtype=fp),
        jnp.asarray(Rfree_macro, dtype=fp),
        jnp.asarray(PermGroFac_macro, dtype=fp),
        Splurge, act_T, J, esc_assets=bool(esc_assets),
        restricted=bool(restricted),
    )
    AggInc, AggCons, cLvl_panel = outs
    AggInc.block_until_ready()
    return AggInc, AggCons, cLvl_panel
