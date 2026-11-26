#!/usr/bin/env bash
# BC5 exp 0439: run 4 (t3s), the black picture and the stall at 11.06 s (the top session, 11-21 ~21:05). The guard build with
# KYTY_BC5_SYSTEM_SW_VERSION (unset or "param", the second argument), BC5_0439_SURF_DUMP (the display surface after the decompress
# pass, private), ACB_DEEP and ACB_REFUSE on, FLAT=1 and IMPORT_PIECES=1 as in t3r-i1, and a box-side stall watch: when the
# journal's frame-profile lines stop for 3 s, one snapshot of every thread (ticks, state, eu-stack) and of labels 0-15.
# (Run 3's header, kept:) the record of the hang in queue 40's chained continuation (the top session's GO, 11-21 ~20:10): the
# guard build (its md5 as the first argument), the 17:04 settings (BC5_DIRECT_JOURNAL=min), the timeout probe, plus
# BC5_0439_PIECE_DUMP=1 (every chained/called piece of the timed-out job), BC5_DIRECT_UMR_ON_TIMEOUT=1 + BC5_0439_UMR_WAVES=1
# (umr -O halt_waves -wa none at the 0.9-s watchdog), BC5_0439_XQ_COUNT=1 (the ring map), and BC5_0439_IMPORT_PIECES=$2
# (0 or 1), and BC5_DIRECT_IB_CHAIN_FLAT=1 (a compute job's chain laid out flat; the top session's decision, 20:40: both fix
# candidates in one run, to spare reboots). R72 gates measurements only: a diagnosis run, the display line recorded. 120 s bound inside the container.
# Start at a clock time (R73: the box-side wait inside this script), so the maintainer can watch; screenshots of the output
# (spectacle, the session's Wayland and D-Bus) at about 4, 8 and 11 s after the emulator's start and then every 15 s while
# it runs, into ~/bc5-data/priv/t3-screens/<tag>/ (mode 700): private, never in git, never attached to a report.
#   t3s.sh <md5-8> <version unset|param> [HH:MM:SS start]
# One box-side wait for a free lock and no emulator (30 min at most, R64), then the run.
# Before: the R72 display line, the dead-mount check, resets and fault records. During: the kernel log streamed to a file
# with its own timeout (R64, R67). The lock only for the run. Output under runs/t3s-v<version>/.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
PIN=${1:?md5}; VER=${2:?version unset or param}; START=${3:-}; MODE=${4:-none}; IMP=1
TAG=${T3S_TAG:-} # exp 0439 (11-21 ~23:00): T3S_TAG names the run (runs/t3s-v<ver><tag>), T3S_BOUND overrides the bound, T3S_EXTRA adds switches
# MODE (exp 0439, the first screen waits for its confirm button): none (120 s, as before), script (KYTY_BC5_INPUT_CMD, the
# top session's rule of 11-21 ~22:30: cross once at 45 s; then every 20 s one more cross while the picture has not changed for
# 15 s, judged from three screenshots over those 15 s; no other buttons; 300 s), pad (no keys, 300 s, the maintainer at the pad)
case "$MODE" in none) BOUND=120 ;; script) BOUND=300 ;; pad) BOUND=300 ;; *) echo "mode is none, script or pad"; exit 1 ;; esac;
[ -n "${T3S_BOUND:-}" ] && BOUND=$T3S_BOUND
CMDF=$HOME/bc5-work/exp0439/in-t3s.cmd
case "$VER" in unset|param) ;; *) echo "version is unset or param"; exit 1 ;; esac
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator; O=runs/t3s-v$VER$TAG
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || { echo "the binary is not $PIN"; exit 1; }
[ "${T3S_PRIV_CHECK:-1}" = 0 ] || for w in BC5_0439_PIECE_DUMP BC5_0439_UMR_WAVES BC5_0439_IMPORT_PIECES BC5_0439_XQ_COUNT BC5_DIRECT_IB_CHAIN_FLAT BC5_0439_SURF_DUMP KYTY_BC5_SYSTEM_SW_VERSION BC5_0439_ACB_REFUSE BC5_0439_SEMA_TRACE BC5_0439_THREAD_LOG BC5_0439_REAL_CPU; do grep -aq $w "$BIN" || { echo "no $w in the binary"; exit 1; }; done
EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/TITLE3/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_0439_PIECE_DUMP=1 BC5_DIRECT_UMR_ON_TIMEOUT=1 BC5_0439_UMR_WAVES=1 BC5_0439_XQ_COUNT=1 BC5_0439_IMPORT_PIECES=$IMP BC5_DIRECT_IB_CHAIN_FLAT=1 BC5_0439_ACB_DEEP=1 BC5_0439_ACB_REFUSE=1 BC5_0439_SURF_DUMP=$HOME/bc5-data/priv/t3-screens/t3s-v$VER$TAG-surf BC5_RUN_ENV=$HOME/bc5-work/exp0439/run-log.env BC5_0439_SEMA_TRACE=1 BC5_0439_THREAD_LOG=1 BC5_DIRECT_AGC_EOP_IDENT=1"
[ "$VER" = param ] && EXTRA="$EXTRA KYTY_BC5_SYSTEM_SW_VERSION=param"
[ -n "${T3S_EXTRA:-}" ] && EXTRA="$EXTRA $T3S_EXTRA"
# T3S_NO_UMR=1 (the top session, 11-22 06:35): the 0.9-s umr watchdog and its wave dump off; the timeout probe stays
[ "${T3S_NO_UMR:-0}" = 1 ] && EXTRA=$(for w in $EXTRA; do case "$w" in BC5_DIRECT_UMR_ON_TIMEOUT=*|BC5_0439_UMR_WAVES=*) ;; *) printf '%s ' "$w" ;; esac; done)
# T3S_NO_WAVES=1 (11-22 07:20): only the wave-dump word off, so the watchdog runs bc5-gpu-hang-dump (CP registers, gfx ring)
[ "${T3S_NO_WAVES:-0}" = 1 ] && EXTRA=$(for w in $EXTRA; do case "$w" in BC5_0439_UMR_WAVES=*) ;; *) printf '%s ' "$w" ;; esac; done)
if [ "${DRY:-0}" = 1 ]; then # the launch as it would go, nothing started, no lock (R66)
  echo "DRY: binary $PIN ok, switches present; start ${START:-now}; run0439.sh run normal t3s-v$VER$TAG $BOUND (mode $MODE) with RUN_PRIV=$BIN"
  echo "DRY: RUN_EXTRA=$EXTRA"
  grep -q '^BC5_DIRECT_JOURNAL=min$' "$HOME/bc5-work/bc5-run.env" && echo "DRY: bc5-run.env sets BC5_DIRECT_JOURNAL=min"
  grep -n 'P439_BIN\|exec\|"\$EMU"' "$HOME/bc5-work/exp0439/k439/play439.sh" | head -4
  bash "$HOME/bc5-work/exp0439/k439/r72check.sh"
  exit 0
