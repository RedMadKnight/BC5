#!/usr/bin/env python3
# exp 0381: the 01:26 start-up event: rows F677-F678 after F676. usage: python handoff0381e.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rows = (
    "| F677 | **Exp 0379's D2 run (10-30 01:26, binary e1cc0c92, zero skip off, RT on, S6N from a copy of the live saves) "
    "hit the 16:25 job again at t ~57–59 s, before any menu key: TCP read faults at 0x8608c654000–0x8608c65d000, a gfx "
    "timeout and a successful ring reset.** It is the same buffer: dcb #34604, 14,911 dwords, 890 indirect dispatches "
    "with `USER_DATA_5` 0x11 in 887; the same `LOAD_SH_REG_INDEX` 0x909842dc0 at dword 8; no host prefix; the same "
    "`USER_DATA_3/4/5`; the same program 0x909977100 and grid [697 1 1]; ME 0xe15 and IB1 0x38f8 of 0x4138; "
    "`GRBM_STATUS` 0xa04030ac. Only the initiator differs, 0x61 against 0x65, so FORCE_START (H6) is refuted. The same "
    "garbage high half 0x860 from two binaries points to a deterministic source (the title's table or data it points "
    "to) rather than a random stale register. | experiment 0381 (README §8, `raw/hang-0126-emitted-head.txt`; "
    "devcoredump `20261030-012643-devcd1.txt`, ib-timeout `play-20261030-0125` private) | High |\n"
    "| F678 | **Start-up from the maintainer's current saves reproduces the F443 class at ~57–60 s (2 of 2: his 16:25 "
    "start 1 and D2), so a start-up run with `BC5_DIRECT_DISPATCH_JOURNAL=1` can decide where `USER_DATA_0` comes from: "
    "the table (0x860 in it), the CP's table fetch (0x11 in it), or carried state (0x240 not in it).** It needs box "
    "writes this session's classifier refuses; it is listed for the maintainer's morning decision with exp 0379 D2's "
    "invocation plus the journal switch, 120 s or the first timeout. The risk is a gfx timeout; both resets so far "
    "succeeded. | experiment 0381 (README §8) | Plan |\n"
)
m = re.search(r"^\| F676 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + rows + s[m.end():]
s, n = re.subn(r"^(\| F663 \| )", lambda m: m.group(1) + "*Reproduced by F677 (01:26, without FORCE_START).* ", s, count=1, flags=re.M)
assert n == 1
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
