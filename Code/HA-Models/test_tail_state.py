"""Fast unit tests for HAFISCAL_DIST_TAIL_STATE (the P4' analytic tail state).

Covers, per the build brief:
  * column-stochasticity of a small random tail-state TM built by the REAL
    kernel (_build_period_tm_a_tail), cross-checked cell-by-cell against an
    INDEPENDENT dense reference implementing the DERIVATION note's column
    recipe, plus newborn-zero-tail, strong irreducibility (T communicates --
    verified, not assumed) and a positive stationary tail mass;
  * byte-identity smoke of the flag-off path: the base kernel
    (_build_period_tm_a) must be bit-identical whether the flag is on or off
    (the flag acts ONLY through the build_tm_agg_fiscal_a dispatch), and the
    dispatcher-level scope guards must fire BEFORE any agent attribute is
    touched;
  * the re-entry law against the note's V2 Monte Carlo numbers (P(stay) =
    m^alpha; truncated-Pareto landing lotteried through the kernel-style
    searchsorted/clip/linear-weight code);
  * the T_age-split Kesten alpha resolution against the note's V1/V3 pins
    (ledger 1.779332 raw; production split 2.163413; subcritical and
    band-out per-atom disables);
  * the read-out expansion (terminal atom => exactly mean-preserving at any
    span; K-invariance) and the disabled-atom m_top materiality tripwire;
  * the experiment/Step-5a refusals (flag-on entry raises + the (A+1)*J
    size tripwires in the aggregators/propagator).

All tests are economy-free (stub agents / synthetic fixtures); total wall
well under 30 s including the seeded 1e6-draw MC.
"""
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [sys.argv[0]]
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if os.path.join(_HERE, "FromPandemicCode") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, "FromPandemicCode"))

import dist_tail_state as dts  # noqa: E402
import per_atom_alpha as paa  # noqa: E402
import tm_methods as tmm  # noqa: E402

FLAG = "HAFISCAL_DIST_TAIL_STATE"


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

def test_flag_parse_off_on_and_raise(monkeypatch):
    for off_val in ("", "0", "off", "OFF", " off "):
        monkeypatch.setenv(FLAG, off_val)
        assert tmm._dist_tail_state_enabled() is False
    monkeypatch.delenv(FLAG, raising=False)
    assert tmm._dist_tail_state_enabled() is False
    for on_val in ("1", "on", "ON"):
        monkeypatch.setenv(FLAG, on_val)
        assert tmm._dist_tail_state_enabled() is True
    monkeypatch.setenv(FLAG, "banana")
    with pytest.raises(ValueError, match=FLAG):
        tmm._dist_tail_state_enabled()


# ---------------------------------------------------------------------------
# Re-entry law (DERIVATION note section 2, V2)
# ---------------------------------------------------------------------------

# The note's V2 fixture: ledger alpha, unit top, production-like grid top.
V2_ALPHA = 1.779
V2_X = 1.0
V2_GRID = np.array([0.85, 0.88, 0.92, 0.96, 1.00])
# The note's printed theory node masses at m=0.90 (6-dp, so pin at 1e-6):
V2_NODES_M090 = np.array([0.056659, 0.376870, 0.387234, 0.179236])


def test_landing_node_weights_matches_note_pins():
    node = dts.landing_node_weights(V2_ALPHA, 0.90, V2_GRID)
    assert node.shape == V2_GRID.shape
    assert abs(node.sum() - 1.0) < 1e-12
    assert np.all(node >= 0.0)
    # first grid node (0.85) is below the landing support [0.90, 1.0): zero
    assert node[0] == 0.0
    np.testing.assert_allclose(node[1:], V2_NODES_M090, atol=1e-6)


def test_landing_node_weights_validation():
    with pytest.raises(ValueError, match="alpha > 1"):
        dts.landing_node_weights(1.0, 0.9, V2_GRID)
    for bad_m in (1.0, 1.02, 0.0, -0.5):
        with pytest.raises(ValueError, match="0 < m < 1"):
            dts.landing_node_weights(V2_ALPHA, bad_m, V2_GRID)


