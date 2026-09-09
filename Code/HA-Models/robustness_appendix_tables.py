#!/usr/bin/env python3
"""Re-issue of the appendix's consumption-equivalent welfare tables (BUG-082; owner ruling 2026-08-27 20:30, memo v3 §6
decision 1): the four 𝒞-in-basis-points tables of `Subfiles/Appendix-Robustness.tex` recomputed on the chain's final
configuration (default world, the paper's UI window unless --policy histB; sharing + weighted panel; hark; CRRA-consistent
normalizer `welfare_ce.py`), from the P29/P30/P31 batteries (Tables/<config>[_histB]_seed{0,1,2}/welfare4_candidate.tex)
with the Baseline reference from Tables/Baseline_uiA_seed{0..4} (or Baseline_uiB_seed* for histB). Published values are the
hand-typed tex rows (line refs below). The gamma = 1 row stays dropped (owner ruling 2026-08-21, BUG-086).

Fifth block, "the UI-extension policy" (Econ-7, plans/20260828-1200h_econ-7_ui-policy-to-robustness-appendix_plan.md;
owner rulings 2026-08-27 17:00 "reported separately, not a chain column" and 2026-08-28 10:33 "window everywhere"): the
policy is a DISCRETIONARY design choice, not a correction -- the main text keeps the paper's window; the history-consistent
policy is the appendix arm. Rows = the two-row Baseline report of `waterfall_table.py --order ui-policy` (that ORDERS
entry is imported, so the pair cannot drift from the report) + the same pair for LowerUBnoB, the one configuration where
the policy moves the UI multiplier (Tables/LowerUBnoB vs Tables/LowerUBnoB_histB; welfare from their _seed* batteries).
Columns: the three 10-year AD multipliers (5a Multiplier_candidate.tex; the exact TM evolution has no draws, so no SE),
the UI extension's welfare-6 cells in a recession with and without AD effects (per dollar of outlay; mean over the S seeds
found on disk, SE = std/sqrt(S) in parentheses), the share of the extension's outlay paid during the recession, and S per
row. The block is part of the default run (the appendix is five blocks; --policy scopes only the four 𝒞 tables -- this
block shows both policies by construction) and degrades to ⟨pending⟩ like the others when an arm is absent. Besides the
--out/--tex streams it is written on its own as `_candidate` files -- UIpolicy_candidate.md (the record) and
UIpolicy_candidate.tex (the tabular in the appendix's conventions, the proposed caption as a leading comment) -- under
--candidate-dir, default Code/HA-Models/FromPandemicCode/Tables/Robustness/ of THIS checkout (the directory C10 of
plans/20260828-1130h_infrastructure-lessons-implementation_plan.md names for the appendix's generated candidates;
`*_candidate.tex` is gitignored; no locked file lives there; Subfiles/Appendix-Robustness.tex is never edited here --
promotion = a frozen sibling + a LOCKED_TABLES row + a \\fetchgeneratedtabular wrapper, the owner's step).
The arm tables are untracked results: --tables, else this checkout's FromPandemicCode/Tables, else -- from a linked
worktree -- the main checkout's (waterfall_table.resolve_tables_dir).
Usage: python robustness_appendix_tables.py [--policy window|histB] [--out FILE.md] [--tex FILE.tex] [--tables DIR]
                                            [--candidate-dir DIR | --candidate-dir '']
Test:  pytest Code/HA-Models/test_robustness_appendix_ui_block.py Code/HA-Models/test_updates_report_appendix.py
UPDATES.md (C10 rescoped, owner 2026-08-28 17:10: the published appendix is never replaced; the annotated build of the
changed pages + UPDATES.md is the deliverable): Code/HA-Models/updates_report.py renders the same five blocks through
block_inputs / render_blocks_md / render_ui_policy_md below -- never pasted numbers -- so the two cannot drift.
"""
import argparse, glob, os, re, sys, textwrap
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import waterfall_table as wt  # noqa: E402  (the arm readers, the ui-policy ORDER and the Tables-root resolver)

