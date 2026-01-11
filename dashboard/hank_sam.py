"""
hank_sam.py – Complete HANK + SAM with HA-Fiscal households (Modular Refactoring)
Author: Alan Lujan <alujan@jhu.edu>

This is a clean, modular refactoring of hafiscal.py that produces EXACTLY the same
results, features, and graphs while improving code organization and maintainability.

This module implements a Heterogeneous Agent New Keynesian (HANK) model combined with
a Search and Matching (SAM) labor market framework. The model features:

1. Heterogeneous households with unemployment risk across 6 employment states:
   - State 0: Employed
   - States 1-2: Unemployed with UI benefits
   - States 3-4: Unemployed with exhausted UI (eligible for extensions)
   - State 5: Long-term unemployed

2. Search frictions in the labor market:
   - Cobb-Douglas matching function M = χ·v^α·u^(1-α)
   - Endogenous job finding and separation rates
   - Vacancy posting costs

3. Fiscal policy tools:
   - Unemployment insurance (UI) extensions for states 3-4
   - Lump-sum transfers (stimulus checks)
   - Temporary tax cuts on labor income

4. Monetary policy regimes:
   - Standard Taylor rule responding to inflation
   - Fixed nominal interest rate
   - Fixed real interest rate

5. Financial markets:
   - Long-term government bonds with geometric decay δ
   - No-arbitrage bond pricing

6. Nominal rigidities:
   - Rotemberg price adjustment costs
   - Real wage rigidity

The main workflow:
1. Calibrate labor market parameters and steady-state distributions
2. Calibrate general equilibrium values (production, government, bonds)
3. Load pre-computed household Jacobians from pickle files
4. Define sequence-jacobian model blocks for GE interactions
5. Create different model variants for policy experiments
6. Run policy experiments and compute fiscal multipliers
7. Generate plots comparing policies under different monetary regimes

Key Results:
- Fiscal multipliers vary significantly with monetary policy stance
- UI extensions have larger multipliers than untargeted transfers
- Tax cuts have the smallest multipliers
- Fixed nominal/real rates amplify fiscal policy effects via GE channels
"""

import numpy as np
from copy import deepcopy
import scipy.sparse as sp
import matplotlib.pyplot as plt
import pickle
from pathlib import Path

# Import updated plotting functions
from plotting_functions import (
    plot_multipliers_three_experiments,
    plot_consumption_irfs_three_experiments
)

import sequence_jacobian as sj
from sequence_jacobian.classes import JacobianDict, SteadyStateDict
from sequence_jacobian import create_model

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1: GLOBAL PARAMETERS AND CALIBRATION
# ═════════════════════════════════════════════════════════════════════════════

# Labor market parameters
job_find = (
    2 / 3
)  # Job finding probability per quarter (implies avg 1.5 quarters to find job)
EU_prob = 0.0306834  # Employment to Unemployment transition probability (calibrated to match U = 6.4%)
job_sep = EU_prob / (
    1 - job_find
)  # Job separation rate (derived from flow balance equation)

# Matching function parameters (Cobb-Douglas: M = χ·v^α·u^(1-α))
alpha = 0.65  # Matching elasticity with respect to vacancies (higher α = vacancies more important)
phi_ss = 0.71  # Steady-state vacancy filling probability (firms fill 71% of vacancies each quarter)

# Financial parameters
R = 1.01  # Quarterly gross real interest rate (4% annual)
r_ss = R - 1  # Net real interest rate

# Steady state values (from heterogeneous agent model simulation)
C_ss_sim = 0.6910496136078721  # Aggregate consumption from HA model steady state
C_ss = C_ss_sim
A_ss_sim = 1.4324029855872642  # Aggregate assets from HA model steady state
A_ss = A_ss_sim

# Policy parameters
wage_ss = 1.0  # Steady state wage (normalized to 1 for convenience)
inc_ui_exhaust = (
    0.5  # Income replacement ratio for UI-exhausted unemployed (50% of wage)
)
tau_ss = 0.3  # Steady state labor income tax rate (30%)
UI = 0.5 * (1 - tau_ss) * wage_ss  # Effective UI benefit (50% of after-tax wage)

# Production parameters (monopolistic competition with Rotemberg pricing)
epsilon_p = 6  # Elasticity of substitution between varieties (markup = ε/(ε-1) = 20%)
varphi = 96.9  # Rotemberg price adjustment cost parameter
MC_ss = (epsilon_p - 1) / epsilon_p  # Steady state marginal cost (= 1/markup)

# Monetary and fiscal policy parameters
phi_pi = 1.5  # Taylor rule coefficient on inflation deviation (standard value)
phi_y = 0.0  # Taylor rule coefficient on output gap (0 = strict inflation targeting)
rho_r = 0.0  # Interest rate smoothing parameter (0 = no inertia)
kappa_p_ss = 0.06191950464396284  # Slope of Phillips curve (calibrated to match inflation dynamics)
phi_b = 0.015  # Fiscal adjustment speed (tax rate response to debt/GDP ratio)
real_wage_rigidity = (
    0.837  # Degree of real wage rigidity (0 = flexible, 1 = fixed real wage)
)
phi_w = 1.0  # Wage rigidity parameter (can be overridden in steady state dict)

# Policy experiment durations (in quarters)
UI_extension_length = (
    4  # Duration of 2-quarter UI extension policy (benefits extended for 4 quarters)
)
stimulus_check_length = 1  # One-time lump-sum transfer payment
tax_cut_length = 8  # Temporary tax cut lasts 2 years

# Computational parameters
bigT = 300  # Time horizon for impulse responses and Jacobian matrices

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2: LABOR MARKET CALIBRATION
# ═════════════════════════════════════════════════════════════════════════════


def calibrate_labor_market():
    """
    Calibrate job transition probabilities and compute steady state distribution.

    Uses global parameters job_find, EU_prob, and job_sep to construct a 6-state
    Markov transition matrix for employment states and compute its steady-state
    distribution using eigenvalue decomposition.

    Returns:
        tuple: Contains (markov_array_ss, ss_dstn, U_ss, N_ss, num_mrkv)
            - markov_array_ss: 6x6 Markov transition matrix
            - ss_dstn: Steady-state distribution across 6 employment states
            - U_ss: Steady-state unemployment rate
            - N_ss: Steady-state employment rate
            - num_mrkv: Number of Markov states (6)
    """
    markov_array_ss = np.array(
        [
            [
                1 - job_sep * (1 - job_find),
                job_find,
                job_find,
                job_find,
                job_find,
                job_find,
            ],
            [job_sep * (1 - job_find), 0.0, 0.0, 0, 0, 0],
            [0.0, (1 - job_find), 0.0, 0.0, 0.0, 0.0],
            [0.0, 0, (1 - job_find), 0.0, 0.0, 0.0],
            [0.0, 0, 0.0, (1 - job_find), 0.0, 0.0],
            [0.0, 0.0, 0, 0, (1 - job_find), (1 - job_find)],
        ]
    )

    num_mrkv = len(markov_array_ss)

    # Get steady state distribution
    from scipy.sparse.linalg import eigs

    eigen, ss_dstn = eigs(markov_array_ss, k=1, which="LM")
    ss_dstn = ss_dstn[:, 0] / np.sum(ss_dstn[:, 0])
    ss_dstn = ss_dstn.real

    U_ss = 1 - ss_dstn[0]  # steady state unemployment
    N_ss = ss_dstn[0]  # steady state employment

    return markov_array_ss, ss_dstn, U_ss, N_ss, num_mrkv


def compute_unemployment_jacobian(markov_array_ss, ss_dstn, num_mrkv):
    """
    Compute unemployment rate Jacobian with respect to job finding probability.

    This function calculates how the distribution across employment states changes
    in response to a small change in the job finding probability, creating a
    Jacobian matrix of dimension (num_mrkv x bigT x bigT).

    Args:
        markov_array_ss: Steady-state Markov transition matrix
        ss_dstn: Steady-state distribution
        num_mrkv: Number of Markov states

    Returns:
        np.ndarray: Jacobian matrix of shape (num_mrkv, bigT, bigT)
    """

    def create_matrix_U(dx):
        job_find_dx = job_find + dx
        markov_array = np.array(
            [
                [
                    1 - job_sep * (1 - job_find_dx),
                    job_find_dx,
                    job_find_dx,
                    job_find_dx,
                    job_find_dx,
                    job_find_dx,
                ],
                [job_sep * (1 - job_find_dx), 0.0, 0.0, 0, 0, 0],
                [0.0, (1 - job_find_dx), 0.0, 0.0, 0.0, 0.0],
                [0.0, 0, (1 - job_find_dx), 0.0, 0.0, 0.0],
                [0.0, 0, 0.0, (1 - job_find_dx), 0.0, 0.0],
                [0.0, 0.0, 0, 0, (1 - job_find_dx), (1 - job_find_dx)],
            ]
        )
        return markov_array

    dx = 0.0001
    dstn = ss_dstn.copy()
    UJAC = np.zeros((num_mrkv, bigT, bigT))

    for s in range(bigT):
        for i in range(bigT):
            if i == s:
                tranmat = create_matrix_U(dx)
                dstn = np.dot(tranmat, dstn)
            else:
                dstn = np.dot(markov_array_ss, dstn)

            UJAC[:, i, s] = (dstn - ss_dstn) / dx

    return UJAC


