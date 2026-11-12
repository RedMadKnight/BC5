#!/usr/bin/env python3
"""BC5 experiment 0416: the catcher for exp 0414's ray-tracing hypothesis ("a BVH walk reads a link from a page we left
unbacked; zero looks like a valid link, so the walk need not end"; KytyPS5 6030fde reads such pages as all ones).
Logging only: nothing is filled and nothing in the emulator or the backend changes.

It reads the kernel log as it comes (sudo -n dmesg -w, one of the read-only commands the box allows) while an emulator
runs. For every amdgpu page-fault block (the format of experiments/0016-direct-first-submits/raw/d-run27-dmesg.txt:
"[gfxhub] page fault (...)", "in page starting at address 0x... from client ...", then sometimes "Faulty UTCL2 client
ID: ...", "RW: 0x.") it writes the kernel time, the faulting GPU address, and a sample of the emulator's CPU address
space at that address.

Which kernel lines belong to this run (Codex, 2026-11-12, R11/R46): the boundary is a kernel timestamp, not the time
a line is received. At the start the newest stamp of the existing log is read (sudo -n dmesg, one shot); the followed
stream is then filtered to lines whose stamp is greater. A fault in the first seconds is kept; a late line of the old
backlog is not. If that first read fails or has no stamp, the catcher follows nothing and writes "MONITOR ERROR"
(exit 2). The stamp says when the kernel wrote a line, not which run caused it. The reader is a thread, so the time
limit and a stop signal are obeyed in silence too, and in a finally block (also on SIGTERM, SIGINT and SIGHUP) the
dmesg child is ended and waited for first, the reader joined with a limit, and the stream closed only after the
reader has ended; anything left over is written as "INCOMPLETE cleanup".

What the sample is and is not (Codex, R13). It is /proc/<pid>/maps of the pinned emulator process, read when the
catcher reads the kernel's line, which is later than the fault. The labels:
  CPU VMA now: present <perms> <range> <name>   a VMA covers the address at the sample time. It may be ---p. It does
                                                not show that pages are backed or that the GPU's page table is right.
  CPU VMA now: none                             no VMA covers it at the sample time. It does not show that the GPU
                                                read zeros, and it does not prove the BVH hypothesis.
  CPU VMA now: unknown (<why>)                  no pinned process, the process is gone, or maps could not be read.
Every sample carries the PID and the wall time of the sample. The process is pinned: --pid N, or else the first
kyty_emulator seen (one that runs at the start, or the first that appears); a later emulator is never sampled. The
kernel's lines do not name the process or the run that faulted, so attribution to a run stays "unknown" here; a
stronger claim needs the fault tied to the run by other means (PASID, the host's hang probe).
The client (TCP = a load by a shader) and read/write follow on their own lines when the kernel prints them. A repeated
address is written the first time and then at every 100th repeat. Ring timeout and reset lines are copied, so the
order "fault, then timeout" (F336, F582) can be read from one file.
usage (on the box, beside a run): fault0416.py <out file> [seconds, default 900] [--pid N]
       fault0416.py --test <a saved dmesg file>     (prints what it would log; every sample reads "unknown")"""
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time

ADDR = re.compile(r"in page starting at address\s+0x([0-9a-fA-F]+)")
CLIENT = re.compile(r"Faulty UTCL2 client ID:\s*(.+?)\s*$")
RW = re.compile(r"\bRW:\s*0x([01])")
HANG = re.compile(r"amdgpu.*(ring \S+ timeout|GPU reset|reset\S* (succeeded|failed)|VRAM is lost)", re.I)
STAMP = re.compile(r"^\[\s*([0-9]+\.[0-9]+)\]")
EOF = object()  # the reader's end


def stamp_of(line):
    m = STAMP.match(line)
    return float(m.group(1)) if m else None


def newest_stamp(lines):
    """The boundary: the newest kernel stamp of the log as it is before the run (-1.0 for an empty log)."""
    newest = -1.0
    for line in lines:
        s = stamp_of(line)
        if s is not None and s > newest:
            newest = s
    return newest


def start_time(pid):
    """Field 22 of /proc/<pid>/stat (start time in clock ticks): tells a reused PID from the pinned process."""
    try:
        return open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def find_emulator():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open("/proc/%s/comm" % d).read().strip() == "kyty_emulator":
                    return int(d)
            except OSError:
                pass
    return None


class Pinned:
    """The one emulator process of this run. Never re-pinned: after it ends every sample is 'unknown'."""

    def __init__(self, pid=None, find=find_emulator, started=start_time):
        self.find, self.started = find, started
        self.pid, self.birth = None, None
        if pid is not None:
            self.pid, self.birth = pid, started(pid)

    def poll(self):
        """Called on every tick: pins the first emulator that is seen. Returns a note for the log, once."""
        if self.pid is None:
            pid = self.find()
            if pid is not None:
                self.pid, self.birth = pid, self.started(pid)
                return "pinned pid %d" % pid
        return None

    def sample(self, addr):
        when = time.strftime("%T") + ".%03d" % (time.time() % 1 * 1000)
        if self.pid is None:
            return "CPU VMA now: unknown (no pinned process; sampled %s)" % when
        head = "pid %d, sampled %s" % (self.pid, when)
        if self.birth is None or self.started(self.pid) != self.birth:
            return "CPU VMA now: unknown (the pinned process is gone; %s)" % head
        try:
            for line in open("/proc/%d/maps" % self.pid):
                f = line.split(None, 5)
                a, b = (int(x, 16) for x in f[0].split("-"))
                if a <= addr < b:
                    return "CPU VMA now: present %s %x-%x %s (%s)" % (f[1], a, b, f[5].strip() if len(f) > 5 else "(anonymous)", head)
        except (OSError, ValueError):
            return "CPU VMA now: unknown (maps unreadable; %s)" % head
        return "CPU VMA now: none (%s)" % head


