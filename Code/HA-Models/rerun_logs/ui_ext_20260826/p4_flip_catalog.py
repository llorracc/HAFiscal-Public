#!/usr/bin/env python3
"""P4 catalog flip (apply ONLY after every running battery has finished -- catalog.py is imported by each child):
default world -> Improvement B (ui_extension_policy canonical 'history'); ENV_FLAGS default text; parity-test literal."""
import re, sys
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
def patch(path, old, new):
    s = open(path).read(); assert old in s, (path, old[:60]); open(path, "w").write(s.replace(old, new, 1))
patch(f"{REPO}/Code/HA-Models/config/catalog.py",
      "        # Improvement B (owner 2026-08-26; the case is REALISM). canonical='window' until the\n        # plan's P4 flips the default world to 'history' (after the Improvement-A gates).\n        canonical=\"window\",",
      "        # Improvement B (owner 2026-08-26; the case is REALISM). canonical FLIPPED to 'history'\n        # at P4 (2026-08-26) after the Improvement-A gates (G0/G1) and the Baseline runs.\n        canonical=\"history\",")
patch(f"{REPO}/Code/HA-Models/config/test_runtime_parity.py",
      '    "HAFISCAL_UI_EXTENSION_POLICY": "window",', '    "HAFISCAL_UI_EXTENSION_POLICY": "history",   # P4 flip 2026-08-26')
patch(f"{REPO}/Code/HA-Models/docs/ENV_FLAGS.md",
      "**Default:** `window` (EstimParameters.py; the `default` world's catalog value until the plan's P4 flips the default world to `history`; `as-corrected` = `window`, where it is inert anyway because the encoding is `legacy`)",
      "**Default:** `history` in the `default` world (catalog DISCRETIONARY canonical, flipped at P4 2026-08-26); the code-literal fallback in EstimParameters.py is `window`; `as-corrected` = `window` (the paper's policy), where it is inert anyway because the encoding is `legacy`")
patch(f"{REPO}/Code/HA-Models/docs/ENV_FLAGS.md",
      "**Purpose:** Catalog DISCRETIONARY `ui_extension_policy` (canonical `window` until P4, paper `window`).",
      "**Purpose:** Catalog DISCRETIONARY `ui_extension_policy` (canonical `history` since P4 2026-08-26, paper `window`).")
patch(f"{REPO}/CLAUDE.md",
      "**B** (`HAFISCAL_UI_EXTENSION_POLICY=history`, DISCRETIONARY): the history-consistent policy on A's machinery",
      "**B** (`HAFISCAL_UI_EXTENSION_POLICY=history`, DISCRETIONARY; the `default` world's value since P4 2026-08-26): the history-consistent policy on A's machinery")
print("catalog flipped to history; ENV_FLAGS/CLAUDE/parity updated")
