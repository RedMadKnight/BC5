#!/usr/bin/env bash
# BC5 exp 0412, E1 (E1-plan.md): build e1-probe and run ONE case. Raw GPU submission (CLAUDE.md hard rule 5): only in
# its own slot, no emulator, the kernel log streamed by the caller, the maintainer's word (2026-11-13 "zgoda").
#   e1run.sh build            compile in the ubuntu container (no GPU); --dump-ib and compare with the laptop's sums
#   e1run.sh case N           N = 0..4: guard, claim the lock, run the case, keep its output and the kernel lines
# Files: $E1/src (e1-probe.cpp, dispatch_min.cpp, pm4.cpp, include/bc5/*.hpp from the branch), $E1/raw/case-N.*
# Stop rule (the caller applies it): for cases 0-3 any amdgpu kernel line means stop; for case 4 the page-fault,
# ring timeout and "reset succeeded" lines are the result; "reset failed", "GPU reset begin", MODE1, "VRAM is lost"
# mean stop (bc5-gpu-watch reboots the box then).
set -u
export LC_ALL=C
W=$HOME/bc5-work; E1=$W/exp0412/e1; LOCK=$W/BOX-LOCK; R=$E1/raw
die() { echo "STOP: $*"; exit 1; }
mkdir -p "$R" || die mkdir
case "${1:-}" in
  build)
    pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
    distrobox enter ubuntu -- bash -c "cd '$E1/src' && g++ -std=c++20 -O1 -Wall -Wextra -Werror -DBC5_WITH_AMDGPU -I include e1-probe.cpp dispatch_min.cpp pm4.cpp \$(pkg-config --cflags --libs libdrm_amdgpu libdrm) -o '$E1/e1-probe'" < /dev/null > "$R/build.out" 2>&1 ||
      die "the build failed: $(grep -m3 'error' "$R/build.out" | cut -c1-200 | tr '\n' ' ')"
    distrobox enter ubuntu -- "$E1/e1-probe" --dump-ib "$R/ib" < /dev/null | tee "$R/dump.out"
    md5sum "$E1/e1-probe" "$R/ib-clear.bin" "$R/ib-copy.bin"
    distrobox enter ubuntu -- "$E1/e1-probe" < /dev/null
    echo "built" ;;
  case)
    N=${2:?a case 0..4}
    case "$N" in [0-5]) ;; *) die "case 0..5" ;; esac
    [ -x "$E1/e1-probe" ] || die "not built"
    [ -e "$R/case-$N.out" ] && die "case $N has been run (raw/case-$N.out); it is not run twice"
    pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
    LINE="guard exp 0412 | E1 case $N (raw GPU submission, no emulator), token $$"
    [ -e "$LOCK" ] || touch "$LOCK"
    [ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
    printf '%s\n' "$LINE" > "$LOCK" || die "the claim failed"
    trap 'if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then : > "$LOCK"; fi' EXIT
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
    ND=$(sudo -n dmesg 2> /dev/null | wc -l)
    {
      echo "case $N at $(date '+%F %T'); kernel $(uname -r); uptime $(awk '{printf "%.1f h", $1 / 3600}' /proc/uptime); plasmashell $(pgrep -cx plasmashell)"
      echo "vram total $(cat /sys/class/drm/card*/device/mem_info_vram_total 2> /dev/null | head -1), used $(cat /sys/class/drm/card*/device/mem_info_vram_used 2> /dev/null | head -1); gtt used $(cat /sys/class/drm/card*/device/mem_info_gtt_used 2> /dev/null | head -1)"
    } > "$R/case-$N.out"
    sync
    distrobox enter ubuntu -- "$E1/e1-probe" --submit --case "$N" < /dev/null >> "$R/case-$N.out" 2>&1
    RC=$?
    echo "exit code $RC at $(date '+%T')" >> "$R/case-$N.out"
    sync
    sleep 20
    sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" > "$R/case-$N.dmesg"
    cat "$R/case-$N.out"
    echo "--- kernel lines since the start of the case: $(wc -l < "$R/case-$N.dmesg") ($(grep -ci amdgpu "$R/case-$N.dmesg") amdgpu)"
    cut -c1-240 "$R/case-$N.dmesg" | head -60 ;;
  *) echo "usage: e1run.sh build | case N"; exit 1 ;;
esac
