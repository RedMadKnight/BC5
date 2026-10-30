#!/usr/bin/env python3
# BC5 experiment 0380 (F580): s6n0380m.sh, the memory-type logging run, made from s6n0380w.sh by literal edits only: its
# directory ~/bc5-work/exp0380m/run, its lock text "top exp 0380 | memlog run", and the binary
# ~/bc5-work/exp0380m/kyty_emulator (the shared objects with the logging memory.cpp object, the shared archive;
# build0380m.py), md5 pinned. No switches: the GPU path is the shared build's.
# usage: python3 mk-s6n0380m.py s6n0380w.sh s6n0380m.sh <binary md5>
import re
import sys

src, out, md5 = sys.argv[1:4]
assert re.fullmatch(r"[0-9a-f]{8}", md5)
t = open(src, encoding="utf-8").read()
old = ("BIN=$W/exp0380w/kyty_emulator; WANT=${BC5_0380_WANT:-c3c8660b}   # exp 0380w: the shared objects + archive "
       "eff535ac (link0380r.py), no zero skip")
assert t.count(old) == 1, "binary line"
t = t.replace(old, f"BIN=$W/exp0380m/kyty_emulator; WANT=${{BC5_0380_WANT:-{md5}}}   # exp 0380m: the shared objects "
                   "with the logging memory.cpp object, the shared archive (build0380m.py)")
n1 = t.count("exp0380w/run")
t = t.replace("exp0380w/run", "exp0380m/run")
n2 = t.count("top exp 0380 | wb run")
t = t.replace("top exp 0380 | wb run", "top exp 0380 | memlog run")
n3 = t.count("private exp0380w $WANT")
t = t.replace("private exp0380w $WANT", "private exp0380m $WANT")
assert "exp0380w" not in t, "an exp0380w path is left"
assert n2 == 3 and n3 == 1, (n2, n3)
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written (paths {n1}, lock text {n2}, lock detail {n3})")
