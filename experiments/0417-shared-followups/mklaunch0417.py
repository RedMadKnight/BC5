#!/usr/bin/env python3
"""BC5 experiment 0417: play-pkg-log.sh and play-pkg-quiet.sh made again from the current play-pkg.sh.

Read on the box on 2026-11-13 (read only): play-pkg-log.sh 5080d2ce and play-pkg-quiet.sh 48fa60ba are copies of
play-pkg.sh from 2026-10-16, last changed 2026-10-26. Against play-pkg.sh 157021e3 each lacks more than 90 lines
(the lean switch, BC5_EMU, the TF ring, the reflections' settings, the RT-on guards, the start delay, the unpacked
title, `ulimit -c 0`, the title's 20 switch words, ...) and has only this of its own:
  play-pkg-log.sh    the guest's printf goes to a file in the capture directory (--printf-direction File)
  play-pkg-quiet.sh  the same, and BC5_LOGGING=0 with no timing, no frame profile and no per-second counters
So patching them line by line would leave them stale. This script takes play-pkg.sh (pinned 157021e3) and makes the
two files from it with only those differences. NOT INSTALLED: the launchers change on the maintainer's own word. No
desktop shortcut names either file (only old run scripts in ~/bc5-work do).
usage: mklaunch0417.py <play-pkg.sh> <out dir>"""
import hashlib
import sys

src, out = sys.argv[1:3]
base = open(src, "rb").read()
assert hashlib.md5(base).hexdigest() == "157021e3c7adc36f93170369c63056a6" and b"\r" not in base


def make(name, edits):
    s = base
    for old, new in edits:
        assert s.count(old) == 1, (name, old[:60], s.count(old))
        s = s.replace(old, new)
    open(out + "/" + name, "wb").write(s)
    print(name, hashlib.md5(s).hexdigest())


HEAD = b"#!/usr/bin/env bash\n"
EMU_OLD = b'  "$EMU" --game "$M" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1\n'
EMU_NEW = (b'  PRINTF_OUT=${BC5_GC_DUMP_DIR:+$BC5_GC_DUMP_DIR/../guest-printf.txt}; PRINTF_OUT=${PRINTF_OUT:-$HOME/bc5-work/play-pkg-guest-printf.txt}  # %s: the guest\'s printf (beside the capture; a fixed file with BC5_LEAN=1)\n'
           b'  "$EMU" --game "$M" --printf-direction File --printf-output-file "$PRINTF_OUT" --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1\n')

make("play-pkg-log.sh", (
    (HEAD, HEAD + b"# BC5 play-pkg-log.sh: play-pkg.sh (157021e3) with the guest's printf written to a file (exp 0417's mklaunch0417.py; first made 2026-10-16 for the save data diagnosis)\n"),
    (EMU_OLD, EMU_NEW % b"play-pkg-log.sh"),
))
make("play-pkg-quiet.sh", (
    (HEAD, HEAD + b"# BC5 play-pkg-quiet.sh: play-pkg.sh (157021e3) with the logging switch off (exp 0172) and the guest's printf written to a file (exp 0417's mklaunch0417.py)\n"),
    (b'  export BC5_GC_DUMP_DIR=$HOME/bc5-data/captures/play-$(date +%Y%m%d-%H%M)/gc BC5_DIRECT_TIMING=1 BC5_DIRECT_FRAME_PROFILE=1\n',
     b'  export BC5_GC_DUMP_DIR=$HOME/bc5-data/captures/play-$(date +%Y%m%d-%H%M)/gc BC5_LOGGING=0  # play-pkg-quiet.sh (exp 0172): no journal, the logging switch off; no timing, no frame profile\n'),
    (b'[ "${BC5_LEAN:-0}" = 1 ] || export KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1  # exp 0177: none with BC5_LEAN=1\n',
     b'# play-pkg-quiet.sh: no per-second counters (play-pkg.sh sets KYTY_BC5_FPS_COUNTER, KYTY_BC5_AUDIO_TRACE and KYTY_BC5_MEASURE here)\n'),
    (EMU_OLD, EMU_NEW % b"play-pkg-quiet.sh"),
))
