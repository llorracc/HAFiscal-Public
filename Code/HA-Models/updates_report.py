#!/usr/bin/env python3
"""updates_report.py — generate UPDATES.md: the systematic frozen-vs-current
comparison (U2 of plans_local/20260823-1030h_updates-document-and-annotated-paper_plan.md;
owner ruling 2026-08-23: the text stays frozen — this document, regenerable and
never hand-edited, is how changes are communicated).

Columns per exhibit (each cell-level; vocabulary = the config-worlds taxonomy,
owner relabel 2026-08-26):
  PUBLISHED — as published: the same relative path in the canonical sibling
              ../HAFiscal-QE (the ONLY authority for published numbers).
  BUGFIXED  — the `as-corrected` world: the paper's economics + all bug fixes + the
              certified numerics package (owner 2026-08-26; formerly "all-and-only
              bug fixes. Joined from an extra-world map (default:
              conclusions_private/artifacts_20260823_wfix/wfix_map.tsv, the
              former W-FIX column); `--extra BUGFIXED=path.tsv` overrides.
  IMPROVED  — the `default` world: bug fixes + adopted improvements + the
              canonical discretionary choices; = the _candidate sibling that
              current code produces (the former CURRENT column).
  DRAFT     — what the working paper's text currently renders (this repo's
              locked file; the former FROZEN column). Shown ONLY where it
              differs from PUBLISHED and from IMPROVED — the transitional
              post-publication promotions — so a reader of the annotated PDF
              can match the numbers on the page. The manifest provenance of
              every exhibit is still stated on its entry line.
Other extra worlds join via --extra NAME=path pairs mapping exhibit basenames
to alternative generated files.
The closing section "What changed" lists the code behind the numbers: every
catalogued setting (config/catalog.py: bug fixes, improvements, discretionary)
and the BUGS_private ledger index.

The section "Online appendix — robustness tables" (C10 rescoped, owner ruling
2026-08-28 17:10: the published content, appendices included, is NEVER replaced;
the annotated build of the changed pages + this document is the deliverable)
shows the appendix's hand-typed consumption-equivalent (𝒞) tables beside the
re-issued candidates, rendered by robustness_appendix_tables.py's own row
builders (never pasted numbers), and the annotations map badges the appendix's
section head so `make pdf-annotated` can point at it (the appendix source is
untouched: the badge is attached by @local/local-qe-figs-and-tables.sty).

Figures compare by SHA (changed/unchanged/no-candidate); tabulars cell-by-cell.
Exit 0 always (reporting tool, not a gate).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _main_checkout():
    """Root of the main working tree (None outside git); differs from REPO inside a linked worktree."""
    try:
        out = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None
    return os.path.dirname(os.path.abspath(os.path.join(REPO, out)))


def _resolve_qe():
    """The canonical sibling ../HAFiscal-QE (the ONLY authority for published numbers): next to this
    checkout, else -- from a linked worktree, whose parent is .claude/worktrees -- next to the main one."""
    cands = [os.path.normpath(os.path.join(REPO, "..", "HAFiscal-QE"))]
    main_root = _main_checkout()
    if main_root and os.path.normpath(main_root) != os.path.normpath(REPO):
        cands.append(os.path.normpath(os.path.join(main_root, "..", "HAFiscal-QE")))
    return next((c for c in cands if os.path.isdir(c)), cands[0])


QE = _resolve_qe()
MANIFEST = os.path.join(REPO, "LOCKED_TABLES.manifest")

NUM = re.compile(r"-?\d+\.?\d*")


def _artifact_world(apath):
    """The world a static artifact was produced in, from the PROVENANCE.tsv beside it (written by the
    install scripts, 2026-09-07); None when unknown."""
    tsv = os.path.join(os.path.dirname(apath), "PROVENANCE.tsv")
    try:
        with open(tsv) as fh:
            for line in fh:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if parts and parts[0] == os.path.basename(apath) and len(parts) >= 3:
                    return parts[2].strip() or None
    except OSError:
        pass
    return None


def _candidate_world(cand):
    """The world of the run that wrote `cand`: HAFISCAL_WORLD from the newest RUN_*.prov.json in its
    directory (unset = default), None when there is no sidecar."""
    if not cand:
        return None
    import glob as _glob
    d = os.path.dirname(cand)
    sidecars = sorted(_glob.glob(os.path.join(d, "RUN_*.prov.json")), key=os.path.getmtime)
    if not sidecars:
        return None
    try:
        j = json.load(open(sidecars[-1]))
    except (OSError, ValueError):
        return None
    env = dict(j.get("resolved_config", {}).get("env", {})); env.update(j.get("set_flags", {}))
    return (env.get("HAFISCAL_WORLD") or "default").strip().lower()


def _stamp(mtime):
    """UTC date of an artifact, for the vintage note on a static extra column."""
    import datetime
    return datetime.datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%d")


def parse_tabular(path):
    """[(label, [numbers...]), ...] from a LaTeX tabular body; None if unreadable."""
    if not os.path.exists(path):
        return None
    rows = []
    for raw in open(path, errors="replace"):
        line = raw.strip()
        if ("&" not in line) or line.startswith(("%", r"\begin", r"\end", r"\toprule",
                                                 r"\midrule", r"\bottomrule")):
            continue
        cells = line.split("&")
        label = re.sub(r"\\[a-zA-Z]+|[{}$]", "", cells[0]).strip()
        nums = []
        for c in cells[1:]:
            c = c.replace(r"\%", "").replace(r"\\", "")
            m = NUM.findall(c)
            nums.append(float(m[0]) if m else None)
        seen = sum(1 for l, _ in rows if l == label or l.startswith(label + " ["))
        if seen:
            label = f"{label} [{seen + 1}]"
        rows.append((label, nums))
    return rows or None


def sha(path):
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def candidate_path(frozen_rel):
    stem, ext = os.path.splitext(frozen_rel)
    return os.path.join(REPO, stem + "_candidate" + ext)


def fmt(v):
    if v is None:
        return "—"
    return f"{v:g}"


def compare_rows(base, other):
    """Aligned cell diffs: [(label, i, base_v, other_v)] for differing numeric cells."""
    diffs, bmap = [], {l: ns for l, ns in base}
    for label, nums in other:
        if label not in bmap:
            continue
        for i, (a, b) in enumerate(zip(bmap[label], nums)):
            if a is not None and b is not None and abs(a - b) > 1e-12:
                diffs.append((label, i, a, b))
    return diffs


def _first_sentence(text, limit=220):
    t = " ".join((text or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"


RECORD_DIRS = ("conclusions_private", "BUGS_private", "RECONCILED_private", "plans",
               "plans_local", "history", "decay_form")
_RECORD_RE = re.compile(r"(?<![\w:/.\-])(?:" + "|".join(RECORD_DIRS) + r")/[A-Za-z0-9_./+\-*]+\.md")


def _records_in(text):
    """Unique record-document paths cited in ``text`` (order preserved)."""
    out = []
    for m in _RECORD_RE.findall(text or ""):
        if m not in out:
            out.append(m)
    return out


FIGDOC_TEX = "UPDATES-figures.tex"
FIGDOC_PDF = "UPDATES-figures.pdf"

# The figure files the PUBLISHED paper renders (QE 17(3), HAFiscal-QE-published.pdf, Figures
# 1-6; the no-splurge results are a Supplemental Appendix, not part of the published paper).
# Owner ruling 2026-08-26: the comparison document shows only these.
PUBLISHED_PAPER_FIGURES = {
    # Figure 1
    "AggMPC_LotteryWin_comparison.pdf", "LiquWealth_Distribution_comparison.pdf",
    # Figure 2
    "LorenzPoints_CRRA_2.0_R_1.01.pdf",
    # Figure 3
    "IMPCs_wSplEstimated.pdf",
    # Figure 4
    "recession_Check_relrecession.pdf", "recession_UI_relrecession.pdf",
    "recession_taxcut_relrecession.pdf", "Cumulative_multiplier_Check.pdf",
    "Cumulative_multiplier_UI.pdf", "Cumulative_multiplier_TaxCut.pdf",
    # Figure 5
    "HANK_transfer_IRF.pdf", "HANK_UI_IRF.pdf", "HANK_tax_IRF.pdf",
    "HANK_transfer_multiplier.pdf", "HANK_UI_multiplier.pdf", "HANK_tax_multiplier.pdf",
    # Figure 6
    "Cumulative_multipliers_withHank.pdf",
}
AXES_LOCK_REPORT = os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode", "Figures",
                                "axes_lock_report.json")


# Generators whose edits invalidate a candidate figure already on disk. The candidate
# figures are gitignored, so nothing in git shows when one has fallen behind the code
# that draws it -- and on 2026-09-05 the six HANK candidates sat ten hours behind a
# committed change (per-panel legends, b7946b8b) while this document embedded them.
# Narrow on purpose: these are the figures whose generator is unambiguous. A stale
# candidate is reported, not silently shown.
_FIGURE_GENERATORS = {
    "HANK_": [os.path.join("Code", "HA-Models", "step4", "ge.py"),
              os.path.join("Code", "HA-Models", "step4", "figures.py")],
}


def _candidate_staleness(rel):
    """'' or a clause saying this candidate predates the code that draws it."""
    base = os.path.basename(rel)
    srcs = next((v for k, v in _FIGURE_GENERATORS.items() if base.startswith(k)), None)
    if not srcs:
        return ""
    stem, ext = os.path.splitext(os.path.join(REPO, rel))
    cand = stem + "_candidate" + ext
    try:
        t_fig = os.path.getmtime(cand)
    except OSError:
        return ""
    newer = []
    for src in srcs:
        try:
            if os.path.getmtime(os.path.join(REPO, src)) > t_fig:
                newer.append(os.path.basename(src))
        except OSError:
            pass
    if not newer:
        return ""
    return ("; the candidate on disk PREDATES " + ", ".join(sorted(newer))
            + " — regenerate with `python Code/HA-Models/step4/run_ge.py`")


def _axes_note(rel):
    """One sentence on the published-axes lock for this figure (fig_axes.py report)."""
    try:
        rep = json.load(open(AXES_LOCK_REPORT))
    except Exception:
        return "axes: not locked (no lock report)" + _candidate_staleness(rel)
    key = os.path.basename(rel)
    for ext in (".pdf", ".png", ".svg", ".jpg"):
        if key.lower().endswith(ext):
            key = key[: -len(ext)]
    r = rep.get(key)
    if not r:
        return ("axes: not locked (regenerate the candidate under HAFISCAL_FIG_AXES_LOCK)"
                + _candidate_staleness(rel))
    note = f"axes locked to the published limits ({r['matched']}/{r['frames']} panels)"
    # The lock report accumulates across runs and producers, so an entry can describe a
    # figure that has since been regenerated. Render the overflow clause only when the
    # entry is at least as new as the figure it describes -- on 2026-09-05 a stale entry
    # put a clipping claim into this document that did not reproduce from the plotted
    # series (fig_axes._append_report carries the reasoning). Unstamped entries predate
    # the stamp and are treated as stale for the clause, not for the lock sentence.
    _fig = os.path.join(REPO, rel)
    _stamp = r.get("stamped")
    try:
        _fresh = _stamp is not None and os.path.getmtime(_fig) <= float(_stamp) + 1.0
    except OSError:
        _fresh = False
    if r.get("overflow") and not _fresh:
        return (note + "; a clipping report for this figure was recorded but predates the figure and is not shown"
                + _candidate_staleness(rel))
    for o in r.get("overflow", []):
        parts = []
        for axname, (lo, hi) in o["data"].items():
            lim = o["published_" + axname + "lim"]
            parts.append(f"{axname}: improved data span [{lo:.3g}, {hi:.3g}] vs the published axis "
                         f"[{lim[0]:.3g}, {lim[1]:.3g}]")
        note += "; DATA BEYOND the published range, clipped — " + "; ".join(parts)
    return note + _candidate_staleness(rel)


def _tex_path(rel):
    """Brace the basename so graphicx does not mistake dots in it for an extension."""
    d, b = os.path.split(rel)
    stem, ext = os.path.splitext(b)
    return "{" + (d + "/" if d else "") + stem + "}" + ext


def write_figures_doc(changed_figs, head):
    """UPDATES-figures.tex: one page per changed figure of the PUBLISHED paper — PUBLISHED
    (../HAFiscal-QE) beside IMPROVED (the _candidate sibling), same axes (the candidate is
    regenerated under the published-axes lock, fig_axes.py). Page numbers: the index is
    page 1, figure k is page k+1 (each figure on its own page) — what the annotations map
    and UPDATES.md link to."""
    T = [r"% GENERATED by Code/HA-Models/updates_report.py -- do not hand-edit.",
         r"\documentclass[10pt]{article}",
         r"\usepackage[margin=1.6cm]{geometry}\usepackage{graphicx}\usepackage{xcolor}",
         r"\usepackage[hidelinks]{hyperref}\usepackage{url}",
         r"\setlength{\parindent}{0pt}",
         r"\newcommand{\panel}[3]{\begin{minipage}[t]{#1\linewidth}\centering"
         r"{\footnotesize\sffamily\bfseries #2}\\[2pt]"
         r"\includegraphics[width=\linewidth,height=0.72\textheight,keepaspectratio]{#3}\end{minipage}}",
         r"\begin{document}",
         r"{\Large\bfseries HAFiscal --- changed figures: published vs improved}\\[4pt]",
         r"Generated by \texttt{Code/HA-Models/updates\_report.py} at \texttt{" + head + r"}. "
         r"Every figure of the PUBLISHED paper (QE 17(3), Figures 1--6) whose improved version differs: "
         r"\textbf{PUBLISHED} = the file at the same path in the canonical sibling "
         r"\texttt{../HAFiscal-QE}; \textbf{IMPROVED} = the \texttt{\_candidate} current code produces "
         r"(the \texttt{default} world: all bug fixes + adopted improvements), regenerated with its axes "
         r"locked to the published figure's limits (\texttt{Code/HA-Models/fig\_axes.py}; where the "
         r"improved series leave that range they are clipped and the page says so). Figures outside the "
         r"published paper (the supplemental no-splurge appendix) are not shown. Companion to "
         r"\texttt{UPDATES.md}; the annotated paper's figure badges link here.\\[8pt]",
         r"{\bfseries Contents}\\[2pt]"]
    for k, (rel, prov, vs_pub, vs_cand) in enumerate(changed_figs, start=1):
        T.append(r"p.~%d\quad\texttt{\detokenize{%s}}\\" % (k + 1, rel))
    for k, (rel, prov, vs_pub, vs_cand) in enumerate(changed_figs, start=1):
        stem, ext = os.path.splitext(rel)
        panels = [("PUBLISHED (QE 17(3))", os.path.join(os.path.relpath(QE, REPO), rel)),
                  ("IMPROVED (candidate of current code, published axes)", stem + "_candidate" + ext)]
        T.append(r"\clearpage")
        # named destination `figK`: the annotated paper's badge links open this page
        # (hyperref turns \href{UPDATES-figures.pdf\#figK} into a GoToR action on it)
        T.append(r"\hypertarget{fig%d}{}{\large\bfseries %d.\ \texttt{\detokenize{%s}}}\\[2pt]" % (k, k, rel))
        T.append(r"{\small \detokenize{%s}.}\\[6pt]" % _axes_note(rel))
        T.append(r"\hfill".join(r"\panel{0.48}{%s}{%s}" % (lab, _tex_path(path)) for lab, path in panels))
    T.append(r"\end{document}")
    open(os.path.join(REPO, FIGDOC_TEX), "w").write("\n".join(T) + "\n")


# --- the online appendix (C10 rescoped, owner 2026-08-28 17:10) -------------------------------
APPENDIX_EXHIBIT = "Subfiles/Appendix-Robustness.tex"
APPENDIX_SECTION = "Online appendix — robustness tables (re-issued 𝒞, candidates; not promoted)"
# The badge's pointer text, typeset by pdflatex: ASCII only (the heading's script C is not an
# inputenc character), quotes and the dash as TeX ligatures.
# Exhibit-specific notes (owner rulings that change WHAT an exhibit shows, not just its numbers).
# Rendered into the UPDATES.md entry line and appended to the annotated paper's badge.
PEG_NOTE = ("peg arm dropped: the constant-nominal-rate regime is nearly indeterminate (fiscal "
            "policy is nearly passive too), so its responses are set by the equilibrium-selection "
            "device rather than by the fiscal experiment; the Taylor rule with 0.7 persistence and "
            "the fixed real rate are shown instead (owner, 2026-09-05)")
EXHIBIT_NOTES = {b: PEG_NOTE for b in ("HANK_tax_IRF", "HANK_tax_multiplier", "HANK_transfer_IRF",
                                        "HANK_transfer_multiplier", "HANK_UI_IRF", "HANK_UI_multiplier",
                                        "HANK_IRFs_w_splurge")}
# Exhibits whose note the annotated build places ONCE under the whole figure (map key
# `HFupdfig@`) instead of in every panel badge: the six panels of Figures/HANK_IRFs.tex
# share one note, and six copies in the narrow 2x3 panel badges overflowed the page by
# 197pt (2026-09-05). The UPDATES.md entry line still carries the note per exhibit.
FIGURE_LEVEL_NOTES = {"HANK_tax_IRF", "HANK_tax_multiplier", "HANK_transfer_IRF",
                      "HANK_transfer_multiplier", "HANK_UI_IRF", "HANK_UI_multiplier"}


# Notes on the TEXT (the co-author briefing, 2026-09-03 §9 items 2-3, promised them "in the
# annotation document, beside Section 5"; homed here 2026-09-09): prose the published paper keys to
# results the corrected machinery changes. Rendered as a "Notes on the text" section of UPDATES.md
# and, in the annotated build, as a [NOTE ON THE TEXT ...] box under the section head of the
# subfile named here (map key HFupdtext@<subfile path>; the sty arms it exactly like HFupd@).
# Entries: (subfile path, human label, [(title, body, source record), ...]). Bodies are plain
# text with these Unicode symbols, which _tex() maps to macros: τ φ_π ρ_r ≈ — %.
TEXT_NOTES = [
    ("Subfiles/HANK.tex", "Section 5 (the HANK-SAM cross-check)", [
        ("The two roles of the tax rate",
         "τ = 0.3 stays. It does two jobs at once: it finances government expenditure (≈ 26 % of "
         "output) that the partial-equilibrium model deliberately abstracts from, and it supplies the "
         "marginal stabilization leakage — the automatic stabilizer that damps the demand loop. A "
         "derived rate that funded only the modeled UI and debt service (≈ 0.04) would raise every "
         "multiplier by a third by removing that stabilizer; it was tested and rejected (BUG-077, "
         "withdrawn). Both roles are realistic at 0.3, and the two models' consonance at τ = 0.3 is what "
         "lets this section function as a cross-check.",
         "conclusions_private/2026-08-10_tau-two-roles-lessons_coauthor-note.md"),
        ("The published impulse responses use the un-smoothed Taylor rule",
         "The responses this section reads, and the sentences keyed to them, were computed under a "
         "Taylor rule with no interest smoothing (φ_π = 1.5). With the household block corrected that "
         "rule sits at the model's determinacy boundary: a period-2 zigzag, hidden at coarse wealth "
         "grids and exposed as the grid is refined, is an instability of the rule rather than a bug "
         "(the one-quarter policy lag turns the rule into positive feedback for alternating deviations, "
         "which the purely forward Phillips curve amplifies). The revised results use a standard "
         "inertial rule (ρ_r = 0.70; IMPROVEMENT-003) with the fixed real rate as the robustness "
         "companion; read the published prose about these responses against those.",
         "conclusions_private/2026-09-02_taylor-arm-zigzag-is-a-grid-masked-instability-of-the-unsmoothed-rule.md"),
    ]),
]


def _tex(t):
    """The note text as pdflatex input (badge boxes are typeset, not \\verb). The symbols
    are parked behind placeholders before the underscore/percent escapes run, so the math
    subscripts survive (the first build of 2026-09-09 printed a literal underscore)."""
    sym = (("φ_π", r"$\phi_\pi$"), ("ρ_r", r"$\rho_r$"), ("τ", r"$\tau$"), ("≈", r"$\approx$"))
    for i, (a, _b) in enumerate(sym):
        t = t.replace(a, f"\x00{i}\x00")
    for a, b in (("—", "---"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("_", r"\_")):
        t = t.replace(a, b)
    for i, (_a, b) in enumerate(sym):
        t = t.replace(f"\x00{i}\x00", b)
    return t


def text_notes_section():
    n = sum(len(notes) for _, _, notes in TEXT_NOTES)
    L = [f"\n---\n\n# Notes on the text ({n})\n",
         "Prose in the published paper that is keyed to results the corrected machinery changes. Not "
         "exhibits — nothing here has a `_candidate`; the annotated build places each note under the "
         "section head of the subfile it concerns (`[NOTE ON THE TEXT ...]`). The pointers are the "
         "records the notes condense; the wording follows the co-author briefing "
         "(`HAFiscal_update_for_coauthors.md`, sent 2026-09-03, §9).\n"]
    for path, where, notes in TEXT_NOTES:
        L.append(f"## `{path}` — {where}\n")
        for title, body, src in notes:
            L.append(f"- **{title}.** {body}  *(record: `{src}`)*")
        L.append("")
    return L


def text_note_annotations():
    """Map lines for the text notes: one HFupdtext@ key per include-path shape, as for the appendix."""
    out = []
    for path, _where, notes in TEXT_NOTES:
        body = " ".join(f"({i}) {_tex(t)}: {_tex(b)}" for i, (t, b, _s) in enumerate(notes, start=1))
        for pref in ("", "./", "../", "../../"):
            out.append(r"\expandafter\gdef\csname HFupdtext@%s%s\endcsname{%s}" % (pref, path, body))
    return out


def exhibit_note(rel):
    """The note for an exhibit path, or ''."""
    return EXHIBIT_NOTES.get(os.path.splitext(os.path.basename(rel))[0], "")


APPENDIX_BADGE = ("UPDATES.md, section ``Online appendix --- robustness tables'' "
                  "(re-issued candidates beside the published rows; nothing promoted)")


def appendix_section():
    """(lines, ok): the appendix's hand-typed 𝒞 tables beside the re-issued candidates and the UI-policy
    block, rendered through robustness_appendix_tables.py's own row builders (block_inputs /
    render_blocks_md / render_ui_policy_md) so this section and the generator cannot drift; ok=False
    (with the reason in the lines) when the generator cannot be imported -- the report never fails."""
    L = [f"\n---\n\n# {APPENDIX_SECTION}\n",
         f"*Exhibit:* `{APPENDIX_EXHIBIT}` — the online appendix (rendered on its own as "
         "`Subfiles/Appendix-Robustness.pdf`; inside the main PDF it sits in a `hiddencontent` box that is "
         "processed for labels and discarded). Its four consumption-equivalent welfare (𝒞) tables are "
         "hand-typed, so they have no `LOCKED_TABLES.manifest` row and no `_candidate` sibling: this section "
         "is their published-vs-candidate comparison, generated by `Code/HA-Models/robustness_appendix_tables.py` "
         "from the re-issue batteries (default world, the paper's UI window; "
         "`Tables/<config>_seed*/welfare4_candidate.tex`, the Baseline reference from "
         "`Tables/Baseline_uiA_seed*`). The published rows stand as printed (owner ruling 2026-08-28 17:10: "
         "the published content, appendices included, is never replaced) — nothing here is promoted; the "
         "annotated build badges the appendix's section head with a pointer to this section.\n"]
    try:
        sys.path.insert(0, os.path.join(REPO, "Code", "HA-Models"))
        import robustness_appendix_tables as rat
        td = rat.resolve_tables_dir()
        rat.load_decomposition(tables_dir=td)   # like-for-like 'published formula' column, if present
        blocks = rat.block_inputs("window", td)
        L.extend(rat.HEADER_NOTE)
        L.append("")
        seeds = rat.seed_counts(blocks)
        L.append("Seeds per configuration (the welfare batteries found on disk; 0 = pending): " +
                 "; ".join(f"`{cfg}`: S = {n}" for cfg, n in seeds.items()) + ". Arm tables read from " +
                 ("this checkout's" if os.path.normpath(td).startswith(os.path.normpath(REPO) + os.sep)
                  else "the main checkout's") +
                 " `Code/HA-Models/FromPandemicCode/Tables/` (untracked results; they live where the runs were made).")
        L.append("")
        L.extend(rat.render_blocks_md(blocks))
        L.extend(rat.render_ui_policy_md(rat.ui_policy_inputs(td)))
        return L, True
    except Exception as exc:  # the report never fails on the appendix
        L.append(f"\n*(appendix comparison unavailable: {exc})*\n")
        return L, False


def appendix_annotations():
    """The annotations-map lines that badge the appendix's section head (consumed by
    @local/local-qe-figs-and-tables.sty in the annotated build): one key per include-path shape --
    the main document's \\subfile{Subfiles/Appendix-Robustness} (bare) and the \\latexroot-relative
    forms, among them the standalone compile's ../Subfiles/Appendix-Robustness.tex."""
    return [r"\expandafter\gdef\csname HFupd@%s%s\endcsname{%s}" % (pref, APPENDIX_EXHIBIT, APPENDIX_BADGE)
            for pref in ("", "./", "../", "../../")]


