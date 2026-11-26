#!/usr/bin/env bash
# BC5 exp 0439 (tag ms439, the top session's order of 11-23 ~22:50, owed since the 11-22 23:19 freeze): a memory
# sampler beside the maintainer's play, so a silent freeze leaves its last moment on disk. Reads only /proc and sysfs
# (no root): MemAvailable, SwapFree, Dirty, Unevictable, Shmem, SUnreclaim, PageTables, Mlocked (kB), the GPU's GTT and
# VRAM in use (amdgpu's mem_info_gtt_used / mem_info_vram_used, MiB), and for the emulator: RssAnon, RssShmem, VmPTE
# (kB) and its count of CPU mappings (lines of /proc/<pid>/maps). Each line is appended and the file synced (coreutils
# sync FILE = fsync) before the next sample.
# 11-24 ~08:55: MS_INTERVAL (s, default 1; 0.1 for a spike). 11-24 ~09:40 (the top session's order after the 08:50
# freeze): the five /proc/meminfo fields and VmPTE added at the end of each line; MS_MAPS_S (s, default 0 = off): every
# so many seconds the emulator's /proc/<pid>/maps, gzipped, to <tag>-maps/<seconds>.gz, for what makes the count grow.
#   memsample439.sh <tag>      (started by the launcher before the emulator; ends when the launcher kills it, or by
#                               itself 30 s after the emulator is gone)
set -u
tag=${1:?tag}
D=$HOME/bc5-data/captures/memsample; mkdir -p "$D"; chmod 700 "$D"
F=$D/$tag.txt
G=$(ls /sys/class/drm/card*/device/mem_info_gtt_used 2> /dev/null | head -1)
V=$(ls /sys/class/drm/card*/device/mem_info_vram_used 2> /dev/null | head -1)
I=${MS_INTERVAL:-1}; MS=${MS_MAPS_S:-0}; M=$D/$tag-maps; [ "$MS" != 0 ] && { mkdir -p "$M"; chmod 700 "$M"; }
limit=$(awk -v i="$I" 'BEGIN { printf "%d", 30 / i }')
echo "# ms439 $tag (interval $I s): time mem_avail_kB swap_free_kB dirty_kB gtt_used_MiB vram_used_MiB emu_pid rss_anon_kB rss_shmem_kB cpu_maps unevictable_kB shmem_kB sunreclaim_kB pagetables_kB mlocked_kB vmpte_kB psi_mem_some10 psi_mem_full10 psi_io_full10 allocstall pgscan_direct oom_kill procs_running procs_blocked" > "$F"
sync "$F"
# 11-24 ~11:00 (the freeze catcher without sudo): MS_KLOG=1 tees the kernel's lines as journald receives them
# (journalctl -kf, before journald's own disk flush) into <tag>-klog.txt, one fsync per line; the last fields of each
# sample line: memory/io pressure (avg10), the direct-reclaim and OOM counters of /proc/vmstat, running/blocked tasks.
if [ "${MS_KLOG:-0}" = 1 ]; then
    KL=$D/$tag-klog.txt
    MSP=$$ # the reader stops with the sampler (checked at each line); journalctl then ends on SIGPIPE at its next line
    ( journalctl -k -f -n 20 --no-pager -o short-precise 2>&1 | while IFS= read -r l; do kill -0 "$MSP" 2> /dev/null || exit 0; printf '%s\n' "$l" >> "$KL"; sync "$KL"; done ) &
    KLP=$!
    trap 'pkill -P $KLP 2> /dev/null; kill $KLP 2> /dev/null' EXIT # children first: after the subshell dies they are reparented
    trap 'exit 0' TERM INT
fi
gone=0; t0=$(date +%s); next_maps=$MS
while :; do
    pid=$(pgrep -o "^kyty_emulator" 2> /dev/null || true)
    mi=$(awk '/^(MemAvailable|SwapFree|Dirty|Unevictable|Shmem|SUnreclaim|PageTables|Mlocked):/ {v[$1] = $2} END {n = split("MemAvailable: SwapFree: Dirty: Unevictable: Shmem: SUnreclaim: PageTables: Mlocked:", k, " "); for (i = 1; i <= n; i++) printf "%s%s", (k[i] in v ? v[k[i]] : "-"), (i < n ? " " : "")}' /proc/meminfo)
    set -- $mi
    gt=$([ -n "$G" ] && echo $(( $(cat "$G") / 1048576 )) || echo -)
    vr=$([ -n "$V" ] && echo $(( $(cat "$V") / 1048576 )) || echo -)
    ra=-; rs=-; mp=-; pt=-
    if [ -n "$pid" ]; then
        st=$(awk '/^(RssAnon|RssShmem|VmPTE):/ {v[$1] = $2} END {n = split("RssAnon: RssShmem: VmPTE:", k, " "); for (i = 1; i <= n; i++) printf "%s%s", (k[i] in v ? v[k[i]] : "-"), (i < n ? " " : "")}' /proc/$pid/status 2> /dev/null)
        ra=$(echo "$st" | cut -d' ' -f1); rs=$(echo "$st" | cut -d' ' -f2); pt=$(echo "$st" | cut -d' ' -f3)
        mp=$(wc -l < /proc/$pid/maps 2> /dev/null || echo -)
        gone=0
        if [ "$MS" != 0 ]; then
            el=$(( $(date +%s) - t0 ))
            if [ "$el" -ge "$next_maps" ]; then gzip -c /proc/$pid/maps > "$M/$el.gz" 2> /dev/null; next_maps=$((el + MS)); fi
        fi
    else
        gone=$((gone + 1))
        [ $gone -gt "$limit" ] && exit 0
    fi
    ps_=$(awk '/^some/ {split($2, a, "="); s = a[2]} /^full/ {split($2, b, "="); f = b[2]} END {printf "%s %s", (s == "" ? "-" : s), (f == "" ? "-" : f)}' /proc/pressure/memory 2> /dev/null || echo "- -")
    pio=$(awk '/^full/ {split($2, b, "="); f = b[2]} END {printf "%s", (f == "" ? "-" : f)}' /proc/pressure/io 2> /dev/null || echo -)
    vm=$(awk '/^allocstall_/ {a += $2} /^pgscan_direct/ {p += $2} /^oom_kill / {o = $2} END {printf "%d %d %s", a, p, (o == "" ? "-" : o)}' /proc/vmstat 2> /dev/null || echo "- - -")
    pr=$(awk '/^procs_running/ {r = $2} /^procs_blocked/ {b = $2} END {printf "%s %s", (r == "" ? "-" : r), (b == "" ? "-" : b)}' /proc/stat 2> /dev/null || echo "- -")
    # 11-24 15:20 (the top session, after cE2's guard stop from a 3.8 GB AnonPages jump outside the emulator): below 1 GB
    # available, the six largest processes by RSS, at most every 5 s, to <tag>-top.txt
    if [ "$1" != - ] && [ "$1" -lt 1048576 ] && [ "$(date +%s)" -ge "${next_top:-0}" ]; then
        echo "$(date +%T) avail $1 kB: $(ps -eo pid,rss,comm --sort=-rss 2> /dev/null | sed -n 2,7p | tr -s ' ' | tr '\n' ';')" >> "$D/$tag-top.txt"; sync "$D/$tag-top.txt"
        next_top=$(( $(date +%s) + 5 ))
    fi
    echo "$(date +%T.%N | cut -c1-12) $1 $2 $3 $gt $vr ${pid:--} ${ra:--} ${rs:--} $mp $4 $5 $6 $7 $8 ${pt:--} $ps_ $pio $vm $pr" >> "$F"
    sync "$F"
    sleep "$I"
done
