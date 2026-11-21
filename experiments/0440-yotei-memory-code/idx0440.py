#!/usr/bin/env python3
"""Experiment 0440: disassembly and indexes of the dumped title modules (run on the box, niced; output private).

  idx0440.py build <dump>            for every module of the loader's list: the segments as flat files (ana/bin),
                                     objdump listings of the executable ones (ana/dis/<module>.s), and the indexes
                                     ana/idx/<module>.{calls,riprel,funcs,imports,syscalls,strings,fptrs}.tsv
  idx0440.py dis <dump> <addr> [bytes|-N] [--raw]
                                     a window of disassembly from <addr> (a function start), calls and rip-relative
                                     operands annotated with import names, strings and pointed-to values; -N: start at
                                     the function that holds <addr> and mark the line
  idx0440.py fn <dump> <addr>...     the indexed function start that holds each address
  idx0440.py xref <dump> <addr> [--w]   code that refers to a data address (rip-relative) or calls/jumps to a code address
  idx0440.py imp <dump> <pattern>    imports whose name matches, with their stubs and the call sites' count
  idx0440.py callers <dump> <addr>   call sites of a function (direct calls and tail jumps), with the caller's start
  idx0440.py str <dump> <pattern>    strings matching, with the code that refers to them

Function starts are a heuristic (call targets, code pointers found in data, push rbp / mov rbp,rsp): no symbols exist.
"""
import bisect
import json
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ana0440 import Mem, Syms, parse_modules  # noqa: E402


def seg_list(mods):
    out = []
    for m in mods:
        for i, s in enumerate(m["segs"]):
            if s.get("memory_size", 0) and s.get("addr", 0):
                out.append((m["name"], i, s["addr"] & ~0xfff, (s["addr"] + s["memory_size"] + 0xfff) & ~0xfff, str(s.get("mode"))))
    return out


def paths(dump):
    a = os.path.join(dump, "ana")
    for d in ("bin", "dis", "idx"):
        os.makedirs(os.path.join(a, d), exist_ok=True)
    return a


def objdump_cmd(binfile, vma, start=None, stop=None, raw=False):
    cmd = ["objdump", "-D", "-b", "binary", "-m", "i386:x86-64", "-M", "intel", "--adjust-vma=%#x" % vma, "-w"]
    if not raw:
        cmd.append("--no-show-raw-insn")
    if start is not None:
        cmd += ["--start-address=%#x" % start, "--stop-address=%#x" % stop]
    return cmd + [binfile]


LINE = re.compile(r"^\s*([0-9a-f]+):\t(.*)$")
RIPREF = re.compile(r"#\s*0x([0-9a-f]+)")
TARGET = re.compile(r"^(call|jmp|j[a-z]+)\s+0x([0-9a-f]+)$")


