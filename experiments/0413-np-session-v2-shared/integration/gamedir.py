"""Exp 0413: the replug harness's derived launcher gets the BC5_GAME_DIR edits of play-pkg-0413.diff (the game is unpacked)."""
import sys

p = sys.argv[1]
s = open(p, "rb").read().decode("utf-8")
anchor = "diff -u \"$LAUNCH_SRC\" \"$LAUNCH\" > \"$R/play-pkg-0391.diff\"\n"
assert s.count(anchor) == 1
ins = (
    "# 0413: the unpacked game, as play-pkg-0413.diff does (three lines of the shared launcher)\n"
    "python3 - \"$LAUNCH\" <<'PYEOF' || exit 1\n"
    "import sys\n"
    "p = sys.argv[1]\n"
    "s = open(p).read()\n"
    "E = [('[ -r \"$PKG\" ] || { say \"No package at $PKG\"; exit 1; }\\n',\n"
    "      '[ -n \"${BC5_GAME_DIR:-}\" ] || [ -r \"$PKG\" ] || { say \"No package at $PKG\"; exit 1; }  # 0413: unpacked game\\n'),\n"
    "     ('if ! mountpoint -q \"$M\"; then\\n',\n"
    "      'if [ -n \"${BC5_GAME_DIR:-}\" ]; then M=$BC5_GAME_DIR  # 0413: unpacked game\\nelif ! mountpoint -q \"$M\"; then\\n'),\n"
    "     ('mountpoint -q \"$M\" || { say \"Mounting the package failed', '[ -n \"${BC5_GAME_DIR:-}\" ] || mountpoint -q \"$M\" || { say \"Mounting the package failed')]\n"
    "for a, b in E:\n"
    "    assert s.count(a) == 1, a[:50]\n"
    "    s = s.replace(a, b)\n"
    "open(p, 'w').write(s)\n"
    "PYEOF\n")
s = s.replace(anchor, ins + anchor)
old = "[ \"$(grep -c '^[-+][^-+]' \"$R/play-pkg-0391.diff\")\" = 11 ]"
assert s.count(old) == 1
s = s.replace(old, "[ \"$(grep -c '^[-+][^-+]' \"$R/play-pkg-0391.diff\")\" = 18 ]")
s = s.replace("KYTY_BC5_INPUT_TRACE=1 KYTY_BC5_SWITCH_DEFAULTS=0 ", "KYTY_BC5_INPUT_TRACE=1 BC5_GAME_DIR=/home/kjaniszewski/bc5-data/games/PPSA03671 ")
assert "BC5_GAME_DIR=/home/kjaniszewski/bc5-data/games/PPSA03671" in s
open(p, "wb").write(s.encode("utf-8"))
print("ok")