def test_reentry_law_monte_carlo():
    """The note's V2 MC at N=1e6 (seeded, deterministic): stay prob and node
    masses through the kernel-style lottery, within a few binomial SE."""
    N = 1_000_000
    rng = np.random.default_rng(20260726)
    u = rng.random(N)
    a = V2_X * u ** (-1.0 / V2_ALPHA)  # Pareto(alpha) on [X, inf)

    for m in (0.90, 0.97, 1.02):
        ap = m * a
        stay = ap >= V2_X
        p_th = min(m ** V2_ALPHA, 1.0)
        p_emp = stay.mean()
        assert abs(p_emp - p_th) <= max(5e-3 * p_th, 1e-12), (m, p_emp, p_th)
        ret = ap[~stay]
        if m >= 1.0:
            assert ret.size == 0  # all mass stays
            continue
        # kernel-style lottery (searchsorted/clip/linear weights)
        node_emp = np.zeros(len(V2_GRID))
        idx = np.searchsorted(V2_GRID, ret, side="right") - 1
        idx = np.clip(idx, 0, len(V2_GRID) - 2)
        lo, hi = V2_GRID[idx], V2_GRID[idx + 1]
        wU = np.clip((ret - lo) / (hi - lo), 0.0, 1.0)
        np.add.at(node_emp, idx, 1.0 - wU)
        np.add.at(node_emp, idx + 1, wU)
        node_emp /= ret.size
        node_th = dts.landing_node_weights(V2_ALPHA, m, V2_GRID)
        # ~171k returns at m=0.90: SE <= 1.2e-3 per node; 26k at m=0.97.
        np.testing.assert_allclose(node_emp, node_th, atol=6e-3)


# ---------------------------------------------------------------------------
# Alpha resolution (note sections 3 + 6, V1/V3 pins)
# ---------------------------------------------------------------------------

def _ledger_agent(beta=1.00537, T_age=200):
    """The cap-atom ledger spec (per_atom_alpha module docstring / note V3)."""
    psi_atoms, psi_pmv = paa.equiprobable_mean_one_lognormal(0.003, 7)
    emp = SimpleNamespace(atoms=[psi_atoms, np.ones_like(psi_atoms)],
                          pmv=psi_pmv)
    return SimpleNamespace(
        DiscFac=beta, Rfree=np.array([1.01]), CRRA=2.0,
        PermGroFac=[np.array([1.00490])],
        LivPrb=[np.array([1.0 - 1.0 / 160.0])],
        T_age=T_age, IncShkDstn=[[emp]])


def test_resolve_tail_alpha_ledger_and_split_pins():
    # No T_age: the raw-L ledger root (note V1a/V3: 1.779332)
    info_raw = dts.resolve_tail_alpha(_ledger_agent(T_age=None))
    assert info_raw["enabled"]
    assert abs(info_raw["alpha"] - 1.779332) < 5e-4
    # Production T_age=200: the SPLIT root (note V3: adapter = 2.163413)
    info_split = dts.resolve_tail_alpha(_ledger_agent(T_age=200))
    assert info_split["enabled"]
    assert abs(info_split["alpha"] - 2.163413) < 5e-4
    assert info_split["alpha_source"] == "kesten-split(T_age)"
    # kappa pin (note V1: kappa(L inside) = 0.00541743)
    assert abs(info_split["kappa"] - 0.00541743) < 1e-6
    # pat_num = (1-kappa)*R identity
    assert abs(info_split["pat_num"] - (1.0 - info_split["kappa"]) * 1.01) < 1e-12
    # L_eff pin (note V3: L_eff(T_age=200) = 0.991254)
    assert abs(info_split["L_eff"] - 0.991254) < 1e-6


