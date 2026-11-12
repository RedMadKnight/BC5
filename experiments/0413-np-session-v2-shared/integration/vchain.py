"""g412v's main unit, left out of the shared line: g412d's 5361c8ba through mk0412v.sh's chain, each output against the
box's exp0412/v/out intermediate. Writes steps-v/NN-tag.diff (unified diff of the unit, step by step) and vchain.tsv."""
import difflib
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOX = os.path.join(os.path.dirname(HERE), "box", "exp0412", "v")
MF = r"C:\Users\kjani\Downloads\bc5\bc5-0412\experiments\0412-memory-guardian\memfast"
PY = [sys.executable, "-X", "utf8", "-I", os.path.join(HERE, "runner.py")]
W = os.path.join(HERE, "work", "vchain")
OUT = os.path.join(HERE, "steps-v")
shutil.rmtree(W, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(W)
os.makedirs(OUT)
CHAIN = [("lock", "lk"), ("sect", "se"), ("gap", "gp"), ("buf", "bf"), ("ret", "ra"), ("use", "us"), ("zcat", "zc"),
         ("prot", "pr"), ("nogpu", "ng"), ("nscan", "ns"), ("zpoll", None)]
cur = os.path.join(HERE, "work", "zpolll0412")  # placeholder, replaced below
src = os.path.join(HERE, "work", "v-in.cpp")
shutil.copyfile(os.path.join(os.path.dirname(HERE), "box", "exp0412", "v", "out", "bc5LleAgc-lk.cpp"), os.path.join(W, "unused"))
os.remove(os.path.join(W, "unused"))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


# the input: the tree's unit at step 47 (g412d) = the guard step's output
cur = os.path.join(HERE, "work", "guard0412", "x", "src", "libs", "bc5LleAgc.cpp")
rows = ["NN\tscript\tin\tout\tbox\tsame"]
for i, (tag, suf) in enumerate(CHAIN, 1):
    out = os.path.join(W, "%s.cpp" % tag)
    r = subprocess.run(PY + [os.path.join(MF, "mk%s0412.py" % tag), cur, out], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    box = os.path.join(BOX, "out", "bc5LleAgc-%s.cpp" % suf) if suf else os.path.join(BOX, "src", "bc5LleAgc.cpp")
    m = md5(out) if os.path.exists(out) else "MISSING rc %d %s" % (r.returncode, r.stderr.decode()[-200:])
    rows.append("%02d\tmk%s0412.py\t%s\t%s\t%s\t%s" % (i, tag, md5(cur)[:8], m, md5(box), "yes" if m == md5(box) else "NO"))
    if os.path.exists(out):
        a = open(cur, "rb").read().decode().splitlines(True)
        b = open(out, "rb").read().decode().splitlines(True)
        with open(os.path.join(OUT, "%02d-%s.diff" % (i, tag)), "w", encoding="utf-8", newline="") as f:
            f.writelines(difflib.unified_diff(a, b, "a/src/libs/bc5LleAgc.cpp", "b/src/libs/bc5LleAgc.cpp"))
        cur = out
open(os.path.join(HERE, "vchain.tsv"), "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")
print("\n".join(rows))
