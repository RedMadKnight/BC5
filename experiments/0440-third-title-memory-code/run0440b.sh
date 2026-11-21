#!/usr/bin/env bash
# Experiment 0440, second paused dump: one run of the third title (PPSA26344) into its stall, paused and dumped
# (memdump0440.py). Runs on the BC-250 host from ~/bc5-work/exp0440/ (a copy of this file). As run0440.sh, with:
#   - the build, launcher and settings file named at `prep` and pinned by md5 in $E/kit-b.env;
#   - the emulator's pid taken only from this run: a process whose /proc/<pid>/exe is this kit's own private
#     binary, looked for only after this script holds BOX-LOCK (LESSONS R71), never the first kyty_emulator seen;
#   - everything that starts something in ONE named unit, bc5-0440-<tag>, with its own time limit (R73); the ssh
#     that calls `go` only waits for that unit and prints its log; stop = systemctl --user stop bc5-0440-<tag>;
#   - the registered display buffers and their DCC metadata added to the dump as extra ranges, taken from the
#     run's own log ("flip: index N surface 0x.. meta 0x.. WxH") and from EXTRA="addr:len ...".
#
#   run0440b.sh prep <binary> <md5> [launcher] [settings-file]   private copies under $E/kit-b/, md5 checked
#   run0440b.sh dry                                               the chain to the exec with a stub binary (R66)
#   run0440b.sh go <tag> [wait_s]                                 the run; RUN_WORDS="NAME=value ..." in the
#                                                                 environment are the per-run words (required);
#                                                                 EXTRA and BIG_MB (default 1024) are optional
# Private output: ~/bc5-data/priv/yotei-memdump/<tag>/ (mode 700). Logs: $E/runs/<tag>/.
set -euo pipefail
umask 077
E=$HOME/bc5-work/exp0440
K=$E/kit-b
DIR=$HOME/bc5-data/games/PPSA26344
LOCK=$HOME/bc5-work/BOX-LOCK
PRIV=$HOME/bc5-data/priv/yotei-memdump
BIN=$K/kyty_emulator
LAUNCH=$K/play440b.sh
ENVF=$K/run.env
CAP=900  # timeout(1) inside the container: far beyond the dump, so it never fires on a stopped process

log() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
die() { log "STOP: $*"; exit 1; }
resets() { journalctl -k -b 0 --no-pager 2>/dev/null | grep -c -i -E 'amdgpu.*(timeout|reset)' || true; }
our_lock() { [ -e "$LOCK" ] && grep -q '^exp0440 ' "$LOCK" 2>/dev/null; }
take_lock() {
  exec 9>> "$LOCK.flock"; flock -n 9 || die "lock busy"
  if [ -s "$LOCK" ]; then die "BOX-LOCK is held: $(cat "$LOCK")"; fi
  pgrep -x kyty_emulator >/dev/null && die "an emulator runs without a lock: he plays"
  printf 'exp0440 %s %s\n' "$(date '+%F %T')" "$1" > "$LOCK"; flock -u 9; log "lock taken: $(cat "$LOCK")"
}
drop_lock() { exec 9>> "$LOCK.flock"; flock 9; if our_lock; then : > "$LOCK"; log "lock dropped"; fi; flock -u 9; }
dead_mounts() {
  timeout 60 distrobox enter ubuntu -- bash -c 'n=0; for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "DEAD MOUNT $d"; n=1; fi; done; echo "dead-mount check done ($n)"' < /dev/null 2>&1 | tail -n 3
}
wl() { local w; w=$(ls -1 "/run/user/$(id -u)/" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || true); echo "${w:-wayland-0}"; }
words() {  # RUN_WORDS -> the array W, each word checked
  read -r -a W <<< "${RUN_WORDS:-}"
  [ "${#W[@]}" -gt 0 ] || die "RUN_WORDS is empty: the per-run words are required"
  local w; for w in "${W[@]}"; do [[ $w =~ ^[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_.,:/+-]*$ ]] || die "bad word: $w"; done
}
# The emulator of THIS run: its exe is this kit's private binary (R71). Prints the pid or nothing.
own_pid() {
  local p
  for p in $(pgrep -x kyty_emulator || true); do
    if [ "$(readlink "/proc/$p/exe" 2>/dev/null)" = "$BIN" ]; then echo "$p"; return 0; fi
  done
  return 0
}

