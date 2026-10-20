#!/usr/bin/env python3
# BC5 (experiment 0186): for builds older than the AJM dump (exp 0183). Reads the emulator's
# stderr+stdout, writes each "ajm trace: decode-split" line (KYTY_BC5_AJM_TRACE=1) as an index line
# like KYTY_BC5_AJM_DUMP's ajm-index.txt (seconds since start, instance, written bytes, frames,
# total decoded samples) to the file named by AJM_TS_OUT, and passes every other line through.
import os, re, sys, time
out = open(os.environ["AJM_TS_OUT"], "w", buffering=1)
pat = re.compile(r"inst 0x([0-9a-f]+) .* written (\d+) samples (\d+) frames (\d+)")
t0 = time.monotonic()
for line in sys.stdin.buffer:
    if line.startswith(b"ajm trace: decode-split"):
        m = pat.search(line.decode("ascii", "replace"))
        if m:
            out.write("%.6f %05x %s %s %s\n" % (time.monotonic() - t0, int(m.group(1), 16), m.group(2), m.group(4), m.group(3)))
        continue
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()
