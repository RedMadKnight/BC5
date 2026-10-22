#!/usr/bin/env python3
# Replace the sections of the listed files in patch 0001 with the box checkout's current diff;
# every other section stays byte-identical.  splice0193.py <in.patch> <out.patch> <file>...
import re, subprocess, sys

src, dst, files = sys.argv[1], sys.argv[2], sys.argv[3:]
kp = "/home/kjaniszewski/src/KytyPlus"
parts = re.split(r"(?m)^(?=diff --git )", open(src, newline="").read())
out, replaced = [], set()
for part in parts:
    hit = next((f for f in files if part.startswith(f"diff --git a/{f} b/{f}\n")), None)
    if hit is None:
        out.append(part)
        continue
    new = subprocess.run(["git", "-C", kp, "diff", "HEAD", "--", hit], check=True,
                         capture_output=True).stdout.decode("utf-8", "surrogateescape")
    assert new.startswith(f"diff --git a/{hit} "), hit
    out.append(new)
    replaced.add(hit)
missing = set(files) - replaced
assert not missing, missing
open(dst, "w", newline="", encoding="utf-8", errors="surrogateescape").write("".join(out))
old_other = [p for p in parts if not any(p.startswith(f"diff --git a/{f} ") for f in files)]
new_parts = re.split(r"(?m)^(?=diff --git )", "".join(out))
new_other = [p for p in new_parts if not any(p.startswith(f"diff --git a/{f} ") for f in files)]
print("sections", len(parts), "->", len(new_parts), "; others identical:", old_other == new_other)
