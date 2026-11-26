#!/usr/bin/env bash
# BC5 exp 0381: one line a second for the re-read arms, read-only, on the box beside a run. The minute samples could not
# separate the page cache, swap and the NVMe; this does. It ends when the mount is gone or at the cap, and keeps nothing but
# its output file. Columns are named on each line; counters are cumulative, so the analysis takes differences.
# usage: sample-reread.sh <out-file> [cap_s]   (PROC and DRM point it at stand-ins in the test)
set -u
OUT=${1:?out file}; CAP=${2:-1500}
PROC=${PROC:-/proc}
DRM=${DRM:-/sys/class/drm/card0/device}
EVERY=${EVERY:-1}
start=$(date +%s)
waited=0
while :; do
    M=$(pgrep -x bc5-mount | head -1)
    [ -n "$M" ] && break
    waited=$((waited + 1)); [ "$waited" -ge 120 ] && { echo "no mount in 120 s" >> "$OUT"; exit 0; }
    sleep 1
done
vm() { awk 'BEGIN { split("pgmajfault pswpin pswpout workingset_refault_file workingset_refault_anon pgsteal_direct pgsteal_kswapd allocstall_normal allocstall_movable", k); for (i in k) w[k[i]] = 1 } $1 in w { printf " %s=%s", $1, $2 }' "$PROC/vmstat"; }
mem() { awk '$1 == "MemAvailable:" || $1 == "Cached:" || $1 == "Active(file):" || $1 == "Inactive(file):" || $1 == "Shmem:" || $1 == "SwapFree:" || $1 == "Dirty:" { n = $1; sub(":", "", n); gsub(/[()]/, "_", n); printf " %s=%s", n, $2 }' "$PROC/meminfo"; }
psi() { for r in memory io cpu; do [ -r "$PROC/pressure/$r" ] && awk -v r="$r" '{ split($NF, t, "="); printf " %s_%s_us=%s", r, $1, t[2] }' "$PROC/pressure/$r"; done; }
pio() { [ -r "$PROC/$1/io" ] && awk -v p="$2" '$1 == "rchar:" || $1 == "read_bytes:" || $1 == "write_bytes:" { n = $1; sub(":", "", n); printf " %s_%s=%s", p, n, $2 }' "$PROC/$1/io"; }
# utime + stime, comm stripped first: a name may hold spaces.
cpu() { [ -r "$PROC/$1/stat" ] && sed 's/^.*) //' "$PROC/$1/stat" | awk -v p="$2" '{ printf " %s_majflt=%s %s_cpu_ticks=%s", p, $10, p, $12 + $13 }'; }
# The emulator's threads with the most major faults, once in ten lines: who waits for pages.
threads() {
    for t in "$PROC/$1"/task/*; do
        [ -r "$t/stat" ] || continue
        c=$(cat "$t/comm" 2> /dev/null)
        sed 's/^.*) //' "$t/stat" 2> /dev/null | awk -v c="$c" '{ printf "%s %s\n", $10, c }'
    done | sort -rn | head -5 | awk '{ printf " %s:%s", $2, $1 }'
}
i=0
while [ -d "$PROC/$M" ]; do
    now=$(date +%s)
    [ $((now - start)) -ge "$CAP" ] && break
    E=$(pgrep '^kyty_emulator' | head -1)
    {
        printf 'T %s' "$now"
        vm; mem; psi
        pio "$M" mount; cpu "$M" mount
        if [ -n "$E" ]; then pio "$E" emu; cpu "$E" emu; fi
        [ -r "$DRM/mem_info_gtt_used" ] && printf ' gtt=%s' "$(cat "$DRM/mem_info_gtt_used")"
        echo
        if [ -n "$E" ] && [ $((i % 10)) = 0 ]; then
            printf 'THREADS %s' "$now"; threads "$E"; echo
        fi
    } >> "$OUT"
    i=$((i + 1))
    sleep "$EVERY"
done
echo "END $(date +%s)" >> "$OUT"