case "${1:-}" in
prep)
  src=${2:?binary}; md5=${3:?md5}; lsrc=${4:-$HOME/bc5-work/exp0439/k439/play439.sh}; esrc=${5:-$HOME/bc5-work/exp0439/run-log.env}
  mkdir -p "$K" "$E/runs" "$PRIV"; chmod 700 "$PRIV"
  cp "$src" "$BIN"; cp "$lsrc" "$LAUNCH"; cp "$esrc" "$ENVF"; chmod 755 "$BIN" "$LAUNCH"
  [ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$md5" ] || die "the copied binary is not $md5"
  printf 'BIN_MD5=%s\nLAUNCH_MD5=%s\nENV_MD5=%s\nSRC=%s\n' "$md5" "$(md5sum < "$LAUNCH" | cut -d' ' -f1)" "$(md5sum < "$ENVF" | cut -d' ' -f1)" "$src" > "$E/kit-b.env"
  printf '#!/bin/sh\necho "STUB EXEC: $0 $*"\nenv | grep -E "^(BC5_|KYTY_|SHADPS4_|PLAY_|WAYLAND_DISPLAY)" | sort\nexit 0\n' > "$K/stub-emu.sh"; chmod 755 "$K/stub-emu.sh"
  cat "$E/kit-b.env"
  ;;
dry)
  words
  # shellcheck disable=SC1091
  . "$E/kit-b.env"
  pgrep -x kyty_emulator >/dev/null && die "an emulator is running"
  echo "binary: $BIN $(md5sum < "$BIN" | cut -c1-8) (pinned ${BIN_MD5:0:8}); launcher $(md5sum < "$LAUNCH" | cut -c1-8); settings $(md5sum < "$ENVF" | cut -c1-8)"
  echo "launcher EMU lines:"; grep -n -E '^ *EMU=' "$LAUNCH"
  ( ulimit -c 0; timeout 120 distrobox enter ubuntu -- bash -c 'ulimit -c 0; exec timeout -k 15 60 env "$@"' _ \
      BC5_GAME_DIR="$DIR" P439_BIN="$K/stub-emu.sh" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=0 WAYLAND_DISPLAY="$(wl)" BC5_RUN_ENV="$ENVF" "${W[@]}" "$LAUNCH" "$DIR" ) < /dev/null 2>&1 | tail -n 5
  echo "the stub's lines in the launcher's log:"; grep -E '^STUB EXEC|^BC5_DIRECT_|^BC5_0439|^SHADPS4_SYSMODULES|^BC5_GAME_DIR|^== .* exit' "$HOME/bc5-work/play-last.log" || true
  dead_mounts
  ;;
go)
  tag=${2:?tag}; waits=${3:-30}
  words
  [ -e "$PRIV/$tag" ] && die "dump directory $PRIV/$tag exists: pick a new tag"
  mkdir -p "$E/runs/$tag"
  systemd-run --user --collect --wait --quiet --unit="bc5-0440-$tag" -p RuntimeMaxSec=1500 \
    --setenv=WAYLAND_DISPLAY="$(wl)" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    --setenv=RUN_WORDS="$RUN_WORDS" --setenv=EXTRA="${EXTRA:-}" --setenv=BIG_MB="${BIG_MB:-1024}" \
    /usr/bin/bash "$E/run0440b.sh" go-inner "$tag" "$waits" || echo "unit ended with rc $?"
  cat "$E/runs/$tag/go.log"
  ;;
