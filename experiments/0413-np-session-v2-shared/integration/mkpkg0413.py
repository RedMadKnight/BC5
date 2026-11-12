"""Exp 0413: the proposed change of the shared ~/bc5-work/play-pkg.sh (97835f88) for the integrated builds (patch 0001
01abfc0c). Not installed: the shared launcher changes only on the maintainer's own word.

Second version (2026-11-12, after the swap): the emulator's defaults table carries audit rows A2-A14, A18-A20, B16 and
C1-C3, so the launcher only adds what is this title's own: the 20 switches of rows A15, A16, A17, A21 and A22, the
start delay, the orphan release, split and forget. No zero skip (exp 0412 section 47: it hangs the GPU without the
ledger; off until understood). BC5_R3_SUBMIT_EOP_EVENT is listed as a comment only (Codex's review: its packet ring
can be read after a wrap).
usage: mkpkg0413.py <play-pkg.sh> <words file: NAME=VALUE per line> <out>"""
import sys

src, wordsf, out = sys.argv[1:4]
s = open(src, "rb").read().decode("utf-8")
words = [w.strip() for w in open(wordsf, encoding="utf-8") if w.strip()]
assert len(words) == 20 and all("=" in w and " " not in w for w in words)
loop = ("# exp 0413: this title's switches that are not defaults in the emulator (audit rows A15, A16, A17, A21, A22 of patch\n"
        "# 0001), as the daily line fast7/lean7 ran them. A value already in the environment wins; NAME=0 there turns one off.\n"
        "for w in \\\n")
for i in range(0, len(words), 4):
    loop += "    " + " ".join(words[i:i + 4]) + " \\\n"
loop += "    ; do\n  n=${w%%=*}; [ -n \"${!n+x}\" ] || export \"$w\"\ndone\n"
EDITS = [
    ("set -u\n",
     "set -u\n"
     "ulimit -c 0  # exp 0409/0413: no core dump of the emulator (systemd-coredump froze the desktop for minutes, 11-09)\n"),
    ('[ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }\n',
     '[ -n "${BC5_GAME_DIR:-}" ] || [ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }  # exp 0409/0413: BC5_GAME_DIR = an unpacked game, no package\n'),
    ("export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n",
     "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n"
     "# exp 0413: the second title's own words, as the tested daily line fast7/lean7 (exp 0412) ran them; each can be\n"
     "# overridden from the environment.\n"
     "export BC5_DIRECT_CP_COHER_START_DELAY=${BC5_DIRECT_CP_COHER_START_DELAY:-1}  # on in every play since 11-03; never A/B'd\n"
     "export BC5_DIRECT_LAZY_RELEASE=${BC5_DIRECT_LAZY_RELEASE:-30,eager}  # orphan release\n"
     "export BC5_GUARD_SPLIT=${BC5_GUARD_SPLIT:-1} BC5_GUARD_FORGET=${BC5_GUARD_FORGET:-10}\n"
     + loop +
     "# Optional, off here: export BC5_R3_SUBMIT_EOP_EVENT=1  (on in the daily line until 11-12; its global packet ring can be\n"
     "# read after a wrap by a deferred callback, Codex's review of exp 0413; back on once the owned-packet fix is in)\n"
     "# No zero skip (BC5_DIRECT_ZERO_SKIP): it hung the GPU in 5 of 8 runs without the ledger (exp 0412 section 47).\n"),
    ('if ! mountpoint -q "$M"; then\n',
     'if [ -n "${BC5_GAME_DIR:-}" ]; then M=$BC5_GAME_DIR  # exp 0409/0413: an unpacked game dir, no bc5-mount\nelif ! mountpoint -q "$M"; then\n'),
    ('mountpoint -q "$M" || { say "Mounting the package failed',
     '[ -n "${BC5_GAME_DIR:-}" ] || mountpoint -q "$M" || { say "Mounting the package failed'),
]
for a, b in EDITS:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(out, "wb").write(s.encode("utf-8"))
print("ok")