T = os.path.join(HERE, "FromPandemicCode", "Tables")
CANDIDATE_DIR = os.path.join(T, "Robustness")
ROW_RE = {"noAD": r"\\mathcal\{C\}\(Rec,\\text\{policy\}\)\$?\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)",
          "AD": r"\\mathcal\{C\}\(Rec, AD,\\text\{policy\}\)\$?\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)"}
MULT_RE = r"10y-horizon Multiplier \(AD effect\)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)"

# Published (QE 17(3)) rows, Subfiles/Appendix-Robustness.tex (line numbers as of 2026-08-27): check / UI / tax cut
PUB = {
    "R":       {"noAD": {"Rfree_1005": (0.005, 0.295, 0.001), "Baseline": (0.011, 0.509, 0.002), "Rfree_1015": (0.014, 0.666, 0.003)},   # :79-81
                "AD":   {"Rfree_1005": (0.081, 0.618, 0.030), "Baseline": (0.151, 1.101, 0.056), "Rfree_1015": (0.215, 1.496, 0.081)}},  # :82-84
    "gamma":   {"noAD": {"Baseline": (0.011, 0.509, 0.002), "CRRA3": (0.011, 0.558, 0.002)},                                            # :201-202
                "AD":   {"Baseline": (0.151, 1.101, 0.056), "CRRA3": (0.156, 1.207, 0.059)}},                                           # :204-205
    "benefit": {"noAD": {"Baseline": (0.011, 0.509, 0.002), "LowerUBnoB": (0.043, 1.845, 0.003)},                                        # :263-264
                "AD":   {"Baseline": (0.151, 1.101, 0.056), "LowerUBnoB": (0.157, 2.514, 0.048)}},                                       # :265-266
    "recession": {"noAD": {"Baseline": (0.011, 0.509, 0.002), "Rspell_4": (0.010, 0.424, 0.002), "ADElas": (0.011, 0.509, 0.002)},      # :300-302
                  "AD":   {"Baseline": (0.151, 1.101, 0.056), "Rspell_4": (0.143, 0.926, 0.045), "ADElas": (0.297, 1.695, 0.110)}},     # :303-305
}
PUB_MULT = {"Baseline": (1.245, 1.200, 0.999), "Rspell_4": (1.224, 1.180, 0.967), "ADElas": (1.636, 1.492, 1.152)}   # text :284, :292
LABELS = {"R": ("interest rate", [("Rfree_1005", "$R = 1.005$"), ("Baseline", "$R = 1.01$ (baseline)"), ("Rfree_1015", "$R = 1.015$")]),
          "gamma": ("risk aversion", [("Baseline", "$\\gamma = 2.0$ (baseline)"), ("CRRA3", "$\\gamma = 3.0$")]),
          "benefit": ("benefits", [("Baseline", "Baseline ($\\rho_b = 0.7$, $\\rho_{nb} = 0.5$)"), ("LowerUBnoB", "Altern. ($\\rho_b = 0.3$, $\\rho_{nb} = 0.15$)")]),
          "recession": ("recession properties", [("Baseline", "Baseline"), ("Rspell_4", "Shorter average recession, 4q"), ("ADElas", "Stronger AD effects, 0.5")])}
