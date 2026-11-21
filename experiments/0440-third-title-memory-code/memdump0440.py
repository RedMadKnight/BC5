#!/usr/bin/env python3
"""Experiment 0440: pause a running emulator and dump its threads and memory (private output).

  memdump0440.py run <pid> <outdir> [--gap 5] [--cap-gb 8] [--big-mb 256] [--deadline 480]
                                    [--extra ADDR:LEN ...] [--keep-stopped]

Sequence (the process is the maintainer's own user, ptrace_scope 0, no emulator build needed):
  1. SIGSTOP, wait until every thread is stopped; snapshot A: per thread comm, state, CPU times,
     context switches, registers (PTRACE_SEIZE on the stopped thread, GETREGS, DETACH) and the stack
     from RSP-256 up (--stack-kb, bounded by its mapping).
  2. SIGCONT, sleep --gap seconds, SIGSTOP again; snapshot B, the same: which threads moved.
  3. With the process still stopped: /proc/<pid>/maps, status, cmdline, environ, the fd list, and the
     memory of the selected mappings through /proc/<pid>/mem, written as sparse files (absent and
     all-zero pages are holes), fsynced.
       selected: every anonymous/memfd/shm mapping with x (<= 1 GiB), then every other such mapping
                 <= --big-mb, in address order, until --cap-gb of real bytes or the --deadline;
                 never: host files (binaries, libraries), /dev/*, [vvar], [vsyscall];
                 --extra ranges are dumped whole even inside a skipped mapping (the label table).
  4. SIGCONT (unless --keep-stopped). The caller ends the run.

Every wait is bounded. The output holds the title's code and data: it belongs under a mode-700
private directory and never in git. This script holds no title data.
"""
import argparse
import ctypes
import json
import os
import signal
import struct
import sys
import time

PAGE = 4096
ZERO_PAGE = bytes(PAGE)
PTRACE_GETREGS, PTRACE_DETACH, PTRACE_SEIZE, PTRACE_INTERRUPT = 12, 17, 0x4206, 0x4207
WALL = 0x40000000
REG_NAMES = ("r15 r14 r13 r12 rbp rbx r11 r10 r9 r8 rax rcx rdx rsi rdi orig_rax rip cs eflags "
             "rsp ss fs_base gs_base ds es fs gs").split()


class UserRegs(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in REG_NAMES]


libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
libc.ptrace.restype = ctypes.c_long

T0 = time.monotonic()


def log(msg):
    print("[%7.2f] %s" % (time.monotonic() - T0, msg), flush=True)


def ptrace(req, tid, addr=0, data=0):
    ctypes.set_errno(0)
    r = libc.ptrace(req, tid, addr, data)
    if r == -1 and ctypes.get_errno():
        e = ctypes.get_errno()
        raise OSError(e, "ptrace(%#x, %d): %s" % (req, tid, os.strerror(e)))
    return r


def read_text(path, default=""):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return default


def tids_of(pid):
    try:
        return sorted(int(t) for t in os.listdir("/proc/%d/task" % pid))
    except OSError:
        return []


def stat_fields(pid, tid):
    """state and the numeric fields after the comm (which may hold spaces and parentheses)."""
    s = read_text("/proc/%d/task/%d/stat" % (pid, tid))
    r = s.rfind(")")
    if r < 0:
        return None
    return s[r + 2:].split()


def stop_all(pid, limit=5.0):
    os.kill(pid, signal.SIGSTOP)
    end = time.monotonic() + limit
    while True:
        running = []
        for tid in tids_of(pid):
            f = stat_fields(pid, tid)
            if f and f[0] not in ("T", "t", "Z", "X"):
                running.append((tid, f[0]))
        if not running:
            return True
        if time.monotonic() > end:
            log("stop_all: %d threads not stopped after %.1f s: %s" % (len(running), limit, running[:8]))
            return False
        time.sleep(0.002)


def parse_maps(text):
    out = []
    for line in text.splitlines():
        p = line.split(None, 5)
        if len(p) < 5:
            continue
        a, b = p[0].split("-")
        out.append({"start": int(a, 16), "end": int(b, 16), "perms": p[1], "off": int(p[2], 16),
                    "dev": p[3], "inode": int(p[4]), "path": p[5] if len(p) > 5 else ""})
    return out


def wait_stop(tid, limit):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        try:
            got, status = os.waitpid(tid, WALL | os.WNOHANG)
        except ChildProcessError:
            return False
        if got == tid:
            return os.WIFSTOPPED(status)
        time.sleep(0.0005)
    return False


