#!/usr/bin/env python3
# BC5 (experiment 0200): did the AJM instance counter wrap in a run? From an AJM index (KYTY_BC5_AJM_DUMP's
# ajm-index.txt or ajm_ts/filt0200's: time, instance hex, written bytes, frames, total decoded samples):
# instances in order of first job, their slot (id & 0x3fff), the times the slot of a newly seen instance falls
# back by more than 8192 (a wrap of the 14-bit counter, KytyPlus ajm.cpp AjmInstanceCreate), and the
# instances that were still decoding when a newer one with the same id started (live reuse). Also the clock
# voice (complete passes of 479,352 samples, F242): its instances, their last job and their first job that
# wrote nothing (with filt0200.py's index, which keeps failed decodes; the DUMP index has none).
# usage: ajm_wrap.py <ajm-index.txt>...
import sys
for path in sys.argv[1:]:
    first, last, jobs, empty = {}, {}, {}, {}
    prev_s, s0, clock = {}, {}, set()
    order = []
    for l in open(path, errors="replace"):
        q = l.split()
        if len(q) < 5:
            continue
        try:
            t = float(q[0]); i = int(q[1], 16); s = int(q[4])
        except ValueError:
            continue
        if i not in first:
            first[i] = t; order.append(i); s0[i] = s
        last[i] = t; jobs[i] = jobs.get(i, 0) + 1
        if int(q[2]) == 0 and i not in empty:  # a job that wrote nothing (the trace index logs those too)
            empty[i] = t
        if i in prev_s and s < prev_s[i]:
            if prev_s[i] - s0[i] == 479352:
                clock.add(i)
            s0[i] = s
        prev_s[i] = s
    if not order:
        print("%s: empty" % path); continue
    wraps = []; maxslot = -1
    for i in order:
        sl = i & 0x3fff
        if maxslot - sl > 8192:
            wraps.append((first[i], i)); maxslot = sl
        maxslot = max(maxslot, sl)
    print("%s: %d instances with decode jobs over %.0f s, slots up to 0x%x, %d wrap(s)%s" % (
        path, len(order), max(last.values()) - min(first.values()), max(i & 0x3fff for i in order), len(wraps),
        "".join(" at %.0f s (0x%x)" % w for w in wraps)))
    for c in sorted(clock):
        print("  clock voice 0x%x: first %.1f s, last job %.1f s, %d jobs, first empty job %s" % (
            c, first[c], last[c], jobs[c], ("%.1f s" % empty[c]) if c in empty else "none"))