fi
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep "^kyty_emulator" > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 15
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box after 30 min (lock [$(cat "$L")])"; exit 1; }
grep -q '^BC5_DIRECT_JOURNAL=min$' "$HOME/bc5-work/bc5-run.env" || { echo "bc5-run.env does not set BC5_DIRECT_JOURNAL=min"; exit 1; }
rm -rf "$O"; mkdir -p "$O"
if ! bash k439/r72check.sh | tee "$O/display.txt"; then
  # LESSONS R72 as extended 11-21 20:14: once, then check again (never during a measured run; this is a diagnosis run)
  echo "display check failed: sudo -n /usr/local/bin/bc5-display-redetect --if-needed" | tee -a "$O/display.txt"
  sudo -n /usr/local/bin/bc5-display-redetect --if-needed 2>&1 | tail -3 | tee -a "$O/display.txt"
  sleep 3
  bash k439/r72check.sh | tee -a "$O/display.txt" || echo "  (still bad: a diagnosis run goes on, the mode recorded)"
fi
journalctl -b -u bc5-display-redetect --no-pager 2> /dev/null | tail -2 | tee -a "$O/display.txt"
for where in container host; do
  if [ $where = container ]; then run_in() { distrobox enter ubuntu -- bash -c "$1"; }; else run_in() { bash -c "$1"; }; fi
  run_in 'for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "dead mount $d: unmounted"; fusermount3 -u "$d" 2>&1 || fusermount3 -u -z "$d" 2>&1; fi; done' 2>&1 | sed "s/^/$where: /"
