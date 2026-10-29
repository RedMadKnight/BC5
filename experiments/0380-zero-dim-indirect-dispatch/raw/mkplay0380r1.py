#!/usr/bin/env python3
# BC5 experiment 0380 (F611): the second "test 0380 noclear" launcher from the first (play-pkg-0380nc.sh 29c82f19), by
# literal, counted edits only: every exp0380nc path becomes exp0380r1 (binary build0380r1.sh, logs, memory sampler and a
# copy of the same zero list), and BC5_CRASH_FRAMES=1 joins the switches, named in the log's first line. The switches
# are otherwise unchanged: BC5_0380_REC=1, BC5_DIRECT_PIECES_NO_CLEAR=1, BC5_DIRECT_ZERO_SKIP on exp 0379's fixed list.
# usage: python3 mkplay0380r1.py <play-pkg-0380nc.sh> <play-pkg-0380r1.sh>
import hashlib
import sys

src, out = sys.argv[1:3]
raw = open(src, "rb").read()
assert hashlib.md5(raw).hexdigest()[:8] == "29c82f19", hashlib.md5(raw).hexdigest()[:8]
t = raw.decode("utf-8")


def rep(old, new):
    global t
    assert t.count(old) == 1, f"anchor found {t.count(old)} times: {old[:80]!r}"
    t = t.replace(old, new)


rep("export BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=",
    "export BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=")
rep('  echo "== exp 0380nc: BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1',
    '  echo "== exp 0380r1: BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1')
rep("bc5LleAgc.cpp with exp 0379's zero skip and the recorder (build0380nc.sh)",
    "bc5LleAgc.cpp with exp 0379's zero skip and the recorder of F608, runtimeLinker.cpp with BC5_CRASH_FRAMES (build0380r1.sh)")
n = t.count("exp0380nc") + t.count("exp 0380nc")
t = t.replace("exp0380nc", "exp0380r1").replace("exp 0380nc", "exp 0380r1")
assert "0380nc" not in t and n >= 8, n
assert t.count("BC5_CRASH_FRAMES=1") == 2
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written ({n} path renames)")
