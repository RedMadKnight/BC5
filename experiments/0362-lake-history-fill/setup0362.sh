#!/usr/bin/env bash
# BC5 experiment 0362: exp 0357's setup0357.sh with 0357 -> 0362 (RT ON, MangoHud off; the launcher derivation unchanged).
# play-pkg-0362.sh is exp 0353's play-pkg-0353.sh (today's play-pkg.sh 55531ab6 with exp 0347's five edits, checked by
# setup0353.sh) with 0353 -> 0362; its diff against play-pkg.sh must be exp 0353's diff with 0353 -> 0362, line for
# line. input-0362.cfg is exp 0347's input-0347.cfg (exp 0194's keyboard-off file, MangoHud off) with RT ON. Writes only
# ~/bc5-work/exp0362.
# usage: setup0362.sh   (on the box; no emulator, nothing shared written)
set -u
W=$HOME/bc5-work; E=$W/exp0362; L=$W/play-pkg.sh; P=$W/exp0353/play-pkg-0353.sh
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$L")" = 55531ab6 ] || { echo "$L is $(m "$L"), not 55531ab6: stop"; exit 1; }
diff "$L" "$P" | grep '^[<>]' | sed 's/0353/0362/g' > "$E/want.lines"
sed 's/0353/0362/g' "$P" > "$E/play-pkg-0362.sh" && chmod +x "$E/play-pkg-0362.sh"
bash -n "$E/play-pkg-0362.sh" || { echo "play-pkg-0362.sh does not parse: stop"; exit 1; }
diff "$L" "$E/play-pkg-0362.sh" > "$E/play-pkg-0362.diff"
grep '^[<>]' "$E/play-pkg-0362.diff" > "$E/got.lines"
cmp -s "$E/want.lines" "$E/got.lines" || { echo "the launcher's edits differ from exp 0353's:"; diff "$E/want.lines" "$E/got.lines"; exit 1; }
[ "$(grep -c '^>' "$E/play-pkg-0362.diff")" = 5 ] || { echo "not five added lines: stop"; exit 1; }
{ grep -v "^RayTracing.PPSA03671=" "$W/exp0347/input-0347.cfg"; echo "RayTracing.PPSA03671=on"; } > "$E/input-0362.cfg"
grep -q '^RayTracing.PPSA03671=on$' "$E/input-0362.cfg" && grep -q '^MangoHud.PPSA03671=off$' "$E/input-0362.cfg" || { echo "input-0362.cfg is not RT on, MangoHud off: stop"; exit 1; }
chmod +x "$E/bench0362.sh" "$E/ab0362.sh"
for f in bench0362.sh ab0362.sh play-pkg-0362.sh; do bash -n "$E/$f" || { echo "$f does not parse"; exit 1; }; done
echo "set up: play-pkg-0362.sh $(m "$E/play-pkg-0362.sh") (5 lines added, 4 replaced, as exp 0353's), input-0362.cfg $(m "$E/input-0362.cfg")"
grep '^>' "$E/play-pkg-0362.diff" | cut -c1-150
