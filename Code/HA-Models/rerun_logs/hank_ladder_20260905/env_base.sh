# Base env for the RE-MEASURED HANK ladder on dell (2026-09-05). Source it; override per arm AFTER sourcing.
# Same arm definitions as the 2026-08-28 ladder (hank_ladder_20260828/env_base.sh, run on ccarroll), with
# ONE rung replaced: the BUG-072 override of column 0 (shown by BUG-112 on 2026-09-01 to be the anticipated
# date-1 experiment with its announcement row deleted, 15.7 % short of cash) is replaced by the published
# construction of column 0 differenced against the unshocked chain (HAFISCAL_STEP4_ZEROTH_COLUMN=unanticipated,
# the BUG-075 differencing). Arm 0 = the published HANK construction on the QE calibration, every axis pinned.
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
LAD=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/rerun_logs/hank_ladder_20260905
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration
export HAFISCAL_DISCFAC_FILE=$LAD/qe_calib/DiscFacEstim_CRRA_2.0_R_1.01.txt
export HAFISCAL_SPLURGE_FILE=$LAD/qe_calib/Result_AllTarget.txt
# PE side: the original-model reproduction set + the QE code's 4-micro-state encoding (as on 08-28)
export HAFISCAL_WORLD=as-corrected HAFISCAL_T_AGE=200 HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=0
export HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_PF_DECAY_Q=slope HAFISCAL_GIC_SHAVE_ON_GPF=0 HAFISCAL_LEGACY_TAXCUT_ATOM=1
export HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window
# HANK block: the published construction (QE_FIDELITY=1 semantics, each flag explicit); BUG-071 fix ON in every arm
export HAFISCAL_QE_FIDELITY=1 HAFISCAL_STEP4_SHOCK_FIX=1 HAFISCAL_STEP4_ZEROTH_FIX=0
export HAFISCAL_HANK_PERMGROFAC=ones HAFISCAL_STEP4_TRANMAT_GROWTH=0 HAFISCAL_HANK_UNEMP_PSI=one
export HAFISCAL_HANK_GRIDS=legacy HAFISCAL_HANK_UNEMP_CHAINS=legacy HAFISCAL_HANK_INCOME_LEVEL=net HAFISCAL_TAU_SS=legacy
export HAFISCAL_HANK_SS_SOURCE=hardcoded HAFISCAL_HANK_SPLURGE=legacy HAFISCAL_HANK_SPLURGE_BYEDUC=0
export HAFISCAL_HANK_MULT_REGIME=mixed HAFISCAL_HANK_TAXCUT_FINANCING=incidence_free
export HAFISCAL_STEP4_FAST_BACKWARD=0 HAFISCAL_STEP4_FAST_TRANMAT=1 HAFISCAL_STEP4_FASTEOP=0
export HAFISCAL_STEP4_SKIP_INSTRUMENTS=
# --- pins added 2026-09-05: defaults that changed AFTER the 08-28 ladder, each held at its 08-28 value ---
export HAFISCAL_PERM_GROWTH_SCALE=1           # lambda = 0.44 installed 08-29; 1 = the paper's growth factors
export HAFISCAL_EARNINGS_PHASE_HAZARD=0       # earnings-phase state (08-29, demoted the same day) off
export HAFISCAL_HANK_SPLURGE_DIAG=legacy      # BUG-111 overlay flipped to `cash` 09-01; the 08-28 code had only `legacy`
export HAFISCAL_HANK_NEWBORN_M=unit           # IMPROVEMENT 09-02; `unit` = the published construction
export HAFISCAL_HANK_RHO_R=0.0                # IMPROVEMENT-003 09-02; 0 = the paper's rule (arm 5c unsets QE_FIDELITY)
export HAFISCAL_STEP4_FAKENEWS_INDEX=legacy   # BUG-110 retracted; `legacy` = the 08-28 assembly byte for byte
export HAFISCAL_HANK_FIGURE_ARMS=all          # 09-05 default draws two arms; the ladder's figures are not used
export HAFISCAL_HANK_INCOME_GUARD=warn        # guard added after 08-28: warn, not raise; the logs are grepped for it
export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=hamilton   # the paper's plain shuffle: catalog defaults are p:5 + madow since 09-07 (owner ruling); pinned so the original-code column is independent of QE_FIDELITY's fate
export HAFISCAL_ONSET_SPIKE_T0_EXEMPT=0       # BUG-122 Step 0, a catalog default (ON) since 09-06; 0 = the published ordering
export HAFISCAL_STEP4_ZEROTH_COLUMN=unanticipated   # the corrected column 0 (BUG-112); overridden per arm below
