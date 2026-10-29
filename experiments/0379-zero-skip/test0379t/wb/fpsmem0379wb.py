# BC5 experiment 0379, follow-up: a play log's fps counter lines (one per ~1 s, KytyPlus' BC5 flip counter) binned per
# minute of wall clock and joined to the launcher's once-a-minute memory record (play-sample0379t.sh's format).
# Wall clock of a counter line = the play log's "== <date> <time> emulator" start line + its t (seconds since the
# emulator's start; the launcher writes that line right before the exec, so the offset is under a second).
# Prints per minute: mean flips/s, the share of seconds under 15 and under 25 flips/s, the longest gap, then the memory
# sample nearest the minute's end. usage: python -I fpsmem0379wb.py <play log> <mem record>
import re, sys
from datetime import datetime, timedelta
log, mem = sys.argv[1], sys.argv[2]
start, rows = None, []
pat = re.compile(r"^fps counter: t ([0-9.]+) s: (\d+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms")
for line in open(log, errors="replace"):
    m = re.match(r"^== (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) emulator", line)
    if m and start is None: start = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    m = pat.match(line)
    if m: rows.append((float(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4))))
samples = []
for line in open(mem):
    if line.startswith("#"): continue
    f = line.split(); kv = dict(x.split("=", 1) for x in f[1:])
    samples.append((f[0], kv))
day = start.date()
def at(hms): return datetime.combine(day, datetime.strptime(hms, "%H:%M:%S").time())
print(f"start {start}, {len(rows)} counter lines, {sum(r[1] for r in rows)} flips in {sum(r[2] for r in rows):.0f} s "
      f"({sum(r[1] for r in rows) / sum(r[2] for r in rows):.1f} flips/s)")
print("minute  flips/s  <15/s  <25/s  gap>=500ms  longest_ms | memavail swap gtt mount_read psi_mem psi_io")
bins = {}
for t, n, d, g in rows:
    w = start + timedelta(seconds=t); bins.setdefault(w.replace(second=0, microsecond=0), []).append((n, d, g))
allsec = []
for k in sorted(bins):
    b = bins[k]; fl = sum(x[0] for x in b); du = sum(x[1] for x in b)
    r = [x[0] / x[1] for x in b]; allsec += [(k, x) for x in r]
    s = min(samples, key=lambda s: abs((at(s[0]) - (k + timedelta(seconds=60))).total_seconds()))[1]
    print(f"{k:%H:%M}  {fl / du:6.1f}  {100 * sum(x < 15 for x in r) / len(r):4.0f}%  {100 * sum(x < 25 for x in r) / len(r):4.0f}%"
          f"  {sum(x[2] >= 500 for x in b):3d}  {max(x[2] for x in b):7.0f} | {s.get('memavail')} {s.get('swapused')} {s.get('gtt')}"
          f" {s.get('mount_read_1min')} {s.get('psi_mem_full60')} {s.get('psi_io_full60')}")
