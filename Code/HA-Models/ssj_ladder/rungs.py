"""Rung registry: config, env, gates, thresholds — data, not code.

The A0 specification is pinned to the letter (plan §2): an independent rebuild from a
looser spec flipped a refinement-gate verdict on a legitimate grid guess, so nothing is
left to guesswork. Thresholds sit at ~1.5x their measured basis; each carries it inline.
"""

# ---- the A0 model (mirrors of hh_setup / ge.py literals; see plan §2) ----
A0_MODEL = dict(
    beta=0.9875150563091549,   # college atom 3 — safely inside the GIC at Gamma=1
    R=1.01,
    crra=2.0,
    wage_ss=1.0,
    tau_ss=0.3,
    EU=0.0306834,              # employed -> unemployed   (hh_setup EU_prob)
    jf=2.0 / 3.0,              # unemployed -> employed   (hh_setup job_find)
    # employed income = wage*(1-tau) = 0.7 ; unemployed = with-UI level 0.49
    livprb=1.0, gamma=1.0,     # the mortality-off / growth-off floor
    T=40,
    a_max=20.0,                # the pinned reference grid top (both engines)
    a_min_step4=1e-4, m_fac=3, # step4 dist grid family: make_grid_exp_mult
)

A0 = dict(
    name="A0",
    title="external parity: minimal household, step4 vs sequence_jacobian",
    model=A0_MODEL,
    inputs=("transfers", "w", "tau", "r"),
    income_inputs=("transfers", "w", "tau"),
    # 3-point refinement ladder (plan v2: the 2-point form flips sign with the grid choice)
    ladder=(50, 150, 450),
    env=dict(
        HAFISCAL_HANK_BIGT="40",              # read at hh_setup IMPORT time
        HAFISCAL_STEP4_FAST_BACKWARD="0",     # certified python reference
        HAFISCAL_STEP4_FAST_TRANMAT="0",      # second compiled path, default ON
        HAFISCAL_STEP4_ZEROTH_COLUMN="unanticipated",
        HAFISCAL_STEP4_FAKENEWS_INDEX="legacy",
        HAFISCAL_EARNINGS_PHASE_HAZARD="0",
        HAFISCAL_QUIET_BETADISTR="1",
        # The Phase-A cells are SPEC-PINNED at the published newborn
        # convention (the 2026-09-02 income-default flip is a production
        # improvement; A7's faithful arm overrides per-cell).
        HAFISCAL_HANK_NEWBORN_M="unit",
    ),
    thresholds=dict(
        # S tier (per engine, pinned config; measured step4 2.5e-11 @50 / ssj 3.9e-13)
        s_off_delivery_rel=1e-10,      # off-delivery |resid| / max|J| per column
        s_cash_spread_rel=1e-6,        # cash constancy across s>=1
        s_announce=1e-10,              # |resid[0, s>=1]| (measured: 0.0 / 3.9e-13)
        s_pv=1e-8,                     # PV identity (measured <=4.2e-10)
        s_col0_income_rel=1e-6,        # column-0 cash == interior cash (income inputs)
        s_col0_r_rel=1e-3,             # r column-0 vs interior, per engine (measured 9.5e-5)
        s_terminal_min=1e-6,           # |J_C[T-1,0]| populated (measured ~5e-3)
        # X tier (cross-engine at the pinned grids)
        x_cash_rel=1e-3,               # income inputs only (measured ~1.5e-11)
        x_r_own_ss_rel=1e-3,           # |cash_r / own A_ss - 1| per engine (measured <=9.5e-5)
        x_relgap_50=8e-2,              # Frobenius on J_C (measured 2.1-5.9e-2)
        x_relgap_150=4.5e-2,           # 1.5x the measured 3.00e-2 max (w, pinned A_MAX=20 run
                                       # 2026-09-01); v1's 1e-2 was a 450-pt number
        # R tier (the doctrine's core): last ratio + overall shrinkage
        r_last_ratio=0.5,              # gap(450)/gap(150)  (measured 0.11-0.15)
        r_total_shrink=5.0,            # gap(50)/gap(450)   (measured ~14x)
    ),
)

