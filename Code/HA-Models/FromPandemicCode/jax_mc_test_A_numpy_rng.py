"""
Test A: Replace JAX RNG with numpy.RandomState in shock sampling.
Pre-generates all atom indices via numpy, then feeds them deterministically
to the JAX kernel. Eliminates Threefry-vs-MT as a source of bias.
"""
from __future__ import annotations
import os, sys, pickle, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax, jax.numpy as jnp
from jax import lax
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs, draw_newborn_pool_from_agent, _broadcast_employed_psi_to_all_states


def make_jax_kernel_with_external_shocks(
    cfunc_table, m_grid, Rfree, PermGroFac, MrkvArray,
    IncShk_psi, IncShk_xi, IncShk_pmv, AggDemandFac, Splurge, LivPrb,
    newborn_aNrm, newborn_pLvl, newborn_mrkv):
    """Build a kernel that takes pre-drawn shocks (atom indices + death masks + mrkv draws).
    All RNG happens outside (numpy)."""
    M = m_grid.shape[0]
    J = MrkvArray.shape[0]

    def step(carry, scan_in):
        aNrm_prev, pLvl_prev, mrkv_prev = carry
        death_u, mrkv_u, atom_u = scan_in   # per-period uniform draws
        N = aNrm_prev.shape[0]

        alive_mask = death_u < LivPrb

        # Mrkv transition
        cum_prob = jnp.cumsum(MrkvArray[mrkv_prev], axis=-1)
        mrkv_now = jnp.sum(mrkv_u[:, None] > cum_prob, axis=-1).astype(jnp.int32)
        mrkv_now = jnp.clip(mrkv_now, 0, J - 1)

        pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
        aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
        pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
        mrkv_now = jnp.where(alive_mask, mrkv_now, newborn_mrkv[pool_idx])

        # Atom draw
        cum_atom = jnp.cumsum(IncShk_pmv[mrkv_now], axis=-1)
        atom_idx = jnp.sum(atom_u[:, None] > cum_atom, axis=-1).astype(jnp.int32)
        atom_idx = jnp.clip(atom_idx, 0, IncShk_pmv.shape[-1] - 1)
        psi = IncShk_psi[mrkv_now, atom_idx]
        xi = IncShk_xi[mrkv_now, atom_idx]

        R_now = Rfree[mrkv_now]
        G_now = PermGroFac[mrkv_now]
        is_employed = (mrkv_now == 0)
        psi_eff = jnp.where(is_employed, psi, 1.0)
        G_eff = jnp.where(is_employed, G_now, 1.0)

        bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
        mNrm = bNrm + xi * AggDemandFac

        i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
        i_hi = i_lo + 1
        m_lo = m_grid[i_lo]; m_hi = m_grid[i_hi]
        w_hi = (mNrm - m_lo) / (m_hi - m_lo)
        c_lo = cfunc_table[mrkv_now, i_lo]
        c_hi = cfunc_table[mrkv_now, i_hi]
        cNrm = c_lo + w_hi * (c_hi - c_lo)

        pLvl_now = pLvl_carry * G_eff * psi_eff
        cLvl_sp = (1 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi * AggDemandFac
        aNrm_next = mNrm - cLvl_sp / pLvl_now
        income = pLvl_now * xi * AggDemandFac

        return (aNrm_next, pLvl_now, mrkv_now), (income.sum(), cLvl_sp.sum())

    @jax.jit
    def run_sim(carry0, death_draws, mrkv_draws, atom_draws):
        _, outs = lax.scan(step, carry0, (death_draws, mrkv_draws, atom_draws))
        return outs

    return run_sim


def main():
    print("=== Test A: numpy.random vs JAX RNG for shock generation ===")
    d = pickle.load(open('welfare6_HS_clean_nshuf_4seed/seed0/base.pkl','rb'))
    h_inc = np.asarray(d['AggIncome'])
    h_aNrm0 = np.asarray(d['aNrm_all_bs'][0])
    h_pLvl0 = np.asarray(d['pLvl_all_bs'][0])
    h_mrkv0 = np.asarray(d['Mrkv_hist_bs'][0]) % 6
    N = len(h_aNrm0)
    T = 40

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']; AggEco.switch_shock_type('base'); AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')
    if getattr(agent, 'perm_shocks_during_unemployment', False):
        new_psi, new_xi, new_pmv, new_natoms = _broadcast_employed_psi_to_all_states(
            inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'])
        inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'] = new_psi, new_xi, new_pmv, new_natoms
    nbA, nbP, nbM = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

    run_sim = make_jax_kernel_with_external_shocks(
        jnp.asarray(inp['cfunc_table']), jnp.asarray(inp['m_grid']),
        jnp.asarray(inp['Rfree']), jnp.asarray(inp['PermGroFac']),
        jnp.asarray(inp['MrkvArray']),
        jnp.asarray(inp['IncShk_psi']), jnp.asarray(inp['IncShk_xi']),
        jnp.asarray(inp['IncShk_pmv']),
        1.0, inp['Splurge'], inp['LivPrb'],
        jnp.asarray(nbA), jnp.asarray(nbP), jnp.asarray(nbM))

    carry0 = (jnp.asarray(h_aNrm0, dtype=jnp.float32),
              jnp.asarray(h_pLvl0, dtype=jnp.float32),
              jnp.asarray(h_mrkv0, dtype=jnp.int32))

    # Run 16 seeds with numpy.RandomState-generated shocks
    print(f"\nWith numpy.random (16 seeds, mirrors HARK's MT RNG):")
    means_np = []
    for s in range(16):
        rs = np.random.RandomState(s)
        death_d = rs.uniform(size=(T, N)).astype(np.float32)
        mrkv_d = rs.uniform(size=(T, N)).astype(np.float32)
        atom_d = rs.uniform(size=(T, N)).astype(np.float32)
        inc, _ = run_sim(carry0,
                         jnp.asarray(death_d), jnp.asarray(mrkv_d),
                         jnp.asarray(atom_d))
        inc.block_until_ready()
        means_np.append(float(np.asarray(inc).mean()))
    print(f"  per-seed: {means_np}")
    print(f"  mean: {np.mean(means_np):.3f}  std: {np.std(means_np, ddof=1):.3f}")

    # Compare to HARK 4-seed mean
    hark_means = [pickle.load(open(f'welfare6_HS_clean_nshuf_4seed/seed{s}/base.pkl','rb'))['AggIncome'].mean()
                  for s in range(4)]
    hark_mean = np.mean(hark_means)
    print(f"\n  HARK 4-seed mean: {hark_mean:.3f}")
    print(f"  Ratio JAX(numpy)/HARK: {np.mean(means_np)/hark_mean:.4f}")
    print(f"\nReference (JAX with Threefry RNG): expected ratio ~1.022-1.025")


if __name__ == '__main__':
    main()
