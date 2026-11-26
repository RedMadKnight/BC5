#!/usr/bin/env python3
"""Experiment 0440: readers for a memdump0440.py dump (run on the box; output is private, stays beside the dump).

  ana0440.py modules <dump>                 the loader's module list from the emulator log -> <dump>/ana/modules.json
  ana0440.py threads <dump> [--depth N]     the thread table: both snapshots, where each thread is (guest module+offset
                                            or host file+symbol), the system call it sits in, CPU ticks and context
                                            switches between the snapshots, and the guest return addresses on its stack
  ana0440.py read <dump> <addr> <len>       hex dump of guest memory from the dump files
  ana0440.py q <dump> <addr> [count]        qwords at an address
  ana0440.py find <dump> <hex-bytes|q:VALUE> [lo hi]   search the dumped files for a byte string or a qword value
  ana0440.py sym <dump> <addr>...           module+offset (or host file+symbol) of addresses

No title data is in this file. The dump and everything this prints from it are private.
"""
import bisect
import json
import os
import re
import struct
import subprocess
import sys

PAGE = 4096


class Mem:
    """Guest and host memory as dumped: mem/m_<start>_<end>_<perms>.bin and x_... (sparse files)."""

    def __init__(self, dump):
        self.dump = dump
        self.rows = []
        with open(os.path.join(dump, "dump-index.tsv")) as f:
            next(f)
            for line in f:
                p = line.rstrip("\n").split("\t")
                r = {"start": int(p[0], 16), "end": int(p[1], 16), "perms": p[2], "kind": p[3], "status": p[4],
                     "real": int(p[5]), "present": int(p[6]), "path": p[7] if len(p) > 7 else ""}
                self.rows.append(r)
        self.files = []
        for r in self.rows:
            if r["status"] in ("dumped", "partial"):
                pre = "x" if r["kind"] == "extra" else "m"
                fn = os.path.join(dump, "mem", "%s_%012x_%012x_%s.bin" % (pre, r["start"], r["end"], r["perms"]))
                if os.path.exists(fn):
                    self.files.append((r["start"], r["end"], fn, r))
        self.files.sort(key=lambda x: (x[0], x[1]))
        self.starts = [f[0] for f in self.files]
        self.fds = {}
        self.maps = []
        with open(os.path.join(dump, "maps.txt")) as f:
            for line in f:
                p = line.split(None, 5)
                if len(p) < 5:
                    continue
                a, b = p[0].split("-")
                self.maps.append((int(a, 16), int(b, 16), p[1], int(p[2], 16), p[5].strip() if len(p) > 5 else ""))
        self.map_starts = [m[0] for m in self.maps]

    def file_at(self, addr):
        i = bisect.bisect_right(self.starts, addr) - 1
        while i >= 0:
            s, e, fn, r = self.files[i]
            if s <= addr < e:
                return self.files[i]
            if addr - s > (1 << 31):
                break
            i -= 1
        return None

    def read(self, addr, n):
        out = b""
        while n > 0:
            f = self.file_at(addr)
            if not f:
                return out if out else None
            s, e, fn, _ = f
            if fn not in self.fds:
                self.fds[fn] = os.open(fn, os.O_RDONLY | getattr(os, "O_BINARY", 0))
            k = min(n, e - addr)
            if hasattr(os, "pread"):
                out += os.pread(self.fds[fn], k, addr - s)
            else:  # no pread on Windows: the laptop copy of a dump
                os.lseek(self.fds[fn], addr - s, 0)
                out += os.read(self.fds[fn], k)
            addr += k
            n -= k
        return out

    def q(self, addr):
        b = self.read(addr, 8)
        return struct.unpack("<Q", b)[0] if b and len(b) == 8 else None

    def map_at(self, addr):
        i = bisect.bisect_right(self.map_starts, addr) - 1
        if i >= 0 and self.maps[i][0] <= addr < self.maps[i][1]:
            return self.maps[i]
        return None


