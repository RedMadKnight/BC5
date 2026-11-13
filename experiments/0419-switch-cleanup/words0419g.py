#!/usr/bin/env python3
"""BC5 experiment 0419: the environment words a tree can read, counted from the source (not from a list).
A word is a string literal "BC5_..." or "KYTY_BC5_..." (capitals, digits, underscores) in a .cpp/.hpp/.h/.inc file of
the host tree's src/ or of the backend's src/ and include/, outside comments. Literals that occur only in
src/bc5/switch_defaults.hpp are tables' rows nothing reads (kIgnored's names, a deleted word's row) and are listed
apart. Compile-time macros (BC5_LEAN, BC5_WITH_AMDGPU...) are not string literals and do not count.
The binary can hold fewer (a lean build compiles the diagnostics out): the first build must repeat this with
`strings` on the binary.
usage: words0419g.py <host src dir> <backend dir> [<direct.cpp to use instead of the backend's>] [<names file to compare>]"""
import os, re, sys

host, backend = sys.argv[1:3]
override = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
cmpf = sys.argv[4] if len(sys.argv) > 4 else None
LIT = re.compile(r'"((?:KYTY_)?BC5_[A-Z0-9_]+)"')


def strip(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)//[^\n]*$", "", s) if False else s


def lits(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    out = set()
    for line in s.split("\n"):
        code = line
        # drop a trailing // comment that is not inside a string (crude: cut at the first // outside quotes)
        q = False
        i = 0
        while i < len(code) - 1:
            c = code[i]
            if c == "\\" and q:
                i += 2
                continue
            if c == '"':
                q = not q
            elif not q and c == "/" and code[i + 1] == "/":
                code = code[:i]
                break
            i += 1
        out.update(LIT.findall(code))
    return out


where = {}
for root in (host, backend + "/src", backend + "/include"):
    for d, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith((".cpp", ".hpp", ".h", ".inc")):
                continue
            p = os.path.join(d, f)
            if override and root != host and f == "direct.cpp":
                p = override
            for w in lits(p):
                where.setdefault(w, set()).add(f)
read = sorted(w for w, fs in where.items() if fs != {"switch_defaults.hpp"})
table_only = sorted(w for w, fs in where.items() if fs == {"switch_defaults.hpp"})
print("%d words read; %d more only named in switch_defaults.hpp's tables" % (len(read), len(table_only)))
if cmpf:
    old = set(open(cmpf, encoding="utf-8").read().split())
    print("gone since: %s" % " ".join(sorted(old - set(read))))
    print("new since: %s" % " ".join(sorted(set(read) - old)))
else:
    print("\n".join(read))
