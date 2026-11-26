#!/usr/bin/env bash
# BC5 exp 0420: a stand-in for util-linux flock(1) in its command form, for the lean-session tests on the laptop (Git
# Bash has no flock). Only what lean-session.sh uses: flock [-o] [-w seconds] [-E code] <lockfile> <command...>.
# Mutual exclusion by an atomic mkdir of <lockfile>.d, held while the command runs; -o is accepted (the stand-in never
# hands a descriptor to the command). The tests never kill a holder, so a stale lock is not handled.
w=60 e=1
while [ $# -gt 0 ]; do
  case "$1" in
    --version) echo "flock (stand-in)"; exit 0 ;;
    -o) shift ;;
    -w) w=$2; shift 2 ;;
    -E) e=$2; shift 2 ;;
    *) break ;;
  esac
done
f=$1; shift
n=$(( ${w%.*} * 20 ))
i=0
until mkdir "$f.d" 2> /dev/null; do
  i=$((i + 1)); [ "$i" -gt "$n" ] && exit "$e"
  sleep 0.05
done
trap 'rmdir "$f.d" 2> /dev/null' EXIT
"$@"
