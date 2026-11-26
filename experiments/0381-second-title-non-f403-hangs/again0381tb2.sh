# BC5 exp 0381: test build 2's second smoke, with no rebuild: the first cycle stopped at the path check, which is text in the launchers and in-tb2.
# Sent after lock0381tb2.inc, with TB2_TOKEN set (tb2run0381.sh again). It claims, puts that one change in the three files, proves the launchers by their pins and leaves the line for the smoke.
TB=$W/exp0381/tb2
PC=$W/exp0381/in-tb2/experiments/0381-second-title-non-f403-hangs/pathcheck0381tb2.inc
BIN_PIN=86318679; L_PIN=fb93a9b9; S_PIN=a28f78c1
pgrep '^kyty_emulator' > /dev/null && { echo "TB2 STOP: an emulator runs"; exit 3; }
tb2_hook before-claim
trap tb2_held_release EXIT
tb2_claim
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "TB2 STOP: an emulator runs"; exit 3; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$TB/bin/kyty_emulator")" = "$BIN_PIN" ] || { echo "TB2 STOP: the binary is not the build's"; exit 5; }
tb2_hook before-edit
tb2_own
for f in "$PC" "$TB/play-pkg-0381tb2.sh" "$TB/play-pkg-0381tb2s.sh"; do
    grep -q 'bc5-work/exp0381/wd:tree' "$f" || continue
    sed -i -e "/^# Every place the smoke writes, then/i # wd itself is a real directory that holds setup0381j.sh's links to the title's files, so only its save directories are trees." -e 's#bc5-work/exp0381/wd:tree#bc5-work/exp0381/wd:dir#' "$f" || { echo "TB2 STOP: $f not changed"; exit 5; }
done
[ "$(m "$TB/play-pkg-0381tb2.sh")" = "$L_PIN" ] && [ "$(m "$TB/play-pkg-0381tb2s.sh")" = "$S_PIN" ] || { echo "TB2 STOP: the launchers are $(m "$TB/play-pkg-0381tb2.sh") and $(m "$TB/play-pkg-0381tb2s.sh"), not the pins"; exit 5; }
tb2_own
tb2_queue "$TB2_LINE: second smoke, no rebuild | $(date '+%F %T')"
TB2_HELD=0
echo claimed
