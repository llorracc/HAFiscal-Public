"""Unit battery for the SST solve-grid policy (grid_sizing.resolve_solve_grid
+ the powerlaw predicates) — owner ruling 2026-07-24 ("I want a SST for this
kind of thing"). Covers the FULL precedence matrix with injected environs (no
os.environ mutation); the production-value byte-parity is additionally gated by
the 2026-07-24 golden-probe matrix (12 regimes x 2 sites, pre- vs post-refactor
identical; see conclusions_private/2026-07-24_f7_step1_khbar_rerun.md).
"""
import math

import pytest

import grid_sizing as gs

R, G = 1.01, 1.0035  # synthetic production-like quarterly primitives (R > Γ)
LEG = dict(legacy_aMax=40, legacy_count=48, aXtraMin=0.001)


def _khbar(K=3.0):
    return K * G / (R - G)


# ---------------------------------------------------------------- predicates
def test_powerlaw_form_active_matrix():
    T, F = True, False
    for raw, expect in (("1", T), ("powerlaw", T), ("anything", T), (" EXP", F),
                        ("exp", F), ("Exp", F), ("0", F), ("", F),
                        ("false", F), ("False", F)):
        assert gs.powerlaw_form_active({"HAFISCAL_PF_DECAY_EXTRAP": raw}) is expect, raw
    assert gs.powerlaw_form_active({}) is True  # unset default = powerlaw ON


def test_powerlaw_measured_active_matrix():
    assert gs.powerlaw_measured_active({}) is True                      # both defaults
    assert gs.powerlaw_measured_active({"HAFISCAL_PF_DECAY_Q": "local2"}) is True
    assert gs.powerlaw_measured_active({"HAFISCAL_PF_DECAY_Q": "MEASURED "}) is True
    assert gs.powerlaw_measured_active({"HAFISCAL_PF_DECAY_Q": "slope"}) is False
    assert gs.powerlaw_measured_active({"HAFISCAL_PF_DECAY_EXTRAP": "exp"}) is False
    assert gs.powerlaw_measured_active({"HAFISCAL_PF_DECAY_EXTRAP": "0"}) is False


# ---------------------------------------------------------------- precedence
def test_legacy_passthrough_uncoerced():
    for env in ({"HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                {"HAFISCAL_PF_DECAY_EXTRAP": "0"},
                {"HAFISCAL_PF_DECAY_Q": "slope"}):
        aMax, aCount, why = gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ=env, **LEG)
        assert why is None
        assert aMax == 40 and type(aMax) is int   # UNCOERCED (cache-key byte parity)
        assert aCount == 48 and type(aCount) is int


def test_default_fires_khbar_with_basis_192():
    aMax, aCount, why = gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ={}, **LEG)
    assert math.isclose(aMax, _khbar(3.0))
    assert aCount == gs.solve_grid_count(aMax, aXtraMin=0.001, legacy_aMax=40,
                                         legacy_count=192)
    assert why == "HAFISCAL_PF_DECAY_Q=local2 solve-top rule aXtraMax=K·h̄ (K=3)"


def test_amax_mult_env():
    aMax, _, why = gs.resolve_solve_grid(
        Rfree=R, PermGroFac=G, environ={"HAFISCAL_PF_DECAY_AMAX_MULT": "5"}, **LEG)
    assert math.isclose(aMax, _khbar(5.0))
    assert "(K=5)" in why