done
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); resets $(journalctl -k -b 0 --no-pager | grep -c -i -E 'amdgpu.*(timeout|reset)'); fault records $(ls ~/bc5-data/captures/faults | wc -l)" | tee "$O/before.txt"
timeout $((BOUND + 120)) journalctl -k -f -n 0 --no-pager > "$O/klog.txt" 2>&1 &
KJ=$!
: > "$HOME/bc5-work/play-last.log"
if [ -n "$START" ]; then # R73: wait on the box until the given clock time (at most 30 min)
  tgt=$(date -d "$START" +%s 2> /dev/null) || { echo "bad start time $START"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
  now=$(date +%s); [ $((tgt - now)) -gt 1800 ] && { echo "start time over 30 min away"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
  [ "$tgt" -gt "$now" ] && sleep $((tgt - now))
  echo "$(date +%T) starting (asked for $START)"
fi
mkdir -p "$HOME/bc5-data/priv/t3-screens/t3s-v$VER$TAG-surf" && chmod 700 "$HOME/bc5-data/priv/t3-screens/t3s-v$VER$TAG-surf"
SH=$HOME/bc5-data/priv/t3-screens/t3s-v$VER$TAG-$(date +%H%M); mkdir -p "$SH" && chmod 700 "$HOME/bc5-data/priv/t3-screens" "$SH"
shot() { for _try in 1 2; do # exp 0439 (11-22 18:50): one spectacle at a time (flock: the 10-s shots and the route's looks collided, 3 shots lost in run s1), one retry
    flock "$SH/.shot.lock" env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$(ls -1 /run/user/$(id -u)/ | grep -m1 -E '^wayland-[0-9]+$') DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1
    [ -s "$SH/$1.png" ] && { echo "$1" >> "$SH/shots.txt"; return 0; }; sleep 1; done; echo "$1 FAILED" >> "$SH/shots.txt"; return 1; }
( for k in $(seq 1 60); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
  t0=$(date +%s); for at in 4 8 11; do sleep $((t0 + at - $(date +%s))); shot "t$(printf %03d $at)s"; done
  at=26; while pgrep "^kyty_emulator" > /dev/null && [ $at -le $((BOUND + 15)) ]; do sleep $((t0 + at - $(date +%s))) 2> /dev/null; shot "t$(printf %03d $at)s"; if [ $at -lt 30 ]; then at=30; else at=$((at + 10)); fi; done
  shot "after" ) &
SHP=$!
( # exp 0439 (11-21 ~22:45): memory every 30 s: the emulator's RssAnon, amdgpu GTT and VRAM in use, MemAvailable
  for k in $(seq 1 60); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done; t0=$(date +%s)
  G=$(ls -d /sys/class/drm/card*/device 2> /dev/null | while read -r d; do [ -r "$d/mem_info_gtt_used" ] && echo "$d" && break; done)
  while P=$(pgrep "^kyty_emulator" | head -1); [ -n "$P" ]; do
    echo "$(date +%T) t $(( $(date +%s) - t0 )) s: RssAnon $(( $(awk '/^RssAnon/ {print $2}' /proc/$P/status 2> /dev/null || echo 0) / 1024 )) MiB, GTT $(( $(cat $G/mem_info_gtt_used 2> /dev/null || echo 0) >> 20 )) MiB, VRAM $(( $(cat $G/mem_info_vram_used 2> /dev/null || echo 0) >> 20 )) MiB, MemAvailable $(( $(awk '/^MemAvailable/ {print $2}' /proc/meminfo) / 1024 )) MiB" >> "$O.mem"
    sleep 30
  done ) &
if [ "$MODE" = script ]; then # exp 0439: the confirm presses, appended to the input script the emulator tails (exp 0382's scheme)
  ( for k in $(seq 1 60); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
    t0=$(date +%s)
    if [ -n "${T3S_ROUTE:-}" ]; then # exp 0439 (11-22 ~17:40, tag rt439): a route of screens, each step waits for the screen it needs
      # need=<name>: from now, a shot every 3 s (up to T3S_NEED_S, default 90 s) until the menu heading (crop 760,515-1160,555
      # of the 1920x1080 desktop shot) is closest to T3S_SCREEN_REFS/<name>.png among all refs there; each look is logged
      # with its scores; never seen -> the run is stopped without a press. cross / right / left: that button, a shot 2 s
      # later. check: the option name against T3S_REF_DIR's quality/performance/raytracing (as in T3S_PRESSES).
      # play: from then a cross every 20 s with shots before and after (cutscenes and prompts) until the bound.
      see() { python3 -I -W ignore -c 'import sys, os
from PIL import Image
def g(p): return Image.open(p).convert("L").crop((760, 515, 1160, 555))
k = g(sys.argv[1]); best = None; out = []
for f in sorted(os.listdir(sys.argv[2])):
    if not f.endswith(".png"): continue
    r = g(os.path.join(sys.argv[2], f)); d = sum(abs(a - b) for a, b in zip(k.getdata(), r.getdata())) / (400 * 40)
    out.append("%s %.2f" % (f[:-4], d)); best = (d, f[:-4]) if best is None or d < best[0] else best
print("; ".join(out), "closest", best[1] if best else "none")' "$1" "${T3S_SCREEN_REFS:-/nonexistent}" 2>&1; }
      i=0
      for st in $T3S_ROUTE; do
        pgrep "^kyty_emulator" > /dev/null || break
        i=$((i + 1)); now=$(( $(date +%s) - t0 ))
        case "$st" in
          need=*) W=${st#need=}; ok=0
            for k in $(seq 0 3 ${T3S_NEED_S:-90}); do
              pgrep "^kyty_emulator" > /dev/null || break
              now=$(( $(date +%s) - t0 )); shot "n$(printf %03d $now)s-$W"; v=$(see "$SH/n$(printf %03d $now)s-$W.png")
              echo "$(date +%T) t $now s: step $i need $W: $v" >> "$O.keys"
              case "$v" in *"closest $W") ok=1; break ;; esac
              sleep 3
            done
            [ $ok = 1 ] || { echo "$(date +%T) t $now s: step $i: $W never seen: the run is stopped without a press" >> "$O.keys"; pkill -TERM "^kyty_emulator"; break; } ;;
          cross|right|left|up|down|circle) printf 'press %s\n' "$st" >> "$CMDF"; echo "$(date +%T) t $now s: step $i: $st" >> "$O.keys"; sleep 2; shot "k$(printf %03d $now)s-$st"; sleep 1 ;;
          check) K=$(ls -t "$SH"/k*.png 2> /dev/null | head -1)
            v=$(python3 -I -W ignore -c 'import sys
from PIL import Image
def g(p): return Image.open(p).convert("L").crop((760, 560, 1160, 640))
k = g(sys.argv[1]); best = None
for n in ("quality", "performance", "raytracing"):
    r = g(sys.argv[2] + "/" + n + ".png"); d = sum(abs(a - b) for a, b in zip(k.getdata(), r.getdata())) / (400 * 80)
    print(n, "%.2f" % d, end="; ")
    best = (d, n) if best is None or d < best[0] else best
print("closest", best[1])' "$K" "${T3S_REF_DIR:-/nonexistent}" 2>&1)
            echo "$(date +%T) t $now s: step $i check $(basename "$K"): $v" >> "$O.keys"
            case "$v" in *"closest ${T3S_WANT:-performance}") ;; *) echo "$(date +%T) t $now s: NOT ${T3S_WANT:-performance}: the run is stopped without a confirm" >> "$O.keys"; pkill -TERM "^kyty_emulator"; break ;; esac ;;
          menus) ok=0 # exp 0439 (11-22 ~18:58): the new-game menus in whatever order (a fresh save root showed "experience" first): a look every 4 s; difficulty or experience -> cross (their defaults); graphics -> done; up to 3 x T3S_NEED_S
            for k in $(seq 0 4 $(( ${T3S_NEED_S:-90} * 3 ))); do
              pgrep "^kyty_emulator" > /dev/null || break
              now=$(( $(date +%s) - t0 )); shot "m$(printf %03d $now)s"; v=$(see "$SH/m$(printf %03d $now)s.png")
              echo "$(date +%T) t $now s: step $i menus: $v" >> "$O.keys"
              case "$v" in
                *"closest graphics") ok=1; break ;;
                *"closest difficulty"|*"closest experience") printf 'press cross