def build(dump):
    a = paths(dump)
    mem = Mem(dump)
    mods = parse_modules(dump)
    json.dump(mods, open(os.path.join(a, "modules.json"), "w"), indent=1)
    segs = seg_list(mods)
    code_ranges = [(lo, hi) for n, i, lo, hi, mode in segs if "Execute" in mode]

    def in_code(v):
        return any(lo <= v < hi for lo, hi in code_ranges)

    binfiles = {}
    for name, i, lo, hi, mode in segs:
        fn = os.path.join(a, "bin", "%s.seg%d.%x.bin" % (name, i, lo))
        d = mem.read(lo, hi - lo) or b""
        open(fn, "wb").write(d)
        binfiles[(name, i)] = (fn, lo, hi, mode, len(d))
        print("%-24s seg %d %#x-%#x %-10s %d bytes" % (name, i, lo, hi, mode, len(d)), flush=True)
    for m in mods:
        name = m["name"]
        ex = [(k, v) for k, v in binfiles.items() if k[0] == name and "Execute" in v[3]]
        lst = os.path.join(a, "dis", name + ".s")
        with open(lst, "w") as out:
            for k, (fn, lo, hi, mode, n) in ex:
                subprocess.run(objdump_cmd(fn, lo), stdout=out, check=True)
        # indexes from the listing
        idx = os.path.join(a, "idx", name)
        calls = open(idx + ".calls.tsv", "w")
        rip = open(idx + ".riprel.tsv", "w")
        sysc = open(idx + ".syscalls.tsv", "w")
        starts = set()
        stubs = {}  # address of `jmp [rip+slot]` -> slot
        pending_push = None
        last_eax = None
        n_ins = 0
        with open(lst, errors="replace") as f:
            for line in f:
                mm = LINE.match(line)
                if not mm:
                    continue
                addr = int(mm.group(1), 16)
                ins = mm.group(2).strip()
                n_ins += 1
                op = ins.split(None, 1)[0] if ins else ""
                pad = op == "int3" or ins.startswith(("nop", "data16", "cs nop", "xchg   ax,ax"))
                if pending_push is not None and ins.startswith("mov    rbp,rsp"):
                    starts.add(pending_push)  # push rbp; mov rbp,rsp: the title keeps frame pointers
                pending_push = addr if ins == "push   rbp" else None
                t = TARGET.match(ins)
                if t:
                    tgt = int(t.group(2), 16)
                    if t.group(1) == "call":
                        calls.write("%x\t%x\tcall\n" % (addr, tgt))
                        if in_code(tgt):
                            starts.add(tgt)
                    elif t.group(1) == "jmp":
                        calls.write("%x\t%x\tjmp\n" % (addr, tgt))
                r = RIPREF.search(ins)
                if r and "[rip" in ins:
                    ref = int(r.group(1), 16)
                    rip.write("%x\t%x\t%s\n" % (addr, ref, ins.split("#")[0].strip()))
                    if op == "jmp" and "QWORD PTR [rip" in ins:
                        stubs[addr] = ref
                mv = re.match(r"mov\s+eax,0x([0-9a-f]+)$", ins)
                if mv:
                    last_eax = (addr, int(mv.group(1), 16))
                if op == "syscall":
                    nr = last_eax[1] if last_eax and addr - last_eax[0] < 32 else -1
                    sysc.write("%x\t%d\n" % (addr, nr))
        calls.close()
        rip.close()
        sysc.close()
        # imports: the PLT stubs' slots and what the loader put there
        sy = Syms(mem, mods)
        with open(idx + ".imports.tsv", "w") as f:
            for stub in sorted(stubs):
                v = mem.q(stubs[stub])
                f.write("%x\t%x\t%x\t%s\n" % (stub, stubs[stub], v or 0, sy.name(v) if v else "?"))
        # code pointers in the data segments (vtables, callbacks, thread entries) and strings
        fp = open(idx + ".fptrs.tsv", "w")
        st = open(idx + ".strings.tsv", "w")
        for k, (fn, lo, hi, mode, n) in binfiles.items():
            if k[0] != name or "Execute" in mode:
                continue
            d = open(fn, "rb").read()
            for off in range(0, len(d) - 7, 8):
                v = struct.unpack_from("<Q", d, off)[0]
                if v and in_code(v):
                    fp.write("%x\t%x\n" % (lo + off, v))
                    starts.add(v)
            for s in re.finditer(rb"[\x20-\x7e]{5,200}\x00", d):
                st.write("%x\t%s\n" % (lo + s.start(), s.group()[:-1].decode("ascii")))
        fp.close()
        st.close()
        own = sorted(s for s in starts if any(lo <= s < hi for kk, (fn, lo, hi, mode, n) in ex))
        with open(idx + ".funcs.tsv", "w") as f:
            f.write("".join("%x\n" % s for s in own))
        print("%-24s %d instructions, %d function starts, %d import stubs" % (name, n_ins, len(own), len(stubs)), flush=True)


