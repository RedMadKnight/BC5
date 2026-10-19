#!/usr/bin/env bash
# BC5: one scripted gameplay run (start, slot 1, Continue; the save loads at +121 s), killed at
# +230 s, with the given extra environment. usage: route.sh <run number> ["VAR=value ..."]
# LAUNCHER=play-pkg-quiet.sh runs with the logging switch off and no journal (exp 0172).
# A third argument lists the screenshot times (default "130 150 170").
# Writes runN.sh, driveN.sh, inputN.cmd; waits for the run; prints stallcmp.sh for it.
set -u
N=$1; EXTRA=${2:-}; SHOTS_AT=${3:-130 150 170}
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo "busy: an emulator is running"; exit 1; }
cp ${INPUT:-input794.cmd} input$N.cmd  # INPUT=<file> another pad script (exp 0175)
{ echo "#!/usr/bin/env bash"; echo "# BC5 run $N (route.sh): gameplay route; extra: $EXTRA";
  echo "export KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_VIDEOOUT_TRACE=1 KYTY_BC5_SAVE_TRACE=1 KYTY_BC5_INPUT_CMD=\$HOME/bc5-work/input$N.cmd $EXTRA";
  echo "exec ~/bc5-work/${LAUNCHER:-play-pkg-log.sh}"; } > run$N.sh
sed -e "s/794/$N/g" -e "s/at 200;/at 230;/" -e "s/^for t in 130 150 170;/for t in $SHOTS_AT;/" drive794.sh > drive$N.sh
chmod +x run$N.sh drive$N.sh; rm -f input$N.cmd.done drive$N.log; rm -rf shots$N
setsid nohup ./drive$N.sh < /dev/null > /dev/null 2>&1 &
while [ "$(date +%M)" = "$(stat -c %y play-pkg-last.log | cut -c15-16)" ]; do sleep 5; done
setsid nohup distrobox enter ubuntu -- ~/bc5-work/run$N.sh < /dev/null > ~/bc5-work/run$N.out 2>&1 &
sleep 15; pgrep -x kyty_emulator >/dev/null && echo "RUN $N STARTED $(date +%T)" || { echo "did not start"; tail -3 run$N.out; exit 1; }
until grep -q DONE drive$N.log 2>/dev/null; do sleep 5; done
if [ "${LAUNCHER:-}" = play-pkg-quiet.sh ]; then ./fpscmp.sh $N; else ./stallcmp.sh $N; fi
