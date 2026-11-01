#!/usr/bin/env bash
# BC5 exp 0388, memory cycle: exp 0379's sampler, to stdout, for ssh from the laptop, with major faults per process.
# BC5 experiment 0379, GTT growth (raw/sample0379.sh plus the emulator's GPU memory per DRM client): the box's memory
# and I/O every 10 s while an
# emulator runs, one line each, to <out>. Read-only (/proc, /sys). Ends when the emulator is gone or after <max s>.
# Columns: uptime; MemAvailable SwapUsed Shmem Cached (MiB); GTT used (MiB); PSI memory full total, PSI io full total (us);
# bc5-mount read_bytes (MiB, cumulative) and Rss (MiB); the emulator's Rss (MiB); /proc/vmstat pswpin pswpout pgmajfault
# workingset_refault_file; then one field per DRM client of the emulator, c<client id>=<GTT MiB>/<resident GTT MiB>/<shared GTT MiB>, from
# /proc/<pid>/fdinfo (drm-total-gtt, else the older drm-memory-gtt; drm-resident-gtt; drm-shared-gtt, the dma-buf
# shared part; 7.2.9 prints all four, read 2026-10-30 on plasma-keyboard's fds; KiB or MiB units; "?" when a field
# is missing). TODO(verify) the
# key names on kernel 7.2.9 and that the direct path's udmabuf imports count in its client's drm-total-gtt.
# usage: ssh bc250 'bash -s -- 7200' < sample0388m.sh >> samples.txt   (started before the emulator; waits up to 10 min)
set -u
MAX=${1:-7200}
for _ in $(seq 1 1200); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${EP:-}" ] || { echo "# no emulator"; exit 1; }
MP=$(pgrep -o -x bc5-mount || echo "")
echo "# emulator $EP ($(readlink "/proc/$EP/exe")), bc5-mount ${MP:-none}; columns: uptime avail swapused shmem cached gtt_used psi_mem_full_us psi_io_full_us mount_read_mib mount_rss emu_rss pswpin pswpout pgmajfault refault_file emu_majflt mount_majflt c<id>=gtt/resident/shared..."
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
  # Codex review (REVIEW-02): the END block's newline is an escape, and a missing GTT or resident field prints "?"
  # (unknown), never 0.
  fd=$(for f in /proc/$EP/fdinfo/*; do awk 'function mib(v, u) { return u == "KiB" ? v / 1024 : (u == "MiB" ? v : v / 1048576) }
      BEGIN {t = "?"; m = "?"; r = "?"; h = "?"} /^drm-client-id:/ {c=$2} /^drm-total-gtt:/ {t=sprintf("%d", mib($2, $3))}
      /^drm-memory-gtt:/ {m=sprintf("%d", mib($2, $3))} /^drm-resident-gtt:/ {r=sprintf("%d", mib($2, $3))} /^drm-shared-gtt:/ {h=sprintf("%d", mib($2, $3))}
      END {if (c != "") printf "c%s=%s/%s/%s\n", c, (t != "?" ? t : m), r, h}' "$f" 2> /dev/null; done | sort -u | tr '\n' ' ')
  ej=$(awk '{print $12}' "/proc/$EP/stat" 2> /dev/null || echo -1)
  mj=$( [ -n "$MP" ] && awk '{print $12}' "/proc/$MP/stat" 2> /dev/null || echo -1)
  echo "$(cut -d' ' -f1 /proc/uptime) $mi $gtt $pm $pio $mnt $er $vm $ej $mj $fd"
  sleep 10
done
echo "# end $(date '+%F %T')"
