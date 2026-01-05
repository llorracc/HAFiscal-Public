## Merge Plan: 20250612_finish-latexmk-fixes -> master

### Goals
- Integrate LaTeX build fixes, CI updates, and symlink enforcement into `master`
- Preserve correct long/short build behavior and reproducible builds in CI

### Pre-merge checklist
- Fetch/prune remotes; ensure both branches are up to date
- Confirm clean working trees (no uncommitted changes)
- Verify required symlinks exist and point to correct targets on both branches:
  - `.latexmkrc` -> `@resources/latexmk/latexmkrc/latexmkrc_for-projects-with-circular-crossrefs`
  - `Subfiles/.latexmkrc` -> `../.latexmkrc`
  - `reproduce/.latexmkrc` -> `../.latexmkrc`
- Validate CI workflows present and correct on feature branch
- Confirm local builds succeed (short/long as needed)

### Divergence analysis (dry run)
- git log --oneline --graph --decorate master 20250612_finish-latexmk-fixes --
- git checkout 20250612_finish-latexmk-fixes
- git merge --no-commit --no-ff master || true
- git diff --name-only --diff-filter=U
- git merge --abort

### Conflict resolution policy
- Prefer feature branch for:
  - Reproduce scripts and shellcheck-safe changes in `reproduce/`
  - Symlink corrections (`.latexmkrc`, `Subfiles/.latexmkrc`, `reproduce/.latexmkrc`)
  - CI workflow updates that force long mode on push
- Prefer `master` if it has newer textual content in `.tex` sources; re-apply script/symlink fixes after

### Execute merge
- git checkout 20250612_finish-latexmk-fixes
- git merge master
- Resolve conflicts per policy
- Re-affirm symlink targets (see checklist)

### Post-merge verification
- Local build (SHORT): `reproduce/reproduce_document_pdf_main-only.sh`
- Local build (FULL): `reproduce/reproduce_document_pdfs.sh`
- Verify PDFs updated and logs free of critical errors
- Push branch; confirm GitHub Actions complete successfully (push workflows)

### Roll-forward to master
- Fast-forward or open PR from `20250612_finish-latexmk-fixes` to `master`
- Ensure CI green on PR/push

### Follow-ups
- Consider enabling the stricter local pre-commit hook on `master` as well:
  - Use `.githooks/pre-commit` and set `core.hooksPath` to `.githooks`
  - Enforce symlink targets and shellcheck in pre-commit (as on the feature branch)
- Keep CI step that forces LONG mode on push builds

### Success criteria
- `master` builds clean in CI (LONG mode), with correct symlinks recorded as 120000
- Local builds pass; no broken symlinks or mode drift
- Clear merge record documenting resolution choices 