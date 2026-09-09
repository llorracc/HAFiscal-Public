# Overnight plan, 2026-08-31 22:00 → report due 08:30–09:00

Owner: "keep working on this overnight, on all machines (m5, ccarroll, xubuntark, dell) using
ultracode ... to try to understand HANK models better. I'll expect a report at maybe 8:30 or 9:00 am."

Note: the owner's earlier "do NOT use the ccarroll machine" was explicitly lifted by this
instruction, which names ccarroll among the machines to use.

## Compute in flight

| machine | job | what it answers | out dir |
|---|---|---|---|
| dell | G13 horizon ladder under `fixed` (bigT 300/200/450/600 × φ_π 0/0.05/0.2) | does the fixed-nominal NON-IDENTIFICATION survive the BUG-110 fix? G13's verdict was measured on the buggy Jacobians. | `rerun_logs/g13fix_20260831/` |
| ccarroll-m5 | legacy-vs-fixed multipliers at bigT=300 | cross-platform replication on a different float environment — is the −16 % UI / −1.6 % tax-cut pattern real? | `rerun_logs/bug110_m5_20260831/` (on m5) |
| ccarroll | splurge sweep, both arms × ς ∈ {0, 0.135, 0.2704, 0.4, 0.6} | how much of the multiplier change runs through the splurge overlay (which installs PV directly) vs the direct Jacobian? At ς=0 the overlay vanishes. | `rerun_logs/bug110_splurge_20260831/` (on ccarroll) |
| xubuntark | fine ladder under `fixed`, bigT ∈ {250,350,400,500} | fills between dell's points → an 8-point horizon ladder for the identification question | `rerun_logs/g13fix_fine_20260831/` (on xubuntark) |

Code distribution: pushed sub-branch `..._TM-vs-MC_bug110` (NOT the shared branch — 123 commits
ahead of origin, and the three remotes sit on unrelated lineages). Each remote runs in its own
`git worktree` at `HAFiscal-bug110`, so no remote checkout was disturbed.

Caveat carried into the report: m5/ccarroll are macOS and xubuntark has no-FMA floats, so none of
them is bit-comparable to dell. They are replication and sensitivity, not precision work; every
precision claim (the O(dx) proof, byte-identity) stays on dell.

## Agent work in flight (ultracode)

* `hank-block-audit` — 12 finders over the HANK block hunting BUG-110-class silent defects
  (index/convention/timing, dead channels, hardcoded knobs), each surviving finding put through 3
  adversarial lenses (correctness / silent-failure / already-known), majority-refute kills it.
* `hank-understanding` — 8 investigations (iMPC structure vs the empirical MPC literature; budget
  adding-up restrictions; our fake-news vs the canonical Auclert-Bardóczy-Rognlie-Straub algorithm;
  the splurge overlay's economics; peg determinacy as an explanation for the fixed-nominal
  non-identification; literature comparison of HANK fiscal multipliers; why the UI channel has a
  2-quarter duration; and exactly what the paper claims from this block) → independent re-check of
  every high-confidence claim → synthesis.

## Standing state

* BUG-110 fix is behind `HAFISCAL_STEP4_FAKENEWS_INDEX=fixed`; **default remains `legacy`** —
  flipping it changes every HANK number and is the owner's call.
* `legacy` verified byte-identical to the pre-fix assembly (all nine G13 cells reproduce exactly).