def test_resolve_tail_alpha_disables():
    # Subcritical atom (note V6b beta=0.8): kesten raises -> per-atom disable
    info_sub = dts.resolve_tail_alpha(_ledger_agent(beta=0.8, T_age=200))
    assert not info_sub["enabled"]
    assert "SUBCRITICAL" in info_sub["reason"]
    # beta=0.9: root ~57 (note V6b) -> caught by the (1, 20) band
    info_band = dts.resolve_tail_alpha(_ledger_agent(beta=0.9, T_age=None))
    assert not info_band["enabled"]
    assert "plausibility band" in info_band["reason"]


def test_effective_livprb_scalar_locked_to_tm_methods():
    for L in (0.99375, 0.95, 0.999):
        for T_age in (None, 120, 200, 400):
            ours = dts._effective_LivPrb_scalar(L, T_age)
            theirs = float(tmm._effective_LivPrb(np.array([L]), T_age)[0])
            assert abs(ours - theirs) < 1e-15, (L, T_age, ours, theirs)


# ---------------------------------------------------------------------------
# Read-out expansion (note section 5, V5)
# ---------------------------------------------------------------------------

def test_tail_readout_nodes_mean_exact_and_k_invariant():
    for alpha, span in ((1.47, 100.0), (2.17, 1000.0), (2.163413, 1000.0)):
        nodes, w = dts.tail_readout_nodes(alpha, X=1300.0, K=12, span=span)
        assert nodes.shape == (13,) and w.shape == (13,)
        assert abs(w.sum() - 1.0) < 1e-12
        assert np.all(w > 0.0) and np.all(nodes >= 1300.0)
        # terminal atom: mass span^-alpha at alpha/(alpha-1)*span*X
        assert abs(w[-1] - span ** (-alpha)) < 1e-15
        assert abs(nodes[-1] - alpha / (alpha - 1.0) * span * 1300.0) < 1e-6
        # exactly mean-preserving at ANY span (the terminal atom's job):
        exact_mean = alpha / (alpha - 1.0) * 1300.0
        assert abs(float(nodes @ w) / exact_mean - 1.0) < 1e-12
    # K-invariance of the mean (estimands of record wholly contain the tail)
    means = []
    for K in (6, 12, 24):
        nodes, w = dts.tail_readout_nodes(2.17, X=1300.0, K=K, span=1000.0)
        means.append(float(nodes @ w))
    assert max(means) - min(means) < 1e-9 * means[0]


# ---------------------------------------------------------------------------
# The tail-state TM kernel itself (note section 4, V4 -- against the REAL
# _build_period_tm_a_tail, cross-checked vs an independent dense reference)
# ---------------------------------------------------------------------------

def _fixture():
    """Small deterministic fixture exercising below/interior/above lottery
    mass, a stay-all atom (m>1), an exactly-boundary atom (m=1), and a
    2-cell landing span (m=0.714)."""
    rng = np.random.default_rng(7)
    A, J = 6, 3
    dist_aGrid = np.array([0.0, 0.10, 0.30, 0.55, 0.80, 1.00])
    micro_trans = rng.uniform(0.05, 1.0, (J, J))
    micro_trans /= micro_trans.sum(axis=1, keepdims=True)
    LivPrb_arr = np.array([0.95, 0.93, 0.97])       # the culling (L_eff role)
    Rfree_arr = np.full(J, 1.5)
    PermGroFac_arr = np.array([1.0, 1.02, 0.98])
    psi = np.array([0.6, 1.2, 1.0, 1.4])
    xi = np.array([0.20, 0.30, 0.10, 0.25])
    dstns = []
    for jp in range(J):
        pmv = rng.uniform(0.1, 1.0, len(psi))
        pmv /= pmv.sum()
        dstns.append(SimpleNamespace(pmv=pmv, atoms=[psi, xi]))
    cFuncs = [lambda m, cr: 0.5 * m for _ in range(J)]
    markov_w = rng.uniform(0.2, 1.0, J)
    markov_w /= markov_w.sum()
    tail_state = {"alpha": 1.6, "pat_num": 1.0}
    return (dist_aGrid, cFuncs, dstns, micro_trans, Rfree_arr,
            PermGroFac_arr, LivPrb_arr, markov_w, tail_state)


