"""The SSJ gated ladder — construction certification for the HANK household block.

Phase A of `plans/20260901-2010h_ssj-gated-ladder_plan.md`: the same minimal household is
built twice — through the untouched step4 per-cell API and through the installed
`sequence_jacobian` package's own het block — and the two are required to satisfy the same
invariant suite (the ABRS block contract: flow budget with the cash on the delivery row
including column 0, announcement identity, PV/truncation identity, same-index dating) and
to converge to a shared limit under grid refinement.

Nothing here runs on any production path; the runner monkeypatches every output location
to scratch. Entry point:

    python -m ssj_ladder.run_rung A0 [--out <dir>] [--quick]

Submodules import step4 (which reads env at import time), so `run_rung` sets the pinned
environment FIRST; do not import `minimal_cell` before it.
"""