def calibrate_general_equilibrium(N_ss, ss_dstn):
    """
    Calibrate general equilibrium parameters given labor market steady state.

    This function computes all general equilibrium values including labor market
    tightness, bond prices, government spending, production parameters, and
    steady-state output.

    Args:
        N_ss: Steady-state employment rate
        ss_dstn: Steady-state distribution across employment states

    Returns:
        dict: Dictionary containing all calibrated GE parameters including:
            v_ss, theta_ss, chi_ss, eta_ss, delta, qb_ss, B_ss, Y_priv,
            G_ss, kappa, HC_ss, Z_ss, Y_ss, pi_ss
    """
    # Steady State vacancies
    # From flow balance: hires = v * phi = N * job_sep (in steady state)
    v_ss = N_ss * job_sep / phi_ss

    # Count unemployed job searchers (all unemployed states)
    unemployed_searchers = (
        ss_dstn[1] + ss_dstn[2] + ss_dstn[3] + ss_dstn[4] + ss_dstn[5]
    )

    # Total job searchers include unemployed + employed who will separate
    seachers = unemployed_searchers + N_ss * job_sep

    # Labor market tightness = vacancies / searchers
    theta_ss = v_ss / seachers

    # Matching efficiency calibrated to match steady state phi and theta
    # From matching function: phi = chi * theta^(-alpha)
    # Solving for chi: chi = phi * theta^alpha
    chi_ss = (phi_ss ** (1 / -alpha) / theta_ss) ** (-alpha)

    # Job finding probability from matching function
    # eta = M/u = chi * (v/u)^(1-alpha) = chi * theta^(1-alpha)
    eta_ss = chi_ss * theta_ss ** (1 - alpha)

    # Long term bonds with geometric maturity structure
    # Bond has expected duration of 5 years (20 quarters)
    # Each period, fraction (1/5)^(1/4) of bonds mature
    delta = ((R**4) * (1 - (1 / 5))) ** (1 / 4)  # Geometric decay rate

    # Bond price from no-arbitrage condition
    # q = 1/(R - delta) gives price of perpetuity paying delta*q each period
    qb_ss = (1) / (R - delta)

    # Total bonds outstanding to match household asset holdings
    B_ss = A_ss / qb_ss

    # Private/spousal income for unemployed
    # UI exhausted (states 3-5): receive 50% of after-tax wage from spousal/informal income
    # UI recipients (states 1-2): receive additional 20% on top of UI benefits
    Y_priv = inc_ui_exhaust * (1 - tau_ss) * wage_ss * (
        ss_dstn[3] + ss_dstn[4] + ss_dstn[5]
    ) + (0.7 - 0.5) * (1 - tau_ss) * wage_ss * (ss_dstn[1] + ss_dstn[2])

    # Government budget constraint in steady state
    # Revenue: tau * w * N + seigniorage from bond rollovers
    # Spending: G + UI benefits
    # Seigniorage = (1 + delta*q)*B - q*B = delta*q*B
    G_ss = tau_ss * wage_ss * ss_dstn[0] - (
        UI * (ss_dstn[1] + ss_dstn[2]) + (1 + delta * qb_ss) * B_ss - qb_ss * B_ss
    )

    # Vacancy posting cost calibrated as 7% of quarterly wage bill
    kappa = 0.07 * (wage_ss * phi_ss)

    # Hiring cost from firm's FOC for vacancy posting
    # HC = w + kappa/phi - (1/R)*(1-sep)*kappa/phi(+1)
    # In steady state, phi(+1) = phi, so:
    HC_ss = (kappa / phi_ss) * (1 - (1 / R) * (1 - job_sep)) + wage_ss

    # TFP ensures marginal cost equals steady state value
    # From MC = HC/Z, we get Z = HC/MC
    Z_ss = HC_ss / MC_ss

    # Output from production function Y = Z*N
    Y_ss = Z_ss * N_ss

    # Zero inflation in steady state
    pi_ss = 0.0

    return {
        "v_ss": v_ss,
        "theta_ss": theta_ss,
        "chi_ss": chi_ss,
        "eta_ss": eta_ss,
        "delta": delta,
        "qb_ss": qb_ss,
        "B_ss": B_ss,
        "Y_priv": Y_priv,
        "G_ss": G_ss,
        "kappa": kappa,
        "HC_ss": HC_ss,
        "Z_ss": Z_ss,
        "Y_ss": Y_ss,
        "pi_ss": pi_ss,
    }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3: SEQUENCE-JACOBIAN MODEL BLOCKS
# ═════════════════════════════════════════════════════════════════════════════
# These blocks define the general equilibrium relationships in the model.
# Each block represents an equation or system that determines endogenous variables.
# The @sj decorators specify whether blocks are simple algebraic (@sj.simple) or
# require numerical solving (@sj.solved).


@sj.simple
def unemployment1(U1, U2, U3, U4, U5):
    """
    Aggregate unemployment rate calculation.

    Sums unemployment across all 5 unemployed states to get total unemployment.
    State 1-2: Unemployed with UI benefits
    State 3-4: Unemployed with exhausted UI
    State 5: Long-term unemployed

    Returns:
        U: Total unemployment rate
    """
    U = U1 + U2 + U3 + U4 + U5
    return U


@sj.simple
def marginal_cost(HC, Z):
    """
    Firm's marginal cost of production.

    In equilibrium, marginal cost equals hiring cost divided by productivity.
    This reflects that firms must pay hiring costs to expand employment.

    Args:
        HC: Hiring cost per worker
        Z: Total factor productivity

    Returns:
        MC: Marginal cost of production
    """
    MC = HC / Z
    return MC


@sj.solved(unknowns={"HC": (-10, 10.0)}, targets=["HC_resid"], solver="brentq")
def hiring_cost(HC, Z, phi, job_sep, r_ante, w):
    """
    Hiring cost determination from firm's first-order condition.

    Firms choose vacancies to equate marginal hiring cost with the present value
    of marginal profits from an additional worker. The hiring cost includes both
    the wage and the expected cost of replacing the worker.

    Args:
        HC: Hiring cost (endogenous, solved for)
        Z: Productivity
        phi: Vacancy filling probability
        job_sep: Job separation rate
        r_ante: Ex-ante real interest rate
        w: Real wage

    Returns:
        HC_resid: Residual of hiring cost FOC (should be 0 in equilibrium)
    """
    HC_resid = HC - (
        w + (kappa / (phi)) - (1 / (1 + r_ante)) * (1 - job_sep) * (kappa / (phi(+1)))
    )
    return HC_resid


@sj.solved(unknowns={"w": (-10, 10.0)}, targets=["wage_resid"], solver="brentq")
def wage_(w, N, phi_w):
    """
    Wage determination with real wage rigidity.

    Wages adjust partially to employment changes. With phi_w = 1, real wages are
    completely rigid. With phi_w = 0, wages fully adjust to clear the labor market.
    The equation is in logs to ensure positive wages.

    Args:
        w: Real wage (endogenous, solved for)
        N: Employment rate
        phi_w: Degree of real wage rigidity (0 = flexible, 1 = rigid)

    Returns:
        wage_resid: Residual of wage equation (should be 0 in equilibrium)
    """
    wage_resid = (w / wage_ss).apply(np.log) - (
        phi_w * (w(-1) / wage_ss).apply(np.log) + (1 - phi_w) * (N / N_ss).apply(np.log)
    )
    return wage_resid


@sj.solved(unknowns={"pi": (-0.1, 0.1)}, targets=["nkpc_resid"], solver="brentq")
def Phillips_Curve(pi, MC, Y, r_ante, kappa_p):
    """
    New Keynesian Phillips Curve with Rotemberg pricing.

    Inflation depends on current marginal cost deviations and expected future
    inflation, discounted by the real interest rate. The slope kappa_p determines
    how responsive inflation is to marginal cost.

    Args:
        pi: Inflation rate (endogenous, solved for)
        MC: Marginal cost
        Y: Output
        r_ante: Ex-ante real interest rate
        kappa_p: Slope of Phillips curve

    Returns:
        nkpc_resid: Residual of NKPC (should be 0 in equilibrium)
    """
    nkpc_resid = (1 + pi).apply(np.log) - (
        kappa_p * (MC - MC_ss)
        + (1 / (1 + r_ante)) * (Y(+1) / Y) * (1 + pi(+1)).apply(np.log)
    )
    return nkpc_resid


@sj.solved(unknowns={"i": (-0.5, 0.4)}, targets=["taylor_resid"], solver="brentq")
def taylor(i, pi, Y, ev, rho_r, phi_y, phi_pi):
    """
    Standard Taylor rule for monetary policy.

    The central bank sets the nominal interest rate in response to inflation
    and output deviations. The rule includes interest rate smoothing (rho_r)
    and can incorporate exogenous monetary shocks (ev).

    Args:
        i: Nominal interest rate (endogenous, solved for)
        pi: Inflation rate
        Y: Output (in deviation from steady state)
        ev: Monetary policy shock
        rho_r: Interest rate smoothing parameter
        phi_y: Response coefficient to output
        phi_pi: Response coefficient to inflation

    Returns:
        taylor_resid: Residual of Taylor rule (should be 0)
    """
    taylor_resid = i - rho_r * i(-1) - (1 - rho_r) * (phi_pi * pi + phi_y * Y) - ev
    return taylor_resid


@sj.solved(unknowns={"i": (-0.5, 0.4)}, targets=["taylor_resid"], solver="brentq")
def taylor_lagged(i, pi, Y, ev, rho_r, phi_y, phi_pi, lag):
    """
    Taylor rule with lagged responses.

    This variant allows the central bank to respond to lagged values of inflation
    and output, capturing implementation delays in monetary policy.

    Args:
        i: Nominal interest rate (endogenous, solved for)
        pi: Inflation rate
        Y: Output
        ev: Monetary policy shock
        rho_r: Interest rate smoothing
        phi_y: Response to output
        phi_pi: Response to inflation
        lag: Number of periods to lag the response

    Returns:
        taylor_resid: Residual of Taylor rule
    """
    taylor_resid = (
        i - rho_r * i(-1) - (1 - rho_r) * (phi_pi * pi(-lag) + phi_y * Y(-lag)) - ev
    )
    return taylor_resid


