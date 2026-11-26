#!/usr/bin/env python3
"""BC5 exp 0412 (README section 25): threads, cores and the CPU's clock during a run. Read-only, on the host.
Every 250 ms, for every thread of the emulator: "T <monotonic s> <tid> <last cpu> <utime> <stime> <run ns> <runqueue ns>"
(ticks at HZ, schedstat). Every second: "F <monotonic s> <MHz of cpu0> <MHz of cpu1> ..." from /proc/cpuinfo and
"K <monotonic s> <k10temp millidegrees>". Every 5 s: "P <monotonic s> <pid> <utime+stime> <comm>" for every other
process that used CPU since the last line. At <names at s> after the emulator's start, once: for every thread
"N <tid> <policy> <rt priority> <priority> <nice> <cpus allowed list> | <comm>".
The header gives HZ, the CPU topology (which logical CPUs are siblings) and the emulator's start.
usage: thr0412.py <out file> <seconds> <names at s>"""
import glob
import os
import subprocess
import sys
import time


def rd(p):
    try:
        return open(p).read()
    except OSError:
        return ""


def main():
    out_path, secs, names_at = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    pid = None
    for _ in range(90):
        r = subprocess.run(["pgrep", "-o", "^kyty_emulator"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            pid = int(r.stdout.split()[0])
            break
        time.sleep(2)
    with open(out_path, "a", buffering=1 << 16) as out:
        if pid is None:
            out.write("# no emulator in 180 s\n")
            return
        sib = sorted({rd(p).strip() for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology/thread_siblings_list")})
        start = time.monotonic()
        out.write(f"# thr0412: emulator {pid}, HZ {os.sysconf('SC_CLK_TCK')}, monotonic {start:.3f}, siblings {' '.join(sib)}\n")
        temp = next((os.path.dirname(p) + "/temp1_input" for p in glob.glob("/sys/class/hwmon/hwmon*/name") if rd(p).strip() == "k10temp"), None)
        t_end, nxt, k, named, seen = start + secs, start, 0, False, {}
        while os.path.isdir(f"/proc/{pid}") and time.monotonic() < t_end:
            now = time.monotonic()
            try:
                tids = os.listdir(f"/proc/{pid}/task")
            except OSError:
                break
            for t in tids:
                st = rd(f"/proc/{pid}/task/{t}/stat")
                ss = rd(f"/proc/{pid}/task/{t}/schedstat").split()
                if not st or len(ss) < 2:
                    continue
                f = st[st.rindex(")") + 2:].split()
                out.write(f"T {now:.3f} {t} {f[36]} {f[11]} {f[12]} {ss[0]} {ss[1]}\n")
            if k % 4 == 0:
                mhz = [ln.split(":")[1].strip().split(".")[0] for ln in rd("/proc/cpuinfo").splitlines() if ln.startswith("cpu MHz")]
                out.write(f"F {now:.3f} " + " ".join(mhz) + "\n")
                if temp:
                    out.write(f"K {now:.3f} {rd(temp).strip()}\n")
            if k % 20 == 0:
                for p in glob.glob("/proc/[0-9]*/stat"):
                    st = rd(p)
                    if not st:
                        continue
                    q = p.split("/")[2]
                    if q == str(pid):
                        continue
                    f = st[st.rindex(")") + 2:].split()
                    tot = int(f[11]) + int(f[12])
                    if tot != seen.get(q, tot) or q not in seen:
                        if q in seen:
                            out.write(f"P {now:.3f} {q} {tot} {st[st.index('(') + 1:st.rindex(')')]}\n")
                        seen[q] = tot
            if not named and now - start >= names_at - 3:  # the emulator was found some seconds after its start
                named = True
                for t in tids:
                    st, sta = rd(f"/proc/{pid}/task/{t}/stat"), rd(f"/proc/{pid}/task/{t}/status")
                    if not st:
                        continue
                    f = st[st.rindex(")") + 2:].split()
                    allowed = next((ln.split(":")[1].strip() for ln in sta.splitlines() if ln.startswith("Cpus_allowed_list")), "?")
                    out.write(f"N {t} {f[38]} {f[37]} {f[15]} {f[16]} {allowed} | {st[st.index('(') + 1:st.rindex(')')]}\n")
            k += 1
            nxt += 0.25
            d = nxt - time.monotonic()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.monotonic()
        out.write(f"# end {time.strftime('%F %T')}\n")


if __name__ == "__main__":
    main()
