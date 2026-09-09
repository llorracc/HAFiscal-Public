# Dolo-plus integration — Phase 0.4 baseline snapshot (2026-06-12)

The "before" picture that all dolo-plus integration seams diff against
(Phase 0.4 of `plans/20260611_doloplus-integration-master.md`). Taken on
branch `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` at commit `63d66dcf`
(Phase 0.1–0.3 already applied; the test-gate repair `0281c45c` is in).

## pytest collection

```
python -m pytest Code/ reproduce/ --collect-only -q
# -> 230 tests collected, 0 errors (repo-root conftest.py collection guard active)
```

Note: `dolo_plus_validation/test_euler_at_point.py` is still in the repo-root
`collect_ignore` at snapshot time (module-level solve); the validation-
productionization plan converts it and removes the ignore — collected-count
will grow accordingly.

## reproduce_min.sh

```
./reproduce.sh --comp min --accept-unpushed   # via reproduce_min.sh path
# -> exit 0 (completed 2026-06-12; log: reproduce/logs/comp_min_20260612-*.log)
```

(First attempt failed the pre-flight gate on a dirty worktree — that is the
gate working as designed, not a reproduction failure; rerun after the Phase-0
commit with `--accept-unpushed` since the branch intentionally isn't pushed.)

## Stale-report checksums (pre-re-baseline)

These are the BUG-047-era (pre-2026-06-04-fix) reports, recorded so the
re-baseline diff is auditable:

```
17ec7466807d99068513a3eb1ae15b5d41ccba3199ea0732fd4a798a1cdc933f  check_vs_hafiscal_report.txt
0798748c44ca92bad82dee80f22a4215b70cb6db67cb3d9f90256e4067e43110  validation_report.txt
```

## YAML

```
python -c "import yaml; yaml.safe_load(open('HAFiscal-doloplus-draft.yaml'))"  # OK
```