class Idx:
    def __init__(self, dump):
        self.dump = dump
        self.a = os.path.join(dump, "ana")
        self.mem = Mem(dump)
        self.mods = json.load(open(os.path.join(self.a, "modules.json")))
        self.sy = Syms(self.mem, self.mods)
        self.segs = seg_list(self.mods)
        self._funcs = {}
        self._imports = None
        self._strings = None

    def mod_of(self, addr):
        for name, i, lo, hi, mode in self.segs:
            if lo <= addr < hi:
                return name, i, lo, hi, mode
        return None

    def funcs(self, name):
        if name not in self._funcs:
            self._funcs[name] = [int(x, 16) for x in open(os.path.join(self.a, "idx", name + ".funcs.tsv"))]
        return self._funcs[name]

    def fn_start(self, addr):
        m = self.mod_of(addr)
        if not m:
            return None
        f = self.funcs(m[0])
        i = bisect.bisect_right(f, addr) - 1
        return f[i] if i >= 0 else None

    def imports(self):
        if self._imports is None:
            self._imports = {}
            for m in self.mods:
                for line in open(os.path.join(self.a, "idx", m["name"] + ".imports.tsv")):
                    p = line.rstrip("\n").split("\t")
                    self._imports[int(p[0], 16)] = (int(p[1], 16), int(p[2], 16), p[3])
        return self._imports

    def strings(self):
        if self._strings is None:
            self._strings = {}
            for m in self.mods:
                for line in open(os.path.join(self.a, "idx", m["name"] + ".strings.tsv"), errors="replace"):
                    p = line.rstrip("\n").split("\t", 1)
                    self._strings[int(p[0], 16)] = p[1]
        return self._strings

    def note(self, addr):
        imp = self.imports().get(addr)
        if imp:
            return "IMPORT " + imp[2]
        s = self.strings().get(addr)
        if s is not None:
            return 'str "%s"' % s[:70]
        m = self.mod_of(addr)
        if m and "Execute" in m[4]:
            return "code %s+0x%x" % (m[0], addr - [x for x in self.mods if x["name"] == m[0]][0]["base_vaddr"])
        v = self.mem.q(addr)
        if v is not None:
            t = ""
            if v in self.imports():
                t = " IMPORT " + self.imports()[v][2]
            elif v > 0x10000 and self.mem.map_at(v):
                t = " -> " + self.sy.name(v)
            return "[%#x]=%#x%s" % (addr, v, t)
        return ""

    def dis(self, addr, nbytes, raw=False, mark=None):
        m = self.mod_of(addr)
        if not m:
            print("%#x is not in a module" % addr)
            return
        name, i, lo, hi, mode = m
        fn = os.path.join(self.a, "bin", "%s.seg%d.%x.bin" % (name, i, lo))
        out = subprocess.run(objdump_cmd(fn, lo, addr, min(hi, addr + nbytes), raw), capture_output=True, text=True).stdout
        for line in out.splitlines():
            mm = LINE.match(line)
            if not mm:
                continue
            a = int(mm.group(1), 16)
            ins = mm.group(2).rstrip()
            extra = ""
            body = ins.split("\t")[-1].strip() if raw else ins.strip()
            t = TARGET.match(body)
            if t:
                extra = self.note(int(t.group(2), 16)) if t.group(1) in ("call", "jmp") else ""
                if t.group(1) == "call" and not extra:
                    extra = "fn"
            r = RIPREF.search(ins)
            if r:
                extra = self.note(int(r.group(1), 16))
            print("%s%x:\t%s%s" % (">>" if a == mark else "  ", a, ins, ("\t; " + extra) if extra else ""))


def grep_tsv(path, col, value):
    key = "%x" % value
    out = []
    try:
        for line in open(path):
            p = line.rstrip("\n").split("\t")
            if p[col] == key:
                out.append(p)
    except OSError:
        pass
    return out


