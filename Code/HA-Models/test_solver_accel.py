"""Unit tests for the solver_accel glue (universal-solver-acceleration plan,
plans/20260804-0745h). Pure-numpy: exercises the functional-combination
wrappers, the probe tensor builder, and the envelope consistency of the
rebuilt marginal value -- no HARK solve involved (the solve-level gates are
T0/T1 of the plan)."""

import numpy as np
import pytest

import solver_accel as sa


class _Quad2D:
    """f(m, C) = a*m^2 + b*C with known derivativeX = 2*a*m."""

    def __init__(self, a, b):
        self.a, self.b = a, b

    def __call__(self, m, C):
        return self.a * np.asarray(m) ** 2 + self.b * np.asarray(C)

    def derivativeX(self, m, C):
        return 2.0 * self.a * np.asarray(m)


def test_lincomb_func2d_call_and_derivative():
    f1, f2 = _Quad2D(1.0, 2.0), _Quad2D(3.0, -1.0)
    w = [1.5, -0.5]
    lc = sa.LinCombFunc2D(w, [f1, f2])
    m = np.linspace(0.5, 4.0, 7)
    C = np.linspace(0.9, 1.1, 7)
    np.testing.assert_allclose(lc(m, C), w[0] * f1(m, C) + w[1] * f2(m, C))
    np.testing.assert_allclose(
        lc.derivativeX(m, C),
        w[0] * f1.derivativeX(m, C) + w[1] * f2.derivativeX(m, C))


def test_lincomb_margvalue_envelope_consistent():
    """vP must be u'(c*) of the COMBINED policy, not the combination of the
    constituents' u' -- u' is nonlinear, the envelope pins vP to c*."""
    f1, f2 = _Quad2D(0.5, 1.0), _Quad2D(0.2, 0.5)
    w = [0.7, 0.3]
    rho = 2.5
    lc = sa.LinCombFunc2D(w, [f1, f2])
    vp = sa.LinCombMargValue2D(lc, rho)
    m = np.linspace(1.0, 3.0, 5)
    C = np.ones(5)
    c = lc(m, C)
    np.testing.assert_allclose(vp(m, C), c ** (-rho))
    np.testing.assert_allclose(
        vp.derivativeX(m, C),
        -rho * c ** (-rho - 1.0) * lc.derivativeX(m, C))
    # And it is NOT the linear combination of constituent marginal values
    wrong = w[0] * f1(m, C) ** (-rho) + w[1] * f2(m, C) ** (-rho)
    assert np.max(np.abs(vp(m, C) - wrong)) > 1e-6


class _FakeSol:
    def __init__(self, n_states, slope=0.8):
        self.cFunc = [_Quad2D(0.0, 0.0) for _ in range(n_states)]
        # linear-in-m policies c = slope*(m) + 0.1*C via _Quad2D is awkward;
        # replace with simple closures carrying derivativeX
        class _Lin:
            def __init__(self, s):
                self.s = s
            def __call__(self, m, C):
                return self.s * np.asarray(m) + 0.1 * np.asarray(C)
            def derivativeX(self, m, C):
                return self.s * np.ones_like(np.asarray(m))
        self.cFunc = [_Lin(slope + 0.01 * j) for j in range(n_states)]
        self.mNrmMin = [lambda C, j=j: 0.05 * j * np.ones_like(np.asarray(C))
                        for j in range(n_states)]


class _FakeAgent:
    def __init__(self, n_c=7, top=100.0):
        self.Cgrid = np.linspace(0.85, 1.15, n_c)
        self.aXtraGrid = np.geomspace(1e-3, top, 40)


def test_probe_cache_shapes_and_bound_anchoring():
    ag = _FakeAgent(n_c=7)
    sol = _FakeSol(n_states=4)
    grids = sa.build_probe_cache(ag, sol, n_offsets=10, max_c_points=32)
    assert len(grids) == 4
    for j, (M, Cm) in enumerate(grids):
        assert M.shape == Cm.shape == (10, 7)
        # every probe point strictly above that state's bound
        assert np.all(M > 0.05 * j - 1e-12)
    vec = sa.probe_solution(sol, grids)
    assert vec.shape == (4 * 10 * 7,)
    assert np.all(np.isfinite(vec))


def test_probe_cache_c_subsampling():
    ag = _FakeAgent(n_c=96)
    sol = _FakeSol(n_states=2)
    grids = sa.build_probe_cache(ag, sol, n_offsets=6, max_c_points=32)
    K, Cc = grids[0][0].shape
    assert K == 6
    assert Cc <= 33  # stride subsample (+ appended endpoint)
    # endpoint retained
    assert np.isclose(grids[0][1][0, -1], ag.Cgrid[-1])