def _reference_tail_tm(dist_aGrid, cFuncs, dstns, micro_trans, Rfree_arr,
                       PermGroFac_arr, LivPrb_arr, NewBorn, tail_state):
    """Independent dense implementation of the note's column recipe
    (per-(i, j, jp, s) loops; no code shared with the kernel)."""
    A = len(dist_aGrid)
    J = micro_trans.shape[0]
    stride = A + 1
    X = float(dist_aGrid[-1])
    alpha = tail_state["alpha"]
    pat = tail_state["pat_num"]
    T = np.zeros((stride * J, stride * J))
    for j in range(J):
        L = LivPrb_arr[j]
        for i in range(stride):            # death from ALL A+1 columns
            T[:, j * stride + i] += (1.0 - L) * NewBorn
        for jp in range(J):
            if micro_trans[j, jp] < 1e-15:
                continue
            d = dstns[jp]
            for s in range(len(d.pmv)):
                w = L * micro_trans[j, jp] * d.pmv[s]
                # ordinary columns
                for i in range(A):
                    m_next = (Rfree_arr[jp] * dist_aGrid[i]
                              / (PermGroFac_arr[jp] * d.atoms[0][s])
                              + d.atoms[1][s])
                    # the fixture's known ESC policy c = 0.5*m, inlined so the
                    # reference shares no code path with the kernel
                    a_next = m_next - 0.5 * m_next
                    col = j * stride + i
                    if a_next >= X:
                        T[jp * stride + A, col] += w      # redirect to T
                    elif a_next <= dist_aGrid[0]:
                        T[jp * stride + 0, col] += w
                    else:
                        k = np.searchsorted(dist_aGrid, a_next,
                                            side="right") - 1
                        wU = (a_next - dist_aGrid[k]) \
                            / (dist_aGrid[k + 1] - dist_aGrid[k])
                        T[jp * stride + k, col] += w * (1.0 - wU)
                        T[jp * stride + k + 1, col] += w * wU
                # tail column
                colT = j * stride + A
                m = pat / (PermGroFac_arr[jp] * d.atoms[0][s])
                if m >= 1.0:
                    T[jp * stride + A, colT] += w
                else:
                    stay = m ** alpha
                    T[jp * stride + A, colT] += w * stay
                    node = dts.landing_node_weights(alpha, m, dist_aGrid)
                    for k in range(A):
                        if node[k] > 0:
                            T[jp * stride + k, colT] += w * (1.0 - stay) * node[k]
    return T


def test_tail_tm_column_stochastic_irreducible_and_matches_reference():
    (dist_aGrid, cFuncs, dstns, micro_trans, Rfree_arr, PermGroFac_arr,
     LivPrb_arr, markov_w, tail_state) = _fixture()
    A, J = len(dist_aGrid), micro_trans.shape[0]
    stride = A + 1

    NewBorn = tmm._make_newborn_dist_a_tail(dist_aGrid, markov_w)
    tail_rows = np.arange(J) * stride + A
    assert NewBorn.shape == (stride * J,)
    assert np.all(NewBorn[tail_rows] == 0.0)   # newborns at the grid bottom
    assert abs(NewBorn.sum() - 1.0) < 1e-15

    TM = tmm._build_period_tm_a_tail(
        dist_aGrid, 0.0, cFuncs, dstns, micro_trans, Rfree_arr,
        PermGroFac_arr, LivPrb_arr, NewBorn, tail_state,
        Cratio=1.0, interpretation="ESC")
    assert TM.shape == (stride * J, stride * J)

    # column-stochastic including death->newborn
    colsum = np.asarray(TM.sum(axis=0)).ravel()
    assert np.max(np.abs(colsum - 1.0)) < 1e-12

    # cell-by-cell against the independent dense reference
    T_ref = _reference_tail_tm(dist_aGrid, cFuncs, dstns, micro_trans,
                               Rfree_arr, PermGroFac_arr, LivPrb_arr,
                               NewBorn, tail_state)
    np.testing.assert_allclose(TM.toarray(), T_ref, atol=1e-14)

    # irreducibility VERIFIED, not assumed: T communicates via re-entry+death
    n_comp, _ = connected_components(sp.csr_matrix(TM.toarray() > 0),
                                     directed=True, connection="strong")
    assert n_comp == 1

    # the actual production ergodic solver converges with pi_T > 0
    v = tmm.find_ergodic_distribution(TM)
    assert abs(v.sum() - 1.0) < 1e-9
    resid = np.max(np.abs(TM @ v - v))
    assert resid < 1e-10
    pi_T = float(v[tail_rows].sum())
    assert 0.0 < pi_T < 1.0

    # ESC-only kernel guard
    with pytest.raises(ValueError, match="ESC-only"):
        tmm._build_period_tm_a_tail(
            dist_aGrid, 0.0, cFuncs, dstns, micro_trans, Rfree_arr,
            PermGroFac_arr, LivPrb_arr, NewBorn, tail_state,
            Cratio=1.0, interpretation="CDC")