@sj.simple
def matching(theta, chi):
    """
    Cobb-Douglas matching function.

    Determines job finding rate (eta) and vacancy filling rate (phi) given
    labor market tightness (theta = v/u) and matching efficiency (chi).

    Args:
        theta: Labor market tightness (v/u ratio)
        chi: Matching efficiency parameter

    Returns:
        eta: Job finding rate for workers
        phi: Vacancy filling rate for firms
    """
    eta = chi * theta ** (1 - alpha)  # Job finding rate = M/u
    phi = chi * theta ** (-alpha)  # Vacancy filling rate = M/v
    return eta, phi


@sj.solved(unknowns={"B": (0.0, 10)}, targets=["fiscal_resid"], solver="brentq")
def fiscal(
    B,
    N,
    qb,
    G,
    w,
    v,
    pi,
    phi_b,
    UI,
    U1,
    U2,
    U3,
    U4,
    transfers,
    UI_extend,
    deficit_T,
    UI_rr,
):
    """
    Government budget constraint with fiscal rule.

    The government finances spending (G), transfers, and UI benefits through
    labor income taxes and bond issuance. Taxes adjust gradually to stabilize
    the debt-to-GDP ratio according to the fiscal rule parameter phi_b.

    Args:
        B: Real government debt (endogenous, solved for)
        N: Employment
        qb: Bond price
        G: Government consumption
        w: Wage
        v: Vacancies (unused but kept for compatibility)
        pi: Inflation (unused but kept for compatibility)
        phi_b: Fiscal adjustment speed
        UI: Basic UI benefit
        U1, U2: Unemployed with UI benefits
        U3, U4: Unemployed eligible for UI extensions
        transfers: Lump-sum transfers (stimulus checks)
        UI_extend: UI extension indicator
        deficit_T: Periods until fiscal adjustment begins
        UI_rr: Additional UI replacement rate

    Returns:
        fiscal_resid: Budget constraint residual (should be 0)
        UI_extension_cost: Cost of UI extensions
        debt: Market value of government debt
        UI_rr_cost: Cost of additional UI benefits
    """
    # Government budget constraint:
    # (1 + δ*q)*B(-1) + G + transfers + UI_benefits = q*B + tax_revenue
    fiscal_resid = (
        (1 + delta * qb) * B(-1)  # Maturing bonds (principal + coupon)
        + G  # Government consumption
        + transfers  # Stimulus checks
        + UI * (U1 + U2)  # Basic UI benefits
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)  # Additional UI
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)  # UI extensions
        + -qb * B  # New bond issuance (negative = revenue)
        - (tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss)
        * w
        * N  # Tax revenue with fiscal rule
    )

    # Track fiscal costs for multiplier calculations
    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
    debt = qb * B

    return fiscal_resid, UI_extension_cost, debt, UI_rr_cost


@sj.simple
def fiscal_rule(B, phi_b, deficit_T):
    """
    Tax rate determination under fiscal rule.

    The tax rate adjusts from its steady state value in response to debt
    deviations, with adjustment speed phi_b. The adjustment can be delayed
    by deficit_T periods.

    Args:
        B: Government debt
        phi_b: Fiscal adjustment speed
        deficit_T: Periods until adjustment begins

    Returns:
        tau: Labor income tax rate
    """
    tau = tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    return tau


@sj.solved(unknowns={"B": (0.0, 10)}, targets=["fiscal_resid"], solver="brentq")
def fiscal_G(B, N, qb, w, v, pi, UI, U1, U2, transfers, phi_G, tau, deficit_T):
    """
    Government budget with endogenous G (for tax shock experiments).

    In this variant, government consumption adjusts to balance the budget
    when taxes are exogenously changed (e.g., tax cut experiments).

    Args:
        B: Government debt (endogenous)
        N: Employment
        qb: Bond price
        w: Wage
        v, pi: Unused (kept for compatibility)
        UI: UI benefit
        U1, U2: Unemployed with benefits
        transfers: Lump-sum transfers
        phi_G: Government spending adjustment speed
        tau: Tax rate (exogenous in this block)
        deficit_T: Adjustment delay

    Returns:
        fiscal_resid: Budget residual
        tax_cost: Total tax revenue (for multiplier calculations)
    """
    fiscal_resid = (
        (1 + delta * qb) * B(-1)
        + G_ss
        + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss  # G adjusts to debt
        + transfers
        + UI * (U1 + U2)
        + -qb * B
        - (tau) * w * N
    )

    tax_cost = (tau) * 1.0 * N_ss  # Tax revenue at steady state employment

    return fiscal_resid, tax_cost


@sj.simple
def fiscal_rule_G(B, phi_G, deficit_T):
    """
    Government consumption under fiscal rule.

    When taxes are fixed, government consumption adjusts to stabilize debt.

    Args:
        B: Government debt
        phi_G: Spending adjustment speed (negative of phi_b)
        deficit_T: Adjustment delay

    Returns:
        G: Government consumption
    """
    G = G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    return G


@sj.simple
def production(Z, N):
    """
    Aggregate production function.

    Output is produced with labor and constant TFP.

    Args:
        Z: Total factor productivity
        N: Employment

    Returns:
        Y: Aggregate output
    """
    Y = Z * N
    return Y


@sj.simple
def ex_post_longbonds_rate(qb):
    """
    Ex-post return on long-term bonds.

    Calculates the realized return on bonds purchased last period,
    accounting for capital gains/losses from price changes.

    Args:
        qb: Current bond price

    Returns:
        r: Ex-post real return
    """
    r = (1 + delta * qb) / qb(
        -1
    ) - 1  # Total return = (coupon + price) / purchase price - 1
    return r


@sj.solved(unknowns={"qb": (0.1, 30.0)}, targets=["lbp_resid"], solver="brentq")
def longbonds_price(qb, r_ante):
    """
    No-arbitrage pricing of long-term government bonds.

    Bond price ensures that expected return equals the risk-free rate.
    Bonds pay geometric coupon δ*q each period and mature probabilistically.

    Args:
        qb: Bond price (endogenous, solved for)
        r_ante: Ex-ante real interest rate

    Returns:
        lbp_resid: Pricing equation residual
    """
    # No-arbitrage: q = (1 + δ*q(+1)) / (1 + r)
    lbp_resid = qb - (1 + delta * qb(+1)) / (1 + r_ante)
    return lbp_resid


@sj.simple
def vacancies(N, phi, job_sep):
    """
    Vacancy determination from employment dynamics.

    The number of new hires equals employment change plus separations.
    Vacancies are then determined by the hiring rate (phi).

    Args:
        N: Current employment
        phi: Vacancy filling rate
        job_sep: Separation rate

    Returns:
        v: Number of vacancies
    """
    # New hires = N - (1-sep)*N(-1) = Change in employment + Separations
    v = (N - (1 - job_sep(-1)) * N(-1)) / phi
    return v


@sj.simple
def mkt_clearing(C, G, A, qb, B, w, N, U1, U2, U3, U4, U5):
    """
    Market clearing conditions.

    Ensures goods market and asset market clear in equilibrium.

    Args:
        C: Aggregate consumption
        G: Government consumption
        A: Household assets
        qb: Bond price
        B: Government bonds
        w: Wage
        N: Employment
        U1-U5: Unemployment by state

    Returns:
        goods_mkt: Goods market clearing residual (Y - C - G)
        asset_mkt: Asset market clearing residual (A - qB)
        Y_priv: Private income of unemployed (for accounting)
    """
    # Private income of unemployed (spousal income, informal work, etc.)
    Y_priv = (1 - tau_ss) * wage_ss * 0.5 * (U3 + U4 + U5) + (
        1 - tau_ss
    ) * wage_ss * 0.2 * (U1 + U2)

    goods_mkt = C + G - w * N - Y_priv  # Y = C + G (where Y = wN + Y_priv)
    asset_mkt = A - qb * B  # Household assets = Government debt

    return goods_mkt, asset_mkt, Y_priv


@sj.simple
def fisher_clearing(r_ante, pi, i):
    """
    Fisher equation linking nominal and real interest rates.

    Ensures consistency between nominal rate (i), real rate (r_ante),
    and expected inflation.

    Args:
        r_ante: Ex-ante real rate
        pi: Inflation
        i: Nominal rate

    Returns:
        fisher_resid: Fisher equation residual
    """
    fisher_resid = 1 + r_ante - ((1 + i) / (1 + pi(+1)))
    return fisher_resid


@sj.simple
def fisher_clearing_fixed_real_rate(pi):
    """
    Fisher equation with fixed real rate.

    For experiments with fixed real rates, nominal rate adjusts
    one-for-one with expected inflation.

    Args:
        pi: Inflation rate

    Returns:
        i: Nominal interest rate
    """
    i = (1 + pi(+1)) * (1 + r_ss) - 1
    return i


@sj.solved(unknowns={"B": (0.0, 10)}, targets=["fiscal_resid"], solver="brentq")
def fiscal_fixed_real_rate(
    B, N, G, w, v, pi, phi_b, UI, U1, U2, U3, U4, transfers, UI_extend, deficit_T, UI_rr
):
    """
    Government budget constraint with fixed real interest rate.

    Special case where bond prices are fixed at steady state values,
    used for fixed real rate experiments.

    All arguments and returns same as standard fiscal block, but with
    qb fixed at qb_ss throughout.
    """
    fiscal_resid = (
        (1 + delta * qb_ss) * B(-1)
        + G
        + transfers
        + UI * (U1 + U2)
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
        + -qb_ss * B
        - (tau_ss + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss) * w * N
    )

    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)

    return fiscal_resid, UI_extension_cost, UI_rr_cost


@sj.solved(unknowns={"B": (0.0, 10)}, targets=["fiscal_resid"], solver="brentq")
def fiscal_G_fixed_real_rate(
    B, N, w, v, pi, UI, U1, U2, transfers, phi_G, tau, deficit_T
):
    """
    Government budget with endogenous G and fixed real rate.

    Combines tax experiments with fixed real rate assumption.

    All arguments and returns same as fiscal_G block, but with
    qb fixed at qb_ss.
    """
    fiscal_resid = (
        (1 + delta * qb_ss) * B(-1)
        + G_ss
        + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
        + transfers
        + UI * (U1 + U2)
        + -qb_ss * B
        - (tau) * w * N
    )
    tax_cost = (tau) * 1.0 * N_ss

    return fiscal_resid, tax_cost


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4: STEADY STATE DICTIONARY AND JACOBIAN LOADING
# ═════════════════════════════════════════════════════════════════════════════

