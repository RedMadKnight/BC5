"""BC5 exp 0418 section 3b: name the exports the /dev/gc caller trace found, from public tables.

The trace (BC5_GC_IOCTL_TRACE=1, kit/0418-start-state.diff) writes lines such as
  [bc5-gc-trace] 0x80888123 #1 frame 0 0x... <module>+0x... export <NID>+0x...
This script reads such lines (a copy of the run's stderr, kept in the laptop's scratch, never committed: it holds module
offsets of the title's driver), collects the NIDs per request code and looks each NID up in the public source trees
under <refs> (emulators' NID tables, e.g. KytyPlus src/libs/libGraphicsDriver.cpp LIB_FUNC lines). It prints, per
request code, the frames and every public line that names the NID. Nothing is fetched; no NID is computed.

usage: python -I nid-names.py <trace log> <refs dir> [max matches per NID, default 4]
"""
import os
import re
import sys

LINE = re.compile(r"\[bc5-gc-trace\] (0x[0-9a-f]{8}) #(\d+) (frame|scan) (\d+) 0x[0-9a-f]+ (\S+)\+0x([0-9a-f]+)(?: export ([A-Za-z0-9+\-]+)\+0x([0-9a-f]+))?")
TEXT_EXT = {".c", ".cc", ".cpp", ".h", ".hpp", ".inl", ".inc", ".rs", ".txt", ".json", ".py", ".md", ".cs", ".pas", ".ts", ".js"}
NID_CHARS = re.compile(rb"[A-Za-z0-9+\-]")


def collect(path):
    per_code = {}
    with open(path, "rb") as f:
        for raw in f:
            m = LINE.search(raw.decode("utf-8", "replace"))
            if not m:
                continue
            code, call, kind, idx, module, off, nid, delta = m.groups()
            per_code.setdefault(code, []).append((int(call), kind, int(idx), module, nid, delta))
    return per_code


def search(refs, nids, limit):
    found = {n: [] for n in nids}
    wanted = {n.encode(): n for n in nids}
    for root, dirs, files in os.walk(refs):
        dirs[:] = [d for d in dirs if d not in (".git", "build", "node_modules")]
        for name in files:
            if os.path.splitext(name)[1].lower() not in TEXT_EXT:
                continue
            p = os.path.join(root, name)
            try:
                if os.path.getsize(p) > 64 << 20:
                    continue
                data = open(p, "rb").read()
            except OSError:
                continue
            for nb, n in wanted.items():
                if len(found[n]) >= limit:
                    continue
                start = 0
                while True:
                    i = data.find(nb, start)
                    if i < 0:
                        break
                    start = i + 1
                    before = data[i - 1:i] if i > 0 else b""
                    after = data[i + len(nb):i + len(nb) + 1]
                    if (before and NID_CHARS.match(before)) or (after and NID_CHARS.match(after)):
                        continue  # part of a longer token
                    ln = data.count(b"\n", 0, i) + 1
                    a = data.rfind(b"\n", 0, i) + 1
                    b = data.find(b"\n", i)
                    text = data[a:b if b >= 0 else len(data)].decode("utf-8", "replace").strip()
                    found[n].append(f"{os.path.relpath(p, refs)}:{ln}: {text[:160]}")
                    if len(found[n]) >= limit:
                        break
    return found


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    per_code = collect(sys.argv[1])
    nids = sorted({e[4] for v in per_code.values() for e in v if e[4]})
    names = search(sys.argv[2], nids, limit)
    for code in sorted(per_code):
        print(f"== {code}")
        seen = set()
        for call, kind, idx, module, nid, delta in sorted(per_code[code]):
            key = (kind, idx, module, nid, delta)
            if key in seen:
                continue
            seen.add(key)
            print(f"  call {call} {kind} {idx}: {module} " + (f"export {nid}+0x{delta}" if nid else "(no export at or before it)"))
    print("== NIDs")
    for n in nids:
        print(f"  {n}: {len(names[n])} public line(s)")
        for t in names[n]:
            print(f"    {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
