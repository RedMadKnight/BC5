"""Exp 0413: derive run0413p.sh from exp 0412's run0412n.sh (main ed2d2d50). Every anchor must occur exactly once."""
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, "rb").read().decode("utf-8")
EDITS = [
    ("# usage (on the box): run0412n.sh <tag> <arm> <play s after G> [KEY=VALUE ...]",
     "# exp 0413 (2026-11-12): derived by mkrun0413.py for the private build of the integration (int/0413-tested-into-shared):\n"
     "# the binary is P_BIN (pinned P_WANT) through the launcher's BC5_EMU word, the words come from the file P_WORDS, and\n"
     "# everything written lands in ~/bc5-work/exp0413/n; exp 0412's named snapshot, tools and launcher are only read.\n"
     "# usage (on the box): run0412n.sh <tag> <arm> <play s after G> [KEY=VALUE ...]"),
    ("W=$HOME/bc5-work; X=$W/exp0412; N=$X/night; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$N/saves-named",
     "W=$HOME/bc5-work; X=$W/exp0412; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$X/night/saves-named; NSF=$X/night/saves-named.sum"),
    ('if [ "${MODE:-}" = name ]; then', 'if [ "${MODE:-}" = name ]; then echo "exp 0413: no MODE=name here (exp 0412 owns the snapshot)"; exit 1\nfi\nif false; then'),
    ('BIN=$X/bin/kyty_emulator; LAUNCH_SRC=$X/play-pkg-0412.sh; LAUNCH=$N/play-pkg-0412n.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$N/direct-learned-pkg.txt',
     'BIN=${P_BIN:?the private binary}; LAUNCH_SRC=$X/play-pkg-0412.sh; LAUNCH=$N/play-pkg-0413n.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$N/direct-learned-pkg.txt'),
    ('grep -qxF "$(m "$BIN")  bin/kyty_emulator" "$X/built.md5" && grep -qxF "$(m "$LAUNCH_SRC")  play-pkg-0412.sh" "$X/built.md5" || { echo "the binary or the launcher is not the one in built.md5: not started"; exit 1; }',
     '[ "$(m "$BIN")" = "${P_WANT:?the binary md5}" ] && grep -qxF "$(m "$LAUNCH_SRC")  play-pkg-0412.sh" "$X/built.md5" || { echo "the binary is not P_WANT or the launcher is not the one in built.md5: not started"; exit 1; }'),
    ('[ -d "$NS/PPSA03671" ] && [ ! -L "$NS" ] && [ -s "$N/saves-named.sum" ] || { echo "no named snapshot (MODE=name makes it): not started"; exit 1; }',
     '[ -d "$NS/PPSA03671" ] && [ ! -L "$NS" ] && [ -s "$NSF" ] || { echo "no named snapshot of exp 0412: not started"; exit 1; }'),
    ('NSUM=$(sumof "$NS"); [ "$NSUM" = "$(cat "$N/saves-named.sum")" ] || { echo "the named snapshot reads $NSUM, not $(cat "$N/saves-named.sum"): not started"; exit 1; }',
     'NSUM=$(sumof "$NS"); [ "$NSUM" = "$(cat "$NSF")" ] || { echo "the named snapshot reads $NSUM, not $(cat "$NSF"): not started"; exit 1; }'),
    ('mapfile -t WORDS < <(bash "$X/play-guard-0412.sh" "$ARM" words) && [ "${#WORDS[@]}" -ge 70 ] || { echo "no words for arm $ARM: not started"; exit 1; }',
     'mapfile -t WORDS < <(grep -v "^#" "${P_WORDS:?the words file}" | grep .) && [ "${#WORDS[@]}" -ge 3 ] || { echo "no words in $P_WORDS: not started"; exit 1; }\nWORDS+=("BC5_EMU=$BIN")'),
    ('LINE="guard exp 0412 | night arm $TAG ($ARM, cap $SECS s), the second title on exp0412/${WANT:0:8}, unattended, token $T"',
     'LINE="exp 0413 | private run $TAG ($ARM, cap $SECS s), the second title on exp0413/${WANT:0:8}, token $T"'),
    ('printf \'%s\\n\' "guard exp 0412 | claimed: night arm $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
     'printf \'%s\\n\' "exp 0413 | claimed: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"'),
    ('  printf \'%s\\n\' "guard exp 0412 | released: night arm $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
     '  printf \'%s\\n\' "exp 0413 | released: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"'),
    ('awk -v a="$LOGA" -v b="LOG=$N/play-last.log  # exp 0412 night: own log"',
     'awk -v a="$LOGA" -v b="LOG=$N/play-last.log  # exp 0413: own log"'),
    ("cd ~/bc5-work/exp0412/night/wd  \\# exp 0412 night: the private working directory (its own _SaveData)#",
     "cd ~/bc5-work/exp0413/n/wd  \\# exp 0413: the private working directory (its own _SaveData)#"),
    ("export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0412/night/wd/_SaveData-pkg-play  \\# exp 0412 night: private#",
     "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0413/n/wd/_SaveData-pkg-play  \\# exp 0413: private#"),
    ("export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0412/night/direct-learned-pkg.txt  \\# exp 0412 night: a private copy#",
     "export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0413/n/direct-learned-pkg.txt  \\# exp 0413: a private copy#"),
    ('diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0412n.diff"', 'diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0413n.diff"'),
    ('[ "$(grep -c \'^[-+][^-+]\' "$R/play-pkg-0412n.diff")" = 9 ]', '[ "$(grep -c \'^[-+][^-+]\' "$R/play-pkg-0413n.diff")" = 9 ]'),
    ('pgrep -f "night/play-pkg-0412n.sh"', 'pgrep -f "exp0413/n/play-pkg-0413n.sh"'),
]
for a, b in EDITS:
    c = s.count(a)
    assert c == 1, (c, a[:90])
    s = s.replace(a, b)
assert "exp0412/night/wd" not in s and "night/play-pkg-0412n" not in s
open(out, "wb").write(s.encode("utf-8"))
print("ok")