# Initialize calibration
markov_array_ss, ss_dstn, U_ss, N_ss, num_mrkv = calibrate_labor_market()
ge_params = calibrate_general_equilibrium(N_ss, ss_dstn)

# Extract calibrated values
v_ss = ge_params["v_ss"]
theta_ss = ge_params["theta_ss"]
chi_ss = ge_params["chi_ss"]
eta_ss = ge_params["eta_ss"]
delta = ge_params["delta"]
qb_ss = ge_params["qb_ss"]
B_ss = ge_params["B_ss"]
Y_priv = ge_params["Y_priv"]
G_ss = ge_params["G_ss"]
kappa = ge_params["kappa"]
HC_ss = ge_params["HC_ss"]
Z_ss = ge_params["Z_ss"]
Y_ss = ge_params["Y_ss"]
pi_ss = ge_params["pi_ss"]

# Define steady state dictionary
SteadyState_Dict = SteadyStateDict(
    {
        "asset_mkt": 0.0,
        "goods_mkt": 0.0,
        "arg_fisher_resid": 0.0,
        "lbp_resid": 0.0,
        "fiscal_resid": 0.0,
        "labor_evo_resid": 0.0,
        "taylor_resid": 0.0,
        "nkpc_resid": 0.0,
        "epsilon_p": epsilon_p,
        "U": (1 - N_ss),
        "U1": ss_dstn[1],
        "U2": ss_dstn[2],
        "U3": ss_dstn[3],
        "U4": ss_dstn[4],
        "U5": ss_dstn[5],
        "HC": MC_ss * Z_ss,
        "MC": MC_ss,
        "C": C_ss_sim,
        "r": r_ss,
        "r_ante": r_ss,
        "Y": Y_ss,
        "B": B_ss,
        "G": G_ss,
        "A": A_ss_sim,
        "tau": tau_ss,
        "eta": eta_ss,
        "phi_b": phi_b,
        "phi_w": phi_w,
        "N": N_ss,
        "phi": phi_ss,
        "v": v_ss,
        "ev": 0.0,
        "Z": Z_ss,
        "job_sep": job_sep,
        "w": wage_ss,
        "pi": pi_ss,
        "i": r_ss,
        "qb": qb_ss,
        "varphi": varphi,
        "rho_r": rho_r,
        "kappa_p": kappa_p_ss,
        "phi_pi": phi_pi,
        "phi_y": phi_y,
        "chi": chi_ss,
        "theta": theta_ss,
        "UI": UI,
        "transfers": 0.0,
        "UI_extend": 0.0,
        "deficit_T": -1,
        "UI_extension_cost": 0.0,
        "UI_rr": 0.0,
        "debt": qb_ss * B_ss,
        "tax_cost": tau_ss * wage_ss * N_ss,
        "lag": -1,
    }
)


def load_jacobians():
    """
    Load pre-computed Jacobians from pickle files.

    This function loads the main consumption and asset Jacobians as well as
    education-specific Jacobians and UI extension realizations from pickle files.

    Returns:
        tuple: (Jacobian_Dict, Jacobian_Dict_by_educ, Jacobian_Dict_UI_extend_real)
    """
    # Define base path relative to root directory (one above dashboard)
    base_path = Path(__file__).parent.parent / "Code/HA-Models/FromPandemicCode"

    # Load main Jacobians
    with open(base_path / "HA_Fiscal_Jacs.obj", "rb") as f:
        HA_fiscal_JAC = pickle.load(f)

    # Main jacobians for aggregate consumption and aggregate assets
    Jacobian_Dict = JacobianDict({"C": HA_fiscal_JAC["C"], "A": HA_fiscal_JAC["A"]})

    CJACs_by_educ = HA_fiscal_JAC["C_by_educ"]
    AJACs_by_educ = HA_fiscal_JAC["A_by_educ"]

    # Load UI extension Jacobians
    with open(base_path / "HA_Fiscal_Jacs_UI_extend_real.obj", "rb") as f:
        UI_extend_realized_Jacs = pickle.load(f)

    Jacobian_Dict_UI_extend_real = deepcopy(
        JacobianDict({"C": HA_fiscal_JAC["C"], "A": HA_fiscal_JAC["A"]})
    )

    Jacobian_Dict_UI_extend_real["C"]["UI_extend"] = UI_extend_realized_Jacs["C"][
        "UI_extend_real"
    ]
    Jacobian_Dict_UI_extend_real["A"]["UI_extend"] = UI_extend_realized_Jacs["A"][
        "UI_extend_real"
    ]

    Jacobian_Dict_by_educ = JacobianDict(
        {
            "C_dropout": CJACs_by_educ["dropout"],
            "C_highschool": CJACs_by_educ["highschool"],
            "C_college": CJACs_by_educ["college"],
            "A_dropout": AJACs_by_educ["dropout"],
            "A_highschool": AJACs_by_educ["highschool"],
            "A_college": AJACs_by_educ["college"],
        }
    )

    return Jacobian_Dict, Jacobian_Dict_by_educ, Jacobian_Dict_UI_extend_real


def apply_splurge_behavior(Jacobian_Dict):
    """
    Apply splurge behavior to Jacobians to capture hand-to-mouth consumption.

    This function modifies the consumption Jacobians to account for households
    that immediately consume a fraction (splurge rate) of any income shock rather
    than smoothing consumption over time. This captures the behavior of
    liquidity-constrained or hand-to-mouth households.

    The splurge behavior is implemented by:
    1. Computing the present value of each income shock
    2. Having splurge fraction consumed immediately when income arrives
    3. Remaining (1-splurge) fraction follows standard consumption smoothing

    Args:
        Jacobian_Dict: Dictionary of Jacobians to modify

    Returns:
        JacobianDict: Modified Jacobians with splurge behavior incorporated
    """
    old_Jacobian_Dict = deepcopy(Jacobian_Dict)
    periods = old_Jacobian_Dict["C"]["transfers"].shape[0]

    do_splurge = True
    if do_splurge:
        splurge = 0.3  # 30% of households are hand-to-mouth

        # Apply splurge behavior to all income-related Jacobians
        for jacobian_input in ["transfers", "tau", "UI_extend", "UI_rr", "eta", "w"]:
            # Calculate the present value of the policy announced for time s
            # This represents the total lifetime value of the shock
            present_value = np.sum(
                (old_Jacobian_Dict["C"][jacobian_input] / R ** np.arange(periods)),
                axis=0,
            )

            # The splurge jacobian consists of spending the present value
            # immediately when the cash arrives (diagonal matrix)
            splurge_jacobian_component = np.diag(
                present_value * R ** np.arange(periods)
            )

            # Total consumption response is weighted average:
            # - splurge fraction consumes immediately
            # - (1-splurge) fraction follows standard consumption smoothing
            splurge_jacobian = (
                splurge * splurge_jacobian_component
                + (1 - splurge) * old_Jacobian_Dict["C"][jacobian_input]
            )
            Jacobian_Dict["C"][jacobian_input] = splurge_jacobian

            # Assets only accumulate for non-splurge fraction
            Jacobian_Dict["A"][jacobian_input] = (1 - splurge) * old_Jacobian_Dict["A"][
                jacobian_input
            ]

    return Jacobian_Dict


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5: MODEL CREATION
# ═════════════════════════════════════════════════════════════════════════════

# Load and prepare Jacobians
Jacobian_Dict, Jacobian_Dict_by_educ, Jacobian_Dict_UI_extend_real = load_jacobians()
Jacobian_Dict = apply_splurge_behavior(Jacobian_Dict)
Jacobian_Dict_UI_extend_real = apply_splurge_behavior(Jacobian_Dict_UI_extend_real)

# Compute unemployment Jacobians
UJAC = compute_unemployment_jacobian(markov_array_ss, ss_dstn, num_mrkv)

# (Un)employment rate Jacobians
UJAC_dict = JacobianDict(
    {
        "N": {"eta": UJAC[0]},
        "U1": {"eta": UJAC[1]},
        "U2": {"eta": UJAC[2]},
        "U3": {"eta": UJAC[3]},
        "U4": {"eta": UJAC[4]},
        "U5": {"eta": UJAC[5]},
    }
)

# Create models
HANK_SAM = create_model(
    [
        Jacobian_Dict,
        Jacobian_Dict_by_educ,
        fiscal,
        longbonds_price,
        ex_post_longbonds_rate,
        fiscal_rule,
        production,
        matching,
        taylor,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing,
        mkt_clearing,
    ],
    name="HARK_HANK",
)

HANK_SAM_tax_rate_shock = create_model(
    [
        Jacobian_Dict,
        Jacobian_Dict_by_educ,
        fiscal_G,
        longbonds_price,
        ex_post_longbonds_rate,
        fiscal_rule_G,
        production,
        matching,
        taylor,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing,
        mkt_clearing,
    ],
    name="HARK_HANK",
)

HANK_SAM_lagged_taylor_rule = create_model(
    [
        Jacobian_Dict,
        Jacobian_Dict_by_educ,
        fiscal,
        longbonds_price,
        ex_post_longbonds_rate,
        fiscal_rule,
        production,
        matching,
        taylor_lagged,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing,
        mkt_clearing,
    ],
    name="HARK_HANK",
)

HANK_SAM_fixed_real_rate = create_model(
    [
        Jacobian_Dict,
        Jacobian_Dict_by_educ,
        fiscal_fixed_real_rate,
        fiscal_rule,
        production,
        matching,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing_fixed_real_rate,
        mkt_clearing,
    ],
    name="HARK_HANK",
)

