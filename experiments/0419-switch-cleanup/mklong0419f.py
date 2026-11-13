#!/usr/bin/env python3
"""BC5 experiment 0419: the long walk on candidate F again, after the GPU hang at 601 s of its first long run
(README section 13). Made from chk0419f.sh (lock, pad recorder, `second`). Each argument on the box is one arm:
a tag, then its words, comma-separated; every arm is the second title's walk to G+560 on F's private binary.
The chain STOPS at the first arm that is not clean (a kernel line, a fault record, an early end): the next arm is
then a decision, not a default. After each arm: the timing and the last "memory (exp 0401)" line of its journal.
usage: mklong0419f.py <chk0419f.sh> <out dir>
on the box (detached): long0419f.sh <tag>[,NAME=VALUE,...] [...]     e.g. long0419f.sh n1 n2
                       long0419f.sh n3,BC5_GUARD_K1R=0,BC5_GUARD_K1_FILTER=0"""
import sys

f, out = sys.argv[1:3]
s = open(f, encoding="utf-8", newline="").read()
assert "\r" not in s
head = s[:s.index("WD=$N/wda; KEEP=")]
a = 'exp 0419 candidate F, private: ASTRO BOT x4, the second title x6 (walk, walk K1R off, cutscene arm; twice each), lean" 60'
assert head.count(a) == 1
head = head.replace(a, 'exp 0419 candidate F, private: the long walk to G+560 again, $# arm(s), stop at the first that is not clean" $(($# * 12 + 3))')
tail = r'''[ "$#" -ge 1 ] || { echo "long0419f: arms, please"; exit 1; }
for arm in "$@"; do
    tag=${arm%%,*}; rest=${arm#"$tag"}; rest=${rest#,}
    IFS=, read -r -a ws <<< "$rest"
    t0=$(date +%s)
    PLAYS=560 second "$tag" "$BN" "$MN" "${ws[@]}"
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag words: ${rest:-none: the defaults of F}; last memory line: $(grep -a '^memory (exp 0401)' "$J" 2> /dev/null | tail -1 | cut -c1-170)"
    echo "$tag frame-profile lines over 500 ms: $(grep -a 'frame profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); fault records since it began: $(recs "$t0")"
    if [ "$OK" != 1 ] || [ "$KERN" != 0 ]; then echo "long0419f STOP at $tag: not clean (OK $OK, kernel $KERN); the arms after it were NOT run"; break; fi
done
echo "long0419f ended $(date +%T)"
'''
t = (head + tail).replace("chk0419f", "long0419f")
open(out + "/long0419f.sh", "w", encoding="utf-8", newline="\n").write(t)
print("long0419f.sh ok")
