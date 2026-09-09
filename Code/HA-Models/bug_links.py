#!/usr/bin/env python3
"""Owner rule 2026-08-27: every mention of a bug carries a link to its record in HAFiscal-Latest. This rewrites bare
`BUG-NNN` (and `BUG-NNN/MMM`) mentions in a markdown file into links to the record on GitHub (the current branch), leaving
mentions that are already inside a link or a code span alone. Usage: python bug_links.py FILE.md [FILE2.md ...]
The link target is the repo file `BUGS_private/HAFiscal_BUG-NNN_*.md`; the URL is
https://github.com/llorracc/HAFiscal-Latest/blob/<branch>/BUGS_private/<file>.
"""
import glob, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRANCH = subprocess.run(["git", "-C", REPO, "branch", "--show-current"], capture_output=True, text=True).stdout.strip() or "master"
BASE = f"https://github.com/llorracc/HAFiscal-Latest/blob/{BRANCH}/BUGS_private/"


def record_for(num):
    fs = sorted(glob.glob(os.path.join(REPO, "BUGS_private", f"HAFiscal_BUG-{num}_*.md")))
    return os.path.basename(fs[0]) if fs else None


def link(num):
    f = record_for(num)
    return f"[BUG-{num}]({BASE}{f})" if f else f"BUG-{num}"


def rewrite(text):
    out, i = [], 0
    # protect code spans and existing links: split on them and only rewrite the plain segments
    pattern = re.compile(r"(`[^`]*`|\[[^\]]*\]\([^)]*\))")
    for seg in pattern.split(text):
        if seg.startswith("`") or (seg.startswith("[") and "](" in seg):
            out.append(seg); continue
        seg = re.sub(r"\bBUG-(\d{3})/(\d{3})\b", lambda m: link(m.group(1)) + "/" + link(m.group(2)), seg)
        seg = re.sub(r"\bBUG-(\d{3})\b", lambda m: link(m.group(1)), seg)
        out.append(seg)
    return "".join(out)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = open(p).read()
        # a bug record's own H1 title ("# BUG-NNN: ...") is never self-linked (2026-08-28)
        head, sep, rest = s.partition("\n")
        t = (head + sep + rewrite(rest)) if re.match(r"# BUG-\d{3}\b", head) else rewrite(s)
        if t != s:
            n_new = len(re.findall(r"\[BUG-", t)) - len(re.findall(r"\[BUG-", s))
            open(p, "w").write(t); print(f"{p}: {n_new} links added")
        else:
            print(f"{p}: no change")