def parse_modules(dump):
    """'Loading: <path>' blocks of the emulator log: base and the segment list."""
    log = os.path.join(dump, "play-last.log")
    mods = []
    cur = None
    seg = None
    with open(log, errors="replace") as f:
        for line in f:
            line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            m = re.match(r"Loading: (\S.*)$", line)
            if m:
                cur = {"path": m.group(1), "name": os.path.basename(m.group(1)), "segs": []}
                mods.append(cur)
                continue
            if cur is None:
                continue
            m = re.match(r"(base_vaddr|base_size|base_size_aligned|mapped_size)\s*=\s*(0x[0-9a-fA-F]+)", line)
            if m:
                cur[m.group(1)] = int(m.group(2), 16)
                continue
            m = re.match(r"\[(\d+)\] (addr|file_size|memory_size|mode)\s*=\s*(\S.*)$", line)
            if m:
                i = int(m.group(1))
                while len(cur["segs"]) <= i:
                    cur["segs"].append({})
                v = m.group(3)
                cur["segs"][i][m.group(2)] = int(v, 0) if m.group(2) != "mode" else v
                continue
            if line.startswith("--- Relocate program") or line.startswith("--- Start module"):
                cur = None
    return [m for m in mods if "base_vaddr" in m]


class Syms:
    def __init__(self, mem, mods):
        self.mem = mem
        self.mods = sorted(mods, key=lambda m: m["base_vaddr"])
        self.host = {}

    def guest(self, addr):
        for m in self.mods:
            if m["base_vaddr"] <= addr < m["base_vaddr"] + m.get("mapped_size", m.get("base_size", 0)):
                return m, addr - m["base_vaddr"]
        return None

    def is_guest_code(self, addr):
        g = self.guest(addr)
        if not g:
            return False
        m, _ = g
        for s in m["segs"]:
            if "Execute" in str(s.get("mode", "")) and s.get("addr", 0) <= addr < s.get("addr", 0) + s.get("memory_size", 0):
                return True
        return False

    def host_syms(self, path):
        if path in self.host:
            return self.host[path]
        tab = []
        real = path.replace(" (deleted)", "")
        if os.path.exists(real):
            for args in (["nm", "-C", "-n", "--defined-only", real], ["nm", "-C", "-n", "-D", "--defined-only", real]):
                try:
                    out = subprocess.run(args, capture_output=True, text=True, timeout=180).stdout
                except Exception:
                    out = ""
                for line in out.splitlines():
                    p = line.split(None, 2)
                    if len(p) == 3 and p[1] in "TtWwiI":
                        try:
                            tab.append((int(p[0], 16), p[2]))
                        except ValueError:
                            pass
                if tab:
                    break
            with open(real, "rb") as f:
                hdr = f.read(20)
            pie = len(hdr) >= 18 and struct.unpack("<H", hdr[16:18])[0] == 3
        else:
            pie = True
        tab.sort()
        self.host[path] = (tab, [t[0] for t in tab], pie)
        return self.host[path]

    EXPORT_FILES = {"agc1.tsv": "libSceAgc.sprx", "agc2.tsv": "libSceAgc.sprx", "drv.tsv": "libSceAgcDriver.sprx",
                    "psml1.tsv": "libScePsml.sprx", "psml2.tsv": "libScePsml.sprx"}

    def exports(self):
        """Private export tables (offset, size, NID, library, name) beside the dump, if present: ana/exports/*.tsv."""
        if not hasattr(self, "_exp"):
            self._exp = {}
            d = os.path.join(self.mem.dump, "ana", "exports")
            for fn, mod in self.EXPORT_FILES.items():
                try:
                    rows = open(os.path.join(d, fn)).read().splitlines()[1:]
                except OSError:
                    continue
                tab = self._exp.setdefault(mod, [])
                for r in rows:
                    p = r.split("\t")
                    try:
                        tab.append((int(p[0], 16), int(p[1], 16), p[4] or ("nid_" + p[2])))
                    except (ValueError, IndexError):
                        pass
            for tab in self._exp.values():
                tab.sort()
        return self._exp

    def name(self, addr):
        g = self.guest(addr)
        if g:
            tab = self.exports().get(g[0]["name"])
            if tab:
                i = bisect.bisect_right(tab, (g[1], 1 << 60, "")) - 1
                if i >= 0 and tab[i][0] <= g[1] < tab[i][0] + max(tab[i][1], 1):
                    return "%s+0x%x <%s%s>" % (g[0]["name"], g[1], tab[i][2], "" if g[1] == tab[i][0] else "+0x%x" % (g[1] - tab[i][0]))
            return "%s+0x%x" % (g[0]["name"], g[1])
        m = self.mem.map_at(addr)
        if not m:
            return "?"
        path = m[4]
        if not path.startswith("/") or path.startswith(("/memfd:", "/dev/")):
            return "[%s %x+0x%x]" % (path or "anon", m[0], addr - m[0])
        tab, keys, pie = self.host_syms(path)
        bias = 0
        if pie:  # the file's first mapping (offset 0) is its load bias
            bias = min(x[0] for x in self.mem.maps if x[4] == path)
        v = addr - bias
        i = bisect.bisect_right(keys, v) - 1
        base = os.path.basename(path)
        if i >= 0 and v - keys[i] < 0x40000:
            return "%s:%s+0x%x" % (base, tab[i][1][:90], v - keys[i])
        return "%s+0x%x" % (base, v)


