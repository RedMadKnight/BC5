#!/usr/bin/env bash
# BC5 exp 0401 series e11 (2026-11-10, his "Tak" relayed by the top session, and his yes in the water session): on the box,
# build ~/bc5-work/exp0411/bin/kyty_emulator = exp 0409's binary with e11's main unit (e8's bd181169 + mkm110401.py), run the
# m110401 CPU gate (the four switches =1, =0, unset), and make play-pkg-0411.sh from exp 0409's launcher (ulimit -c 0 kept). Shared
# files are only read; exp0401e8 and exp0409 are only read. The kit (mkm110401.py, m110401.cpp, link0411.py, kit.sha256) is
# in $X/kit. BOX-LOCK by an atomic hard-link claim, our exact line removed at the end.
# usage (on the box): bash mk0411.sh <e11 unit md5>
set -u
export LC_ALL=C
WANT=${1:?the e11 unit md5}
W=$HOME/bc5-work; X=$W/exp0411; K=$X/kit; E8=$W/exp0401e8; X9=$W/exp0409; LOCK=$W/BOX-LOCK
SW=(BC5_DIRECT_RESET_REPLAY_ACB BC5_DIRECT_RESET_LABELS BC5_DIRECT_LEARN_GUEST_ONLY BC5_DIRECT_RESET_LABEL_JOURNAL)  # hang2242's switches 5 and 6 are not in e11
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$E8/src/bc5LleAgc.cpp")" = bd1811690b685369194602027b61a2d5 ] || die "e8's unit is not bd181169"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
[ "$(m "$X9/play-pkg-0409.sh")" = e4253b93b63fd26ffa41fb49c0705c4d ] || die "exp 0409's launcher is not e4253b93"
LINE="water exp 0411 | build e11 (exp 0409 + the reset/learn switches), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0411-$$.new; al=$LOCK.0411-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0411-rel"; mv -fT "$LOCK.0411-rel" "$LOCK"; fi
  printf '%s\n' "water exp 0411 | released: build e11 | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "water exp 0411 | claimed: build e11 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
mkdir -p "$X/src" "$X/in/src/libs" "$X/obj" "$X/bin" "$X/raw" || die "mkdir"
cp -p "$E8/src/"*.inc "$X/src/" && cp -p "$E8/src/bc5LleAgc.cpp" "$X/in/src/libs/bc5LleAgc.cpp" || die "cannot copy e8's unit"
rm -rf "$X/out" && python3 -I "$K/mkm110401.py" "$X/in" "$X/out" > "$X/raw/mkm110401.out" 2>&1 || die "mkm110401.py: $(tail -1 "$X/raw/mkm110401.out")"
[ "$(m "$X/out/src/libs/bc5LleAgc.cpp")" = "$WANT" ] || die "the e11 unit is $(m "$X/out/src/libs/bc5LleAgc.cpp"), not $WANT"
cp -p "$X/out/src/libs/bc5LleAgc.cpp" "$X/src/bc5LleAgc.cpp" || die "cp"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$K/link0411.py" "$E8" "$X9/obj" "$W/kytyplus-build" "$X/bin/kyty_emulator" "$X/src/bc5LleAgc.cpp" "$X/obj" \
    --gate "$K/m110401.cpp" "$X/raw/m110401" < /dev/null > "$X/raw/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$X/raw/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED' | cut -c1-160 | tr '\n' ' ')"
[ -x "$X/bin/kyty_emulator" ] && [ -x "$X/raw/m110401" ] || die "no binary or gate"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$X/raw/build.out" | grep -c 'warning:')"
for s in "${SW[@]}" BC5_DIRECT_JOURNAL_QUIET KYTY_BC5_AMM_SCATTER; do grep -aqF -- "$s" "$X/bin/kyty_emulator" || die "the binary lacks [$s]"; done
for g in on off unset; do
  v=(env -u KYTY_BC5_SAVEDATA_DIR); for s in "${SW[@]}"; do case $g in on) v+=("$s=1") ;; off) v+=("$s=0") ;; unset) v+=(-u "$s") ;; esac; done
  d=$X/run-gate-$g; rm -rf "$d" && mkdir -p "$d" || die "mkdir $d"
  (cd "$d" && distrobox enter ubuntu -- "${v[@]}" "$X/raw/m110401" "${g/unset/off}" < /dev/null) > "$X/raw/m110401-$g.out" 2>&1 || die "the gate ($g) failed: $(grep -m2 -E 'FAIL|error' "$X/raw/m110401-$g.out" | cut -c1-160 | tr '\n' ' ')"
  grep -q "^m110401: ${g/unset/off} \([0-9]*\) of \1\b.*; end\$" "$X/raw/m110401-$g.out" || die "no end marker from the gate ($g)"
  echo "gate $g: $(tail -1 "$X/raw/m110401-$g.out")"
done
sed -e "s|^EMU=.*|EMU=$X/bin/kyty_emulator  # exp 0411: the private build|" -e "s|^LOG=.*|LOG=$X/play-last.log  # exp 0411: own log|" "$X9/play-pkg-0409.sh" > "$X/play-pkg-0411.sh" || die "launcher"
chmod +x "$X/play-pkg-0411.sh" && bash -n "$X/play-pkg-0411.sh" || die "the launcher does not parse"
[ "$(diff "$X9/play-pkg-0409.sh" "$X/play-pkg-0411.sh" | grep -c '^[<>]')" = 4 ] && grep -q '^ulimit -c 0' "$X/play-pkg-0411.sh" || die "the launcher is not 0409's with EMU and LOG changed"
echo "binary $(m "$X/bin/kyty_emulator"), unit $WANT, launcher $(m "$X/play-pkg-0411.sh")"
echo "built: e11"
