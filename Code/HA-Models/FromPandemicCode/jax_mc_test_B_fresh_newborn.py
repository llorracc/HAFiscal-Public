"""
Test B: Use fresh per-period newborn draws (HARK style) instead of fixed pool.
Pre-generates a (T, N) array of newborn pLvl values (each death gets a unique
fresh draw). Removes any pool-indexing correlation.
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax, jax.numpy as jnp
from jax import lax
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs, _broadcast_employed_psi_to_all_states


def main():
    print("=== Test B: per-period fresh newborn draws (no pool) ===")
    d = pickle.load(open('welfare6_HS_clean_nshuf_4seed/seed0/base.pkl','rb'))
    h_aNrm0 = np.asarray(d['aNrm_all_bs'][0])
    h_pLvl0 = np.asarray(d['pLvl_all_bs'][0])
    h_mrkv0 = np.asarray(d['Mrkv_hist_bs'][0]) % 6
    N = len(h_aNrm0); T = 40

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']; AggEco.switch_shock_type('base'); AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')
    if getattr(agent, 'perm_shocks_during_unemployment', False):
        new_psi, new_xi, new_pmv, new_natoms = _broadcast_employed_psi_to_all_states(
            inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'])
        inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'] = new_psi, new_xi, new_pmv, new_natoms

    cfunc_table = jnp.asarray(inp['cfunc_table'])
    m_grid = jnp.asarray(inp['m_grid'])
    Rfree = jnp.asarray(inp['Rfree'])
    PermGroFac = jnp.asarray(inp['PermGroFac'])
    MrkvArray = jnp.asarray(inp['MrkvArray'])
    IncShk_psi = jnp.asarray(inp['IncShk_psi'])
    IncShk_xi = jnp.asarray(inp['IncShk_xi'])
    IncShk_pmv = jnp.asarray(inp['IncShk_pmv'])
    Splurge = inp['Splurge']; LivPrb = inp['LivPrb']
    M = m_grid.shape[0]; J = MrkvArray.shape[0]

    def step(carry, scan_in):
        aNrm_prev, pLvl_prev, mrkv_prev = carry
        death_u, mrkv_u, atom_u, newborn_aNrm_t, newborn_pLvl_t = scan_in
        N_ = aNrm_prev.shape[0]
        alive_mask = death_u < LivPrb
        cum_prob = jnp.cumsum(MrkvArray[mrkv_prev], axis=-1)
        mrkv_now = jnp.sum(mrkv_u[:, None] > cum_prob, axis=-1).astype(jnp.int32)
        mrkv_now = jnp.clip(mrkv_now, 0, J - 1)
        # Newborn: PER-PERIOD fresh per-agent draws (no pool indexing)
        aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm_t)
        pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl_t)
        mrkv_now = jnp.where(alive_mask, mrkv_now, 0)
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
        mNrm = bNrm + xi * 1.0
        i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
        w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
        cNrm = cfunc_table[mrkv_now, i_lo] + w_hi * (cfunc_table[mrkv_now, i_lo + 1] - cfunc_table[mrkv_now, i_lo])
        pLvl_now = pLvl_carry * G_eff * psi_eff
        cLvl_sp = (1 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi
        aNrm_next = mNrm - cLvl_sp / pLvl_now
        return (aNrm_next, pLvl_now, mrkv_now), pLvl_now.dot(xi)

    @jax.jit
    def run_sim(carry0, death_d, mrkv_d, atom_d, newborn_aNrm_TN, newborn_pLvl_TN):
        _, AggInc = lax.scan(step, carry0, (death_d, mrkv_d, atom_d, newborn_aNrm_TN, newborn_pLvl_TN))
        return AggInc

    # Sample newborn pool params from HARK
    if hasattr(agent, 'pLvlInitDstn'):
        agent.pLvlInitDstn.seed = 12345
    if hasattr(agent, 'kNrmInitDstn'):
        agent.kNrmInitDstn.seed = 12346

    carry0 = (jnp.asarray(h_aNrm0, dtype=jnp.float32),
              jnp.asarray(h_pLvl0, dtype=jnp.float32),
              jnp.asarray(h_mrkv0, dtype=jnp.int32))

    means = []
    for s in range(16):
        rs = np.random.RandomState(s)
        death_d = rs.uniform(size=(T, N)).astype(np.float32)
        mrkv_d = rs.uniform(size=(T, N)).astype(np.float32)
        atom_d = rs.uniform(size=(T, N)).astype(np.float32)
        # Fresh newborn per period per agent — draw (T, N) values
        # Use Lognormal directly
        mu = float(getattr(agent, 'pLogInitMean', 2.4069))
        sigma = float(getattr(agent, 'pLogInitStd', 0.42))
        newborn_pLvl_TN = rs.lognormal(mean=mu, sigma=sigma, size=(T, N)).astype(np.float32)
        newborn_aNrm_TN = np.full((T, N), 1e-5, dtype=np.float32)
        inc = run_sim(carry0, jnp.asarray(death_d), jnp.asarray(mrkv_d), jnp.asarray(atom_d),
                      jnp.asarray(newborn_aNrm_TN), jnp.asarray(newborn_pLvl_TN))
        inc.block_until_ready()
        means.append(float(np.asarray(inc).mean()))
    print(f"Per-period fresh newborn draws (16 seeds):")
    print(f"  mean: {np.mean(means):.3f}  std: {np.std(means, ddof=1):.3f}")
    hark_means = [pickle.load(open(f'welfare6_HS_clean_nshuf_4seed/seed{s}/base.pkl','rb'))['AggIncome'].mean()
                  for s in range(4)]
    hark_mean = np.mean(hark_means)
    print(f"  HARK 4-seed mean: {hark_mean:.3f}")
    print(f"  Ratio JAX(fresh-newborn)/HARK: {np.mean(means)/hark_mean:.4f}")
    print(f"  Reference (pool): expected ~1.024")


if __name__ == '__main__':
    main()
