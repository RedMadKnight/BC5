#!/usr/bin/env bash
# BC5 exp 0439 (tag ib439): BC5_DIRECT_IB_CHAIN smokes (the top session's order, 11-21 ~16:45). Private normal build with
# the chain rule (pinned by the first argument, md5's first 8): the first title 60 s with the switch off and on (does the first title
# chain at all: chain submits, longest chain, IBs NOP-ed, refusals), then the third title 30 s and 120 s with it on
# (flips, labels and the queue table at 20 s of the 30-s run). Usual settings for the third title (mode 2 present, map
# rule; the ident switch off). One box-side wait for an empty lock, the lock held for the series; resets and fault
# records before and after each run; the series stops on a new reset line or fault record; dead mounts cleaned.
#   ib29.sh <md5-8>
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
PIN=${1:?md5 of the private normal}
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || { echo "the binary is not $PIN"; exit 1; }
grep -aq BC5_DIRECT_IB_CHAIN "$BIN" || { echo "no BC5_DIRECT_IB_CHAIN in the binary"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep "^kyty_emulator" > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
unlock() { bash e0439.sh unlock 2>&1 | tail -1; }
bash "$HOME/bc5-work/exp0439/k439/r72check.sh" || echo "  (LESSONS R72: a diagnosis series, recorded; its frame numbers do not describe normal play)"
resets() { journalctl -k -b 0 --no-pager 2> /dev/null | grep -c -i -E 'amdgpu.*(timeout|reset)' || true; }
faults() { ls "$HOME/bc5-data/captures/faults" 2> /dev/null | wc -l; }
wl=$(ls -1 "/run/user/$(id -u)/" | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
dead_mounts() {
  for where in container host; do
    if [ $where = container ]; then run_in() { distrobox enter ubuntu -- bash -c "$1"; }; else run_in() { bash -c "$1"; }; fi
    run_in 'for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "dead mount $d: unmounted"; fusermount3 -u "$d" 2>&1 || fusermount3 -u -z "$d" 2>&1; fi; done' 2>&1 | sed "s/^/$where: /"
  done
}
ibsum() { # $1 log
  echo "  ib439: chain submits $(grep -a -c 'tag ib439): submit #.* with chains' "$1"), last: $(grep -a 'tag ib439): submit #.* with chains' "$1" | tail -1 | sed 's/.*with chains: //')"
  echo "  ib439: submits with IBs NOP-ed $(grep -a -c 'tag ib439): submit of .* NOP-ed' "$1"), last: $(grep -a 'tag ib439): submit of .* NOP-ed' "$1" | tail -1 | sed 's/.*dwords at [0-9a-fx]*: //')"
  echo "  ib439: refusals $(grep -a -c 'tag ib439): submit of .* refused' "$1"), soft CP budget stops $(grep -a -c 'tag ib439): soft CP' "$1"); unmapped drops in the summary: $(grep -a -o 'unmapped[_ a-z]*[0-9]\+' "$1" | tail -1)"
  grep -a 'tag ib439)' "$1" | head -3 | cut -c1-240 | sed 's/^/  first: /'
}
t1() { # $1 tag, $2 switch value
  local O=runs/ib29-$1 r0 r1 f0 f1; rm -rf "$O"; mkdir -p "$O"; r0=$(resets); f0=$(faults); : > "$HOME/bc5-work/play-last.log"
  systemd-run --user --collect --unit="bc5-0439-ib29-$1" -p RuntimeMaxSec=95 --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; exec distrobox enter ubuntu -- timeout -k 15 60 env BC5_LOGS=1 BC5_LEAN=0 P439_BIN="$1" BC5_DIRECT_IB_CHAIN="$2" WAYLAND_DISPLAY="$3" "$4"' \
    _ "$BIN" "$2" "$wl" "$HOME/bc5-work/exp0439/k439/play439.sh" > /dev/null 2>&1
  sleep 5; for k in $(seq 1 24); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
  pgrep "^kyty_emulator" > /dev/null && { echo "$1: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
  cp ~/bc5-work/play-last.log "$O/"; dead_mounts > "$O/mounts.txt"
  r1=$(resets); f1=$(faults)
  echo "== the first title $1 (BC5_DIRECT_IB_CHAIN=$2): resets $r0 -> $r1, fault records $f0 -> $f1; flips $(grep -a 'tag fc439' "$O/play-last.log" | tail -1 | sed -E 's/.*t ([0-9.]+) s flip ([0-9]+).*/\2 by \1 s/'); exit $(grep -a '== .* exit' "$O/play-last.log" | tail -1 | sed 's/.* exit //')"
  ibsum "$O/play-last.log"; cat "$O/mounts.txt"
  [ "$r0" = "$r1" ] && [ "$f0" = "$f1" ]
}
t3() { # $1 tag, $2 seconds, $3 queue-table time or 0
  local O=runs/ib29-$1 P; rm -rf "$O"; : > "$HOME/bc5-work/play-last.log"
  RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/TITLE3/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1" bash run0439.sh run normal "ib29-$1" "$2" 2>&1 | tail -1
  if [ "$3" != 0 ]; then
    for k in $(seq 1 30); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
    P=$(pgrep "^kyty_emulator" | head -1); sleep "$3"
    [ -n "$P" ] && kill -0 "$P" 2> /dev/null && python3 -I "$HOME/bc5-work/exp0439/k439/qtab.py" "$P" "$HOME/bc5-work/play-last.log" "$1 t $3 s" > "runs/ib29-$1.q" 2>&1
  fi
  sleep 5; for k in $(seq 1 $(( $2 / 5 + 10 ))); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
  pgrep "^kyty_emulator" > /dev/null && { echo "$1: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
  RUN_PRIV=$BIN bash run0439.sh collect normal "ib29-$1" > /dev/null 2>&1
  [ -f "runs/ib29-$1.q" ] && mv "runs/ib29-$1.q" "$O/qtab.txt"
  local PL=$O/play-last.log
  echo "== third title $1 ($2 s, BC5_DIRECT_IB_CHAIN=1): $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); flips $(grep -a -c 'tag dc439): t .* flip:' $PL), last flip line: $(grep -a 'tag dc439): t .* flip:' $PL | tail -1 | cut -c1-120); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
  ibsum "$PL"
  [ -f "$O/qtab.txt" ] && grep -a -E '^==|^labels|DIFFER' "$O/qtab.txt" | cut -c1-300
  grep -a -c 'deferred' $PL | sed 's/^/  queue deferral lines: /'
  grep -a -E 'GPU fault|page fault|exit 86' $PL | head -3
  dead_mounts
  grep -q "after: $(grep before $O/meta.txt | sed 's/.*before: //')" $O/meta.txt
}
# ON first (16:49 and 16:56 the ON run after OFF failed at the start: param.json unreadable), then OFF
t1 on 1 || { echo "the first title on: a reset or fault: the series stops"; unlock; exit 1; }
for k in $(seq 1 30); do pgrep -x bc5-mount > /dev/null || break; sleep 1; done; sleep 3
t1 off 0 || { echo "the first title off: a reset or fault: the series stops"; unlock; exit 1; }
t3 t30 30 20 || { echo "third title 30 s: a reset, a fault or no meta: the series stops"; unlock; exit 1; }
t3 t120 120 0
unlock
