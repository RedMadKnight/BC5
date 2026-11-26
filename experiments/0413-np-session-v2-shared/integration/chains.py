"""Follow each unit's md5 chain in e8's build.txt from the shared tree's md5 and locate the final file on the box."""
import re
import sys

S = sys.argv[1]
txt = open(S + "/e8-build.txt", encoding="utf-8", errors="replace").read()
steps = re.findall(r"(src/[A-Za-z0-9_/]+\.(?:cpp|h|inc|hpp)):([0-9a-f]{32}):([0-9a-f]{32})", txt)
shared, files = {}, {}
for line in open(S + "/box-md5.txt", encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    md5, path = line.split(None, 1)
    path = path.lstrip("*")
    if path.startswith("SHARED:"):
        shared[path[7:]] = md5
    else:
        files.setdefault(md5, []).append(path)
succ = {}
for unit, a, b in steps:
    if a != b:
        succ.setdefault(unit, {})[a] = b
for unit in sorted({u for u, _, _ in steps}):
    cur = shared.get(unit)
    seen = [cur]
    while cur in succ.get(unit, {}):
        cur = succ[unit][cur]
        seen.append(cur)
        if len(seen) > 40:
            break
    loose = [a for a in succ.get(unit, {}) if a not in seen]
    where = files.get(cur, [])
    print(f"{unit}\tshared={shared.get(unit, '?')[:8]}\tfinal={cur[:8] if cur else '?'}\tsteps={len(seen)-1}\tunused-links={len(loose)}\t{where[0] if where else 'NOT FOUND'}")
