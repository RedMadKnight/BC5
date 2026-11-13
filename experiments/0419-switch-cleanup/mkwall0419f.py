#!/usr/bin/env python3
"""BC5 experiment 0419: one arm OUTSIDE candidate F's acceptance, for exp 0412's memory-wall plan (step 2): the walk
to G+560 with its log-only zero scan AND its writers catcher (BC5_GUARD_WRITERS=1), the whole-box table and the
emulator's fdinfo near G+500. Made from chk0419f.sh (lock, pad recorder, `second`) and chk0419e.sh's k4wall block.
Frame numbers of this arm are not comparable (the scan preads the eager heaps on a nice-19 thread).
usage: mkwall0419f.py <chk0419f.sh> <chk0419e.sh> <out dir>"""
import sys

f, e, out = sys.argv[1:4]
sf = open(f, encoding="utf-8", newline="").read()
se = open(e, encoding="utf-8", newline="").read()
assert "\r" not in sf + se
head = sf[:sf.index("WD=$N/wda; KEEP=")]
a = se.index("# exp 0412's first measurement of the memory wall")
b = se.index('echo "candidate E, private:')
block = se[a:b]
for old, new in (("k4wall", "m5wall"),
                 ('BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,640 ', 'BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,640 BC5_GUARD_WRITERS=1 ')):
    assert old in block, old
    block = block.replace(old, new)
assert block.count("\nfi\n") >= 1
i = block.rindex("\nfi\n")
block = (block[:i] + '\n    echo "m5wall writers lines (exp 0412, tag ww412): $(grep -a -c \'^writers (exp 0412\' "$J" 2> /dev/null)"\n'
         '    grep -a \'^writers (exp 0412\' "$J" 2> /dev/null | tail -3 | cut -c1-220\nfi\n' + block[i + 4:])
head = head.replace("exp 0419 candidate F, private: ASTRO BOT x4, the second title x6 (walk, walk K1R off, cutscene arm; twice each), lean\" 60",
                    "exp 0419 / exp 0412's wall plan: one walk to G+560 on candidate F's private build with the zero scan and the writers catcher (log only)\" 16")
assert "wall plan: one walk" in head
t = head + block + 'echo "wall0419f ended $(date +%T)"\n'
t = t.replace("chk0419f", "wall0419f")
open(out + "/wall0419f.sh", "w", encoding="utf-8", newline="\n").write(t)
print("wall0419f.sh ok")
