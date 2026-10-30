#!/usr/bin/env python3
"""Recount the warnings of a boxcheck build.out, without the colour codes.

The shared flags hold -fcolor-diagnostics, so boxbuild_port.py's WARNING pattern matched no line of run2's compiles and its
"new warnings 0 of 0" says nothing. This reads the log's four unit compiles, baseline and fixed in turn, up to the
"== warnings:" line, with the runner's own pattern after the codes are removed.
usage: recount_warnings.py <build.out>
"""
import collections
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
WARNING = re.compile(r"^(?:.*[/\\])?([^/\\:]+):\d+:\d+: warning: (.*)$")


def main():
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        lines = [ANSI.sub("", line.rstrip("\r\n")) for line in f]
    compiles = []
    for line in lines:
        if line.startswith("== warnings:"):
            break
        if line.startswith("+ "):
            compiles.append(collections.Counter())
        else:
            m = WARNING.match(line)
            if m and compiles:
                compiles[-1][m.groups()] += 1
    if len(compiles) != 4:
        print(f"expected 4 compiles before the warnings line, found {len(compiles)}")
        return 1
    base, fixed = compiles[0] + compiles[2], compiles[1] + compiles[3]
    new = fixed - base
    gone = base - fixed
    print(f"baseline {sum(base.values())}, fixed {sum(fixed.values())}, new {sum(new.values())}, gone {sum(gone.values())}")
    for key, count in sorted(fixed.items()):
        print(f"fixed: {count} x {key[0]}: {key[1]}")
    for key, count in sorted(new.items()):
        print(f"new: {count} x {key[0]}: {key[1]}")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