TEX_HEADER = "% GENERATED by Code/HA-Models/robustness_appendix_tables.py — candidate rows for Subfiles/Appendix-Robustness.tex"
# The reader's note above the four blocks (the BUG-082 normalizer sentence): the md report's header and UPDATES.md's.
HEADER_NOTE = [
    "𝒞 = consumption-equivalent welfare gain in basis points of lifetime consumption (`welfare_ce.py`, `crra`); candidate = mean over",
    "seeds (± SE) on the chain's final configuration; published = QE 17(3) hand-typed rows. γ = 1 stays dropped (ruling 2026-08-21).",
    "",
    "**DO NOT COMPARE THE TWO COLUMNS CELL BY CELL.** They are different measures, not the same measure on two models. The",
    "published 𝒞 divided the utility change by a log-utility normalizer W_c = PDV(1)·N (BUG-082). At γ = 2 that divisor is 12.06×",
    "too large, and — worse than a scale error — it leaves the gain carrying units of 1/c while the cost share it is netted against",
    "is dimensionless. So the error is NOT a common factor: it does not preserve ratios between policies, and it is not even",
    "sign-preserving. Measured on this model (welfare_ce_decomposition.py, seed 0): under the published formula the revised model",
    "reports the UI extension's recession gain as NEGATIVE in 8 of the 10 arms, while the corrected 𝒞 and the main-text 𝒲 (which",
    "never used W_c and is correct for any ρ) both make it strongly positive. The published column's own positivity was a",
    "coincidence of its calibration, not a property of the measure.",
    "",
    "The comparisons that DO carry over: the within-table ORDERING of the corrected column, and the main-text 𝒲 and the",
    "multipliers, which are unaffected by BUG-082. Where a `published formula` column appears below, it is THIS model scored by",
    "the published measure — that column, and only that column, is like-for-like against `published`.",
]


# The "published formula" column: this model's C scored by the SUPERSEDED measure, so the
# published column has a like-for-like counterpart. Produced by welfare_ce_decomposition.py
# from the battery's stored pickles (no re-run); absent => the column is simply not rendered.
DECOMP = {}
DECOMP_CELL = {("noAD", 0): "check_C_rec", ("noAD", 1): "ui_C_rec", ("noAD", 2): "taxcut_C_rec",
               ("AD", 0): "check_C_rec_AD", ("AD", 1): "ui_C_rec_AD", ("AD", 2): "taxcut_C_rec_AD"}


def decomp_default(tables_dir=None):
    """Beside the arms it describes, NOT at a fixed repo path: the decomposition belongs to a
    particular Tables root, so pointing --tables at another tree (a worktree, or the synthetic
    fixture in the guard) must not pick up this checkout's numbers."""
    return os.path.join(tables_dir or T, "Robustness", "ce_decomposition.json")


def load_decomposition(path=None, tables_dir=None):
    """{config: {'legacy': {cell: bp}, ...}} from welfare_ce_decomposition.py --json.
    Resolved beside the tables root so every consumer -- this CLI and updates_report.py --
    gets the like-for-like column without being told about it separately."""
    global DECOMP
    p = path or decomp_default(tables_dir)
    DECOMP = {}
    if p and os.path.exists(p):
        import json as _json
        DECOMP = _json.load(open(p))
    return DECOMP


def legacy_cells(cfg, block):
    """This model's C under the published formula, or None."""
    d = DECOMP.get(cfg)
    if not d or "legacy" not in d:
        return None
    return tuple(d["legacy"][DECOMP_CELL[(block, i)]] for i in range(3))


def resolve_tables_dir(explicit=None):
    """--tables; else this checkout's FromPandemicCode/Tables; else -- from a linked worktree -- the main checkout's
    (the arm tables are untracked results). The Baseline window arm is the reference every block needs."""
    return wt.resolve_tables_dir(explicit, [a[1:] for a in ui_policy_arms()[:1]])


def rows_of(path):
    txt = open(path).read()
    out = {}
    for k, rx in ROW_RE.items():
        m = re.search(rx, txt)
        if m:
            out[k] = tuple(float(x) for x in m.groups())
    return out


