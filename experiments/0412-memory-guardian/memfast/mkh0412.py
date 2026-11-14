#!/usr/bin/env python3
"""BC5 experiment 0412, the second chain on build g412zg (README section 92; the top session's GO of 2026-11-14,
under the maintainer's yes "repeated until the hang comes again").
  night0412h.sh from night0412g.sh: tags n10F1..n10F8; odd arms as before (BC5_DISPATCH_COUNT=1), even arms with
                BC5_DISPATCH_COUNT=0 (tl412 and ph412 stay armed), so that dc412's effect on the hang and on the
                flip rate can be told apart; stop file STOP-n10. Nothing else changes.
usage: mkh0412.py <night0412g.sh> <night0412h.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412g (mkzg0412.py from night0412b.sh, README section 91):",
            b"# night0412h (mkh0412.py from night0412g.sh, README section 92): the second chain, tags n10F1..n10F8; odd arms with\n# BC5_DISPATCH_COUNT=1, even arms with BC5_DISPATCH_COUNT=0; stop file $N/STOP-n10.\n# night0412g was (mkzg0412.py from night0412b.sh, README section 91):")
    s = rep(s, b"# usage (on the box, detached): night0412g.sh\n", b"# usage (on the box, detached): night0412h.sh\n")
    s = rep(s, b"STOPF=$N/STOP-n9\n", b"STOPF=$N/STOP-n10\n")
    s = rep(s, b" BC5_TIMEOUT_LAYOUT=1 BC5_DISPATCH_COUNT=1 BC5_FAULT_POINTERS=1 ", b" BC5_TIMEOUT_LAYOUT=1 BC5_FAULT_POINTERS=1 ")
    s = rep(s, b'    arm "n9F$FN" F\n', b'    arm "n10F$FN" F "BC5_DISPATCH_COUNT=$((FN % 2))"\n')
    s = rep(s, b"night0412g: the stop file is there", b"night0412h: the stop file is there")
    assert b"n9F$" not in s and b"STOP-n9\n" not in s
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
