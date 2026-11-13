#!/usr/bin/env bash
# BC5 exp 0412 (README section 60; the maintainer's order of 2026-11-13, relayed by the top session: "masz sie pozbyc
# wyuczonych okien"): the second title's shared launchers run with NO learned file from now on.
#   - in play-pkg.sh, play-pkg-log.sh and play-pkg-quiet.sh the one line that exports BC5_DIRECT_LEARNED is replaced by
#     two: the path of an EMPTY, read-only file, and BC5_GUARD_LEARN_LOG=2 (the catcher of the shared build: a GPU fault
#     is journaled as "would learn ..." with its address and kind; nothing is written and nothing is added);
#   - each old launcher is kept beside as <name>.before-nolearned; bash -n; the sums before and after are printed;
#   - the shared learned file is MOVED to today's trash directory, not deleted.
# Undo: copy the three .before-nolearned files back and move the learned file back from the trash directory.
# usage (on the box, no emulator running): bash nolearned0412.sh [dry]
set -u
export LC_ALL=C
W=$HOME/bc5-work; T=$W/trash-$(date +%Y%m%d); NONE=$W/direct-learned-none.txt; DRY=${1:-}
OLD='export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
NEW1='export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-none.txt  # 2026-11-13, the maintainer'"'"'s order (exp 0412 sections 52-56, 60): NO learned windows; an empty read-only file'
NEW2='export BC5_GUARD_LEARN_LOG=${BC5_GUARD_LEARN_LOG:-2}  # the catcher: a GPU fault is journaled ("would learn ..." in gc/direct.log) with its address and kind; nothing is written, nothing added'
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do
  [ -f "$W/$f" ] || die "no $W/$f"
  [ "$(grep -cxF -- "$OLD" "$W/$f")" = 1 ] || die "$f does not hold the learned line exactly once"
  [ ! -e "$W/$f.before-nolearned" ] || die "$f.before-nolearned exists already"
done
grep -aqF BC5_GUARD_LEARN_LOG "$W/kytyplus-build/src/kyty_emulator" || die "the shared normal build has no BC5_GUARD_LEARN_LOG"
grep -aqF BC5_GUARD_LEARN_LOG "$W/kytyplus-build-lean/src/kyty_emulator" || die "the shared lean build has no BC5_GUARD_LEARN_LOG"
[ "$DRY" = dry ] && { echo "dry: the three launchers hold the line once each; both shared builds know the catcher; nothing changed"; exit 0; }
[ -e "$NONE" ] || { : > "$NONE" && chmod 444 "$NONE"; } || die "cannot make $NONE"
[ ! -s "$NONE" ] || die "$NONE is not empty"
for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do
  b=$(md5sum < "$W/$f" | cut -c1-8)
  cp -p "$W/$f" "$W/$f.before-nolearned" || die "cannot keep $f"
  awk -v old="$OLD" -v n1="$NEW1" -v n2="$NEW2" '$0 == old {print n1; print n2; next} {print}' "$W/$f.before-nolearned" > "$W/$f.new-$$" || die "awk $f"
  bash -n "$W/$f.new-$$" || { rm -f "$W/$f.new-$$"; die "$f does not parse after the change"; }
  [ "$(diff "$W/$f.before-nolearned" "$W/$f.new-$$" | grep -c '^[<>]')" = 3 ] || { rm -f "$W/$f.new-$$"; die "$f changed by more than the one line"; }
  chmod --reference="$W/$f.before-nolearned" "$W/$f.new-$$" && mv -fT "$W/$f.new-$$" "$W/$f" || die "cannot put $f in place"
  echo "$f: $b -> $(md5sum < "$W/$f" | cut -c1-8) (full: $(md5sum < "$W/$f" | cut -d' ' -f1)); old kept as $f.before-nolearned"
done
mkdir -p "$T" || die "mkdir $T"
if [ -e "$W/direct-learned-pkg.txt" ]; then
  mv -n "$W/direct-learned-pkg.txt" "$T/direct-learned-pkg.txt" && echo "the learned file ($(wc -l < "$T/direct-learned-pkg.txt") lines, $(md5sum < "$T/direct-learned-pkg.txt" | cut -c1-8)) moved to $T/"
fi
echo "still naming the old file: $(grep -l 'direct-learned-pkg.txt' "$W"/*.sh 2> /dev/null | xargs -r -n1 basename | tr '\n' ' ')"
