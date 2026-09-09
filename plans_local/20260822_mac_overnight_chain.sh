#!/bin/bash
# Overnight chain (2026-08-22): sync to HEAD -> f-pin probe -> [m5 only] S1 knots0-full arm.
# $1 = role: "m5" (full arm) or "light" (sync+probe only)
set -u
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
ROLE="${1:-light}"; LOG=~/overnight_20260822_${ROLE}.log; DONE=~/overnight_20260822_${ROLE}.done
{
echo "== chain start $(date) role=$ROLE =="
cd ~/GitHub/llorracc/HAFiscal-Latest || { echo "exit=65 no-repo" > $DONE; exit 65; }
# refuse only on modified/staged TRACKED files; untracked scratch is harmless for ff-only
if git status --porcelain | grep -qv "^??"; then
  echo "DIRTY TREE (tracked modifications) - refusing sync:"; git status --porcelain | grep -v "^??" | head -5
  echo "exit=66 dirty" > $DONE; exit 66
fi
git fetch origin && git merge --ff-only origin/0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC || { echo "exit=67 ff" > $DONE; exit 67; }
echo "HEAD now: $(git log --oneline -1)"
make sync || { echo "exit=68 sync" > $DONE; exit 68; }
PY="$PWD/.venv/bin/python"; "$PY" -c "import numpy, HARK; print('venv ok', numpy.__version__)" || { echo "exit=69 venv" > $DONE; exit 69; }
# cross-platform f-pin probe: f at the installed SoR under the install config (knots0 @ full)
cd Code/HA-Models && env HAFISCAL_SOLVE_GRID_PROFILE=full HAFISCAL_STEP1_TAIL_KNOTS=0 PYTHONUNBUFFERED=1 \
  "$PY" step1_attach_probe.py --out ~/attach_probe_knots0_full_${ROLE}.npz \
  --splurge 0.299869842312644 --beta 0.9795228226132132 --nabla 0.029390125527173155 \
  || { echo "exit=70 probe" > $DONE; exit 70; }
if [ "$ROLE" = "m5" ]; then
  cd ~/GitHub/llorracc/HAFiscal-Latest
  git worktree add -f ~/hafiscal-s1arm "$(git rev-parse HEAD)" 2>/dev/null || true
  cd ~/hafiscal-s1arm/Code/HA-Models/Target_AggMPCX_LiquWealth || { echo "exit=71 wt" > $DONE; exit 71; }
  rm -f Result_AllTarget_Splurge0_startpoint*.txt Result_AllTarget_Splurge0.txt Result_AllTarget_ESC.txt Result_AllTarget_startpoint*_ESC.txt
  echo "== S1 knots0-full arm start $(date) =="
  env HAFISCAL_SOLVE_GRID_PROFILE=full HAFISCAL_STEP1_TAIL_KNOTS=0 HAFISCAL_STEP1_PLOT=0 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" Estimation_BetaNablaSplurge.py
  RC=$?
  echo "== S1 arm end $(date) rc=$RC =="
  echo "exit=$RC s1arm" > $DONE; exit $RC
fi
echo "exit=0 light" > $DONE
} >> $LOG 2>&1
