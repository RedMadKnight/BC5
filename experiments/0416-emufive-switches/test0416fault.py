#!/usr/bin/env python3
"""BC5 experiment 0416: synthetic cases for fault0416.py (Codex's list, 2026-11-12): silence, an old backlog, a new
fault at the start, the reader's end; plus the pinned process and the child cleanup. No dmesg, no emulator, no box.
usage: test0416fault.py     (run from any directory; exits 1 on a failed check)"""
import os
import queue
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fault0416 as f  # noqa: E402

fails = 0


def check(ok, what):
    global fails
    if not ok:
        fails += 1
    print("%s %s" % ("ok  " if ok else "FAIL", what))


def fault(stamp, addr):
    return "[%12.6f] amdgpu 0000:01:00.0: amdgpu:   in page starting at address 0x%016x from client 0x1b (UTCL2)\n" % (stamp, addr)


def feed(items):
    """A get() over a list: a number is a silence of that many seconds."""
    it = iter(items)

    def get(timeout):
        x = next(it, f.EOF)
        if isinstance(x, float):
            time.sleep(min(x, timeout))
            return None
        return x
    return get


def run(items, boundary, keep=lambda: True, sample=lambda a: "S", tick=None):
    out = []
    res = f.scan(feed(items), out.append, sample, boundary, keep, tick)
    return out, res


# 1. silence: the limit is obeyed with no line at all (the old code blocked in the pipe read)
t0 = time.monotonic()
q = queue.Queue()
out, (n, d, old, ended) = [], f.scan(f.getter(q), lambda s: None, lambda a: "S", 0.0, lambda: time.monotonic() - t0 < 1.2)
el = time.monotonic() - t0
check(1.2 <= el < 2.0 and ended == "limit" and n == 0, "silence: a 1.2 s limit ended the scan after %.2f s with no line received" % el)

# 2. an old backlog that arrives late is dropped, whenever it is received
out, (n, d, old, ended) = run([1.0, fault(50.0, 0x2000), fault(99.999999, 0x3000), fault(100.0, 0x4000)], 100.0)
check(n == 0 and old == 3 and not out, "old backlog: 3 lines at or below the boundary, received after 1 s, dropped (%d faults, %d dropped)" % (n, old))

# 3. a new fault in the first moment is kept (the old code dropped everything received in the first 2 s)
out, (n, d, old, ended) = run([fault(100.000001, 0x1000)], 100.0)
check(n == 1 and len(out) == 1 and "gpu va 0x1000" in out[0], "new fault at the start: kept (%d fault)" % n)

# 3b. the newest stamp of a snapshot is the boundary; a continuation line without a stamp follows the line before it
snap = ["[   10.000000] a\n", "no stamp\n", "[   99.500000] b\n", "[   42.000000] out of order\n"]
check(f.newest_stamp(snap) == 99.5 and f.newest_stamp([]) == -1.0, "boundary: newest stamp of the snapshot (99.5), -1 for an empty log")
out, (n, d, old, ended) = run([fault(50.0, 0x2000), "amdgpu 0000:01:00.0: amdgpu:   in page starting at address 0x5000 from client\n",
                               fault(101.0, 0x1000), "amdgpu: RW: 0x1\n"], 100.0)
check(n == 1 and old == 2 and any("write" in s for s in out), "a line without a stamp takes the stamp before it (old one dropped, new one's RW kept)")

# 4. the reader's end is reported and ends the scan
out, (n, d, old, ended) = run([fault(101.0, 0x1000), f.EOF, fault(102.0, 0x2000)], 100.0)
check(ended == "reader end" and n == 1, "reader end: the scan stops and says so (%s, %d fault)" % (ended, n))
q = queue.Queue()
f.reader(iter(["x\n", "y\n"]), q)
check([q.get(), q.get(), q.get()] == ["x\n", "y\n", f.EOF], "the reader thread puts its end mark after the last line")

# 5. repeats: first and every 100th; timeout lines are copied
items = [fault(101.0 + i * 0.001, 0x7000) for i in range(250)] + ["[  102.000000] amdgpu 0000:01:00.0: ring gfx_0.0.0 timeout, signaled seq=1, emitted seq=3\n"]
out, (n, d, old, ended) = run(items, 100.0)
check(n == 250 and d == 1 and sum("fault:" in s for s in out) == 3 and any("kernel: " in s and "timeout" in s for s in out),
      "repeats: 250 faults at one address give 3 lines (1st, 100th, 200th); the ring timeout is copied")

# 6. the pinned process: first one seen, never re-pinned, PID reuse is told apart, labels say what they are
world = {"pid": None, "birth": {}}
pin = f.Pinned(find=lambda: world["pid"], started=lambda p: world["birth"].get(p))
check(pin.poll() is None and "unknown (no pinned process" in pin.sample(0x1000), "no emulator yet: the sample is unknown")
world["pid"], world["birth"] = 4242, {4242: "100"}
check(pin.poll() == "pinned pid 4242" and pin.poll() is None, "the first emulator seen is pinned, once")
world["pid"], world["birth"] = 5555, {5555: "900"}
check(pin.pid == 4242 and "unknown (the pinned process is gone; pid 4242" in pin.sample(0x1000), "a later emulator is not sampled: the pinned one is gone, unknown")
world["birth"] = {4242: "777"}
check("unknown (the pinned process is gone" in pin.sample(0x1000), "a reused PID (another start time) is not the pinned process")
world["birth"] = {4242: "100"}
s = pin.sample(0x1000)  # /proc/4242/maps does not exist here (or is not ours)
check(s.startswith("CPU VMA now: ") and "pid 4242, sampled " in s, "a sample names 'CPU VMA now', the PID and the sample time: %s" % s[:70])
if os.path.exists("/proc/self/maps"):
    me = f.Pinned(os.getpid())
    stack = next(int(l.split("-")[0], 16) for l in open("/proc/self/maps") if "[stack]" in l)
    check("CPU VMA now: present" in me.sample(stack) and "CPU VMA now: none" in me.sample(8), "own process: the stack is present, address 8 has no VMA")
out, _ = run([fault(101.0, 0x1000)], 100.0, sample=pin.sample)
check("run attribution: unknown" in out[0] and "mapped" not in out[0].replace("unmapped", ""), "a fault line keeps 'run attribution: unknown' and has no bare 'mapped'")

# 7. tick notes are written; the saved-file mode still reads the 0016 format
out, _ = run([0.1, fault(101.0, 0x1000)], 100.0, tick=iter(["pinned pid 7", None, None, None]).__next__)
check(out[0] == "# pinned pid 7\n", "the pin note goes to the log")

# 8. the child cleanup: a child that ignores nothing is ended and reaped; closing the pipe comes first
p = subprocess.Popen([sys.executable, "-c", "import sys,time\nwhile True:\n    print('x', flush=True); time.sleep(0.05)"], stdout=subprocess.PIPE, text=True)
q = queue.Queue()
threading.Thread(target=f.reader, args=(p.stdout, q), daemon=True).start()
q.get(timeout=5)
msg = f.end_child(p)
check(p.poll() is not None and msg.startswith("child ended"), "cleanup: the child is ended and reaped (%s)" % msg)
check(f.end_child(None) == "no child", "cleanup with no child started")

print("%s: %d failed checks" % ("PASS" if fails == 0 else "FAIL", fails))
sys.exit(1 if fails else 0)
