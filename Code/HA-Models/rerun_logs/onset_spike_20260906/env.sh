# Shared environment for the BUG-122 Step-0 measurement (the onset-spike t=0 exemption).
# Nothing here overrides an economic setting: the values are the catalog canonicals, stated
# explicitly so each log records the world its arm ran in.
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
# an outer export wins, so the same drivers can run a second world without a second env file
export HAFISCAL_WORLD=${HAFISCAL_WORLD:-default}
export HAFISCAL_UI_EXTENSION_POLICY=${HAFISCAL_UI_EXTENSION_POLICY:-paper}
unset HAFISCAL_EDTYPES HAFISCAL_TM_AMAX HAFISCAL_NUM_STARTS HAFISCAL_EARNINGS_PHASE_HAZARD
# HYGIENE ONLY -- this is NOT how an arm selects OFF. Since 2026-09-06 the flag is a catalog
# default (ON, both worlds), so EstimParameters setdefaults it and an UNSET arm is an ON arm.
# The unset here only clears a stale value inherited from the caller; every arm driver then
# pins 0 or 1 EXPLICITLY. See onset_spike_rule.t0_exempt.
unset HAFISCAL_ONSET_SPIKE_T0_EXEMPT
