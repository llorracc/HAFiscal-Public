#!/bin/bash
# P10 on xubuntark (2026-08-26 23:10): seeds 2,3,4 of the runtime-only perm-shock arm (m5 runs its 5a and seeds 0,1):
# default-world economics under the paper's numerics (legacy 4-state encoding, non-shuffled HARK MC, own AD loops -- no 5a
# needed) with HAFISCAL_PERM_DURING_UNEMP=off on the default calibration. Worktree ~/coldrun_ps detached at dell's 5633bd43.
# No-FMA floats here: not bitwise with dell/m5, sig-fig stable (band computed on dell from the five summaries).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
echo "worktree at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { tag=$1; K=$2; shift 2
  stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1
  stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l)"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; }
PERMOFF=(HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_PERM_DURING_UNEMP=off HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0)
for K in 2 3 4; do w6 uiL_permoff_nshuf $K "${PERMOFF[@]}"; done
echo "P10 XUB DONE $(date +%H:%M:%S)"