def is_return_address(mem, v):
    """True when the bytes before v decode as a call (direct E8 or an indirect FF /2 form)."""
    b = mem.read(v - 7, 7)
    if not b or len(b) < 7:
        return False
    if b[2] == 0xE8:
        return True
    for k in (2, 3, 4, 6, 7):  # length of an FF /2 call without a prefix
        if b[7 - k] == 0xFF and (b[7 - k + 1] >> 3) & 7 == 2:
            return True
    return False


SYSCALLS = {0: "read", 1: "write", 7: "poll", 23: "select", 34: "pause", 35: "nanosleep", 202: "futex", 230: "clock_nanosleep",
            232: "epoll_wait", 270: "pselect6", 271: "ppoll", 281: "epoll_pwait", 16: "ioctl", 45: "recvfrom", 47: "recvmsg",
            61: "wait4", 247: "waitid", 24: "sched_yield", 441: "epoll_pwait2", 449: "futex_waitv", 14: "rt_sigprocmask",
            128: "rt_sigtimedwait", 262: "newfstatat", 17: "pread64", 426: "io_uring_enter"}


def cmd_threads(dump, depth):
    mem = Mem(dump)
    mods = parse_modules(dump)
    sy = Syms(mem, mods)
    A = {t["tid"]: t for t in json.load(open(os.path.join(dump, "snapA", "threads.json")))["threads"]}
    B = {t["tid"]: t for t in json.load(open(os.path.join(dump, "snapB", "threads.json")))["threads"]}
    out = []
    for tid in sorted(B):
        b = B[tid]
        a = A.get(tid)
        rb = b.get("regs")
        if not rb:
            out.append("%d %s: no registers (%s)" % (tid, b["comm"], b.get("regs_error")))
            continue
        ticks = (b["utime"] + b["stime"] - a["utime"] - a["stime"]) if a else -1
        vol = (b.get("voluntary_ctxt_switches", 0) - a.get("voluntary_ctxt_switches", 0)) if a else -1
        invol = (b.get("nonvoluntary_ctxt_switches", 0) - a.get("nonvoluntary_ctxt_switches", 0)) if a else -1
        ra = a.get("regs") if a else None
        same_ip = bool(ra) and ra["rip"] == rb["rip"] and ra["rsp"] == rb["rsp"]
        orig = rb["orig_rax"]
        insys = orig < (1 << 32)
        where = sy.name(rb["rip"])
        head = "tid %d  %-16s ticks %3d  vol %5d invol %4d  %s  rip %#x  %s" % (
            tid, b["comm"], ticks, vol, invol, "SAME" if same_ip else ("NEW " if a else "new-thread"), rb["rip"], where)
        if insys:
            head += "  [syscall %d %s rdi=%#x rsi=%#x rdx=%#x r10=%#x]" % (orig, SYSCALLS.get(orig, ""), rb["rdi"], rb["rsi"], rb["rdx"], rb["r10"])
        out.append(head)
        if ra and not same_ip:
            out.append("      snapshot A: rip %#x %s" % (ra["rip"], sy.name(ra["rip"])))
        out.append("      rsp %#x rbp %#x rdi %#x rsi %#x rdx %#x rcx %#x rax %#x fs_base %#x" % (
            rb["rsp"], rb["rbp"], rb["rdi"], rb["rsi"], rb["rdx"], rb["rcx"], rb["rax"], rb["fs_base"]))
        st = b.get("stack")
        if st:
            data = open(os.path.join(dump, "snapB", "stack_%d.bin" % tid), "rb").read()
            off = rb["rsp"] - st["lo"]
            n = 0
            for i in range(off, len(data) - 7, 8):
                v = struct.unpack_from("<Q", data, i)[0]
                if sy.is_guest_code(v) and is_return_address(mem, v):
                    out.append("      [rsp+0x%04x] %#x %s" % (i - off, v, sy.name(v)))
                    n += 1
                    if n >= depth:
                        break
    text = "\n".join(out) + "\n"
    os.makedirs(os.path.join(dump, "ana"), exist_ok=True)
    with open(os.path.join(dump, "ana", "threads.txt"), "w") as f:
        f.write(text)
    sys.stdout.write(text)


