"""Single source of truth for the recession's ONSET UNEMPLOYMENT SPIKE.

WHAT THE SPIKE IS.  The recession in this model is *unanticipated*: the baseline chain has a
single macro state, so the ergodic distribution the experiment starts from carries the NORMAL
unemployment rate.  A recession, however, is defined partly by a higher unemployment rate, and a
Markov chain reaches its new rate only gradually.  The published code therefore does what the
Krusell-Smith literature does: at the instant the recession begins it lays off, by fiat, exactly
enough employed households to take the unemployment rate from ``Urate_normal`` to
``Urate_recession`` in one step.  Exit is left to the chain, so unemployment falls back gradually
when the recession ends.  Entry is instantaneous; exit is gradual.  None of this is described in
the paper.

    spike fraction  f = (Ur - Un) / (1 - Un)      -- the share of the EMPLOYED who are laid off

WHERE IT LIVES.  Two engines implement it and their timing must stay aligned:

* Monte Carlo (``AggFiscalModel.hit_with_recession_shock``): the spiked households have their
  micro state written from 0 (employed) to 1 (first benefit quarter) before the simulation loop.
* Transition matrix (``tm_methods.propagate_experiment_tm``/``_tm_a``): the same thing expressed
  as a blend of the employed row of the period-0 transition, since a TM has no individuals to
  relabel.  Consumption happens under the EMPLOYED policy first -- spiking before the
  consumption half-step overstated the new unemployed's saving by ~85 % (found 2026-04-10).

THE TIMING QUESTION (BUG-122 Step 0).  The spike writes households into the first benefit state
BEFORE any period is recorded, and the period-0 transition then advances them out of it.  So at
the first recorded quarter they are LABELLED as having drawn a benefit quarter they never
received, and they collect one recorded quarter of ordinary benefits where a household that
reaches unemployment through the chain collects two.

That is not just an arithmetic quirk.  Under the ``calendar`` encoding a household's micro state
IS its position in the benefit spell, so "quarters already drawn" is read straight off the label
-- and that label is what BUG-122's four-quarter cap must be applied to.  While this cohort's
label lies, the cap would cut it to three and break a row that is currently correct.

The fix is an ordering, not new state: hold the spiked households in their FIRST benefit state
for the first recorded period, exactly as newborns are already exempted from that transition.
They then look like what they economically are -- households that become unemployed AT the start
of the recession, indistinguishable from an ordinary period-0 entrant.

AND THE SPIKE MUST BE RESIZED WHEN THEY ARE HELD, or the fix breaks the calibration.  Under the
published ordering a share T[1,0] of the newly laid off find work again within the same quarter,
so the spike has to over-lay-off to land on the target rate; measured on the paper's calibration
(2026-09-06), holding them without resizing puts the first recession quarter's unemployment
12.5 % ABOVE the doubled-unemployment target in every education group (high school 8.8 % ->
9.9 %).  Since the laid-off no longer get that immediate job-finding draw, fewer are needed:

    f_exempt = f * (T[0,0] - T[1,0]) / T[0,0]

Equate the net unemployment each ordering adds -- f*(T[0,0] - T[1,0]) when the spiked transition,
f_exempt*T[0,0] when they are held -- and this is what falls out.  It is exact and needs nothing
but the chain.  With it the two orderings produce the SAME unemployment rate at period 0, and
(because job-finding does not depend on the benefit state in this calibration: T[j,0] = 0.25 for
every unemployed j) the same rate at every period after it, verified to machine precision.

So the fix changes WHO IS WHERE in the benefit chain and nothing else: the unemployment path is
untouched, and the onset cohort's state label becomes the count of quarters it has actually drawn.

SCOPE.  This is NOT confined to the UI extension.  It also gives the spike cohort its second
ordinary benefit quarter in the plain recession, the stimulus check and the tax cut, so it moves
three arms that have nothing to do with unemployment insurance.  Hence the flag and the
measure-on-its-own discipline of the plan
(``plans_local/20260906-0600h_ui-extension-four-quarter-cap_plan.md``).

Flag: ``HAFISCAL_ONSET_SPIKE_T0_EXEMPT``.  See ``Code/HA-Models/docs/ENV_FLAGS.md``.
"""

import os

import numpy as np

#: micro state index of the first benefit quarter in the UNWRAPPED employment chain
FIRST_BENEFIT_STATE = 1

#: micro state index of employment in the UNWRAPPED employment chain
EMPLOYED_STATE = 0

#: the shock types whose period 0 applies the spike (``tm_methods._mc_hit_uses_recession_urate``
#: and ``AggFiscalModel.hit_with_recession_shock`` must agree with this list)
SPIKED_SHOCK_TYPES = ('recession', 'recessionUI', 'recessionTaxCut', 'recessionCheck')

_ENV = "HAFISCAL_ONSET_SPIKE_T0_EXEMPT"


