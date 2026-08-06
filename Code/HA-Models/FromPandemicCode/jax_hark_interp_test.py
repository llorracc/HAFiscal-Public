"""Unit tests: JAX interp vs HARK reference, 1e-10 relative precision target."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from HARK.interpolation import (LinearInterp, BilinearInterp,
                                  LinearInterpOnInterp1D, LowerEnvelope2D,
                                  VariableLowerBoundFunc2D)
from HARK.interpolation_jax import (
    linear_interp_1d, bilinear_interp, bilinear_interp_derX,
    linear_interp_on_interp_1d_shared_xgrid,
    linear_interp_on_interp_1d_general,
    lower_envelope_2d_apply, marg_value_to_consumption)


def check(name, jax_val, hark_val, tol=1e-10):
    jax_val = np.asarray(jax_val)
    hark_val = np.asarray(hark_val)
    # Compare only finite vals (NaN positions should match)
    finite_match = np.isfinite(jax_val) == np.isfinite(hark_val)
    if not finite_match.all():
        print(f"  ✗ {name}: NaN mismatch — JAX nans={(~np.isfinite(jax_val)).sum()}, "
              f"HARK nans={(~np.isfinite(hark_val)).sum()}")
        return False
    finite = np.isfinite(jax_val)
    if not finite.any():
        print(f"  ✓ {name}: all NaN, matched")
        return True
    rel = np.abs((jax_val[finite] - hark_val[finite]) /
                 np.maximum(np.abs(hark_val[finite]), 1e-15))
    max_rel = rel.max()
    if max_rel < tol:
        print(f"  ✓ {name}: max rel diff = {max_rel:.2e}")
        return True
    print(f"  ✗ {name}: max rel diff = {max_rel:.2e} (> tol {tol:.0e})")
    return False


def test_linear_interp_1d():
    print("\n[T1] LinearInterp 1-D (no decay extrap)")
    rng = np.random.default_rng(42)
    x_grid = np.sort(rng.uniform(0, 10, 20))
    y_vals = np.sin(x_grid) + 0.1 * x_grid
    # Queries: interior, below, above, exact-grid
    x_query = np.concatenate([
        rng.uniform(x_grid.min(), x_grid.max(), 50),  # interior
        np.array([x_grid.min() - 1.0, x_grid.min() - 0.001]),  # below
        np.array([x_grid.max() + 0.001, x_grid.max() + 5.0]),  # above (linear extrap)
        x_grid,  # exact grid points
    ])

    hark = LinearInterp(x_grid, y_vals, lower_extrap=False)
    h_vals = hark(x_query)
    j_vals = np.asarray(linear_interp_1d(x_grid, y_vals, jnp.asarray(x_query),
                                          lower_extrap=False))
    return check("LinearInterp(x) no decay extrap", j_vals, h_vals)


def test_linear_interp_1d_lower_extrap():
    print("\n[T2] LinearInterp 1-D with lower_extrap=True")
    rng = np.random.default_rng(43)
    x_grid = np.sort(rng.uniform(0, 10, 15))
    y_vals = np.exp(-x_grid)
    x_query = rng.uniform(-5, 15, 100)

    hark = LinearInterp(x_grid, y_vals, lower_extrap=True)
    h_vals = hark(x_query)
    j_vals = np.asarray(linear_interp_1d(x_grid, y_vals, jnp.asarray(x_query),
                                          lower_extrap=True))
    return check("LinearInterp(x) lower_extrap", j_vals, h_vals)


def test_bilinear_interp():
    print("\n[T3] BilinearInterp 2-D")
    rng = np.random.default_rng(44)
    x_grid = np.sort(rng.uniform(0, 10, 12))
    y_grid = np.sort(rng.uniform(0, 5, 8))
    Xg, Yg = np.meshgrid(x_grid, y_grid, indexing='ij')
    f_vals = np.sin(Xg) * np.cos(Yg) + 0.1 * Xg

    x_query = rng.uniform(-1, 11, 80)
    y_query = rng.uniform(-0.5, 6, 80)

    hark = BilinearInterp(f_vals, x_grid, y_grid)
    h_vals = hark(x_query, y_query)
    j_vals = np.asarray(bilinear_interp(f_vals, x_grid, y_grid,
                                          jnp.asarray(x_query), jnp.asarray(y_query)))
    return check("BilinearInterp(x,y)", j_vals, h_vals)


def test_bilinear_derX():
    print("\n[T4] BilinearInterp derX")
    rng = np.random.default_rng(45)
    x_grid = np.sort(rng.uniform(0, 10, 10))
    y_grid = np.sort(rng.uniform(0, 5, 7))
    Xg, Yg = np.meshgrid(x_grid, y_grid, indexing='ij')
    f_vals = Xg ** 2 + Yg ** 2

    x_query = rng.uniform(1, 9, 50)
    y_query = rng.uniform(0.5, 4.5, 50)

    hark = BilinearInterp(f_vals, x_grid, y_grid)
    h_dx = hark.derivativeX(x_query, y_query)
    j_dx = np.asarray(bilinear_interp_derX(f_vals, x_grid, y_grid,
                                             jnp.asarray(x_query), jnp.asarray(y_query)))
    return check("BilinearInterp.derX", j_dx, h_dx)


def test_linear_on_interp_1d_shared():
    print("\n[T5] LinearInterpOnInterp1D (shared x_grid)")
    rng = np.random.default_rng(46)
    x_grid = np.sort(rng.uniform(0, 10, 15))
    y_grid = np.sort(rng.uniform(0, 5, 4))
    f_vals = np.zeros((len(y_grid), len(x_grid)))
    for k, y in enumerate(y_grid):
        f_vals[k] = np.sin(x_grid) + 0.3 * y * x_grid

    x_query = rng.uniform(x_grid.min(), x_grid.max(), 40)
    y_query = rng.uniform(y_grid.min(), y_grid.max(), 40)

    inner_interps = [LinearInterp(x_grid, f_vals[k], lower_extrap=True) for k in range(len(y_grid))]
    hark = LinearInterpOnInterp1D(inner_interps, y_grid)
    h_vals = hark(x_query, y_query)
    j_vals = np.asarray(linear_interp_on_interp_1d_shared_xgrid(
        x_grid, y_grid, f_vals, jnp.asarray(x_query), jnp.asarray(y_query)))
    return check("LinearInterpOnInterp1D shared x_grid", j_vals, h_vals)


def test_linear_on_interp_1d_general():
    print("\n[T6] LinearInterpOnInterp1D (per-y x_grid)")
    rng = np.random.default_rng(47)
    y_grid = np.sort(rng.uniform(0, 5, 4))
    # Per-y x_grids — each y has its own m_grid
    Nx = 12
    x_grids = np.zeros((len(y_grid), Nx))
    f_vals = np.zeros((len(y_grid), Nx))
    for k, y in enumerate(y_grid):
        x_grids[k] = np.sort(rng.uniform(0, 10, Nx))
        f_vals[k] = np.sin(x_grids[k]) + 0.3 * y * x_grids[k]

    x_query = rng.uniform(2, 8, 30)  # interior to all x_grids
    y_query = rng.uniform(y_grid.min(), y_grid.max(), 30)

    inner_interps = [LinearInterp(x_grids[k], f_vals[k], lower_extrap=True) for k in range(len(y_grid))]
    hark = LinearInterpOnInterp1D(inner_interps, y_grid)
    h_vals = hark(x_query, y_query)
    j_vals = np.asarray(linear_interp_on_interp_1d_general(
        x_grids, y_grid, f_vals, jnp.asarray(x_query), jnp.asarray(y_query)))
    return check("LinearInterpOnInterp1D per-y x_grid", j_vals, h_vals)


def test_lower_envelope_2d():
    print("\n[T7] LowerEnvelope2D (elementwise min)")
    rng = np.random.default_rng(48)
    N = 50
    f1 = rng.uniform(0, 10, N)
    f2 = rng.uniform(0, 10, N)
    f3 = rng.uniform(0, 10, N)
    j_min = np.asarray(lower_envelope_2d_apply(jnp.asarray(f1), jnp.asarray(f2),
                                                  jnp.asarray(f3)))
    expected = np.minimum(np.minimum(f1, f2), f3)
    return check("min(f1,f2,f3)", j_min, expected)


def test_marg_value_crra():
    print("\n[T8] MargValueFuncCRRA inverse semantics")
    rng = np.random.default_rng(49)
    rho = 2.0
    c = rng.uniform(0.1, 5.0, 30)
    vP = c ** (-rho)  # u'(c)
    c_recover = np.asarray(marg_value_to_consumption(jnp.asarray(vP), rho))
    return check("c = vP^(-1/rho)", c_recover, c)


if __name__ == '__main__':
    print("=== JAX HARK interp unit tests ===")
    results = [
        test_linear_interp_1d(),
        test_linear_interp_1d_lower_extrap(),
        test_bilinear_interp(),
        test_bilinear_derX(),
        test_linear_on_interp_1d_shared(),
        test_linear_on_interp_1d_general(),
        test_lower_envelope_2d(),
        test_marg_value_crra(),
    ]
    n_pass = sum(results)
    n = len(results)
    print(f"\n=== {n_pass}/{n} tests passed ===")
    sys.exit(0 if n_pass == n else 1)
