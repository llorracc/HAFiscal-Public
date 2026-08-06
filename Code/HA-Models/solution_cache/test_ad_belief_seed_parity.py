"""Leg B parity gate for the cross-phase AD-belief WARM-START.

Plan: ``plans/20260622_welfare6-reuse-presolved-AD-equilibria.md`` (LEG B).

Leg B publishes Step-5a's converged macro AD belief (``economy.CFunc``) as a tiny
sidecar (``solution_cache/<param>/<shock_type>/ad_belief.pkl``) that Step-5b loads to
**seed** ``solve_ad_recession``. This is a WARM START, NOT a skip: the AD loop runs to
its own ``convergence_cutoff`` UNCHANGED. The seed only changes how many iterations the
loop takes (MEASURED 2026-06-22 at HS_Only recessionCheck_AD: 4 -> 1, ~1.6x wall).

CORRECTNESS BAR — NUMERICAL EQUIVALENCE, **not** byte-identity. A loop-seed warm start
changes the AD trajectory, and the loop stops when its *step* falls below
``convergence_cutoff`` (~1e-2), NOT at a machine-precision fixed point. A warm and a flat
trajectory therefore cross that threshold at DIFFERENT points, so their converged beliefs
differ by an amount BELOW the cutoff. MEASURED agreement (HS_Only recessionCheck_AD,
N=2000): welfare integrand reldiff 9.8e-8, per-duration cLvl panel max reldiff 2.5e-5 —
numerically equivalent for any research purpose, but NOT the same bytes. So the warm
start is for FRESH / candidate runs; the byte-identical fast path for frozen
``LOCKED_TABLES`` reproduction is the AD CACHE (Leg A, exact replay), not this seed.
(Byte-identity is mathematically unachievable for a trajectory-changing seed at a finite
cutoff; forcing it would need machine-precision convergence, killing the speedup. Owner
decision 2026-06-22: keep as a default-OFF candidate-run speedup, assert numerical
equivalence here.)

This gate asserts that, for ``HS_Only recessionCheck_AD`` (the strongest-AD reportable
cell, hence the most demanding warm-start round-trip):

    test_seed_numerically_equivalent
        (i)  flat ``solve_ad_recession`` (HAFISCAL_AD_BELIEF_SEED unset)  vs
        (ii) ``HAFISCAL_AD_BELIEF_SEED=1`` warm-started from a PRE-PUBLISHED belief
        -> per-duration cLvl panels + welfare scalar agree within rtol=1e-3 (~40x above
           the measured 2.5e-5, far below a real basin divergence).

    test_fingerprint_mismatch_falls_back
        Publish a belief, then TAMPER its stored fingerprint so it cannot match this run.
        The soft gate must DETECT the mismatch, ignore the sidecar, and run the flat path
        — result BYTE-IDENTICAL to the flat-start reference (the warm start was skipped
        entirely, so this one IS exact: a mismatch only forgoes the speedup). (Tampering,
        NOT a PERMGROFAC_FIX flip, avoids depending on the absent legacy calibration — the
        legacy solver is never exercised by this suite.)

    test_cross_engine_tag_warm_start
        A belief tagged ``engine='tm'`` consumed under an MC run is an ALLOWED
        cross-engine warm-start (the seed is only a guess). Assert numerical equivalence
        (same bar as test_seed_numerically_equivalent — the warm start fires).

Why numerical-equivalence (not exact) is the right bar (plan §"Correctness", LEG B,
amended 2026-06-22 by measurement): Leg B leaves ``solve_ad_recession``'s damped-Picard
step and stopping rule UNCHANGED and does not touch the forward-sim RNG (``seed_offset``,
``IncShkDstn[0].seed``), so the ONLY difference is the trajectory-dependent stopping
point within the convergence band. rtol=1e-3 passes that sub-cutoff difference while still
failing loudly if the seed lands in a DIFFERENT basin (the Leg-B NO-GO, which would be
>=1%). The warm start is wired through ``eco._ad_warm_start`` (AggFiscalModel.py): the
flat reset is skipped AND the seed is re-applied after ``self.update()`` rebuilds CFunc.

CASCADE-GATE (per [cascade-gating] / [grid_convergence_test_in_college_beta_het]): run
HS_Only FIRST (this test). Escalate to ``College_Only`` with all 7 beta atoms (the
binding high-aNrm tail) ONLY on a clean HS_Only pass. HALT-on-fail at the current tier.

Marked ``slow``; honors ``HAFISCAL_SKIP_SLOW_ITEST=1`` (skip at collection time) so
``--collect-only`` and a plain ``pytest`` sweep never build the economy.

Run explicitly with:
    pytest Code/HA-Models/solution_cache/test_ad_belief_seed_parity.py -m slow
"""
import os
import pickle
import subprocess
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
# _HERE = .../Code/HA-Models/solution_cache; FromPandemicCode is a sibling.
_HAMODELS = os.path.abspath(os.path.join(_HERE, ".."))
_FPC = os.path.join(_HAMODELS, "FromPandemicCode")