def config_cells(cfg, policy, td=None):
    """seed-mean and SE of the two 𝒞 rows for one config; None if no seed landed."""
    td = td or T
    if cfg == "Baseline":
        # window: the PRODUCTION Baseline. `Baseline_uiA` was the 2026-08-26 A/B experiment's name
        # for the window arm; since the owner's 2026-08-28 "window everywhere" ruling the production
        # Baseline IS that arm, and it is the one kept current (Tables/Baseline_seed*, incl. seed 0).
        # Fall back to the uiA battery when no production seed battery is on disk.
        if policy == "window":
            b = "Baseline" if glob.glob(os.path.join(td, "Baseline_seed*", "welfare4_candidate.tex")) else "Baseline_uiA"
        else:
            b = "Baseline_uiB"
        pat = os.path.join(td, f"{b}_seed*", "welfare4_candidate.tex")
    else:
        tag = cfg if policy == "window" else f"{cfg}_histB"
        pat = os.path.join(td, f"{tag}_seed*", "welfare4_candidate.tex")
    files = sorted(glob.glob(pat))
    rs = [rows_of(f) for f in files]
    rs = [r for r in rs if "noAD" in r and "AD" in r]
    if not rs:
        return None
    out = {}
    for k in ("noAD", "AD"):
        a = np.array([r[k] for r in rs])
        out[k] = (a.mean(axis=0), a.std(axis=0, ddof=1) / np.sqrt(len(a)) if len(a) > 1 else np.full(3, np.nan), len(a))
    return out


def multipliers(cfg, policy, td=None):
    td = td or T
    if cfg == "Baseline":
        # see config_cells: the production Baseline is the window arm (uiA = its 2026-08-26 name)
        d = "Baseline_uiB" if policy != "window" else (
            "Baseline" if os.path.exists(os.path.join(td, "Baseline", "Multiplier_candidate.tex")) else "Baseline_uiA")
    else:
        d = cfg if policy == "window" else f"{cfg}_histB"
    p = os.path.join(td, d, "Multiplier_candidate.tex")
    if not os.path.exists(p):
        return None
    m = re.search(MULT_RE, open(p).read())
    return tuple(float(x) for x in m.groups()) if m else None


def fmt(v, se=None):
    s = f"{v:.3f}"
    return s if se is None or not np.isfinite(se) else f"{s} ± {se:.3f}"


# ---------------------------------------------------------------------------------------------------------------
# The four 𝒞 blocks: one data pass (block_inputs), two renderers (md = published beside candidate, tex = the
# appendix's layout). The CLI and UPDATES.md both go through these, so a row cannot differ between them.
def block_inputs(policy, td=None):
    """One dict per 𝒞 block, in the appendix's order: key, title, rows = [(config, label)], cells = {config:
    config_cells(...) or None (pending)}; the recession block also carries mult = {config: multipliers(...) or None}."""
    out = []
    for key, (title, rows) in LABELS.items():
        b = {"key": key, "title": title, "rows": rows, "cells": {cfg: config_cells(cfg, policy, td) for cfg, _ in rows}}
        if key == "recession":
            b["mult"] = {cfg: multipliers(cfg, policy, td) for cfg, _ in rows}
        out.append(b)
    return out


def seed_counts(blocks):
    """{config: S} over the four blocks, first appearance first -- S = the seed batteries found on disk (0 = pending)."""
    out = {}
    for b in blocks:
        for cfg, _ in b["rows"]:
            c = b["cells"][cfg]
            out.setdefault(cfg, c["AD"][2] if c else 0)
    return out


def render_blocks_md(blocks):
    """The four blocks as markdown: published check / UI / tax cut beside the candidate (mean ± SE, S); after the
    recession block, the 10-year multipliers the appendix text quotes."""
    L = []
    for b in blocks:
        has_leg = any(legacy_cells(cfg, "noAD") for cfg, _ in b["rows"])
        hdr = "| | row | published check / UI / tax cut | THIS model, published formula | candidate check / UI / tax cut (S) |" \
            if has_leg else "| | row | published check / UI / tax cut | candidate check / UI / tax cut (S) |"
        L += [f"## {b['title']}", "", hdr, "|---|---|---|---|---|" if has_leg else "|---|---|---|---|"]
        for block, blabel in (("noAD", "no AD effects"), ("AD", "AD effects")):
            first = True
            for cfg, lab in b["rows"]:
                pub = PUB[b["key"]][block][cfg]; cells = b["cells"][cfg]
                if cells is None:
                    cand = PENDING_MD
                else:
                    m, se, S = cells[block]
                    cand = " / ".join(fmt(m[i], se[i]) for i in range(3)) + f" (S={S})"
                row = f"| {blabel if first else ''} | {lab} | {pub[0]:.3f} / {pub[1]:.3f} / {pub[2]:.3f} |"
                if has_leg:
                    lg = legacy_cells(cfg, block)
                    row += (" " + (" / ".join(f"{v:.3f}" for v in lg) if lg else PENDING_MD) + " |")
                L.append(row + f" {cand} |")
                first = False
        if b["key"] == "recession":
            L += ["", "10-year multipliers with AD (the text quotes them; published → candidate):"]
            for cfg, lab in b["rows"]:
                pub = PUB_MULT[cfg]; mm = b["mult"][cfg]
                L.append(f"- {lab}: {pub[0]:.3f} / {pub[1]:.3f} / {pub[2]:.3f} → " + (" / ".join(f"{x:.3f}" for x in mm) if mm else PENDING_MD))
        L.append("")
    return L


