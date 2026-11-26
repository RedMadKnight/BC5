#!/usr/bin/env python3
"""BC5 experiment 0412, build g412zg and its chain (README section 91; the maintainer's yes of 2026-11-14, relayed by
the top session: long walks on F with the three catchers, repeated until the hang comes again).
  mk0412zg.sh   from mk0412zf.sh: kit-zg, raw-zg; two more CPU tests (ph0412, dw0412); two more unit steps
                (mkph0412.py -> 4a8d5211, mkdw0412.py -> a53e98b7); the binary beside as bin-g with built-g.md5,
                so bin-n (f8cb77ad) stays as it is.
  night0412g.sh from night0412b.sh: bin-g; F arms only, n9F1..n9F8; the three catchers and the snapshot of the
                buffer both candidate dispatches of n8F8 were given; a stop file looked at before every arm (the
                stop command is a touch of that file: no process is matched by name); stop first as before.
usage: mkzg0412.py <mk0412zf.sh> <mk0412zg.sh> <night0412b.sh> <night0412g.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 5, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# BC5 exp 0412, build g412zf (2026-11-14, README section 85):", b"# BC5 exp 0412, build g412zg (2026-11-14, README section 91; mkzg0412.py from mk0412zf.sh): g412zf plus ph412\n# (BC5_FAULT_POINTERS), tl412 (BC5_TIMEOUT_LAYOUT), dc412 (BC5_DISPATCH_COUNT), all default off; the binary goes to bin-g.\n# g412zf was (README section 85):")
    s = rep(s, b"KIT=$X/kit-zf;", b"KIT=$X/kit-zg;")
    s = rep(s, b"build g412zf", b"build g412zg", 3)
    s = rep(s, b"(candidate F + bd412 + wc412 + kc412 + the ff412 arming line, private copies; CPU only)", b"(g412zf + ph412 + tl412 + dc412, private copies; CPU only)")
    s = rep(s, b"R=$X/raw-zf;", b"R=$X/raw-zg;")
    s = rep(s, b"for t in bd0412 wc0412 kc0412 ww0412 k1r0412; do", b"for t in bd0412 wc0412 kc0412 ww0412 k1r0412 ph0412 dw0412; do")
    s = rep(s, b'rm -f "$P"/f-u[12].cpp "$P"/f-memory.cpp\n', b'rm -f "$P"/f-u[1234].cpp "$P"/f-memory.cpp\n')
    a = b'step mkkc0412.py unit "$P/f-u1.cpp" "$P/f-u2.cpp" 7af3f752\n'
    s = rep(s, a, a + b'step mkph0412.py - "$P/f-u2.cpp" "$P/f-u3.cpp" 4a8d5211\nstep mkdw0412.py - "$P/f-u3.cpp" "$P/f-u4.cpp" a53e98b7\n')
    s = rep(s, b'cp "$P/f-u2.cpp" "$P/tree/src/libs/bc5LleAgc.cpp"', b'cp "$P/f-u4.cpp" "$P/tree/src/libs/bc5LleAgc.cpp"')
    s = rep(s, b'for s in BC5_GUARD_COVER_LOG "tag kc412"', b'for s in BC5_FAULT_POINTERS "tag ph412" BC5_TIMEOUT_LAYOUT "tag tl412" BC5_DISPATCH_COUNT "tag dc412" BC5_GUARD_COVER_LOG "tag kc412"')
    s = rep(s, b"bin-n", b"bin-g", s.count(b"bin-n"))
    s = rep(s, b"built-n.md5", b"built-g.md5", s.count(b"built-n.md5"))
    s = rep(s, b'echo "$(date \'+%F %T\') built: g412zf"', b'echo "$(date \'+%F %T\') built: g412zg"')
    assert b"zf" not in s.replace(b"mk0412zf.sh", b"").replace(b"g412zf", b""), "a zf name is left"
    open(sys.argv[2], "wb").write(s)

    s = open(sys.argv[3], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412b (mknight0412b.py):", b"# night0412g (mkzg0412.py from night0412b.sh, README section 91): build g412zg in bin-g; F arms only, n9F1..n9F8, with\n# BC5_TIMEOUT_LAYOUT, BC5_DISPATCH_COUNT, BC5_FAULT_POINTERS and the timeout snapshot; a stop file looked at before\n# every arm (touch $N/STOP-n9: the arm in flight ends by itself, no later arm starts); N9_DRY=1 with the stop file\n# present is the dry check of that path (claims, sees the file, releases; no arm).\n# night0412b was (mknight0412b.py):")
    s = rep(s, b"# usage (on the box, detached): night0412b.sh\n", b"# usage (on the box, detached): night0412g.sh\n")
    s = rep(s, b"BIN=$X/bin-n/kyty_emulator;", b"BIN=$X/bin-g/kyty_emulator;")
    s = rep(s, b'grep -qxF "$MD  bin-n/kyty_emulator" "$X/built-n.md5" || { echo "night0412 ended $(date +%T): NOT STARTED, bin-n is not the build in built-n.md5"; exit 1; }',
            b'grep -qxF "$MD  bin-g/kyty_emulator" "$X/built-g.md5" || { echo "night0412 ended $(date +%T): NOT STARTED, bin-g is not the build in built-g.md5"; exit 1; }\nSTOPF=$N/STOP-n9\nif [ "${N9_DRY:-0}" = 1 ]; then [ -e "$STOPF" ] || { echo "night0412 ended $(date +%T): NOT STARTED, a dry check needs the stop file"; exit 1; }\nelse [ ! -e "$STOPF" ] || { echo "night0412 ended $(date +%T): NOT STARTED, the stop file $STOPF is there"; exit 1; }; fi')
    s = rep(s, b"the night's long walks of the second title on the private build g412zf (F and w0 only, stop at the first arm that is not clean), unattended, until about 07:00",
            b"long walks of the second title on the private build g412zg (F only, up to 8, stop at the first arm that is not clean; the maintainer's yes), about 2 hours")
    s = rep(s, b'echo "binary $MD (bin-n);', b'echo "binary $MD (bin-g);')
    s = rep(s, b"CATCH=(KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1)",
            b"CATCH=(KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1 BC5_TIMEOUT_LAYOUT=1 BC5_DISPATCH_COUNT=1 BC5_FAULT_POINTERS=1 BC5_DIRECT_SNAP_ON_TIMEOUT=11a5ae8000:1572864)")
    a = b'''    echo "$tag journal: would-learn'''
    s = rep(s, a, b'''    echo "$tag dispatch count: $(grep -a '^dispatch count (exp 0412, tag dc412): t ' "$J" 2> /dev/null | tail -1 | cut -c1-240)"\n    echo "$tag timeout layout: $(grep -a -c 'tag tl412' "$J" 2> /dev/null) line(s); files: $(ls "$(dirname "$J")" 2> /dev/null | grep -c '^timeout-')"\n''' + a)
    i = s.index(b'late() { [ "$(date +%H%M)"')
    s = s[:i] + b'''stopped() { if [ -e "$STOPF" ]; then echo "night0412g: the stop file is there, no further arm"; echo "night0412 ended $(date +%T): STOPPED by the stop file"; exit 0; fi; }
stopped
[ "${N9_DRY:-0}" = 1 ] && { echo "night0412 ended $(date +%T): a dry check ran past the stop file: WRONG"; exit 1; }
FCLEAN=0
for FN in 1 2 3 4 5 6 7 8; do
    stopped
    arm "n9F$FN" F
    FCLEAN=$((FCLEAN + 1))
    echo "-- $(date +%T) so far: F arms $FN, clean $FCLEAN"
done
echo "night0412 totals: F arms 8, clean $FCLEAN: the hang did not come"
echo "night0412 ended $(date +%T): eight walks done"
'''
    assert b"bin-n/" not in s and b"n8W" not in s.split(b"\nstopped() {")[1]
    open(sys.argv[4], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
