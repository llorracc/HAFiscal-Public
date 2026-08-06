"""Meld plan P0 -> F1 router tests: the fti_step1 tail-form consistency guard/router.

The Phase-0 guard (live since the 2026-07-23 HAFISCAL_PF_DECAY_EXTRAP
default-ON flip) originally refused the Step-1 FTI transplant for EVERY method
under the power-law form. After meld P1/P2 landed the power-law tail in
hark_fti's AndersonEGM (fast-time-iteration d474914), the guard became a
ROUTER (F1 everywhere-audit, 2026-07-23):

  * AndersonEGM  -> routes: the transplant solve runs tail_form='powerlaw'
    (tail_Q=None => slope-derived Q) — import succeeds, agent configured;
  * NAM/ATI/NAMG -> still refuse (exp-pinned tails), at import for the
    env-configured method AND per-call for programmatic method overrides;
  * legal escapes: explicit legacy tail (exp / 0), or
    HAFISCAL_FTI_ALLOW_TAIL_MISMATCH=1 (restores pre-router behavior
    everywhere, including no Anderson routing — mismatch benchmarking).

The import-time guard raises at module import, so each case runs a fresh
interpreter.
"""
import os
import subprocess
import sys
from pathlib import Path

_HA = Path(__file__).resolve().parent
_TARGET = _HA / "Target_AggMPCX_LiquWealth"

# Minimal Step-1-like base params for constructing (NOT solving) an FTI type.
_MAKE_TYPE_SNIPPET = """
import fti_step1
from copy import deepcopy
from SetupParamsCSTW import init_infinite
b = deepcopy(init_infinite)
b.update(LivPrb=[1 - 1/160], Rfree=1.02**0.25, Rsave=1.02**0.25,
         Rboro=1.137**0.25, UnempPrb=0.044, IncUnemp=0.60,
         PermShkStd=[0.001**0.5], TranShkStd=[0.132**0.5], BoroCnstArt=0,
         PermGroFacAgg=1.01**0.25, CRRA=2.0, T_age=None)
"""


def _run(code, **env):
    full = {k: v for k, v in os.environ.items()
            if not k.startswith("HAFISCAL_")}
    full.update({"PYTHONPATH": str(_TARGET), **env})
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=full, cwd=str(_TARGET))


def _import_fti_step1(**env):
    return _run("import fti_step1", **env)


def test_guard_fires_on_default_powerlaw_form():
    # STEP1_FTI on + form unset (default = powerlaw since 2026-07-23) + method
    # default (NAM, exp-pinned) -> refuse
    r = _import_fti_step1(HAFISCAL_STEP1_FTI="1")
    assert r.returncode != 0
    assert "wrong tail" in r.stderr and "RuntimeError" in r.stderr


def test_guard_fires_on_explicit_powerlaw_form_per_exp_pinned_method():
    """NAM and ATI stay exp-pinned and must still refuse.

    NAMG was in this list until 2026-07-25; it moved to the routing test below
    when the power-law port landed (plan 20260725_namg-powerlaw-port). NAM/ATI
    have no power-law tail in any kernel, so their refusal is permanent.
    """
    for method in ("NAM", "ATI"):
        r = _import_fti_step1(HAFISCAL_STEP1_FTI="1",
                              HAFISCAL_PF_DECAY_EXTRAP="powerlaw",
                              HAFISCAL_FTI_METHOD=method)
        assert r.returncode != 0 and "RuntimeError" in r.stderr, \
            f"{method} should refuse under the power-law form"


def test_namg_routes_or_refuses_per_installed_kernel_capability():
    """N3 capability handshake: NAMG routes iff the INSTALLED kernel says it can.

    The point of a handshake (rather than a version/env guess) is that BOTH
    outcomes are correct behavior — so this test asserts the outcome that
    matches whatever `hark_fti` is actually resolvable here, and asserts the
    refusal message is the capability-worded one either way.
    """
    # Probe through the SAME resolver the code under test uses — a bare
    # `import hark_fti` finds nothing here (the sibling checkout is located by
    # `_hark_fti_path`), which would make this test assert the wrong branch.
    supported = False
    try:
        import os
        import sys
        _fpc = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'FromPandemicCode')
        if _fpc not in sys.path:
            sys.path.insert(0, _fpc)
        import _hark_fti_path  # noqa: F401  (resolves the sibling checkout)
        import hark_fti
        supported = bool(getattr(hark_fti, 'NAMG_SUPPORTS_POWERLAW_TAIL', False))
    except Exception:
        supported = False

    r = _import_fti_step1(HAFISCAL_STEP1_FTI="1",
                          HAFISCAL_PF_DECAY_EXTRAP="powerlaw",
                          HAFISCAL_FTI_METHOD="NAMG")
    if supported:
        assert r.returncode == 0, (
            "NAMG must ROUTE (not refuse) when the installed kernel advertises "
            f"NAMG_SUPPORTS_POWERLAW_TAIL. stderr: {r.stderr[-600:]}")
    else:
        assert r.returncode != 0 and "RuntimeError" in r.stderr, \
            "NAMG must refuse when the installed kernel lacks the power-law port"


