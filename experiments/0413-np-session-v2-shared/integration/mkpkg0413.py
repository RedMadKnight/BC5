"""Exp 0413: the proposed change of the shared ~/bc5-work/play-pkg.sh (97835f88) for the integrated builds. Not installed:
the shared launcher changes only on the maintainer's own word.
usage: mkpkg0413.py <play-pkg.sh> <words file: NAME=VALUE per line> <out>"""
import sys

src, wordsf, out = sys.argv[1:4]
s = open(src, "rb").read().decode("utf-8")
words = [w.strip() for w in open(wordsf, encoding="utf-8") if w.strip()]
assert all("=" in w and " " not in w for w in words)
loop = ("# exp 0413: the integration's switches (audit rows A2-A22, B16, C1-C3 of patch 0001), as the daily line fast7/lean7 ran\n"
        "# them: this title's words, not defaults in the emulator (ASTRO BOT's start crashed with them on by default). A value\n"
        "# already in the environment wins; NAME=0 there turns one off.\n"
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
     "export BC5_DIRECT_LAZY_RELEASE=${BC5_DIRECT_LAZY_RELEASE:-30,eager}  # orphan release; 10 s hung the GPU with the zero skip\n"
     "export BC5_GUARD_SPLIT=${BC5_GUARD_SPLIT:-1} BC5_GUARD_FORGET=${BC5_GUARD_FORGET:-10}\n"
     + loop +
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
open(out, "wb").write(s.encode("utf-8"))
print("ok")
