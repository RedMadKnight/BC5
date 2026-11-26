#!/usr/bin/env bash
# BC5 exp 0401t: exp 0372's software replug check (as exp 0391 ran it) on a private build, for an audio switch: one scripted
# route of run0401t.sh (MODE=route, RT on, JobArenaFix on, its lock, wd, save snapshot, freeze watcher and sampler) with
# exp 0391's traces (KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1) and the owner word
# BC5_0401T_OWNER=<tag>, while replug0401t.sh pulls the DualSense's PipeWire card profile (pulls: 5 s, under 1 s, 30 s; late:
# off before the start, on at ~170 s, one 5-s pull). Then exp 0391's check0391.py, unchanged, classifies from this run's files:
#   <tag>-verdict.txt   "pass" when run0401t.sh's summary is a clean end (ended at G+play; crash, kernel, freeze-dump and
#                       devcoredump counts 0), else the summary
#   <tag>-audio-lines.txt  exp 0391's grep of the play log (trace lines only; the play log stays on the box)
#   <tag>-replug.txt    replug0401t.sh's own file; <tag>-end.txt and <tag>-summary.txt are run0401t.sh's
# The physical replug and a DualShock 4 stay the maintainer's.
# usage (on the box): aud0401t.sh <live saves sum, LC_ALL=C> <tag> <pulls|late> <binary> <md5> [KEY=VALUE ...]
set -u
SUM=${1:?the live saves sum}; TAG=${2:?a tag}; RMODE=${3:?pulls or late}; BIN=${4:?a binary}; MD5=${5:?its md5}; shift 5
W=$HOME/bc5-work; E=$W/exp0401t; R=$E/raw; A=$E/aud
case "$TAG" in *[!A-Za-z0-9]* | "") echo "a tag is letters and digits"; exit 1 ;; esac
case "$RMODE" in pulls | late) ;; *) echo "the replug mode is pulls or late"; exit 1 ;; esac
[ -x "$E/run0401t.sh" ] || [ -f "$E/run0401t.sh" ] || { echo "no $E/run0401t.sh"; exit 1; }
for f in replug0401t.sh streams0391.py check0391.py; do [ -f "$A/$f" ] || { echo "no $A/$f"; exit 1; }; done
mkdir -p "$R"
[ ! -e "$R/$TAG-replug.txt" ] && [ ! -e "$R/$TAG-start.txt" ] && [ ! -e "$R/$TAG-result.txt" ] || { echo "tag $TAG was used"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: not started"; exit 1; }
# the replug script first: it waits up to 3 min for this tag's lock line and emulator, then for the pad port's open
setsid timeout -k 30 1000 bash "$A/replug0401t.sh" "$TAG" "$RMODE" < /dev/null > "$R/$TAG-replug.out" 2>&1 &
RP=$!
MODE=route bash "$E/run0401t.sh" "$SUM" "$TAG" 900 420 "$BIN" "$MD5" "BC5_0401T_OWNER=$TAG" \
    KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1 "$@"
RC=$?
wait "$RP"; echo "replug rc $?" >> "$R/$TAG-replug.out"
grep -a -E "AudioOut \(exp 0372\)|pad route:|audio trace:|input trace: rumble|rumble: pad instance|AudioOut:" "$R/$TAG-play.log" > "$R/$TAG-audio-lines.txt" 2> /dev/null
S=$(cat "$R/$TAG-summary.txt" 2> /dev/null)
case "$S" in
    "$TAG (route): ended at G+420 after "*"crash lines 0, kernel lines 0, freeze dumps 0, devcoredumps 0") echo pass ;;
    *) echo "not clean: ${S:-no summary}" ;;
esac > "$R/$TAG-verdict.txt"
python3 -I "$A/check0391.py" run "$TAG" "$RMODE" "$RC" "$R" > "$R/$TAG-check.txt" 2>&1
C=$?
L=$(tail -1 "$R/$TAG-check.txt")
case "$L" in "CLASS "*) ;; *) L="CLASS INVALID mode $RMODE pulls 0" ;; esac
echo "RESULT $TAG runner $RC check $C $L" | tee "$R/$TAG-result.txt"
