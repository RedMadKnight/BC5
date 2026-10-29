#!/usr/bin/env bash
# BC5 experiment 0379 (exp 0330's sample0330.sh plus exp 0371's I/O): the box's memory and I/O every 10 s while an
# emulator runs, one line each, to <out>. Read-only (/proc, /sys). Ends when the emulator is gone or after <max s>.
# Columns: uptime; MemAvailable SwapUsed Shmem Cached (MiB); GTT used (MiB); PSI memory full total, PSI io full total (us);
# bc5-mount read_bytes (MiB, cumulative) and Rss (MiB); the emulator's Rss (MiB); /proc/vmstat pswpin pswpout pgmajfault
# workingset_refault_file.
# usage: sample0379.sh <out> [max s]   (started before the emulator; waits up to 120 s for it)
set -u
OUT=$1; MAX=${2:-900}
for _ in $(seq 1 240); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${EP:-}" ] || { echo "# no emulator" >> "$OUT"; exit 1; }
MP=$(pgrep -o -x bc5-mount || echo "")
echo "# emulator $EP ($(readlink "/proc/$EP/exe")), bc5-mount ${MP:-none}; columns: uptime avail swapused shmem cached gtt_used psi_mem_full_us psi_io_full_us mount_read_mib mount_rss emu_rss pswpin pswpout pgmajfault refault_file" >> "$OUT"
T0=$(date +%s)
while [ -d "/proc/$EP" ] && [ $(($(date +%s) - T0)) -lt "$MAX" ]; do
  mi=$(awk '/^MemAvailable:/ {a=$2} /^SwapTotal:/ {t=$2} /^SwapFree:/ {s=$2} /^Shmem:/ {h=$2} /^Cached:/ {c=$2} END {printf "%d %d %d %d", a/1024, (t-s)/1024, h/1024, c/1024}' /proc/meminfo)
  gtt=$(awk '{printf "%d", $1/1048576}' /sys/class/drm/card1/device/mem_info_gtt_used 2> /dev/null || echo 0)
  pm=$(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)
  pio=$(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/io)
  if [ -n "$MP" ] && [ -d "/proc/$MP" ]; then
    mnt="$(awk '/^read_bytes:/ {printf "%d", $2/1048576}' "/proc/$MP/io" 2> /dev/null || echo -1) $(awk '/^VmRSS:/ {printf "%d", $2/1024}' "/proc/$MP/status" 2> /dev/null || echo -1)"
  else mnt="-1 -1"; fi
  er=$(awk '/^VmRSS:/ {printf "%d", $2/1024}' "/proc/$EP/status" 2> /dev/null || echo -1)
  vm=$(awk '$1 == "pswpin" || $1 == "pswpout" || $1 == "pgmajfault" || $1 == "workingset_refault_file" {v[$1]=$2} END {printf "%d %d %d %d", v["pswpin"], v["pswpout"], v["pgmajfault"], v["workingset_refault_file"]}' /proc/vmstat)
  echo "$(cut -d' ' -f1 /proc/uptime) $mi $gtt $pm $pio $mnt $er $vm" >> "$OUT"
  sleep 10
done
echo "# end $(date '+%F %T')" >> "$OUT"