def t0_exempt():
    """Hold the onset-spiked households in their first benefit state at period 0?

    Reads ``HAFISCAL_ONSET_SPIKE_T0_EXEMPT``.  Two different defaults meet here and the gap
    between them is a trap worth stating plainly:

    * **The catalog's default is ON** -- a BUG_FIX in BOTH worlds since the owner's ruling of
      2026-09-06 -- applied by ``EstimParameters``' world block through ``os.environ.setdefault``.
    * **This function's own fallback, when the variable is UNSET, is OFF**: the published
      ordering, which advances the spiked out of their first benefit quarter.

    On a normal run the first fact wins and the second is unreachable.  It becomes reachable
    exactly on the paths that skip the world block -- a ``HAFISCAL_QE_FIDELITY=1`` reproduction
    arm, a bare diagnostic import -- which are also the paths where OFF is the wanted answer.
    That is convenient and it is fragile: a driver that marked its reference arm by UNSETTING
    the variable got OFF before 2026-09-06 and gets ON after it, with nothing said either way.
    Three such drivers existed on 2026-09-07 (see ``rerun_logs/onset_spike_20260906/``).

    So an unset variable at the point of use is treated as what it is -- nobody having decided --
    and announced once, loudly, naming which ordering it selected.  Pin ``0`` or ``1``.
    """
    raw = os.environ.get(_ENV, "").strip()
    if raw == "":
        _announce_unset()
        return False
    return raw.lower() in ("1", "on", "true", "yes")


def spike_fraction(urate_normal, urate_recession):
    """Share of the employed laid off at the onset, or 0.0 when the target rate is no higher."""
    un = float(urate_normal)
    ur = float(urate_recession)
    if not ur > un:
        return 0.0
    return (ur - un) / (1.0 - un)


_ANNOUNCED = set()
_UNSET_ANNOUNCED = False


def _announce_unset():
    """Say once that nobody decided the onset-spike ordering, and which way it therefore went.

    The companion of ``_announce``: that one proves the fix ARRIVED, this one proves a run that
    looks configured is running on a fallback.  Both exist because BUG-085 was a flag that
    resolved, logged, and never reached the code that mattered.
    """
    global _UNSET_ANNOUNCED
    if _UNSET_ANNOUNCED:
        return
    _UNSET_ANNOUNCED = True
    enc = os.environ.get("HAFISCAL_UI_STATE_ENCODING", "") or "<unset>"
    print(f"[onset-spike] WARNING: {_ENV} is UNSET where it is read, so the PUBLISHED ordering "
          f"is in force (the spiked are advanced out of their first benefit quarter). The "
          f"catalog default is ON, so this run did not pass through the world block "
          f"(HAFISCAL_UI_STATE_ENCODING={enc}). Pin {_ENV}=0 if this is the reproduction "
          f"reference arm, 1 otherwise. Unsetting it is not a decision.", flush=True)


def _announce(published, exempt_frac):
    """Say once per process that the exemption reached the computation, and with what number.

    A new axis is worth nothing until you can see it arrive: BUG-085 was a flag that resolved,
    logged and never reached the code that mattered. One line per distinct fraction pair keeps
    this cheap at Baseline scale (21 cohorts x 8 experiments would otherwise be 168 lines).
    """
    key = (round(float(published), 9), round(float(exempt_frac), 9))
    if key in _ANNOUNCED:
        return
    _ANNOUNCED.add(key)
    print(f"[onset-spike] t=0 exemption ON: the spiked are held in their first benefit quarter; "
          f"spike fraction {published:.6f} -> {exempt_frac:.6f} "
          f"(resized so the unemployment path is unchanged)", flush=True)


def exempt_spike_fraction(cond_mrkv, published_fraction):
    """Resize the spike for the exempt ordering, so the unemployment rate is unchanged.

    Under the published ordering the spiked households transition immediately, and a share
    ``T[1, 0]`` of them find work again in the same quarter; the net unemployment the spike adds
    is ``f * (T[0,0] - T[1,0])``.  When they are HELD in their first benefit state instead, all of
    them stay unemployed, but they forgo the ``T[0,0]`` chance of having kept their job, so the
    net addition is ``f_exempt * T[0,0]``.  Equating the two gives the factor below.

    Returns 0.0 rather than a negative fraction in the degenerate case where job-finding out of
    the first benefit state is at least as likely as staying employed.
    """
    chain = np.asarray(cond_mrkv, dtype=np.float64)
    stay = float(chain[EMPLOYED_STATE, EMPLOYED_STATE])
    find = float(chain[FIRST_BENEFIT_STATE, EMPLOYED_STATE])
    if stay <= 0.0 or find >= stay:
        return 0.0
    frac = float(published_fraction) * (stay - find) / stay
    _announce(published_fraction, frac)
    return frac


def period0_employed_row(cond_mrkv, published_fraction, exempt=None):
    """The period-0 transition row for the EMPLOYED state, with the spike blended in.

    ``cond_mrkv`` is the UNWRAPPED (J, J) employment chain for the period-0 macro state, and
    ``published_fraction`` is :func:`spike_fraction` -- the share the PUBLISHED ordering lays off.
    The unspiked share transitions normally.  The spiked share either transitions from the first
    benefit state (published ordering, ``exempt=False``) or stays in it for this one recorded
    period (``exempt=True``), in which case the share itself is resized by
    :func:`exempt_spike_fraction` so the unemployment rate is the same either way.

    Returns a fresh (J,) row; the caller writes it into its own copy of the chain and wraps it.
    """
    if exempt is None:
        exempt = t0_exempt()
    chain = np.asarray(cond_mrkv, dtype=np.float64)
    if not exempt:
        return ((1.0 - published_fraction) * chain[EMPLOYED_STATE, :]
                + published_fraction * chain[FIRST_BENEFIT_STATE, :])
    frac = exempt_spike_fraction(chain, published_fraction)
    held = np.zeros(chain.shape[1], dtype=np.float64)
    held[FIRST_BENEFIT_STATE] = 1.0
    return (1.0 - frac) * chain[EMPLOYED_STATE, :] + frac * held
