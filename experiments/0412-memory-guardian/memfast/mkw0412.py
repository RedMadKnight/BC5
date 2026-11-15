#!/usr/bin/env python3
"""BC5 experiment 0412, the series on exp 0419's build W (README section 102; to be started on the top's word).
  night0412w.sh from night0412v.sh: arms tA and tP in turn, tags n15A<k>, n15P<k>, stop file $N/STOP-n15.
                tA: the words as they are, BC5_DISPATCH_COUNT alternating 1 / 0 by round (the price of W's
                "FileSystem never lazy" against the tA walks of U, GTT and pin at 420 s and 600 s);
                tP: KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0, the arm whose fourth walk on U
                faulted in FileSystem (n13P4): whether the fix holds there.
                tJ is gone: W has both AJM fixes on for good. Everything else as night0412v.sh.
usage: mkw0412.py <night0412v.sh> <night0412w.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412v (mkv0412.py from night0412u.sh, README section 99):",
            b"# night0412w (mkw0412.py from night0412v.sh, README section 102): the series on build W: tA and tP in turn, tags\n# n15A<k>, n15P<k>, stop file $N/STOP-n15.\n# night0412v was (mkv0412.py from night0412u.sh, README section 99):")
    s = rep(s, b"# usage (on the box, detached): night0412v.sh\n", b"# usage (on the box, detached): night0412w.sh\n")
    s = rep(s, b"STOPF=$N/STOP-n14\n", b"STOPF=$N/STOP-n15\n")
    s = rep(s, b"arms tA tJ in turn (resumed after the GPU read fault of 18:40, without tP),", b"arms tA tP in turn on build W (FileSystem never lazy),")
    s = rep(s, b"night0412v: the stop file is there", b"night0412w: the stop file is there")
    s = rep(s, b'''        0) arm "n14A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n14J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
''', b'''        0) arm "n15A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n15P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
''')
    a = b'''    echo "$tag AJM ids given out while still alive: '''
    s = rep(s, a, b'''    echo "$tag kl412, the last line: $(grep -a '^k1r written chunks (exp 0412, tag kl412): t ' "$J" 2> /dev/null | tail -1 | cut -c1-160)"\n    echo "$tag pinned at the end: $(grep -a '^direct: [0-9]* views' "$J" 2> /dev/null | tail -1 | sed 's/^.*(\\([0-9]*, [0-9.]* MiB pinned\\)).*$/\\1/')"\n''' + a)
    body = s.split(b"\nset -u\n", 1)[1]
    assert b"n14" not in body and b"AJM_DEFER" not in body
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
