#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G: a crude stand-in for -Wunused-function / -Wunused-variable on a unit the laptop
cannot compile (bc5LleAgc.cpp is Linux-only). For every `static` function or variable defined at the start of a line
(any indentation of namespaces' bodies is at column 0 or one tab here), it counts the name's uses as a whole word in
the unit, comments and string literals stripped. A name that occurs once is defined and never used; twice, when one
is a forward declaration. Run on the tree before and after an edit: the NEW names are the edit's leftovers.
usage: unused0419g.py <file> [<baseline file>]"""
import re, sys


def strip(s):
    s = re.sub(r"//[^\n]*", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', s)
    return s


def unused(path):
    s = strip(open(path, encoding="utf-8", errors="replace", newline="").read().replace("\r\n", "\n"))
    out = set()
    defs = {}
    for m in re.finditer(r"^\t?(?:static|inline|constexpr)[^\n;{=(]*?\b([A-Za-z_]\w*)\s*(\(|=|;|\{|\[)", s, re.M):
        defs.setdefault(m.group(1), 0)
        defs[m.group(1)] += 1
    for name, nd in defs.items():
        if name in ("operator", "if", "for", "while", "return"):
            continue
        uses = len(re.findall(r"\b" + re.escape(name) + r"\b", s))
        if uses <= nd:
            out.add(name)
    return out


a = unused(sys.argv[1])
if len(sys.argv) > 2:
    b = unused(sys.argv[2])
    new = sorted(a - b)
    print("%d names defined and not used (%d in the baseline); new: %s" % (len(a), len(b), " ".join(new) if new else "none"))
else:
    print("%d: %s" % (len(a), " ".join(sorted(a))))
