#!/usr/bin/env python3
# BC5 experiment 0380 (F595): s6n0380rec.sh, the part A smoke run, made from s6n0380w.sh by literal edits only: its
# directory ~/bc5-work/exp0380rec/run, its lock text "top exp 0380 | rec build run", and the binary
# ~/bc5-work/exp0380rec/bin/kyty_emulator (the shared objects with the recorder's bc5LleAgc.cpp object, the shared
# archive; build0380x.py), md5 pinned. The recorder's switches come in through BC5_0368_SWITCHES.
# usage: python3 mk-s6n0380rec.py s6n0380w.sh s6n0380rec.sh <binary md5>
import re
import sys

src, out, md5 = sys.argv[1:4]
assert re.fullmatch(r"[0-9a-f]{8}", md5)
t = open(src, encoding="utf-8").read()
old = ("BIN=$W/exp0380w/kyty_emulator; WANT=${BC5_0380_WANT:-c3c8660b}   # exp 0380w: the shared objects + archive "
       "eff535ac (link0380r.py), no zero skip")
assert t.count(old) == 1, "binary line"
t = t.replace(old, f"BIN=$W/exp0380rec/bin/kyty_emulator; WANT=${{BC5_0380_WANT:-{md5}}}   # exp 0380rec: the shared objects "
                   "with the recorder's bc5LleAgc.cpp object, the shared archive (build0380x.py)")
n1 = t.count("exp0380w/run")
t = t.replace("exp0380w/run", "exp0380rec/run")
n2 = t.count("top exp 0380 | wb run")
t = t.replace("top exp 0380 | wb run", "top exp 0380 | rec build run")
n3 = t.count("private exp0380w $WANT")
t = t.replace("private exp0380w $WANT", "private exp0380rec $WANT")
assert "exp0380w" not in t, "an exp0380w path is left"
assert n2 == 3 and n3 == 1, (n2, n3)
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written (paths {n1}, lock text {n2}, lock detail {n3})")
