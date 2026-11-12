#!/usr/bin/env python3
"""BC5 experiment 0416: the catcher for exp 0414's ray-tracing hypothesis ("a BVH walk reads a link from a page we left
unbacked; zero looks like a valid link, so the walk need not end"; KytyPS5 6030fde reads such pages as all ones).
Logging only: nothing is filled and nothing in the emulator or the backend changes.

It reads the kernel log as it comes (sudo -n dmesg -w, one of the read-only commands the box allows) while an emulator
runs. For every amdgpu page-fault block (the format of experiments/0016-direct-first-submits/raw/d-run27-dmesg.txt:
"[gfxhub] page fault (...)", "in page starting at address 0x... from client ...", then sometimes "Faulty UTCL2 client
ID: ...", "RW: 0x.") it writes the kernel time, the faulting GPU address, and where that address lies in the emulator
process at that moment (/proc/<pid>/maps; in the direct path a GPU address is the guest address):
  mapped       the page is mapped in the process: the title has memory there, only the GPU mapping is missing
  unmapped     nothing is mapped there: a read of a page nobody backs (the hypothesis' case)
  no-process   no emulator was running when the line came
with the mapping's protection, range and name. The client (TCP = a load by a shader) and read/write follow on their
own lines when the kernel prints them. A repeated address is written the first time and then at every 100th repeat.
Ring timeout and reset lines are copied, so the order "fault, then timeout" (F336, F582) can be read from one file.
The program that did the read is not in the kernel's lines; the host's hang probe names it.
usage (on the box, beside a run): fault0416.py <out file> [seconds, default 900]
       fault0416.py --test <a saved dmesg file>     (prints what it would log; every address reads "no-process")"""
import os
import re
import subprocess
import sys
import time

ADDR = re.compile(r"in page starting at address\s+0x([0-9a-fA-F]+)")
CLIENT = re.compile(r"Faulty UTCL2 client ID:\s*(.+?)\s*$")
RW = re.compile(r"\bRW:\s*0x([01])")
HANG = re.compile(r"amdgpu.*(ring \S+ timeout|GPU reset|reset\S* (succeeded|failed)|VRAM is lost)", re.I)
STAMP = re.compile(r"^\[\s*([0-9.]+)\]")


def emulator():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open("/proc/%s/comm" % d).read().strip() == "kyty_emulator":
                    return int(d)
            except OSError:
                pass
    return None


def where(addr):
    pid = emulator()
    if pid is None:
        return "no-process"
    try:
        for line in open("/proc/%d/maps" % pid):
            f = line.split(None, 5)
            a, b = (int(x, 16) for x in f[0].split("-"))
            if a <= addr < b:
                return "mapped %s %x-%x %s" % (f[1], a, b, f[5].strip() if len(f) > 5 else "(anonymous)")
    except (OSError, ValueError):
        return "maps-unreadable"
    return "unmapped"


def scan(lines, write, where_fn, keep):
    seen = {}
    n = 0
    for line in lines:
        if not keep():
            break
        m = STAMP.match(line)
        t = m.group(1) if m else "?"
        m = ADDR.search(line)
        if m and "amdgpu" in line:
            a = int(m.group(1), 16)
            seen[a] = seen.get(a, 0) + 1
            n += 1
            if seen[a] == 1 or seen[a] % 100 == 0:
                write("%s fault: gpu va 0x%x (%d of this address): %s\n" % (t, a, seen[a], where_fn(a)))
            continue
        m = CLIENT.search(line)
        if m:
            write("%s   client %s\n" % (t, m.group(1)))
            continue
        m = RW.search(line)
        if m and "amdgpu" in line:
            write("%s   %s\n" % (t, "write" if m.group(1) == "1" else "read"))
            continue
        if HANG.search(line):
            write("%s kernel: %s\n" % (t, line.split("]", 1)[-1].strip()[:200]))
    return n, len(seen)


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        n, d = scan(open(sys.argv[2], errors="replace"), sys.stdout.write, lambda a: "no-process", lambda: True)
        print("# %d fault blocks, %d distinct addresses" % (n, d))
        sys.exit(0)
    out = open(sys.argv[1], "w", buffering=1)
    secs = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    p = subprocess.Popen(["sudo", "-n", "dmesg", "-w"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
    t0 = time.time()
    out.write("# fault0416 started %s; the kernel's old lines (printed in the first 2 s) are skipped\n" % time.strftime("%F %T"))

    def fresh():
        for line in p.stdout:
            if time.time() - t0 >= 2:  # dmesg -w first prints the whole buffer
                yield line

    n, d = scan(fresh(), out.write, where, lambda: time.time() - t0 < secs)
    p.terminate()
    out.write("# ended after %.0f s: %d fault blocks, %d distinct addresses\n" % (time.time() - t0, n, d))
