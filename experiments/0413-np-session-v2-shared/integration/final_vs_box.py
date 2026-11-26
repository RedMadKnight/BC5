"""Every file of the replayed tree that differs from the shared tree (kp): its md5 against the box copy the private build
compiled (g412L2 line), found by md5 + basename among scratchpad/int/box, and against the expected one."""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.dirname(HERE)
KP = os.path.join(os.path.dirname(INT), "kp")
TREE = os.path.join(HERE, "tree")
BOX = os.path.join(INT, "box")
# the file the private build compiled (or included), per unit; e8's units from e8 build.txt's last writer
EXPECT = {
    "src/libs/bc5LleAgc.cpp": "exp0412/L2/src/bc5LleAgc.cpp",
    "src/kernel/memory.cpp": "exp0412/v/out/src/kernel/memory.cpp",
    "src/kernel/eventQueue.cpp": "exp0412/e/out/src/kernel/eventQueue.cpp",
    "src/graphics/host_gpu/renderer/sync.cpp": "exp0412/e/out/src/graphics/host_gpu/renderer/sync.cpp",
    "src/kernel/event_cap0412.hpp": "exp0412/kit-e/event_cap0412.hpp",
    "src/libs/libAmpr.cpp": "exp0409/out/amm/libAmpr.cpp",
    "src/graphics/presentation/hostMenu.cpp": "exp0409/out/menu/hostMenu.cpp",
    "src/loader/systemContent.cpp": "exp0401e8/mem/src/loader/systemContent.cpp",
    "src/loader/systemContent.h": "exp0401e8/mem/src/loader/systemContent.h",
    "src/libs/libNpCppWebApi.cpp": "exp0401e8/x5-fwn/src/libs/libNpCppWebApi.cpp (not copied; build.txt e613bc8f)",
}
LAST = {}  # e8: unit -> last writer's dir, from the box0401 rows order in e8-build.txt
import re
txt = open(os.path.join(INT, "e8-build.txt"), encoding="utf-8").read()
order = []
for ser in ("e4", "e5", "e6", "e7", "e8"):
    for line in txt.splitlines():
        m = re.match(r"%s (\w+) mk\S+\.py (.*)$" % ser, line)
        if m and not line.startswith(ser + " test"):
            order.append((ser, m.group(1), m.group(2)))
for ser, tag, rest in order:
    for f in rest.split():
        if f.startswith("src/"):
            rel = f.split(":")[0]
            LAST[rel] = ("exp0401e8/x-%s/%s" if ser == "e4" else "exp0401e8/x5-%s/%s") % (tag, rel)
for rel, p in LAST.items():
    EXPECT.setdefault(rel, p)


def md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


idx = {}
for d, _, fs in os.walk(BOX):
    for f in fs:
        p = os.path.join(d, f)
        idx.setdefault(md5(p), []).append(os.path.relpath(p, BOX).replace(os.sep, "/"))
rows = []
for d, dirs, fs in os.walk(TREE):
    if ".git" in dirs:
        dirs.remove(".git")
    for f in fs:
        p = os.path.join(d, f)
        rel = os.path.relpath(p, TREE).replace(os.sep, "/")
        k = os.path.join(KP, rel)
        m = md5(p)
        if os.path.exists(k) and md5(k) == m:
            continue
        exp = EXPECT.get(rel, "?")
        ep = os.path.join(BOX, exp.split(" ")[0])
        em = md5(ep) if os.path.exists(ep) else "(no local copy)"
        same = [x for x in idx.get(m, []) if os.path.basename(x) == os.path.basename(rel)]
        rows.append("%s\t%s\t%s\t%s\t%s\t%s" % (rel, m, "SAME" if m == em else "DIFF", exp, em, ";".join(same[:3]) or "-"))
sys.stdout.buffer.write(("unit\treplay md5\tvs box\tbox copy\tbox md5\tbox files with this md5 and name\n" + "\n".join(sorted(rows)) + "\n").encode())
