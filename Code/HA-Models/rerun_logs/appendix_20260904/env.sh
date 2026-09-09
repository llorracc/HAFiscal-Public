# Shared environment for the 2026-09-04 robustness-appendix re-run.
# The current defaults come from config/catalog.py via EstimParameters; nothing here overrides
# an economic setting. HAFISCAL_WORLD/UI_EXTENSION_POLICY are stated explicitly (not relied on
# as defaults) so a log records the world the arm ran in; both equal the catalog canonicals.
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
unset HAFISCAL_EDTYPES HAFISCAL_TM_AMAX HAFISCAL_NUM_STARTS HAFISCAL_EARNINGS_PHASE_HAZARD
