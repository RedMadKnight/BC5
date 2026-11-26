#!/usr/bin/env bash
# BC5 experiment 0330: the box's memory every 10 s during the maintainer's play on the test shortcut (his choice "a",
# 2026-10-26). It is sample0330.sh's line (same 27 columns, same order) plus who reads the title's data:
#   - the emulator's and bc5-mount's read_bytes and rchar from /proc/<pid>/io (MiB);
#   - the NVMe's sectors read (MiB, /sys/block/nvme0n1/stat);
#   - VRAM in use (MiB).
# Read-only (/proc, /sys); one line each 10 s; it ends when the emulator is gone or after <max s>. A column it cannot
# read shows -1.
# usage: sample0330p.sh <out> [max s]   (started on the host before the launcher; waits up to 180 s for the emulator)
set -u
OUT=$1; MAX=${2:-7200}
for _ in $(seq 1 360); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${EP:-}" ] || { echo "# no emulator within 180 s $(date '+%F %T')" >> "$OUT"; exit 1; }
MP=$(pgrep -o -x bc5-mount || echo "")
echo "# $(date '+%F %T') emulator $EP ($(readlink "/proc/$EP/exe")), bc5-mount ${MP:-none}; columns: uptime avail swapfree shmem cached dirty zram_data zram_compr psi_full_us gtt_used_mib emu_rss emu_pss_shmem emu_anon emu_swap emu_threads mount_rss mount_swap pswpin pswpout pgmajfault compact_stall active_file inactive_file pgsteal_file pgsteal_anon refault_file refault_anon emu_read_mib emu_rchar_mib mount_read_mib mount_rchar_mib nvme_read_mib vram_used_mib" >> "$OUT"
io() { awk '/^read_bytes:/ {r=$2} /^rchar:/ {c=$2} END {if (r == "" || c == "") print "-1 -1"; else printf "%d %d", r/1048576, c/1048576}' "/proc/$1/io" 2> /dev/null || echo "-1 -1"; }
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
  eio=$(io "$EP"); if [ -n "$MP" ] && [ -d "/proc/$MP" ]; then mio=$(io "$MP"); else mio="-1 -1"; fi
  nv=$(awk '{printf "%d", $3 * 512 / 1048576}' /sys/block/nvme0n1/stat 2> /dev/null || echo -1)
  vr=$(awk '{printf "%d", $1/1048576}' /sys/class/drm/card1/device/mem_info_vram_used 2> /dev/null || echo -1)
  echo "$(cut -d' ' -f1 /proc/uptime) $mi $zr $psi $gtt $emu $th $mnt $vm $lru $rc $eio $mio $nv $vr" >> "$OUT"
  sleep 10
done
echo "# end $(date '+%F %T')" >> "$OUT"
