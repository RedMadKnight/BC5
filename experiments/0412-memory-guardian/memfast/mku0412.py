#!/usr/bin/env python3
"""BC5 experiment 0412, the night series restarted on the binary after exp 0419's dead-code round (README
section 97; the top session, 2026-11-14 15:25).
  night0412u.sh from night0412t.sh: three arms in turn, tA tJ tP, tags n13A<k>, n13J<k>, n13P<k>, counted from
                one for the new binary; stop file $N/STOP-n13. Arm tD is dropped: BC5_GUARD_DESC_TARGETS=2 cost
                5 flips/s in n12D1 (20.5 against 25.0-26.3) and its MiB figure counts the same buffers every
                second. Everything else as night0412t.sh (T_BIN, T_WANT, T_WORDS, N8_WORDS_MD5, T_MAX, T_LAST,
                T_FIRST; R55; the one exception the title's known CPU fault).
usage: mku0412.py <night0412t.sh> <night0412u.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412t (mkt0412.py from night0412i.sh):",
            b"# night0412u (mku0412.py from night0412t.sh, README section 97): the series restarted on the binary after exp 0419's\n# dead-code round: arms tA tJ tP in turn (tD dropped), tags n13A<k>, n13J<k>, n13P<k>, stop file $N/STOP-n13.\n# night0412t was (mkt0412.py from night0412i.sh):")
    s = rep(s, b"# usage (on the box, detached): night0412t.sh\n", b"# usage (on the box, detached): night0412u.sh\n")
    s = rep(s, b"STOPF=$N/STOP-n12\n", b"STOPF=$N/STOP-n13\n")
    s = rep(s, b"the night series on test build T: long walks of the second title, arms tA tJ tP tD in turn,", b"the night series on the test build after the dead-code round: long walks of the second title, arms tA tJ tP in turn,")
    s = rep(s, b"night0412t: the stop file is there", b"night0412u: the stop file is there")
    s = rep(s, b'''    RND=$(((K + 3) / 4))   # the round: the k-th walk of each arm
    case $(((K - 1) % 4)) in
        0) arm "n12A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n12J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
        2) arm "n12P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
        3) arm "n12D$RND" F BC5_DISPATCH_COUNT=1 BC5_GUARD_DESC_TARGETS=2 ;;
    esac
''', b'''    RND=$(((K + 2) / 3))   # the round: the k-th walk of each arm
    case $(((K - 1) % 3)) in
        0) arm "n13A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n13J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
        2) arm "n13P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
    esac
''')
    a = b'''    echo "$tag audio trail: '''
    s = rep(s, a, b'''    echo "$tag AJM ids given out while still alive: $(grep -a -c 'given out while still alive' "$R/$tag-play.log" 2> /dev/null) line(s); the first: $(grep -a -m1 'given out while still alive' "$R/$tag-play.log" 2> /dev/null | cut -c1-220)"\n''' + a)
    assert b"n12" not in s.split(b"\nset -u\n", 1)[1] and b"DESC_TARGETS" not in s.split(b"\nset -u\n", 1)[1]
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
