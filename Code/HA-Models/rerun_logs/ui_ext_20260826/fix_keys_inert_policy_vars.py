#!/usr/bin/env python3
"""Apply ONLY after every running welfare battery under strict store mode has finished (a key change makes their
later children MISS): drop the five UI_EXT policy vars from the cache-key whitelist. They are captured transitively
(IncShkDstn_recessionUI and the chain size are hashed) and are INERT under legacy/bug_fix, where keying on them split
identical solutions -- the HS_Only legacy batteries MISSed at 14:57 after the catalog flip changed the default world's
(inert) policy value. HAFISCAL_UI_STATE_ENCODING stays in the whitelist."""
import re
p = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/keys.py"
s = open(p).read()
old = '''    # 2026-08-26 (Improvements A/B): the extension POLICY and its per-parameter overrides
    # change IncShkDstn_recessionUI and (through n_extension) the chain size -- captured
    # transitively, but keyed explicitly so no solution ever cross-loads between policies.
    "HAFISCAL_UI_EXTENSION_POLICY",
    "HAFISCAL_UI_EXT_ENACT_LAG",
    "HAFISCAL_UI_EXT_END",
    "HAFISCAL_UI_EXT_ENTRY",
    "HAFISCAL_UI_EXT_QUARTERS",
'''
assert old in s
s = s.replace(old, '''    # 2026-08-26 (Improvements A/B): the extension POLICY (HAFISCAL_UI_EXTENSION_POLICY and its
    # per-parameter overrides HAFISCAL_UI_EXT_{ENACT_LAG,END,ENTRY,QUARTERS}) is deliberately NOT
    # keyed here: its whole effect on a solve is through IncShkDstn_recessionUI and the chain size,
    # both hashed (transitive), and it is INERT under legacy/bug_fix -- keying on it split identical
    # solutions (the 14:57 HS_Only MISSes after the default world's policy value changed). The
    # encoding itself stays keyed (line above).
''', 1)
open(p, "w").write(s)
print("keys.py: inert policy vars removed from the whitelist")

# --- ENV_FLAGS.md: the five entries no longer claim a whitelist slot ---------------------------
d = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/docs/ENV_FLAGS.md"
t = open(d).read()
t = t.replace("; `solution_cache/keys.py` whitelist\n", "\n")
t = t.replace("; `solution_cache/keys.py` whitelist", "")
t = t.replace("(one at a time, explicit env wins). The chain size follows the policy, so solution-cache keys separate the two;",
              "(one at a time, explicit env wins). NOT keyed in `solution_cache/keys.py` (2026-08-26): its whole effect on a solve is through `IncShkDstn_recessionUI` and the chain size, both hashed, and it is inert under `legacy`/`bug_fix` — keying it split identical solutions (strict-store MISSes after the default world's value changed);")
t = t.replace("Must satisfy 0 ≤ lag ≤ `HAFISCAL_UI_EXT_END` (ValueError otherwise).\n**Status:** live",
              "Must satisfy 0 ≤ lag ≤ `HAFISCAL_UI_EXT_END` (ValueError otherwise). Captured transitively by the solution caches (not whitelisted).\n**Status:** live")
open(d, "w").write(t)
print("ENV_FLAGS: whitelist mentions removed for the five UI_EXT entries")