go-inner)
  tag=$2; waits=$3; out=$E/runs/$tag; dump=$PRIV/$tag
  exec >> "$out/go.log" 2>&1
  words
  # shellcheck disable=SC1091
  . "$E/kit-b.env"
  [ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$BIN_MD5" ] || die "the binary is not $BIN_MD5"
  take_lock "third title memdump $tag"
  pid=""; LP=""; start=$(date '+%F %T')
  finish() {
    set +e
    if [ -n "$pid" ] && [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$BIN" ]; then
      kill -CONT "$pid"; sleep 1; kill -TERM "$pid"
      for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
      if kill -0 "$pid" 2>/dev/null; then log "TERM was not enough: KILL"; kill -KILL "$pid"; sleep 2; fi
    fi
    if [ -n "$LP" ]; then for _ in $(seq 1 60); do kill -0 "$LP" 2>/dev/null || break; sleep 0.5; done; kill -0 "$LP" 2>/dev/null && log "the launcher shell $LP is still there"; fi
    cp -p "$HOME/bc5-work/play-last.log" "$out/" 2>/dev/null
    [ -d "$dump" ] && cp -p "$HOME/bc5-work/play-last.log" "$dump/" 2>/dev/null
    cap=$(cat "$HOME/bc5-work/last-play-capture" 2>/dev/null); log "capture: $cap"
    [ -d "$dump" ] && [ -f "$cap/gc/direct.log" ] && cp -p "$cap/gc/direct.log" "$dump/" 2>/dev/null
    log "amdgpu timeout/reset lines after: $(resets)"
    journalctl -k -b 0 --no-pager -S "$start" > "$out/kernel.txt" 2>&1
    log "kernel lines since the start: $(wc -l < "$out/kernel.txt")"
    log "leftovers: own emulator [$(own_pid)] any emulator [$(pgrep -x kyty_emulator | tr '\n' ' ')] bc5-mount [$(pgrep -x bc5-mount | tr '\n' ' ')]"
    dead_mounts
    log "last log line: $(tail -n 1 "$out/play-last.log" 2>/dev/null | cut -c1-200)"
    drop_lock
  }
  trap finish EXIT
  log "tag $tag binary $BIN $BIN_MD5 kernel $(uname -r) boot $(journalctl --list-boots --no-pager 2>/dev/null | tail -n1 | awk '{print $2}')"
  log "amdgpu timeout/reset lines before: $(resets); words: ${W[*]}"
  log "display: edid bytes $(wc -c < /sys/class/drm/card1-DP-1/edid 2>/dev/null), first mode $(head -n1 /sys/class/drm/card1-DP-1/modes 2>/dev/null)"
  dead_mounts
  free -m | sed -n 2p
  ( ulimit -c 0; exec distrobox enter ubuntu -- bash -c 'ulimit -c 0; exec timeout -k 15 "$0" env "$@"' "$CAP" \
      BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=1 WAYLAND_DISPLAY="$WAYLAND_DISPLAY" BC5_RUN_ENV="$ENVF" "${W[@]}" "$LAUNCH" "$DIR" ) > "$out/launch.txt" 2>&1 < /dev/null &
  LP=$!
  for _ in $(seq 1 120); do pid=$(own_pid); [ -n "$pid" ] && break; sleep 0.5; done
  [ -n "$pid" ] || { cat "$out/launch.txt"; die "no emulator of this kit after 60 s"; }
  log "emulator pid $pid (exe $(readlink "/proc/$pid/exe")); $(grep 'Max core file size' "/proc/$pid/limits" | tr -s ' ')"
  sleep "$waits"
  [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$BIN" ] || die "the emulator ended before the dump"
  # the display buffers this run flipped, from its own log: the surface (40 MiB from its base) and 1.25 MiB around its
  # DCC metadata; plus EXTRA; plus the label table's head and the modules (only if the size rule left them out)
  ex=()
  while read -r s m; do
    [ -n "$s" ] || continue
    ex+=(--extra "$s:0x2800000" --extra "$(printf '0x%x' $((m - 0x40000))):0x140000")
  done < <(sed 's/\x1b\[[0-9;]*m//g' "$HOME/bc5-work/play-last.log" | sed -n 's/.*flip: index [0-9]* surface \(0x[0-9a-f]*\) meta \(0x[0-9a-f]*\) .*/\1 \2/p' | sort -u | head -n 8)
  for r in ${EXTRA:-}; do [[ $r =~ ^0x[0-9a-fA-F]+:0x[0-9a-fA-F]+$ ]] && ex+=(--extra "$r"); done
  log "threads: $(ls "/proc/$pid/task" | wc -l); flips in the log: $(grep -c 'flip: index' "$HOME/bc5-work/play-last.log" || true); extra ranges: ${ex[*]:-none}"
  rc=0
  timeout -k 10 700 python3 "$E/memdump0440.py" run "$pid" "$dump" --gap 5 --cap-gb 8 --big-mb "${BIG_MB:-1024}" \
    --extra 0x2000000000:0x10000 --extra 0x900000000:0x50000000 "${ex[@]}" || rc=$?
  log "dumper rc $rc; dump size $(du -sh "$dump" 2>/dev/null | cut -f1) (apparent $(du -sh --apparent-size "$dump" 2>/dev/null | cut -f1))"
  ;;
*) sed -n '2,19p' "$0"; exit 2 ;;
esac
