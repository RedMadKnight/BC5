#!/usr/bin/env bash
# BC5 (2026-10-27): reboot the BC-250 when an amdgpu reset does not finish. Installed as /usr/local/sbin/bc5-gpu-watch.sh
# by install.sh beside this file, run as root by bc5-gpu-watch.service.
#
# Why: at 13:29 that day a GPU hang's reset never finished and the box stood still for 26 minutes until the maintainer
# reset it by hand. The kernel did not lock up (no soft/hard-lockup panic), PID 1 kept feeding the hardware watchdog
# (tools/scripts/watchdog-setup), and this kernel has no hung-task detector (CONFIG_DETECT_HUNG_TASK is not set), so
# nothing turned the stall into a reboot. This watcher reads the kernel log itself (dmesg --follow-new, straight from
# /dev/kmsg: the journal stopped writing in that hang) and arms on a ring timeout or a GPU reset begin. A ring reset
# that succeeds, or a full reset that ends with "GPU reset(N) succeeded", disarms it. If neither comes within
# BC5_GPU_WATCH_GRACE seconds (60), it syncs the disks and crashes the kernel through SysRq (s, then c). With
# kernel.panic_on_oops=1 and kernel.panic=10 (watchdog-setup) the box reboots 10 s later, and with efi-pstore on
# (tools/scripts/pstore-setup) the panic writes the kernel log's tail, so the stall is on record.
# A recovered hang (exp 0342 R2: "Ring gfx_0.0.0 reset succeeded") never reaches the deadline.
# A ring reset that FAILS is acted on at once, with a 1-s sync instead of 5. On this APU the full reset that follows
# (MODE1, about 4 s later) took the box down at 12:52 and 14:25 that day. At 14:25 nothing brought it back: the
# watcher armed but the box was gone before its deadline, and the hardware watchdog did not reset it. The panic has
# to come before MODE1 starts. Every ring reset in the box's journals either succeeded (880) or was followed by a
# dead box (2).
# usage: bc5-gpu-watch.sh            (the service)
#        bc5-gpu-watch.sh --test     (reads kernel lines from stdin, prints what it would do, acts on nothing)
set -u
GRACE=${BC5_GPU_WATCH_GRACE:-60}
TEST=0; [ "${1:-}" = --test ] && TEST=1
say() { if [ "$TEST" = 1 ]; then echo "bc5-gpu-watch: $*"; else echo "<4>bc5-gpu-watch: $*" > /dev/kmsg; fi; }
deadline=0; armed_by=
act() {   # [sync seconds] [reason]
  say "${2:-no reset end $GRACE s after [$armed_by]}: syncing and crashing the kernel for a reboot (SysRq s, c)"
  [ "$TEST" = 1 ] && { echo "WOULD REBOOT"; exit 0; }
  echo s > /proc/sysrq-trigger; sleep "${1:-5}"
  echo c > /proc/sysrq-trigger
  sleep 30; echo b > /proc/sysrq-trigger   # if the crash did not reboot (panic settings undone): reboot outright
}
if [ "$TEST" = 1 ]; then exec 3<&0; else exec 3< <(dmesg --follow-new --notime 2> /dev/null); fi
say "watching the kernel log for amdgpu resets that do not finish (grace $GRACE s)"
while :; do
  if IFS= read -r -t 5 -u 3 line; then
    case "$line" in
      *bc5-gpu-watch:*) ;;   # its own kmsg lines quote the amdgpu line: matching them fed back (18:55, F420)
      *amdgpu*"GPU reset("*") succeeded"* | *amdgpu*"Ring "*" reset succeeded"*)
        [ "$deadline" != 0 ] && say "disarmed: $line"
        deadline=0; armed_by= ;;
      *amdgpu*"Ring "*" reset failed"*)
        act 1 "a ring reset failed [$line]: crashing before the full reset" ;;
      *amdgpu*"GPU reset begin"* | *amdgpu*"ring "*" timeout"*)
        if [ "$deadline" = 0 ]; then deadline=$(( $(date +%s) + GRACE )); armed_by=$line; say "armed: $line"; fi ;;
    esac
  else
    rc=$?
    if [ "$rc" -le 128 ]; then   # end of input (test) or dmesg gone (service: restart)
      [ "$TEST" = 1 ] && { [ "$deadline" != 0 ] && act; echo "END (no reboot)"; exit 0; }
      say "the kernel log stream ended (rc $rc): exiting for a restart"; exit 1
    fi
  fi
  if [ "$deadline" != 0 ] && [ "$(date +%s)" -ge "$deadline" ]; then act; fi
done
