#!/usr/bin/env bash
# BC5 experiment 0267: the second title on the private binary ~/bc5-work/exp0267/kyty_emulator with the
# pad, audio and measurement traces on, for the maintainer's DualShock 4 session (an unplug and a replug
# during play). Everything else is play-pkg.sh as it is (the live saves, the maintainer's settings);
# BC5_EMU is how the launchers take another binary (exp 0194's play-water.sh, exp 0252's bench).
# Log: the launcher's ~/bc5-work/play-pkg-last.log, copied to ~/bc5-work/exp0267/play-ds4-<HHMM>.log at exit.
# What to read afterwards: "rumble:" lines (a failed write, once per pad instance), "input trace: rumble
# L/S for D ms via <path>" (D 100 = the vibration-port fallback, 5000 = classic scePadSetVibration),
# "audio trace: ... port N type 4 ..." with "held" staying near 0 ms, the fps counter around the replug.
set -u
E=~/bc5-work/exp0267
EMU=$E/kyty_emulator
[ -x "$EMU" ] || { echo "no private binary at $EMU (run build0267.sh first)"; exit 1; }
grep -q 'BC5_EMU' ~/bc5-work/play-pkg.sh || { echo "play-pkg.sh does not read BC5_EMU; check how it picks its binary"; exit 1; }
pgrep "^kyty_emulator" >/dev/null && { echo "an emulator is already running"; exit 1; }
echo "exp 0267 | DS4 session on the private binary $(md5sum "$EMU" | cut -c1-8) (play-ds4.sh, the maintainer) | start $(date +%H:%M)" > ~/bc5-work/BOX-LOCK
T=$(date +%H%M)
/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$EMU" KYTY_BC5_INPUT_TRACE=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 \
  "$HOME/bc5-work/play-pkg.sh" "$@"
RC=$?
rm -f ~/bc5-work/BOX-LOCK
cp ~/bc5-work/play-pkg-last.log "$E/play-ds4-$T.log" 2>/dev/null
echo "exit $RC; log copied to $E/play-ds4-$T.log; rumble lines: $(grep -c 'rumble' "$E/play-ds4-$T.log" 2>/dev/null)"
exit $RC
