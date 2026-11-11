#!/usr/bin/env bash
# BC5 exp 0412 (tag ev412; the maintainer's "Tak, buduj", 2026-11-11): on the box, a private build of the shared source
# with the bound on an event's pending queue. mkev0412.py edits copies of src/kernel/eventQueue.cpp and
# src/graphics/host_gpu/renderer/sync.cpp (the tree ~/src/KytyPlus is only read); exp 0401 e8's build0401.py compiles
# them and the tree's unchanged src/libs/bc5LleAgc.cpp with the shared build's own commands (e8's compdb.json) into
# private objects and links them with the shared build's other objects into ~/bc5-work/exp0412/ev/bin/kyty_emulator.
# The shared build, its objects and archive, and exp0401e8 are only read. Then the private launcher copy
# ev/play-astro-ev0412.sh (exp 0412's play-astro-0412.sh with EMU and LOG changed) and ev/built.md5.
# CPU test first (evcap0412.cpp). BOX-LOCK by an atomic hard-link claim, our exact line removed at the end. No emulator
# is started. The kit (mkev0412.py, event_cap0412.hpp, evcap0412.cpp, kit.sha256) is in $V/kit.
# usage (on the box, no emulator running): bash mkev0412.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; V=$X/ev; K=$V/kit; E8=$W/exp0401e8; SB=$W/kytyplus-build; T=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$SB/src/kyty_emulator")" = 4d2b1b1dd52eaea6e3195500f604e73e ] || die "the shared build is not 4d2b1b1d"
[ "$(m "$T/src/libs/bc5LleAgc.cpp")" = d18b448299a335aadac75bbd202155fd ] || die "the tree's main unit is not d18b4482 (the one read on 2026-11-11)"
[ -s "$E8/compdb.json" ] && [ -s "$E8/build0401.py" ] || die "no exp0401e8/compdb.json or build0401.py"
[ -z "$(find "$T/src" -type f -newer "$SB/src/kyty_emulator" -print -quit)" ] || die "a file of the tree is newer than the shared build"
[ "$(m "$X/play-astro-0412.sh")" = 5669f0f617bced6b2b0fd5f3cec5fb3f ] || die "exp 0412's astro launcher is not 5669f0f6"
LINE="guard exp 0412 | build ev412 (the shared source + the events cap), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build ev412 | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build ev412 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
R=$V/raw; B=$V/b
mkdir -p "$R" "$B/obj" "$B/bin" "$V/bin" || die "mkdir"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/evcap0412.cpp" -o "$R/evcap0412" < /dev/null > "$R/evcap0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$R/evcap0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/evcap0412" < /dev/null > "$R/evcap0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$R/evcap0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^evcap0412: \([0-9]*\) of \1; end$' "$R/evcap0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$R/evcap0412.out")"
rm -rf "$B/out" && python3 -I "$K/mkev0412.py" "$T" "$B/out" > "$R/mkev0412.out" 2> "$R/mkev0412.err" || die "mkev0412.py: $(tail -1 "$R/mkev0412.err")"
cat "$R/mkev0412.out"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$E8/build0401.py" "$E8/compdb.json" "$T/src/libs/bc5LleAgc.cpp" "$B/obj" "$SB" "$B/bin/kyty_emulator" "$K" \
    "src/kernel/eventQueue.cpp=$B/out/src/kernel/eventQueue.cpp" "src/graphics/host_gpu/renderer/sync.cpp=$B/out/src/graphics/host_gpu/renderer/sync.cpp" \
    < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED|Assertion' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:')"
for s in KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_EVENT_PENDING_LOG "tag ev412"; do grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"; done
[ "$(m "$SB/src/kyty_emulator")" = 4d2b1b1dd52eaea6e3195500f604e73e ] || die "THE SHARED BUILD CHANGED during the build"
# The launcher: exp 0412's astro copy with the private build and its own log.
sed -e "s|^EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\$|EMU=$V/bin/kyty_emulator  # exp 0412 (ev412): the private build|" \
    -e "s|^LOG=$X/astro-last.log  # exp 0412: own log\$|LOG=$X/astro-ev-last.log  # exp 0412 (ev412): own log|" "$X/play-astro-0412.sh" > "$B/play-astro-ev0412.sh" || die "launcher"
chmod +x "$B/play-astro-ev0412.sh" && bash -n "$B/play-astro-ev0412.sh" || die "the launcher does not parse"
[ "$(diff "$X/play-astro-0412.sh" "$B/play-astro-ev0412.sh" | grep -c '^[<>]')" = 4 ] && grep -q '^ulimit -c 0' "$B/play-astro-ev0412.sh" &&
    [ "$(grep -c "^EMU=$V/bin/kyty_emulator  # exp 0412 (ev412)" "$B/play-astro-ev0412.sh")" = 1 ] && [ "$(grep -c "^LOG=$X/astro-ev-last.log" "$B/play-astro-ev0412.sh")" = 1 ] ||
    die "the launcher is not the astro copy with EMU and LOG changed"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$V/bin/kyty_emulator.new-$$" && mv -fT "$V/bin/kyty_emulator.new-$$" "$V/bin/kyty_emulator" || die "cannot put the binary in place"
cp -p "$B/play-astro-ev0412.sh" "$V/play-astro-ev0412.sh.new-$$" && mv -fT "$V/play-astro-ev0412.sh.new-$$" "$V/play-astro-ev0412.sh" || die "cannot put the launcher in place"
printf '%s  bin/kyty_emulator\n%s  play-astro-ev0412.sh\n' "$(m "$V/bin/kyty_emulator")" "$(m "$V/play-astro-ev0412.sh")" > "$V/built.md5" || die "built.md5"
echo "binary $(m "$V/bin/kyty_emulator") (shared $(m "$SB/src/kyty_emulator" | cut -c1-8)), launcher $(m "$V/play-astro-ev0412.sh")"
echo "built: ev412"
