#!/usr/bin/env bash
# BC5 experiment 0369, run K2: exp 0365's bench0365.sh, its paths changed to exp0369 (play-pkg-0369.sh: exp 0353's checked launcher, 0353 -> 0369).
# BC5 experiment 0369: exp 0362's bench0362.sh, its paths changed to exp0369 (play-pkg-0369.sh: exp 0353's checked launcher, 0353 -> 0369).
# BC5 experiment 0312 (exp 0311's bench0311.sh, 20 frozen-view shots 5 s apart; buf0312.py reads beside it): one run of the maintainer's lake save (a private
# copy of ~/bc5-work/saves-lake-1153 in exp 0299's private working directory) through play-pkg-0369.sh (today's
# play-pkg.sh, bb51caf2 at the run, with exp 0299's three edits, its log in exp0369: the RT reflection traversal runs unless
# BC5_DIRECT_SKIP_PGM says otherwise), with the input
# configuration input-0369.cfg (exp 0194's keyboard-off file plus RayTracing.PPSA03671=off, as the maintainer's own
# input.cfg). The lake bench's route (exp 0194 README; exp 0293's bench0293.sh): the first cross at 90 s (today's
# start-up load took 47-73 s, exp 0299), the slot list down, down (slot 3), cross; down, cross; the Parry prompt
# after LOADWAIT s; Photo Mode (options, down x4, cross, triangle) and exp 0194's camera move; then SERIES shots STEP s
# apart in the frozen view, and patch0197.py's patch share over them. The emulator's output: E/play-last.log.
# usage: ENVX="<switches>" [SERIES=20 STEP=5 LOADWAIT=60] bench0369.sh <tag> [secs]   (started by ab0312.sh)
TAG=$1; SECS=${2:-330}
B=$HOME/bc5-work/exp0299
E=$HOME/bc5-work/exp0369
cd ~/bc5-work || exit 1
pgrep "^kyty_emulator" > /dev/null && { echo busy; exit 1; }
SERIES=${SERIES:-20}; STEP=${STEP:-5}
W=$B/wd/_SaveData/PPSA03671
diff -rq ~/bc5-work/saves-lake-1153 "$W" > /dev/null 2>&1 || { rm -rf "$W" && cp -a ~/bc5-work/saves-lake-1153 "$W"; echo "private save copy reset to saves-lake-1153"; }
sync
R=$E/r-$TAG; mkdir -p "$R/shots"
echo "${ENVX:-defaults}" > "$R/env.txt"
printf 'wait 90000\npress cross\n' > "$R/input.cmd"
UP0=$(cut -d" " -f1 /proc/uptime)
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$R/input.cmd BC5_0299_INPUT_CONFIG=$E/input-0369.cfg ${ENVX:-} "$E/play-pkg-0369.sh" < /dev/null > "$R/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null && break; sleep 1; done
EPID=$(pgrep -n -x kyty_emulator)
T0=$(date +%s)
snap() { XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$R/shots/$(date +%H%M%S)-$1.png" > /dev/null 2>&1; }
gone() { kill -0 "$EPID" 2>/dev/null && [ $(( $(date +%s) - T0 )) -lt "$SECS" ] && return 1; echo "== $TAG: the emulator ended or the time ran out at $(date +%T)"; return 0; }
step() { # append lines, wait until all are done
  gone && return 1
  local n; n=$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)
  printf "$1" >> "$R/input.cmd"
  local add; add=$(printf "$1" | grep -c "")
  for _ in $(seq 1 120); do [ "$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)" -ge $((n + add)) ] && return 0; gone && return 1; sleep 0.5; done
  echo "step timed out: $1"; return 1
}
run() {
  for _ in $(seq 1 120); do [ "$(cat "$R/input.cmd.done" 2>/dev/null || echo 0)" -ge 2 ] && break; gone && return 1; sleep 2; done
  for _ in $(seq 1 ${SLOTWAIT:-5}); do gone && return 1; sleep 1; done
  step "press down\nwait 700\npress down\nwait 900\n" || return 1
  snap slot
  step "press cross\nwait 3500\n" || return 1
  step "press down\nwait 800\npress cross\nwait 1500\n" || return 1
  for _ in $(seq 1 ${LOADWAIT:-60}); do gone && return 1; sleep 1; done
  snap game
  step "press options\nwait 1300\npress down\nwait 400\npress down\nwait 400\npress down\nwait 400\npress down\nwait 600\npress cross\nwait 3000\npress triangle\nwait 1500\n" || return 1
  step "stick r 0 128 1600\nwait 300\ntrigger r2 255 1500\nwait 300\nstick r 128 255 350\nwait 900\n" || return 1
  for k in $(seq -w 0 $((SERIES - 1))); do gone && return 1; snap "ts$k"; sleep $((STEP - 1)); done
}
run
echo "== $TAG (${ENVX:-defaults}) shots done $(date +%T)"
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)
cp "$E/play-last.log" "$R/emu.log" 2>/dev/null
kill "$EPID" 2>/dev/null; sleep 4; kill -9 "$EPID" 2>/dev/null; sleep 3
sudo -n dmesg | awk -v up0="$UP0" "{ts = substr(\$0, 2, index(\$0, \"]\") - 2) + 0; if (ts >= up0) print}" > "$R/dmesg.txt"
echo "$J" > "$R/journal-dir.txt"
echo "kernel: $(grep -c "page fault" "$R/dmesg.txt") fault lines, $(grep -c -i "ring .*timeout\|GPU reset" "$R/dmesg.txt") ring timeout/reset lines"
echo "journal: $(grep -a -c TIMEOUT "$J/direct.log") fence timeouts; $(grep -ac "ray tracing off:" "$J/direct.log") ray-tracing-off lines; compute-ring lines (two rings: >= 1; one ring: 0): $(grep -ac "^compute ring [0-9]" "$J/direct.log"); skip lines: $(grep -a "skip pgm" "$J/direct.log" | sed 's/:.*//' | sort | uniq -c | tr '\n' ' ')"
distrobox enter ubuntu -- python3 ~/bc5-work/exp0197/patch0197.py "$R"/shots/*-ts*.png 2>/dev/null | sed "s|$R/shots/||"
grep -a "fps counter" "$R/emu.log" | tail -1 | cut -c1-90