def main():
    cmd, dump = sys.argv[1], sys.argv[2]
    if cmd == "build":
        build(dump)
        return
    ix = Idx(dump)
    if cmd == "dis":
        addr = int(sys.argv[3], 0)
        raw = "--raw" in sys.argv
        arg = [x for x in sys.argv[4:] if x != "--raw"]
        if arg and arg[0].startswith("-"):
            start = ix.fn_start(addr) or addr
            n = max(int(arg[0][1:], 0), addr - start + 64)
            print("function start %#x (%s), marked %#x" % (start, ix.sy.name(start), addr))
            ix.dis(start, n, raw, addr)
        else:
            ix.dis(addr, int(arg[0], 0) if arg else 256, raw)
    elif cmd == "fn":
        for x in sys.argv[3:]:
            a = int(x, 0)
            s = ix.fn_start(a)
            print("%#x in function %s (%s)" % (a, "%#x" % s if s else "?", ix.sy.name(s) if s else ""))
    elif cmd in ("xref", "callers"):
        addr = int(sys.argv[3], 0)
        only_w = "--w" in sys.argv
        for m in ix.mods:
            base = os.path.join(ix.a, "idx", m["name"])
            rows = [("riprel", p) for p in grep_tsv(base + ".riprel.tsv", 1, addr)] if cmd == "xref" else []
            rows += [("call", p) for p in grep_tsv(base + ".calls.tsv", 1, addr)]
            rows += [("fptr", p) for p in grep_tsv(base + ".fptrs.tsv", 1, addr)]
            for kind, p in rows:
                site = int(p[0], 16)
                text = p[2] if len(p) > 2 else ""
                if only_w and kind == "riprel":
                    dst = text.split(",")[0]
                    if "[rip" not in dst or text.startswith(("cmp", "test", "lea", "call", "jmp", "push")):
                        continue
                fs = ix.fn_start(site) if kind != "fptr" else None
                print("%-6s %x  %-56s fn %s" % (kind, site, text, ("%#x %s" % (fs, ix.sy.name(fs))) if fs else ix.sy.name(site)))
    elif cmd == "calls":  # calls <dump> <addr>: every call/tail jump inside the function that holds addr
        addr = int(sys.argv[3], 0)
        m = ix.mod_of(addr)
        f = ix.funcs(m[0])
        i = bisect.bisect_right(f, addr) - 1
        lo, hi = f[i], (f[i + 1] if i + 1 < len(f) else m[3])
        print("function %#x-%#x (%s, %d bytes)" % (lo, hi, ix.sy.name(lo), hi - lo))
        for line in open(os.path.join(ix.a, "idx", m[0] + ".calls.tsv")):
            p = line.split()
            site, tgt = int(p[0], 16), int(p[1], 16)
            if lo <= site < hi and (p[2] == "call" or not lo <= tgt < hi):
                print("  %x %s %x  %s" % (site, p[2], tgt, ix.note(tgt)))
    elif cmd == "imp":
        pat = re.compile(sys.argv[3], re.I)
        counts = {}
        for stub, (slot, val, name) in sorted(ix.imports().items()):
            if pat.search(name):
                m = ix.mod_of(stub)
                n = len(grep_tsv(os.path.join(ix.a, "idx", m[0] + ".calls.tsv"), 1, stub))
                print("stub %x slot %x -> %x %s   (%d direct call/jmp sites in %s)" % (stub, slot, val, name, n, m[0]))
    elif cmd == "str":
        pat = re.compile(sys.argv[3])
        for addr, s in sorted(ix.strings().items()):
            if pat.search(s):
                print('%x "%s"' % (addr, s[:120]))
                for m in ix.mods:
                    for p in grep_tsv(os.path.join(ix.a, "idx", m["name"] + ".riprel.tsv"), 1, addr)[:12]:
                        site = int(p[0], 16)
                        fs = ix.fn_start(site)
                        print("      ref %x  %s  fn %s" % (site, p[2], "%#x" % fs if fs else "?"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
