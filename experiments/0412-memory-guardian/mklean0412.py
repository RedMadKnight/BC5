#!/usr/bin/env python3
"""BC5 exp 0412 (README section 43): the lean launcher play-pkg-0412-lean.sh, made from play-pkg-0412.sh:
the lean binary, and the launcher's own BC5_LEAN branch opened (it refused: "there is no private lean build").
Everything else is the launcher's text; with BC5_LEAN=1 it already leaves out the journal, the timing and frame-profile
switches, the FPS counter, the audio trace, the measure lines, the input recorder and the timeout probe, and sends the
emulator's output to /dev/null. Then writes built-lean.md5 (the binary and the launcher) for play-lean-0412.sh.
usage (on the box): mklean0412.py <exp0412 dir>"""
import hashlib
import os
import sys

e = sys.argv[1]
s = open(os.path.join(e, "play-pkg-0412.sh"), newline="").read()


def rep(s, a, b):
    assert s.count(a) == 1, (a[:60], s.count(a))
    return s.replace(a, b)


s = rep(s, "EMU=/home/kjaniszewski/bc5-work/exp0412/bin/kyty_emulator  # exp 0412: the private build",
        "EMU=/home/kjaniszewski/bc5-work/exp0412/bin-lean/kyty_emulator  # exp 0412: the private LEAN build (mk0412L.sh)")
s = rep(s, "if [ \"${BC5_LEAN:-0}\" = 1 ]; then\n  echo \"exp 0401: there is no private lean build\"; exit 1\nfi\n",
        "[ \"${BC5_LEAN:-0}\" = 1 ] || { echo \"exp 0412: this launcher is the lean one; BC5_LEAN=1 is not set\"; exit 1; }\n")
s = rep(s, "LOG=/home/kjaniszewski/bc5-work/exp0412/play-last.log  # exp 0412: own log",
        "LOG=/home/kjaniszewski/bc5-work/exp0412/play-lean-last.log  # exp 0412 lean: used only with BC5_LOGS=1")
out = os.path.join(e, "play-pkg-0412-lean.sh")
open(out, "w", newline="").write(s)
os.chmod(out, 0o755)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


open(os.path.join(e, "built-lean.md5"), "w").write(
    f"{md5(os.path.join(e, 'bin-lean', 'kyty_emulator'))}  bin-lean/kyty_emulator\n{md5(out)}  play-pkg-0412-lean.sh\n")
print(open(os.path.join(e, "built-lean.md5")).read().strip())
