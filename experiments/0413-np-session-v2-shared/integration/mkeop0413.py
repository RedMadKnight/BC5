#!/usr/bin/env python3
"""BC5 experiment 0413: BC5_R3_SUBMIT_EOP_EVENT leaves the defaults table (the top session, 2026-11-12, after Codex's
review round). The switch stays in the code and can be given as a launcher word.

Why (Codex's reading of patch 0001, not re-derived here): r3gpu_submit_eop rotates a global ring of 4096 packets;
chain_soft_push keeps the packet's raw address and its callback reads it later, so after the ring wraps a deferred
callback can read another event's packet. Codex has a fix (an owned copy) with a CPU test; it goes in as a separate
commit with its own build and run, and the row can come back then.
usage: mkeop0413.py <switch_defaults.hpp in (md5 ad45cfb9)> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("ad45cfb9"), hashlib.md5(s).hexdigest()
ROW = b'    {"BC5_R3_SUBMIT_EOP_EVENT", "1"},\n'
NOTE = (b"    // BC5_R3_SUBMIT_EOP_EVENT is NOT a default (2026-11-12): its packet ring can be read after a wrap by a deferred\n"
        b"    // callback (Codex's review of exp 0413); a launcher word until the owned-packet fix is in.\n")
assert s.count(ROW) == 1
s = s.replace(ROW, NOTE)
# The set-buffer guard is on in code now (the top: the table is for behaviour choices, not bug fixes): its row goes.
E1 = (b"    // E1: set-buffer guard: no AMM map flavour over mapped memory (exp 0413)\n"
      b'    {"KYTY_BC5_AMM_SETBUFFER_GUARD", "1"},\n')
assert s.count(E1) == 1
s = s.replace(E1, b"")
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