def test_base_kernel_is_flag_blind(monkeypatch):
    """Byte-identity smoke: the base kernel must produce BIT-IDENTICAL output
    whether the flag is on or off (the flag acts only via the
    build_tm_agg_fiscal_a dispatch, never inside _build_period_tm_a)."""
    (dist_aGrid, cFuncs, dstns, micro_trans, Rfree_arr, PermGroFac_arr,
     LivPrb_arr, markov_w, _) = _fixture()
    NewBorn = tmm._make_newborn_dist_a(dist_aGrid, markov_w)

    def build():
        return tmm._build_period_tm_a(
            dist_aGrid, 0.0, cFuncs, dstns, micro_trans, Rfree_arr,
            PermGroFac_arr, LivPrb_arr, NewBorn, Cratio=1.0,
            neutral_measure=False, interpretation="ESC")

    monkeypatch.delenv(FLAG, raising=False)
    T_off = build().toarray()
    monkeypatch.setenv(FLAG, "on")
    T_on = build().toarray()
    assert T_off.tobytes() == T_on.tobytes()
    # base kernel is column-stochastic and piles the above-mass at node A-1
    # (no tail rows exist): shape is A*J
    A, J = len(dist_aGrid), micro_trans.shape[0]
    assert T_off.shape == (A * J, A * J)
    assert np.max(np.abs(T_off.sum(axis=0) - 1.0)) < 1e-12


# ---------------------------------------------------------------------------
# Dispatcher guards fire BEFORE agent access (agent=None proves it)
# ---------------------------------------------------------------------------

def test_builder_scope_guards_fire_before_agent(monkeypatch):
    monkeypatch.setenv(FLAG, "on")
    monkeypatch.delenv("HAFISCAL_INTERPRETATION", raising=False)
    with pytest.raises(RuntimeError, match="Cratio == 1.0"):
        tmm.build_tm_agg_fiscal_a(None, Cratio=2.0)
    with pytest.raises(RuntimeError, match="neutral_measure"):
        tmm.build_tm_agg_fiscal_a(None, neutral_measure=True)
    # env interpretation defaults to CDC -> ESC-only guard
    with pytest.raises(RuntimeError, match="ESC-only"):
        tmm.build_tm_agg_fiscal_a(None)
    # mutual exclusion with the read-out tail bucket
    monkeypatch.setenv("HAFISCAL_INTERPRETATION", "ESC")
    monkeypatch.setenv("HAFISCAL_DIST_TAIL_BUCKET", "on")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        tmm.build_tm_agg_fiscal_a(None)