def thread_regs(tid):
    """registers of one group-stopped thread: SEIZE moves it to a ptrace stop, DETACH puts it back."""
    ptrace(PTRACE_SEIZE, tid)
    try:
        if not wait_stop(tid, 1.0):
            ptrace(PTRACE_INTERRUPT, tid)
            if not wait_stop(tid, 2.0):
                raise OSError(0, "thread %d did not reach a ptrace stop" % tid)
        regs = UserRegs()
        ptrace(PTRACE_GETREGS, tid, 0, ctypes.addressof(regs))
        return {n: getattr(regs, n) for n in REG_NAMES}
    finally:
        try:
            ptrace(PTRACE_DETACH, tid)
        except OSError as e:
            log("detach %d: %s" % (tid, e))


def snapshot(pid, outdir, name, stack_kb):
    d = os.path.join(outdir, name)
    os.makedirs(d, exist_ok=True)
    maps = parse_maps(read_text("/proc/%d/maps" % pid))
    mem = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
    recs = []
    t = time.monotonic()
    for tid in tids_of(pid):
        base = "/proc/%d/task/%d/" % (pid, tid)
        rec = {"tid": tid, "comm": read_text(base + "comm").strip()}
        f = stat_fields(pid, tid)
        if f:
            rec.update(state=f[0], utime=int(f[11]), stime=int(f[12]), cpu=int(f[36]))
        for line in read_text(base + "status").splitlines():
            if line.startswith(("voluntary_ctxt_switches", "nonvoluntary_ctxt_switches")):
                k, v = line.split(":")
                rec[k] = int(v)
        rec["schedstat"] = read_text(base + "schedstat").strip()
        try:
            rec["regs"] = thread_regs(tid)
        except OSError as e:
            rec["regs_error"] = str(e)
            recs.append(rec)
            continue
        rsp = rec["regs"]["rsp"]
        m = next((m for m in maps if m["start"] <= rsp < m["end"]), None)
        if m:
            lo = max(m["start"], rsp - 256)
            hi = min(m["end"], rsp + stack_kb * 1024)
            try:
                data = os.pread(mem, hi - lo, lo)
                with open(os.path.join(d, "stack_%d.bin" % tid), "wb") as sf:
                    sf.write(data)
                rec["stack"] = {"lo": lo, "len": len(data), "map_start": m["start"], "map_end": m["end"]}
            except OSError as e:
                rec["stack_error"] = str(e)
        recs.append(rec)
    os.close(mem)
    with open(os.path.join(d, "threads.json"), "w") as jf:
        json.dump({"pid": pid, "wall": time.time(), "threads": recs}, jf, indent=1)
        jf.flush()
        os.fsync(jf.fileno())
    bad = sum(1 for r in recs if "regs" not in r)
    log("snapshot %s: %d threads, %d without registers, %.2f s" % (name, len(recs), bad, time.monotonic() - t))
    return recs


def classify(m):
    p = m["path"]
    if p.startswith("/dev/zero"):  # a shared anonymous mapping
        return "anon"
    if p.startswith(("[vvar", "[vsyscall", "/dev/", "anon_inode:")):
        return "special"
    if p.startswith("/") and not p.startswith(("/memfd:", "/dev/shm/", "/SYSV")):
        return "gamefile" if "/bc5-data/games/" in p else "hostfile"
    return "anon"