def what_changed_section():
    """The code behind the numbers, with its paper trail: every catalogued
    setting by category and the BUGS_private ledger, each row pointing at the
    records (conclusions_private decision docs, bug files, plans, RECONCILED
    entries) that hold its rationale; then an index of those records. Generated
    — the catalog, the ledger and the records are the sources of truth."""
    L = ["\n---\n\n# What changed — the code behind the numbers\n",
         "Two generated inventories, each row with its paper trail. (1) Every setting the "
         "config-worlds catalog classifies (`Code/HA-Models/config/catalog.py`, the single "
         "source of truth for the `default` and `as-corrected` worlds): BUG FIXES apply in both "
         "BUGFIXED and IMPROVED, as do the CERTIFIED NUMERICS (owner 2026-08-26); the other IMPROVEMENTS and the canonical DISCRETIONARY choices apply in "
         "IMPROVED only. (2) The bug ledger (`BUGS_private/`, one file per bug; the `**Status:**` "
         "line is authoritative), which also covers fixes that have no toggle. The **record** "
         "columns are the link to the narrative layer: `conclusions_private/` holds the dated "
         "decision documents (why a setting takes the value it does, the evidence, the owner "
         "ruling), `BUGS_private/` the per-bug diagnosis, `RECONCILED_private/` the investigated "
         "non-bugs, `plans/` the execution records. The closing index lists every record the rows "
         "cite. Flags: `Code/HA-Models/docs/ENV_FLAGS.md`; HARK 0.17 migration fixes: "
         "`CHANGELOG_0170_MIGRATION.md`.\n"]
    cited = {}   # record path -> [who cites it]

    def cite(path, who):
        cited.setdefault(path, [])
        if who not in cited[path]:
            cited[path].append(who)

    try:
        sys.path.insert(0, os.path.join(REPO, "Code", "HA-Models"))
        from config import catalog as cat
        # Certified numerics (owner ruling 2026-08-26): IMPROVEMENT rows whose certification is of
        # the exact-relabeling / asymptotic KIND (C9, 2026-08-28) are applied in BOTH worlds
        # (as-corrected included) — listed as their own group. A "tolerance" certification
        # (a documented residual within stated bounds) is world-scoped and listed separately.
        def _cert(st):
            kind = getattr(st, "certification_kind", None)
            if kind is None:  # pre-C9 catalog: any certification path meant certified numerics
                return bool(getattr(st, "certification", ""))
            return kind in ("exact-relabeling", "asymptotic")

        def _tol(st):
            return getattr(st, "certification_kind", None) == "tolerance"
        groups = [("Bug fixes (in BUGFIXED and IMPROVED)",
                   lambda st: st.category == cat.BUG_FIX),
                  ("Certified numerics (in BUGFIXED and IMPROVED — rigorously tested to leave the "
                   "estimates unchanged for large samples; owner 2026-08-26)",
                   lambda st: st.category == cat.IMPROVEMENT and _cert(st)),
                  ("Tolerance-certified improvements (IMPROVED only — reproduce the reference within "
                   "the stated bounds; the bounds are in the record)",
                   lambda st: st.category == cat.IMPROVEMENT and _tol(st)),
                  ("Improvements (IMPROVED only; opt-in for BUGFIXED)",
                   lambda st: st.category == cat.IMPROVEMENT and not _cert(st) and not _tol(st)),
                  ("Discretionary choices — modifications (IMPROVED = canonical; BUGFIXED = paper value)",
                   lambda st: st.category == cat.DISCRETIONARY)]
        for title, member in groups:
            rows = [st for st in cat.CATALOG if member(st)]
            L.append(f"\n## {title} — {len(rows)}\n")
            L.append("| setting | env var | paper | now | why | record |")
            L.append("|---|---|---|---|---|---|")
            for st in rows:
                why = _first_sentence(st.evidence).replace("|", "\\|")
                recs = []
                for r in (([st.certification] if (_cert(st) or _tol(st)) else []) + list(st.refs)):
                    recs.append(f"`{r}`")
                    for path in _records_in(r):
                        cite(path, f"setting `{st.name}`")
                L.append(f"| `{st.name}` | `{st.env_var or '—'}` | `{st.paper}` | "
                         f"`{st.canonical}` | {why} | {'; '.join(recs) or '—'} |")
    except Exception as exc:  # the report never fails on the inventory
        L.append(f"\n*(catalog inventory unavailable: {exc})*\n")

    bugs_dir = os.path.join(REPO, "BUGS_private")
    entries, skipped = [], []
    for fn in sorted(os.listdir(bugs_dir)) if os.path.isdir(bugs_dir) else []:
        if not fn.startswith("HAFiscal_BUG-") or not fn.endswith(".md"):
            continue
        m = re.match(r"HAFiscal_BUG-(\d+)_.*\.md$", fn)
        if not m:
            skipped.append(fn)   # e.g. a combined "BUG-034+035" audit
            continue
        title, status, body = "", "", []
        for raw in open(os.path.join(bugs_dir, fn), errors="replace"):
            body.append(raw)
            line = raw.strip()
            if not title and line.startswith("# "):
                title = re.sub(r"^#\s*(BUG-\d+:?\s*)?", "", line).strip()
            if not status and line.startswith("**Status"):
                status = re.sub(r"^\*\*Status:?\*\*:?\s*", "", line)
                status = re.sub(r"[*`]", "", status).strip()
        recs = [r for r in _records_in("".join(body))
                if not r.startswith("BUGS_private/" + fn)]
        num = int(m.group(1))
        for path in recs:
            cite(path, f"BUG-{num:03d}")
        entries.append((num, title or fn, status or "(no status line)", fn, recs))
    L.append(f"\n## Bug ledger — {len(entries)} entries (`BUGS_private/`)\n")
    L.append("| bug | what | status | record |")
    L.append("|---|---|---|---|")
    for num, title, status, fn, recs in entries:
        t = title.replace("|", "\\|")
        st = status.replace("|", "\\|")
        st = st if len(st) <= 110 else st[:109].rstrip() + "…"
        shown = [f"`{os.path.basename(r)}`" for r in recs[:3]]
        if len(recs) > 3:
            shown.append(f"+{len(recs) - 3}")
        L.append(f"| BUG-{num:03d} | {t} | {st} | `{fn}`" +
                 (" — cites " + ", ".join(shown) if shown else "") + " |")
    if skipped:
        L.append("\n*Ledger files without a single numeric id (not tabulated): " +
                 ", ".join(f"`{f}`" for f in skipped) + "*")

    # ---- the records index: what the rows above actually cite
    L.append(f"\n## Decision records behind the rows — {len(cited)} cited\n")
    L.append("Every record document cited by a catalog setting or a bug file above, with the "
             "rows that cite it. A record that no row cites is not listed here even if it "
             "changed the method — see the note at the end of this section.\n")
    L.append("| record | cited by |")
    L.append("|---|---|")
    import glob as _glob
    for path in sorted(cited):
        # catalog refs may be globs (e.g. BUGS_private/HAFiscal_BUG-092_*.md)
        exists = bool(_glob.glob(os.path.join(REPO, path)))
        who = ", ".join(cited[path])
        L.append(f"| `{path}`{'' if exists else ' **(MISSING)**'} | {who} |")
    cp = os.path.join(REPO, "conclusions_private")
    n_all = len([f for f in os.listdir(cp) if f.endswith(".md")]) if os.path.isdir(cp) else 0
    n_cited = len([q for q in cited if q.startswith("conclusions_private/")])
    L.append(f"\n*`conclusions_private/` holds {n_all} decision/record documents; {n_cited} are "
             "cited by the rows above. The rest are session records, verdicts and method "
             "syntheses whose adoptions have no catalog toggle (e.g. the hybrid welfare engine, "
             "the TM-ergodic Step-2 engine, the FTI/ATI solver default, the doob Q-construction, "
             "the weighted-tail sampler, the S = 3 seed ruling, the distribution-grid top rule) — "
             "they are reachable from `CLAUDE.md`'s documentation map and `plans/INDEX.md`, not "
             "from this index. Making them visible here means giving each a catalog row or a "
             "ledger entry.*")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "UPDATES.md"))
    ap.add_argument("--extra", action="append", default=[],
                    help="NAME=path-map.tsv: extra world; tsv rows 'frozen-rel<TAB>file'")
    ap.add_argument("--annotations-out",
                    default=os.path.join(REPO, "@local", "updates-annotations.ltx"),
                    help="LaTeX annotations map for `make pdf-annotated` (U3)")
    args = ap.parse_args()

    DEFAULT_BUGFIXED_MAP = os.path.join(
        REPO, "conclusions_private", "artifacts_20260823_wfix", "wfix_map.tsv")
    specs = list(args.extra)
    if not any(sp.split("=", 1)[0] in ("BUGFIXED", "W-FIX") for sp in specs) \
            and os.path.exists(DEFAULT_BUGFIXED_MAP):
        specs.insert(0, "BUGFIXED=" + DEFAULT_BUGFIXED_MAP)
    extras = []
    for spec in specs:
        name, tsv = spec.split("=", 1)
        if name == "W-FIX":          # pre-2026-08-26 spelling of the same world
            name = "BUGFIXED"
        emap = {}
        for line in open(tsv):
            if "\t" in line:
                k, v = line.rstrip("\n").split("\t", 1)
                emap[k] = v
        extras.append((name, emap))

    head = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    qe_ok = os.path.isdir(QE)

    changed, unchanged, pending, figures, wrappers = [], [], [], [], []
    # Exhibits with NO in-repo generator (verified 2026-08-23: only the Tables/
    # compile scripts reference them — nothing writes them). A `_candidate`
    # will never appear for these, so "awaiting candidates" is the wrong bucket.
    # One-line reader-facing definitions for extra worlds we know about (joined
    # into the column legend so the doc explains every column it shows).
    KNOWN_WORLD_NOTES = {
        "BUGFIXED": (" = the `as-corrected` world: the paper's economics + "
                     "all bug fixes + the certified numerics package (the extension-state UI "
                     "encoding carrying the paper's policy one-for-one, and the stratified "
                     "shuffle; owner 2026-08-26) (`HAFISCAL_WORLD=as-corrected`; "
                     "improvements off, discretionary choices at the paper's "
                     "values). Defined only for the Step-2/Step-5-derived "
                     "exhibits (multiplier, welfare, β estimates, non-targeted "
                     "moments): Step-1 exhibits are world-invariant and the "
                     "Splurge0 exhibits are default-world robustness"),
    }
    STATIC_NO_GENERATOR = {
        "tabular/Calibration.ltx",
        "Tables/calibration.tex",
        "Tables/calibrationRecession.tex",
    }
    for raw in open(MANIFEST):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        rel, provenance = parts[0], (parts[4] if len(parts) > 4 else "?")
        frozen = os.path.join(REPO, rel)
        pub = os.path.join(QE, rel) if qe_ok else None
        cand = candidate_path(rel)
        base = os.path.basename(rel)
        if rel.endswith((".pdf", ".png", ".svg")):
            s_f, s_c = sha(frozen), sha(cand)
            s_p = sha(pub) if pub else None
            figures.append((rel, provenance,
                            "matches published" if s_f == s_p and s_p else
                            ("differs from published" if s_p else "no published copy"),
                            "candidate differs" if s_c and s_c != s_f else
                            ("candidate identical" if s_c else "no candidate")))
            continue
        t_f = parse_tabular(frozen)
        t_p = parse_tabular(pub) if pub else None
        t_c = parse_tabular(cand)
        entry = {"rel": rel, "prov": provenance, "frozen": t_f, "pub": t_p,
                 "cand": t_c, "extras": [], "extras_vintage": []}
        for name, emap in extras:
            entry["extras"].append((name, parse_tabular(os.path.join(REPO, emap[base]))
                                    if base in emap else None))
            # An extra column is a STATIC artifact, not a file any run rewrites, so it goes
            # stale silently while the IMPROVED column tracks the code. On 2026-09-07 the
            # BUGFIXED artifacts were two revisions behind (pre-lambda, pre-BUG-122) and
            # nothing in the report said so. Carry each one's date, and whether it predates
            # the candidate it is printed beside, so a reader is never left to assume.
            if base in emap:
                apath = os.path.join(REPO, emap[base])
                try:
                    amt = os.path.getmtime(apath)
                    cmt = os.path.getmtime(cand) if cand and os.path.exists(cand) else None
                    entry["extras_vintage"].append(
                        (name, emap[base], _stamp(amt), cmt is not None and amt < cmt,
                         _artifact_world(apath), _candidate_world(cand)))
                except OSError:
                    pass
        if t_f is None:
            if "hand-maintained" in provenance or rel in STATIC_NO_GENERATOR:
                wrappers.append((rel, provenance))
            else:
                pending.append((rel, provenance, "frozen file unparseable/missing"))
        elif t_c is None:
            # no candidate: still worth a pub-vs-frozen row
            d_pf = compare_rows(t_p, t_f) if t_p else []
            if d_pf:
                changed.append(entry | {"no_cand": True})
            elif "hand-maintained" in provenance or rel in STATIC_NO_GENERATOR:
                # numbers inlined by hand / no generator: a candidate will
                # never arrive — classify honestly instead of "awaiting".
                wrappers.append((rel, provenance))
            else:
                pending.append(entry | {"no_cand": True})
        else:
            d = compare_rows(t_f, t_c)
            d_pf = compare_rows(t_p, t_f) if t_p else []
            (changed if (d or d_pf) else unchanged).append(entry)

    L = []
    L.append("# UPDATES — published vs bug-fixed vs improved (generated; do not hand-edit)\n")
    L.append(f"Generated by `Code/HA-Models/updates_report.py` at `{head}`. "
             "The paper's rendered exhibits stay frozen (owner ruling 2026-08-23); this "
             "document is the systematic account of what the corrected and the improved "
             "code produce instead, and — in the closing section — of the code changes "
             "behind the numbers.\n")
    L.append("Columns: **PUBLISHED** = as published in QE 17(3) (from the canonical sibling "
             "`../HAFiscal-QE`" + ("" if qe_ok else " — NOT FOUND, column omitted") + ")" +
             ("; " + "; ".join(f"**{n}**" + KNOWN_WORLD_NOTES.get(n, "")
                               for n, _ in extras) if extras else "") +
             "; **IMPROVED** = the `default` world: all bug fixes + the adopted "
             "improvements + the canonical discretionary choices (ESC interpretation, "
             "…) — the `_candidate` output of current code; **DRAFT** = what the "
             "working paper's text renders today, shown only where it is neither the "
             "published nor the improved number (the transitional post-publication "
             "promotions of 2026-07-28), so the annotated PDF's page can be matched to "
             "this table. Each entry states its manifest provenance.\n")

    def emit_entry(e):
        rel, prov = e["rel"], e["prov"]
        L.append(f"\n## `{rel}`\n\n*Rendered in the draft from:* {prov}\n")
        labels = [l for l, _ in (e["frozen"] or [])]
        cols = [("PUBLISHED", e["pub"])]
        cols += [(n, t) for n, t in e.get("extras", [])]
        cols += [("IMPROVED", e["cand"]), ("DRAFT", e["frozen"])]
        cols = [(n, {l: ns for l, ns in t}) if t else (n, None) for n, t in cols]
        ncell = max((len(ns) for _, ns in (e["frozen"] or [("", [])])), default=0)
        headcols = [n for n, t in cols if t is not None]
        for label in labels:
            vals_by_col = {n: (t.get(label) if t else None) for n, t in cols}
            present = [n for n in headcols if vals_by_col.get(n)]
            row_differs = False
            for i in range(ncell):
                seen = {round(vals_by_col[n][i], 10) for n in present
                        if vals_by_col[n] and i < len(vals_by_col[n])
                        and vals_by_col[n][i] is not None}
                if len(seen) > 1:
                    row_differs = True
            if not row_differs:
                continue
            L.append(f"\n**{label or '(row)'}**\n")
            L.append("| column | " + " | ".join(f"c{i+1}" for i in range(ncell)) + " |")
            L.append("|" + "---|" * (ncell + 1))
            for n in headcols:
                ns = vals_by_col.get(n)
                if n == "DRAFT":
                    # transitional vintage only: drop the row when the draft
                    # renders the published or the improved numbers
                    same = lambda m: (vals_by_col.get(m) is not None and
                                      [round(x, 10) if x is not None else None for x in vals_by_col[m]]
                                      == [round(x, 10) if x is not None else None for x in (ns or [])])
                    if same("PUBLISHED") or same("IMPROVED"):
                        continue
                cells = [fmt(ns[i]) if ns and i < len(ns) else "—" for i in range(ncell)]
                L.append(f"| {n} | " + " | ".join(cells) + " |")
        if e.get("no_cand"):
            L.append("\n*(no `_candidate` yet — differences shown are "
                     "published-vs-draft only)*")
        for name, apath, adate, older, aworld, cworld in e.get("extras_vintage", []):
            # 2026-09-07 evening: a later candidate from a DIFFERENT world (the income-strata engine
            # adopted in `default` only) does not make an as-corrected artifact stale; say which
            # case this is instead of flagging every date difference as staleness.
            if older and aworld and cworld and aworld != cworld:
                vint = (f" — the candidate printed beside it is a later run of the `{cworld}` world; "
                        f"this artifact is the `{aworld}` world's, and stays current until that world "
                        f"is re-run (a change confined to `{cworld}` leaves it as it is)")
            elif older:
                vint = (" — OLDER than the candidate printed beside it, so it does not "
                        "carry any change made since that date; refreshing it needs a run "
                        "in that world, not a regeneration of this report")
            else:
                vint = ""
            note = f"\n*({name} is the static artifact `{apath}`, dated **{adate}**" + vint + ".)*"
            L.append(note)
        missing_extras = [n for n, t in e.get("extras", []) if t is None]
        if missing_extras:
            L.append("\n*(" + ", ".join(f"**{n}**" for n in missing_extras) +
                     ": no artifact for this exhibit — column omitted; see the "
                     "column legend for where this world is defined)*")

    L.append(f"\n---\n\n# Changed exhibits ({len(changed)})\n")
    for e in changed:
        emit_entry(e)
    L.append(f"\n---\n\n# Unchanged exhibits ({len(unchanged)})\n")
    for e in unchanged:
        L.append(f"- `{e['rel']}` — improved matches the draft; the draft matches published"
                 if e["pub"] else f"- `{e['rel']}` — improved matches the draft")
    L.append(f"\n# Awaiting candidates ({len(pending)})\n")
    for p in pending:
        rel = p["rel"] if isinstance(p, dict) else p[0]
        L.append(f"- `{rel}`")
    by_base = {}
    for e in changed + unchanged:
        if isinstance(e, dict):
            stem = os.path.splitext(os.path.basename(e["rel"]))[0]
            by_base.setdefault(stem, e["rel"])
    changed_all = [f for f in figures if f[3] == "candidate differs"]
    changed_figs = [f for f in changed_all if os.path.basename(f[0]) in PUBLISHED_PAPER_FIGURES]
    fig_page = {f[0]: k + 1 for k, f in enumerate(changed_figs, start=1)}
    L.append(f"\n# Figures ({len(figures)}) — SHA comparison; {len(changed_all)} changed, "
             f"{len(changed_figs)} of them in the published paper\n")
    L.append("A figure counts as changed when its improved candidate differs from the copy the "
             f"text renders. Each changed figure OF THE PUBLISHED PAPER (Figures 1–6 of QE 17(3)) has a "
             f"page in **[`{FIGDOC_PDF}`]({FIGDOC_PDF})** (built by `make pdf-annotated`) showing the "
             "published figure from `../HAFiscal-QE` beside the improved one on the same axes (the "
             "candidate is regenerated under the published-axes lock, `Code/HA-Models/fig_axes.py`; "
             "clipping is stated on the page). Figures of the supplemental no-splurge appendix are "
             "compared by SHA only. The annotated paper's figure badges link to the same pages.\n")
    for rel, prov, vs_pub, vs_cand in figures:
        if rel in fig_page:
            link = f" → [{FIGDOC_PDF} p. {fig_page[rel]}]({FIGDOC_PDF}#page={fig_page[rel]}); {_axes_note(rel)}"
            if exhibit_note(rel):
                link += f" — **{exhibit_note(rel)}**"
        elif vs_cand == "candidate differs":
            link = " — not in the published paper (supplemental appendix): no comparison page"
        else:
            link = ""
        L.append(f"- `{rel}` — {vs_pub}; {vs_cand}  *({prov})*{link}")
    write_figures_doc(changed_figs, head)
    # The online appendix's hand-typed tables (no manifest row): published beside the re-issued candidates.
    appendix_lines, appendix_ok = appendix_section()
    L.extend(appendix_lines)
    L.extend(text_notes_section())
    L.extend(what_changed_section())
    # Wrappers/static exhibits go LAST (owner 2026-08-26): housekeeping, not results.
    L.append(f"\n---\n\n# Hand-maintained wrappers & static exhibits ({len(wrappers)})\n")
    L.append("Numbers in these are inlined by hand, or the exhibit has no in-repo "
             "generator — no `_candidate` will ever appear. Where a generator-side "
             "twin exists, the content comparison lives at that entry.\n")
    for rel, prov in wrappers:
        twin = by_base.get(os.path.splitext(os.path.basename(rel))[0])
        L.append(f"- `{rel}` — {prov}" +
                 (f"; see `{twin}`" if twin and twin != rel else ""))
    L.append("")
    open(args.out, "w").write("\n".join(L))
    # U3 annotations map: one csname per changed exhibit, keyed on the include
    # path exactly as the wrapper edef's it at a root build (\latexroot = ".").
    A = ["% GENERATED by Code/HA-Models/updates_report.py -- do not hand-edit.",
         "% Values are the badge's pointer text: tables -> UPDATES.md entry; figures -> the",
         "% UPDATES-figures.pdf page (\\href; hyperref is loaded by the paper's style).",
         "% Keys: ./<manifest-rel-path>; consumed by the annotated build",
         "% (@local/local-qe-figs-and-tables.sty, make pdf-annotated)."]
    for n, e in enumerate(changed, start=1):
        # \latexroot varies by include depth (./ at root, ../ from Tables/, ...):
        # one key per plausible prefix so the lookup matches every build shape.
        for pref in (".", "..", "../.."):
            A.append(r"\expandafter\gdef\csname HFupd@%s/%s\endcsname"
                     r"{UPDATES.md, Changed exhibits entry %d}" % (pref, e["rel"], n))
    # Changed FIGURES: \frozenORcandidate badges the panel and links to the page of
    # UPDATES-figures.pdf that shows the published and the improved version side by side
    # (owner 2026-08-26). The link is relative: keep the two PDFs in one directory.
    for rel, pg in fig_page.items():
        note = exhibit_note(rel)
        figure_level = note and os.path.splitext(os.path.basename(rel))[0] in FIGURE_LEVEL_NOTES
        tail = (" --- " + note.replace("%", r"\%")) if (note and not figure_level) else ""
        for pref in (".", "..", "../.."):
            A.append(r"\expandafter\gdef\csname HFupd@%s/%s\endcsname"
                     r"{\href{%s\#fig%d}{%s} p.~%d (published vs improved)%s}"
                     % (pref, rel, FIGDOC_PDF, pg - 1, FIGDOC_PDF, pg, tail))
            if figure_level:   # fired once at \end{figure} by the annotated build
                A.append(r"\expandafter\gdef\csname HFupdfig@%s/%s\endcsname{%s}"
                         % (pref, rel, note.replace("%", r"\%")))
    # A hand-maintained wrapper renders the exhibit in the paper even though the
    # content change is tracked at its generator-side twin — badge the wrapper's
    # include path too, pointing at the twin's entry.
    changed_idx = {e["rel"]: n for n, e in enumerate(changed, start=1)}
    for rel, prov in wrappers:
        n = changed_idx.get(by_base.get(os.path.splitext(os.path.basename(rel))[0]))
        if n:
            for pref in (".", "..", "../.."):
                A.append(r"\expandafter\gdef\csname HFupd@%s/%s\endcsname"
                         r"{UPDATES.md, Changed exhibits entry %d}" % (pref, rel, n))
    # The online appendix: badge its section head (the sty attaches it; no hook in the appendix source).
    if appendix_ok:
        A.extend(appendix_annotations())
    A.extend(text_note_annotations())   # notes on the TEXT (section-head boxes)
    open(args.annotations_out, "w").write("\n".join(A) + "\n")
    print(f"wrote {args.out}: {len(changed)} changed, {len(unchanged)} unchanged, "
          f"{len(pending)} pending, {len(wrappers)} wrappers/static, "
          f"{len(figures)} figures ({len(changed_figs)} changed -> {FIGDOC_TEX}); "
          f"appendix section {'rendered' if appendix_ok else 'UNAVAILABLE'}; "
          f"annotations -> {args.annotations_out}")


if __name__ == "__main__":
    main()
