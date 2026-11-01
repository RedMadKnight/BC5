#!/usr/bin/env python3
"""BC5 exp 0388, the integration: the kit of int0388j.sh, from the host tree and this repository. Writes the candidate patch
0001 into the repository, and into <out>: 0001-new.patch and kit/ (the changed files, manifest.txt, removed-names.txt), and
fills the pins of int0388j.sh. A manifest line: root (H host, B backend, T tools, W the work directory), path, old md5, new md5; - for none.
usage: mkkit.py <host tree> <host base commit> <repo base commit> <out>"""
import hashlib, os, re, subprocess, sys

HOST, HBASE, RBASE, OUT = sys.argv[1:5]
PATCH = "backend/kytyplus-patches/0001-bc5-lle-agc.patch"
SCRIPT = "experiments/0388-job-arena-root/integration/int0388j.sh"


def md(b):
    return hashlib.md5(b).hexdigest()[:8]


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, check=True).stdout


def filtered(b):
    return md(b"".join(x for x in b.splitlines(True) if not x.startswith(b"index ")))


old = git("show", f"{RBASE}:{PATCH}")
new = git("-C", HOST, "diff", "--no-color", "1280a6a", "HEAD")
open(PATCH, "wb").write(new)
open(f"{OUT}/0001-new.patch", "wb").write(new)

lines = []


def add(root, rel, status, oldb, newb):
    path = f"{OUT}/kit/{root}/{rel}"
    if newb is not None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(newb)
    lines.append(f"{root} {rel} {md(oldb) if oldb is not None else '-'} {md(newb) if newb is not None else '-'}\n")


for line in git("-C", HOST, "diff", "--name-status", HBASE, "HEAD", "--", "src").decode().splitlines():
    st, rel = line.split("\t")
    add("H", rel, st, None if st == "A" else git("-C", HOST, "show", f"{HBASE}:{rel}"), None if st == "D" else git("-C", HOST, "show", f"HEAD:{rel}"))
for prefix, root in (("backend/", "B"), ("tools/", "T")):
    for line in git("diff", "--name-status", RBASE, "HEAD", "--", prefix).decode().splitlines():
        st, full = line.split("\t")
        if full.startswith("backend/kytyplus-patches/") or full.endswith(".md"):
            continue
        add(root, full[len(prefix):], st, None if st == "A" else git("show", f"{RBASE}:{full}"), None if st == "D" else git("show", f"HEAD:{full}"))
# The two settings files lose their dead lines.
SET = os.path.dirname(OUT.rstrip("/")) + "/settings/"
add("W", "play-pkg.sh", "M", open(os.path.dirname(OUT.rstrip("/")) + "/kitout/kit/W/play-pkg.sh", "rb").read(), open(SET + "play-pkg.sh", "rb").read())
add("W", "bc5-run.env", "M", open("C:/Users/kjani/Documents/ChatGPT/BC5/coordination/box-read/bc5-run.env", "rb").read(), open(SET + "bc5-run.env", "rb").read())
man = "".join(lines).encode()
open(f"{OUT}/kit/manifest.txt", "wb").write(man)

t = open(SCRIPT, encoding="utf-8", newline="").read()
t = re.sub(r"EXPECT_PATCH=[@A-Za-z0-9]+", "EXPECT_PATCH=" + filtered(old), t)
t = re.sub(r"EXPECT_NEW=[@A-Za-z0-9]+", "EXPECT_NEW=" + md(new), t)
t = re.sub(r"EXPECT_KIT=[@A-Za-z0-9]+", "EXPECT_KIT=" + md(man), t)
open(SCRIPT, "w", encoding="utf-8", newline="").write(t)
print("patch", md(old), "->", md(new), "files", len(lines), "H", sum(x[0] == "H" for x in lines), "B", sum(x[0] == "B" for x in lines), "T", sum(x[0] == "T" for x in lines))