def render_blocks_tex(blocks):
    """The four blocks as tabulars in Subfiles/Appendix-Robustness.tex's layout (candidate means only)."""
    TEX = []
    for b in blocks:
        TEX += [f"% --- {b['title']} ---", "\\begin{tabular}{@{}lllll@{}}", "\\toprule",
                "                  &                & Stimulus check & UI extension & Tax cut \\\\ \\cmidrule(l){1-5}"]
        for block, blabel in (("noAD", "no AD effects"), ("AD", "AD effects")):
            first = True
            for cfg, lab in b["rows"]:
                cells = b["cells"][cfg]
                texcand = "\\multicolumn{3}{c}{%s}" % PENDING_TEX if cells is None else " & ".join(f"{cells[block][0][i]:.3f}" for i in range(3))
                prefix = ('\\multirow{%d}{*}{%s}' % (len(b["rows"]), blabel)) if first else ' ' * 18
                TEX.append('    ' + prefix + ' & ' + lab + ' & ' + texcand + ' \\\\')
                first = False
            TEX[-1] += " \\cmidrule(l){1-5}"
        TEX += ["\\end{tabular}", ""]
    return TEX


# ---------------------------------------------------------------------------------------------------------------
# Fifth block: the UI-extension policy (module docstring). The Baseline pair IS waterfall_table's ui-policy order.
UI_POLICY_TITLE = "the UI-extension policy"
UI_POLICY_LABEL = {"window": "the paper's window", "history": "history-consistent"}
UI_CONFIG_LABEL = dict(LABELS["benefit"][1])       # Baseline / LowerUBnoB, worded as in the benefits table
UI_CELLS = (("ui_rec_AD", "AD effects"), ("ui_rec", "no AD effects"))
UI_LOWER_ARMS = [("LowerUBnoB", "window", "LowerUBnoB", "LowerUBnoB_seed*"),                # P29 (window battery)
                 ("LowerUBnoB", "history", "LowerUBnoB_histB", "LowerUBnoB_histB_seed*")]   # P30 (history hedge, m5)
UI_CANDIDATE_STEM = "UIpolicy_candidate"
UI_TEX_NCOL = 9   # configuration, policy, three multipliers, two welfare cells, outlay share, S
PENDING_MD, PENDING_TEX = "⟨pending⟩", "pending"


def ui_policy_arms():
    """(config, policy, 5a dir, welfare glob): the Baseline pair from waterfall_table.ORDERS['ui-policy'] (window first,
    history second -- the report's column order), then the LowerUBnoB pair."""
    base = [("Baseline", pol, d5, wg) for pol, (_, d5, wg) in zip(("window", "history"), wt.ORDERS["ui-policy"])]
    return base + list(UI_LOWER_ARMS)


