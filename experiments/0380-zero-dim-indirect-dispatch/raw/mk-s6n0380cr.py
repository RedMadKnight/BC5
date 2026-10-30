#!/usr/bin/env python3
# BC5 experiment 0380 (F610): s6n0380cr.sh, the crash-reproduction run, made from s6n0380nc.sh by literal edits only:
# the SHARED normal build (read only, md5 pinned), a save copy and an input script given by the caller
# (BC5_0380_SAVES, BC5_0380_CMD), its directory ~/bc5-work/exp0380cr/run and its lock text "top exp 0380 | crash repro run".
# usage: python3 mk-s6n0380cr.py s6n0380nc.sh s6n0380cr.sh
import sys

src, out = sys.argv[1:3]
t = open(src, encoding="utf-8").read()


def rep(old, new, n=1):
    global t
    assert t.count(old) == n, (t.count(old), old[:80])
    t = t.replace(old, new)


rep("BIN=$W/exp0380nc/bin/kyty_emulator; WANT=${BC5_0380_WANT:-99d91d2d}   # exp 0380nc: the shared objects with bc5LleAgc.cpp = exp 0379's zero skip + the recorder, the shared archive (build0380nc.sh)",
    "BIN=$W/kytyplus-build/src/kyty_emulator; WANT=${BC5_0380_WANT:-58c4a627}   # exp 0380cr: the shared normal build, only read")
rep("SAVES=$W/exp0196/saves-before-152617", "SAVES=${BC5_0380_SAVES:?a private save copy}; CMD=${BC5_0380_CMD:?an input script}   # exp 0380cr")
rep('[ -f "$W/exp0203/o2-continue.cmd" ]', '[ -f "$CMD" ]')
rep('cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"', 'cp "$CMD" "$E/in-$TAG.cmd"')
n1 = t.count("exp0380nc")
t = t.replace("exp0380nc", "exp0380cr")
rep("top exp 0380 | noclear build run", "top exp 0380 | crash repro run", 3)
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written ({n1} renames)")
