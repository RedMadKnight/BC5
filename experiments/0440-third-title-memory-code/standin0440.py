#!/usr/bin/env python3
"""Experiment 0440: a stand-in process for memdump0440.py, and the check of what the dumper wrote.

  standin0440.py <pidfile>            threads (one spins, one sleeps, one waits on a lock), a 1 MiB rwx
                                      mapping with known bytes, a 128 MiB mapping with one written page
  standin0440.py --check <dump> <addr>  PASS/FAIL lines for the dump of that process
"""
import ctypes
import json
import mmap
import os
import sys
import threading
import time

MARK = b"STANDIN-0440-MARK"


def name(n):
    ctypes.CDLL(None).prctl(15, n.encode(), 0, 0, 0)


def addr_of(m):
    return ctypes.addressof(ctypes.c_char.from_buffer(m))


def run(pidfile):
    rwx = mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC
    code = mmap.mmap(-1, 1 << 20, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS, prot=rwx)
    code[0:16] = b"\x90" * 15 + b"\xc3"
    code[0x8000:0x8000 + len(MARK)] = MARK
    fd = os.memfd_create("standin0440")  # as the emulator's guest memory: a shared memfd mapping
    os.ftruncate(fd, 64 << 20)
    shared = mmap.mmap(fd, 64 << 20, flags=mmap.MAP_SHARED, prot=rwx)
    alias = mmap.mmap(fd, 64 << 20, flags=mmap.MAP_SHARED)  # the marked page is written through an alias only
    alias[0x5000:0x5000 + len(MARK)] = MARK
    big = mmap.mmap(-1, 128 << 20, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
    big[0x3000:0x3000 + len(MARK)] = MARK
    lock = threading.Lock()
    lock.acquire()

    def spin():
        name("spin0440")
        x = 0
        while True:
            x += 1

    def sleeper():
        name("sleep0440")
        while True:
            time.sleep(1000)

    def waiter():
        name("wait0440")
        lock.acquire()

    for f in (spin, sleeper, waiter):
        threading.Thread(target=f, daemon=True).start()
    time.sleep(0.3)
    with open(pidfile + ".tmp", "w") as f:
        f.write("%d %#x %d\n" % (os.getpid(), addr_of(big), fd))
    os.rename(pidfile + ".tmp", pidfile)
    time.sleep(100)


def check(dump, addr):
    ok = True

    def say(cond, text):
        nonlocal ok
        ok = ok and cond
        print(("PASS " if cond else "FAIL ") + text)

    a = json.load(open(os.path.join(dump, "snapA", "threads.json")))["threads"]
    b = json.load(open(os.path.join(dump, "snapB", "threads.json")))["threads"]
    say(len(a) >= 4 and all("regs" in t for t in a), "snapshot A: %d threads, all with registers" % len(a))
    say(len(b) >= 4 and all("regs" in t for t in b), "snapshot B: %d threads, all with registers" % len(b))
    by = {t["comm"]: t for t in a}
    bb = {t["comm"]: t for t in b}
    for n in ("spin0440", "sleep0440", "wait0440"):
        say(n in by and n in bb, "thread %s named in both" % n)
    if "spin0440" in by and "spin0440" in bb:
        d = bb["spin0440"]["utime"] - by["spin0440"]["utime"]
        say(d >= 50, "the spinner used CPU between the snapshots (%d ticks)" % d)
        d = bb["sleep0440"]["utime"] + bb["sleep0440"]["stime"] - by["sleep0440"]["utime"] - by["sleep0440"]["stime"]
        say(d <= 2, "the sleeper did not (%d ticks)" % d)
        say(bb["sleep0440"]["regs"]["rip"] == by["sleep0440"]["regs"]["rip"], "the sleeper's RIP is unchanged")
        say(by["sleep0440"]["regs"]["orig_rax"] < 600, "the sleeper is in a system call (nr %d)" % by["sleep0440"]["regs"]["orig_rax"])
        say("stack" in by["spin0440"] and by["spin0440"]["stack"]["len"] >= 4096, "stack bytes for the spinner")
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(dump, "dump-index.tsv"))][1:]
    x = [r for r in rows if "x" in r[2] and r[3] == "anon" and r[4] == "dumped" and int(r[1], 16) - int(r[0], 16) == 1 << 20]
    found = False
    for r in x:
        p = os.path.join(dump, "mem", "m_%s_%s_%s.bin" % (r[0], r[1], r[2]))
        d = open(p, "rb").read()
        if d[0x8000:0x8000 + len(MARK)] == MARK and d[:16] == b"\x90" * 15 + b"\xc3":
            found = True
            say(os.stat(p).st_blocks * 512 < (1 << 20), "the rwx mapping's file is sparse (%d of %d bytes)" % (os.stat(p).st_blocks * 512, len(d)))
    say(found, "the private rwx mapping was dumped with its bytes")
    sh = [r for r in rows if "memfd:standin0440" in r[7] and r[4] == "dumped" and "x" in r[2]]
    shd = open(os.path.join(dump, "mem", "m_%s_%s_%s.bin" % tuple(sh[0][:3])), "rb").read() if sh else b""
    say(shd[0x5000:0x5000 + len(MARK)] == MARK, "the shared memfd rwx mapping was dumped with its bytes")
    big = [r for r in rows if int(r[0], 16) == addr and r[3] != "extra"]
    say(bool(big) and big[0][4] == "skipped-big" and int(big[0][6]) >= 1, "the 128 MiB mapping was skipped as big, present pages counted: %s" % (big[0][4:7] if big else "none"))
    e = [r for r in rows if r[3] == "extra"]
    if e:
        d = open(os.path.join(dump, "mem", "x_%s_%s_extra.bin" % (e[0][0], e[0][1])), "rb").read()
        say(d[0x3000:0x3000 + len(MARK)] == MARK, "the extra range inside it was dumped")
    else:
        say(False, "no extra range in the index")
    say(any(r[4] == "skipped-hostfile" for r in rows), "host files were skipped")
    print("STANDIN " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        sys.exit(check(sys.argv[2], int(sys.argv[3], 0)))
    run(sys.argv[1])
