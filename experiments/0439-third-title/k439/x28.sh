#!/usr/bin/env bash
# BC5 exp 0439 (the top session, 11-21 ~16:20): cross-pack runs. The titles were dumped on different firmware, so each
# fakelib/ is the console's system modules of its dump day. The host LLE-loads every module of the one directory named by
# SHADPS4_SYSMODULES_PACK_DIR (KytyPlus runtimeLinker.cpp KytySysModulesPackDir / add_lle_dir) and keeps the rest on HLE,
# so a mixed pack is a directory of symlinks. The first title's pack has five modules (Agc, AgcDriver, Psml, Ampr, PlayGo); the
# third title's has three (its dump renamed Ampr and PlayGo to "... orig", so they stay HLE). To change only the graphics
# modules:
#   X1: the third title with the first title's Agc + AgcDriver + Psml (Ampr, PlayGo HLE as in its own runs), 30 s, the queue table
#       and labels at 20 s;
#   X2: the first title with the third title's Agc + AgcDriver + Psml and the first title's own Ampr + PlayGo, 60 s.
# Kyty's own log on (run-log.env: PLAY_ARGS=--printf-direction Console; without it no "Loading:" lines). Private normal
# 2befcb17, the usual settings (mode 2 present, map rule; BC5_DIRECT_AGC_EOP_IDENT off). The first title's modules
# are copied once into ~/bc5-data/packs/TITLE1/ (private data, mode 700). Each run is checked from its own log: the pack
# directory line and the five or three "Loading:" lines must name the intended files, else the series stops (the launcher
# proof of LESSONS R66 from the run itself). One box-side wait for an empty lock; resets and fault records before and
# after; dead mounts cleaned (container and host). Output under runs/x28-*.
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
unlock() { bash e0439.sh unlock 2>&1 | tail -1; }
bash "$HOME/bc5-work/exp0439/k439/r72check.sh" || echo "  (LESSONS R72: a diagnosis series, recorded; its frame numbers do not describe normal play)"
resets() { journalctl -k -b 0 --no-pager 2> /dev/null | grep -c -i -E 'amdgpu.*(timeout|reset)' || true; }
faults() { ls "$HOME/bc5-data/captures/faults" 2> /dev/null | wc -l; }
dead_mounts() {
  for where in container host; do
    if [ $where = container ]; then run_in() { distrobox enter ubuntu -- bash -c "$1"; }; else run_in() { bash -c "$1"; }; fi
    run_in 'for d in "$HOME"/bc5-data/mnt/* "$HOME"/bc5-work/exp0439/t1-ro; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "dead mount $d: unmounted"; fusermount3 -u "$d" 2>&1 || fusermount3 -u -z "$d" 2>&1; fi; done' 2>&1 | sed "s/^/$where: /"
  done
}
G=$HOME/bc5-data/games/TITLE3/fakelib; PK=$HOME/bc5-data/packs; A=$PK/TITLE1
mkdir -p "$A" && chmod 700 "$PK"
if [ "$(ls "$A" | wc -l)" != 5 ]; then
  distrobox enter ubuntu -- bash -c 'M=$HOME/bc5-work/exp0439/t1-ro; mkdir -p $M; $HOME/bc5-work/bc5-tools-ubuntu/release/bc5-mount mount "$HOME/bc5-data/games/TITLE1 - T1_4xx.ffpfsc" $M > /tmp/am.log 2>&1 & for i in $(seq 50); do [ -s $M/sce_sys/param.json ] && break; sleep 0.2; done; cp $M/fakelib/*.sprx "$1"/; fusermount3 -u $M' _ "$A"
  chmod 600 "$A"/*
fi
rm -rf "$PK/x1" "$PK/x2"; mkdir -p "$PK/x1" "$PK/x2"
for m in libSceAgc libSceAgcDriver libScePsml; do ln -s "$A/$m.sprx" "$PK/x1/$m.sprx"; ln -s "$G/$m.sprx" "$PK/x2/$m.sprx"; done
for m in libSceAmpr libScePlayGo; do ln -s "$A/$m.sprx" "$PK/x2/$m.sprx"; done
echo "== packs"; (cd "$PK" && for d in TITLE1 x1 x2; do for f in $d/*; do echo "$f -> $(readlink -f "$f" | sed "s|$HOME|~|") $(md5sum < "$f" | cut -c1-8) $(stat -L -c %s "$f")"; done; done)
for f in "$G"/*; do echo "TITLE3/$(basename "$f") $(md5sum < "$f" | cut -c1-8) $(stat -c %s "$f")"; done
loads() { grep -a -E 'LLE: sysmodule pack dir|^Loading: .*\.sprx' "$1" | sed -E "s#(/var)?$HOME#~#"; }

# X1: the third title with the first title's graphics modules.
O=runs/x28-x1; rm -rf "$O"; : > "$HOME/bc5-work/play-last.log"  # so the pack check reads this run's log only
RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$PK/x1 BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_RUN_ENV=$HOME/bc5-work/exp0439/run-log.env" bash run0439.sh run normal x28-x1 30 2>&1 | tail -1
for k in $(seq 1 30); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
P=$(pgrep "^kyty_emulator" | head -1)
T0=$(date +%s)
for k in $(seq 1 50); do grep -a -q 'LLE: sysmodule pack dir' "$HOME/bc5-work/play-last.log" && break; sleep 0.5; done
if ! loads "$HOME/bc5-work/play-last.log" | grep -q "pack dir: .*/packs/x1"; then
  echo "X1: the log does not name packs/x1: the series stops"; loads "$HOME/bc5-work/play-last.log"
  pkill -TERM "^kyty_emulator"; sleep 5; unlock; exit 1
