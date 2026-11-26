#!/usr/bin/env bash
# BC5 exp 0415, LAPTOP side: run0415i.sh runs one after another over ssh.
# Each argument: "<runner env words>|<tag> <variant> <play s> [WORD=VALUE ...]".
# Lesson R55: the series stops at the first run that is not clean (no "ended at G+", any kernel line, any crash line,
# a pad key), and before every run it looks for the stop file given as STOPF (a LOCAL file: `touch` it from another
# terminal to end the series after the run in flight; to end the run in flight itself, create ~/bc5-work/exp0415/STOP
# on the box, which the runner looks for every second). Nothing is copied from the box between runs.
# DRY=1 prints what would run and starts nothing: the stop file is tested with it before the first real series.
# usage: STOPF=<file> [DRY=1] bash series0415.sh "<spec>" ...
set -u
STOPF=${STOPF:?a local stop file path}
for spec in "$@"; do
  pre=${spec%%|*}; rest=${spec#*|}
  if [ -e "$STOPF" ]; then echo "SERIES STOPPED by the stop file before [$rest]"; exit 2; fi
  if [ "${DRY:-0}" = 1 ]; then echo "would run: $pre bash ~/bc5-work/exp0415/kit/run0415i.sh $rest"; continue; fi
  out=$(timeout 620 ssh -o ConnectTimeout=20 -o ServerAliveInterval=30 bc250 "$pre bash ~/bc5-work/exp0415/kit/run0415i.sh $rest" 2>&1 | tail -3)
  echo "$(date +%T) $out"
  case "$out" in
    *"NOT A MEASUREMENT"*) echo "SERIES STOPPED at [$rest]: a pad key"; exit 1 ;;
    *"ended at G+"*"kernel lines 0 (GPU 0, OOM 0)"*"crash lines 0"*) ;;
    *) echo "SERIES STOPPED at [$rest]"; exit 1 ;;
  esac
done
echo "SERIES DONE"