def scan(get, write, sample, boundary, keep, tick=None):
    """get(timeout) gives a line, None when nothing came in that time, or EOF. keep() is asked at least once per
    timeout, whatever the traffic. Lines whose kernel stamp is not above the boundary are counted and dropped; a line
    without a stamp takes the stamp of the line before it."""
    seen = {}
    n = old = 0
    last = None
    ended = "limit"
    while keep():
        if tick is not None:
            note = tick()
            if note:
                write("# %s\n" % note)
        line = get(0.5)
        if line is None:
            continue
        if line is EOF:
            ended = "reader end"
            break
        s = stamp_of(line)
        if s is None:
            s = last
        last = s
        if s is None or s <= boundary:
            old += 1
            continue
        t = "%.6f" % s
        m = ADDR.search(line)
        if m and "amdgpu" in line:
            a = int(m.group(1), 16)
            seen[a] = seen.get(a, 0) + 1
            n += 1
            if seen[a] == 1 or seen[a] % 100 == 0:
                write("%s fault: gpu va 0x%x (%d of this address): %s; run attribution: unknown\n" % (t, a, seen[a], sample(a)))
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
    return n, len(seen), old, ended


def reader(stream, q):
    try:
        for line in stream:
            q.put(line)
    except (OSError, ValueError):
        pass
    q.put(EOF)


def getter(q):
    def get(timeout):
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None
    return get


def end_child(p, thread=None):
    """End and reap the sudo/dmesg child, then collect the reader. Order (Codex, R46, 22:43 UTC): the child is ended
    first and waited for with a limit; the stream is NOT closed while the reader may still block in it (a close from
    this thread waits for the reader's buffer lock, so in silence it never returned). The reader is joined with a
    limit; only when it has ended is the stream closed. If it has not (sudo could not be signalled, or a descendant
    still holds the pipe), that is said as an incomplete cleanup and nothing blocks."""
    if p is None:
        return "no child"
    try:
        p.terminate()
    except OSError as e:
        said = "terminate failed (%s)" % e.__class__.__name__
    else:
        said = "terminated"
    try:
        said += ", status %d" % p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            p.kill()
            said += ", then killed, status %d" % p.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            said += ", NOT reaped (pid %d)" % p.pid
    if thread is not None:
        thread.join(timeout=3)
    if thread is not None and thread.is_alive():
        return "INCOMPLETE cleanup: child %s; the reader still blocks (something holds the pipe open), stream not closed" % said
    try:
        p.stdout.close()
    except (OSError, ValueError):
        pass
    return ("child %s" % said) if "NOT reaped" not in said and "failed" not in said else "INCOMPLETE cleanup: child %s" % said


def boundary_of(returncode, text):
    """The boundary from the one-shot dmesg, or None when that read failed or holds no stamp: then nothing may be
    followed, because every old line would pass as new."""
    if returncode != 0:
        return None
    b = newest_stamp(text.splitlines())
    return b if b >= 0 else None


class Stop(Exception):
    pass


def main(argv):
    if argv[1] == "--test":
        lines = open(argv[2], errors="replace").read().splitlines(True) + [EOF]
        it = iter(lines)
        n, d, old, ended = scan(lambda _t: next(it), sys.stdout.write, Pinned(find=lambda: None).sample, -1.0, lambda: True)
        print("# %d fault blocks, %d distinct addresses" % (n, d))
        return 0
    pid = None
    if "--pid" in argv:
        i = argv.index("--pid")
        pid = int(argv[i + 1])
        del argv[i:i + 2]
    out = open(argv[1], "w", buffering=1)
    secs = int(argv[2]) if len(argv) > 2 else 900

    def stop(signum, _frame):
        raise Stop("signal %d" % signum)

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    p = th = None
    rc = 0
    why = "limit"
    n = d = old = 0
    t0 = time.time()
    try:
        snap = subprocess.run(["sudo", "-n", "dmesg"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace", timeout=20)
        boundary = boundary_of(snap.returncode, snap.stdout)
        if boundary is None:
            why = "MONITOR ERROR: the one-shot dmesg gave status %d and no usable stamp; nothing was followed" % snap.returncode
            rc = 2
            return rc
        pin = Pinned(pid)
        first = pin.poll()
        out.write("# fault0416 started %s; kernel lines stamped after %.6f (the newest stamp read at the start) are kept; which run a line belongs to: unknown; process: %s\n"
                  % (time.strftime("%F %T"), boundary, "pid %d (given)" % pid if pid is not None else (first or "none yet, the first kyty_emulator seen is pinned")))
        p = subprocess.Popen(["sudo", "-n", "dmesg", "-w"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
        q = queue.Queue()
        th = threading.Thread(target=reader, args=(p.stdout, q), daemon=True)
        th.start()
        n, d, old, why = scan(getter(q), out.write, pin.sample, boundary, lambda: time.time() - t0 < secs, pin.poll)
    except Stop as e:
        why = str(e)
    except (OSError, subprocess.TimeoutExpired) as e:
        why = "MONITOR ERROR: %s" % e.__class__.__name__
        rc = 2
    finally:
        child = end_child(p, th)
        out.write("# ended after %.0f s (%s): %d fault blocks, %d distinct addresses, %d older lines dropped; %s\n"
                  % (time.time() - t0, why, n, d, old, child))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