fi
sleep $((20 - ($(date +%s) - T0)))
mkdir -p "$O"
[ -n "$P" ] && kill -0 "$P" 2> /dev/null && python3 -I "$HOME/bc5-work/exp0439/k439/qtab.py" "$P" "$HOME/bc5-work/play-last.log" "X1 t 20 s" > "$O.q20" 2>&1
for k in $(seq 1 20); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
pgrep "^kyty_emulator" > /dev/null && { echo "X1: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal x28-x1 > /dev/null 2>&1
mv "$O.q20" "$O/q20.txt" 2> /dev/null
PL=$O/play-last.log
echo "== X1 third title + the first title's Agc/AgcDriver/Psml: $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); flips $(grep -a -c 'tag dc439): t .* flip:' $PL); queue regs $(grep -a -c 'queue reg:' $PL); unresolved PLT $(grep -a -c 'unresolved PLT import patched' $PL), stub calls $(grep -a -c 'Unresolved import stub called' $PL); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
loads $PL
grep -a 'unresolved PLT import patched' $PL | sed -E 's/.*, ([A-Za-z0-9+_-]{11})\[([^]]*)\]\[([^]]*)\].*, ([^,]*)$/\2 \3 \1 <- \4/' | sed "s|$HOME|~|" | sort | uniq -c | sort -rn > "$O/unresolved.txt"
awk '{print $2, $NF}' "$O/unresolved.txt" | sort | uniq -c | head -20
grep -a 'Unresolved import stub called' $PL | sed -E 's/^.*called \[/[/' | sort | uniq -c | sort -rn | head -8 | cut -c1-160
cat "$O/q20.txt" 2> /dev/null | grep -a -E '^==|^labels|DIFFER' | cut -c1-300
dead_mounts | tee "$O/mounts.txt"

# X2: the first title with the third title's graphics modules.
wl=$(ls -1 "/run/user/$(id -u)/" | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
O=runs/x28-x2; rm -rf "$O"; mkdir -p "$O"; r0=$(resets); f0=$(faults); : > "$HOME/bc5-work/play-last.log"
systemd-run --user --collect --unit="bc5-0439-x28-x2" -p RuntimeMaxSec=95 --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
  /usr/bin/bash -c 'ulimit -c 0; exec distrobox enter ubuntu -- timeout -k 15 60 env BC5_LOGS=1 BC5_LEAN=0 P439_BIN="$1" BC5_SYSMODULES_PACK_DIR="$2" BC5_RUN_ENV="$5" WAYLAND_DISPLAY="$3" "$4"' \
  _ "$BIN" "$PK/x2" "$wl" "$HOME/bc5-work/exp0439/k439/play439.sh" "$HOME/bc5-work/exp0439/run-log.env" > /dev/null 2>&1
sleep 3; for k in $(seq 1 50); do grep -a -q 'LLE: sysmodule pack dir' "$HOME/bc5-work/play-last.log" && break; sleep 0.5; done
if ! loads "$HOME/bc5-work/play-last.log" | grep -q "pack dir: .*/packs/x2"; then
  echo "X2: the log does not name packs/x2: ended"; loads "$HOME/bc5-work/play-last.log"; pkill -TERM "^kyty_emulator"; sleep 5
fi
for k in $(seq 1 24); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
pgrep "^kyty_emulator" > /dev/null && { echo "X2: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
cp ~/bc5-work/play-last.log "$O/"; PL=$O/play-last.log
r1=$(resets); f1=$(faults)
echo "== X2 the first title + the third title's Agc/AgcDriver/Psml: resets $r0 -> $r1, fault records $f0 -> $f1; flips $(grep -a 'tag fc439' $PL | tail -1 | sed -E 's/.*t ([0-9.]+) s flip ([0-9]+).*/\2 by \1 s/'); queue regs $(grep -a -c 'queue reg:' $PL); unresolved PLT $(grep -a -c 'unresolved PLT import patched' $PL), stub calls $(grep -a -c 'Unresolved import stub called' $PL); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
loads $PL
grep -a 'Unresolved import stub called' $PL | sed -E 's/^.*called \[/[/' | sort | uniq -c | sort -rn | head -8 | cut -c1-160
for B in runs/ae27-off/play-last.log; do [ -f $B ] && echo "baseline the first title (ae27-off, own pack): flips $(grep -a 'tag fc439' $B | tail -1 | sed -E 's/.*t ([0-9.]+) s flip ([0-9]+).*/\2 by \1 s/'); queue regs $(grep -a -c 'queue reg:' $B); unresolved PLT $(grep -a -c 'unresolved PLT import patched' $B), stub calls $(grep -a -c 'Unresolved import stub called' $B)"; done
dead_mounts | tee "$O/mounts.txt"
unlock