HANK_SAM_fixed_real_rate_UI_extend_real = create_model(
    [
        Jacobian_Dict_UI_extend_real,
        Jacobian_Dict_by_educ,
        fiscal_fixed_real_rate,
        fiscal_rule,
        production,
        matching,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing_fixed_real_rate,
        mkt_clearing,
    ],
    name="HARK_HANK",
)

HANK_SAM_tax_cut_fixed_real_rate = create_model(
    [
        Jacobian_Dict,
        Jacobian_Dict_by_educ,
        fiscal_G_fixed_real_rate,
        fiscal_rule_G,
        production,
        matching,
        Phillips_Curve,
        marginal_cost,
        UJAC_dict,
        hiring_cost,
        wage_,
        vacancies,
        unemployment1,
        fisher_clearing_fixed_real_rate,
        mkt_clearing,
    ],
    name="HARK_HANK",
)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6: POLICY EXPERIMENTS AND ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════


def NPV(irf, length, discount_rate=None):
    """
    Compute Net Present Value of a time series.

    Args:
        irf: Time series array of impulse responses
        length: Number of periods to include in NPV calculation
        discount_rate: Gross discount rate (defaults to global R if not provided)

    Returns:
        float: Net present value of the series
    """
    if discount_rate is None:
        discount_rate = R

    NPV_val = 0
    for i in range(length):
        NPV_val += irf[i] / discount_rate**i
    return NPV_val


def run_ui_extension_experiments(param_overrides=None):
    """
    Run UI extension experiments under different monetary policies.

    This function simulates the effects of a 2-quarter unemployment insurance
    extension under three different monetary policy regimes:
    1. Standard Taylor rule
    2. Fixed nominal interest rate
    3. Fixed real interest rate

    The UI extension increases income replacement for unemployed individuals
    who have exhausted their regular benefits.

    Args:
        param_overrides: Dictionary of parameter overrides to apply

    Returns:
        tuple: Contains IRFs and steady state dictionaries for all three scenarios:
            (irfs_UI_extend, irfs_UI_extend_fixed_nominal_rate,
             irfs_UI_extension_fixed_real_rate, irf_UI_extend_realizations,
             SteadyState_Dict_UI_extend, shocks_UI_extension)
    """
    if param_overrides is None:
        param_overrides = {}

    # Create shock
    ui_length = param_overrides.get("UI_extension_length", UI_extension_length)
    dUI_extension = np.zeros(bigT)
    dUI_extension[:ui_length] = 0.2
    shocks_UI_extension = {"UI_extend": dUI_extension}

    # Set up steady state dictionary
    SteadyState_Dict_UI_extend = deepcopy(SteadyState_Dict)
    SteadyState_Dict_UI_extend["phi_b"] = param_overrides.get("phi_b", phi_b)
    SteadyState_Dict_UI_extend["phi_w"] = param_overrides.get(
        "real_wage_rigidity", real_wage_rigidity
    )
    SteadyState_Dict_UI_extend["rho_r"] = param_overrides.get("rho_r", rho_r)
    SteadyState_Dict_UI_extend["phi_y"] = param_overrides.get("phi_y", phi_y)
    SteadyState_Dict_UI_extend["phi_pi"] = param_overrides.get("phi_pi", phi_pi)
    SteadyState_Dict_UI_extend["kappa_p"] = param_overrides.get("kappa_p", kappa_p_ss)
    SteadyState_Dict_UI_extend["deficit_T"] = -1

    # Standard taylor rule
    unknowns = ["theta", "r_ante"]
    targets = ["asset_mkt", "fisher_resid"]

    irfs_UI_extend = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_extend, unknowns, targets, shocks_UI_extension
    )

    # Fixed nominal rate
    SteadyState_Dict_UI_extend_fixed_nominal_rate = deepcopy(SteadyState_Dict_UI_extend)
    SteadyState_Dict_UI_extend_fixed_nominal_rate["phi_pi"] = 0.0

    irfs_UI_extend_fixed_nominal_rate = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_extend_fixed_nominal_rate,
        unknowns,
        targets,
        shocks_UI_extension,
    )

    # Fixed real rate
    unknowns_fixed_real_rate = ["theta"]
    targets_fixed_real_rate = ["asset_mkt"]

    irfs_UI_extension_fixed_real_rate = HANK_SAM_fixed_real_rate.solve_impulse_linear(
        SteadyState_Dict_UI_extend,
        unknowns_fixed_real_rate,
        targets_fixed_real_rate,
        shocks_UI_extension,
    )

    # UI extend realizations
    irf_UI_extend_realizations = (
        HANK_SAM_fixed_real_rate_UI_extend_real.solve_impulse_linear(
            SteadyState_Dict_UI_extend,
            unknowns_fixed_real_rate,
            targets_fixed_real_rate,
            shocks_UI_extension,
        )
    )

    return (
        irfs_UI_extend,
        irfs_UI_extend_fixed_nominal_rate,
        irfs_UI_extension_fixed_real_rate,
        irf_UI_extend_realizations,
        SteadyState_Dict_UI_extend,
        shocks_UI_extension,
    )


def run_transfer_experiments(param_overrides=None):
    """
    Run transfer (stimulus check) experiments under different monetary policies.

    This function simulates the macroeconomic effects of one-time lump-sum
    transfers to all households (similar to COVID-19 stimulus checks) under:
    1. Standard Taylor rule
    2. Fixed nominal interest rate
    3. Fixed real interest rate
    4. Lagged Taylor rule response

    The transfer is calibrated as 5% of steady-state consumption, representing
    approximately $1,200 per person when scaled to US data.

    Args:
        param_overrides: Dictionary of parameter overrides to apply

    Returns:
        tuple: Contains IRFs and configuration for all monetary policy scenarios:
            (irfs_transfer, irfs_transfer_fixed_nominal_rate,
             irfs_transfer_fixed_real_rate, irfs_transfers_lagged_nominal_rate,
             SteadyState_Dict_transfer, shocks_transfers)
    """
    if param_overrides is None:
        param_overrides = {}

    # Create shock
    dtransfers = np.zeros(bigT)
    dtransfers[:stimulus_check_length] = C_ss * 0.05  # 5% of quarterly consumption
    shocks_transfers = {"transfers": dtransfers}

    # Set up steady state dictionary
    SteadyState_Dict_transfer = deepcopy(SteadyState_Dict)
    SteadyState_Dict_transfer["phi_b"] = param_overrides.get("phi_b", phi_b)
    SteadyState_Dict_transfer["phi_w"] = param_overrides.get(
        "real_wage_rigidity", real_wage_rigidity
    )
    SteadyState_Dict_transfer["rho_r"] = param_overrides.get("rho_r", rho_r)
    SteadyState_Dict_transfer["phi_y"] = param_overrides.get("phi_y", phi_y)
    SteadyState_Dict_transfer["phi_pi"] = param_overrides.get("phi_pi", phi_pi)
    SteadyState_Dict_transfer["kappa_p"] = param_overrides.get("kappa_p", kappa_p_ss)
    SteadyState_Dict_transfer["deficit_T"] = -1

    # Standard taylor rule
    unknowns = ["theta", "r_ante"]
    targets = ["asset_mkt", "fisher_resid"]

    irfs_transfer = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_transfer, unknowns, targets, shocks_transfers
    )

    # Fixed nominal rate
    SteadyState_Dict_UI_transfer_fixed_nominal_rate = deepcopy(
        SteadyState_Dict_transfer
    )
    SteadyState_Dict_UI_transfer_fixed_nominal_rate["phi_pi"] = 0.0

    irfs_transfer_fixed_nominal_rate = HANK_SAM.solve_impulse_linear(
        SteadyState_Dict_UI_transfer_fixed_nominal_rate,
        unknowns,
        targets,
        shocks_transfers,
    )

    # Fixed real rate
    unknowns_fixed_real_rate = ["theta"]
    targets_fixed_real_rate = ["asset_mkt"]

    irfs_transfer_fixed_real_rate = HANK_SAM_fixed_real_rate.solve_impulse_linear(
        SteadyState_Dict_transfer,
        unknowns_fixed_real_rate,
        targets_fixed_real_rate,
        shocks_transfers,
    )

    # Lagged taylor rule
    SteadyState_Dict_transfers_lagged_nominal_rate = deepcopy(SteadyState_Dict_transfer)
    monetary_policy_lag = 2
    SteadyState_Dict_transfers_lagged_nominal_rate["lag"] = monetary_policy_lag

    irfs_transfers_lagged_nominal_rate = (
        HANK_SAM_lagged_taylor_rule.solve_impulse_linear(
            SteadyState_Dict_transfers_lagged_nominal_rate,
            unknowns,
            targets,
            shocks_transfers,
        )
    )

    return (
        irfs_transfer,
        irfs_transfer_fixed_nominal_rate,
        irfs_transfer_fixed_real_rate,
        irfs_transfers_lagged_nominal_rate,
        SteadyState_Dict_transfer,
        shocks_transfers,
    )


