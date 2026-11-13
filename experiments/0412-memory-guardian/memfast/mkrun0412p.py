#!/usr/bin/env python3
"""BC5 experiment 0412, the night of 2026-11-14: the runner for one arm on a private build, written into exp 0412's own
directory. It is exp 0413's run0413p.sh (fc4fe47c on the box; itself derived from exp 0412's run0412n.sh) with
  - everything written under ~/bc5-work/exp0412/n8 (exp 0413's directory is only read),
  - exp 0412's name in the lock and queue lines,
  - faultrec0412.sh after the run, as in run0412n.sh (the kernel lines and the devcoredump beside a fault record).
Every anchor is counted. usage: mkrun0412p.py <run0413p.sh in> <run0412p.sh out>"""
import hashlib
import sys


def rep(s, old, new, n=1):
    assert s.count(old) == n, (s.count(old), old[:60])
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and hashlib.md5(s).hexdigest().startswith("fc4fe47c"), "refused: not run0413p.sh fc4fe47c"
    s = rep(s, b"set -u\n", b"# exp 0412 n8 (2026-11-14, mkrun0412p.py): written under ~/bc5-work/exp0412/n8; exp 0412's lock lines; faultrec0412.sh.\nset -u\n")
    s = rep(s, b"N=$W/exp0413/n; R=$N/raw;", b"N=$X/n8; R=$N/raw;")
    s = rep(s, b"exp0413/n/", b"exp0412/n8/", 4)
    s = rep(s, b'LINE="exp 0413 | private run $TAG ($ARM, cap $SECS s), the second title on exp0413/${WANT:0:8}, token $T"',
            b'LINE="guard exp 0412 | night run $TAG ($ARM, cap $SECS s), the second title on exp0412/${WANT:0:8}, token $T"')
    s = rep(s, b'"exp 0413 | claimed: private run $TAG, token $T', b'"guard exp 0412 | claimed: night run $TAG, token $T')
    s = rep(s, b'"exp 0413 | released: private run $TAG, token $T', b'"guard exp 0412 | released: night run $TAG, token $T')
    a = b'sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\\|gpu\\|oom\\|hung\\|SQC\\|Killed" > "$R/$TAG-dmesg-after.txt"\n'
    s = rep(s, a, a + b'[ -f "$X/faultrec0412.sh" ] && bash "$X/faultrec0412.sh" "$T0" "$BIN" "$ND" > "$R/$TAG-faultrec.txt" 2>&1   # exp 0412 sections 64-65\n')
    for line in s.split(b"\n"):  # exp 0413's directory may be named in comments only
        assert b"exp0413" not in line or line.startswith(b"#"), line[:120]
    open(sys.argv[2], "wb").write(s)
    print(f"run0412p.sh {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
