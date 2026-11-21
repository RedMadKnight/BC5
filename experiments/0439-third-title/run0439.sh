#!/usr/bin/env bash
# Experiment 0439: one bounded first run of the third title (PPSA26344) from its installed folder on the SHARED
# builds, through the shared play-any.sh -> play-astro.sh chain (no launcher change), RT on (the default; refused
# if the settings file turns it off), ulimit -c 0, started in a systemd --user unit (F860, LESSONS R65).
#
#   run0439.sh dry  normal|lean          print the chain and the binary it reaches (R66), run nothing
#   run0439.sh run  normal|lean <tag> [seconds]
#                                        the run (default 600 s; RuntimeMaxSec ends it: our own bound, not a fix),
#                                        logs copied to ~/bc5-work/exp0439/runs/<tag>/ when it ends
#
# The kernel log is streamed separately (klog0439.sh). Needs BOX-LOCK "exp0439 ..." (e0439.sh lock).
set -euo pipefail
E=$HOME/bc5-work/exp0439
DIR=$HOME/bc5-data/games/PPSA26344
LOCK=$HOME/bc5-work/BOX-LOCK
mode=${2:-}; [ "$mode" = normal ] || [ "$mode" = lean ] || { sed -n '2,12p' "$0"; exit 2; }
lean=0; [ "$mode" = lean ] && lean=1
# GPU timeouts and resets of this boot (written before and after every run, the top session's rule of 11-21)
resets() { journalctl -k -b 0 --no-pager 2>/dev/null | grep -c -i -E 'amdgpu.*(timeout|reset)' || true; }
if [ $lean = 1 ]; then BIN=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator LOGF=$HOME/bc5-work/play-lean-last.log
else BIN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator LOGF=$HOME/bc5-work/play-last.log; fi
grep -q '^KYTY_BC5_RT=0' "$HOME/bc5-work/bc5-run.env" && { echo "bc5-run.env turns RT off: refused"; exit 1; }

case "$1" in
dry)
  echo "chain: distrobox enter ubuntu -- env BC5_LEAN=$lean ~/bc5-work/play-any.sh $DIR"
  distrobox enter ubuntu -- env BC5_DRY=1 BC5_LEAN=$lean "$HOME/bc5-work/play-any.sh" "$DIR" 2>&1 | grep -v 'lean-session' || true
  echo "play-astro.sh EMU lines:"; grep -n -E '^ *EMU=|BC5_EMU' "$HOME/bc5-work/play-astro.sh"
  echo "binary: $BIN $(md5sum "$BIN" | cut -c1-8) $(stat -c '%y' "$BIN" | cut -c1-19)"
  echo "title id of the folder: $(sed -n 's/.*"titleId" *: *"\([A-Za-z0-9]*\)".*/\1/p' "$DIR/sce_sys/param.json" | head -n1)"
  ;;
run)
  tag=${3:?tag}; secs=${4:-600}; out=$E/runs/$tag
  grep -q '^exp0439 ' "$LOCK" 2>/dev/null || { echo "BOX-LOCK is not ours"; exit 1; }
  pgrep -f '[k]yty_emulator' >/dev/null && { echo "an emulator is running"; exit 1; }
  mkdir -p "$out"
  # RUN_EXTRA="NAME=value ..." : extra words in the emulator's environment for an env-only arm (no build), e.g. exp
  # 0438's malloc arm MALLOC_TRIM_THRESHOLD_=268435456 MALLOC_MMAP_THRESHOLD_=33554432 against a control without them.
  read -r -a extra <<< "${RUN_EXTRA:-}"
  for w in "${extra[@]}"; do [[ $w =~ ^[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_.,:/+-]*$ ]] || { echo "bad RUN_EXTRA word: $w"; exit 1; }; done
  wl=$(ls -1 "/run/user/$(id -u)/" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || true); wl=${wl:-wayland-0}
  {
    echo "tag $tag mode $mode secs $secs start $(date '+%F %T')"
    echo "binary $BIN $(md5sum "$BIN" | cut -d' ' -f1)"
    echo "kernel $(uname -r); WAYLAND_DISPLAY=$wl; extra: ${RUN_EXTRA:-none}"
    echo "boot $(journalctl --list-boots --no-pager 2>/dev/null | tail -n1 | awk '{print $2}'); amdgpu timeout/reset lines before: $(resets)"
    free -b || true; df -B1 /var 2>&1 | tail -n1 || true
  } > "$out/meta.txt"
  # PLAY_CAPTURE=1 (normal only): the direct-path journal under ~/bc5-data/captures/play-<date>/gc for diagnosis.
  cap=0; [ $lean = 0 ] && cap=1
  systemd-run --user --collect --unit="bc5-0439-$tag" -p RuntimeMaxSec="$secs" \
    --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; d=$1; shift; exec distrobox enter ubuntu -- env "$@" "$HOME/bc5-work/play-any.sh" "$d"' \
    _ "$DIR" BC5_LEAN="$lean" BC5_LOGS=1 PLAY_CAPTURE="$cap" WAYLAND_DISPLAY="$wl" "${extra[@]}"
  echo "started unit bc5-0439-$tag (max $secs s); when it ends: run0439.sh collect $mode $tag"
  ;;
collect)
  tag=${3:?tag}; out=$E/runs/$tag; mkdir -p "$out"
  journalctl --user -u "bc5-0439-$tag" --no-pager > "$out/unit.txt" 2>&1 || true
  cp -p "$LOGF" "$out/" 2>/dev/null || true
  cap=$(cat "$HOME/bc5-work/last-play-capture" 2>/dev/null || true); [ -n "$cap" ] && echo "capture $cap" >> "$out/meta.txt"
  ls -t "$HOME/bc5-data/captures/faults/" 2>/dev/null | head -n 3 > "$out/faults-latest.txt" || true
  ls -t "$HOME/bc5-data/captures/devcoredump/" 2>/dev/null | head -n 3 > "$out/devcd-latest.txt" || true
  echo "amdgpu timeout/reset lines after: $(resets)" >> "$out/meta.txt"
  journalctl -k -b 0 --no-pager -S "$(sed -n 's/.* start \(.*\)$/\1/p' "$out/meta.txt" | head -n1)" > "$out/kernel.txt" 2>&1 || true
  echo "end $(date '+%F %T')" >> "$out/meta.txt"; free -b >> "$out/meta.txt"
  tail -n 3 "$out/$(basename "$LOGF")" 2>/dev/null || true
  ;;
*) sed -n '2,12p' "$0"; exit 2 ;;
esac
