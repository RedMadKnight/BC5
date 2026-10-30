#!/usr/bin/env python3
# BC5 experiment 0380 (F604): s6n0380nc.sh, the "test 0380 noclear" smoke run, made from s6n0380rec.sh by literal edits
# only: its directory ~/bc5-work/exp0380nc/run, its lock text "top exp 0380 | noclear build run", the binary
# ~/bc5-work/exp0380nc/bin/kyty_emulator (build0380nc.sh), md5 pinned, and menu screenshots: from the emulator's start
# a background loop takes full-screen shots (spectacle, the Plasma session) at 80, 86, 87.5, 89 and 200 s into
# ~/bc5-data/captures/exp0380nc/shots/ (private, never the repo): the start screen, the save list, the Continue menu
# (the route's keys come at 85 s) and the game. The switches come in through BC5_0368_SWITCHES.
# usage: python3 mk-s6n0380nc.py s6n0380rec.sh s6n0380nc.sh <binary md5>
import re
import sys

src, out, md5 = sys.argv[1:4]
assert re.fullmatch(r"[0-9a-f]{8}", md5)
t = open(src, encoding="utf-8").read()


def rep(old, new):
    global t
    assert t.count(old) == 1, f"anchor found {t.count(old)} times: {old[:80]!r}"
    t = t.replace(old, new)


rep("BIN=$W/exp0380rec/bin/kyty_emulator; WANT=${BC5_0380_WANT:-b8561eaa}   # exp 0380rec: the shared objects with the "
    "recorder's bc5LleAgc.cpp object, the shared archive (build0380x.py)",
    f"BIN=$W/exp0380nc/bin/kyty_emulator; WANT=${{BC5_0380_WANT:-{md5}}}   # exp 0380nc: the shared objects with "
    "bc5LleAgc.cpp = exp 0379's zero skip + the recorder, the shared archive (build0380nc.sh)")
rep("T0=$(date +%s)\n",
    "T0=$(date +%s)\n"
    "SHOTS=$HOME/bc5-data/captures/exp0380nc/shots; mkdir -p \"$SHOTS\"; chmod 700 \"$HOME/bc5-data/captures/exp0380nc\"   # exp 0380nc: menu shots, private\n"
    "( for s in 80 86 87.5 89 200; do while awk -v n=\"$(date +%s.%N)\" -v t0=\"$T0\" -v s=\"$s\" 'BEGIN {exit !(n - t0 < s)}'; do sleep 0.2; done\n"
    "    pgrep -x kyty_emulator > /dev/null || break\n"
    "    XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o \"$SHOTS/$TAG-$s.png\" > /dev/null 2>&1\n"
    "    echo \"$(date '+%T.%3N') shot $s s: $(stat -c %s \"$SHOTS/$TAG-$s.png\" 2> /dev/null || echo none)\" >> \"$R/$TAG-shots.txt\"; done ) < /dev/null > /dev/null 2>&1 &\n")
n1 = t.count("exp0380rec/run")
t = t.replace("exp0380rec/run", "exp0380nc/run")
n2 = t.count("top exp 0380 | rec build run")
t = t.replace("top exp 0380 | rec build run", "top exp 0380 | noclear build run")
rep("private exp0380rec $WANT", "private exp0380nc $WANT")
assert "exp0380rec" not in t, [l for l in t.splitlines() if "exp0380rec" in l]
assert n2 == 3, n2
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written (paths {n1}, lock text {n2})")