def test_experiment_path_refuses_loudly(monkeypatch):
    A = 6
    grid = np.linspace(0.0, 1.0, A)
    # flag-on entry refusals, before any agent attribute is touched
    monkeypatch.setenv(FLAG, "on")
    with pytest.raises(RuntimeError, match=FLAG):
        tmm.build_experiment_period_tm_a(None, 0, grid)
    with pytest.raises(RuntimeError, match=FLAG):
        tmm.propagate_experiment_tm_a(None, np.zeros(A * 3), [0], grid, 1.0)
    # size tripwire fires even with the flag OFF (a tail ergodic handed
    # across the scope boundary)
    monkeypatch.delenv(FLAG, raising=False)
    fake = SimpleNamespace(num_base_MrkvStates=3, Splurge=0.3)
    with pytest.raises(RuntimeError, match="TAIL-STATE"):
        tmm.propagate_experiment_tm_a(fake, np.zeros((A + 1) * 3), [0],
                                      grid, 1.0)


def test_aggregators_refuse_tail_sized_inputs():
    A, J = 6, 3
    grid = np.linspace(0.0, 1.0, A)
    fake = SimpleNamespace(MrkvArray=[np.eye(J)])
    with pytest.raises(RuntimeError, match="TAIL-STATE"):
        tmm.compute_type_aggregates_tm_a(
            fake, {"dist_aGrid": grid}, np.zeros((A + 1) * J))
    with pytest.raises(RuntimeError, match="TAIL-STATE"):
        tmm.compute_period_aggregates_tm_a(
            np.zeros((A + 1) * J), grid, None, None, np.eye(J),
            None, None, 0.3)


# ---------------------------------------------------------------------------
# tail_state_readout (the estimation consumer surface)
# ---------------------------------------------------------------------------

def test_tail_state_readout_enabled_and_disabled():
    A, J = 6, 3
    grid = np.linspace(0.0, 1.0, A)
    markov_w = np.ones(J) / J

    # no tail_state key => designed error
    with pytest.raises(ValueError, match="tail_state"):
        tmm.tail_state_readout({"dist_aGrid": grid, "markov_ergodic": markov_w},
                               np.zeros(A * J))

    # enabled: grid part + expanded tail with exact pooled mass and mean
    alpha, X = 2.0, float(grid[-1])
    tm_data = {"dist_aGrid": grid, "markov_ergodic": markov_w,
               "tail_state": {"enabled": True, "alpha": alpha, "X": X}}
    erg = np.zeros((A + 1) * J)
    rng = np.random.default_rng(3)
    erg[:] = rng.uniform(0.1, 1.0, erg.size)
    erg /= erg.sum()
    erg2 = erg.reshape(J, A + 1)
    w_T = float(erg2[:, A].sum())
    erg_grid, tail_a, tail_w = tmm.tail_state_readout(tm_data, erg)
    assert erg_grid.shape == (J, A)
    np.testing.assert_allclose(erg_grid, erg2[:, :A], atol=0)
    assert tail_a.shape == tail_w.shape == (13,)   # K=12 segments + terminal
    assert abs(tail_w.sum() - w_T) < 1e-14
    exact_tail_mean = alpha / (alpha - 1.0) * X
    assert abs(float(tail_a @ tail_w) / w_T - exact_tail_mean) < 1e-12
    # total mass of the expansion equals the original ergodic mass
    assert abs(erg_grid.sum() + tail_w.sum() - 1.0) < 1e-12

    # disabled: immaterial pile passes through; material pile refuses
    tm_dis = {"dist_aGrid": grid, "markov_ergodic": markov_w,
              "tail_state": {"enabled": False, "reason": "test-disable"}}
    erg_ok = np.zeros(A * J)
    erg_ok[0] = 1.0 - 1e-9
    erg_ok[A - 1] = 1e-9          # pile below the 1e-8 threshold
    g, ta, tw = tmm.tail_state_readout(tm_dis, erg_ok)
    assert g.shape == (J, A) and ta.size == 0 and tw.size == 0
    erg_bad = np.zeros(A * J)
    erg_bad[0] = 1.0 - 1e-7
    erg_bad[A - 1] = 1e-7         # material pile on a "no-power-tail" atom
    with pytest.raises(RuntimeError, match="m_top"):
        tmm.tail_state_readout(tm_dis, erg_bad)


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-q"]))
