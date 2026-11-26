#!/usr/bin/env python3
# BC5 experiment 0385: derive the lake kit from exp 0369's, the number replaced. Two changes: ab0385.sh gets a box-side cap
# on the run and sums the live saves in the C locale, so the top session's pin compares like with like.
# usage: python mkkit0385.py <0369 dir> <out dir>
import os, sys

src, out = sys.argv[1:3]
n = "0385"
FILES = ["setup0369.sh", "ab0369.sh", "bench0369.sh", "pl0369.py", "sn0369.py", "tz0369.py", "ana0369.sh"]
CAP = r'''# box-side cap (the top session, 2026-10-30, after a dropped ssh left an emulator running): watches only this run's
# emulator, ends with it, stops it at SECS + 60 s
setsid bash -c 'for _ in $(seq 1 60); do p=$(pgrep -n -x kyty_emulator) && break; sleep 1; done; [ -n "$p" ] || exit 0; end=$(( $(date +%s) + $1 )); while kill -0 "$p" 2>/dev/null; do if [ "$(date +%s)" -ge "$end" ]; then echo "cap: stopping emulator $p at $(date +%T)"; kill "$p"; sleep 6; kill -9 "$p" 2>/dev/null; exit 0; fi; sleep 3; done' _ $((SECS + 60)) > "$E/$tag.cap.txt" 2>&1 < /dev/null &
'''
for f in FILES:
    s = open(os.path.join(src, f), encoding="utf-8", newline="").read().replace("0369", n)
    assert s.startswith("#!")
    extra = ""
    if f == "ab0369.sh":
        a = "BP=$!\n"
        assert s.count(a) == 1
        s = s.replace(a, a + CAP)
        a = "| sort -k2 | md5sum"
        assert s.count(a) == 1
        s = s.replace(a, "| LC_ALL=C sort -k2 | md5sum")
        extra = ", the box-side cap and the C-locale saves sum added"
    head, rest = s.split("\n", 1)
    note = "# BC5 experiment %s: exp 0369's %s with 0369 -> %s%s (mkkit%s.py). Older comments below keep their wording.\n" % (n, f, n, extra, n)
    open(os.path.join(out, f.replace("0369", n)), "w", encoding="utf-8", newline="").write(head + "\n" + note + rest)
for f in ("bt0362.sh", "swz0248-z4.json"):
    open(os.path.join(out, f), "wb").write(open(os.path.join(src, f), "rb").read())
print("kit", n, "in", out)
