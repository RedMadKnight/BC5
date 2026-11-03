#!/usr/bin/env bash
# BC5 exp 0388, memory: the long-play sampler for the maintainer's "leak" reading (2026-11-03). Every 20 s while the emulator
# runs, one line of name=value fields to stdout, for ssh from the laptop. Read only: /proc and /sys, no lock.
# The emulator's numbers come from /proc/<pid>/status, which keeps counters: smaps_rollup would walk its 16-GiB guest
# mappings under the mmap lock every 20 s and could stall the title's page faults. The mount is small, so it gets PSS.
# Fields, MiB unless named: avail free cached shmem bufs anon mapped sreclaim sunreclaim mlocked swap (used) zram_orig
# zram_compr zram_used; gtt; psi_mem_full_us psi_io_full_us (totals); e_rss e_anon e_file e_shmem e_swap e_majflt e_threads
# e_fds; m_rss m_pss m_swap m_read (cumulative) m_majflt; vm_pgmajfault vm_pswpin vm_pswpout vm_refault (cumulative
# counts); then the emulator's DRM clients, c<id>=<GTT MiB>/<resident>/<shared>.
# usage: ssh bc250 'bash -s -- 14400' < leak0389m.sh >> leak-<date>.txt   (start before the game; waits up to 10 min)
set -u
export LC_ALL=C
MAX=${1:-14400}
for _ in $(seq 1 1200); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
[ -n "${EP:-}" ] || { echo "# no emulator"; exit 1; }
MP=$(pgrep -o -x bc5-mount || echo "")
echo "# $(date '+%F %T') emulator $EP ($(readlink "/proc/$EP/exe"), md5 $(md5sum < "/proc/$EP/exe" | cut -c1-8)), bc5-mount ${MP:-none}; kernel $(uname -r); swappiness $(cat /proc/sys/vm/swappiness)"
mib() { awk -v k="$1" '$1 == k":" {printf "%d", $2 / 1024; f = 1} END {if (!f) printf "-1"}' "$2" 2> /dev/null || printf -- -1; }
T0=$(date +%s)
while [ -d "/proc/$EP" ] && [ $(($(date +%s) - T0)) -lt "$MAX" ]; do
  t=$(($(date +%s) - T0))
  mi=$(awk '{v[$1] = int($2 / 1024)} END {printf "avail=%d free=%d cached=%d shmem=%d bufs=%d anon=%d mapped=%d sreclaim=%d sunreclaim=%d mlocked=%d swap=%d",
        v["MemAvailable:"], v["MemFree:"], v["Cached:"], v["Shmem:"], v["Buffers:"], v["AnonPages:"], v["Mapped:"], v["SReclaimable:"], v["SUnreclaim:"],
        v["Mlocked:"], v["SwapTotal:"] - v["SwapFree:"]}' /proc/meminfo)
  zr=$(awk '{printf "zram_orig=%d zram_compr=%d zram_used=%d", $1 / 1048576, $2 / 1048576, $3 / 1048576}' /sys/block/zram0/mm_stat 2> /dev/null || echo "zram_orig=-1 zram_compr=-1 zram_used=-1")
  gtt=$(awk '{printf "%d", $1 / 1048576}' /sys/class/drm/card1/device/mem_info_gtt_used 2> /dev/null || echo -1)
  pm=$(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)
  pio=$(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/io)
  S=/proc/$EP/status
  em="e_rss=$(mib VmRSS "$S") e_anon=$(mib RssAnon "$S") e_file=$(mib RssFile "$S") e_shmem=$(mib RssShmem "$S") e_swap=$(mib VmSwap "$S")"
  em="$em e_majflt=$(awk '{print $12}' "/proc/$EP/stat" 2> /dev/null || echo -1) e_threads=$(awk '$1 == "Threads:" {print $2}' "$S" 2> /dev/null || echo -1) e_fds=$(ls "/proc/$EP/fd" 2> /dev/null | wc -l)"
  if [ -n "$MP" ] && [ -d "/proc/$MP" ]; then
    mt="m_rss=$(mib Rss "/proc/$MP/smaps_rollup") m_pss=$(mib Pss "/proc/$MP/smaps_rollup") m_swap=$(mib Swap "/proc/$MP/smaps_rollup")"
    case "$mt" in *"m_pss=-1"*) mt="m_rss=$(mib VmRSS "/proc/$MP/status") m_pss=-1 m_swap=$(mib VmSwap "/proc/$MP/status")" ;; esac  # smaps_rollup unreadable: status
    mt="$mt m_read=$(awk '/^read_bytes:/ {printf "%d", $2 / 1048576}' "/proc/$MP/io" 2> /dev/null || echo -1) m_majflt=$(awk '{print $12}' "/proc/$MP/stat" 2> /dev/null || echo -1)"
  else mt="m_rss=-1 m_pss=-1 m_swap=-1 m_read=-1 m_majflt=-1"; fi
  vm=$(awk '$1 == "pswpin" || $1 == "pswpout" || $1 == "pgmajfault" || $1 == "workingset_refault_file" {v[$1] = $2}
       END {printf "vm_pgmajfault=%d vm_pswpin=%d vm_pswpout=%d vm_refault=%d", v["pgmajfault"], v["pswpin"], v["pswpout"], v["workingset_refault_file"]}' /proc/vmstat)
  fd=$(for f in /proc/$EP/fdinfo/*; do awk 'function m(v, u) { return u == "KiB" ? v / 1024 : (u == "MiB" ? v : v / 1048576) }
      BEGIN {g = "?"; r = "?"; h = "?"} /^drm-client-id:/ {c = $2} /^drm-total-gtt:/ {g = sprintf("%d", m($2, $3))} /^drm-memory-gtt:/ {if (g == "?") g = sprintf("%d", m($2, $3))}
      /^drm-resident-gtt:/ {r = sprintf("%d", m($2, $3))} /^drm-shared-gtt:/ {h = sprintf("%d", m($2, $3))}
      END {if (c != "") printf "c%s=%s/%s/%s\n", c, g, r, h}' "$f" 2> /dev/null; done | sort -u | tr '\n' ' ')
  echo "t=$t $mi $zr gtt=$gtt psi_mem_full_us=$pm psi_io_full_us=$pio $em $mt $vm $fd"
  sleep 20
done
echo "# end $(date '+%F %T') after $(($(date +%s) - T0)) s"
