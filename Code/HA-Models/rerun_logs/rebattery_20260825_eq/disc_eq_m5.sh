#!/bin/bash
# Discriminator: default world, Reduced_Run, welfare AD cells under the HARK engine's own MC AD loop
# (SHARE=0) vs the hybrid loop (gate-2 W_ref) vs the TM equilibrium (gate-2 W_eq).
set -u
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
OUT=$HOME/coldrun_ps_gate_eq; S=$HOME/coldrun_ps_store_eq
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
wrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag/logs; echo "=== $tag start $(date +%H:%M:%S)"; rm -rf ../solution_cache/Reduced_Run; env "$@" $PY run_welfare6_parallel.py --parametrization Reduced_Run --out-dir $OUT/$tag/out --table-dir $OUT/$tag/tables > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? tables=$(ls $OUT/$tag/tables 2>/dev/null | wc -l | tr -d ' ')"; cp -R welfare6_parallel_logs/Reduced_Run/. $OUT/$tag/logs/ 2>/dev/null; echo "   engine lines: $(grep -rh 'welfare_engine\|WELFARE_ENGINE' $OUT/$tag/logs | head -1 | cut -c1-120)"; echo "   AD solves=$(grep -rh 'AD solve took' $OUT/$tag/logs | wc -l | tr -d ' ') HARK-AD=$(grep -rh 'solve_ad_recession\|HARK-AD' $OUT/$tag/logs | wc -l | tr -d ' ') replay=$(grep -rh 'replay' $OUT/$tag/logs | wc -l | tr -d ' ')"; }
wrun W_hark_ref HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark
echo "=== cells: hybrid loop (W_ref) vs HARK loop (W_hark_ref) vs TM equilibrium (W_eq), default world"
$PY ~/bug090_cells.py $OUT W_ref W_hark_ref; $PY ~/bug090_cells.py $OUT W_eq W_hark_ref
echo "DISC DONE $(date +%H:%M:%S)"
