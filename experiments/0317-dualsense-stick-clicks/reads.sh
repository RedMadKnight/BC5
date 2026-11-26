#!/usr/bin/env bash
# BC5 experiment (L3/R3 on the DualSense), R1: read-only. The maintainer's input configuration (which the F2 menu
# writes) and what the newest play logs and the pad recording say about the stick clicks. A few KB; nothing written.
# Stops at once if any emulator runs (the maintainer may be playing without a BOX-LOCK line).
set -u
W=$HOME/bc5-work
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: no reads"; exit 1; }
echo "== $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
echo "== input.cfg, modified $(stat -c '%y' "$W/input.cfg" | cut -c1-19)"
cat "$W/input.cfg"
echo "== its lines naming a stick click (Pad:leftstick / Pad:rightstick / L3= / R3=):"
grep -n -i 'leftstick\|rightstick\|^[[:space:]]*L3[[:space:]]*=\|^[[:space:]]*R3[[:space:]]*=' "$W/input.cfg" || echo "(none)"
echo "== bc5-run.env input lines:"
grep -n 'INPUT_CONFIG\|INPUT_RECORD\|SDL_JOYSTICK\|DUALSENSE' "$W/bc5-run.env"
for f in play-pkg-last.log play-pkg-lean-last.log play-last.log play-lean-last.log; do
  [ -f "$W/$f" ] || continue
  echo "== $f, modified $(stat -c '%y' "$W/$f" | cut -c1-19): $(head -1 "$W/$f" | cut -c1-90)"
  grep -m4 -a 'is disabled, its presses are dropped\|^Host input\|Controller opened as raw joystick' "$W/$f" | cut -c1-200
done
R=$W/route-record.txt
if [ -f "$R" ]; then
  echo "== route-record.txt, modified $(stat -c '%y' "$R" | cut -c1-19): hold l3 $(grep -c '^hold l3$' "$R"), hold r3 $(grep -c '^hold r3$' "$R"), hold cross $(grep -c '^hold cross$' "$R"), hold square $(grep -c '^hold square$' "$R")"
fi
