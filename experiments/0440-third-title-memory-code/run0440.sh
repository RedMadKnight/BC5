#!/usr/bin/env bash
# Experiment 0440: one run of the third title (TITLE3) to its stall, paused and dumped (memdump0440.py).
# Runs on the BC-250 host from ~/bc5-work/exp0440/ (a copy of this file). Shape: exp 0439's run0439.sh.
#
#   run0440.sh prep                copy exp 0439's private build, launcher and settings file here (pinned by md5)
#   run0440.sh dry                 the chain to the emulator's exec with a stub in the binary's place (LESSONS R66)
#   run0440.sh standin             the dumper against a stand-in process in the container (no GPU, no lock)
#   run0440.sh go <tag> [wait_s]   the run: a systemd --user unit (R65) that takes BOX-LOCK, starts the title bounded
#                                  inside the container (R68), waits wait_s (12) after the emulator appears, runs the
#                                  dumper (SIGSTOP .. SIGCONT), ends the emulator, collects, checks for leftovers and
#                                  a dead mount (R70) and drops the lock. Blocks until the unit ends; prints its log.
#
# Private output (the title's code and data): ~/bc5-data/priv/t3-memdump/<tag>/ (mode 700). Logs: $E/runs/<tag>/.
set -euo pipefail
umask 077
E=$HOME/bc5-work/exp0440
SRC=$HOME/bc5-work/exp0439
DIR=$HOME/bc5-data/games/TITLE3
LOCK=$HOME/bc5-work/BOX-LOCK
PRIV=$HOME/bc5-data/priv/t3-memdump
BIN=$E/bin/kyty_emulator
LAUNCH=$E/play440.sh
ENVF=$E/run-log.env
BIN_MD5=${BIN_MD5:-a29080a66641b831262f69af0ccf3c44}
CAP=900  # timeout(1) inside the container: far beyond the dump, so it never fires on a stopped process
WORDS=("BC5_SYSMODULES_PACK_DIR=$DIR/fakelib" BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 "BC5_RUN_ENV=$ENVF")

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
# A mount that is a mountpoint but whose param.json cannot be read is dead (R70); report only, inside the container.
dead_mounts() {
  timeout 60 distrobox enter ubuntu -- bash -c 'n=0; for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "DEAD MOUNT $d"; n=1; fi; done; echo "dead-mount check done ($n)"' < /dev/null 2>&1 | tail -n 3
}
wl() { local w; w=$(ls -1 "/run/user/$(id -u)/" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || true); echo "${w:-wayland-0}"; }

case "${1:-}" in
prep)
  pgrep -x kyty_emulator >/dev/null && die "an emulator is running"
  mkdir -p "$E/bin" "$E/runs" "$PRIV"; chmod 700 "$PRIV"
  cp "$SRC/k439/normal/kyty_emulator" "$BIN"; cp "$SRC/k439/play439.sh" "$LAUNCH"; cp "$SRC/run-log.env" "$ENVF"
  chmod 755 "$BIN" "$LAUNCH"
  md5sum "$BIN" "$LAUNCH" "$ENVF"
  [ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$BIN_MD5" ] || die "the copied binary is not $BIN_MD5"
  printf '#!/bin/sh\necho "STUB EXEC: $0 $*"\nenv | grep -E "^(BC5_|KYTY_|SHADPS4_|PLAY_|WAYLAND_DISPLAY)" | sort\nexit 0\n' > "$E/stub-emu.sh"; chmod 755 "$E/stub-emu.sh"
  ;;
dry)
  pgrep -x kyty_emulator >/dev/null && die "an emulator is running"
  echo "binary: $BIN $(md5sum < "$BIN" | cut -c1-8) $(stat -c '%y' "$BIN" | cut -c1-19); launcher $(md5sum < "$LAUNCH" | cut -c1-8)"
  echo "launcher EMU lines:"; grep -n -E '^ *EMU=' "$LAUNCH"
  echo "chain with the stub in the binary's place:"
  ( ulimit -c 0; timeout 120 distrobox enter ubuntu -- bash -c 'ulimit -c 0; exec timeout -k 15 60 env "$@"' _ \
      BC5_GAME_DIR="$DIR" P439_BIN="$E/stub-emu.sh" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=0 WAYLAND_DISPLAY="$(wl)" "${WORDS[@]}" "$LAUNCH" "$DIR" ) < /dev/null 2>&1 | tail -n 5
  echo "the stub's lines in the launcher's log:"; grep -E '^STUB EXEC|^BC5_DIRECT_(DCC|EAGER_GPU)|^SHADPS4_SYSMODULES|^BC5_GAME_DIR|^== .* exit' "$HOME/bc5-work/play-last.log" || true
  dead_mounts
  ;;
