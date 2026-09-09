#!/bin/bash
# BUG-092 owner's test on the WELFARE cells: does the shared-equilibrium gap (We: TM equilibrium vs Wh: own
# HARK-MC loop; +4.4 % on check_rec_AD at 1x) shrink with 10x agents? Reduced_Run, uncapped default world,
# gate-2 store (~/coldrun_ps_store_eq holds the 1x-published TM equilibria; the key excludes AgentCount).
set -u
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
OUT=$HOME/coldrun_ps_gate_eq; S=$HOME/coldrun_ps_store_eq
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
wrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag/logs; echo "=== $tag start $(date +%H:%M:%S)"; rm -rf ../solution_cache/Reduced_Run; env "$@" $PY run_welfare6_parallel.py --parametrization Reduced_Run --agent-count-total 50000 --out-dir $OUT/$tag/out --table-dir $OUT/$tag/tables > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? tables=$(ls $OUT/$tag/tables 2>/dev/null | wc -l | tr -d ' ')"; cp -R welfare6_parallel_logs/Reduced_Run/. $OUT/$tag/logs/ 2>/dev/null; echo "   equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $OUT/$tag/logs | wc -l | tr -d ' ') skipped=$(grep -rh 'AD loop SKIPPED' $OUT/$tag/logs | wc -l | tr -d ' ') miss=$(grep -rl 'MISS at' $OUT/$tag/logs | wc -l | tr -d ' ') agentcount=$(grep -rh 'agent_count_total\|AgentCountTotal' $OUT/$tag/logs | head -1 | cut -c1-80)"; grep -h "FAIL rc=" $OUT/$tag.log | head -2; }
wrun Wh_10x HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark
wrun We_10x HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=1
echo "=== 10x cells: TM equilibrium (We_10x) vs HARK loop (Wh_10x)   [1x: check +4.39 %, UI -0.19 %, taxcut +1.37 %]"; $PY ~/bug090_cells.py $OUT We_10x Wh_10x
echo "=== 10x vs 1x own-loop (Wh_10x vs W_hark_ref) and TM-eq (We_10x vs W_eq): pure N effect per arm"; $PY ~/bug090_cells.py $OUT W_hark_ref Wh_10x; $PY ~/bug090_cells.py $OUT W_eq We_10x
echo "W10X DONE $(date +%H:%M:%S)"
