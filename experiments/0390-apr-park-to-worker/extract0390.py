#!/usr/bin/env python3
# BC5 experiment 0390: cut the real APR queue code out of a libAmpr.cpp, so harness0390.cpp compiles it without the
# emulator's headers. Nothing is rewritten: two line ranges are copied verbatim.
# usage: extract0390.py <libAmpr.cpp> <types.inc> <queue.inc>
import sys

lines = open(sys.argv[1], encoding="utf-8").read().split("\n")


def find(text, start=0):
    hits = [i for i in range(start, len(lines)) if lines[i].startswith(text)]
    if not hits:
        raise SystemExit(f"marker not found: {text}")
    return hits[0]


a = find("enum class AmmCommandKind : uint32_t {")
s = find("struct CommandBufferState {", a)
b = next(i for i in range(s, len(lines)) if lines[i] == "};") + 1
c = find("static int ReadHostFileToGuest(const std::string& host_path", b)
d = find("static bool AdvanceCommandBuffer(", c)
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write("\n".join(lines[a:b]) + "\n")
open(sys.argv[3], "w", encoding="utf-8", newline="\n").write("\n".join(lines[c:d]) + "\n")
print(f"types lines {a + 1}-{b}, queue lines {c + 1}-{d}")
