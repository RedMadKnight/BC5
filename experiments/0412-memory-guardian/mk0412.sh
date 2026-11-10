#!/usr/bin/env bash
# BC5 exp 0412 (the memory guardian's first build; mk0411.sh's pattern): on the box, build ~/bc5-work/exp0412/bin/kyty_emulator
# = exp 0411's e11 binary with its main unit edited by mkguard0412.py (six BC5_GUARD_* switches, all default off), run the
# CPU test test0412.cpp, and make play-pkg-0412.sh from exp 0411's launcher (ulimit -c 0 kept). Shared files are only read;
# exp0401e8, exp0409 and exp0411 are only read. The kit (mkguard0412.py, guard0412.inc, test0412.cpp, env_flag.hpp,
# kit.sha256) is in $X/kit. BOX-LOCK by an atomic hard-link claim, our exact line removed at the end.
# Not run yet: it needs the top session's GO and the kit copied to the box.
# usage (on the box, no emulator running): bash mk0412.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit; E8=$W/exp0401e8; X9=$W/exp0409; X11=$W/exp0411; LOCK=$W/BOX-LOCK
SW=(BC5_GUARD_LEDGER BC5_GUARD_MLOCK BC5_GUARD_FILE BC5_GUARD_FILE_ROOT BC5_GUARD_PSI BC5_GUARD_PIN_CAP BC5_GUARD_APPLY_MIN_MS)
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
case "$(m "$X11/src/bc5LleAgc.cpp")" in f366ff7b*) ;; *) die "exp 0411's unit is not e11's f366ff7b" ;; esac
[ "$(m "$X11/bin/kyty_emulator")" = 70df5cb1f43cf276011037aaf7793a30 ] || die "exp 0411's binary is not e11's 70df5cb1"
[ "$(m "$X11/kit/link0411.py")" = 0634167b6bd8dedf0799cb1fe5de8606 ] || die "exp 0411's link0411.py is not 0634167b"
[ "$(m "$X11/play-pkg-0411.sh")" = 3e758fdfac5718c82ff6ac108a85ec13 ] || die "exp 0411's launcher is not 3e758fdf"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
LINE="guard exp 0412 | build g412 (e11 + the guardian's switches), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412 | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
mkdir -p "$X/src" "$X/in/src/libs" "$X/obj" "$X/bin" "$X/raw" || die "mkdir"
cp -p "$X11/src/"*.inc "$X/src/" && cp -p "$X11/src/bc5LleAgc.cpp" "$X/in/src/libs/bc5LleAgc.cpp" || die "cannot copy e11's unit"
rm -rf "$X/out" && python3 -I "$K/mkguard0412.py" "$X/in" "$X/out" > "$X/raw/mkguard0412.out" 2> "$X/raw/mkguard0412.err" || die "mkguard0412.py: $(tail -1 "$X/raw/mkguard0412.err")"
cp -p "$X/out/src/libs/bc5LleAgc.cpp" "$X/src/bc5LleAgc.cpp" || die "cp"
UNIT=$(m "$X/src/bc5LleAgc.cpp")
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/test0412.cpp" -o "$X/raw/test0412" < /dev/null > "$X/raw/test0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$X/raw/test0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$X/raw/test0412" < /dev/null > "$X/raw/test0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$X/raw/test0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0412: \([0-9]*\) of \1; end$' "$X/raw/test0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$X/raw/test0412.out")"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$X11/kit/link0411.py" "$E8" "$X9/obj" "$W/kytyplus-build" "$X/bin/kyty_emulator" "$X/src/bc5LleAgc.cpp" "$X/obj" \
    < /dev/null > "$X/raw/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$X/raw/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED' | cut -c1-160 | tr '\n' ' ')"
[ -x "$X/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$X/raw/build.out" | grep -c 'warning:')"
for s in "${SW[@]}" BC5_DIRECT_RESET_LABELS BC5_DIRECT_JOURNAL_QUIET KYTY_BC5_AMM_SCATTER; do grep -aqF -- "$s" "$X/bin/kyty_emulator" || die "the binary lacks [$s]"; done
sed -e "s|^EMU=.*|EMU=$X/bin/kyty_emulator  # exp 0412: the private build|" -e "s|^LOG=.*|LOG=$X/play-last.log  # exp 0412: own log|" "$X11/play-pkg-0411.sh" > "$X/play-pkg-0412.sh" || die "launcher"
chmod +x "$X/play-pkg-0412.sh" && bash -n "$X/play-pkg-0412.sh" || die "the launcher does not parse"
[ "$(diff "$X11/play-pkg-0411.sh" "$X/play-pkg-0412.sh" | grep -c '^[<>]')" = 4 ] && grep -q '^ulimit -c 0' "$X/play-pkg-0412.sh" || die "the launcher is not 0411's with EMU and LOG changed"
printf '%s  bin/kyty_emulator\n%s  play-pkg-0412.sh\n' "$(m "$X/bin/kyty_emulator")" "$(m "$X/play-pkg-0412.sh")" > "$X/built.md5" || die "built.md5"
echo "binary $(m "$X/bin/kyty_emulator"), unit $UNIT (from $(m "$X11/src/bc5LleAgc.cpp")), launcher $(m "$X/play-pkg-0412.sh")"
echo "built: g412"
