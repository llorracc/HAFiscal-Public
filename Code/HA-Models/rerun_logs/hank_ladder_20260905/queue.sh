#!/bin/bash
# The re-measured ladder, sequential (the Jacobian obj, the Results_HANK pickle and the candidate HANK figures
# are FIXED paths, so arms cannot co-run in one tree). Production artefacts are backed up first and restored
# last; HA_Fiscal_Jacs.obj is TRACKED, so it is also restored from git.
ROOT=/home/shared/github/llorracc/HAFiscal-Latest
LAD=$ROOT/Code/HA-Models/rerun_logs/hank_ladder_20260905
PY=$ROOT/.venv/bin/python
BK=/home/econ-ark/hank_ladder_20260905_backup
FPC=$ROOT/Code/HA-Models/FromPandemicCode
cd "$LAD" || exit 1
exec > "$LAD/queue.out" 2>&1
echo "queue start $(date '+%F %T')"
mkdir -p "$BK/Figures" "$BK/Results_HANK"
cp -p "$FPC/HA_Fiscal_Jacs.obj" "$BK/" && cp -p "$ROOT/Code/HA-Models/Results_HANK/"*.obj "$BK/Results_HANK/" \
  && cp -p "$FPC"/Figures/HANK_*_candidate.pdf "$BK/Figures/" && cp -p "$FPC/Figures/axes_lock_report.json" "$BK/Figures/" 2>/dev/null
(cd "$ROOT" && sha256sum Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj Code/HA-Models/Results_HANK/*.obj Code/HA-Models/FromPandemicCode/Figures/HANK_*_candidate.pdf Code/HA-Models/FromPandemicCode/Figures/axes_lock_report.json) > "$BK/sha256_before.txt" 2>/dev/null
echo "backup: $(wc -l < "$BK/sha256_before.txt") files at $BK"
PUB=$ROOT/../HAFiscal-QE/Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj
PKG="HAFISCAL_STEP4_FAST_BACKWARD=1 HAFISCAL_PLVL_GROWS_DURING_UNEMP=on HAFISCAL_STEP4_ZEROTH_FIX=1"

./run_arm.sh arm0_published monolith
$PY compare_jacs.py "$PUB" arm0_published/HA_Fiscal_Jacs.obj "arm0 (dell, 0.17, monolith, QE calib) vs PUBLISHED pickle (0.14.1)" > arm0_vs_published_pickle.txt 2>&1
GE_ONLY=1 ./run_arm.sh arm0_ss_jacs_c monolith HAFISCAL_HANK_SS_SOURCE=jacs_c
GE_ONLY=1 ./run_arm.sh arm0_ss_jacs monolith HAFISCAL_HANK_SS_SOURCE=jacs

# rung 1, three constructions of column 0 on the package engine (each vs arm 0 = engine + kernel + the column)
./run_arm.sh arm1_col0_ghost   package $PKG HAFISCAL_STEP4_ZEROTH_COLUMN=unanticipated   # the corrected rung
./run_arm.sh arm1b_bug072      package $PKG HAFISCAL_STEP4_ZEROTH_COLUMN=bug072          # the retracted rung (= Mac arm 1p)
./run_arm.sh arm1h_col0_static package $PKG HAFISCAL_STEP4_ZEROTH_COLUMN=historical      # published construction, static-SS differencing
$PY compare_jacs.py arm1_col0_ghost/HA_Fiscal_Jacs.obj arm1h_col0_static/HA_Fiscal_Jacs.obj "ghost vs static differencing (BUG-075 alone)" > arm1_vs_arm1h.txt 2>&1
$PY compare_jacs.py arm0_published/HA_Fiscal_Jacs.obj arm1_col0_ghost/HA_Fiscal_Jacs.obj "arm0 vs arm1 (engine + kernel + BUG-075)" > arm0_vs_arm1.txt 2>&1

# the cumulative ladder on the corrected rung (arm definitions as on 08-28)
R2="$PKG HAFISCAL_HANK_PERMGROFAC=main HAFISCAL_STEP4_TRANMAT_GROWTH=1 HAFISCAL_UI_STATE_ENCODING=bug_fix"
./run_arm.sh arm2_growth package $R2
./run_arm.sh arm2b_growth_unempfrozen package $R2 HAFISCAL_PLVL_GROWS_DURING_UNEMP=off
R3="$R2 HAFISCAL_HANK_UNEMP_CHAINS=pe";                 ./run_arm.sh arm3_pechains package $R3
R4="$R3 HAFISCAL_HANK_TAXCUT_FINANCING=household";      ./run_arm.sh arm4_symfin package $R4
R5="$R4 HAFISCAL_HANK_SS_SOURCE=jacs_c HAFISCAL_HANK_MULT_REGIME=consistent"; ./run_arm.sh arm5_revision_conv package $R5
R5B="$R5 HAFISCAL_HANK_SPLURGE=calib HAFISCAL_HANK_SPLURGE_BYEDUC=1 HAFISCAL_HANK_UNEMP_PSI=main"; ./run_arm.sh arm5b_live_conv package $R5B
GE_ONLY=1 ./run_arm.sh arm5c_calib_splurge package $R5B HAFISCAL_QE_FIDELITY=

echo "restore production artefacts $(date '+%F %T')"
(cd "$ROOT" && git checkout -- Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj)
cp -p "$BK/Results_HANK/"*.obj "$ROOT/Code/HA-Models/Results_HANK/" && cp -p "$BK"/Figures/HANK_*_candidate.pdf "$FPC/Figures/" && cp -p "$BK/Figures/axes_lock_report.json" "$FPC/Figures/" 2>/dev/null
(cd "$ROOT" && sha256sum -c "$BK/sha256_before.txt" 2>&1 | grep -v ": OK$"; echo "restore check: $(cd "$ROOT" && sha256sum -c "$BK/sha256_before.txt" 2>/dev/null | grep -c ': OK$') OK of $(wc -l < "$BK/sha256_before.txt")")
echo "queue end $(date '+%F %T')"
echo QUEUE_DONE
