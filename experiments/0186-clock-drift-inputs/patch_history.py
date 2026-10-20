#!/usr/bin/env python3
# For each commit since a date that changed the KytyPlus patch: which source files' sections changed
# against the previous patch version, with added/removed line counts of the section diff.
import subprocess, sys, difflib
REPO = sys.argv[1]; SINCE = sys.argv[2]
P = "backend/kytyplus-patches/0001-bc5-lle-agc.patch"
FOCUS = sys.argv[3].split(",") if len(sys.argv) > 3 else []


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def sections(text):
    out = {}; cur = None; buf = []
    for line in text.splitlines():
        if line.startswith("diff --git "):
            if cur: out[cur] = buf
            cur = line.split(" b/")[-1]; buf = []
        elif cur:
            buf.append(line)
    if cur: out[cur] = buf
    return out


commits = git("log", "--reverse", "--since=" + SINCE, "--pretty=%h|%ad|%s", "--date=format:%m-%d %H:%M", "--", P).splitlines()
first = commits[0].split("|")[0]
prev = sections(git("show", first + "~1:" + P))
for c in commits:
    h, d, s = c.split("|", 2)
    cur = sections(git("show", h + ":" + P))
    print("%s %s %s" % (h, d, s[:110]))
    for f in sorted(set(prev) | set(cur)):
        a, b = prev.get(f, []), cur.get(f, [])
        if a == b: continue
        add = rem = 0
        for l in difflib.unified_diff(a, b, lineterm="", n=0):
            if l.startswith("+++") or l.startswith("---") or l.startswith("@@"): continue
            if l.startswith("+"): add += 1
            elif l.startswith("-"): rem += 1
        print("     %-60s +%d -%d" % (f, add, rem))
        if any(x in f for x in FOCUS):
            for l in difflib.unified_diff(a, b, lineterm="", n=0):
                if l.startswith("+++") or l.startswith("---"): continue
                # lines of the patch section that changed: show the code lines (strip patch '+')
                if l.startswith("@@"): continue
                t = l[1:]
                if t.startswith("+") or t.startswith("-") or t.startswith(" "):
                    t2 = t[1:].strip()
                    if t2.startswith("//") or not t2: continue
                print("        " + l[:1] + " " + t[:150])
    prev = cur
