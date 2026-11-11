#!/usr/bin/env bash
# BC5 exp 0412, the third build (g412c: g412b + BC5_GUARD_SPLIT; this file is mk0412b.sh with the kit and work directories renamed): on the box, build exp 0411's e11 binary with its main unit
# edited by this kit's mkguard0412.py (the first build's six BC5_GUARD_* switches plus BC5_GUARD_CAP_ACT and
# BC5_GUARD_CAP_NAMES, all default off), run the CPU test test0412.cpp, and make play-pkg-0412.sh again from exp 0411's
# launcher (ulimit -c 0 kept; one more line: BC5_GUARD_AMM_BY_USE=1 takes AMM out of the eager heaps). The binary is
# built beside the first build's and moved over it at the end; the first build is kept as bin/kyty_emulator.g412-<md5>,
# its launcher as play-pkg-0412.sh.g412-<md5>. Shared files are only read; exp0401e8, exp0409 and exp0411 are only read.
# The kit (mkguard0412.py, guard0412.inc, test0412.cpp, env_flag.hpp, kit.sha256) is in $X/kit-b.
# BOX-LOCK by an atomic hard-link claim, our exact line removed at the end. No emulator is started.
# usage (on the box, no emulator running): bash mk0412b.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit-c; E8=$W/exp0401e8; X9=$W/exp0409; X11=$W/exp0411; LOCK=$W/BOX-LOCK
SW=(BC5_GUARD_LEDGER BC5_GUARD_MLOCK BC5_GUARD_FILE BC5_GUARD_FILE_ROOT BC5_GUARD_PSI BC5_GUARD_PIN_CAP BC5_GUARD_APPLY_MIN_MS BC5_GUARD_CAP_ACT BC5_GUARD_CAP_NAMES BC5_GUARD_SPLIT)
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
case "$(m "$X11/src/bc5LleAgc.cpp")" in f366ff7b*) ;; *) die "exp 0411's unit is not e11's f366ff7b" ;; esac
[ "$(m "$X11/bin/kyty_emulator")" = 70df5cb1f43cf276011037aaf7793a30 ] || die "exp 0411's binary is not e11's 70df5cb1"
[ "$(m "$X11/kit/link0411.py")" = 0634167b6bd8dedf0799cb1fe5de8606 ] || die "exp 0411's link0411.py is not 0634167b"
[ "$(m "$X11/play-pkg-0411.sh")" = 3e758fdfac5718c82ff6ac108a85ec13 ] || die "exp 0411's launcher is not 3e758fdf"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
LINE="guard exp 0412 | build g412c (e11 + the guardian's second build), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412c | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412c | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
B=$X/c; R=$X/raw-c
mkdir -p "$B/src" "$B/in/src/libs" "$B/obj" "$B/bin" "$R" || die "mkdir"
cp -p "$X11/src/"*.inc "$B/src/" && cp -p "$X11/src/bc5LleAgc.cpp" "$B/in/src/libs/bc5LleAgc.cpp" || die "cannot copy e11's unit"
rm -rf "$B/out" && python3 -I "$K/mkguard0412.py" "$B/in" "$B/out" > "$R/mkguard0412.out" 2> "$R/mkguard0412.err" || die "mkguard0412.py: $(tail -1 "$R/mkguard0412.err")"
cp -p "$B/out/src/libs/bc5LleAgc.cpp" "$B/src/bc5LleAgc.cpp" || die "cp"
UNIT=$(m "$B/src/bc5LleAgc.cpp")
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/test0412.cpp" -o "$R/test0412" < /dev/null > "$R/test0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$R/test0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/test0412" < /dev/null > "$R/test0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$R/test0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^test0412: \([0-9]*\) of \1; end$' "$R/test0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$R/test0412.out")"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$X11/kit/link0411.py" "$E8" "$X9/obj" "$W/kytyplus-build" "$B/bin/kyty_emulator" "$B/src/bc5LleAgc.cpp" "$B/obj" \
    < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:')"
