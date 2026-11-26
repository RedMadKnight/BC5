#!/usr/bin/env python3
"""BC5 exp 0412 (README section 23): the outside half of the gap classifier. Read-only, on the host, no ptrace.
Every 20 ms it reads, for the emulator's threads named on the command line, /proc/<pid>/task/<tid>/stat, schedstat and
syscall, and writes one line per thread:
  <CLOCK_MONOTONIC s> <thread index> <state> <utime> <stime> <minflt> <majflt> <blkio ticks> <run ns> <runqueue ns> <syscall>
<syscall> is "run" for a running thread, the number and the first two arguments (hex) of the system call it is
blocked in ("202:7f..:89" is a futex wait on that address), "-1" when it is blocked outside a system call (a page
fault), "?" when the file cannot be read. utime/stime are in clock ticks (the header gives HZ). The header also lists
the indexes. It waits up to 180 s for the emulator and ends when the emulator ends or after <seconds>.
usage: gapsamp0412.py <out file> <seconds> <thread name> [<thread name> ...]   (a name is the thread's comm, e.g. "Render Thread")"""
import os
import subprocess
import sys
import time


def find_pid():
    for _ in range(90):
        r = subprocess.run(["pgrep", "-o", "^kyty_emulator"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.split()[0])
        time.sleep(2)
    return None


def tids(pid, names):
    out = {}
    try:
        for t in os.listdir(f"/proc/{pid}/task"):
            try:
                c = open(f"/proc/{pid}/task/{t}/comm").read().rstrip("\n")
            except OSError:
                continue
            if c in names and c not in out:
                out[c] = t
    except OSError:
        pass
    return out


def main():
    out_path, secs, names = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
    assert names, __doc__
    pid = find_pid()
    with open(out_path, "a", buffering=1 << 16) as out:
        if pid is None:
            out.write("# no emulator in 180 s\n")
            return
        out.write(f"# gapsamp0412: emulator {pid}, HZ {os.sysconf('SC_CLK_TCK')}, every 20 ms, threads: " + "; ".join(f"{i}={n}" for i, n in enumerate(names)) + "\n")
        t_end = time.monotonic() + secs
        known, next_look = {}, 0.0
        step = 0.020
        nxt = time.monotonic()
        while os.path.isdir(f"/proc/{pid}"):
            now = time.monotonic()
            if now >= t_end:
                break
            if len(known) < len(names) and now >= next_look:
                known = tids(pid, names)
                next_look = now + 1.0
            for i, n in enumerate(names):
                t = known.get(n)
                if t is None:
                    continue
                base = f"/proc/{pid}/task/{t}/"
                try:
                    st = open(base + "stat").read()
                    f = st[st.rindex(")") + 2:].split()
                    ss = open(base + "schedstat").read().split()
                except (OSError, ValueError):
                    known.pop(n, None)
                    continue
                try:
                    sc = open(base + "syscall").read().split()
                    sysc = "run" if sc[0] == "running" else (sc[0] if sc[0] == "-1" else f"{sc[0]}:{sc[1][2:]}:{sc[2][2:]}")
                except (OSError, IndexError):
                    sysc = "?"
                # f[0] state, f[7] minflt, f[9] majflt, f[11] utime, f[12] stime, f[39] delayacct_blkio_ticks
                out.write(f"{time.monotonic():.4f} {i} {f[0]} {f[11]} {f[12]} {f[7]} {f[9]} {f[39]} {ss[0]} {ss[1]} {sysc}\n")
            nxt += step
            d = nxt - time.monotonic()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.monotonic()
        out.write(f"# end {time.strftime('%F %T')}\n")


if __name__ == "__main__":
    main()
