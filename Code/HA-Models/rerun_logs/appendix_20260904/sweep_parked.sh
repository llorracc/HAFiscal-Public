#!/bin/bash
# Move every parked pre-lambda artefact out of the Tables/ glob namespace.
# MUST run before generating the report: the queues launched on 2026-09-04 sourced the first
# cut of park(), which renamed Tables/<NAME>_seedK to Tables/<NAME>_seedK_pre_lambda_20260904 --
# still a match for the readers' "<NAME>_seed*" glob, so the appendix C rows would average the
# fresh seeds together with the August ones. Idempotent; safe while a queue is running
# (parked directories are inert, nothing reads or writes them).
set -u
T="${1:-/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Tables}"
cd "$T" || exit 9
mkdir -p _parked_20260904
n=0
for d in *_pre_lambda_20260904; do
  [ -d "$d" ] || continue
  mv "$d" _parked_20260904/ && n=$((n+1))
done
echo "sweep_parked: relocated $n directories; $(ls _parked_20260904 2>/dev/null | wc -l) now parked"
echo "remaining glob-namespace matches that are still parked: $(ls -d *_pre_lambda_* 2>/dev/null | wc -l) (must be 0)"