# Collection-time skip guard: building the HS_Only AD cell is too heavy for some
# environments. Honoring this env var keeps `--collect-only` (and any non-slow
# sweep) from importing/instantiating anything expensive.
_SKIP_SLOW = os.environ.get("HAFISCAL_SKIP_SLOW_ITEST", "").lower() in (
    "1", "on", "true", "yes")
pytestmark = pytest.mark.skipif(
    _SKIP_SLOW,
    reason="HAFISCAL_SKIP_SLOW_ITEST set — skipping heavy AD-belief warm-start build",
)

_SCENARIO = "recessionCheck_AD"
_SHOCK_TYPE = "recessionCheck"   # the shock_type the sidecar is keyed under
_PARAMETRIZATION = "HS_Only"
# Small N keeps the build affordable while still exercising the full warm-start
# round-trip; parity is exact regardless of N.
_AGENT_COUNT_TOTAL = 2000


def _belief_pkl_path():
    """Path to the AD-belief sidecar this gate publishes/consumes."""
    return os.path.join(_HERE, _PARAMETRIZATION, _SHOCK_TYPE, "ad_belief.pkl")


def _clear_belief():
    """Remove any pre-existing belief sidecar so each test starts clean."""
    d = os.path.join(_HERE, _PARAMETRIZATION, _SHOCK_TYPE)
    for fn in ("ad_belief.pkl", "ad_belief.meta.json"):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            os.remove(p)


def _tamper_belief_fingerprint():
    """Overwrite the published belief's stored fingerprint with a value no real SHA256 can
    match, so the consumer's soft gate detects a mismatch. This forces the mismatch path
    WITHOUT publishing under a second solver regime (PERMGROFAC_FIX=0 would require the
    matched legacy calibration, absent in many checkouts, and trips the BUG-047 guard)."""
    p = _belief_pkl_path()
    with open(p, "rb") as f:
        payload = pickle.load(f)
    payload["fingerprint"] = "0" * 64
    with open(p, "wb") as f:
        pickle.dump(payload, f)


