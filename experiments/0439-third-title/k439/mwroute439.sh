#!/usr/bin/env bash
# BC5 exp 0439 (tag mw439 route, 11-24 07:50): t3s.sh's screen route block (tag rt439, 11-22), cut out unchanged by line
# (mkroute in the 11-24 session), run beside mw439.sh. Needs from the caller: SH (shot dir), O (keys file prefix: $O.keys),
# CMDF (the KYTY_BC5_INPUT_CMD file the emulator tails), BOUND, T3S_ROUTE, T3S_SCREEN_REFS, T3S_REF_DIR, T3S_WANT,
# T3S_NEED_S. t0 = the emulator's appearance.
set -u
shot() { for _try in 1 2; do
    flock "$SH/.shot.lock" env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$(ls -1 /run/user/$(id -u)/ | grep -m1 -E '^wayland-[0-9]+$') DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1
    [ -s "$SH/$1.png" ] && { echo "$1" >> "$SH/shots.txt"; return 0; }; sleep 1; done; echo "$1 FAILED" >> "$SH/shots.txt"; return 1; }
for k in $(seq 1 60); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
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
          edge) # 11-24 12:20 (edge test): the same moves in every arm until the bound, a shot every 2 s while they run:
            # walk forward 4 s, pan right 2 s, walk left 3 s, pan left 2 s, walk back 4 s (stick x y 0..255, 128 = centre)
            n=0
            while pgrep "^kyty_emulator" > /dev/null && [ $(( $(date +%s) - t0 )) -le $((BOUND - 8)) ]; do
              for mv in "l 128 0 4000" "r 255 128 2000" "l 0 128 3000" "r 0 128 2000" "l 128 255 4000"; do
                set -- $mv; printf 'stick %s %s %s %s\n' "$1" "$2" "$3" "$4" >> "$CMDF"
                T=$(( $(date +%s) - t0 )); echo "$(date +%T) t $T s: edge: stick $mv" >> "$O.keys"
                for k in $(seq 1 $(( $4 / 2000 ))); do sleep 1; shot "e$(printf %04d $(( $(date +%s) - t0 )))s-$n"; n=$((n + 1)); done
                sleep 1
              done
            done ;;
          *) echo "$(date +%T) t $now s: step $i: unknown $st" >> "$O.keys" ;;
        esac
      done; exit 0
    fi
