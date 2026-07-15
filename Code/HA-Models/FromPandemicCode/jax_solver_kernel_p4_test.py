"""P4 validation: JAX solver vs HARK at HS_Only recession (multi-Markov, ADF active).

Switches AggEco to recession scenario (StateCount = num_base_MrkvStates × num_macros),
then validates JAX solve_one_period_jax against HARK at the converged solution.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve
from jax_solver_kernel import solve_one_period_jax, evaluate_cFunc
from jax_solver_kernel_test import (
    tabulate_vPfuncNext, tabulate_mNrmMinNext, extract_CFunc_arrays)


def main():
    print("=== P4: JAX solver vs HARK at HS_Only recession (multi-Markov + ADF) ===")
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    print(f"build+solve base: {time.time()-t0:.1f}s")

    # Switch to recession + re-solve agent
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    agent = eco.agents[0]
    print(f"After switch: num_base_MrkvStates={agent.num_base_MrkvStates}")
    print(f"  MrkvArray[0] shape: {np.asarray(agent.MrkvArray[0]).shape}")
    print(f"  CFunc shape: {len(eco.CFunc)}x{len(eco.CFunc[0])}")

    print("\nSolving agent for recession scenario...")
    t0 = time.time()
    agent.solve()
    print(f"HARK solve: {time.time()-t0:.1f}s")

    solution = agent.solution[0]
    StateCount = len(solution.cFunc)
    Ccount = agent.Cgrid.size
    aCount = agent.aXtraGrid.size
    print(f"StateCount={StateCount}, Ccount={Ccount}, aCount={aCount}")

    # m_eval grid: dense, log-spaced near 0
    m_eval = np.concatenate([
        np.linspace(0.001, 0.1, 100),
        np.linspace(0.1, 1.0, 200),
        np.linspace(1.0, 5.0, 200),
        np.linspace(5.0, 50.0, 200),
    ])
    m_eval = np.unique(m_eval)
    C_eval = np.array(agent.Cgrid)

    print(f"Tabulating solution_next on m_eval={len(m_eval)}, C_eval={len(C_eval)} ...")
    t0 = time.time()
    vPfuncNext_table = tabulate_vPfuncNext(solution, StateCount, m_eval, C_eval)
    mNrmMinNext_table, mNrmMin_is_callable, mNrmMin_scalar = tabulate_mNrmMinNext(
        solution, StateCount, C_eval)
    print(f"  tabulate: {time.time()-t0:.1f}s")

    IncShkDstn_states = agent.IncShkDstn[0]
    max_atoms = max(len(np.asarray(IncShkDstn_states[j].pmv)) for j in range(StateCount))
    IncShk_pmv = np.zeros((StateCount, max_atoms))
    IncShk_perm = np.zeros((StateCount, max_atoms))
    IncShk_tran = np.zeros((StateCount, max_atoms))
    for j in range(StateCount):
        d = IncShkDstn_states[j]
        n = len(np.asarray(d.pmv))
        IncShk_pmv[j, :n] = np.asarray(d.pmv)
        IncShk_perm[j, :n] = np.asarray(d.atoms[0])
        IncShk_tran[j, :n] = np.asarray(d.atoms[1])
        IncShk_perm[j, n:] = 1.0

    Rfree = np.asarray(agent.Rfree[:StateCount])
    PermGroFac = np.asarray(agent.PermGroFac[0][:StateCount])
    LivPrb = np.asarray(agent.LivPrb[0][:StateCount])
    DiscFac = float(agent.DiscFac)
    CRRA = float(agent.CRRA)
    MrkvArray = np.asarray(agent.MrkvArray[0])
    CFunc_slope, CFunc_intercept = extract_CFunc_arrays(eco, StateCount)
    num_base = int(agent.num_base_MrkvStates)
    RecState_per_state = np.array(
        [((j // num_base) % 2 == 1) for j in range(StateCount)], dtype=np.int32)
    n_rec = int(RecState_per_state.sum())
    print(f"  RecState=True for {n_rec}/{StateCount} states (active ADF path)")
    ADelasticity = float(eco.demand_ADelasticity)
    BoroCnstArt = float(agent.BoroCnstArt) if agent.BoroCnstArt is not None else 0.0
    print(f"  ADelasticity={ADelasticity}")

    print(f"\nRunning JAX solver ...")
    t0 = time.time()
    result = solve_one_period_jax(
        jnp.asarray(vPfuncNext_table),
        jnp.asarray(m_eval), jnp.asarray(C_eval),
        jnp.asarray(mNrmMinNext_table),
        jnp.asarray(mNrmMin_is_callable),
        jnp.asarray(mNrmMin_scalar),
        jnp.asarray(IncShk_pmv),
        jnp.asarray(IncShk_perm),
        jnp.asarray(IncShk_tran),
        jnp.asarray(LivPrb),
        DiscFac, CRRA,
        jnp.asarray(Rfree),
        jnp.asarray(PermGroFac),
        jnp.asarray(MrkvArray),
        BoroCnstArt,
        jnp.asarray(agent.aXtraGrid),
        jnp.asarray(agent.Cgrid),
        jnp.asarray(CFunc_slope),
        jnp.asarray(CFunc_intercept),
        ADelasticity,
        jnp.asarray(RecState_per_state),
    )
    print(f"JAX solver: {time.time()-t0:.2f}s (incl. JIT compile)")

    # Validate across multiple states (covering both non-recession AND recession macros)
    n_query = 50
    m_query_np = np.linspace(1.0, 10.0, n_query)
    C_query_val = 1.0
    C_query_np = np.full(n_query, C_query_val)

    # Sample states from each macro
    test_states = []
    for macro in range(min(8, StateCount // num_base)):
        for micro in [0, 1, 5]:  # employed, u1Q, noBen
            j = macro * num_base + micro
            if j < StateCount:
                test_states.append((j, macro, micro))

    print(f"\n=== Per-state validation ({len(test_states)} states, C=1.0, m in [1,10]) ===")
    print(f"{'state':>5} {'macro':>5} {'micro':>5} {'RecState':>8} {'max rel':>10} {'mean rel':>10} {'pass':>5}")
    n_pass = 0
    for j, macro, micro in test_states:
        hark_c = solution.cFunc[j](m_query_np, C_query_np)
        jax_c = np.asarray(evaluate_cFunc(
            result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
            BoroCnstArt, jnp.asarray(agent.Cgrid), j,
            jnp.asarray(m_query_np), jnp.asarray(C_query_np)))
        denom = np.maximum(np.abs(hark_c), 1e-12)
        rd = np.abs((jax_c - hark_c) / denom)
        rec = bool(RecState_per_state[j])
        passed = rd.max() < 2e-3  # slightly relaxed for ADF interpolation error
        mark = '✓' if passed else '✗'
        print(f"{j:>5} {macro:>5} {micro:>5} {str(rec):>8} {rd.max():>10.4e} {rd.mean():>10.4e} {mark:>5}")
        if passed: n_pass += 1

    print(f"\n=== {n_pass}/{len(test_states)} states pass at max_rel < 2e-3 ===")
    if n_pass == len(test_states):
        print("✓ P4 validated: JAX solver matches HARK at recession scale + ADF active")
    else:
        print(f"⚠ {len(test_states)-n_pass} states fail; investigate")


if __name__ == '__main__':
    main()
