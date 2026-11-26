#!/usr/bin/env bash
# BC5 experiment 0330: the box's memory every 10 s while an emulator runs, one line each, to <out> (exp 0288's
# sample0288.sh with the reclaim split added): uptime, MemAvailable/SwapFree/Shmem/Cached/Dirty (MiB), zram data/compressed
# (MiB), PSI memory full total (us), GTT used (MiB), the emulator's smaps_rollup (Rss, Pss_Shmem, Anonymous, Swap in MiB) and
# thread count, bc5-mount's Rss/Swap (MiB), /proc/vmstat pswpin/pswpout/pgmajfault/compact_stall, then Active(file) and
# Inactive(file) (MiB) and /proc/vmstat pgsteal_file/pgsteal_anon/workingset_refault_file/workingset_refault_anon (whether
# reclaim takes the page cache or the title's pages). Read-only (/proc, /sys). Ends when the emulator is gone or after <max s>.
# usage: sample0330.sh <out> [max s]   (started before the emulator; waits up to 120 s for it)
set -u
OUT=$1; MAX=${2:-900}
for _ in $(seq 1 240); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${EP:-}" ] || { echo "no emulator" >> "$OUT"; exit 1; }
MP=$(pgrep -o -x bc5-mount || echo "")
echo "# emulator $EP ($(readlink "/proc/$EP/exe")), bc5-mount ${MP:-none}; columns: uptime avail swapfree shmem cached dirty zram_data zram_compr psi_full_us gtt_used_mib emu_rss emu_pss_shmem emu_anon emu_swap emu_threads mount_rss mount_swap pswpin pswpout pgmajfault compact_stall active_file inactive_file pgsteal_file pgsteal_anon refault_file refault_anon" >> "$OUT"
T0=$(date +%s)
while [ -d "/proc/$EP" ] && [ $(($(date +%s) - T0)) -lt "$MAX" ]; do
  mi=$(awk '/^MemAvailable:/ {a=$2} /^SwapFree:/ {s=$2} /^Shmem:/ {h=$2} /^Cached:/ {c=$2} /^Dirty:/ {d=$2} END {printf "%d %d %d %d %d", a/1024, s/1024, h/1024, c/1024, d/1024}' /proc/meminfo)
  zr=$(awk '{printf "%d %d", $1/1048576, $2/1048576}' /sys/block/zram0/mm_stat 2> /dev/null || echo "0 0")
  psi=$(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)
  gtt=$(awk '{printf "%d", $1/1048576}' /sys/class/drm/card1/device/mem_info_gtt_used 2> /dev/null || echo 0)
  emu=$(awk '/^Rss:/ {r=$2} /^Pss_Shmem:/ {s=$2} /^Anonymous:/ {a=$2} /^Swap:/ {w=$2} END {printf "%d %d %d %d", r/1024, s/1024, a/1024, w/1024}' "/proc/$EP/smaps_rollup" 2> /dev/null || echo "0 0 0 0")
  th=$(awk '/^Threads:/ {print $2}' "/proc/$EP/status" 2> /dev/null || echo 0)
  if [ -n "$MP" ] && [ -d "/proc/$MP" ]; then mnt=$(awk '/^Rss:/ {r=$2} /^Swap:/ {w=$2} END {printf "%d %d", r/1024, w/1024}' "/proc/$MP/smaps_rollup"); else mnt="0 0"; fi
  vm=$(awk '$1 == "pswpin" || $1 == "pswpout" || $1 == "pgmajfault" || $1 == "compact_stall" {v[$1]=$2} END {printf "%d %d %d %d", v["pswpin"], v["pswpout"], v["pgmajfault"], v["compact_stall"]}' /proc/vmstat)
  lru=$(awk '/^Active\(file\):/ {a=$2} /^Inactive\(file\):/ {i=$2} END {printf "%d %d", a/1024, i/1024}' /proc/meminfo)
  rc=$(awk '$1 == "pgsteal_file" || $1 == "pgsteal_anon" || $1 == "workingset_refault_file" || $1 == "workingset_refault_anon" {v[$1]=$2} END {printf "%d %d %d %d", v["pgsteal_file"], v["pgsteal_anon"], v["workingset_refault_file"], v["workingset_refault_anon"]}' /proc/vmstat)
  echo "$(cut -d' ' -f1 /proc/uptime) $mi $zr $psi $gtt $emu $th $mnt $vm $lru $rc" >> "$OUT"
  sleep 10
done
echo "# end $(date '+%F %T')" >> "$OUT"
