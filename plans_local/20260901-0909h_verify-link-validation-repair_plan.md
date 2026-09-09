# Plan — verify the HAFiscal-make link-validation repair

> **SUPERSEDED the same day (2026-09-01, 11:05–12:20) — folded into this branch 2026-09-09 for provenance only.** The verification this file asked for was done: the repaired workflow turned out to be inert, was rewired onto lychee (HAFiscal-make `d746d05`, `596f8eb`), and its findings are recorded in `conclusions_private/2026-09-01_link-validation-findings-for-the-paper.md` and `…_why-the-papers-online-appendix-links-are-dead.md`. The dead links were fixed 2026-09-09 (redirect front door at econ-ark.github.io/HAFiscal + `\WebBase`/`\webanchor` in the sources). Nothing below is pending.


## Context

`validate-links.yml` in `llorracc/HAFiscal-make` failed every Monday from
2025-12-01 to 2026-08-31 without ever checking a link, and filed 38 duplicate
issues saying links were broken. Two commits (`efd2c63`, `fda9414`) repaired it.
A manual run then passed. See
`history/*_link-validation-workflow-repaired.md`.

The repair was made by an assistant working on an unrelated project, on an
ambiguous instruction. It should be reviewed by someone who knows HAFiscal
before it is trusted.

## Steps

1. **Read the diff.** `git -C HAFiscal-make show efd2c63 fda9414`. The
   substantive change is one token name; everything else is the notify job.
2. **Confirm the token is the right one.** `HAFISCAL_ACCESS_TOKEN` is what the
   three sibling workflows use. Check it has not since expired and that its
   scope is no broader than this needs.
3. **Wait for, or force, a scheduled run.** The manual `workflow_dispatch` run
   passed, but `workflow_dispatch` and `schedule` differ — notably the issue
   step is now schedule-only. The first Monday run is the real test.
4. **Read what the link checker actually reports.** This is the part nobody has
   ever seen. Nine months of "failures" hid whether any HAFiscal URL is in fact
   broken. Expect genuine findings.
5. **Decide on the 38 open issues.** All the same false alarm. Bulk-close with a
   comment pointing at the fix, or keep one as the record.
6. **Separately: `Local and Devcontainer CI`** has been failing at the
   devcontainer build since at least 2026-08-05. Unrelated, unattended, and
   worth its own look.

## Verification

- A scheduled run completes with `Run Link Validation` reaching `success`
  rather than `skipped`
- No new duplicate issue is filed while a `link-validation` issue is open
- A manual run files no issue at all