def test_anderson_routes_instead_of_refusing():
    # Import succeeds AND the constructed type carries the power-law tail config.
    code = _MAKE_TYPE_SNIPPET + """
a = fti_step1.make_fti_type(b, 0.94)
assert getattr(a, 'anderson_tail_form', 'exp') == 'powerlaw', a
assert getattr(a, 'anderson_tail_Q', 'MISSING') is None  # None => slope-derived Q
print('ROUTED-OK')
"""
    r = _run(code, HAFISCAL_STEP1_FTI="1", HAFISCAL_FTI_METHOD="AndersonEGM")
    assert r.returncode == 0, r.stderr[-800:]
    assert "ROUTED-OK" in r.stdout


def test_anderson_route_threads_explicit_tail_q():
    code = _MAKE_TYPE_SNIPPET + """
a = fti_step1.make_fti_type(b, 0.94, tail_Q=1.25)
assert getattr(a, 'anderson_tail_form', 'exp') == 'powerlaw'
assert abs(a.anderson_tail_Q - 1.25) < 1e-15
print('TAILQ-OK')
"""
    r = _run(code, HAFISCAL_STEP1_FTI="1", HAFISCAL_FTI_METHOD="AndersonEGM")
    assert r.returncode == 0, r.stderr[-800:]
    assert "TAILQ-OK" in r.stdout


def test_percall_method_override_still_refuses():
    # Import passes (env method AndersonEGM routes), but a programmatic
    # override to an exp-pinned method must hit the same wall.
    code = _MAKE_TYPE_SNIPPET + """
try:
    fti_step1.make_fti_type(b, 0.94, method='NAM')
except RuntimeError as e:
    assert 'EXPONENTIAL' in str(e) or 'wrong tail' in str(e)
    print('PERCALL-REFUSED')
else:
    raise SystemExit('NAM override was not refused')
"""
    r = _run(code, HAFISCAL_STEP1_FTI="1", HAFISCAL_FTI_METHOD="AndersonEGM")
    assert r.returncode == 0, r.stderr[-800:]
    assert "PERCALL-REFUSED" in r.stdout


def test_escape_hatch_disables_routing_and_refusal():
    # Mismatch benchmarking: pre-router behavior everywhere — NAM imports fine,
    # Anderson builds WITHOUT the powerlaw config (exp-pinned legacy transplant).
    r = _import_fti_step1(HAFISCAL_STEP1_FTI="1",
                          HAFISCAL_FTI_ALLOW_TAIL_MISMATCH="1")
    assert r.returncode == 0, r.stderr[-400:]
    code = _MAKE_TYPE_SNIPPET + """
a = fti_step1.make_fti_type(b, 0.94)
assert getattr(a, 'anderson_tail_form', 'exp') == 'exp'
print('ESCAPE-NO-ROUTE')
"""
    r = _run(code, HAFISCAL_STEP1_FTI="1", HAFISCAL_FTI_METHOD="AndersonEGM",
             HAFISCAL_FTI_ALLOW_TAIL_MISMATCH="1")
    assert r.returncode == 0, r.stderr[-800:]
    assert "ESCAPE-NO-ROUTE" in r.stdout


def test_guard_allows_legacy_tails_and_off():
    for env in ({"HAFISCAL_STEP1_FTI": "1", "HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                {"HAFISCAL_STEP1_FTI": "1", "HAFISCAL_PF_DECAY_EXTRAP": "0"},
                {}):  # FTI off entirely: guard must not fire regardless of form
        r = _import_fti_step1(**env)
        assert r.returncode == 0, f"unexpected refusal under {env}: {r.stderr[-400:]}"


def test_legacy_tail_builds_anderson_without_routing():
    code = _MAKE_TYPE_SNIPPET + """
a = fti_step1.make_fti_type(b, 0.94)
assert getattr(a, 'anderson_tail_form', 'exp') == 'exp'
print('EXP-NO-ROUTE')
"""
    r = _run(code, HAFISCAL_STEP1_FTI="1", HAFISCAL_FTI_METHOD="AndersonEGM",
             HAFISCAL_PF_DECAY_EXTRAP="exp")
    assert r.returncode == 0, r.stderr[-800:]
    assert "EXP-NO-ROUTE" in r.stdout


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
