#!/usr/bin/env python3
"""BC5 experiment 0412: night0412b.sh from night0412.sh (the top session's second GO of 2026-11-14, after arm n8B1's
GPU fault and the heartbeat's rule relayed by Codex):
  - STOP FIRST: the chain ends after the first arm that is not clean (any kernel line, a new fault record, a crash
    line, any ending but "ended at G+620"); no later arm starts;
  - only F and W arms, numbered from 7 (the arms after the GPU reset of 01:07 on the same boot); no b arm;
  - the lock claim inside a mkdir mutex (lesson R35: the empty check and the link are one step for every claimant
    that takes the same mutex; the form of exp 0413's p-scripts).
usage: mknight0412b.py <night0412.sh in> <night0412b.sh out>"""
import sys


def rep(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# usage (on the box, detached): night0412.sh\n",
            b"# night0412b (mknight0412b.py): stop first, F and W arms only from number 7, the claim inside a mkdir mutex.\n# usage (on the box, detached): night0412b.sh\n")
    a = b'[ -e "$LOCK" ] || touch "$LOCK"\n'
    s = rep(s, a, b'MUT=$LOCK.d19-claim\nmkdir "$MUT" 2> /dev/null || { echo "night0412 ended $(date +%T): NOT STARTED, another claim runs, or $MUT was left behind"; exit 1; }\nunmut() { rmdir "$MUT" 2> /dev/null; }\n' + a)
    s = rep(s, b'''the box is locked: $(cat "$LOCK")"; exit 1; }\ntl=''', b'''the box is locked: $(cat "$LOCK")"; unmut; exit 1; }\ntl=''')
    s = rep(s, b'''NOT STARTED, the claim failed"; exit 1; }''', b'''NOT STARTED, the claim failed"; unmut; exit 1; }''')
    s = rep(s, b'''a foreign line arrived during the claim"; exit 1; fi\nrm -f "$al" "$tl"\n''', b'''a foreign line arrived during the claim"; unmut; exit 1; fi\nrm -f "$al" "$tl"\nunmut\n''')
    s = rep(s, b"(F, w0, one b1), unattended, until about 07:00", b"(F and w0 only, stop at the first arm that is not clean), unattended, until about 07:00")
    a = b"    sync; sleep 15\n}\n"
    s = rep(s, a, b'''    [ "$CLEAN" = 1 ] || { echo "night0412b STOP after $tag: the arm was not clean (stop first: no later arm starts)"; echo "night0412 ended $(date +%T): STOPPED"; exit 1; }\n''' + a)
    s = rep(s, b"FN=0; WN=0; WCLEAN=0; BDONE=0; FCLEAN=0; FBAD=0\n", b"FN=6; WN=6; WCLEAN=0; BDONE=1; FCLEAN=0; FBAD=0   # arms 7 and later: after the GPU reset of 01:07, the same boot\n")
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
