#!/usr/bin/env bash
# BC5 exp 0429, the shared swap (exp 0431's int0431.sh adapted): the removal of exp 0359's JobArenaFix workaround from
# both shared builds (mkswap0429.py), nothing else. On top of the shared patch 9e7c4514 (exp 0431). The maintainer's word
# ("JobArenaFix ma zniknac z menu, z przelacznikow i wszystkich miejsc", 2026-11-16) and the top session's GO of 2026-11-17.
#   1. checks: no emulator; the shared tree's diff is 9e7c4514; both binaries are 6044be08 / d239d4bf; units at their pins
#      (pins-swap0429.txt); kit here
#   2. the lock (chain_claim); copies under ~/bc5-work/exp0429/swap (*.before-0429), read back; pins file
#   3. mkswap0429.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the pad_audio_route
#      header, the file list = the old one less gamePatch.cpp, gamePatch.h and job_arena_fix.hpp; BC5_GUARD_MAP_RULE /
#      BC5_GUARD_PRT_BG / learned line counts as before; JOB_ARENA 0 lines; JobArenaFix only on the silent-accept line)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds lose only KYTY_BC5_JOB_ARENA_FIX (if they held it) and gain nothing; neither holds
#      "job-arena fix", "Game fixes", ApplyJobArenaFix, bc5_title_switch_job_arena_fix or "JobArenaFix takes"
#   6. ~/bc5-work/input.cfg: its JobArenaFix lines removed (a copy kept; nothing else changes)
# Any failure after step 2 runs undo0429.sh (units, binaries and input.cfg back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0429): bash int0429.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0429/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
CFG=$W/input.cfg
PIN_OLD=9e7c4514; NORMAL_OLD=6044be08; LEAN_OLD=d239d4bf; PIN_NEW=fcedb6cd
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0429 STOP: $*"; exit 1; }
undo() { echo "int0429: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0429.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkswap0429.py pins-swap0429.txt undo0429.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
while read -r h u; do [ "$(m8 "$K/$u")" = "$h" ] || stop "$u is $(m8 "$K/$u"), not its pin $h"; done < "$HERE/pins-swap0429.txt"
[ "$(grep -c 'JobArenaFix' "$CFG")" = "$(grep -c '^JobArenaFix\.[A-Z0-9]*=\(on\|off\)$' "$CFG")" ] || stop "input.cfg has a JobArenaFix line of another shape"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0429: shared swap, the JobArenaFix removal, patch $PIN_OLD + 0429; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/pins.before-0429" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0429" && cp -p "$LB" "$X/kyty_emulator.lean.before-0429" && cp -p "$CFG" "$X/input.cfg.before-0429" || stop "cannot copy"
while read -r h u; do cp -p "$K/$u" "$X/units/$(basename "$u").before-0429" || stop "cannot copy $u"; done < "$HERE/pins-swap0429.txt"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0429.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; echo "CFG_MD5=$(m8 "$CFG")"
  while read -r h u; do echo "UNIT $h $u"; done < "$HERE/pins-swap0429.txt"; } > "$X/pins.before-0429"
[ "$(m8 "$X/kyty_emulator.normal.before-0429")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0429")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/input.cfg.before-0429")" = "$(m8 "$CFG")" ] && [ "$(m8 "$X/0001.before-0429.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
while read -r h u; do [ "$(m8 "$X/units/$(basename "$u").before-0429")" = "$h" ] || stop "the copy of $u does not read back"; done < "$HERE/pins-swap0429.txt"
echo "before: $(grep -v '^UNIT' "$X/pins.before-0429" | tr '\n' ' ')"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0429" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkswap0429.py" "$K" || undo "mkswap0429.py refused"
git -C "$K" diff --no-color f266548 > "$X/0001-new0429.patch" || undo "cannot write the new patch"
P=$X/0001-new0429.patch; O=$X/0001.before-0429.patch
[ "$(m8 "$P")" = "$PIN_NEW" ] || undo "the new patch is $(m8 "$P"), not $PIN_NEW (the laptop's rebase)"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | grep -v ' a/src/loader/gamePatch\.\(cpp\|h\) \| a/src/bc5/job_arena_fix\.hpp ' | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list is not the old one less the three files"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
[ "$(grep -c 'JOB_ARENA\|job_arena\|job-arena\|Game fixes\|ApplyJobArenaFix' "$P")" = 0 ] || undo "the patch still names the workaround"
[ "$(grep -c 'JobArenaFix' "$P")" = 1 ] && grep -q '^+.*EqualNoCase(left.substr(0, 12), "JobArenaFix.")) {$' "$P" || undo "JobArenaFix outside the silent-accept line"
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5, pad_audio_route header in"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0429" | cut -d= -f2)" ] || undo "the backend archive changed"
[ "$(m8 "$NB")" != "$NORMAL_OLD" ] && [ "$(m8 "$LB")" != "$LEAN_OLD" ] || undo "a binary did not change"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    plus=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' '); minus=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')
    echo "$v words: +[$plus] -[$minus]"
    [ -z "$plus" ] || undo "$v gained words: $plus"
    [ -z "$minus" ] || [ "$minus" = "KYTY_BC5_JOB_ARENA_FIX " ] || undo "$v lost words beyond KYTY_BC5_JOB_ARENA_FIX: $minus"
    s=$(nice -n 19 strings "$b" | grep -c 'job-arena fix\|Game fixes\|ApplyJobArenaFix\|bc5_title_switch_job_arena_fix\|JobArenaFix takes\|KYTY_BC5_JOB_ARENA_FIX')
    [ "$s" = 0 ] || undo "$v still holds $s workaround strings"
    echo "$v: 'JobArenaFix.' literal (the silent accept of an old input.cfg line): $(nice -n 19 strings "$b" | grep -c 'JobArenaFix')"
done
# 6
grep -v '^JobArenaFix\.[A-Z0-9]*=\(on\|off\)$' "$X/input.cfg.before-0429" > "$CFG.new0429" || true
[ "$(( $(wc -l < "$X/input.cfg.before-0429") - $(wc -l < "$CFG.new0429") ))" = "$(grep -c '^JobArenaFix\.' "$X/input.cfg.before-0429")" ] || undo "input.cfg: unexpected line count"
echo "CFG_NEW=$(m8 "$CFG.new0429")" >> "$X/pins.before-0429"
mv "$CFG.new0429" "$CFG" || undo "input.cfg: cannot write"
echo "input.cfg: $(grep '^CFG_MD5=' "$X/pins.before-0429" | cut -d= -f2) -> $(m8 "$CFG"), JobArenaFix lines left $(grep -c JobArenaFix "$CFG")"
echo "int0429 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0429.sh (then exp0431/undo0431.sh further back)"
