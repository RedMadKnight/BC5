"""Exp 0413: the proposed change of the shared ~/bc5-work/play-pkg.sh (97835f88) for the integrated builds. Not installed:
the shared launcher changes only on the maintainer's own word."""
import sys

s = open(sys.argv[1], "rb").read().decode("utf-8")
EDITS = [
    ("set -u\n",
     "set -u\n"
     "ulimit -c 0  # exp 0409/0413: no core dump of the emulator (systemd-coredump froze the desktop for minutes, 11-09)\n"),
    ('[ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }\n',
     '[ -n "${BC5_GAME_DIR:-}" ] || [ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }  # exp 0409/0413: BC5_GAME_DIR = an unpacked game, no package\n'),
    ("export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n",
     "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n"
     "# exp 0413: the second title's own words, as the tested daily line fast7/lean7 (exp 0412) ran them. The emulator's other\n"
     "# fixes are defaults in its code now (src/bc5/switch_defaults.hpp); each word here can be overridden from the environment.\n"
     "export BC5_DIRECT_CP_COHER_START_DELAY=${BC5_DIRECT_CP_COHER_START_DELAY:-1}  # on in every play since 11-03; never A/B'd\n"
     "export BC5_DIRECT_LAZY_RELEASE=${BC5_DIRECT_LAZY_RELEASE:-30,eager}  # orphan release; 10 s hung the GPU with the zero skip\n"
     "export BC5_GUARD_SPLIT=${BC5_GUARD_SPLIT:-1} BC5_GUARD_FORGET=${BC5_GUARD_FORGET:-10}\n"
     "# the zero skip only with its poll before every submission (exp 0412 section 40); the list is this title's, private data\n"
     "ZL=$HOME/bc5-work/zero-list-pkg.txt\n"
     "if [ -z \"${BC5_DIRECT_ZERO_SKIP+x}\" ] && [ -s \"$ZL\" ]; then export BC5_DIRECT_ZERO_SKIP=$ZL BC5_GUARD_ZSKIP_POLL_SUBMIT=${BC5_GUARD_ZSKIP_POLL_SUBMIT:-1}; fi\n"),
    ('if ! mountpoint -q "$M"; then\n',
     'if [ -n "${BC5_GAME_DIR:-}" ]; then M=$BC5_GAME_DIR  # exp 0409/0413: an unpacked game dir, no bc5-mount\nelif ! mountpoint -q "$M"; then\n'),
    ('mountpoint -q "$M" || { say "Mounting the package failed',
     '[ -n "${BC5_GAME_DIR:-}" ] || mountpoint -q "$M" || { say "Mounting the package failed'),
]
for a, b in EDITS:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(sys.argv[2], "wb").write(s.encode("utf-8"))
print("ok")