def dump_range(mem, pm, start, end, path, use_pagemap, deadline):
    """Write [start, end) to a sparse file. Returns (real bytes, present pages or -1, complete)."""
    npages = (end - start) // PAGE
    chunk = 256
    zero_chunk = bytes(chunk * PAGE)
    real = 0
    present_total = 0 if use_pagemap else -1
    complete = True
    with open(path, "wb") as f:
        for off in range(0, npages, chunk):
            if time.monotonic() > deadline:
                complete = False
                break
            n = min(chunk, npages - off)
            addr = start + off * PAGE
            present = None
            if use_pagemap:
                try:
                    raw = os.pread(pm, n * 8, (addr // PAGE) * 8)
                except OSError:
                    raw = b""
                if len(raw) == n * 8:
                    present = [(q >> 62) != 0 for q in struct.unpack("<%dQ" % n, raw)]
                    c = sum(present)
                    present_total += c
                    if c == 0:
                        continue
            try:
                buf = os.pread(mem, n * PAGE, addr)
            except OSError:
                buf = b""
            if len(buf) == n * PAGE:
                if present is None or all(present):
                    if buf == zero_chunk[:n * PAGE]:
                        continue
                for i in range(n):
                    if present is not None and not present[i]:
                        continue
                    pg = buf[i * PAGE:(i + 1) * PAGE]
                    if pg != ZERO_PAGE:
                        f.seek((off + i) * PAGE)
                        f.write(pg)
                        real += PAGE
            else:  # a hole or a read error inside the chunk: page by page
                for i in range(n):
                    if present is not None and not present[i]:
                        continue
                    try:
                        pg = os.pread(mem, PAGE, addr + i * PAGE)
                    except OSError:
                        continue
                    if len(pg) == PAGE and pg != ZERO_PAGE:
                        f.seek((off + i) * PAGE)
                        f.write(pg)
                        real += PAGE
        f.truncate(end - start)
        f.flush()
        os.fsync(f.fileno())
    return real, present_total, complete


def memfd_table(pid):
    """inode -> /proc/<pid>/fd/<n> for the process's memfds (the emulator keeps guest memory in them)."""
    t = {}
    base = "/proc/%d/fd" % pid
    for fd in os.listdir(base):
        p = os.path.join(base, fd)
        try:
            if os.readlink(p).startswith("/memfd:"):
                t[os.stat(p).st_ino] = p
        except OSError:
            pass
    return t


ZERO_MB = bytes(1 << 20)


def dump_file_range(fd, foff, size, path, deadline):
    """A shared memfd mapping, read from the file's allocated extents (SEEK_DATA/SEEK_HOLE): no page of the
    process is faulted in (a read fault on a shmem hole through /proc/<pid>/mem would allocate it), and pages
    written only by the GPU or through another alias are still found."""
    real = 0
    complete = True
    pos = foff
    end = foff + size
    with open(path, "wb") as f:
        while pos < end:
            if time.monotonic() > deadline:
                complete = False
                break
            try:
                d = os.lseek(fd, pos, os.SEEK_DATA)
            except OSError:
                break  # ENXIO: no data after pos
            if d >= end:
                break
            try:
                h = min(os.lseek(fd, d, os.SEEK_HOLE), end)
            except OSError:
                h = end
            p = d - d % PAGE
            while p < h:
                buf = os.pread(fd, min(1 << 20, h - p), p)
                if not buf:
                    break
                if buf != ZERO_MB[:len(buf)]:
                    for i in range(0, len(buf), PAGE):
                        pg = buf[i:i + PAGE]
                        if pg != ZERO_PAGE[:len(pg)]:
                            f.seek(p - foff + i)
                            f.write(pg)
                            real += len(pg)
                p += len(buf)
            pos = max(h, pos + PAGE)
        f.truncate(size)
        f.flush()
        os.fsync(f.fileno())
    return real, -1, complete


def count_present(pm, start, end):
    total = 0
    step = 1 << 16
    for first in range(start // PAGE, end // PAGE, step):
        n = min(step, end // PAGE - first)
        try:
            raw = os.pread(pm, n * 8, first * 8)
        except OSError:
            return -1
        total += sum(1 for q in struct.unpack("<%dQ" % (len(raw) // 8), raw) if q >> 62)
    return total


def full_dump(pid, outdir, cap_bytes, big_bytes, deadline, extras):
    t = time.monotonic()
    maps_text = read_text("/proc/%d/maps" % pid)
    for name, src in (("maps.txt", None), ("status.txt", "status"), ("cmdline.bin", "cmdline"),
                      ("environ.bin", "environ"), ("limits.txt", "limits")):
        with open(os.path.join(outdir, name), "wb") as f:
            f.write(maps_text.encode() if src is None else read_text("/proc/%d/%s" % (pid, src)).encode())
            f.flush()
            os.fsync(f.fileno())
    with open(os.path.join(outdir, "fds.txt"), "w") as f:
        for fd in sorted(os.listdir("/proc/%d/fd" % pid), key=int):
            try:
                f.write("%s -> %s\n" % (fd, os.readlink("/proc/%d/fd/%s" % (pid, fd))))
            except OSError:
                pass
    maps = parse_maps(maps_text)
    mem = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
    pm = os.open("/proc/%d/pagemap" % pid, os.O_RDONLY)
    md = os.path.join(outdir, "mem")
    os.makedirs(md, exist_ok=True)
    index = []
    total = 0
    memfds = memfd_table(pid)
    open_fds = {}

    def fname(prefix, m):
        return "%s_%012x_%012x_%s.bin" % (prefix, m["start"], m["end"], m["perms"])

    def dump_any(m, start, end, target):
        """[start, end) inside mapping m, by the cheapest safe source; nothing is faulted in."""
        src = memfds.get(m["inode"]) if m["perms"][3] == "s" and m["path"].startswith("/memfd:") else None
        if src:
            if src not in open_fds:
                open_fds[src] = os.open(src, os.O_RDONLY)
            return dump_file_range(open_fds[src], m["off"] + (start - m["start"]), end - start, target, deadline) + ("memfd",)
        # only pages present in the process's page tables (or swapped)
        return dump_range(mem, pm, start, end, target, True, deadline) + (m["kind"],)

    order = []
    for m in maps:
        kind = classify(m)
        size = m["end"] - m["start"]
        m2 = dict(m, kind=kind, size=size, real=0, present=-1, status="")
        if kind in ("special", "hostfile"):
            m2["status"] = "skipped-" + kind
        elif "x" in m["perms"] and size <= (1 << 30):
            order.append((0, m2))
        elif size <= big_bytes:
            order.append((1, m2))
        else:
            m2["status"] = "skipped-big"
        index.append(m2)
    order.sort(key=lambda x: (x[0], x[1]["start"]))
    for _, m in order:
        if total >= cap_bytes:
            m["status"] = "skipped-cap"
            continue
        if time.monotonic() > deadline:
            m["status"] = "skipped-deadline"
            continue
        real, present, ok, m["kind"] = dump_any(m, m["start"], m["end"], os.path.join(md, fname("m", m)))
        m["real"], m["present"], m["status"] = real, present, "dumped" if ok else "partial"
        total += real
    # --extra ranges: the parts of them that the rules above left out (inside a big or capped mapping)
    for start, length in extras:
        for m in [m for m in index if m["kind"] not in ("special", "hostfile", "extra")]:
            lo, hi = max(start, m["start"]), min(start + length, m["end"])
            if lo >= hi or m["status"] in ("dumped", "partial"):
                continue
            x = {"start": lo, "end": hi, "perms": "extra"}
            real, _, ok, _k = dump_any(m, lo, hi, os.path.join(md, fname("x", x)))
            total += real
            index.append(dict(x, kind="extra", path=m["path"], real=real, present=-1, status="dumped" if ok else "partial"))
    for m in index:
        if m["status"] == "skipped-big":  # pages present in this process's page tables
            m["present"] = count_present(pm, m["start"], m["end"])
    os.close(mem)
    os.close(pm)
    with open(os.path.join(outdir, "dump-index.tsv"), "w") as f:
        f.write("start\tend\tperms\tkind\tstatus\treal_bytes\tpresent_pages\tpath\n")
        for m in sorted(index, key=lambda m: m["start"]):
            f.write("%012x\t%012x\t%s\t%s\t%s\t%d\t%d\t%s\n" % (m["start"], m["end"], m["perms"], m["kind"],
                                                             m["status"], m["real"], m["present"], m.get("path", "")))
        f.flush()
        os.fsync(f.fileno())
    by = {}
    for m in index:
        by[m["status"]] = by.get(m["status"], 0) + 1
    log("full dump: %d mappings, %s, %.1f MiB real, %.1f s" % (len(maps), by, total / 1048576, time.monotonic() - t))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("pid", type=int)
    ap.add_argument("outdir")
    ap.add_argument("--gap", type=float, default=5.0)
    ap.add_argument("--cap-gb", type=float, default=8.0)
    ap.add_argument("--big-mb", type=int, default=256)
    ap.add_argument("--deadline", type=float, default=480.0, help="seconds for the memory dump")
    ap.add_argument("--stack-kb", type=int, default=64)
    ap.add_argument("--extra", action="append", default=[], help="ADDR:LEN (hex or decimal)")
    ap.add_argument("--keep-stopped", action="store_true")
    a = ap.parse_args()
    extras = [tuple(int(x, 0) for x in e.split(":")) for e in a.extra]
    os.umask(0o077)
    os.makedirs(a.outdir, exist_ok=True)
    pid = a.pid
    rc = 0
    stopped = False
    try:
        stopped = True
        if not stop_all(pid):
            rc = 3
        t_stop = time.monotonic()
        snapshot(pid, a.outdir, "snapA", a.stack_kb)
        os.kill(pid, signal.SIGCONT)
        stopped = False
        log("snapshot A held the process stopped for %.2f s; running for %.1f s" % (time.monotonic() - t_stop, a.gap))
        time.sleep(a.gap)
        stopped = True
        if not stop_all(pid):
            rc = 3
        t_stop = time.monotonic()
        snapshot(pid, a.outdir, "snapB", a.stack_kb)
        full_dump(pid, a.outdir, int(a.cap_gb * (1 << 30)), a.big_mb << 20, time.monotonic() + a.deadline, extras)
        os.sync()
        log("stopped window of the dump: %.1f s" % (time.monotonic() - t_stop))
    except Exception as e:  # report and always let the process go on
        log("ERROR: %r" % (e,))
        rc = 1
    finally:
        if stopped and not a.keep_stopped:
            try:
                os.kill(pid, signal.SIGCONT)
                log("SIGCONT sent")
            except OSError as e:
                log("SIGCONT: %s" % e)
    return rc


if __name__ == "__main__":
    sys.exit(main())
