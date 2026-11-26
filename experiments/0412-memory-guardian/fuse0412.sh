#!/usr/bin/env bash
# BC5 exp 0412 (g412b): the launcher's memory fuse, after 2026-11-10 (two plays that ended in a dead box and one global
# OOM kill after the swap was full). While one emulator runs, the cgroup it runs in - the ubuntu container's
# ".../libpod-<id>.scope/container", whose memory.max the maintainer's user owns - gets memory.max and memory.swap.max.
# Past them the kernel reclaims inside that cgroup only and then kills its largest task, the emulator (exit 137; the
# launchers set ulimit -c 0, so no core dump). The desktop and sshd are outside and stay alive. Both files are set back
# to "max" when the emulator's process ends, and by "fuse0412.sh restore" (the wrappers call it before every start) when a
# run of this script died first: the marker file $STATE names the cgroup while a fuse is set.
# Nothing system-wide: no sysctl, no systemd unit, no file outside the one cgroup and ~/bc5-work/exp0412. The limits
# cover everything in the container while they stand (the emulator, bc5-mount, shells), so no build beside a play.
# usage (host): fuse0412.sh set <RAM MiB> <swap MiB> <log file> [pgrep arguments, default: -x kyty_emulator]
#               fuse0412.sh restore <log file>
set -u
export LC_ALL=C
E=$HOME/bc5-work/exp0412; STATE=$E/fuse.active
say() { printf '%s fuse: %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
undo() { # $1: the cgroup directory
  local ok=1
  echo max > "$1/memory.max" 2> /dev/null || ok=0
  echo max > "$1/memory.swap.max" 2> /dev/null || ok=0
  if [ "$ok" = 1 ] && [ "$(cat "$1/memory.max" 2> /dev/null)" = max ] && [ "$(cat "$1/memory.swap.max" 2> /dev/null)" = max ]; then
    rm -f "$STATE"; say "limits back to max on $1; $(grep -E '^(oom_kill|max) ' "$1/memory.events" 2> /dev/null | tr '\n' ' ')"
  else
    say "COULD NOT set the limits back on $1 (memory.max $(cat "$1/memory.max" 2> /dev/null))"
  fi
}
case "${1:-}" in
  restore)
    LOG=${2:?the log file}
    [ -s "$STATE" ] || exit 0
    cgd=$(head -1 "$STATE")
    if [ -d "$cgd" ]; then say "a marker was left: restoring"; undo "$cgd"; else rm -f "$STATE"; say "a marker was left for a cgroup that is gone: removed"; fi
    exit 0 ;;
  set) ;;
  *) echo "usage: fuse0412.sh set <RAM MiB> <swap MiB> <log file> [pgrep arguments] | restore <log file>"; exit 1 ;;
esac
RAM=${2:?RAM MiB}; SWP=${3:?swap MiB}; LOG=${4:?the log file}; shift 4
[ "$#" -gt 0 ] || set -- -x kyty_emulator
case "$RAM$SWP" in *[!0-9]*) say "the limits are not numbers: no fuse"; exit 1 ;; esac
[ "$RAM" -ge 256 ] && [ "$RAM" -le 65536 ] && [ "$SWP" -le 65536 ] || { say "the limits are out of range: no fuse"; exit 1; }
ep=""
for _ in $(seq 1 150); do ep=$(pgrep "$@" | head -1); [ -n "$ep" ] && break; sleep 2; done
[ -n "$ep" ] || { say "no process (pgrep $*) in 300 s: no fuse"; exit 0; }
cgd=/sys/fs/cgroup$(cut -d: -f3 "/proc/$ep/cgroup" 2> /dev/null | head -1)
case "$cgd" in
  /sys/fs/cgroup/user.slice/user-*.slice/user@*.service/user.slice/libpod-*.scope/container) ;;
  *) say "process $ep is in $cgd, not in a container's cgroup: no fuse"; exit 0 ;;
esac
[ -w "$cgd/memory.max" ] && [ -w "$cgd/memory.swap.max" ] || { say "$cgd/memory.max is not writable: no fuse"; exit 0; }
[ "$(cat "$cgd/memory.max")" = max ] && [ "$(cat "$cgd/memory.swap.max")" = max ] || { say "$cgd has a limit already ($(cat "$cgd/memory.max"), swap $(cat "$cgd/memory.swap.max")): left as it is, no fuse"; exit 0; }
[ ! -s "$STATE" ] || { say "a marker exists ($STATE): no second fuse"; exit 0; }
cur=$(($(cat "$cgd/memory.current") / 1048576))
[ "$cur" -lt "$RAM" ] || { say "the cgroup holds $cur MiB already, over $RAM: no fuse"; exit 0; }
printf '%s\n' "$cgd" > "$STATE" || { say "cannot write the marker: no fuse"; exit 0; }
trap 'undo "$cgd"' EXIT
trap 'exit 0' INT TERM HUP
if echo "$((RAM * 1048576))" > "$cgd/memory.max" && echo "$((SWP * 1048576))" > "$cgd/memory.swap.max"; then
  say "set on $cgd for process $ep: memory.max $RAM MiB, memory.swap.max $SWP MiB (the cgroup held $cur MiB)"
else
  say "could not set the limits on $cgd"
  exit 0
fi
while [ -d "/proc/$ep" ]; do sleep 2; done
say "process $ep ended; the cgroup's peak $(($(cat "$cgd/memory.peak" 2> /dev/null || echo 0) / 1048576)) MiB"