def ui_policy_inputs(td=None):
    """One dict per row, in table order: config, policy, dir5a, welfare_glob, mult (the AD row's three strings, or None),
    outlay (the UI column of the outlay-share row as printed, e.g. '79.4', or None), cells {ui_rec_AD, ui_rec:
    (mean, SE, S)} with S = the seed summaries found on disk (0 = pending)."""
    td = td or T
    rows = []
    for cfg, pol, d5, wg in ui_policy_arms():
        mr = wt.mult_rows(os.path.join(td, d5, "Multiplier_candidate.tex"))
        ad, share = mr.get("AD"), mr.get("outlay share in recession")
        w = wt.welfare(wg, td)
        rows.append({"config": cfg, "policy": pol, "dir5a": d5, "welfare_glob": wg,
                     "mult": list(ad) if ad and len(ad) == 3 else None,
                     "outlay": share[1] if share and len(share) == 3 else None,
                     "cells": {c: w[c] for c, _ in UI_CELLS}})
    return rows


def _seeds(r):
    return r["cells"][UI_CELLS[0][0]][2]


def _wcell(m, se, S, tex=False):
    if S == 0 or not np.isfinite(m):
        return PENDING_TEX if tex else PENDING_MD
    if S < 2 or not np.isfinite(se):
        return f"{m:.3f}"
    return f"{m:.3f} ({se:.3f})" if tex else f"{m:.3f} ± {se:.3f}"


def ui_policy_notes(rows):
    """The caption/notes, one sentence per entry; the seed counts come from the rows (never typed)."""
    def S_of(cfg):
        s = sorted({_seeds(r) for r in rows if r["config"] == cfg})
        return "S = " + "/".join(map(str, s or [0])) + (" seeds" if len(s) <= 1 else " seeds, per row")
    return [
        "The UI-extension policy is a DISCRETIONARY design choice, not a correction (owner rulings 2026-08-27 17:00 and "
        "2026-08-28 10:33): the main text keeps the paper's window, a one-time extension at the recession's onset (four "
        "quarters for the onset cohort, three for the next quarter's entrants, nothing further); the history-consistent "
        "policy, enacted one quarter in with open entry and in force through quarter 8 with a hard stop, is this appendix's arm.",
        f"Rows: the revised model under each policy, for the Baseline ({S_of('Baseline')}; the two-row report of "
        f"waterfall_table.py --order ui-policy, memo v3 section 5) and for the alternative benefit rates "
        f"({S_of('LowerUBnoB')}), the one configuration where the policy moves the UI multiplier.",
        "Columns: the 10-year multipliers with AD effects (the exact transition-matrix evolution; no sampling, so no SE); "
        "the welfare gain of the UI extension in a recession with and without AD effects, PER DOLLAR of outlay (the "
        "welfare-6 cells; mean over the S seeds, SE = std/sqrt(S) in parentheses); the share of the extension's outlay paid "
        "during the recession; S = the number of welfare seeds in the row.",
    ]


