#!/usr/bin/env bash
# BC5 exp 0412: the whole box's memory at given moments of one emulator run (the top session, 2026-11-11: "one measured
# whole-box table at his wall ... the sum must close to MemTotal"). Read-only, on the host. At each <second> after the
# emulator's start it writes one block with: /proc/meminfo; the emulator's status, smaps_rollup and a per-class sum of
# its smaps; every process's RssAnon/RssFile/RssShmem/VmSwap/VmPTE summed by name; memory.current and the main
# memory.stat lines of every cgroup down to the user's services and the container; the GPU's GTT and VRAM counters;
# zram's mm_stat; the THP settings; tmpfs use.
# usage (host): snap0412.sh <out file> <second> [<second> ...]
set -u
export LC_ALL=C
OUT=${1:?out}; shift
[ "$#" -ge 1 ] || { echo "seconds, please"; exit 1; }
EP=""
for _ in $(seq 1 90); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 180 s" >> "$OUT"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
D=/sys/class/drm/card1/device
snap() {
  echo "######## snapshot at $(($(date +%s) - T0)) s ($(date '+%F %T')), emulator $EP"
  echo "## meminfo"; cat /proc/meminfo
  echo "## emulator status"; grep -E '^(VmRSS|RssAnon|RssFile|RssShmem|VmSwap|VmPTE|VmData|VmSize|Threads):' "/proc/$EP/status"
  echo "## emulator smaps_rollup"; cat "/proc/$EP/smaps_rollup" 2> /dev/null
  echo "## emulator smaps by class (kB): class maps size rss pss anon swap shmem_pmd"
  awk '
    function flush() { if (range == "") return
      cls = "other"; if (name == "[heap]") cls = "heap"; else if (name ~ /^\[stack/) cls = "stack"; else if (name ~ /memfd:KytyDirect/) cls = "memfd-direct"
      else if (name ~ /memfd:KytyPrivate/) cls = "memfd-private"; else if (name ~ /memfd:/) cls = "memfd-other"; else if (name ~ /^\/dev\/dri|drm|amdgpu/) cls = "gpu-map"
      else if (name == "") cls = "anon"; else if (name ~ /^\//) cls = "file"
      n[cls]++; sz[cls] += size; rs[cls] += rss; ps[cls] += pss; an[cls] += anon; sw[cls] += swap; pm[cls] += pmd }
    /^[0-9a-f]+-[0-9a-f]+ / { flush(); range = $1; name = ""; for (i = 6; i <= NF; i++) name = name (i > 6 ? " " : "") $i; size = rss = pss = anon = swap = pmd = 0; next }
    /^Size:/ { size = $2 } /^Rss:/ { rss = $2 } /^Pss:/ { pss = $2 } /^Anonymous:/ { anon = $2 } /^Swap:/ { swap = $2 } /^ShmemPmdMapped:/ { pmd = $2 }
    END { flush(); for (c in n) print c, n[c], sz[c], rs[c], ps[c], an[c], sw[c], pm[c] }' "/proc/$EP/smaps" 2> /dev/null
  echo "## processes by name (kB): name count rssanon rssfile rssshmem vmswap vmpte"
  for s in /proc/[0-9]*/status; do cat "$s" 2> /dev/null; echo "--"; done | awk '
    /^Name:/ { name = $2 } /^RssAnon:/ { a = $2 } /^RssFile:/ { f = $2 } /^RssShmem:/ { sh = $2 } /^VmSwap:/ { sw = $2 } /^VmPTE:/ { pt = $2 }
    /^--/ { if (name != "") { c[name]++; A[name] += a; F[name] += f; S[name] += sh; W[name] += sw; P[name] += pt } name = ""; a = f = sh = sw = pt = 0 }
    END { for (k in c) if (A[k] + F[k] + S[k] + W[k] > 2048) print k, c[k], A[k], F[k], S[k], W[k], P[k] }' | sort -k3,3nr
  echo "## cgroups (bytes): path current swap | anon file shmem kernel slab pagetables file_mapped inactive_file active_file unevictable"
  for g in /sys/fs/cgroup /sys/fs/cgroup/*.slice /sys/fs/cgroup/user.slice/user-*.slice /sys/fs/cgroup/user.slice/user-*.slice/* /sys/fs/cgroup/user.slice/user-*.slice/user@*.service/* /sys/fs/cgroup/user.slice/user-*.slice/user@*.service/user.slice/* /sys/fs/cgroup/user.slice/user-*.slice/user@*.service/user.slice/*/container /sys/fs/cgroup/system.slice/*; do
    [ -r "$g/memory.stat" ] || continue
    cur=$(cat "$g/memory.current" 2> /dev/null || echo -); swc=$(cat "$g/memory.swap.current" 2> /dev/null || echo -)
    [ "$cur" = - ] || [ "$cur" -ge 20971520 ] || continue
    echo "${g#/sys/fs/cgroup} $cur $swc | $(awk '$1 == "anon" || $1 == "file" || $1 == "shmem" || $1 == "kernel" || $1 == "slab" || $1 == "pagetables" || $1 == "file_mapped" || $1 == "inactive_file" || $1 == "active_file" || $1 == "unevictable" { printf "%s=%s ", $1, $2 }' "$g/memory.stat")"
  done
  echo "## gpu (bytes)"; for f in mem_info_gtt_used mem_info_gtt_total mem_info_vram_used mem_info_vram_total mem_info_vis_vram_used; do echo "$f $(cat "$D/$f" 2> /dev/null)"; done
  echo "## zram mm_stat (orig compr mem_used limit max same pages_compacted huge)"; cat /sys/block/zram0/mm_stat 2> /dev/null
  echo "## thp"; for f in enabled shmem_enabled defrag; do echo "$f: $(cat /sys/kernel/mm/transparent_hugepage/$f 2> /dev/null)"; done
  echo "## tmpfs"; df -k -t tmpfs 2> /dev/null | awk 'NR == 1 || $3 > 1024'
  echo "## vmstat"; grep -E '^(nr_shmem|nr_shmem_hugepages|nr_file_pages|nr_anon_pages|nr_mapped|nr_unevictable|nr_mlock|nr_page_table_pages|nr_kernel_stack|nr_slab_reclaimable|nr_slab_unreclaimable|nr_zspages|nr_free_pages|nr_zone_inactive_anon|nr_zone_active_anon|nr_zone_inactive_file|nr_zone_active_file|nr_swapcached|nr_vmscan_write|nr_sec_page_table_pages) ' /proc/vmstat
}
for t in "$@"; do
  while [ -d "/proc/$EP" ] && [ $(($(date +%s) - T0)) -lt "$t" ]; do sleep 1; done
  [ -d "/proc/$EP" ] || break
  snap >> "$OUT" 2>&1
done
echo "# end $(date '+%F %T')" >> "$OUT"
