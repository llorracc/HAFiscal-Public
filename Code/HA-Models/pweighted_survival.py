"""The p-weighted survival weight: the ONE definition of how mass moves under mortality and growth.

BUG-108. Under a permanent-income-weighted measure -- HARK's Harmenberg neutral measure IS the Doob
h-transform with h(p) = p, which is what makes the ``pmv *= psi`` rescale legitimate -- the objects
being tracked are permanent-income DOLLARS, not people. Over one period, from a cell holding P
dollars and N people:

    survivors carry forward   LivPrb * Gamma * P     (they survive at LivPrb; each survivor's p grows by Gamma)
    newborns bring            (1 - LivPrb) * 1 * N   (a headcount of arrivals, each at p = p_birth = 1)

so in the normalized stationary measure survivors and newborns stand in the ratio

    LivPrb * Gamma  :  1 - LivPrb * Gamma                        <- 'doob'

The plain kernel uses ``LivPrb : 1 - LivPrb`` ('bst'), which is exact under its own kernel and biased
against the true p-weighted dynamics whenever there is BOTH mortality and growth: it forgets that the
incumbent stock of permanent income expands every period, so newborns -- who always arrive at p = 1
with no assets -- take their HEADCOUNT share of the dollars instead of their smaller dollar share.
The bias is signed: over-injecting at m = 1 under-weights the long-lived dynasties that carry the
wealth tail, so it lands almost entirely on the patient discount-factor atoms.

Measured on the Step-4 household block (2026-08-30, lambda = 0.44, LivPrb = 0.99375): the plain
newborn weight is 1.33x (dropout) to 1.52x (college) too large; correcting it moves the
education- and beta-weighted aggregates A_ss +22.97 % and C_ss +1.07 %, and +30.10 % at the most
patient college atom -- which is the same headline number the PE side's BUG-093 reported.

WHY THIS MODULE EXISTS AT ALL. The rule had been written down twice, in two spellings, and the two
drifted: ``tm_methods`` (the PE's a-indexed path) was corrected to 'doob' by BUG-093 in August, while
``ConsMarkovModel``/``step4_fast_tranmat`` (the HANK path) stayed on 'bst' because nobody asked
whether Step 4 was on the same construction. That is the fourth instance of one pattern in a single
day (BUG-105 the unemployed income SST, BUG-106 the tail machinery, BUG-107 the PF limits). The
arithmetic was never the hard part; keeping ONE copy of it is.

NOTATION (owner ruling 2026-08-30). In prose and math this quantity is written **ℒΓ** -- the product
of two symbols the econ-ark registry already carries, survival probability and growth factor -- and
is given NO letter of its own. NARK reserves ω for weights (``\ARKcommand{\weight}{\omega}``, now
recorded in the registry as of v1.2.0), so ω would have been available; it is deliberately not used
here. Writing the product keeps the CONTENT of BUG-108 visible at every mention: a reader sees that
the survivor weight is survival times growth, which is the entire substance of the defect, whereas a
single letter would hide it. In code the name is ``SurvWgt`` -- NARK's own escape hatch for a taken
letter is a multi-letter name, and NARK exempts only {a, b, c, m} from its single-letter prohibition.
It was briefly written ``w``, which collides with NARK's W = Wage -- the wage is a live input to this
very model -- and that is what prompted the ruling.

WHAT CALLERS GET, AND WHY IT IS A SINGLE SCALAR. ``survivor_weight`` returns SurvWgt = ℒΓ. Every
caller then obtains the newborn weight as ``1.0 - SurvWgt`` in one operation on that identical float -- HARK's
``gen_tran_matrix_1D`` does this internally, and the numba kernel does it inline. So no caller ever
multiplies LivPrb by Gamma, and the two builders cannot disagree by grouping the product differently:
there is no product left in either of them. The pre-existing bitwise kernel-vs-loop gate therefore
becomes a structural invariant rather than a coincidence maintained by care.

DOCUMENTED RESIDUAL (4.2e-5). Correcting the WEIGHT is not the whole of the exact p-weighted step.
The newborn CROSS-SECTION is also wrong in the plain form: the newborn term is shaped by the parent
column's p-weighted mass f rather than by the people count N, and those differ because growth is
suspended during unemployment (``income_process_sst.build_PermGroFac_micro(..., G_unemployed=1.0)``),
so E[p | employment state] is not flat -- it spreads 0.77 / 1.03 / 1.13 % across states. The exact
affine form (f = A f + w_new * pi_N (x) NB, with A sub-stochastic) was measured against the
column-stochastic form used here: A_ss +22.975 % vs +22.970 %, a 4.2e-5 relative difference. The
column-stochastic form is used because it keeps every transition matrix column summing to 1, so
``calc_ergodic_dist`` and every consumer of ``tran_matrix`` are unchanged in FORM; adopting the exact
affine step would turn the matrix into an operator-plus-constant. Revisit if a future calibration
makes Gamma vary more across states.
"""
import os