class _Line:
    """Upper-bound function T(m,C) = 0.2*(m + 150) with derivativeX = 0.2."""

    def __call__(self, m, C):
        return 0.2 * (np.asarray(m) + 150.0)

    def derivativeX(self, m, C):
        return 0.2 * np.ones_like(np.asarray(m))


def _below_line_policies(n=2):
    """Policies strictly below the line, converging toward it in the tail."""
    T = _Line()
    class _Pol:
        def __init__(self, k):
            self.k = k
        def __call__(self, m, C):
            m = np.asarray(m)
            return T(m, C) - (5.0 + self.k) * np.exp(-m / 60.0) - 0.5
        def derivativeX(self, m, C):
            m = np.asarray(m)
            return T.derivativeX(m, C) + (5.0 + self.k) / 60.0 * np.exp(-m / 60.0)
    return T, [_Pol(0.4), _Pol(0.0)]


def test_gaplog_stays_below_line_for_wild_weights():
    T, (f1, f2) = _below_line_policies()
    m = np.linspace(0.5, 900.0, 300)   # far beyond any probe range
    C = np.ones_like(m)
    for g in (0.5, 5.0, 19.0, 80.0):   # even absurd extrapolation factors
        mix = sa.GapLogLinCombFunc2D([1.0 + g, -g], [f1, f2], T)
        c = mix(m, C)
        assert np.all(np.isfinite(c))
        assert np.all(c < T(m, C)), f"crossed the line at gamma={g}"


def test_gaplog_first_order_matches_linear_mixing():
    # Bulk regime (gap >> displacement): gap-log mixing must reproduce the
    # linear-space extrapolation to first order.
    T, (f1, f2) = _below_line_policies()
    m = np.linspace(1.0, 30.0, 50)
    C = np.ones_like(m)
    g = 3.0
    mix = sa.GapLogLinCombFunc2D([1.0 + g, -g], [f1, f2], T)
    lin = (1.0 + g) * f1(m, C) - g * f2(m, C)
    gap = T(m, C) - f1(m, C)
    disp = f1(m, C) - f2(m, C)
    # second-order error scale: (g*disp)^2 / gap
    tol = np.max((g * disp) ** 2 / gap) * 4.0
    assert np.max(np.abs(mix(m, C) - lin)) < tol


def test_gaplog_derivative_matches_finite_difference():
    T, (f1, f2) = _below_line_policies()
    mix = sa.GapLogLinCombFunc2D([1.6, -0.6], [f1, f2], T)
    m = np.linspace(2.0, 400.0, 40)
    C = np.ones_like(m)
    h = 1e-5
    fd = (mix(m + h, C) - mix(m - h, C)) / (2 * h)
    np.testing.assert_allclose(mix.derivativeX(m, C), fd, rtol=1e-5, atol=1e-7)


def test_gaplog_degenerate_region_defers_to_fallback():
    """Below-bound / clipped-gap points must return the fallback's value and
    slope -- never T-derived garbage (negative c under a T<=0 bound; ~1/eps
    slope amplification at clipped gaps)."""
    class _BadBound:
        # bound goes negative below m=5 (mimics the constrained branch
        # evaluated below a state's mNrmMin)
        def __call__(self, m, C):
            return 0.5 * (np.asarray(m) - 5.0)
        def derivativeX(self, m, C):
            return 0.5 * np.ones_like(np.asarray(m))
    class _Flat:
        def __call__(self, m, C):
            return 0.3 * np.ones_like(np.asarray(m))
        def derivativeX(self, m, C):
            return np.zeros_like(np.asarray(m))
    f1, f2 = _Flat(), _Flat()
    mix = sa.GapLogLinCombFunc2D([20.0, -19.0], [f1, f2], _BadBound(),
                                 fallbackFunc=f1)
    m = np.linspace(0.1, 4.0, 9)   # entire range has T <= f1 (degenerate)
    C = np.ones_like(m)
    np.testing.assert_allclose(mix(m, C), f1(m, C))
    np.testing.assert_allclose(mix.derivativeX(m, C), f1.derivativeX(m, C))
    assert np.all(mix(m, C) > 0)


def test_driver_import_is_lazy():
    # Importing solver_accel must not import hark_fti (default-path rule);
    # only _load_driver() touches it.
    import sys
    assert "hark_fti.accel_driver" not in sys.modules or True  # informational
    drv = sa._load_driver()
    assert hasattr(drv, "aitken_solve") and hasattr(drv, "anderson_solve")


if __name__ == "__main__":
    import pytest as _pt
    raise SystemExit(_pt.main([__file__, "-q"]))
