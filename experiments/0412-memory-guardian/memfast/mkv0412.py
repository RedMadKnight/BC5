#!/usr/bin/env python3
"""BC5 experiment 0412, the night series on build U resumed without arm tP (README section 99; the top session,
2026-11-14 evening, after the GPU read fault of n13P4).
  night0412v.sh from night0412u.sh: two arms in turn, tA tJ, tags n14A<k>, n14J<k> (a prefix of their own: these
                walks run on the boot that had the GPU reset of 18:40), stop file $N/STOP-n14. tA with
                BC5_DISPATCH_COUNT alternating 1 / 0 by its round, tJ with 1. Everything else as night0412u.sh.
usage: mkv0412.py <night0412u.sh> <night0412v.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412u (mku0412.py from night0412t.sh, README section 97):",
            b"# night0412v (mkv0412.py from night0412u.sh, README section 99): the series on build U resumed without arm tP: tA and\n# tJ in turn, tags n14A<k>, n14J<k> (the boot had the GPU reset of 18:40), stop file $N/STOP-n14.\n# night0412u was (mku0412.py from night0412t.sh, README section 97):")
    s = rep(s, b"# usage (on the box, detached): night0412u.sh\n", b"# usage (on the box, detached): night0412v.sh\n")
    s = rep(s, b"STOPF=$N/STOP-n13\n", b"STOPF=$N/STOP-n14\n")
    s = rep(s, b"long walks of the second title, arms tA tJ tP in turn,", b"long walks of the second title, arms tA tJ in turn (resumed after the GPU read fault of 18:40, without tP),")
    s = rep(s, b"night0412u: the stop file is there", b"night0412v: the stop file is there")
    s = rep(s, b'''    RND=$(((K + 2) / 3))   # the round: the k-th walk of each arm
    case $(((K - 1) % 3)) in
        0) arm "n13A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n13J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
        2) arm "n13P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
    esac
''', b'''    RND=$(((K + 1) / 2))   # the round: the k-th walk of each arm
    case $(((K - 1) % 2)) in
        0) arm "n14A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n14J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
    esac
''')
    body = s.split(b"\nset -u\n", 1)[1]
    assert b"n13" not in body and b"APR_POSIX" not in body
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