standin)
  out=$E/standin-out; rm -rf "$out"; mkdir -p "$out"
  ( timeout 120 distrobox enter ubuntu -- python3 "$E/standin0440.py" "$out/pid" ) < /dev/null > "$out/standin.txt" 2>&1 &
  for _ in $(seq 1 40); do [ -s "$out/pid" ] && break; sleep 0.5; done
  [ -s "$out/pid" ] || { cat "$out/standin.txt"; die "no stand-in"; }
  read -r pid addr mfd < "$out/pid"
  echo "stand-in pid $pid, big mapping at $addr; memfd blocks before the dump: $(stat -L -c %b "/proc/$pid/fd/$mfd")"
  timeout -k 5 100 python3 "$E/memdump0440.py" run "$pid" "$out/dump" --gap 2 --big-mb 64 --extra "$addr:0x10000" || echo "dumper rc $?"
  echo "memfd blocks after the dump: $(stat -L -c %b "/proc/$pid/fd/$mfd") (equal = the dump allocated nothing in it)"
  kill -TERM "$pid" 2>/dev/null || true
  python3 "$E/standin0440.py" --check "$out/dump" "$addr"
  ;;
go)
  tag=${2:?tag}; waits=${3:-12}
  [ -e "$PRIV/$tag" ] && die "dump directory $PRIV/$tag exists: pick a new tag"
  mkdir -p "$E/runs/$tag"
  systemd-run --user --collect --wait --quiet --unit="bc5-0440-$tag" -p RuntimeMaxSec=1500 \
    --setenv=WAYLAND_DISPLAY="$(wl)" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash "$E/run0440.sh" go-inner "$tag" "$waits" || echo "unit ended with rc $?"
  cat "$E/runs/$tag/go.log"
  ;;
go-inner)
  tag=$2; waits=$3; out=$E/runs/$tag; dump=$PRIV/$tag
  exec >> "$out/go.log" 2>&1
  [ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$BIN_MD5" ] || die "the binary is not $BIN_MD5"
  take_lock "third title memdump $tag"
  pid=""; LP=""; start=$(date '+%F %T')
  finish() {
    set +e
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill -CONT "$pid"; sleep 1; kill -TERM "$pid"
      for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
      if kill -0 "$pid" 2>/dev/null; then log "TERM was not enough: KILL"; kill -KILL "$pid"; sleep 2; fi
    fi
    if [ -n "$LP" ]; then for _ in $(seq 1 60); do kill -0 "$LP" 2>/dev/null || break; sleep 0.5; done; kill -0 "$LP" 2>/dev/null && log "the launcher shell $LP is still there"; fi
    cp -p "$HOME/bc5-work/play-last.log" "$out/" 2>/dev/null
    [ -d "$dump" ] && cp -p "$HOME/bc5-work/play-last.log" "$dump/" 2>/dev/null
    log "capture: $(cat "$HOME/bc5-work/last-play-capture" 2>/dev/null)"
    log "amdgpu timeout/reset lines after: $(resets)"
    journalctl -k -b 0 --no-pager -S "$start" > "$out/kernel.txt" 2>&1
    log "kernel lines since the start: $(wc -l < "$out/kernel.txt")"
    log "leftovers: emulators [$(pgrep -x kyty_emulator | tr '\n' ' ')] bc5-mount [$(pgrep -x bc5-mount | tr '\n' ' ')]"
    dead_mounts
    log "last log line: $(tail -n 1 "$out/play-last.log" 2>/dev/null | cut -c1-200)"
    drop_lock
  }
  trap finish EXIT
  log "tag $tag binary $BIN $BIN_MD5 kernel $(uname -r) boot $(journalctl --list-boots --no-pager 2>/dev/null | tail -n1 | awk '{print $2}')"
  log "amdgpu timeout/reset lines before: $(resets); words: ${WORDS[*]}"
  dead_mounts
  free -m | sed -n 2p
  ( ulimit -c 0; exec distrobox enter ubuntu -- bash -c 'ulimit -c 0; exec timeout -k 15 "$0" env "$@"' "$CAP" \
      BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=1 WAYLAND_DISPLAY="$WAYLAND_DISPLAY" "${WORDS[@]}" "$LAUNCH" "$DIR" ) > "$out/launch.txt" 2>&1 < /dev/null &
  LP=$!
  for _ in $(seq 1 120); do pid=$(pgrep -x kyty_emulator | head -n1 || true); [ -n "$pid" ] && break; sleep 0.5; done
  [ -n "$pid" ] || { cat "$out/launch.txt"; die "no emulator after 60 s"; }
  log "emulator pid $pid; $(grep 'Max core file size' "/proc/$pid/limits" | tr -s ' ')"
  sleep "$waits"
  kill -0 "$pid" 2>/dev/null || die "the emulator ended before the dump"
  log "threads: $(ls "/proc/$pid/task" | wc -l); starting the dumper"
  rc=0
  # mappings up to 1 GiB (the 620 MiB views with the label table, rings and command buffers; not the 4 GB view);
  # the extras only matter if the rules left them out: the label table's first 64 KiB and the five modules' ranges
  timeout -k 10 700 python3 "$E/memdump0440.py" run "$pid" "$dump" --gap 5 --cap-gb 8 --big-mb 1024 \
    --extra 0x2000000000:0x10000 --extra 0x900000000:0x50000000 || rc=$?
  log "dumper rc $rc; dump size $(du -sh "$dump" 2>/dev/null | cut -f1) (apparent $(du -sh --apparent-size "$dump" 2>/dev/null | cut -f1))"
  ;;
*) sed -n '2,13p' "$0"; exit 2 ;;
esac
