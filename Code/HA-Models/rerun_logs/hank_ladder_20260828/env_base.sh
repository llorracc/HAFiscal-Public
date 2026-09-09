# Base env for the Econ-9 HANK ladder on ccarroll (2026-08-28). Source it; override per arm AFTER sourcing.
# Arm 0 = the published HANK construction on the QE calibration, every axis pinned explicitly.
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
export HAFISCAL_DISCFAC_FILE=$LAD/qe_calib/DiscFacEstim_CRRA_2.0_R_1.01.txt
export HAFISCAL_SPLURGE_FILE=$LAD/qe_calib/Result_AllTarget.txt
# PE side: the original-model reproduction set (memory feedback_reproduce_original_model_verify_primitives)
# + the QE code's 4-micro-state encoding (the monolith's "states = 4 + 2" was written against it)
export HAFISCAL_WORLD=as-corrected HAFISCAL_T_AGE=200 HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=0
export HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_PF_DECAY_Q=slope HAFISCAL_GIC_SHAVE_ON_GPF=0 HAFISCAL_LEGACY_TAXCUT_ATOM=1
export HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window
# Pinned 2026-09-07: BUG-122 Step 0 became a catalog default (ON, both worlds) on 09-06, AFTER this
# ladder ran. 0 = the ordering this ladder actually used, so a re-run reproduces it.
export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=hamilton   # the paper's plain shuffle: catalog defaults are p:5 + madow since 09-07 (owner ruling); pinned so the original-code column is independent of QE_FIDELITY's fate
export HAFISCAL_ONSET_SPIKE_T0_EXEMPT=0
# HANK block: the published construction (QE_FIDELITY=1 semantics, each flag made explicit).
# BUG-071 fix ON in EVERY arm: reclassified 2026-08-28 as a HARK-0.17 machinery artifact — the published
# 0.14.1 code solved on the correct shocks, so SHOCK_FIX=1 is what reproduces it here.
export HAFISCAL_QE_FIDELITY=1 HAFISCAL_STEP4_SHOCK_FIX=1 HAFISCAL_STEP4_ZEROTH_FIX=0
export HAFISCAL_HANK_PERMGROFAC=ones HAFISCAL_STEP4_TRANMAT_GROWTH=0 HAFISCAL_HANK_UNEMP_PSI=one
export HAFISCAL_HANK_GRIDS=legacy HAFISCAL_HANK_UNEMP_CHAINS=legacy HAFISCAL_HANK_INCOME_LEVEL=net HAFISCAL_TAU_SS=legacy
export HAFISCAL_HANK_SS_SOURCE=hardcoded HAFISCAL_HANK_SPLURGE=legacy HAFISCAL_HANK_SPLURGE_BYEDUC=0
export HAFISCAL_HANK_MULT_REGIME=mixed HAFISCAL_HANK_TAXCUT_FINANCING=incidence_free
export HAFISCAL_STEP4_FAST_BACKWARD=0 HAFISCAL_STEP4_FAST_TRANMAT=1 HAFISCAL_STEP4_FASTEOP=0
export HAFISCAL_STEP4_SKIP_INSTRUMENTS=