def run_tax_cut_experiments(param_overrides=None):
    """
    Run tax cut experiments under different monetary policies.

    This function simulates temporary reductions in the labor income tax rate
    by 2 percentage points for 8 quarters (2 years). Government spending
    adjusts endogenously to satisfy the budget constraint.

    Experiments are run under:
    1. Standard Taylor rule
    2. Fixed nominal interest rate
    3. Fixed real interest rate

    Args:
        param_overrides: Dictionary of parameter overrides to apply

    Returns:
        tuple: Contains IRFs and configuration for all scenarios:
            (irfs_tau, irfs_tau_fixed_nominal_rate, irfs_tau_fixed_real_rate,
             SteadyState_Dict_tax_shock, shocks_tau)
    """
    if param_overrides is None:
        param_overrides = {}

    # Create shock
    tax_length = param_overrides.get("tax_cut_length", tax_cut_length)
    dtau = np.zeros(bigT)
    dtau[:tax_length] = -0.02  # 2 percentage point tax cut
    shocks_tau = {"tau": dtau}

    # Set up steady state dictionary
    SteadyState_Dict_tax_shock = deepcopy(SteadyState_Dict)
    SteadyState_Dict_tax_shock["phi_G"] = -param_overrides.get(
        "phi_b", phi_b
    )  # G adjusts instead of tau
    SteadyState_Dict_tax_shock["phi_w"] = param_overrides.get(
        "real_wage_rigidity", real_wage_rigidity
    )
    SteadyState_Dict_tax_shock["rho_r"] = param_overrides.get("rho_r", rho_r)
    SteadyState_Dict_tax_shock["phi_y"] = param_overrides.get("phi_y", phi_y)
    SteadyState_Dict_tax_shock["phi_pi"] = param_overrides.get("phi_pi", phi_pi)
    SteadyState_Dict_tax_shock["kappa_p"] = param_overrides.get("kappa_p", kappa_p_ss)
    SteadyState_Dict_tax_shock["deficit_T"] = -1

    # Standard taylor rule
    unknowns = ["theta", "r_ante"]
    targets = ["asset_mkt", "fisher_resid"]

    irfs_tau = HANK_SAM_tax_rate_shock.solve_impulse_linear(
        SteadyState_Dict_tax_shock, unknowns, targets, shocks_tau
    )

    # Fixed nominal rate
    SteadyState_Dict_tax_shock_fixed_rate = deepcopy(SteadyState_Dict_tax_shock)
    SteadyState_Dict_tax_shock_fixed_rate["phi_pi"] = 0.0

    irfs_tau_fixed_nominal_rate = HANK_SAM_tax_rate_shock.solve_impulse_linear(
        SteadyState_Dict_tax_shock_fixed_rate, unknowns, targets, shocks_tau
    )

    # Fixed real rate
    unknowns_fixed_real_rate = ["theta"]
    targets_fixed_real_rate = ["asset_mkt"]

    irfs_tau_fixed_real_rate = HANK_SAM_tax_cut_fixed_real_rate.solve_impulse_linear(
        SteadyState_Dict_tax_shock,
        unknowns_fixed_real_rate,
        targets_fixed_real_rate,
        shocks_tau,
    )

    return (
        irfs_tau,
        irfs_tau_fixed_nominal_rate,
        irfs_tau_fixed_real_rate,
        SteadyState_Dict_tax_shock,
        shocks_tau,
    )