A1_MODEL = dict(A0_MODEL)
A1_MODEL.update(
    ue_rr=0.7,     # with-UI replacement (U1, U2), on the net wage
    nb_rr=0.5,     # exhausted replacement (U3..U5)
)

A1 = dict(
    name="A1",
    title="the real 6-state SAM chain: per-state income, UI instruments, eta",
    model=A1_MODEL,
    builder="a1",
    inputs=("transfers", "w", "tau", "r", "UI_extend", "UI_rr"),
    income_inputs=("transfers", "w", "tau", "UI_extend", "UI_rr"),
    ladder=(50, 150, 450),
    env=dict(A0["env"]),
    # Pinned 2026-09-01 from the measure pass (verdict_A1_20260901-222542):
    # the UI columns carry ~30-300x smaller cash than transfers, so the
    # step4 engine's ~2e-10 absolute budget noise lands at 2.2e-10 of maxJ
    # (measured; transfers 8e-12) -> off-delivery tier 3.3e-10 = 1.5x.
    # UI_rr's n50 relgap is constraint-region grid coarseness (0.417 @50 ->
    # 0.0205 @150, 20x per step; the R tier owns convergence) -> the n50
    # cross-engine tier is 0.63 = 1.5x measured, and @150 keeps A0's 4.5e-2.
    thresholds={**A0["thresholds"],
                "s_off_delivery_rel": 3.3e-10,
                "x_relgap_50": 0.63},
    # eta: gated by the chain-implied dY path (budget identity), step4 side
    # (measured 6.4e-10 @50; pinned 1e-9). The SSJ twin's dPi Jacobian is
    # probed and recorded (v1.0.0: AttributeError — not natively shockable).
    eta_gate=dict(provisional_rel=1e-9),
)

A2_MODEL = dict(A1_MODEL)
A2_MODEL.update(
    gamma=0.99,   # Gamma < 1: keeps the (W) newborn mass 1-LG > 0 at
                  # LivPrb=1 (wall dodged, mechanism exercised; see the
                  # 2026-09-02 derivation note)
    beta=0.95,    # GIC: at A1's beta=0.9874 the GPF (betaR)^(1/sigma)/Gamma
                  # = 1.0088 > 1 -- no ergodic dstn at Gamma=0.99. 0.95 gives
                  # GPF = 0.9897 < 1 (growth-impatient, well-posed).
)

A2 = dict(
    name="A2",
    title="uniform growth at LivPrb=1: the derived (rho, cash) signatures",
    model=A2_MODEL,
    builder="a2",
    inputs=("transfers", "w", "tau", "r", "UI_extend", "UI_rr"),
    income_inputs=("transfers", "w", "tau", "UI_extend", "UI_rr"),
    ladder=(50, 150),          # discrimination rung: the R tier is A1's job
    env=dict(A0["env"]),
    # Pinned from the A2 measure pass (verdict_A2_20260901-2240xx): the
    # ll-Gamma-weighted builder's absolute noise on the tiny-cash UI columns
    # needs 1.1e-8 (measured 7.2e-9 @50 / 9.96e-10 @150 — coarser grids
    # carry more arithmetic noise on a 3e-3-cash column); the terminal gate is scoped to the
    # big-cash inputs at tier 1e-7 (r measured 4.0-4.1e-7; the UI columns'
    # terminals straddle the engines' noise floors and are diagnostics).
    thresholds={**A1["thresholds"],
                "s_off_delivery_rel": 1.1e-8,
                "s_terminal_min": 1e-7},
    terminal_inputs=("transfers", "w", "tau", "r"),
    # The derived cross-convention gates (2026-09-02 note, (W) verified in
    # ConsMarkovModel ~1824): step4 cash = LG x the Gamma=1 cash; twin cash
    # = the Gamma=1 cash; ratio step4/twin = LG = Gamma at LivPrb=1.
    a2_gate=dict(cash_ratio_rel=1e-3),
)

