#!/usr/bin/env bash
# BC5 experiment 0302: the maintainer's own play session on the exp 0302 binary (the descriptor snapshot at filter time,
# compared at a fence timeout; it only reads, adds no packet; exp 0290's refusal in) — the next F360 hang during play
# gives the A/B/C answer the 2 x 600 s chain did not get (no hang). Prepared 2026-10-25 at the supervisor's request, for
# the maintainer's decision; nothing here runs without him starting it.
#   - his live saves (~/bc5-work/_SaveData), with a snapshot into ~/bc5-work/exp0302/saves-before-play-<HHMM> before each
#     start (a copy; nothing is restored by this script — after a machine-down the live saves are his to compare);
#   - today's play-pkg.sh (its md5 must be in EXPECTED_MD5 below: the supervisor names the md5 after the MangoHud
#     integration), derived once per md5 into exp0302/play-pkg-0302-play.sh with two anchored edits taken from exp 0299's
#     launcher: the BC5_0302_INPUT_CONFIG re-export after the bc5-run.env export loop (that loop exports
#     KYTY_BC5_INPUT_CONFIG unconditionally), and its own log (exp0302/play-0302-play.log). NO private working directory,
#     NO KYTY_BC5_SAVEDATA_DIR change: he plays on his saves;
#   - ray tracing ON by default (the maintainer, 2026-10-25 ~12:55: "przygotuj prywatny launcher z binarką 0302 na moją sesję
#     gry z RT włączonym"): a private copy of his input configuration with RayTracing.PPSA03671=on is handed through
#     BC5_0302_INPUT_CONFIG (his file, where the menu saved =off this morning, is only read; the menu switch still works
#     during play and saves into the private copy, not his); RT=off as the first argument plays with his saved setting;
#   - BC5_EMU = the exp 0302 binary (checked against exp0302/binary.md5), BC5_DIRECT_TIMEOUT_PROBE=1; BC5_DIRECT_TABLE_PGM
#     default (the 0x11d03a family); the journal goes where the launcher puts it (~/bc5-data/captures/play-<time>/gc/).
# usage: play0302.sh [RT=off]   (on the box, from the KDE Wayland session as play-pkg.sh; or a desktop shortcut pointing here)
set -u
E=$HOME/bc5-work/exp0302; W=$HOME/bc5-work
EXPECTED_MD5="fde58cda ac7a9a57 628b2714"   # play-pkg.sh versions this derivation is allowed on: fde58cda (noplaygo pack), ac7a9a57 (12:49, the MangoHud integration, F367), 628b2714 (13:03, the lab fix of exp 0304); the anchors are checked again at run time
BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2>/dev/null)
LAUNCH_SRC=$W/play-pkg.sh; L99=$W/exp0299/play-pkg-0299.sh
RT=${1:-RT=on}
m() { md5sum < "$1" | cut -c1-8; }
[ -n "$WANT" ] && [ "$(m "$BIN")" = "$WANT" ] || { echo "the exp 0302 binary is not md5 $WANT: not started"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
SRC_MD5=$(m "$LAUNCH_SRC")
case " $EXPECTED_MD5 " in *" $SRC_MD5 "*) ;; *) echo "play-pkg.sh is md5 $SRC_MD5, not one this script was checked against ($EXPECTED_MD5): not started"; exit 1 ;; esac
# the derived launcher, once per play-pkg.sh version
LAUNCH=$E/play-pkg-0302-play-$SRC_MD5.sh; LOG=$E/play-0302-play.log
if [ ! -x "$LAUNCH" ]; then
  A=$(grep -n 'BC5_0299_INPUT_CONFIG' "$L99" 2> /dev/null | head -1 | cut -d: -f1)
  [ -n "$A" ] && [ "$A" -gt 1 ] || { echo "no BC5_0299_INPUT_CONFIG line in $L99 to take the anchor from: not started"; exit 1; }
  ANCHOR=$(sed -n "$((A - 1))p" "$L99")
  [ "$(grep -cxF -- "$ANCHOR" "$LAUNCH_SRC")" = 1 ] || { echo "the anchor line [$ANCHOR] is not unique in $LAUNCH_SRC: not started"; exit 1; }
  AL=$(grep -nxF -- "$ANCHOR" "$LAUNCH_SRC" | cut -d: -f1)
  EL=$(grep -nF 'export "$key=$val"' "$LAUNCH_SRC" | head -1 | cut -d: -f1)
  [ -n "$EL" ] && [ "$EL" -lt "$AL" ] || { echo "the export loop is not above the anchor: not started"; exit 1; }
  [ "$(grep -c '^LOG=' "$LAUNCH_SRC")" -ge 1 ] || { echo "no LOG= line in $LAUNCH_SRC: not started"; exit 1; }
  awk -v al="$AL" -v lg="$LOG" '{ if ($0 ~ /^LOG=/ && !done) { print "LOG=" lg "  # exp 0302: own log"; done = 1 } else print } NR == al { print "[ -n \"${BC5_0302_INPUT_CONFIG:-}\" ] && export KYTY_BC5_INPUT_CONFIG=$BC5_0302_INPUT_CONFIG  # exp 0302: a private input configuration when given" }' "$LAUNCH_SRC" > "$LAUNCH" && chmod +x "$LAUNCH" || { echo "could not write $LAUNCH"; exit 1; }
  diff -u "$LAUNCH_SRC" "$LAUNCH" > "$E/play-pkg-0302-play-$SRC_MD5.diff"
  [ "$(grep -c '^[-+][^-+]' "$E/play-pkg-0302-play-$SRC_MD5.diff")" = 3 ] || { echo "the derived launcher differs in more than the two edits: look at $E/play-pkg-0302-play-$SRC_MD5.diff, not started"; rm -f "$LAUNCH"; exit 1; }
  echo "derived $LAUNCH from play-pkg.sh $SRC_MD5 (two edits; diff beside it)"
fi
# ray tracing: his saved setting, or forced on through a private copy of his configuration
CFG=""
if [ "$RT" != "RT=off" ] && [ "$RT" != "off" ]; then
  CFG=$E/input-rt-play.cfg
  { grep -v -i "^RayTracing\.PPSA03671=" "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; } > "$CFG" || { echo "could not write $CFG"; exit 1; }
  echo "ray tracing forced on through $CFG (his $W/input.cfg is only read)"
fi
# the live saves: a snapshot before the start, nothing more
SNAP=$E/saves-before-play-$(date +%H%M%S)
cp -a "$W/_SaveData/PPSA03671" "$SNAP" && diff -rq "$W/_SaveData/PPSA03671" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
SUM=$(cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)
echo "$(date '+%F %T') play on exp 0302 binary $WANT, launcher $LAUNCH, RT ${CFG:+forced on}${CFG:-as saved}, live saves $SUM snapshot $SNAP" | tee -a "$E/play-sessions.txt"
exec env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 ${CFG:+BC5_0302_INPUT_CONFIG="$CFG"} "$LAUNCH" "${@:2}"
