#!/usr/bin/env python3
"""BC5 experiment 0412, the runner of the night series on test build T (exp 0419's night-series-T.md, the top
session's decisions of 2026-11-14).
  night0412t.sh from night0412i.sh. The binary, its md5 and the words file are given at the start:
                T_BIN=<kyty_emulator of T> T_WANT=<its md5, 32 hex> T_WORDS=<words file> N8_WORDS_MD5=<first 8>.
                Arms in the order tA tJ tP tD, repeated; tags n12A<k>, n12J<k>, n12P<k>, n12D<k>:
                  tA  no extra word; BC5_DISPATCH_COUNT alternates 1 / 0 (odd / even walks of tA);
                  tJ  KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1;
                  tP  KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0;
                  tD  BC5_GUARD_DESC_TARGETS=2 (dt412, log only);
                tJ, tP, tD with BC5_DISPATCH_COUNT=1; every arm with KYTY_BC5_AUDIO_TRAIL=1 and the log-only set.
                Ends at T_MAX walks (60), when the next walk would start after T_LAST (06:45 of the coming
                morning), at the stop file ($N/STOP-n12), or at the first walk that is not clean: R55 stands, the
                first kernel GPU line stops it, also after a successful reset. The one exception is the title's
                known CPU fault (as night0412i.sh). T_FIRST=<k> resumes the count after a stop (the top's GO).
usage: mkt0412.py <night0412i.sh> <night0412t.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412i (mki0412.py from night0412h.sh, README section 93):",
            b"# night0412t (mkt0412.py from night0412i.sh): the night series on test build T (exp 0419's night-series-T.md): arms\n# tA tJ tP tD in turn, up to T_MAX walks, until T_LAST, the stop file $N/STOP-n12 or the first walk that is not clean.\n# start: T_BIN=... T_WANT=<md5> T_WORDS=... N8_WORDS_MD5=<8> night0412t.sh   (T_FIRST=<k> to resume the count)\n# night0412i was (mki0412.py from night0412h.sh, README section 93):")
    s = rep(s, b"# usage (on the box, detached): night0412i.sh\n", b"# usage (on the box, detached): night0412t.sh\n")
    s = rep(s, b'''BIN=$X/bin-g/kyty_emulator; MD=$(md5sum < "$BIN" | cut -d' ' -f1)\ngrep -qxF "$MD  bin-g/kyty_emulator" "$X/built-g.md5" || { echo "night0412 ended $(date +%T): NOT STARTED, bin-g is not the build in built-g.md5"; exit 1; }\n''',
            b'''BIN=${T_BIN:?the path of the kyty_emulator of T}; [ -x "$BIN" ] || { echo "night0412 ended $(date +%T): NOT STARTED, no binary $BIN"; exit 1; }\nMD=$(md5sum < "$BIN" | cut -d' ' -f1)\n[ "$MD" = "${T_WANT:?the md5 of the binary of T}" ] || { echo "night0412 ended $(date +%T): NOT STARTED, $BIN is $MD, not $T_WANT"; exit 1; }\n''')
    s = rep(s, b"STOPF=$N/STOP-n10\n", b"STOPF=$N/STOP-n12\n")
    s = rep(s, b"WORDS=$W/exp0413/n/words0413nz.txt   # exp 0419's words for candidate F, only read\n", b'WORDS=${T_WORDS:?the words file of T}   # exp 0419\'s words for test build T, only read\n[ -s "$WORDS" ] || { echo "night0412 ended $(date +%T): NOT STARTED, no words file $WORDS"; exit 1; }\n')
    s = rep(s, b"LAST=${N8_LAST:-06:40}\n", b'LAST=${T_LAST:-06:45}; TEND=$(date -d "$LAST" +%s); [ "$TEND" -gt "$(date +%s)" ] || TEND=$(date -d "tomorrow $LAST" +%s)\nTMAX=${T_MAX:-60}; TFIRST=${T_FIRST:-1}\ncase "$TMAX$TFIRST" in *[!0-9]*) echo "night0412 ended $(date +%T): NOT STARTED, T_MAX and T_FIRST are numbers"; exit 1 ;; esac\n')
    s = rep(s, b"long walks of the second title on the private build g412zg (F only, up to 8, stop at the first arm that is not clean; the maintainer's yes), about 2 hours",
            b"the night series on test build T: long walks of the second title, arms tA tJ tP tD in turn, up to $TMAX walks or $LAST, stop at the first walk that is not clean (R55)")
    s = rep(s, b'echo "binary $MD (bin-g);', b'echo "binary $MD ($BIN); words $WORDS; walks $TFIRST..$TMAX;')
    s = rep(s, b"CATCH=(KYTY_BC5_MEM_FIRSTFAIL=1 ", b"CATCH=(KYTY_BC5_AUDIO_TRAIL=1 KYTY_BC5_MEM_FIRSTFAIL=1 ")
    a = b'''    echo "$tag dispatch count: '''
    s = rep(s, a, b'''    echo "$tag desc targets: $(grep -a '^desc targets (exp 0412, tag dt412): t [0-9]* s: mode' "$J" 2> /dev/null | tail -1 | cut -c1-220)"\n''' + a)
    s = rep(s, b"night0412i: the stop file is there", b"night0412t: the stop file is there")
    i = s.index(b"FCLEAN=0; FKNOWN=0\n")
    s = s[:i] + b'''FCLEAN=0; FKNOWN=0; K=$TFIRST
while [ "$K" -le "$TMAX" ]; do
    stopped
    [ "$(date +%s)" -lt "$TEND" ] || { echo "night0412 ended $(date +%T): the time limit $LAST; walks done up to $((K - 1)), clean $FCLEAN, known CPU fault $FKNOWN"; exit 0; }
    RND=$(((K + 3) / 4))   # the round: the k-th walk of each arm
    case $(((K - 1) % 4)) in
        0) arm "n12A$RND" F "BC5_DISPATCH_COUNT=$((RND % 2))" ;;
        1) arm "n12J$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1 ;;
        2) arm "n12P$RND" F BC5_DISPATCH_COUNT=1 KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0 ;;
        3) arm "n12D$RND" F BC5_DISPATCH_COUNT=1 BC5_GUARD_DESC_TARGETS=2 ;;
    esac
    if [ "$CLEAN" = 1 ]; then FCLEAN=$((FCLEAN + 1)); else FKNOWN=$((FKNOWN + 1)); fi
    echo "-- $(date +%T) so far: walk $K of $TMAX, clean $FCLEAN, known CPU fault $FKNOWN (this start)"
    K=$((K + 1))
done
echo "night0412 totals: walks $TFIRST..$TMAX: clean $FCLEAN, known CPU fault $FKNOWN: no GPU line"
echo "night0412 ended $(date +%T): the series is done"
'''
    assert b"bin-g" not in s.split(b"\nset -u\n", 1)[1], "bin-g is left in the code"
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
