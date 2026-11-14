#!/usr/bin/env python3
"""BC5 experiment 0412, the launcher-word arms again, with the words set to 0 (README section 95).
The four walks of night0412j.sh changed nothing: candidate F's binary sets BC5_DIRECT_LAZY_RELEASE=30,eager,
BC5_GUARD_SPLIT=1 and BC5_GUARD_FORGET=10 itself for the second title when the environment does not hold them
(src/bc5/switch_defaults.hpp, setenv without overwrite), so a launcher that leaves a word out still runs with it.
  night0412k.sh from night0412j.sh: the arms named in N11_ARMS (default "l3"): g<k> the words without
                BC5_GUARD_FORGET plus BC5_GUARD_FORGET=0; l<k> the words without the pair plus
                BC5_DIRECT_LAZY_RELEASE=0 BC5_GUARD_SPLIT=0. Everything else as night0412j.sh.
usage: mkk0412.py <night0412j.sh> <night0412k.sh>"""
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:70])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3, __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s
    s = rep(s, b"# night0412j (mkj0412.py from night0412i.sh, README section 95):",
            b"# night0412k (mkk0412.py from night0412j.sh, README section 95): the arms of N11_ARMS (default l3) with the words set\n# to 0: g<k> BC5_GUARD_FORGET=0; l<k> BC5_DIRECT_LAZY_RELEASE=0 BC5_GUARD_SPLIT=0 (the binary sets them when they are absent).\n# night0412j was (mkj0412.py from night0412i.sh, README section 95):")
    s = rep(s, b"# usage (on the box, detached): night0412j.sh\n", b"# usage (on the box, detached): night0412k.sh\n")
    s = rep(s, b"four long walks of the second title on the private build g412zg for two launcher-word arms (without BC5_GUARD_FORGET; without BC5_DIRECT_LAZY_RELEASE and BC5_GUARD_SPLIT), about 55 minutes",
            b"long walks of the second title on the private build g412zg for the launcher-word arms ${N11_ARMS:-l3} (g: BC5_GUARD_FORGET=0; l: BC5_DIRECT_LAZY_RELEASE=0 BC5_GUARD_SPLIT=0), 13 minutes each")
    i = s.index(b"FCLEAN=0; FKNOWN=0\n")
    s = s[:i] + b'''FCLEAN=0; FKNOWN=0
for A in ${N11_ARMS:-l3}; do
    stopped
    case $A in
        g[0-9]) AW=$WG; arm "n11F$A" F BC5_DISPATCH_COUNT=1 BC5_GUARD_FORGET=0 ;;
        l[0-9]) AW=$WL; arm "n11F$A" F BC5_DISPATCH_COUNT=1 BC5_DIRECT_LAZY_RELEASE=0 BC5_GUARD_SPLIT=0 ;;
        *) echo "night0412 ended $(date +%T): STOPPED, no arm $A"; exit 1 ;;
    esac
    if [ "$CLEAN" = 1 ]; then FCLEAN=$((FCLEAN + 1)); else FKNOWN=$((FKNOWN + 1)); fi
    echo "-- $(date +%T) so far: up to n11F$A, clean $FCLEAN, known CPU fault $FKNOWN"
done
echo "night0412 totals: word arms ${N11_ARMS:-l3}: clean $FCLEAN, known CPU fault $FKNOWN"
echo "night0412 ended $(date +%T): the arms are done"
'''
    open(sys.argv[2], "wb").write(s)
    print("ok")


if __name__ == "__main__":
    main()
