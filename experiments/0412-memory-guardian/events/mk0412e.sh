#!/usr/bin/env bash
# BC5 exp 0412, build g412e (2026-11-11, the maintainer's "Tak, przenies"): the guardian's build g412d (the e11-based line
# the second title is played on) with the events cap of README section 11. On the box.
# mkev0412.py edits copies of exp 0401 e8's eventQueue.cpp (exp0401e8/x5-eq, d8eaa6d2) and of the shared sync.cpp
# (68733b6c); linkev0412.py compiles them and g412d's main unit ($X/d/src/bc5LleAgc.cpp, 5361c8ba) with the shared
# build's commands and links them with e8's other private objects, exp 0409's two and the shared objects.
# The binary is built beside g412d's and moved over it at the end; g412d is kept as bin/kyty_emulator.g412-<md5>.
# The launcher play-pkg-0412.sh does not change. Shared files, exp0401e8, exp0409 and exp0411 are only read.
# CPU test first (evcap0412.cpp). BOX-LOCK by an atomic hard-link claim, our exact line removed at the end. No emulator
# is started. The kit (mkev0412.py, linkev0412.py, event_cap0412.hpp, evcap0412.cpp, kit.sha256) is in $X/kit-e.
# usage (on the box, no emulator running): bash mk0412e.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit-e; E8=$W/exp0401e8; X9=$W/exp0409; SB=$W/kytyplus-build; T=$HOME/src/KytyPlus; LOCK=$W/BOX-LOCK
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$X/bin/kyty_emulator")" = ca10649409282fb1078cb478295e369c ] || die "the build in place is not g412d ca106494"
[ "$(m "$X/d/src/bc5LleAgc.cpp")" = 5361c8baac7690e5167e89a27cc7b4c7 ] || die "g412d's unit is not 5361c8ba"
[ "$(m "$E8/x5-eq/src/kernel/eventQueue.cpp")" = d8eaa6d22e3e415ea8331dced30867c0 ] || die "e8's eventQueue.cpp is not d8eaa6d2"
[ "$(m "$T/src/graphics/host_gpu/renderer/sync.cpp")" = 68733b6c5be980f238571723296f7d05 ] || die "the shared sync.cpp is not 68733b6c"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
grep -qxF "$(m "$X/play-pkg-0412.sh")  play-pkg-0412.sh" "$X/built.md5" || die "the launcher is not the one in built.md5"
LINE="guard exp 0412 | build g412e (g412d + the events cap), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412e | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412e | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
B=$X/e; R=$X/raw-e
mkdir -p "$B/obj" "$B/bin" "$R" || die "mkdir"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/evcap0412.cpp" -o "$R/evcap0412" < /dev/null > "$R/evcap0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$R/evcap0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/evcap0412" < /dev/null > "$R/evcap0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$R/evcap0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^evcap0412: \([0-9]*\) of \1; end$' "$R/evcap0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$R/evcap0412.out")"
rm -rf "$B/out" && python3 -I "$K/mkev0412.py" --eq "$E8/x5-eq/src/kernel/eventQueue.cpp" "$T" "$B/out" > "$R/mkev0412.out" 2> "$R/mkev0412.err" || die "mkev0412.py: $(tail -1 "$R/mkev0412.err")"
cat "$R/mkev0412.out"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$K/linkev0412.py" "$E8" "$X9/obj" "$SB" "$B/bin/kyty_emulator" "$X/d/src/bc5LleAgc.cpp" "$B/obj" "$K" \
    "$B/out/src/kernel/eventQueue.cpp" "$B/out/src/graphics/host_gpu/renderer/sync.cpp" < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED|Assertion' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:'); $(grep -m1 '^private objects' "$R/build.out")"
for s in KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_EVENT_PENDING_LOG "tag ev412" BC5_GUARD_SPLIT BC5_GUARD_FORGET BC5_GUARD_CAP_ACT BC5_DIRECT_LAZY_RELEASE KYTY_BC5_EQUEUE_FIXES KYTY_BC5_AMM_SCATTER; do
  grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"
done
old=$(m "$X/bin/kyty_emulator")
if [ ! -e "$X/bin/kyty_emulator.g412-${old:0:8}" ]; then cp -p "$X/bin/kyty_emulator" "$X/bin/kyty_emulator.g412-${old:0:8}" || die "cannot keep g412d"; fi
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$X/bin/kyty_emulator.new-$$" && mv -fT "$X/bin/kyty_emulator.new-$$" "$X/bin/kyty_emulator" || die "cannot put the binary in place"
printf '%s  bin/kyty_emulator\n%s  play-pkg-0412.sh\n' "$(m "$X/bin/kyty_emulator")" "$(m "$X/play-pkg-0412.sh")" > "$X/built.md5" || die "built.md5"
echo "binary $(m "$X/bin/kyty_emulator") (g412d $old kept), launcher $(m "$X/play-pkg-0412.sh")"
echo "built: g412e"
