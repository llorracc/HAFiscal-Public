#!/bin/bash
# Gather the remote P9/P10 arms into dell's Tables/ (the waterfall and ladder tabulators glob locally). Idempotent; rsync
# only the arm directories (tables + summaries + provenance sidecars), never the pickles. Logs to $LOG/gather.log.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; T=$REPO/Code/HA-Models/FromPandemicCode/Tables; LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
g() { host=$1; remote=$2; shift 2; for pat in "$@"; do rsync -a --include="/$pat/" --include="/$pat/**" --exclude='*' "$host:$remote/" "$T/" 2>&1 | grep -v "^$" | sed "s/^/[$host] /"; done; }
g ccarroll-m5 'coldrun_ps/Code/HA-Models/FromPandemicCode/Tables' 'Baseline_ac_nofix_tma*' 'Baseline_ac_nofix_amax*' 'Baseline_ac_nofix_qmethod*' 'Baseline_uiL_permoff' 'Baseline_uiL_permoff_nshuf_seed*' 'Baseline_uiA_nshare_seed*' 'Baseline_nocap_pkg_seed*' 'Baseline_uiB_repub' 'Baseline_uiB_hark_seed*' 'Baseline_uiA_nshare_N4_seed*' 'Baseline_uiA_nshare_N10_seed*' 'Baseline_orig_pgf' 'Baseline_orig_pgf_seed*' 'Baseline_orig_pfx' 'Baseline_orig_pfx_seed*'
g ccarroll 'coldrun_ps/Code/HA-Models/FromPandemicCode/Tables' 'Baseline_uiA_b095' 'Baseline_uiA_b095_seed*' 'Baseline_ac_nofix_pfdecay_seed*' 'Baseline_ac_nofix_pfq_seed*' 'Baseline_ac_mcmult'
g xubuntark-wan 'coldrun_ps/Code/HA-Models/FromPandemicCode/Tables' 'Baseline_uiA_amax500'
g xubuntark-wan 'coldrun_ps/Code/HA-Models/FromPandemicCode/Tables' 'Baseline_uiL_permoff_nshuf_seed*' 'Baseline_nocap_pkg_seed*'
g ccarroll-m5 'coldrun_ps/Code/HA-Models/FromPandemicCode/Tables' 'LowerUBnoB*' 'CRRA3*' 'CRRA1*'   # P29/P30 appendix re-issue (2026-08-27)
mkdir -p $LOG/m5logs $LOG/ccarroll_logs $LOG/xub_logs
rsync -a ccarroll-m5:ui_ext_20260826/ $LOG/m5logs/ 2>/dev/null; rsync -a ccarroll-m5:p9_m5.out ccarroll-m5:p10_m5.out $LOG/m5logs/ 2>/dev/null
rsync -a ccarroll:ui_ext_20260826/ $LOG/ccarroll_logs/ 2>/dev/null; rsync -a xubuntark-wan:ui_ext_20260826/ $LOG/xub_logs/ 2>/dev/null
echo "gathered $(date +%H:%M:%S): $(ls -d $T/Baseline_ac_nofix_* $T/Baseline_uiL_permoff* $T/Baseline_uiA_nshare* 2>/dev/null | wc -l) arm dirs present"