for s in "${SW[@]}" BC5_DIRECT_RESET_LABELS BC5_DIRECT_JOURNAL_QUIET KYTY_BC5_AMM_SCATTER BC5_DIRECT_LAZY_RELEASE "tag g412b"; do grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"; done
AMM='[ "${BC5_GUARD_AMM_BY_USE:-0}" = 1 ] \&\& export BC5_DIRECT_EAGER_NAMES="${BC5_DIRECT_EAGER_NAMES/,AMM,/,}"  # exp 0412 (g412b): the AMM heap by use, not eager'
sed -e "s|^EMU=.*|EMU=$X/bin/kyty_emulator  # exp 0412: the private build|" -e "s|^LOG=.*|LOG=$X/play-last.log  # exp 0412: own log|" \
    -e "/^export BC5_DIRECT_EAGER_NAMES=/a $AMM" "$X11/play-pkg-0411.sh" > "$B/play-pkg-0412.sh" || die "launcher"
chmod +x "$B/play-pkg-0412.sh" && bash -n "$B/play-pkg-0412.sh" || die "the launcher does not parse"
[ "$(diff "$X11/play-pkg-0411.sh" "$B/play-pkg-0412.sh" | grep -c '^[<>]')" = 5 ] && grep -q '^ulimit -c 0' "$B/play-pkg-0412.sh" &&
    [ "$(grep -c '^\[ "${BC5_GUARD_AMM_BY_USE:-0}" = 1 \] && export BC5_DIRECT_EAGER_NAMES="${BC5_DIRECT_EAGER_NAMES/,AMM,/,}"  # exp 0412' "$B/play-pkg-0412.sh")" = 1 ] ||
    die "the launcher is not 0411's with EMU and LOG changed and the AMM line added"
# The AMM line, on the launcher's own list: with the word the list loses AMM and nothing else; without it nothing changes.
EL=$(grep '^export BC5_DIRECT_EAGER_NAMES=' "$B/play-pkg-0412.sh") AL=$(grep '^\[ "${BC5_GUARD_AMM_BY_USE' "$B/play-pkg-0412.sh")
PR='printf "%s" "$BC5_DIRECT_EAGER_NAMES"'
on=$(env -i BC5_GUARD_AMM_BY_USE=1 /usr/bin/bash -c "$EL"$'\n'"$AL"$'\n'"$PR") off=$(env -i /usr/bin/bash -c "$EL"$'\n'"$AL"$'\n'"$PR")
case ",$off," in *,AMM,*) ;; *) die "the launcher's eager list has no AMM" ;; esac
case ",$on," in *,AMM,*) die "the AMM line does not take AMM out" ;; esac
[ "$on" = "${off/,AMM,/,}" ] && [ "$(printf '%s' "$on" | tr ',' '\n' | grep -c .)" = "$(($(printf '%s' "$off" | tr ',' '\n' | grep -c .) - 1))" ] || die "the AMM line changes more than AMM"
echo "launcher: eager heaps $(printf '%s' "$off" | tr ',' '\n' | grep -c .), with BC5_GUARD_AMM_BY_USE=1 $(printf '%s' "$on" | tr ',' '\n' | grep -c .)"
# Put the build in place; the first build stays beside it.
old=$(m "$X/bin/kyty_emulator"); oldl=$(m "$X/play-pkg-0412.sh")
if [ -n "$old" ] && [ ! -e "$X/bin/kyty_emulator.g412-${old:0:8}" ]; then cp -p "$X/bin/kyty_emulator" "$X/bin/kyty_emulator.g412-${old:0:8}" || die "cannot keep the first build"; fi
if [ -n "$oldl" ] && [ ! -e "$X/play-pkg-0412.sh.g412-${oldl:0:8}" ]; then cp -p "$X/play-pkg-0412.sh" "$X/play-pkg-0412.sh.g412-${oldl:0:8}" || die "cannot keep the first launcher"; fi
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$X/bin/kyty_emulator.new-$$" && mv -fT "$X/bin/kyty_emulator.new-$$" "$X/bin/kyty_emulator" || die "cannot put the binary in place"
cp -p "$B/play-pkg-0412.sh" "$X/play-pkg-0412.sh.new-$$" && mv -fT "$X/play-pkg-0412.sh.new-$$" "$X/play-pkg-0412.sh" || die "cannot put the launcher in place"
printf '%s  bin/kyty_emulator\n%s  play-pkg-0412.sh\n' "$(m "$X/bin/kyty_emulator")" "$(m "$X/play-pkg-0412.sh")" > "$X/built.md5" || die "built.md5"
echo "binary $(m "$X/bin/kyty_emulator") (the first build $old kept), unit $UNIT (from $(m "$X11/src/bc5LleAgc.cpp")), launcher $(m "$X/play-pkg-0412.sh")"
echo "built: g412c"
