#!/usr/bin/env python3
"""fig_axes.py — lock the axes of regenerated (candidate) figures to the PUBLISHED figures' axes.

Owner ruling 2026-08-26: in the published-vs-improved figure comparison "axes should be the
same in the improved as in the original version". The published figures exist only as PDFs
(no plot data survives in ../HAFiscal-QE), so the published axis limits are RECOVERED from
the PDFs' vector geometry (matplotlib output: the axes patch is a rectangle; tick labels are
positioned text) and stored once in a registry; the figure generators then apply those limits
to every matplotlib axes of a figure whose canonical name is in the registry, just before
saving (hook: FromPandemicCode/generated_output.py; env HAFISCAL_FIG_AXES_LOCK, default on).

Recovery: for each axes frame (x0,y0,x1,y1) in PDF points, the numeric tick labels below the
frame (x ticks) / left of it (y ticks) give (value, position) pairs; a linear fit maps the frame
edges to data limits (matplotlib's ticks are exactly linear in position; residuals ~1e-12).
Log-scale axes are not handled (none of the paper's figures uses one). Multi-panel figures:
each frame is one entry; a generator's axes are matched to frames by their normalized
position in the figure (fraction of page width/height), robust to subplot creation order.

CLI:
  python Code/HA-Models/fig_axes.py build            # registry from ../HAFiscal-QE (all manifest figures)
  python Code/HA-Models/fig_axes.py show <fig.pdf>   # recovered axes of one PDF
"""
from __future__ import annotations
import hashlib
import json
import time
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
QE = os.path.normpath(os.path.join(REPO, "..", "HAFiscal-QE"))
MANIFEST = os.path.join(REPO, "LOCKED_TABLES.manifest")
REGISTRY = os.path.join(HERE, "fig_axes_published.json")
ENV_LOCK = "HAFISCAL_FIG_AXES_LOCK"          # 0 disables the lock
REPORT = os.path.join(HERE, "FromPandemicCode", "Figures", "axes_lock_report.json")

_NUM = re.compile(r"^[−\-]?\d+(\.\d+)?$")


