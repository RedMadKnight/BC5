#!/usr/bin/env python3
# BC5 exp 0381: one table per run for the re-read arms. Reads the mount's log (BC5_MOUNT_STATS lines) and optionally the
# per-second sampler, and prints per minute: served, first-time and repeated bytes, the NVMe reads, decode-ahead's use and
# where reads wait. A repeat here is a page that reached the mount twice; with the page cache on it was evicted in between.
# usage: ana-reread.py <mount-log> [sampler-file] [--minute 60]
import re
import sys

STATS = re.compile(r"bc5-mount stats ([\d.]+) s: served (\d+) MiB .*decoded (\d+) blocks (\d+) MiB .*, (\d+) decoded again, from disk (\d+) blocks (\d+) MiB")
REREAD = re.compile(r"bc5-mount reread ([\d.]+) s: first (\d+) MiB \(\+\d+\), again (\d+) MiB \(\+\d+\), age s (\[.*?\]) (\[.*?\]) MiB, distance MiB (\[.*?\]) (\[.*?\]) MiB")
SPANS = re.compile(r"bc5-mount spans ([\d.]+) s: jobs peak (\d+), image (\d+) MiB .*written (\d+) MiB .*block uses (\d+), ahead (\d+) used (\d+)(.*)")
SPAN = re.compile(r", (\w+) (\d+) mean (\d+) us peak (\d+) us")


def parse_mount(lines):
    stats, reread, spans = [], [], []
    for line in lines:
        m = STATS.search(line)
        if m:
            stats.append((float(m[1]), int(m[2]), int(m[4]), int(m[7])))
        m = REREAD.search(line)
        if m:
            reread.append((float(m[1]), int(m[2]), int(m[3]), eval_list(m[5]), eval_list(m[7]), eval_list(m[4]), eval_list(m[6])))
        m = SPANS.search(line)
        if m:
            spans.append((float(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[6]), int(m[7]), {s[0]: (int(s[1]), int(s[2]), int(s[3])) for s in SPAN.findall(m[8])}))
    return stats, reread, spans


def eval_list(text):
    return [float(x) for x in text.strip("[]").split(",")]


def parse_sampler(lines):
    rows = []
    for line in lines:
        if line.startswith("T "):
            f = line.split()
            rows.append((int(f[1]), dict(kv.split("=", 1) for kv in f[2:] if "=" in kv)))
    return rows


def at(series, t):
    """The newest row at or before t."""
    best = None
    for row in series:
        if row[0] <= t:
            best = row
    return best


def table(stats, reread, spans, minute):
    if not stats:
        return ["no stats lines"]
    end = stats[-1][0]
    out = ["min served_MiB image+disk first again again% decoded_MiB disk_MiB ahead_used% queue_us service_us jobs_peak"]
    t = minute
    last_st, last_rr, last_sp = (0, 0, 0, 0), (0, 0, 0), None
    while t < end + minute:
        st = at(stats, t) or last_st
        rr = at(reread, t)
        sp = at(spans, t)
        served = st[1] - last_st[1]
        first = again = 0
        if rr:
            first, again = rr[1] - last_rr[1], rr[2] - last_rr[2]
            last_rr = rr[:3]
        share = 100.0 * again / (first + again) if first + again else 0.0
        used = queue = service = peak = image = 0
        if sp:
            base = last_sp if last_sp else (0, 0, 0, 0, 0, 0, {})
            made = sp[4] - base[4]
            used = 100.0 * (sp[5] - base[5]) / made if made else 0.0
            image = sp[2] - base[2]
            peak = max(r[1] for r in spans if t - minute < r[0] <= t) if any(t - minute < r[0] <= t for r in spans) else 0
            q = [r[6]["queue"] for r in spans if t - minute < r[0] <= t and "queue" in r[6]]
            s = [r[6]["service"] for r in spans if t - minute < r[0] <= t and "service" in r[6]]
            queue = sum(n * mean for n, mean, _ in q) / max(1, sum(n for n, _, _ in q))
            service = sum(n * mean for n, mean, _ in s) / max(1, sum(n for n, _, _ in s))
            last_sp = sp
        out.append("%3d %6d %6d %6d %6d %5.1f %6d %6d %5.0f %6.0f %6.0f %3d" % (t // minute, served, image + st[3] - last_st[3], first, again, share, st[2] - last_st[2], st[3] - last_st[3], used, queue, service, peak))
        last_st = st
        t += minute
    if reread:
        r = reread[-1]
        out.append("repeats by age (s < %s, then older): %s MiB" % (r[5], r[3]))
        out.append("repeats by distance (MiB < %s, then farther): %s MiB" % (r[6], r[4]))
    return out


def sampler_table(rows, minute):
    if len(rows) < 2:
        return []
    t0 = rows[0][0]
    keys = ("pgmajfault", "pswpin", "workingset_refault_file", "pgsteal_direct", "mount_read_bytes", "mount_cpu_ticks", "emu_majflt")
    out = ["min " + " ".join(keys) + " io_full_ms mem_full_ms"]
    last = rows[0][1]
    for start in range(minute, rows[-1][0] - t0 + minute, minute):
        now = at(rows, t0 + start)[1]
        vals = ["%d" % (int(now.get(k, 0)) - int(last.get(k, 0))) for k in keys]
        io = (int(now.get("io_full_us", 0)) - int(last.get("io_full_us", 0))) // 1000
        mem = (int(now.get("memory_full_us", 0)) - int(last.get("memory_full_us", 0))) // 1000
        out.append("%3d %s %d %d" % (start // minute, " ".join(vals), io, mem))
        last = now
    return out


def main(argv):
    minute = 60
    if "--minute" in argv:
        i = argv.index("--minute")
        minute = int(argv[i + 1])
        del argv[i:i + 2]
    with open(argv[1], errors="replace") as f:
        print("\n".join(table(*parse_mount(f), minute)))
    if len(argv) > 2:
        with open(argv[2], errors="replace") as f:
            print("\n".join(sampler_table(parse_sampler(f), minute)))


if __name__ == "__main__":
    main(sys.argv)
