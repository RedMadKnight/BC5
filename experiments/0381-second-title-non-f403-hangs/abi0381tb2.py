#!/usr/bin/env python3
# BC5 exp 0381: what the private r1 unit meets on the rebuilt base. Run on the laptop, reads git only. Test build 1 linked that unit
# against the archive built from <old>, so a header it reaches that changed between <old> and <new> needs a look, and anything main
# added to the tree unit is missing from the private one. It checks: the two headers carried privately are main's, every other backend
# header the unit reaches has the same text apart from the allowed lines, the unit does not reach indirect_check.hpp (whose Stats
# changed, F765), and the tree unit's own change is exactly F767's three names. A link on the box proves the symbols; this does not.
# usage: python abi0381tb2.py [old] [new]
import hashlib, re, subprocess, sys

OLD = sys.argv[1] if len(sys.argv) > 1 else "49f1116"
NEW = sys.argv[2] if len(sys.argv) > 2 else "fab8660"
PATCH = "backend/kytyplus-patches/0001-bc5-lle-agc.patch"
PRIVATE = {"acb_restore.hpp": "d01f31c6", "zero_skip.hpp": "782ca0e9"}
ALLOWED = {"full_state.hpp": {'+#include "bc5/env_flag.hpp"', "+"}}
FORBIDDEN = {"indirect_check.hpp"}
NAMES = ("BC5_DIRECT_PIECES_NO_CLEAR", "BC5_DIRECT_INDEX_BASE_DUP", "BC5_DIRECT_NO_CARRY")
fails = 0


def show(ref, path):
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "show", f"{ref}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def check(ok, text):
    global fails
    print(("ok: " if ok else "FAIL: ") + text)
    fails += 0 if ok else 1


def unit(ref):
    d = show(ref, PATCH)
    i = d.index(b"diff --git a/src/libs/bc5LleAgc.cpp b/src/libs/bc5LleAgc.cpp\n")
    j = d.index(b"\ndiff --git ", i + 1)
    lines = d[i:j].split(b"\n")
    k = next(n for n, l in enumerate(lines) if l.startswith(b"@@")) + 1
    return [l[1:].decode("utf-8") for l in lines[k:] if l.startswith(b"+")]


old_u, new_u = unit(OLD), unit(NEW)
check(hashlib.md5(("\n".join(old_u) + "\n").encode()).hexdigest()[:8] == "e7cc2f60", f"the tree unit at {OLD} is test build 1's, e7cc2f60")
pairs = [(a, b) for a, b in zip(old_u, new_u) if a != b]
same_len = len(old_u) == len(new_u)
f767 = same_len and all("env_on(std::getenv" in b and any(n in b for n in NAMES) and "std::getenv" in a for a, b in pairs)
check(f767 and {n for n in NAMES if any(n in b for _, b in pairs)} == set(NAMES), f"the tree unit's change is {len(pairs)} lines, all F767's three names")

# The headers the unit reaches: the tree unit's, plus the two the private unit adds, and whatever those include.
seen, todo = set(), {"acb_restore.hpp", "zero_skip.hpp"}
todo |= set(re.findall(r'#include "bc5/([^"]+)"', "\n".join(new_u)))
while todo:
    h = todo.pop()
    if h in seen:
        continue
    seen.add(h)
    t = show(NEW, f"backend/include/bc5/{h}")
    if t is None:
        print(f"note: bc5/{h} is not a backend header (the host's own)")
        seen.discard(h)
        continue
    todo |= set(re.findall(r'#include "bc5/([^"]+)"', t.decode("utf-8")))
print("reached:", " ".join(sorted(seen)))
for h in sorted(seen):
    n, o = show(NEW, f"backend/include/bc5/{h}"), show(OLD, f"backend/include/bc5/{h}")
    if h in PRIVATE:
        check(hashlib.md5(n).hexdigest()[:8] == PRIVATE[h], f"{h} at {NEW} is the private copy, {PRIVATE[h]}")
    elif h == "env_flag.hpp":
        check(o is None and b"inline bool env_on" in n and n.count(b"inline") == 1, "env_flag.hpp is new and only an inline function")
    elif o == n:
        check(True, f"{h} unchanged")
    else:
        r = subprocess.run(["git", "diff", "-U0", OLD, NEW, "--", f":/backend/include/bc5/{h}"], capture_output=True, text=True)
        changed = {l for l in r.stdout.split("\n") if l[:1] in "+-" and l[:3] not in ("+++", "---") and l}
        check(changed and changed <= ALLOWED.get(h, set()), f"{h}: only allowed lines changed: {sorted(changed)}")
for h in FORBIDDEN:
    check(h not in seen, f"the unit does not reach {h}")
print("ABI PASS" if fails == 0 else f"ABI FAIL {fails}")
sys.exit(1 if fails else 0)