def main():
    cmd, dump = sys.argv[1], sys.argv[2]
    if cmd == "modules":
        mods = parse_modules(dump)
        os.makedirs(os.path.join(dump, "ana"), exist_ok=True)
        json.dump(mods, open(os.path.join(dump, "ana", "modules.json"), "w"), indent=1)
        for m in mods:
            print("%-28s base %#x size %#x" % (m["name"], m["base_vaddr"], m.get("mapped_size", 0)))
            for i, s in enumerate(m["segs"]):
                print("    [%d] %#x file %#x mem %#x %s" % (i, s.get("addr", 0), s.get("file_size", 0), s.get("memory_size", 0), s.get("mode")))
    elif cmd == "threads":
        depth = int(sys.argv[sys.argv.index("--depth") + 1]) if "--depth" in sys.argv else 10
        cmd_threads(dump, depth)
    elif cmd == "read":
        mem = Mem(dump)
        addr, n = int(sys.argv[3], 0), int(sys.argv[4], 0)
        d = mem.read(addr, n)
        if d is None:
            print("not in the dump")
            return
        for i in range(0, len(d), 16):
            row = d[i:i + 16]
            print("%012x  %-47s  %s" % (addr + i, row.hex(" "), "".join(chr(c) if 32 <= c < 127 else "." for c in row)))
    elif cmd == "q":
        mem = Mem(dump)
        addr = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0) if len(sys.argv) > 4 else 8
        sy = Syms(mem, parse_modules(dump))
        for i in range(n):
            v = mem.q(addr + 8 * i)
            print("%012x: %s" % (addr + 8 * i, "-" if v is None else "%016x  %s" % (v, sy.name(v) if v > 0x10000 and mem.map_at(v) else "")))
    elif cmd == "table":  # one line per thread: ticks, moved or not, the host wait it sits in, the innermost guest frame
        mem = Mem(dump)
        sy = Syms(mem, parse_modules(dump))
        A = {t["tid"]: t for t in json.load(open(os.path.join(dump, "snapA", "threads.json")))["threads"]}
        for t in json.load(open(os.path.join(dump, "snapB", "threads.json")))["threads"]:
            r, a = t["regs"], A.get(t["tid"])
            ticks = t["utime"] + t["stime"] - a["utime"] - a["stime"] if a else -1
            same = bool(a) and a["regs"]["rip"] == r["rip"] and a["regs"]["rsp"] == r["rsp"]
            host, guest = "", ""
            if sy.guest(r["rip"]):
                guest = "runs at " + sy.name(r["rip"])
            bp = r["rbp"]
            for _ in range(48):
                ret, nxt = mem.q(bp + 8), mem.q(bp)
                if ret is None or nxt is None:
                    break
                n = sy.name(ret)
                if sy.guest(ret):
                    if not guest:
                        guest = "called from " + n
                    break
                m = re.search(r"(Libs|Loader|Common)::[A-Za-z0-9_:]+", n)
                if m and "CondVar" not in m.group(0) and "Mutex::" not in m.group(0):
                    host = m.group(0)
                if nxt <= bp or nxt - bp > (1 << 20):
                    break
                bp = nxt
            sysc = SYSCALLS.get(r["orig_rax"], str(r["orig_rax"])) if r["orig_rax"] < (1 << 32) else "-"
            print("%-16s|%4d|%-4s|%-15s|%-58s|%s" % (t["comm"], ticks, "same" if same else "MOVED", sysc, host[-58:], guest))
    elif cmd == "bt":  # frame-pointer walk of one thread (snapshot B): bt <dump> <tid> [frames]
        mem = Mem(dump)
        sy = Syms(mem, parse_modules(dump))
        tid = int(sys.argv[3])
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 40
        for snap in ("snapA", "snapB"):
            t = [t for t in json.load(open(os.path.join(dump, snap, "threads.json")))["threads"] if t["tid"] == tid][0]
            r = t["regs"]
            print("%s %s rip %#x %s  rsp %#x rbp %#x" % (snap, t["comm"], r["rip"], sy.name(r["rip"]), r["rsp"], r["rbp"]))
            print("   " + " ".join("%s=%#x" % (k, r[k]) for k in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15")))
        bp = r["rbp"]
        for i in range(n):
            ret, nxt = mem.q(bp + 8), mem.q(bp)
            if ret is None or nxt is None:
                print("   (frame %d: %#x not in the dump)" % (i, bp))
                break
            print("   #%d rbp %#x ret %#x %s%s" % (i, bp, ret, sy.name(ret), "" if is_return_address(mem, ret) else "  (not after a call)"))
            if nxt <= bp or nxt - bp > (1 << 20):
                break
            bp = nxt
    elif cmd == "pm4":  # pm4 <dump> <addr> <bytes> [--follow]: walk type-3 packets (names: Mesa src/amd/common/sid.h)
        names = {0x10: "NOP", 0x12: "CLEAR_STATE", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT", 0x1E: "ATOMIC_MEM",
                 0x22: "COND_EXEC", 0x28: "CONTEXT_CONTROL", 0x37: "WRITE_DATA", 0x39: "MEM_SEMAPHORE", 0x3C: "WAIT_REG_MEM",
                 0x3F: "INDIRECT_BUFFER", 0x40: "COPY_DATA", 0x46: "EVENT_WRITE", 0x49: "RELEASE_MEM", 0x50: "DMA_DATA",
                 0x58: "ACQUIRE_MEM", 0x69: "SET_CONTEXT_REG", 0x76: "SET_SH_REG", 0x79: "SET_UCONFIG_REG", 0x11: "SET_BASE",
                 0x2D: "DRAW_INDEX_AUTO", 0x27: "DRAW_INDEX_2", 0x47: "EVENT_WRITE_EOP", 0x48: "EVENT_WRITE_EOS",
                 0x33: "INDIRECT_BUFFER_CONST", 0x1F: "OCCLUSION_QUERY", 0x20: "SET_PREDICATION", 0x9F: "LOAD_CONTEXT_REG_INDEX",
                 0x63: "LOAD_SH_REG_INDEX", 0x64: "LOAD_UCONFIG_REG_INDEX", 0x5E: "LOAD_UCONFIG_REG", 0x7D: "SET_RESOURCES"}
        mem = Mem(dump)
        follow = "--follow" in sys.argv
        segs = [0]

        def walk(addr, nbytes, depth):
            d = mem.read(addr, nbytes)
            if not d:
                print("%s%#x: not in the dump" % ("  " * depth, addr))
                return
            dw = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
            i = 0
            while i < len(dw):
                h = dw[i]
                if h == 0:
                    z = i
                    while i < len(dw) and dw[i] == 0:
                        i += 1
                    print("%s%#x: %d zero dwords" % ("  " * depth, addr + 4 * z, i - z))
                    continue
                t = h >> 30
                if h == 0xFFFF1000:  # PKT3_NOP_PAD, the header-only NOP (Mesa sid.h)
                    z = i
                    while i < len(dw) and dw[i] == 0xFFFF1000:
                        i += 1
                    print("%s%#x: %d one-dword NOPs" % ("  " * depth, addr + 4 * z, i - z))
                elif t == 3:
                    n = ((h >> 16) & 0x3FFF) + 1
                    op = (h >> 8) & 0xFF
                    body = dw[i + 1:i + 1 + n]
                    print("%s%#x: %08x %-18s %s%s" % ("  " * depth, addr + 4 * i, h, names.get(op, "op_%02x" % op),
                                                      " ".join("%08x" % x for x in body[:10]), " ..." if n > 10 else ""))
                    if follow and op == 0x3F and len(body) >= 3:
                        tgt, sz, chain = body[0] | (body[1] << 32), (body[2] & 0xFFFFF) * 4, (body[2] >> 20) & 1
                        if chain:  # a chain replaces the current buffer: same level, no limit
                            segs[0] += 1
                            print("%s== chained segment %d: %#x, %d dwords" % ("  " * depth, segs[0], tgt, sz // 4))
                            if segs[0] < 400:
                                return walk(tgt, sz, depth)
                        elif depth < 3:
                            walk(tgt, sz, depth + 1)
                    i += 1 + n
                elif t == 2:
                    print("%s%#x: %08x type-2 filler" % ("  " * depth, addr + 4 * i, h))
                    i += 1
                else:
                    n = ((h >> 16) & 0x3FFF) + 1 if t == 0 else 0
                    print("%s%#x: %08x type-%d" % ("  " * depth, addr + 4 * i, h, t))
                    i += 1 + n

        walk(int(sys.argv[3], 0), int(sys.argv[4], 0), 0)
    elif cmd == "sym":
        mem = Mem(dump)
        sy = Syms(mem, parse_modules(dump))
        for a in sys.argv[3:]:
            print(a, sy.name(int(a, 0)))
    elif cmd == "find":
        mem = Mem(dump)
        pat = sys.argv[3]
        needle = struct.pack("<Q", int(pat[2:], 0)) if pat.startswith("q:") else bytes.fromhex(pat)
        lo = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
        hi = int(sys.argv[5], 0) if len(sys.argv) > 5 else 1 << 64
        hits = 0
        for s, e, fn, r in mem.files:
            if e <= lo or s >= hi or r["real"] == 0:
                continue
            with open(fn, "rb") as f:
                pos = 0
                while True:
                    try:
                        pos = os.lseek(f.fileno(), pos, os.SEEK_DATA)
                    except OSError:
                        break
                    end = os.lseek(f.fileno(), pos, os.SEEK_HOLE)
                    data = os.pread(f.fileno(), end - pos, pos)
                    i = data.find(needle)
                    while i >= 0:
                        a = s + pos + i
                        if lo <= a < hi and (not pat.startswith("q:") or a % 8 == 0):
                            print("%012x  (%s %s)" % (a, r["perms"], r["path"][:40]))
                            hits += 1
                            if hits >= 400:
                                print("... more")
                                return
                        i = data.find(needle, i + 1)
                    pos = end
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