import numpy as np

METHODS = ("doob", "bst")
_DEFAULT = "doob"


def resolve_method(method=None, environ=None):
    """Which construction is in force: explicit argument, then HAFISCAL_STEP4_TRANMAT_QMETHOD, then
    HAFISCAL_TM_Q_METHOD (so one knob moves the PE and the HANK block together, which is what the
    correction ladder wants), then the module default.

    HAFISCAL_TM_Q_METHOD's third value 'cohort' is a PE-only start rule that has no meaning for a
    stationary transition matrix; it resolves to the default here rather than raising, so a PE
    experiment that sets it does not break Step 4.
    """
    env = os.environ if environ is None else environ
    if method is not None:
        if method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}, got {method!r}")
        return method
    for var in ("HAFISCAL_STEP4_TRANMAT_QMETHOD", "HAFISCAL_TM_Q_METHOD"):
        val = env.get(var, "").strip().lower()
        if val in METHODS:
            return val
        if val and var == "HAFISCAL_STEP4_TRANMAT_QMETHOD":
            raise ValueError(f"{var}={val!r} not recognized; valid: {', '.join(METHODS)}")
    return _DEFAULT


def survivor_weight(LivPrb, PermGroFac, method=None, environ=None):
    """The weight the SURVIVING mass carries into the next period, under the p-weighted measure.

    Newborns take the complement, which every caller forms as ``1.0 - SurvWgt`` on the returned float.

    Parameters
    ----------
    LivPrb : float                 survival probability (scalar; mortality is state-independent here)
    PermGroFac : float or array    the growth factor of the state being transitioned INTO. Under
                                   'doob' this is what the plain kernel omits; pass 1.0 (or the
                                   growth-free vector) and 'doob' and 'bst' agree EXACTLY, since
                                   x * 1.0 == x in IEEE arithmetic -- which is why turning growth off
                                   leaves the build byte-identical.
    Returns
    -------
    float or ndarray               SurvWgt, matching PermGroFac's shape.
    """
    L = float(LivPrb)
    if resolve_method(method, environ) == "bst":
        g = np.asarray(PermGroFac, dtype=float)
        return L if g.ndim == 0 else np.full(g.shape, L)
    return L * np.asarray(PermGroFac, dtype=float) if np.ndim(PermGroFac) else L * float(PermGroFac)


def newborn_pmass_weight(delta_bar, p_bar, pLvl_factor):
    """The DATED form of the same rule, for a p-distribution being propagated period by period:
    w_new = (delta_bar / p_bar) / pLvl_factor_t. This is the quantity ``tm_methods._q_step`` applies
    to the newborn distribution on the PE's a-indexed path (BUG-093's Fix 4).

    It is the same specification as ``survivor_weight``'s complement, evaluated in a dated rather
    than a stationary regime: as the p-level factor settles onto its balanced-growth path the dated
    weight converges to ``1 - LivPrb*Gamma``. ``test_pweighted_survival.py`` asserts that convergence,
    which is the check that would have caught the two spellings drifting apart.

    SCOPE NOTE (dual-path sweep 2026-09-02): the welfare joint-pLvl kernels
    (``welfare6_tm_joint5d``, ``welfare6_jpLvl``, ``welfare6_ajpLvl_build``), the 2D (m,p)
    branches of ``ConsMarkovModel.calc_transition_matrix``, and the state-fraction propagator
    (``tm_methods._propagate_state_fracs``) use the PLAIN ``1 - LivPrb`` split ON PURPOSE:
    they work in representations that carry the permanent-income level explicitly (per-capita
    measure), where the plain split is the correct arithmetic. ``LivPrb*Gamma`` is the
    p-WEIGHTED measure's weight and applies only where income has been factored out
    (Harmenberg). Do not "fix" those sites onto this module.

    NOTE ON WHY tm_methods IS NOT ROUTED THROUGH ``survivor_weight``. It would look like the obvious
    reuse, and it would be a downgrade. ``_baseline_ergodic_a`` does not evaluate any closed form: it
    takes ``doob_inj = 1 - sum(T_surv_p @ pi_Q)`` -- the complement of its survivor operator's ACTUAL
    mass throughput on the stationary distribution. That is the same specification computed FROM THE
    OBJECT, and it is strictly more general than ``LivPrb*Gamma`` because it assumes nothing about how
    growth and survival enter the operator. The Step-4 builders cannot use that form: they need a
    per-block scalar while assembling the matrix, before any stationary distribution exists. So the
    two are one specification with two evaluations, not two spellings of one formula -- and the
    honest link is an equality GATE (``test_sst_weights_reproduce_the_operator_mass_throughput``),
    which asserts that the closed form reproduces what the operator says to machine precision.
    """
    return (float(delta_bar) / float(p_bar)) / float(pLvl_factor)
