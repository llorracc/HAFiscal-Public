"""HAFISCAL_T_AGE flag: parsing, age-chain lengths, and Parameters/EstimParameters sync.

Owner decision 2026-07-26 (see docs/ENV_FLAGS.md HAFISCAL_T_AGE): the QE-era
maximum-age cap (T_age=200) is undocumented in the paper and executes 28.5% of
each cohort at the wall; 'none' removes it. Default (unset) must be byte-identical
status quo. Fast (<1s), no model solves.
"""
import importlib
import math
import os
import subprocess
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")
for p in (HAM, FPC):
    if p not in sys.path:
        sys.path.insert(0, p)

L_RAW = 1.0 - 1.0 / 160  # the production quarterly survival probability


def _fresh_tm():
    import tm_methods
    return importlib.reload(tm_methods) if 'tm_methods' in sys.modules else tm_methods


def test_age_chain_length_capped_passthrough():
    from tm_methods import effective_age_chain_length
    assert effective_age_chain_length(L_RAW, 200) == 200
    assert effective_age_chain_length(L_RAW, 100) == 100
    assert effective_age_chain_length(L_RAW, 400) == 400


def test_age_chain_length_uncapped_tolerance():
    from tm_methods import effective_age_chain_length
    T = effective_age_chain_length(L_RAW, None, tol=1e-9)
    expect = math.ceil(math.log(1e-9) / math.log(L_RAW))
    assert T == max(400, expect)
    # the truncated survivor mass really is below tol
    assert L_RAW ** T <= 1e-9 * (1 + 1e-12)
    # and the legacy 400 bound would have discarded material mass (~8%)
    assert L_RAW ** 400 > 0.05


def test_effective_livprb_none_is_raw():
    from tm_methods import _effective_LivPrb
    arr = np.array([L_RAW, L_RAW])
    out = _effective_LivPrb(arr, None)
    assert np.array_equal(out, arr)


def _estim_T_age(env_val):
    """EstimParameters resolves T_age at import in a subprocess (clean env)."""
    env = dict(os.environ)
    env.pop("HAFISCAL_T_AGE", None)
    if env_val is not None:
        env["HAFISCAL_T_AGE"] = env_val
    env["HAFISCAL_EDTYPES"] = ""
    env["HAFISCAL_QUIET_BETADISTR"] = "1"
    code = (
        "import sys; sys.argv=[sys.argv[0]]; sys.path.insert(0, %r);"
        "import EstimParameters as ep; print(repr(ep.init_dropout['T_age']))"
        % FPC
    )
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=FPC,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout.strip().splitlines()[-1]


def test_estimparameters_default_uncapped_epoch():
    # EPOCH 2026-07-27: the default world is UNCAPPED (belief-consistent).
    assert _estim_T_age(None) == "None"


def test_estimparameters_explicit_values():
    assert _estim_T_age("none") == "None"
    assert _estim_T_age("200") == "200"   # the paper/as-corrected cap
    assert _estim_T_age("320") == "320"


def test_estimparameters_rejects_garbage():
    env = dict(os.environ)
    env["HAFISCAL_T_AGE"] = "-5"
    env["HAFISCAL_EDTYPES"] = ""
    code = ("import sys; sys.argv=[sys.argv[0]]; sys.path.insert(0, %r);"
            "import EstimParameters" % FPC)
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=FPC,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode != 0 and "HAFISCAL_T_AGE" in out.stderr
