"""stackhist.py <eu-sampler file> <thread name> [depth]
For one thread: how many samples were running vs sleeping, which host functions they were in
(the innermost named KytyPlus/bc5 frame), and the call chains below the direct path's entry."""
import re, sys, collections
path, want = sys.argv[1], sys.argv[2]
depth = int(sys.argv[3]) if len(sys.argv) > 3 else 4
txt = open(path, encoding="utf-8", errors="replace").read()
blocks = txt.split("== sample ")[1:]
n = 0; states = collections.Counter(); inner = collections.Counter(); chains = collections.Counter(); area = collections.Counter()
host_markers = ("Bc5Gc", "bc5::", "LibKernel", "Graphics::", "LibAmpr", "Loader::", "Libs::")
def clean(f):
    f = re.sub(r"^#\d+\s+0x[0-9a-f]+\s*", "", f.strip())
    mod = ""
    m = re.search(r"\s+-\s+(/\S+)$", f)
    if m:
        mod = m.group(1).rsplit("/", 1)[-1]
        f = f[: m.start()]
    f = re.sub(r"\(.*\)( const)?$", "", f)
    f = re.sub(r"<.*>", "<>", f)
    return f.strip(), mod
for b in blocks:
    lines = b.splitlines()
    th = lines[1] if len(lines) > 1 else ""
    tid = None; st = "?"
    for m in re.finditer(r"(\d+):([^:]+):(\S)", th):
        if m.group(2) == want:
            tid, st = m.group(1), m.group(3)
    if tid is None:
        continue
    cur = None; frames = []
    for l in lines[2:]:
        m = re.match(r"TID (\d+):", l)
        if m:
            cur = m.group(1); continue
        if cur == tid and l.strip().startswith("#"):
            frames.append(clean(l))
    if not frames:
        continue
    n += 1; states[st] += 1
    named = [f for f, mod in frames if f and any(k in f for k in host_markers)]
    top_mod = frames[0][1] or frames[0][0][:30]
    first = named[0] if named else "(no host frame)"
    inner[(first, top_mod if not frames[0][0] or not any(k in frames[0][0] for k in host_markers) else "")] += 1
    chains[" < ".join(x.split("::")[-1] for x in named[:depth])] += 1
    a = "title code"
    for f in named:
        if "Bc5Gc::Direct" in f or "bc5::direct" in f or "bc5::policy" in f or "full_state" in f or "state_stack" in f or "indirect_check" in f or "SoftCp" in f:
            a = "direct path"; break
        if "LibKernel" in f or "LibAmpr" in f:
            a = "kernel/AMM HLE"; break
        if "Graphics::" in f:
            a = "graphics HLE"; break
        if "Loader::" in f:
            a = "loader"; break
    if st == "S":
        a += " (sleeping)"
    area[a] += 1
print(f"{want}: {n} samples, states {dict(states)}")
print("areas:")
for k, v in area.most_common():
    print(f"  {v:4d} {k}")
print("innermost host function (and the module of the top frame when it is outside the host):")
for (f, mod), v in inner.most_common(18):
    print(f"  {v:4d} {f[:90]} {('[' + mod + ']') if mod else ''}")
print("chains:")
for k, v in chains.most_common(12):
    print(f"  {v:4d} {k[:160]}")