A3_MODEL = dict(A1_MODEL)
A3_MODEL.update(
    psi_std=0.05477225575051661,    # sqrt(0.003), the production PermShkStd
    theta_std=0.34641016151377546,  # sqrt(0.12), the production TranShkStd
    shk_count=7,
    beta=0.95,   # NOT A1's 0.9874: with production psi/theta risk the
                 # buffer-stock target wealth at near-GIC beta explodes past
                 # a_max=20 (probe 2026-09-02: A_ss=10.7, top-of-grid mass,
                 # the SS flow identity itself off by 10% of C -- truncation
                 # destroys resources). At 0.95 the SS identity is 1.6e-12
                 # and A_ss=0.46, interior. The psi/neutral-measure machinery
                 # was never at fault; the first A3 spec violated the cell's
                 # own impatience requirement (the A2 lesson, re-learned with
                 # risk instead of growth).
)

A3 = dict(
    name="A3",
    title="psi/theta risk on the 6-state chain (S-only; the plan's fallback scope)",
    model=A3_MODEL,
    builder="a3",
    inputs=("transfers", "w", "tau", "r", "UI_extend", "UI_rr"),
    income_inputs=("transfers", "w", "tau", "UI_extend", "UI_rr"),
    ladder=(50, 150),
    env=dict(A0["env"]),
    # Pinned 2026-09-02 from the beta=0.95 measure pass: the 49-atom shock
    # arithmetic on the tiny-cash UI columns needs 1.7e-9 = 1.5x the measured
    # 1.12e-9 (A1's 1-atom tier was 3.3e-10; same noise-per-cash family).
    thresholds={**A1["thresholds"], "s_off_delivery_rel": 1.7e-9},
    terminal_inputs=("transfers", "w", "tau", "r"),
    eta_gate=dict(provisional_rel=1e-9),  # measured 5.5e-10
    s_only=True,   # no SSJ twin: sj has no Harmenberg psi machinery — the
                   # plan's own fallback ("drop to S-only and cross the wall
                   # here"); the (W)-convention operator is certified at A2
)

A3T_MODEL = dict(A3_MODEL)
A3T_MODEL.update(psi_std=1e-12)   # theta-only probe: Harmenberg ~ trivial

A3T = dict(A3, name="A3T", model=A3T_MODEL,
           title="A3 probe: theta-only risk (is the defect the psi path?)")

A4_MODEL = dict(A3_MODEL)
A4_MODEL.update(livprb=0.99375)   # mortality ON -- the SSJ wall (the plan's
#                                   A4). Newborn complement 1-LG = 0.00625 > 0
#                                   at Gamma=1; beta stays A3's safe 0.95.

A4 = dict(
    name="A4",
    title="mortality on: rho = R*LivPrb, kappa = L*Gamma, the wall crossed S-only",
    model=A4_MODEL,
    builder="a3",          # the A3 cell builder is livprb-generic
    s_only=True,           # by design: sequence_jacobian has no mortality
    inputs=("transfers", "w", "tau", "r", "UI_extend", "UI_rr"),
    income_inputs=("transfers", "w", "tau", "UI_extend", "UI_rr"),
    ladder=(50, 150),
    env=dict(A0["env"]),
    thresholds=dict(A3["thresholds"]),
    terminal_inputs=("transfers", "w", "tau", "r"),
    eta_gate=dict(provisional_rel=1e-9),
    # Derived-cash gate (the A2 pattern at the mortality rung): the newborn
    # injection keeps the EMPLOYMENT-state marginal unchanged, so every
    # income input's delivered cash scales by exactly kappa = L*Gamma
    # relative to the A3 (L=1) cell: cash_A4 = 0.99375 * cash_A3.
    a4_gate=dict(cash_ratio_rel=1e-3,
                 ref_verdict="verdict_A3_20260902-092424.json"),
    # The two mortality SSTs run as gates: the dated FD oracle's pinned
    # identity and the survivor-weight unit tests.
    sst_gates=["step4/test_g10_fd_oracle.py", "test_pweighted_survival.py"],
)

RUNGS = {"A0": A0, "A1": A1, "A2": A2, "A3": A3, "A3T": A3T, "A4": A4}
