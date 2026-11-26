#!/usr/bin/env bash
# BC5 exp 0439 (tag ae439): BC5_DIRECT_AGC_EOP_IDENT smokes (the top session, 11-21 ~16:10): the first title 60 s with the
# switch off and on (normal build, diagnosis only), then the third title 30 s with it on. Private normal 2befcb17
# (patch 0fede35d's tree). One box-side wait for an empty lock; reset lines and fault records before and after each;
# the series stops on a new fault record or reset line. After each first-title run a dead FUSE mount is unmounted (container
# and host). Output under runs/ae27-*.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator
[ "$(md5sum < "$BIN" | cut -c1-8)" = 2befcb17 ] || { echo "the binary is not 2befcb17"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep "^kyty_emulator" > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
resets() { journalctl -k -b 0 --no-pager 2> /dev/null | grep -c -i -E 'amdgpu.*(timeout|reset)' || true; }
faults() { ls "$HOME/bc5-data/captures/faults" 2> /dev/null | wc -l; }
wl=$(ls -1 "/run/user/$(id -u)/" | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
dead_mounts() {
  for where in container host; do
    if [ $where = container ]; then run_in() { distrobox enter ubuntu -- bash -c "$1"; }; else run_in() { bash -c "$1"; }; fi
    run_in 'for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "dead mount $d: unmounted"; fusermount3 -u "$d" 2>&1 || fusermount3 -u -z "$d" 2>&1; fi; done' 2>&1 | sed "s/^/$where: /"
  done
}
t1() { # $1 tag, $2 switch value
  local O=runs/ae27-$1 r0 r1 f0 f1; mkdir -p "$O"; r0=$(resets); f0=$(faults)
  systemd-run --user --collect --unit="bc5-0439-ae27-$1" -p RuntimeMaxSec=95 --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; exec distrobox enter ubuntu -- timeout -k 15 60 env BC5_LOGS=1 BC5_LEAN=0 P439_BIN="$1" BC5_DIRECT_AGC_EOP_IDENT="$2" WAYLAND_DISPLAY="$3" "$4"' \
    _ "$BIN" "$2" "$wl" "$HOME/bc5-work/exp0439/k439/play439.sh" > /dev/null 2>&1
  sleep 5; for k in $(seq 1 24); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
  pgrep "^kyty_emulator" > /dev/null && { echo "$1: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
  cp ~/bc5-work/play-last.log "$O/"; dead_mounts > "$O/mounts.txt"
  r1=$(resets); f1=$(faults)
  echo "== the first title $1 (BC5_DIRECT_AGC_EOP_IDENT=$2): resets $r0 -> $r1, fault records $f0 -> $f1; flips $(grep -a 'tag fc439' "$O/play-last.log" | tail -1 | sed -E 's/.*t ([0-9.]+) s flip ([0-9]+).*/\2 by \1 s/'); ae439 lines $(grep -a -c 'tag ae439): t' "$O/play-last.log"); exit $(grep -a '== .* exit' "$O/play-last.log" | tail -1 | sed 's/.* exit //')"
  grep -a 'tag ae439): t' "$O/play-last.log" | sed -E 's/.* (RELEASE_MEM|EVENT_WRITE_EOP) INT_SEL ([0-9]) on ([a-z ]+) \(slot (0x[0-9a-f]+)\): ident (0x[0-9a-f]+) data (0x[0-9a-f]+) to ([0-9]+).*/\1 int \2 \3 slot \4 ident \5 regs \7/' | sort | uniq -c | head -8
  cat "$O/mounts.txt"
  [ "$r0" = "$r1" ] && [ "$f0" = "$f1" ]
}
t1 off 0 || { echo "the first title off: a reset or fault: the series stops"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
t1 on 1 || { echo "the first title on: a reset or fault: the series stops"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
O=runs/ae27-t3; rm -rf "$O"
RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/TITLE3/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_AGC_EOP_IDENT=1" bash run0439.sh run normal ae27-t3 30 2>&1 | tail -1
sleep 5; for k in $(seq 1 20); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
RUN_PRIV=$BIN bash run0439.sh collect normal ae27-t3 > /dev/null 2>&1
PL=$O/play-last.log
echo "== third title (on): $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); flips $(grep -a -c 'tag dc439): t .* flip:' $PL); ae439 lines $(grep -a -c 'tag ae439): t' $PL)"
grep -a 'tag ae439): t' $PL | head -4 | cut -c1-200
bash e0439.sh unlock 2>&1 | tail -1
