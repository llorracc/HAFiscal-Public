"""Validate jax_solver_kernel against HARK at HAFiscal HS_Only scale.

Strategy:
  1. Build HAFiscal HS_Only single-beta agent
  2. Solve via HARK → get converged solution (cFunc, vPfunc, mNrmMin per state)
  3. Tabulate solution_next (vPfuncNext at fixed grid)
  4. Run jax_solver_kernel.solve_one_period_jax with solution_next = converged solution
  5. At a fixed point, JAX output cNrm should match HARK's cFunc evaluation
  6. Evaluate at interior query points (well above borrowing constraint)

Pass criterion: max rel diff < 1e-3 at interior points.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_solver_kernel import solve_one_period_jax, evaluate_cFunc


def tabulate_vPfuncNext(solution_next, StateCount, m_eval, C_eval):
    """Tabulate vPfunc[j](m, C) on a fixed (m, C) eval grid for each next-state j."""
    table = np.zeros((StateCount, len(m_eval), len(C_eval)))
    mM, cC = np.meshgrid(m_eval, C_eval, indexing='ij')
    for j in range(StateCount):
        vP = solution_next.vPfunc[j](mM, cC)
        table[j] = vP
    return table


def tabulate_mNrmMinNext(solution_next, StateCount, C_eval):
    """Tabulate mNrmMin[j](C) for each next-state j, plus is_callable + scalar fallback."""
    table = np.zeros((StateCount, len(C_eval)))
    is_callable = np.zeros(StateCount, dtype=bool)
    scalar = np.zeros(StateCount)
    for j in range(StateCount):
        mNrmMinNext_j = solution_next.mNrmMin[j]
        if isinstance(mNrmMinNext_j, float) or (hasattr(mNrmMinNext_j, '__class__') and
                                                  'float' in str(type(mNrmMinNext_j))):
            is_callable[j] = False
            scalar[j] = float(mNrmMinNext_j)
            table[j] = float(mNrmMinNext_j) * C_eval  # broadcast (matches HARK semantics)
        else:
            is_callable[j] = True
            table[j] = mNrmMinNext_j(C_eval)
            scalar[j] = 0.0  # unused
    return table, is_callable, scalar


def extract_CFunc_arrays(eco, StateCount):
    """Extract CFunc[i][j] = CRule(slope, intercept) into two (StateCount, StateCount) arrays."""
    slope = np.zeros((StateCount, StateCount))
    intercept = np.zeros((StateCount, StateCount))
    for i in range(StateCount):
        for j in range(StateCount):
            rule = eco.CFunc[i][j]
            slope[i][j] = float(rule.slope)
            intercept[i][j] = float(rule.intercept)
    return slope, intercept


def main():
    print("=== JAX solver kernel validation: HS_Only single-beta agent ===")
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    print(f"build+solve: {time.time()-t0:.1f}s")

    # HS_Only is a single cohort
    print(f"  num cohorts: {len(AggEco.agents)}")
    agent = AggEco.agents[0]
    if not hasattr(agent, 'solution') or agent.solution is None:
        print("Agent not solved; solving now...")
        agent.solve()

    solution = agent.solution[0]
    StateCount = len(solution.cFunc)
    Ccount = agent.Cgrid.size
    aCount = agent.aXtraGrid.size
    print(f"StateCount={StateCount}, Ccount={Ccount}, aCount={aCount}")

    # Build eval grid for vPfunc tabulation — log-spaced for curvature near 0
    m_eval = np.concatenate([
        np.linspace(0.001, 0.1, 100),
        np.linspace(0.1, 1.0, 200),
        np.linspace(1.0, 5.0, 200),
        np.linspace(5.0, 50.0, 200),
    ])
    m_eval = np.unique(m_eval)
    C_eval = np.array(agent.Cgrid)         # use same Cgrid as solver
    print(f"Tabulating solution_next on m_eval={len(m_eval)}, C_eval={len(C_eval)} ...")

    vPfuncNext_table = tabulate_vPfuncNext(solution, StateCount, m_eval, C_eval)
    mNrmMinNext_table, mNrmMin_is_callable, mNrmMin_scalar = tabulate_mNrmMinNext(
        solution, StateCount, C_eval)

    # Extract IncShkDstn arrays — HAFiscal stores as list[period_list][state_list]
    IncShkDstn_states = agent.IncShkDstn[0]  # first (only) period
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
        # Pad with perm=1.0 to avoid div-by-zero in kernel (pmv=0 → no contribution to sum)
        IncShk_perm[j, n:] = 1.0

    # Extract per-state params
    Rfree = np.asarray(agent.Rfree[:StateCount])
    PermGroFac = np.asarray(agent.PermGroFac[0][:StateCount])
    LivPrb = np.asarray(agent.LivPrb[0][:StateCount])
    DiscFac = float(agent.DiscFac)
    CRRA = float(agent.CRRA)

    # Extract MrkvArray
    MrkvArray = np.asarray(agent.MrkvArray[0])
    print(f"MrkvArray shape: {MrkvArray.shape}")

    # Extract CFunc arrays
    CFunc_slope, CFunc_intercept = extract_CFunc_arrays(AggEco, StateCount)

    # Build RecState per state: state j is recession if (j // num_base_MrkvStates) % 2 == 1
    num_base = int(agent.num_base_MrkvStates)
    RecState_per_state = np.array(
        [((j // num_base) % 2 == 1) for j in range(StateCount)], dtype=np.int32)

    ADelasticity = float(AggEco.demand_ADelasticity)
    BoroCnstArt = float(agent.BoroCnstArt) if agent.BoroCnstArt is not None else 0.0

    # Diagnostic: check inputs
    print(f"\nInput diagnostics:")
    print(f"  vPfuncNext_table: shape={vPfuncNext_table.shape}, "
          f"finite={np.isfinite(vPfuncNext_table).all()}, "
          f"min={vPfuncNext_table.min():.4f}, max={vPfuncNext_table.max():.4f}")
    print(f"  mNrmMinNext_table: shape={mNrmMinNext_table.shape}, "
          f"finite={np.isfinite(mNrmMinNext_table).all()}")
    print(f"  mNrmMin_is_callable: {mNrmMin_is_callable}")
    print(f"  mNrmMin_scalar: {mNrmMin_scalar}")
    print(f"  IncShk_pmv sum per j: {IncShk_pmv.sum(axis=1)}")
    print(f"  IncShk_perm min/max: {IncShk_perm.min()}/{IncShk_perm.max()}")
    print(f"  IncShk_tran min/max: {IncShk_tran.min()}/{IncShk_tran.max()}")
    print(f"  Rfree: {Rfree}")
    print(f"  PermGroFac: {PermGroFac}")
    print(f"  LivPrb: {LivPrb}")
    print(f"  DiscFac={DiscFac}, CRRA={CRRA}")
    print(f"  BoroCnstArt={BoroCnstArt}")
    print(f"  aXtraGrid[:5]={np.asarray(agent.aXtraGrid)[:5]}, [-3:]={np.asarray(agent.aXtraGrid)[-3:]}")
    print(f"  Cgrid: {agent.Cgrid}")
    print(f"  RecState_per_state: {RecState_per_state}")
    print(f"  MrkvArray[0]: {MrkvArray[0]}")
    print(f"  CFunc_intercept[0]: {CFunc_intercept[0]}")
    print(f"  CFunc_slope[0]: {CFunc_slope[0]}")

    print(f"\nInputs ready. Running JAX solver ...")
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

    # Diagnostic: check outputs
    print(f"\nOutput diagnostics:")
    print(f"  cNrm shape={result['cNrm'].shape}, "
          f"finite={np.isfinite(np.asarray(result['cNrm'])).all()}, "
          f"min={float(np.nanmin(np.asarray(result['cNrm']))):.4f}, "
          f"max={float(np.nanmax(np.asarray(result['cNrm']))):.4f}")
    print(f"  mNrm finite={np.isfinite(np.asarray(result['mNrm'])).all()}")
    print(f"  BoroCnstNat_per_j: {np.asarray(result['BoroCnstNat_per_j'])}")
    print(f"  BoroCnstNat_per_i: {np.asarray(result['BoroCnstNat_per_i'])}")

    # Evaluate JAX cFunc and HARK cFunc at interior query points for state 0
    state_i = 0
    n_query = 50
    m_query_np = np.linspace(1.0, 10.0, n_query)  # interior, well above constraint
    C_query_val = 1.0  # middle of Cgrid
    C_query_np = np.full(n_query, C_query_val)

    # HARK cFunc[i](m, C)
    hark_c = solution.cFunc[state_i](m_query_np, C_query_np)

    # JAX evaluate_cFunc
    jax_c = np.asarray(evaluate_cFunc(
        result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
        BoroCnstArt, jnp.asarray(agent.Cgrid), state_i,
        jnp.asarray(m_query_np), jnp.asarray(C_query_np)))

    # Compare
    rel_diff = np.abs((jax_c - hark_c) / np.maximum(np.abs(hark_c), 1e-12))
    print(f"\n=== State {state_i}, C={C_query_val}, m in [1, 10]: comparison ===")
    print(f"  HARK cFunc[:5] = {hark_c[:5]}")
    print(f"  JAX  cFunc[:5] = {jax_c[:5]}")
    print(f"  max rel diff: {rel_diff.max():.4e}")
    print(f"  mean rel diff: {rel_diff.mean():.4e}")
    if rel_diff.max() < 1e-3:
        print(f"  ✓ JAX matches HARK to <0.1% — P2+P3 validated at state 0")
    else:
        print(f"  ✗ JAX diverges from HARK by {rel_diff.max():.2e} (target <1e-3)")

    # Try a few more states
    print(f"\n=== Same comparison across multiple states ===")
    for state_i_try in [0, 1, 2, 6, 12]:
        if state_i_try >= StateCount:
            continue
        hark_c_s = solution.cFunc[state_i_try](m_query_np, C_query_np)
        jax_c_s = np.asarray(evaluate_cFunc(
            result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
            BoroCnstArt, jnp.asarray(agent.Cgrid), state_i_try,
            jnp.asarray(m_query_np), jnp.asarray(C_query_np)))
        rd = np.abs((jax_c_s - hark_c_s) / np.maximum(np.abs(hark_c_s), 1e-12))
        mark = '✓' if rd.max() < 1e-3 else '✗'
        print(f"  state={state_i_try}: max rel diff = {rd.max():.4e} {mark}")


if __name__ == '__main__':
    main()