def compute_fiscal_multipliers(horizon_length=20, **param_overrides):
    """
    Compute fiscal multipliers for all policies and monetary regimes.

    This function runs all three fiscal experiments (UI extensions, transfers,
    tax cuts) under different monetary policies and computes their cumulative
    fiscal multipliers over time.

    The fiscal multiplier is defined as:
        Multiplier(t) = NPV(ΔC, t) / NPV(Fiscal Cost, ∞)

    Where NPV is net present value and t is the horizon. This measures the
    cumulative consumption response per dollar of fiscal spending.

    Args:
        horizon_length: Number of quarters to compute multipliers (default=20)
        **param_overrides: Parameter overrides to apply to all experiments

    Returns:
        dict: Contains two sub-dictionaries:
            - 'multipliers': Arrays of multipliers by horizon for each policy/regime
            - 'irfs': Full impulse response functions for each experiment
    """
    # Run all experiments with parameter overrides
    (
        irfs_UI_extend,
        irfs_UI_extend_fixed_nominal_rate,
        irfs_UI_extension_fixed_real_rate,
        irf_UI_extend_realizations,
        _,
        _,
    ) = run_ui_extension_experiments(param_overrides)

    (
        irfs_transfer,
        irfs_transfer_fixed_nominal_rate,
        irfs_transfer_fixed_real_rate,
        irfs_transfers_lagged_nominal_rate,
        _,
        _,
    ) = run_transfer_experiments(param_overrides)

    (irfs_tau, irfs_tau_fixed_nominal_rate, irfs_tau_fixed_real_rate, _, _) = (
        run_tax_cut_experiments(param_overrides)
    )

    # Initialize multiplier arrays
    multipliers_transfers = np.zeros(horizon_length)
    multipliers_UI_extend = np.zeros(horizon_length)
    multipliers_tax_cut = np.zeros(horizon_length)

    multipliers_transfers_fixed_nominal_rate = np.zeros(horizon_length)
    multipliers_UI_extensions_fixed_nominal_rate = np.zeros(horizon_length)
    multipliers_tax_cut_fixed_nominal_rate = np.zeros(horizon_length)

    multipliers_transfers_fixed_real_rate = np.zeros(horizon_length)
    multipliers_UI_extensions_fixed_real_rate = np.zeros(horizon_length)
    multipliers_tax_cut_fixed_real_rate = np.zeros(horizon_length)

    # Compute multipliers at each horizon
    # Multiplier = Cumulative consumption response / Total fiscal cost
    for i in range(horizon_length):
        # Fixed nominal rate
        multipliers_transfers_fixed_nominal_rate[i] = NPV(
            irfs_transfer_fixed_nominal_rate["C"], i + 1
        ) / NPV(irfs_transfer_fixed_nominal_rate["transfers"], 300)
        multipliers_UI_extensions_fixed_nominal_rate[i] = NPV(
            irfs_UI_extend_fixed_nominal_rate["C"], i + 1
        ) / NPV(irfs_UI_extend_fixed_nominal_rate["UI_extension_cost"], 300)
        multipliers_tax_cut_fixed_nominal_rate[i] = -NPV(
            irfs_tau_fixed_nominal_rate["C"], i + 1
        ) / NPV(
            irfs_tau_fixed_nominal_rate["tax_cost"], 300
        )  # Negative because tax cut reduces revenue

        # Standard taylor rule
        multipliers_transfers[i] = NPV(irfs_transfer["C"], i + 1) / NPV(
            irfs_transfer["transfers"], 300
        )
        multipliers_UI_extend[i] = NPV(irfs_UI_extend["C"], i + 1) / NPV(
            irfs_UI_extend["UI_extension_cost"], 300
        )
        multipliers_tax_cut[i] = -NPV(irfs_tau["C"], i + 1) / NPV(
            irfs_tau["tax_cost"], 300
        )

        # Fixed real rate
        multipliers_transfers_fixed_real_rate[i] = NPV(
            irfs_transfer_fixed_real_rate["C"], i + 1
        ) / NPV(irfs_transfer_fixed_real_rate["transfers"], 300)
        multipliers_UI_extensions_fixed_real_rate[i] = NPV(
            irfs_UI_extension_fixed_real_rate["C"], i + 1
        ) / NPV(irfs_UI_extension_fixed_real_rate["UI_extension_cost"], 300)
        multipliers_tax_cut_fixed_real_rate[i] = -NPV(
            irfs_tau_fixed_real_rate["C"], i + 1
        ) / NPV(irfs_tau_fixed_real_rate["tax_cost"], 300)

    # Print summary multipliers (output multipliers at infinite horizon)
    print("FISCAL MULTIPLIERS SUMMARY")
    print("=" * 60)
    print(
        f"UI Extension (active taylor rule): {NPV(irfs_UI_extend['Y'], bigT) / NPV(irfs_UI_extend['UI_extension_cost'], bigT):.3f}"
    )
    print(
        f"UI Extension (fixed nominal rate): {NPV(irfs_UI_extend_fixed_nominal_rate['Y'], bigT) / NPV(irfs_UI_extend_fixed_nominal_rate['UI_extension_cost'], bigT):.3f}"
    )
    print(
        f"UI Extension (fixed real rate): {NPV(irfs_UI_extension_fixed_real_rate['Y'], bigT) / NPV(irfs_UI_extension_fixed_real_rate['UI_extension_cost'], bigT):.3f}"
    )
    print(
        f"Transfers (active taylor rule): {NPV(irfs_transfer['Y'], bigT) / NPV(irfs_transfer['transfers'], bigT):.3f}"
    )
    print(
        f"Transfers (fixed nominal rate): {NPV(irfs_transfer_fixed_nominal_rate['Y'], bigT) / NPV(irfs_transfer_fixed_nominal_rate['transfers'], bigT):.3f}"
    )
    print(
        f"Transfers (fixed real rate): {NPV(irfs_transfer_fixed_real_rate['Y'], bigT) / NPV(irfs_transfer_fixed_real_rate['transfers'], bigT):.3f}"
    )
    print(
        f"Tax cut (active taylor rule): {NPV(irfs_tau['Y'], bigT) / NPV(irfs_tau['tax_cost'], bigT):.3f}"
    )
    print(
        f"Tax cut (fixed nominal rate): {NPV(irfs_tau_fixed_nominal_rate['Y'], bigT) / NPV(irfs_tau_fixed_nominal_rate['tax_cost'], bigT):.3f}"
    )
    print(
        f"Tax cut (fixed real rate): {NPV(irfs_tau_fixed_real_rate['Y'], bigT) / NPV(irfs_tau_fixed_real_rate['tax_cost'], bigT):.3f}"
    )
    print("=" * 60)

    return {
        "multipliers": {
            "transfers": multipliers_transfers,
            "UI_extend": multipliers_UI_extend,
            "tax_cut": multipliers_tax_cut,
            "transfers_fixed_nominal": multipliers_transfers_fixed_nominal_rate,
            "UI_extend_fixed_nominal": multipliers_UI_extensions_fixed_nominal_rate,
            "tax_cut_fixed_nominal": multipliers_tax_cut_fixed_nominal_rate,
            "transfers_fixed_real": multipliers_transfers_fixed_real_rate,
            "UI_extend_fixed_real": multipliers_UI_extensions_fixed_real_rate,
            "tax_cut_fixed_real": multipliers_tax_cut_fixed_real_rate,
        },
        "irfs": {
            "UI_extend": irfs_UI_extend,
            "UI_extend_fixed_nominal": irfs_UI_extend_fixed_nominal_rate,
            "UI_extend_fixed_real": irfs_UI_extension_fixed_real_rate,
            "transfer": irfs_transfer,
            "transfer_fixed_nominal": irfs_transfer_fixed_nominal_rate,
            "transfer_fixed_real": irfs_transfer_fixed_real_rate,
            "tau": irfs_tau,
            "tau_fixed_nominal": irfs_tau_fixed_nominal_rate,
            "tau_fixed_real": irfs_tau_fixed_real_rate,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7: PLOTTING FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════


def plot_single_multiplier_panel(
    ax,
    multipliers_standard,
    multipliers_fixed_nominal,
    multipliers_fixed_real,
    title,
    show_legend=False,
    fontsize=10,
):
    """
    Plot fiscal multipliers for one policy under different monetary regimes.

    This granular function plots on a provided axis rather than creating its own figure,
    giving the caller complete control over layout and figure management.

    Args:
        ax: Matplotlib axis object to plot on
        multipliers_standard: Multipliers under standard Taylor rule
        multipliers_fixed_nominal: Multipliers under fixed nominal rate
        multipliers_fixed_real: Multipliers under fixed real rate
        title: Panel title
        show_legend: Whether to show legend on this panel
        fontsize: Base font size for scaling
    """
    # Colors for different monetary regimes
    colors = {
        "standard": "#1f77b4",  # Default blue
        "nominal": "#ff7f0e",  # Orange
        "real": "#d62728",  # Red
    }

    horizon_length = min(20, len(multipliers_standard))
    width = 2
    label_size = max(6, int(fontsize * 0.8))
    legend_size = max(8, int(fontsize * 1.0))
    ticksize = max(6, int(fontsize * 0.8))

    x_axis = np.arange(horizon_length) + 1

    # Plot the three monetary policy scenarios
    ax.plot(
        x_axis,
        multipliers_standard[:horizon_length],
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    ax.plot(
        x_axis,
        multipliers_fixed_nominal[:horizon_length],
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    ax.plot(
        x_axis,
        multipliers_fixed_real[:horizon_length],
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )

    # Zero line
    ax.axhline(y=0, color="black", linewidth=0.8, alpha=0.7)

    # Formatting with proper axis labels
    ax.set_title(title, pad=8)
    ax.tick_params(axis="both")
    ax.set_ylabel("Consumption Multiplier")
    ax.set_xlabel("Time (Quarters)")
    ax.locator_params(axis="both", nbins=6)
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.set_xlim(0.5, 12.5)  # Focus on first 3 years

    if show_legend:
        ax.legend(framealpha=0.9)


def plot_single_consumption_panel(
    ax,
    irf_standard,
    irf_fixed_nominal,
    irf_fixed_real,
    title,
    show_legend=False,
    fontsize=10,
):
    """
    Plot consumption IRFs for one policy under different monetary regimes.

    Args:
        ax: Matplotlib axis object to plot on
        irf_standard: IRF dict under standard Taylor rule
        irf_fixed_nominal: IRF dict under fixed nominal rate
        irf_fixed_real: IRF dict under fixed real rate
        title: Panel title
        show_legend: Whether to show legend on this panel
        fontsize: Base font size for scaling
    """
    # Colors for different monetary regimes (same as multipliers)
    colors = {
        "standard": "#1f77b4",  # Default blue
        "nominal": "#ff7f0e",  # Orange
        "real": "#d62728",  # Red
    }

    Length = 12  # 3 years
    width = 2
    label_size = max(6, int(fontsize * 0.8))
    legend_size = max(8, int(fontsize * 1.0))
    ticksize = max(6, int(fontsize * 0.8))

    x_axis = np.arange(Length)

    # Plot consumption responses as percent deviations
    ax.plot(
        x_axis,
        100 * irf_standard["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    ax.plot(
        x_axis,
        100 * irf_fixed_nominal["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    ax.plot(
        x_axis,
        100 * irf_fixed_real["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )

    # Zero line
    ax.axhline(y=0, color="black", linewidth=0.8, alpha=0.7)

    # Formatting with proper axis labels
    ax.set_title(title, pad=8)
    ax.tick_params(axis="both")
    ax.set_ylabel("Consumption Response (%)")
    ax.set_xlabel("Time (Quarters)")
    ax.locator_params(axis="both", nbins=6)
    ax.grid(alpha=0.3, linewidth=0.5)

    if show_legend:
        ax.legend(loc="best", framealpha=0.9)


def create_dashboard_figure(multipliers, irfs, figsize=(12, 8), fontsize=10):
    """
    Create a unified academic-quality figure for the dashboard.

    This function creates a single matplotlib figure with all panels arranged
    in a 2x3 grid, giving the dashboard complete control over layout.

    Args:
        multipliers: Dictionary of multiplier arrays
        irfs: Dictionary of IRF dictionaries
        figsize: Overall figure size
        fontsize: Base font size

    Returns:
        fig: Matplotlib figure object ready for display
    """
    # Create figure with 2 rows, 3 columns
    fig, axes = plt.subplots(2, 3, figsize=figsize, sharey="row")

    # Policy names for titles
    policies = ["Stimulus Check", "UI Extension", "Tax Cut"]

    # Row 1: Fiscal Multipliers
    for i, policy in enumerate(["transfers", "UI_extend", "tax_cut"]):
        plot_single_multiplier_panel(
            axes[0, i],
            multipliers[policy],
            multipliers[f"{policy}_fixed_nominal"],
            multipliers[f"{policy}_fixed_real"],
            policies[i],
            show_legend=(i == 0),  # Only show legend on first panel
            fontsize=fontsize,
        )

    # Row 2: Consumption IRFs
    irf_mapping = ["transfer", "UI_extend", "tau"]
    for i, policy in enumerate(irf_mapping):
        plot_single_consumption_panel(
            axes[1, i],
            irfs[policy],
            irfs[f"{policy}_fixed_nominal"],
            irfs[f"{policy}_fixed_real"],
            policies[i],
            show_legend=(i == 0),  # Only show legend on first panel
            fontsize=fontsize,
        )

    # Add row labels
    axes[0, 0].text(
        -0.15,
        0.5,
        "Fiscal Multipliers",
        transform=axes[0, 0].transAxes,
        rotation=90,
        va="center",
        ha="center",
        fontsize=fontsize + 1,
        weight="bold",
    )
    axes[1, 0].text(
        -0.15,
        0.5,
        "Consumption Response",
        transform=axes[1, 0].transAxes,
        rotation=90,
        va="center",
        ha="center",
        fontsize=fontsize + 1,
        weight="bold",
    )

    # Adjust layout for academic presentation
    plt.tight_layout(pad=2.0, rect=[0.03, 0.03, 0.97, 0.97])

    return fig


def plot_multipliers_three_experiments(
    multipliers_transfers,
    multipliers_transfers_fixed_nominal_rate,
    multipliers_transfers_fixed_real_rate,
    multipliers_UI_extend,
    multipliers_UI_extensions_fixed_nominal_rate,
    multipliers_UI_extensions_fixed_real_rate,
    multipliers_tax_cut,
    multipliers_tax_cut_fixed_nominal_rate,
    multipliers_tax_cut_fixed_real_rate,
    fig_and_axes=None,
):
    """
    Plot fiscal multipliers for three experiments under different monetary policies.

    This function can either create its own figure or draw on a provided canvas,
    giving the caller complete control over figure layout and sizing.

    Args:
        multipliers_* : Arrays of multiplier values for each policy/regime
        fig_and_axes: Optional tuple of (fig, axes) to draw on. If None, creates new figure.

    Returns:
        fig: The matplotlib figure object (for dashboard control)
    """
    import matplotlib.pyplot as plt

    # Dashboard control: use provided figure/axes or create new
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
        show_figure = False  # Dashboard will handle display
    else:
        fig, axs = plt.subplots(1, 3, figsize=(12, 4))
        show_figure = True  # Standalone mode

    # Colors and styling
    colors = {
        "standard": "#1f77b4",  # Blue
        "nominal": "#ff7f0e",  # Orange
        "real": "#d62728",  # Red
    }

    horizon_length = min(20, len(multipliers_transfers))
    width = 2
    fontsize = 12  # Increased from 10
    label_size = 14  # Increased from 8
    legend_size = 10
    ticksize = 10  # Increased from 8

    x_axis = np.arange(horizon_length) + 1

    # Stimulus Check (transfers) - Left panel
    axs[0].plot(
        x_axis,
        multipliers_transfers[:horizon_length],
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[0].plot(
        x_axis,
        multipliers_transfers_fixed_nominal_rate[:horizon_length],
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[0].plot(
        x_axis,
        multipliers_transfers_fixed_real_rate[:horizon_length],
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[0].set_title("Stimulus Check", fontsize=fontsize)
    axs[0].legend(prop={"size": legend_size}, loc="upper left", framealpha=0.0)

    # UI Extension - Middle panel
    axs[1].plot(
        x_axis,
        multipliers_UI_extend[:horizon_length],
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[1].plot(
        x_axis,
        multipliers_UI_extensions_fixed_nominal_rate[:horizon_length],
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[1].plot(
        x_axis,
        multipliers_UI_extensions_fixed_real_rate[:horizon_length],
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[1].set_title("UI Extension", fontsize=fontsize)

    # Tax Cut - Right panel
    axs[2].plot(
        x_axis,
        multipliers_tax_cut[:horizon_length],
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[2].plot(
        x_axis,
        multipliers_tax_cut_fixed_nominal_rate[:horizon_length],
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[2].plot(
        x_axis,
        multipliers_tax_cut_fixed_real_rate[:horizon_length],
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[2].set_title("Tax Cut", fontsize=fontsize)

    # Format all panels with proper axis labels
    for i in range(3):
        axs[i].axhline(y=0, color="black", linewidth=0.8, alpha=0.7)
        axs[i].tick_params(axis="both", labelsize=ticksize)
        axs[i].set_ylabel("Consumption Multiplier", fontsize=label_size, labelpad=10)  # Added labelpad
        
        axs[i].set_xlabel("Time (Quarters)", fontsize=label_size, labelpad=10)  # Added labelpad
        #axs[i].set_title("Consumption Multiplier", fontsize=fontsize, pad=10)  # Added pad
        axs[i].locator_params(axis="both", nbins=6)
        axs[i].grid(alpha=0.3, linewidth=0.5)
        axs[i].set_xlim(0.5, 12.5)

    # Only show if standalone (not controlled by dashboard)
    if show_figure:
        fig.tight_layout(pad=1.0)
        plt.show()

    return fig


def plot_consumption_irfs_three_experiments(
    irf_UI1,
    irf_UI2,
    irf_UI3,
    irf_SC1,
    irf_SC2,
    irf_SC3,
    irf_TC1,
    irf_TC2,
    irf_TC3,
    fig_and_axes=None,
):
    """
    Plot consumption IRFs for three experiments under different monetary policies.

    This function can either create its own figure or draw on a provided canvas,
    giving the caller complete control over figure layout and sizing.

    Args:
        irf_*: IRF dictionaries for each policy/regime combination
        fig_and_axes: Optional tuple of (fig, axes) to draw on. If None, creates new figure.

    Returns:
        fig: The matplotlib figure object (for dashboard control)
    """
    import matplotlib.pyplot as plt

    # Dashboard control: use provided figure/axes or create new
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
        show_figure = False  # Dashboard will handle display
    else:
        fig, axs = plt.subplots(1, 3, figsize=(12, 4))
        show_figure = True  # Standalone mode

    # Colors and styling (consistent with multipliers)
    colors = {
        "standard": "#1f77b4",  # Blue
        "nominal": "#ff7f0e",  # Orange
        "real": "#d62728",  # Red
    }

    Length = 12  # 3 years
    width = 2
    fontsize = 12  # Increased from 10
    label_size = 16  # Increased from 8
    legend_size = 10
    ticksize = 10  # Increased from 8

    x_axis = np.arange(Length)

    # Stimulus Check (left panel)
    axs[0].plot(
        x_axis,
        100 * irf_SC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[0].plot(
        x_axis,
        100 * irf_SC2["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[0].plot(
        x_axis,
        100 * irf_SC3["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[0].set_title("Stimulus Check", fontsize=fontsize)
    axs[0].legend(prop={"size": legend_size}, loc="best", framealpha=0.0)

    # UI Extension (middle panel)
    axs[1].plot(
        x_axis,
        100 * irf_UI1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[1].plot(
        x_axis,
        100 * irf_UI2["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[1].plot(
        x_axis,
        100 * irf_UI3["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[1].set_title("UI Extension", fontsize=fontsize)

    # Tax Cut (right panel)
    axs[2].plot(
        x_axis,
        100 * irf_TC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
        color=colors["standard"],
    )
    axs[2].plot(
        x_axis,
        100 * irf_TC2["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Nominal Rate",
        linestyle="--",
        color=colors["nominal"],
    )
    axs[2].plot(
        x_axis,
        100 * irf_TC3["C"][:Length] / C_ss,
        linewidth=width,
        label="Fixed Real Rate",
        linestyle=":",
        color=colors["real"],
    )
    axs[2].set_title("Tax Cut", fontsize=fontsize)

    # Format all panels with proper axis labels
    for i in range(3):
        axs[i].axhline(y=0, color="black", linewidth=0.8, alpha=0.7)
        axs[i].tick_params(axis="both", labelsize=ticksize)
        axs[i].set_ylabel("% Change in Consumption", fontsize=label_size, labelpad=10)
        axs[i].set_xlabel("Time (Quarters)", fontsize=label_size, labelpad=10)
        axs[i].locator_params(axis="both", nbins=6)
        axs[i].grid(alpha=0.3, linewidth=0.5)
        axs[i].set_xlim(0.5, 12.5)

    # Only show if standalone (not controlled by dashboard)
    if show_figure:
        fig.tight_layout(pad=1.0)
        plt.show()

    return fig


def plot_multipliers_across_horizon():
    """
    Plot fiscal multipliers across time horizon under standard Taylor rule.

    This function computes and plots the cumulative consumption multipliers
    for all three fiscal policies (transfers, UI extensions, tax cuts) over
    a 20-quarter horizon under the standard Taylor rule. Shows how multipliers
    evolve from impact to long-run values.
    """
    # Compute multipliers for all experiments
    results = compute_fiscal_multipliers()
    multipliers = results["multipliers"]

    # Plot multiplier paths
    plt.plot(
        np.arange(20) + 1,
        multipliers["transfers"],
        label="Stimulus Check",
        color="green",
    )
    plt.plot(
        np.arange(20) + 1,
        multipliers["UI_extend"],
        label="UI extensions",
        color="blue",
    )
    plt.plot(
        np.arange(20) + 1,
        multipliers["tax_cut"],
        label="Tax cut",
        color="red",
    )
    plt.legend(loc="lower right")
    plt.ylabel("C multipliers")
    plt.xlabel("quarters $t$")
    plt.xlim(0.5, 12.5)
    plt.show()


def plot_consumption_irfs_three(irf_SC1, irf_UI1, irf_TC1):
    """
    Plot consumption IRFs for three fiscal policies under standard Taylor rule.

    Creates a 3-panel figure showing the consumption impulse responses to
    stimulus checks, UI extensions, and tax cuts. All responses are shown
    as percentage deviations from steady state.

    Args:
        irf_SC1: IRF dictionary for stimulus check experiment
        irf_UI1: IRF dictionary for UI extension experiment
        irf_TC1: IRF dictionary for tax cut experiment
    """
    Length = 12  # Plot first 3 years
    fontsize = 10
    width = 2
    label_size = 8
    legend_size = 8
    ticksize = 8
    fig, axs = plt.subplots(
        1, 3, figsize=(12, 4)
    )  # Responsive size for dashboard containers

    # Set y-axis limits based on largest response
    y_max1 = max(100 * irf_TC1["C"][:Length] / C_ss) * 1.05
    y_max2 = max(100 * irf_SC1["C"][:Length] / C_ss) * 1.05
    y_max = max([y_max1, y_max2])
    for i in range(3):
        axs[i].set_ylim(-0.1, y_max)

    # UI Extension (middle panel)
    axs[1].plot(
        100 * irf_UI1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
    )
    axs[1].set_title("UI Extension", fontdict={"fontsize": fontsize})

    # Stimulus Check (left panel)
    axs[0].plot(
        100 * irf_SC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
    )
    axs[0].set_title("Stimulus Check", fontdict={"fontsize": fontsize})
    axs[0].legend(prop={"size": legend_size})

    # Tax Cut (right panel)
    axs[2].plot(
        100 * irf_TC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Standard Taylor Rule",
    )
    axs[2].set_title("Tax Cut", fontdict={"fontsize": fontsize})

    # Format all panels
    for i in range(3):
        axs[i].plot(np.zeros(Length), "k")  # Zero line
        axs[i].tick_params(axis="both", labelsize=ticksize)
        axs[i].set_ylabel("% consumption deviation", fontsize=label_size)
        axs[i].set_xlabel("Quarters", fontsize=label_size)
        axs[i].locator_params(axis="both", nbins=7)
        axs[i].grid(alpha=0.3)
    fig.tight_layout(pad=0.3)  # Minimal padding for maximum space usage
    plt.show()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8: MAIN EXECUTION
# ═════════════════════════════════════════════════════════════════════════════
# When run as a script, this code:
# 1. Runs all fiscal policy experiments under different monetary regimes
# 2. Computes fiscal multipliers and prints summary statistics
# 3. Creates four publication-quality figures:
#    - Figure 1: Multipliers by policy and monetary regime over time
#    - Figure 2: Consumption IRFs comparing monetary regimes
#    - Figure 3: Consumption IRFs under baseline Taylor rule
#    - Figure 4: Multiplier evolution under baseline Taylor rule
#
# Key findings:
# - UI extensions have highest multipliers due to targeting
# - Fixed nominal/real rates amplify fiscal effects ~40-50%
# - Tax cuts have lowest multipliers due to savings leakage
# - Multipliers converge to long-run values after ~3 years

if __name__ == "__main__":
    # Run all policy experiments and compute fiscal multipliers
    # This will print a summary table of output multipliers
    results = compute_fiscal_multipliers()

    # Extract results for plotting
    multipliers = results["multipliers"]
    irfs = results["irfs"]

    # Figure 1: Compare multipliers across policies and monetary regimes
    # Shows how monetary accommodation affects fiscal effectiveness
    plot_multipliers_three_experiments(
        multipliers["transfers"],
        multipliers["transfers_fixed_nominal"],
        multipliers["transfers_fixed_real"],
        multipliers["UI_extend"],
        multipliers["UI_extend_fixed_nominal"],
        multipliers["UI_extend_fixed_real"],
        multipliers["tax_cut"],
        multipliers["tax_cut_fixed_nominal"],
        multipliers["tax_cut_fixed_real"],
    )

    # Figure 2: Consumption impulse responses for all combinations
    # Demonstrates both level and persistence effects
    plot_consumption_irfs_three_experiments(
        irfs["UI_extend"],
        irfs["UI_extend_fixed_nominal"],
        irfs["UI_extend_fixed_real"],
        irfs["transfer"],
        irfs["transfer_fixed_nominal"],
        irfs["transfer_fixed_real"],
        irfs["tau"],
        irfs["tau_fixed_nominal"],
        irfs["tau_fixed_real"],
    )

    # Figure 3: Baseline consumption responses under standard Taylor rule
    plot_consumption_irfs_three(irfs["transfer"], irfs["UI_extend"], irfs["tau"])

    # Figure 4: Evolution of multipliers over time (standard Taylor rule only)
    plot_multipliers_across_horizon()