' >> "$CMDF"; echo "$(date +%T) t $now s: step $i menus: cross" >> "$O.keys"; sleep 4 ;;
                *) sleep 4 ;;
              esac
            done
            [ $ok = 1 ] || { echo "$(date +%T) t $now s: step $i: graphics never seen: the run is stopped without a press" >> "$O.keys"; pkill -TERM "^kyty_emulator"; break; } ;;
          wait*) sleep $((t0 + ${st#wait} - $(date +%s))) 2> /dev/null; echo "$(date +%T) t $(( $(date +%s) - t0 )) s: step $i: waited to ${st#wait} s" >> "$O.keys" ;;
          play) while pgrep "^kyty_emulator" > /dev/null && [ $(( $(date +%s) - t0 )) -le $((BOUND - 5)) ]; do
              T=$(( $(date +%s) - t0 )); shot "b$(printf %03d $T)s"; printf 'press cross\n' >> "$CMDF"; echo "$(date +%T) t $T s: play: cross" >> "$O.keys"; sleep 2; shot "a$(printf %03d $T)s"; sleep 18
            done ;;
          *) echo "$(date +%T) t $now s: step $i: unknown $st" >> "$O.keys" ;;
        esac
      done; exit 0
    fi
    if [ -n "${T3S_PRESSES:-}" ]; then # exp 0439 (11-21 ~22:30): fixed press times in seconds, e.g. "45 125"; no picture rule
      for it in $T3S_PRESSES; do # "T" = cross at T s; "T:button" = that button (KYTY_BC5_INPUT_CMD names: up down left right ...), with a shot 2 s later
        T=${it%%:*}; Bn=cross; [ "$it" != "$T" ] && Bn=${it#*:}
        sleep $((t0 + T - $(date +%s))) 2> /dev/null; pgrep "^kyty_emulator" > /dev/null || break
        if [ "$Bn" = check ]; then # exp 0439 (11-22): the newest k-shot's option name against T3S_REF_DIR's quality/performance/raytracing.png
          K=$(ls -t "$SH"/k*.png 2> /dev/null | head -1)
          v=$(python3 -I -W ignore -c 'import sys
from PIL import Image
def g(p): return Image.open(p).convert("L").crop((760, 560, 1160, 640))
k = g(sys.argv[1]); best = None
for n in ("quality", "performance", "raytracing"):
    r = g(sys.argv[2] + "/" + n + ".png"); d = sum(abs(a - b) for a, b in zip(k.getdata(), r.getdata())) / (400 * 80)
    print(n, "%.2f" % d, end="; ")
    best = (d, n) if best is None or d < best[0] else best
print("closest", best[1])' "$K" "${T3S_REF_DIR:-/nonexistent}" 2>&1)
          echo "$(date +%T) t $T s: check $(basename "$K"): $v" >> "$O.keys"
          case "$v" in *"closest ${T3S_WANT:-performance}") ;; *) echo "$(date +%T) t $T s: NOT ${T3S_WANT:-performance}: the run is stopped without a confirm" >> "$O.keys"; pkill -TERM "^kyty_emulator"; break ;; esac
          continue
        fi
        if [ "$Bn" = xs ]; then # cross with a shot just before and 2 s after
          shot "b$(printf %03d $T)s"; printf 'press cross\n' >> "$CMDF"; echo "$(date +%T) t $T s: cross (fixed time, shots before and after)" >> "$O.keys"; sleep 2; shot "a$(printf %03d $T)s"; continue
        fi
        printf 'press %s\n' "$Bn" >> "$CMDF"; echo "$(date +%T) t $T s: $Bn (fixed time)" >> "$O.keys"
        if [ "$Bn" != cross ]; then sleep 2; shot "k$(printf %03d $T)s-$Bn"; fi
      done; exit 0
    fi
    sleep $((t0 + 45 - $(date +%s))) 2> /dev/null; printf 'press cross\n' >> "$CMDF"; echo "$(date +%T) t 45 s: cross (the first press)" >> "$O.keys"
    # the picture's change: mean absolute grey difference (0-255) on a 480x270 copy; under 1.0 counts as unchanged (11-21 21:38 shots: black to dialog 1.66, the speckle growing 0.5-0.7 per 15 s, still dialog 0.08)
    dif() { python3 -I -W ignore -c 'import sys
from PIL import Image
a, b = (Image.open(p).convert("L").resize((480, 270)) for p in sys.argv[1:3])
print("%.2f" % (sum(abs(x - y) for x, y in zip(a.getdata(), b.getdata())) / (480 * 270)))' "$1" "$2" 2> /dev/null || echo x; }
    T=65; while [ $T -le $((BOUND - 5)) ] && pgrep "^kyty_emulator" > /dev/null; do
      sleep $((t0 + T - $(date +%s))) 2> /dev/null; shot "p$(printf %03d $T)s"
      A=$SH/t$(printf %03d $((T - 15)))s.png; B=$SH/t$(printf %03d $((T - 5)))s.png; C=$SH/p$(printf %03d $T)s.png
      d1=$(dif "$A" "$B"); d2=$(dif "$B" "$C")
      if awk -v a="$d1" -v b="$d2" 'BEGIN { exit !(a != "x" && b != "x" && a + 0 < 1.0 && b + 0 < 1.0) }'; then
        printf 'press cross\n' >> "$CMDF"; echo "$(date +%T) t $T s: cross (unchanged for 15 s: $d1, $d2)" >> "$O.keys"
      else echo "$(date +%T) t $T s: no press (changed or missing: $d1, $d2)" >> "$O.keys"; fi
      T=$((T + 20)); done ) &
fi
( # the stall watch: frame-profile lines in the newest capture's journal stop for 3 s -> one snapshot (threads, stacks, labels)
  mkdir -p "$O/stall"; sleep 8
  J=$(ls -d "$HOME"/bc5-data/captures/play-* | tail -1)/gc/direct.log
  last=0; same=0
  for k in $(seq 1 $((BOUND * 2 + 40))); do
    pgrep "^kyty_emulator" > /dev/null || break
    c=$(grep -a -c "frame profile" "$J" 2> /dev/null); c=${c:-0}
    if [ "$c" -gt 0 ] && [ "$c" = "$last" ]; then same=$((same + 1)); else same=0; fi
    last=$c
    if [ $same -ge 6 ]; then
      P=$(pgrep "^kyty_emulator" | head -1)
      echo "$(date +%T) stall: frame-profile lines stopped at $c" > "$O/stall/when.txt"
      ticks() { for t in /proc/$P/task/*; do echo "$(basename $t) $(awk '{print $14+$15, $3}' $t/stat 2> /dev/null) $(cat $t/comm 2> /dev/null) $(cat $t/wchan 2> /dev/null)"; done; }
      ticks > "$O/stall/t0.txt"; sleep 1; ticks > "$O/stall/t1.txt"
      join <(sort "$O/stall/t0.txt") <(sort "$O/stall/t1.txt") | awk '{print $5-$2, $1, $6, $7, $8}' | sort -rn > "$O/stall/threads.txt"
      distrobox enter ubuntu -- eu-stack -p "$P" -n 16 > "$O/stall/stacks.txt" 2>&1
      python3 -I - "$P" > "$O/stall/labels.txt" 2>&1 <<'EOF'
import sys
pid = int(sys.argv[1])
with open(f"/proc/{pid}/mem", "rb") as m:
    m.seek(0x2000000000); b = m.read(16 * 32)
    print("labels 0..15: " + " ".join(f"{k}={int.from_bytes(b[32*k:32*k+8], 'little'):x}" for k in range(16)))
    for a in (0x20000081c0, 0x2000008220, 0x20000082e0, 0x2000008200, 0x2000008040, 0x20000081a0):
        m.seek(a); print(f"0x{a:x} = 0x{int.from_bytes(m.read(8), 'little'):x}")
EOF
      if [ "${T3S_STALL_STOP:-0}" = 1 ]; then # exp 0439 (11-21 ~22:45, the top session): a stall ends the run after the snapshot
        echo "$(date +%T) the run is stopped after the snapshot (T3S_STALL_STOP=1)" >> "$O/stall/when.txt"; pkill -TERM "^kyty_emulator"
      fi
      break
    fi
    sleep 0.5
  done ) &
SWP=$!
printf 'wait 1000\n' > "$CMDF"; rm -f "$CMDF.done" "$O.keys" "$O.mem"
[ "$MODE" = script ] && EXTRA="$EXTRA KYTY_BC5_INPUT_CMD=$CMDF"
RUN_PRIV=$BIN RUN_EXTRA="$EXTRA" bash run0439.sh run normal t3s-v$VER$TAG $BOUND 2>&1 | tail -1
sleep 5; for k in $(seq 1 $((BOUND / 5 + 20))); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
pgrep "^kyty_emulator" > /dev/null && { echo "EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal t3s-v$VER$TAG > /dev/null 2>&1
kill $KJ 2> /dev/null
wait $SHP 2> /dev/null
wait $SWP 2> /dev/null
if [ -f "$O/stall/when.txt" ]; then cat "$O/stall/when.txt"; head -8 "$O/stall/threads.txt"; cat "$O/stall/labels.txt"; else echo "no stall seen by the watch"; fi
grep -a "tag sv439\|tag sr439\|tag ar439" "$O/play-last.log" 2> /dev/null | head -12 | cut -c1-240
echo "screenshots: $(ls "$SH" | grep -c png) in $SH"
PL=$O/play-last.log
grep -a "frame profile" "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null | tail -2 | cut -c1-200
echo "r438 BUG lines: $(grep -a -c 'r438 (exp 0438, b438): BUG' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null)"
grep -a -c "tag ip439" $O/play-last.log 2> /dev/null | sed 's/^/ip439 lines: /'
echo "fl439: flattened $(grep -a -c 'tag fl439): .* laid out flat:' $O/play-last.log), refused $(grep -a -c 'tag fl439): .* NOT laid out flat' $O/play-last.log); k1f412 imports $(grep -a -c 'k1 at the filter' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null), ud434 imports $(grep -a -c 'user-data target (exp 0434' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null)"
grep -a 'tag fl439\|tag ip439\|tag pd439' $O/play-last.log | head -6 | cut -c1-220
echo "== t3s-v$VER$TAG: $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); fault records $(ls ~/bc5-data/captures/faults | wc -l); flips $(grep -a -c 'tag dc439): t .* flip:' $PL); decompress OK $(grep -a -c 'decompress of index .*: OK' $PL); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
grep -a 'GPU FAULT\|Error ---' -A2 $PL | head -6 | cut -c1-220
grep -a -i 'amdgpu' "$O/klog.txt" | head -8 | cut -c1-200
ls -d ~/bc5-data/captures/play-* | tail -1
bash e0439.sh unlock 2>&1 | tail -1
