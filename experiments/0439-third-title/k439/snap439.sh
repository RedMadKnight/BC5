#!/usr/bin/env bash
# BC5 exp 0439 (tag sn439, 11-25 night, the top session's step 1: the memory budget at the peak). Every SN_EVERY s (30)
# while an emulator runs, one snapshot directory <out>/<hhmmss>/ with, all readable without root:
#   meminfo, vmstat, zram (mm_stat / disksize of every zram device), gtt (mem_info_* of the GPU);
#   emu-smaps-by-name.txt: the emulator's smaps summed per mapping name (Rss, Pss, Anonymous, Shared/Private, Swap,
#     Locked) with the number of mappings, emu-status.txt, emu-rollup.txt, emu-maps-count;
#   procs.txt: every process of the user with RSS over 50 MiB (pid, rss kB, comm, args);
#   drm.txt: per process with a DRM fd, the fdinfo totals (drm-memory-gtt / -vram / -cpu, drm-resident-*, drm-shared-*);
#   threads: the emulator's thread count and the summed stack mappings.
#   snap439.sh <out dir>
set -u
O=${1:?out dir}; EVERY=${SN_EVERY:-30}; mkdir -p "$O" && chmod 700 "$O"
G=$(ls -d /sys/class/drm/card*/device 2> /dev/null | head -1)
snap() {
    local p=$1 d; d=$O/$(date +%H%M%S); mkdir -p "$d"
    cat /proc/meminfo > "$d/meminfo"; cat /proc/vmstat > "$d/vmstat"
    for z in /sys/block/zram*; do [ -e "$z/mm_stat" ] && echo "$(basename "$z") disksize $(cat "$z/disksize") mm_stat $(cat "$z/mm_stat")"; done > "$d/zram"
    for f in mem_info_gtt_used mem_info_gtt_total mem_info_vram_used mem_info_vram_total mem_info_vis_vram_used; do echo "$f $(cat "$G/$f" 2> /dev/null)"; done > "$d/gtt"
    cat "/proc/$p/status" > "$d/emu-status.txt" 2> /dev/null; cat "/proc/$p/smaps_rollup" > "$d/emu-rollup.txt" 2> /dev/null
    wc -l < "/proc/$p/maps" > "$d/emu-maps-count" 2> /dev/null
    awk '/^[0-9a-f]+-[0-9a-f]+ / {n = (NF >= 6 ? $6 : "[anon]"); for (i = 7; i <= NF; i++) n = n " " $i; if (n ~ /^\/memfd:/) sub(/ \(deleted\)$/, "", n); maps[n]++; cur = n; next}
         /^(Rss|Pss|Anonymous|Shared_Clean|Shared_Dirty|Private_Clean|Private_Dirty|Swap|Locked):/ {k = $1; sub(":", "", k); v[cur, k] += $2; keys[k] = 1}
         END {printf "%-60s %8s %10s %10s %10s %10s %10s %10s %10s\n", "name", "maps", "Rss", "Pss", "Anonymous", "Shared_D", "Private_D", "Swap", "Locked";
              for (n in maps) printf "%-60s %8d %10d %10d %10d %10d %10d %10d %10d\n", substr(n, 1, 60), maps[n], v[n, "Rss"], v[n, "Pss"], v[n, "Anonymous"], v[n, "Shared_Dirty"], v[n, "Private_Dirty"], v[n, "Swap"], v[n, "Locked"]}' "/proc/$p/smaps" 2> /dev/null | sort -k3 -n -r > "$d/emu-smaps-by-name.txt"
    ps -u "$(id -u)" -o pid=,rss=,comm=,args= --sort=-rss | awk '$2 > 51200' | cut -c1-200 > "$d/procs.txt"
    for q in $(ls /proc | grep -E '^[0-9]+$'); do
        [ -O "/proc/$q" ] || continue
        s=$(for fd in /proc/$q/fd/*; do l=$(readlink "$fd" 2> /dev/null) || continue; case $l in /dev/dri/*) cat "/proc/$q/fdinfo/${fd##*/}" 2> /dev/null;; esac; done |
            awk '/^drm-client-id:/ {c = $2} /^drm-(memory|resident|shared|total|purgeable|active)-/ {if (!seen[c, $1]++) {k[$1] += $2; u[$1] = $3}} END {for (x in k) printf "%s %d %s; ", x, k[x], u[x]}')
        [ -n "$s" ] && echo "$q $(cat /proc/$q/comm 2> /dev/null): $s"
    done > "$d/drm.txt"
    echo "threads $(ls /proc/$p/task 2> /dev/null | wc -l)" > "$d/threads"
}
[ -n "${SN_PID:-}" ] && { snap "$SN_PID"; exit 0; } # a stand-in test on another process
t=0; until p=$(pgrep -o "^kyty_emulator") || [ $t -gt 600 ]; do sleep 0.5; t=$((t + 1)); done
[ -n "${p:-}" ] || exit 1
while kill -0 "$p" 2> /dev/null; do snap "$p"; sleep "$EVERY"; done
