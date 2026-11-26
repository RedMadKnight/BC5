#!/usr/bin/env python3
# BC5 (experiment 0200): the emulator's stdout+stderr filter (after exp 0186's ajm_ts.py).
# - "ajm trace: decode-split" lines (KYTY_BC5_AJM_TRACE=1) become index lines in $AJM_TS_OUT, stamped with
#   CLOCK_MONOTONIC: mono, instance, written bytes, frames, total decoded samples (the columns of
#   KYTY_BC5_AJM_DUMP's ajm-index.txt). Other "ajm trace" lines are dropped.
# - "mono <t> amm trace: ..." lines (KYTY_BC5_AMM_TRACE=1, stamped by the host) of the APR path go to $AMM_OUT
#   with the "amm trace: " dropped: submit, read file, finished, waits at, queued behind, resumed. The rest
#   (maps, unmaps, pool, set-buffer) is only counted, one "counts" line a second.
# Everything else goes to stdout, the play log.
import collections, os, re, sys, time
aj = open(os.environ["AJM_TS_OUT"], "w", buffering=1)
am = open(os.environ["AMM_OUT"], "w", buffering=1) if os.environ.get("AMM_OUT") else None
pat = re.compile(r"inst 0x([0-9a-f]+) .* written (\d+) samples (\d+) frames (\d+)")
KEEP = (b"submit ", b"read file", b"submission ", b"resumed submission", b"SHORT read")
counts = collections.Counter(); last = time.monotonic()
for line in sys.stdin.buffer:
    if line.startswith(b"ajm trace: "):
        if line.startswith(b"ajm trace: decode-split"):
            m = pat.search(line.decode("ascii", "replace"))
            if m:
                aj.write("%.6f %05x %s %s %s\n" % (time.monotonic(), int(m.group(1), 16), m.group(2), m.group(4), m.group(3)))
        continue
    if am is not None and line.startswith(b"mono ") and b" amm trace: " in line[:40]:
        head, _, rest = line.partition(b" amm trace: ")
        if rest.startswith(KEEP):
            am.write(head.decode("ascii", "replace") + " " + rest.decode("ascii", "replace").rstrip() + "\n")
        else:
            counts[rest.split(b" ", 1)[0].decode("ascii", "replace")] += 1
        now = time.monotonic()
        if now - last >= 1.0:
            am.write("counts %.3f %s\n" % (now, " ".join("%s=%d" % kv for kv in sorted(counts.items()))))
            counts.clear(); last = now
        continue
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()
