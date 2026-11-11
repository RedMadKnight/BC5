#!/usr/bin/env bash
# BC5 exp 0412: the line-level profile runs for build g412i, one after another on the box under setsid nohup.
# n1src, n2src: the scripted load of the copy of his save, arm fast2 (both table fixes on), the stack sampler in source
# mode (PROF_SRC=1) on Render_Thread and game-main. Every run has the sampler, the fuse and the watchdog (run0412n.sh).
# A file night/STOP ends the chain between runs.
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
calm() { for _ in $(seq 1 36); do pgrep '^kyty_emulator' > /dev/null || pgrep -f prof0412.sh > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
one() { # tag
  local tag=$1
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $tag"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $tag"; exit 1; }
  sleep 10
  (setsid nohup distrobox enter ubuntu -- env PROF_SRC=1 bash "$X/prof0412.sh" "$N/raw/$tag-prof-render.txt" 0 25 200 Render_Thread > /dev/null 2>&1 < /dev/null &)
  (setsid nohup distrobox enter ubuntu -- env PROF_SRC=1 bash "$X/prof0412.sh" "$N/raw/$tag-prof-game.txt" 0.5 25 200 game-main > /dev/null 2>&1 < /dev/null &)
  bash "$X/run0412n.sh" "$tag" fast2 60 > "$N/run-$tag.log" 2>&1
}
one n1src
one n2src
echo "$(date +%T) chain: end"
