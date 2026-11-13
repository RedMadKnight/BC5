#!/usr/bin/env bash
# BC5 exp 0412: install the maintainer's test shortcut "BC5 emulator (0412 K1r test)" in place of "BC5 emulator (0412
# fast9 bez Plasmy)" (his word of 2026-11-13, relayed by the top: "Tak, zamien"; README section 74).
#   - the wrapper play-guard-0412.sh is replaced by the copy with the arm k1rcut (the old one kept beside it);
#   - the old shortcut is MOVED to ~/bc5-work/trash-20261113/pulpit, not deleted;
#   - the new .desktop file is validated and put on the desktop.
# Nothing else is touched: no other shortcut, no shared launcher, no save. No emulator is started (one dry run of the
# wrapper, which starts nothing).
# usage (on the box, kit in ~/bc5-work/exp0412/kit-sc): bash install0412k.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0412; KIT=$E/kit-sc; LOCK=$W/BOX-LOCK
OLDW=eb4feddcf2dde9ad3a3dde4c4f1a8631; NEWW=b1080e6f425de7895206ab3a11d0994c; BIN=be507cd56ea4e04448fb7e48811b00c5
OLDN="BC5 emulator (0412 fast9 bez Plasmy)"; NEWN="BC5 emulator (0412 K1r test)"
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
[ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
[ -d "$DESK" ] && [ ! -L "$DESK" ] || die "no desktop directory $DESK"
[ "$(m "$KIT/play-guard-0412.sh")" = "$NEWW" ] || die "the kit's wrapper is not $NEWW"
[ "$(m "$E/play-guard-0412.sh")" = "$OLDW" ] || [ "$(m "$E/play-guard-0412.sh")" = "$NEWW" ] || die "the box's wrapper is $(m "$E/play-guard-0412.sh"), neither $OLDW nor $NEWW"
grep -qxF "$BIN  bin-d/kyty_emulator" "$E/built-d.md5" && [ "$(m "$E/bin-d/kyty_emulator")" = "$BIN" ] || die "bin-d is not g412zd $BIN"
bash -n "$KIT/play-guard-0412.sh" || die "the kit's wrapper does not parse"
[ -f "$KIT/$NEWN.desktop" ] && grep -qxF "Name=$NEWN" "$KIT/$NEWN.desktop" || die "no new .desktop file in the kit"
grep -qxF "Exec=/usr/bin/env BC5_0412_LEAN=1 /usr/bin/bash $E/play-guard-0412.sh k1rcut" "$KIT/$NEWN.desktop" || die "the new .desktop file's Exec line is not the expected one"
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$KIT/$NEWN.desktop" || die "the new .desktop file is not valid"; fi
[ ! -e "$DESK/$NEWN.desktop" ] || grep -qxF "Name=$NEWN" "$DESK/$NEWN.desktop" || die "$DESK/$NEWN.desktop exists and is not ours"
# 1. the wrapper
if [ "$(m "$E/play-guard-0412.sh")" = "$OLDW" ]; then
  cp -p "$E/play-guard-0412.sh" "$E/play-guard-0412.sh.before-k1rcut-${OLDW:0:8}" || die "cannot keep the old wrapper"
  cp "$KIT/play-guard-0412.sh" "$E/play-guard-0412.sh.new-$$" && chmod 755 "$E/play-guard-0412.sh.new-$$" && mv -fT "$E/play-guard-0412.sh.new-$$" "$E/play-guard-0412.sh" || die "cannot put the wrapper"
fi
[ "$(m "$E/play-guard-0412.sh")" = "$NEWW" ] || die "the wrapper in place is not $NEWW"
echo "== the wrapper's dry run (starts nothing)"
BC5_0412_LEAN=1 /usr/bin/bash "$E/play-guard-0412.sh" k1rcut dry || die "the dry run failed; the old wrapper is $E/play-guard-0412.sh.before-k1rcut-${OLDW:0:8}"
/usr/bin/bash "$E/play-guard-0412.sh" k1rcut words > "$E/k1rcut-words.txt" || die "no words"
/usr/bin/bash "$E/play-guard-0412.sh" fast9 words > /dev/null || echo "NOTE: arm fast9 no longer gives its words"
# 2. the shortcuts
T=$W/trash-20261113/pulpit
if [ -e "$DESK/$OLDN.desktop" ]; then
  mkdir -p "$T" && mv -n "$DESK/$OLDN.desktop" "$T/" && [ ! -e "$DESK/$OLDN.desktop" ] || die "cannot move the old shortcut to $T"
  echo "moved: $OLDN.desktop -> $T"
else echo "NOTE: no $DESK/$OLDN.desktop to move"; fi
cp "$KIT/$NEWN.desktop" "$E/k1r-test.tmp.$$.desktop" && chmod +x "$E/k1r-test.tmp.$$.desktop" && mv -fT "$E/k1r-test.tmp.$$.desktop" "$DESK/$NEWN.desktop" || die "cannot write the new shortcut"
echo "== result"
echo "shortcut: $DESK/$NEWN.desktop md5 $(m "$DESK/$NEWN.desktop")"
grep -E '^(Name|Exec)=' "$DESK/$NEWN.desktop"
echo "wrapper $(m "$E/play-guard-0412.sh"); launcher play-pkg-0412.sh $(m "$E/play-pkg-0412.sh"), derived play-pkg-0412-nolearn.sh $(m "$E/play-pkg-0412-nolearn.sh"); binary bin-d $(m "$E/bin-d/kyty_emulator")"
echo "words ($(wc -l < "$E/k1rcut-words.txt")): $(tr '\n' ' ' < "$E/k1rcut-words.txt")"
echo "save directory of the launcher: $(grep -m1 'KYTY_BC5_SAVEDATA_DIR=' "$E/play-pkg-0412-nolearn.sh"); cd: $(grep -m1 '^cd ' "$E/play-pkg-0412-nolearn.sh")"
echo "ulimit: $(grep -m1 '^ulimit -c 0' "$E/play-pkg-0412-nolearn.sh")"
echo "RT in input.cfg: $(grep -i '^RayTracing\.PPSA03671=' "$W/input.cfg" || echo 'no line')"
echo "second-title shortcuts on the desktop now:"; ls "$DESK" | grep -i "emulator\|0412\|pkg" | sed 's/^/  /'