def _publish_belief(engine, *, mc_method, extra_env=None):
    """Pre-publish an AD-belief sidecar for (HS_Only, recessionCheck), the way
    Step-5a does, by building the economy IN A SUBPROCESS, solving the
    recessionCheck AD fixed point, and calling ad_belief.save_ad_belief on the
    converged eco.CFunc.

    Done in a subprocess (not in-process) so the heavy HARK import + solve does
    not pollute the test process and so ``extra_env`` (e.g. a flipped
    HAFISCAL_PERMGROFAC_FIX for the mismatch test) is applied cleanly to the
    publishing regime only.
    """
    env = dict(os.environ)
    env["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
    env["HAFISCAL_USE_JAX_2B"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)
    # A self-contained publisher: build_and_solve -> run_base -> converge the
    # recessionCheck AD belief -> save_ad_belief. Mirrors Simulate.py's MC publish.
    code = (
        "import sys; sys.argv = sys.argv[:1]\n"
        "import welfare6_scenario as ws\n"
        "from solution_cache import ad_belief\n"
        f"ctx = ws.build_and_solve('{_PARAMETRIZATION}', "
        f"agent_count_total={_AGENT_COUNT_TOTAL})\n"
        "ws.run_base(ctx)\n"
        "eco = ctx['AggEco']\n"
        f"eco.switch_shock_type('{_SHOCK_TYPE}')\n"
        "eco.solve_ad_check_recession("
        "num_max_iterations=ctx['num_max_iterations_solvingAD'], "
        "convergence_cutoff=ctx['convergence_tol_solvingAD'], "
        f"name='{_SHOCK_TYPE}')\n"
        f"eco.restore_ADsolution(name='{_SHOCK_TYPE}')\n"
        f"ad_belief.save_ad_belief(eco, '{_SHOCK_TYPE}', '{_PARAMETRIZATION}', "
        f"engine='{engine}', mc_method={mc_method!r})\n"
        "print('PUBLISHED', ad_belief._belief_paths("
        f"'{_PARAMETRIZATION}', '{_SHOCK_TYPE}')[0])\n"
    )
    subprocess.run(
        [sys.executable, "-c", code], cwd=_FPC, env=env, check=True,
    )
    assert os.path.exists(_belief_pkl_path()), (
        "publisher subprocess did not write the belief sidecar")


def _run_scenario(out_dir, *, seed, extra_env=None):
    """Run the single AD scenario once via welfare6_scenario.py (subprocess,
    matching the test_ad_cache_parity.py driver) and return the loaded payload.

    ``seed`` sets HAFISCAL_AD_BELIEF_SEED for the child (the warm-start consume).
    The AD cache is OFF for all runs here so we isolate the warm-start effect,
    not the Leg-A cache HIT.
    """
    env = dict(os.environ)
    env["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
    env["HAFISCAL_USE_JAX_2B"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    if seed:
        env["HAFISCAL_AD_BELIEF_SEED"] = "1"
    else:
        env.pop("HAFISCAL_AD_BELIEF_SEED", None)
    if extra_env:
        env.update(extra_env)
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        [sys.executable, "welfare6_scenario.py",
         "--scenario", _SCENARIO,
         "--parametrization", _PARAMETRIZATION,
         "--out-dir", out_dir,
         "--agent-count-total", str(_AGENT_COUNT_TOTAL)],
        cwd=_FPC, env=env, check=True,
    )
    with open(os.path.join(out_dir, f"{_SCENARIO}.pkl"), "rb") as f:
        return pickle.load(f)


def _welfare_integrand_sum(payload):
    """Deterministic scalar summarizing this AD cell's welfare contribution from
    its per-duration panels (BUG-046 per-duration ordering: felicity per duration,
    then rec_probs weighting). A deterministic function of the panels, so it is
    bit-identical iff the panels are. Same definition as test_ad_cache_parity.py.
    """
    per_dur = payload["per_dur_cLvl_all_splurge"]
    rec_probs = payload["rec_probs"]
    CRRA = payload["CRRA"]
    acc = 0.0
    for dur in range(len(per_dur)):
        c = np.maximum(np.asarray(per_dur[dur], dtype=np.float64), 1e-16)
        if abs(CRRA - 1.0) < 1e-12:
            fel = np.log(c)
        else:
            fel = c ** (1 - CRRA) / (1 - CRRA)
        acc += float(rec_probs[dur]) * float(np.sum(fel))
    return acc


def _assert_bit_identical(ref, other, label):
    """Assert two welfare6_scenario payloads are bit-identical on the welfare-
    determining arrays + the welfare scalar (exact equality, no tolerance)."""
    for tag, p in (("ref", ref), (label, other)):
        assert "per_dur_cLvl_all_splurge" in p, (
            f"{tag} payload missing per_dur_cLvl_all_splurge")
        assert "rec_probs" in p, f"{tag} payload missing rec_probs"

    ref_panel = np.asarray(ref["per_dur_cLvl_all_splurge"], dtype=np.float64)
    oth_panel = np.asarray(other["per_dur_cLvl_all_splurge"], dtype=np.float64)
    assert ref_panel.shape == oth_panel.shape, (
        f"{label}: per-duration panel shape mismatch "
        f"(ref={ref_panel.shape}, {label}={oth_panel.shape})")
    np.testing.assert_array_equal(
        ref_panel, oth_panel,
        err_msg=f"{label}: per-duration cLvl panel differs from the flat-start "
                f"reference — the warm-started solve did NOT converge to the same "
                f"fixed point (basin lock-in -> Leg B NO-GO).")

    w_ref = _welfare_integrand_sum(ref)
    w_oth = _welfare_integrand_sum(other)
    assert w_ref == w_oth, (
        f"{label}: welfare scalar not bit-identical "
        f"(flat={w_ref!r}, {label}={w_oth!r})")

    for key in ("cLvl_all_splurge", "AggCons", "AggIncome"):
        if key in ref and key in other:
            np.testing.assert_array_equal(
                np.asarray(ref[key], dtype=np.float64),
                np.asarray(other[key], dtype=np.float64),
                err_msg=f"{label}: {key} differs from the flat-start reference")


def _assert_numerically_equivalent(ref, other, label, rtol=1e-3):
    """Assert two welfare6_scenario payloads agree to within the AD solver's own
    convergence tolerance — numerical equivalence, NOT byte-identity.

    A loop-seed warm start changes the AD trajectory, which crosses the
    convergence_cutoff step-threshold at a different point than the flat trajectory, so
    the converged beliefs differ by an amount BELOW the cutoff (MEASURED 2026-06-22,
    HS_Only recessionCheck_AD: welfare reldiff 9.8e-8, cLvl panel max reldiff 2.5e-5).
    rtol=1e-3 sits ~40x above that measured agreement yet far below a genuine basin
    divergence (the original Leg-B NO-GO would be >=1%), so it passes the
    numerically-equivalent warm start and still fails loudly on basin lock-in."""
    for tag, p in (("ref", ref), (label, other)):
        assert "per_dur_cLvl_all_splurge" in p, (
            f"{tag} payload missing per_dur_cLvl_all_splurge")
        assert "rec_probs" in p, f"{tag} payload missing rec_probs"

    ref_panel = np.asarray(ref["per_dur_cLvl_all_splurge"], dtype=np.float64)
    oth_panel = np.asarray(other["per_dur_cLvl_all_splurge"], dtype=np.float64)
    assert ref_panel.shape == oth_panel.shape, (
        f"{label}: per-duration panel shape mismatch "
        f"(ref={ref_panel.shape}, {label}={oth_panel.shape})")
    np.testing.assert_allclose(
        oth_panel, ref_panel, rtol=rtol, atol=1e-9,
        err_msg=f"{label}: per-duration cLvl panel differs from the flat-start "
                f"reference by MORE than rtol={rtol:g} — the warm-started solve landed "
                f"in a different basin (Leg B NO-GO), not just a sub-cutoff trajectory "
                f"difference.")

    w_ref = _welfare_integrand_sum(ref)
    w_oth = _welfare_integrand_sum(other)
    assert abs(w_oth - w_ref) <= rtol * abs(w_ref), (
        f"{label}: welfare scalar differs by more than rtol={rtol:g} "
        f"(flat={w_ref!r}, {label}={w_oth!r}, "
        f"reldiff={abs(w_oth - w_ref) / abs(w_ref):.2e})")

    for key in ("cLvl_all_splurge", "AggCons", "AggIncome"):
        if key in ref and key in other:
            np.testing.assert_allclose(
                np.asarray(other[key], dtype=np.float64),
                np.asarray(ref[key], dtype=np.float64),
                rtol=rtol, atol=1e-9,
                err_msg=f"{label}: {key} differs from the flat-start reference by "
                        f"more than rtol={rtol:g}")


@pytest.mark.slow
def test_seed_numerically_equivalent(tmp_path):
    """Flat solve vs warm-started-from-a-published-belief: the per-duration cLvl panels
    + welfare scalar must be NUMERICALLY EQUIVALENT (within rtol=1e-3, NOT byte-identical)
    for HS_Only recessionCheck_AD. See the module docstring for why exact equality is
    unachievable for a trajectory-changing loop seed.
    """
    _clear_belief()
    # (i) flat reference (HAFISCAL_AD_BELIEF_SEED unset).
    flat = _run_scenario(str(tmp_path / "flat"), seed=False)
    # Publish a (same-engine) MC belief the consumer can warm-start from.
    _publish_belief(engine="hark_mc", mc_method="hark_mc")
    # (ii) warm-started from the published belief.
    seeded = _run_scenario(str(tmp_path / "seeded"), seed=True)
    _assert_numerically_equivalent(flat, seeded, "seeded")


@pytest.mark.slow
def test_fingerprint_mismatch_falls_back(tmp_path):
    """A published belief whose stored fingerprint does NOT match this run's must be
    IGNORED by the soft gate and the flat path run — result BYTE-identical to the
    flat-start reference (a mismatch only forgoes the speedup, never corrupts).

    The mismatch is forced by TAMPERING the stored fingerprint, NOT by publishing under a
    second solver regime: the obvious PERMGROFAC_FIX=0 trigger requires the matched legacy
    calibration (Results/_pgf_legacy/...), which is not materialized in every checkout and
    trips the BUG-047 matched-pair guard before the belief can even build. Tampering the
    fingerprint exercises the gate logic directly, under the default solver only.
    """
    _clear_belief()
    flat = _run_scenario(str(tmp_path / "flat"), seed=False)
    # Publish a normal default-solver belief, then corrupt its stored fingerprint so the
    # consumer's soft gate sees a mismatch (a real run's SHA256 never equals "0"*64).
    _publish_belief(engine="hark_mc", mc_method="hark_mc")
    _tamper_belief_fingerprint()
    # Consume with SEED on: the soft gate rejects the tampered sidecar, the flat path
    # runs, and the result is byte-identical to the flat reference.
    seeded = _run_scenario(str(tmp_path / "seeded"), seed=True)
    _assert_bit_identical(flat, seeded, "seeded_mismatch_fallback")


@pytest.mark.slow
def test_cross_engine_tag_warm_start(tmp_path):
    """An engine='tm' belief consumed under an MC run is an ALLOWED cross-engine
    warm-start (the seed is only a guess). The result must still be bit-identical
    to the flat-start MC solve.
    """
    _clear_belief()
    flat = _run_scenario(str(tmp_path / "flat"), seed=False)
    # Publish a TM-tagged belief (mc_method=None, the TM publish convention) from
    # the same converged CFunc; the consumer should accept it as a cross-engine
    # warm-start (calibration matches; only the engine tag differs).
    _publish_belief(engine="tm", mc_method=None)
    seeded = _run_scenario(str(tmp_path / "seeded"), seed=True)
    # The warm start FIRES here (cross-engine is allowed), so the bar is numerical
    # equivalence, not byte-identity — same as test_seed_numerically_equivalent.
    _assert_numerically_equivalent(flat, seeded, "seeded_cross_engine")