# --------------------------------------------------------------------------- recovery
def extract_axes_from_pdf(path):
    """[{'bbox': [x0,y0,x1,y1] (pt), 'frac': [l,b,r,t] (page fractions), 'xlim', 'ylim',
        'xticks', 'yticks'}] for every axes frame found on page 1 of a matplotlib PDF."""
    import numpy as np
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTCurve, LTLine, LTRect, LTTextLine
    page = next(extract_pages(path, laparams=LAParams(char_margin=1.0, line_margin=0.2)))
    W, H = page.width, page.height
    rects, texts, ticklines = [], [], []

    def walk(o):
        if isinstance(o, LTLine):
            # tick marks: short axis-parallel segments (matplotlib: 3.5pt, outward)
            (ax0, ay0), (ax1, ay1) = o.pts[0], o.pts[-1]
            L = max(abs(ax1 - ax0), abs(ay1 - ay0))
            if 1.5 <= L <= 12 and (abs(ax1 - ax0) < 0.2 or abs(ay1 - ay0) < 0.2):
                ticklines.append((min(ax0, ax1), min(ay0, ay1), max(ax0, ax1), max(ay0, ay1)))
        elif isinstance(o, LTRect):
            rects.append(o.bbox)
        elif isinstance(o, LTCurve) and not isinstance(o, LTLine):
            pts = o.pts
            if pts and len(pts) in (4, 5):
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                rects.append((min(xs), min(ys), max(xs), max(ys)))
        elif isinstance(o, LTTextLine):
            t = o.get_text().strip().replace("−", "-")
            if _NUM.match(t):
                texts.append((float(t), o.bbox))
        if hasattr(o, "_objs"):
            for c in o:
                walk(c)
    for el in page:
        walk(el)
    # candidate frames: big rectangles that are not the page background and not nested
    # duplicates; legends are small, so a 50pt minimum side removes them
    frames = []
    for r in sorted(rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True):
        w, h = r[2] - r[0], r[3] - r[1]
        if w >= 0.98 * W and h >= 0.98 * H:
            continue
        if w < 50 or h < 50:
            continue
        if any(abs(r[0] - f[0]) < 2 and abs(r[1] - f[1]) < 2 and abs(r[2] - f[2]) < 2
               and abs(r[3] - f[3]) < 2 for f in frames):
            continue
        frames.append(r)
    # a rect that CONTAINS two or more other candidates is a figure-level box, not an axes
    # (an axes may legitimately contain ONE box: its legend, or an inset panel)
    def _contains(r, f):
        return f is not r and r[0] <= f[0] + 1 and r[1] <= f[1] + 1 and r[2] >= f[2] - 1 and r[3] >= f[3] - 1
    frames = [r for r in frames if sum(_contains(r, f) for f in frames) < 2]
    out = []
    for (x0, y0, x1, y1) in frames:
        # labels by their glyph-box centre (approximate) ...
        xl = [(v, (b[0] + b[2]) / 2) for v, b in texts
              if b[3] < y0 + 2 and b[1] > y0 - 40 and x0 - 8 <= (b[0] + b[2]) / 2 <= x1 + 8]
        yl = [(v, (b[1] + b[3]) / 2) for v, b in texts
              if b[2] < x0 + 2 and b[0] > x0 - 60 and y0 - 8 <= (b[1] + b[3]) / 2 <= y1 + 8]
        # ... snapped to the nearest tick MARK, whose position is exact: vertical marks
        # touching the bottom edge (x ticks), horizontal marks touching the left edge (y ticks)
        def _dedupe(vals, tol=0.05):
            outv = []
            for v in sorted(vals):
                if not outv or v - outv[-1] > tol:
                    outv.append(v)
            return outv
        xmarks = _dedupe((t[0] + t[2]) / 2 for t in ticklines
                         if abs(t[2] - t[0]) < 0.2 and t[1] <= y0 + 0.5 and t[3] >= y0 - 12
                         and x0 - 1 <= (t[0] + t[2]) / 2 <= x1 + 1)
        ymarks = _dedupe((t[1] + t[3]) / 2 for t in ticklines
                         if abs(t[3] - t[1]) < 0.2 and t[0] <= x0 + 0.5 and t[2] >= x0 - 12
                         and y0 - 1 <= (t[1] + t[3]) / 2 <= y1 + 1)

        def snap(labels, marks):
            outp = []
            for v, c in labels:
                if marks:
                    m = min(marks, key=lambda q: abs(q - c))
                    if abs(m - c) <= 6:
                        outp.append((v, m)); continue
                outp.append((v, c))     # no mark near: keep the (biased) centre
            return outp
        xt, yt = snap(xl, xmarks), snap(yl, ymarks)
        entry = {"bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                 "frac": [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4)]}
        for name, ticks, lo, hi in (("x", xt, x0, x1), ("y", yt, y0, y1)):
            if len(ticks) < 2:
                entry[name + "lim"] = None
                entry[name + "ticks"] = sorted(v for v, _ in ticks)
                continue
            v = np.array([t[0] for t in ticks]); p = np.array([t[1] for t in ticks])
            a, b = np.polyfit(p, v, 1)
            entry[name + "lim"] = [float(a * lo + b), float(a * hi + b)]
            entry[name + "ticks"] = sorted(set(v.tolist()))
            entry[name + "fit_resid"] = float(np.max(np.abs(a * p + b - v)))
        entry["tickmarks"] = {"x": len(xmarks), "y": len(ymarks)}
        out.append(entry)
    # legend boxes survive the size filter but carry no tick marks: drop them when the
    # figure has frames that do (an axes always has marks on at least one side)
    if any(e["tickmarks"]["x"] or e["tickmarks"]["y"] for e in out):
        out = [e for e in out if e["tickmarks"]["x"] or e["tickmarks"]["y"]]
    # a box NESTED in another frame that lacks marks on one side is a legend sitting on
    # that frame's edge (it borrowed the host's marks/labels), not an inset — insets carry
    # their own marks on both sides
    def _inside(e, f):
        a, b = e["bbox"], f["bbox"]
        return e is not f and a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1
    out = [e for e in out if not (any(_inside(e, f) for f in out)
                                  and not (e["tickmarks"]["x"] and e["tickmarks"]["y"]))]
    # ... and a box with limits on ONE side only (a legend sitting on an axis edge) is not
    # an axes either, when the figure has frames with both
    if any(e["xlim"] is not None and e["ylim"] is not None for e in out):
        out = [e for e in out if e["xlim"] is not None and e["ylim"] is not None]
    # geometric order: top-to-bottom, then left-to-right (matches row-major subplot creation)
    out.sort(key=lambda e: (-e["frac"][3], e["frac"][0]))
    return out


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def manifest_figures():
    rels = []
    for raw in open(MANIFEST):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel = line.split("\t")[0]
        if rel.endswith(".pdf"):
            rels.append(rel)
    return rels


def build_registry(out=REGISTRY, qe=QE):
    """Recover the axes of every manifest figure from its PUBLISHED copy in ../HAFiscal-QE."""
    reg = {"_about": ("Axis limits of the PUBLISHED figures (QE 17(3)), recovered from the PDFs in "
                      "../HAFiscal-QE by Code/HA-Models/fig_axes.py; keyed by the figure's canonical "
                      "basename (no extension). Consumed by generated_output.py to lock the axes of "
                      "regenerated figures (HAFISCAL_FIG_AXES_LOCK). Regenerate with "
                      "`python Code/HA-Models/fig_axes.py build`."),
           "figures": {}}
    for rel in manifest_figures():
        src = os.path.join(qe, rel)
        key = _key(rel)
        if not os.path.exists(src):
            reg["figures"][key] = {"source": rel, "error": "no published copy"}
            continue
        try:
            axes = extract_axes_from_pdf(src)
        except Exception as exc:  # keep going; the figure just stays unlocked
            reg["figures"][key] = {"source": rel, "error": f"{type(exc).__name__}: {exc}"}
            continue
        reg["figures"][key] = {"source": rel, "source_sha256": _sha(src), "axes": axes}
    json.dump(reg, open(out, "w"), indent=1)
    return reg


def load_registry(path=REGISTRY):
    if not os.path.exists(path):
        return {}
    return json.load(open(path)).get("figures", {})


# --------------------------------------------------------------------------- the lock
_IMG_EXT = (".pdf", ".png", ".svg", ".jpg", ".jpeg")


def _key(name):
    """Registry key = the figure's basename with only an IMAGE extension stripped
    (`LorenzPoints_CRRA_2.0_R_1.01` keeps its dots — os.path.splitext would eat `.01`)."""
    b = os.path.basename(str(name))
    low = b.lower()
    for ext in _IMG_EXT:
        if low.endswith(ext):
            return b[: -len(ext)]
    return b


def lock_enabled():
    return os.environ.get(ENV_LOCK, "1").strip().lower() not in ("0", "off", "false", "no")


def _match_axes(fig_axes, frames):
    """Pair matplotlib axes with recovered frames. Equal counts: by geometric order
    (top-to-bottom, left-to-right on both sides — robust to tight_layout shifts and to
    inset axes); otherwise greedy nearest by normalized position within half a figure."""
    usable = [f for f in frames if f.get("xlim") is not None and f.get("ylim") is not None]
    def _order(ax):
        p = ax.get_position(); return (-p.y1, p.x0)
    axs = sorted(fig_axes, key=_order)
    frs = sorted(usable, key=lambda f: (-f["frac"][3], f["frac"][0]))
    if len(axs) == len(frs):
        return list(zip(axs, frs))
    pairs, used = [], set()
    for ax in axs:
        p = ax.get_position(); best, bd = None, 1e9
        for i, fr in enumerate(frs):
            if i in used:
                continue
            f = fr["frac"]
            d = abs(p.x0 - f[0]) + abs(p.y0 - f[1]) + abs(p.x1 - f[2]) + abs(p.y1 - f[3])
            if d < bd:
                best, bd = i, d
        if best is not None and bd < 0.5:
            pairs.append((ax, frs[best])); used.add(best)
    return pairs


def lock_axes(fig, name, registry=None, verbose=True):
    """Apply the published limits to `fig` (a Figure or the pyplot module) for canonical
    figure `name` (basename without extension). Returns a report dict or None when the
    lock does not apply. Data beyond the published range is NOT rescaled (the owner's
    rule is identical axes) — it is reported so the comparison document can say so."""
    if not lock_enabled():
        return None
    reg = load_registry() if registry is None else registry
    key = _key(name)
    entry = reg.get(key)
    if not entry or not entry.get("axes"):
        return None
    if not hasattr(fig, "add_axes"):      # the pyplot module (its .axes is a function)
        fig = fig.gcf()
    frames = entry["axes"]
    pairs = _match_axes([ax for ax in fig.axes if ax.get_visible()], frames)
    report = {"name": key, "matched": len(pairs), "frames": len(frames), "overflow": []}
    import numpy as np
    for ax, fr in pairs:
        xlim, ylim = fr["xlim"], fr["ylim"]
        xs, ys = [], []
        for ln in ax.get_lines():
            xd, yd = np.asarray(ln.get_xdata(), float), np.asarray(ln.get_ydata(), float)
            m = np.isfinite(xd) & np.isfinite(yd)
            xs.extend(xd[m].tolist()); ys.extend(yd[m].tolist())
        for coll in ax.collections:           # scatter points
            try:
                off = np.asarray(coll.get_offsets(), float)
                if off.size:
                    xs.extend(off[:, 0].tolist()); ys.extend(off[:, 1].tolist())
            except Exception:
                pass
        if xs and ys:
            over = {}
            tx = 1e-6 * max(abs(xlim[1] - xlim[0]), 1e-12)   # recovered limits carry ~1e-7 noise
            ty = 1e-6 * max(abs(ylim[1] - ylim[0]), 1e-12)
            if min(xs) < xlim[0] - tx or max(xs) > xlim[1] + tx:
                over["x"] = [min(xs), max(xs)]
            if min(ys) < ylim[0] - ty or max(ys) > ylim[1] + ty:
                over["y"] = [min(ys), max(ys)]
            if over:
                report["overflow"].append({"published_xlim": xlim, "published_ylim": ylim, "data": over})
        ax.set_xlim(*xlim); ax.set_ylim(*ylim)
    if verbose:
        msg = f"[fig-axes] {key}: locked {len(pairs)}/{len(frames)} axes to the published limits"
        if report["overflow"]:
            msg += f"; DATA BEYOND the published range on {len(report['overflow'])} axes (clipped, reported)"
        print(msg, flush=True)
    _append_report(report)
    return report


def _append_report(report):
    """Merge one figure's lock report into the persistent registry.

    The registry ACCUMULATES across runs and across producers (the HANK figures come
    from step4/ge.py, the PE ones from several scripts), so an entry can outlive the
    figure it describes.  On 2026-09-05 a stale entry put a false statement into a
    co-author-facing document -- a "DATA BEYOND the published range" clause on the UI
    extension panel whose bounds did not reproduce from the plotted series, and which
    vanished as soon as the figure was regenerated.  Every entry therefore carries the
    wall-clock time it was produced, and `updates_report._axes_note` renders the
    overflow clause only when the entry is at least as new as the figure file it
    describes.  A stale entry is then inert rather than wrong.
    """
    try:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        cur = json.load(open(REPORT)) if os.path.exists(REPORT) else {}
        report = dict(report, stamped=time.time())
        cur[report["name"]] = report
        json.dump(cur, open(REPORT, "w"), indent=1)
    except Exception:
        pass


def main(argv):
    if len(argv) >= 2 and argv[1] == "build":
        reg = build_registry()
        ok = [k for k, v in reg["figures"].items() if v.get("axes")]
        bad = {k: v.get("error") for k, v in reg["figures"].items() if not v.get("axes")}
        multi = [k for k in ok if len(reg["figures"][k]["axes"]) > 1]
        print(f"registry -> {REGISTRY}: {len(ok)} figures with axes ({len(multi)} multi-panel: {multi}); "
              f"{len(bad)} without: {bad}")
        return 0
    if len(argv) >= 3 and argv[1] == "show":
        for e in extract_axes_from_pdf(argv[2]):
            print(json.dumps(e))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