def test_solve_amax_wins_over_everything_even_exp():
    for env in ({"HAFISCAL_SOLVE_AMAX": "300"},
                {"HAFISCAL_SOLVE_AMAX": "300", "HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                {"HAFISCAL_SOLVE_AMAX": "300", "HAFISCAL_ENDOGENOUS_GRID": "1"}):
        aMax, aCount, why = gs.resolve_solve_grid(
            Rfree=R, PermGroFac=G, environ=env, allow_endogenous=True,
            endogenous_kwargs=dict(beta=0.98, CRRA=2.0, LivPrb=0.994), **LEG)
        assert aMax == 300.0
        assert why == "HAFISCAL_SOLVE_AMAX=300 (all groups)"
        assert aCount == gs.solve_grid_count(300.0, aXtraMin=0.001, legacy_aMax=40,
                                             legacy_count=192)
    # empty-string override is treated as unset (the sites' `not in (None,'')`)
    _, _, why = gs.resolve_solve_grid(
        Rfree=R, PermGroFac=G,
        environ={"HAFISCAL_SOLVE_AMAX": "", "HAFISCAL_PF_DECAY_EXTRAP": "exp"}, **LEG)
    assert why is None


def test_count_basis_guards():
    # explicit env AXTRA_COUNT blocks the 192 promotion (caller passes it in legacy_count)
    _, aCount, _ = gs.resolve_solve_grid(
        Rfree=R, PermGroFac=G, environ={"HAFISCAL_AXTRA_COUNT": "96"},
        legacy_aMax=40, legacy_count=96, aXtraMin=0.001)
    assert aCount == gs.solve_grid_count(_khbar(), aXtraMin=0.001, legacy_aMax=40,
                                         legacy_count=96)
    # code-level override (FAST_GRIDS-style 24 != anchor 48) blocks it too
    _, aCount, _ = gs.resolve_solve_grid(
        Rfree=R, PermGroFac=G, environ={},
        legacy_aMax=40, legacy_count=24, aXtraMin=0.001)
    assert aCount == gs.solve_grid_count(_khbar(), aXtraMin=0.001, legacy_aMax=40,
                                         legacy_count=24)
    # Step-1 anchor: legacy 20/20 promotes to the 192 basis when anchor=20
    _, aCount, _ = gs.resolve_solve_grid(
        Rfree=1.02 ** 0.25, PermGroFac=1.0, environ={},
        legacy_aMax=20, legacy_count=20, aXtraMin=1e-5, count_basis_anchor=20)
    top1 = 3.0 * 1.0 / (1.02 ** 0.25 - 1.0)
    assert aCount == gs.solve_grid_count(top1, aXtraMin=1e-5, legacy_aMax=20,
                                         legacy_count=192)
    # ... but NOT when anchor stays 48 (a non-anchor legacy_count of 20)
    _, aCount48, _ = gs.resolve_solve_grid(
        Rfree=1.02 ** 0.25, PermGroFac=1.0, environ={},
        legacy_aMax=20, legacy_count=20, aXtraMin=1e-5, count_basis_anchor=48)
    assert aCount48 == gs.solve_grid_count(top1, aXtraMin=1e-5, legacy_aMax=20,
                                           legacy_count=20)


def test_endogenous_branch_semantics():
    env = {"HAFISCAL_ENDOGENOUS_GRID": "1", "HAFISCAL_PF_DECAY_EXTRAP": "exp"}
    kw = dict(beta=0.98, CRRA=2.0, LivPrb=0.994)
    # fires only when allowed (EstimParameters semantics)...
    aMax, _, why = gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ=env,
                                         allow_endogenous=True,
                                         endogenous_kwargs=kw, **LEG)
    expect = gs.solve_grid_aMax(R, 0.98, 2.0, 0.994, PermGroFac=G,
                                C1=gs.SOLVE_C1, bar=gs.SOLVE_BAR, tm_cap=1300.0)
    assert math.isclose(aMax, expect)
    assert why == f"HAFISCAL_ENDOGENOUS_GRID=1 (C1={gs.SOLVE_C1:g} bar={gs.SOLVE_BAR:g} tm_cap=1300)"
    # ... and is INERT for sites that never allowed it (Parameters semantics):
    _, _, why = gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ=env,
                                      allow_endogenous=False, **LEG)
    assert why is None
    # under the measured default, K·h̄ outranks nothing here — endogenous wins
    # (it sits ABOVE K·h̄ in the precedence, mirroring EstimParameters' if/elif)
    aMax2, _, why2 = gs.resolve_solve_grid(
        Rfree=R, PermGroFac=G, environ={"HAFISCAL_ENDOGENOUS_GRID": "1"},
        allow_endogenous=True, endogenous_kwargs=kw, **LEG)
    assert math.isclose(aMax2, expect) and "ENDOGENOUS" in why2
    # missing kwargs when the branch fires -> loud
    with pytest.raises(ValueError, match="endogenous_kwargs"):
        gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ=env,
                              allow_endogenous=True, **LEG)


def test_endogenous_kwargs_lazy_callable():
    def boom():
        raise AssertionError("must not be evaluated when the branch does not fire")
    _, _, why = gs.resolve_solve_grid(Rfree=R, PermGroFac=G, environ={},
                                      allow_endogenous=True,
                                      endogenous_kwargs=boom, **LEG)
    assert why is not None and "K·h̄" in why  # K·h̄ fired, callable untouched
    # and IS evaluated when it fires
    called = {}
    def kw():
        called["yes"] = True
        return dict(beta=0.98, CRRA=2.0, LivPrb=0.994)
    gs.resolve_solve_grid(Rfree=R, PermGroFac=G,
                          environ={"HAFISCAL_ENDOGENOUS_GRID": "1"},
                          allow_endogenous=True, endogenous_kwargs=kw, **LEG)
    assert called.get("yes") is True


def test_deep_top_warning_once_per_call(capsys):
    # near-R=Γ blowup: h̄ = Γ/(R−Γ) huge
    gs.resolve_solve_grid(Rfree=1.0002, PermGroFac=1.0, environ={},
                          legacy_aMax=40, legacy_count=48, aXtraMin=0.001,
                          tag="[grid_sizing:test]")
    out = capsys.readouterr().out
    assert out.count("WARNING") == 1 and "[grid_sizing:test]" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
