#!/usr/bin/env python3
# BC5 experiment 0380 (F604): the "test 0380 noclear" launcher from the "test 0380 rec" one (play-pkg-0380rec.sh
# 9aa6f587, itself play-pkg.sh 55531ab6 by mkplay0380rec.pl), by literal, counted edits only:
# - every exp0380rec path becomes exp0380nc (binary, logs, memory sampler);
# - the binary is the combined one (build0380nc.sh: the recorder's part A + exp 0379's zero skip, bc5LleAgc.cpp only);
# - the switches: BC5_0380_REC=1, BC5_DIRECT_PIECES_NO_CLEAR=1 (F603: the full-state prefix without its
#   CONTEXT_CONTROL and CLEAR_STATE), BC5_DIRECT_ZERO_SKIP on exp 0379's fixed list (a private copy); no write-back,
#   FORCE_START, copy, rebase, zero guard, scan or self-test;
# - the log's first line names them, the list's md5 and the binary's md5.
# usage: python3 mkplay0380nc.py <play-pkg-0380rec.sh> <play-pkg-0380nc.sh>
import hashlib
import sys

src, out = sys.argv[1:3]
raw = open(src, "rb").read()
assert hashlib.md5(raw).hexdigest()[:8] == "9aa6f587", hashlib.md5(raw).hexdigest()[:8]
t = raw.decode("utf-8")


def rep(old, new):
    global t
    assert t.count(old) == 1, f"anchor found {t.count(old)} times: {old[:80]!r}"
    t = t.replace(old, new)


rep("EMU=~/bc5-work/exp0380rec/bin/kyty_emulator  # exp 0380rec: shared objects and archive, bc5LleAgc.cpp with the recorder (build0380x.py)",
    "EMU=~/bc5-work/exp0380nc/bin/kyty_emulator  # exp 0380nc: shared objects and archive, bc5LleAgc.cpp with exp 0379's zero skip and the recorder (build0380nc.sh)")
rep("# exp 0380rec (the maintainer's play): the flight recorder's part A after a fence timeout; no exp 0379/0380 fix switch.\n"
    "export BC5_0380_REC=1\n"
    "unset BC5_DIRECT_ARGS_WB BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_COPY BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT BC5_0380_REC_SELFTEST_S BC5_NO_TIMEOUT_PROBE\n",
    "# exp 0380nc (the maintainer's play, F603/F604): the prefix without CONTEXT_CONTROL and CLEAR_STATE, exp 0379's zero skip\n"
    "# on its fixed list, the flight recorder's part A after a fence timeout; no other exp 0379/0380 switch.\n"
    "unset BC5_DIRECT_ARGS_WB BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_COPY BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT BC5_0380_REC_SELFTEST_S BC5_NO_TIMEOUT_PROBE\n"
    "export BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=$HOME/bc5-work/exp0380nc/zero-list-20261029-120000.txt\n")
rep('''  echo "== exp 0380rec: BC5_0380_REC=1; no write-back, FORCE_START, copy, rebase or zero skip; binary $(md5sum < "$EMU" | cut -c1-8)"''',
    '''  echo "== exp 0380nc: BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=$BC5_DIRECT_ZERO_SKIP ($(md5sum < "$BC5_DIRECT_ZERO_SKIP" | cut -c1-8)); no write-back, FORCE_START, copy or rebase; binary $(md5sum < "$EMU" | cut -c1-8)"''')
n = t.count("exp0380rec") + t.count("exp 0380rec")
t = t.replace("exp0380rec", "exp0380nc").replace("exp 0380rec", "exp 0380nc")
assert "0380rec" not in t and n >= 8, n
c = (t.count("BC5_DIRECT_PIECES_NO_CLEAR=1"), t.count("BC5_DIRECT_ZERO_SKIP"))
assert c == (2, 4), c  # the export line, the log line (the list three times there)
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written ({n} path renames)")