def render_ui_policy_md(rows):
    L = [f"## {UI_POLICY_TITLE}", ""] + ui_policy_notes(rows) + [
        "", "| configuration | UI-extension policy | 10y AD multiplier check / UI / tax cut | W(UI, Rec, AD) per $ | "
        "W(UI, Rec) per $ | UI outlay in recession | S |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        mult = " / ".join(r["mult"]) if r["mult"] else PENDING_MD
        out = f"{r['outlay']} %" if r["outlay"] else PENDING_MD
        cells = [_wcell(*r["cells"][c]) for c, _ in UI_CELLS]
        L.append(f"| {UI_CONFIG_LABEL[r['config']]} | {UI_POLICY_LABEL[r['policy']]} | {mult} | {cells[0]} | {cells[1]} | "
                 f"{out} | {_seeds(r)} |")
    return L + [""]


def render_ui_policy_tex(rows):
    """The tabular in Subfiles/Appendix-Robustness.tex's conventions (booktabs, \\multirow group labels, \\cmidrule after
    each group); the proposed caption rides along as a comment -- the appendix wrapper is the owner's edit."""
    L = [f"% --- {UI_POLICY_TITLE} ---",
         "% proposed caption/notes for the wrapper in Subfiles/Appendix-Robustness.tex (not edited by this tool):"]
    L += ["% " + s for s in textwrap.wrap(" ".join(ui_policy_notes(rows)), 116)]
    L += ["\\begin{tabular}{@{}" + "ll" + "c" * (UI_TEX_NCOL - 2) + "@{}}", "\\toprule",
          "                  &                     & \\multicolumn{3}{c}{10y-horizon multiplier (AD effect)} & "
          "\\multicolumn{2}{c}{$\\mathcal{W}$(UI, Rec) per dollar} & UI outlay    &     \\\\",
          "                  & UI-extension policy & Stimulus check & UI extension & Tax cut & AD effects & no AD effects & "
          "in recession & $S$ \\\\ \\cmidrule(l){1-%d}" % UI_TEX_NCOL]
    for cfg in dict.fromkeys(r["config"] for r in rows):
        pair = [r for r in rows if r["config"] == cfg]
        for i, r in enumerate(pair):
            prefix = ("\\multirow{%d}{*}{%s}" % (len(pair), UI_CONFIG_LABEL[cfg])) if i == 0 else " " * 18
            mult = " & ".join(r["mult"]) if r["mult"] else "\\multicolumn{3}{c}{%s}" % PENDING_TEX
            out = f"{r['outlay']}\\%" if r["outlay"] else PENDING_TEX
            cells = [_wcell(*r["cells"][c], tex=True) for c, _ in UI_CELLS]
            L.append("    " + prefix + " & " + UI_POLICY_LABEL[r["policy"]] + " & " + mult + " & " + cells[0] + " & " +
                     cells[1] + " & " + out + " & " + str(_seeds(r)) + " \\\\")
        L[-1] += " \\cmidrule(l){1-%d}" % UI_TEX_NCOL
    return L + ["\\end{tabular}", ""]


def write_ui_policy_candidates(rows, cand_dir):
    """UIpolicy_candidate.md + .tex under cand_dir (created); returns the two paths."""
    os.makedirs(cand_dir, exist_ok=True)
    md, tex = (os.path.join(cand_dir, UI_CANDIDATE_STEM + ext) for ext in (".md", ".tex"))
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(render_ui_policy_md(rows)) + "\n")
    with open(tex, "w", encoding="utf-8") as f:
        f.write("\n".join([TEX_HEADER, ""] + render_ui_policy_tex(rows)) + "\n")
    return md, tex


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--policy", default="window", choices=("window", "histB"))
    ap.add_argument("--out", default=None); ap.add_argument("--tex", default=None)
    ap.add_argument("--tables", default=None,
                    help="Tables root holding the arms (default: this checkout's FromPandemicCode/Tables, else the main checkout's)")
    ap.add_argument("--decomposition", default=None,
                    help="welfare_ce_decomposition.py --json output; adds the 'THIS model, published formula' "
                         "column, the only one that is like-for-like against the published column")
    ap.add_argument("--candidate-dir", default=CANDIDATE_DIR,
                    help=f"where the UI-policy block's {UI_CANDIDATE_STEM}.md/.tex go (default {CANDIDATE_DIR}; '' = do not write)")
    a = ap.parse_args()
    td = resolve_tables_dir(a.tables)
    load_decomposition(a.decomposition, td)
    blocks = block_inputs(a.policy, td)
    L = [f"# Appendix 𝒞 tables re-issued (CRRA-consistent normalizer, BUG-082) — UI policy: {a.policy}", ""] + HEADER_NOTE + [""]
    L += render_blocks_md(blocks)
    TEX = [TEX_HEADER, ""] + render_blocks_tex(blocks)
    ui_rows = ui_policy_inputs(td)
    L += render_ui_policy_md(ui_rows)
    TEX += render_ui_policy_tex(ui_rows)
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w").write(text)
    if a.tex:
        open(a.tex, "w").write("\n".join(TEX) + "\n")
    print(text)
    if a.candidate_dir:
        md, tex = write_ui_policy_candidates(ui_rows, a.candidate_dir)
        print(f"UI-policy block -> {md}\n                   {tex}", file=sys.stderr)


if __name__ == "__main__":
    main()
