#!/usr/bin/env python3
"""BC5 exp 0401t: derive replug0401t.sh from exp 0391's replug0391.sh (exp 0372's software replug test).
What differs (each marked "0401t:" in the output): the run is the night runner's (run0401t.sh), recognised by its lock line's
own prefix "water exp 0401t | arm <tag> (" (one line, nothing else in the lock), and the emulator by BC5_0401T_OWNER=<tag> in
its environment (run0401t.sh proves every switch word there); the paths are exp0401t's (its play log, its raw directory).
Every anchor must occur exactly once. usage: mkrep0401t.py <replug0391.sh> <out>"""
import hashlib
import sys

SRC_MD5 = None  # printed, pinned in the README

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8", newline="").read()
reps = [
    ("# BC5 exp 0391: exp 0372's software replug test (raw/replug0372.sh, 2026-10-29) on the shared normal build, under run0391.sh's\n"
     "# token lock.",
     "# BC5 exp 0401t (from exp 0391's replug0391.sh by mkrep0401t.py): exp 0372's software replug test (raw/replug0372.sh,\n"
     "# 2026-10-29) beside a night-runner route (run0401t.sh) on a private build, started by aud0401t.sh. From exp 0391:\n#"),
    ("# What differs from replug0372.sh (marked \"0391:\"): the run is recognised by its exact lock line (E0391_LOCKLINE) and the\n"
     "# emulator by the D19_OWNER token in its environment; private paths under ~/bc5-work/exp0391/run.\n"
     "# Started by run0391.sh with the token; usage: replug0391.sh <tag> [pulls|late]   (waits up to 3 min for the run)\n",
     "# What differs from replug0391.sh (marked \"0401t:\"): the run is run0401t.sh's arm of this tag, recognised by the lock's one\n"
     "# line starting \"water exp 0401t | arm <tag> (\", and the emulator by BC5_0401T_OWNER=<tag> in its environment; the paths\n"
     "# are ~/bc5-work/exp0401t's (its play log, its raw directory). Exp 0391's own \"0391:\" marks stay as they were.\n"
     "# Started by aud0401t.sh; usage: replug0401t.sh <tag> [pulls|late]   (waits up to 3 min for the run)\n"),
    ('TAG=${1:?tag}; MODE=${2:-pulls}; W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0391/run; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log\n'
     'OWNER=${D19_OWNER:?}; LOCKLINE=${E0391_LOCKLINE:?}  # 0391: the run\'s token and lock line\n',
     'TAG=${1:?tag}; MODE=${2:-pulls}; W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0401t; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log  # 0401t: the night runner\'s paths\n'
     'case "$TAG" in *[!A-Za-z0-9]* | "") echo "a tag is letters and digits"; exit 1 ;; esac\n'
     'OWNER=$TAG; LOCKPFX="water exp 0401t | arm $TAG ("  # 0401t: run0401t.sh\'s lock line for this tag, and the owner word aud0401t.sh passes\n'),
    ('ours() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }  # 0391: the exact line\n',
     'ours() { local l; [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && l=$(cat "$LOCK" 2> /dev/null) && [ "$(printf \'%s\\n\' "$l" | grep -c .)" = 1 ] && case "$l" in "$LOCKPFX"*) ;; *) false ;; esac; }  # 0401t: one line, this tag\'s arm\n'),
    ('grep -qxF -- "D19_OWNER=$OWNER" && { echo "$p"; return 0; }',
     'grep -qxF -- "BC5_0401T_OWNER=$OWNER" && { echo "$p"; return 0; }'),
    ('\nours && emu > /dev/null || { say "no s6n0391.sh run under this lock line: nothing done"; exit 1; }\n',
     '\nours && emu > /dev/null || { say "no run0401t.sh run of this tag under the lock: nothing done"; exit 1; }  # 0401t\n'),
]
for a, b in reps:
    n = s.count(a)
    assert n == 1, (a[:80], n)
    s = s.replace(a, b)
# the first wait: the night runner claims, sets up and launches in well under a minute; 3 min as in exp 0391
for marker in ("0401t: the night runner's paths", "0401t: one line, this tag's arm", "BC5_0401T_OWNER=$OWNER", "run0401t.sh run of this tag"):
    assert s.count(marker) == 1, marker
assert "D19_OWNER" not in s and "E0391_LOCKLINE" not in s and "exp0391/run" not in s
open(out, "w", encoding="utf-8", newline="").write(s)
print("source", hashlib.md5(open(src, "rb").read()).hexdigest(), "out", hashlib.md5(s.encode()).hexdigest())
