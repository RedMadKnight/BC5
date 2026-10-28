#!/usr/bin/env bash
# BC5 experiment 0363: ASTRO BOT on the integrated shared normal build, by script (tools/scripts/astro-route.sh's route:
# the title screen, X, the save loads, X, then walking and jumping), SECS seconds, RT as the shared input.cfg says
# (RayTracing.PPSA21564=off is the maintainer's setting for this title). A PRIVATE copy of the title's saves
# (KYTY_BC5_SAVEDATA_DIR; the live ones compared before and after, never written), a private copy of play-astro.sh with
# its own log, the kernel log streamed, the box lock held, the emulator (this script's own) stopped at SECS or at the
# first crash/kernel line. Prints the frame rate per 20-s window (KYTY_BC5_FPS_COUNTER), the game-fix line, crash /
# kernel / TIMEOUT counts. usage: astro0363.sh <tag> [secs] ["VAR=value ..."] [emulator]   (on the box)
set -u
TAG=${1:?a tag}; SECS=${2:-200}; ENVS=${3:-}; BIN=${4:-$HOME/bc5-work/kytyplus-build/src/kyty_emulator}
W=$HOME/bc5-work; E=$W/exp0363; R=$E/raw; LOCK=$W/BOX-LOCK; SD=$W/_SaveData/PPSA21564; SROOT=$E/_SaveData
LAUNCH_SRC=$W/play-astro.sh; LAUNCH=$E/play-astro-0363.sh; EXPECT_LAUNCH=${EXPECT_LAUNCH:-48238ccd}
L=$E/play/play-$TAG.log
mkdir -p "$R" "$E/play"
m() { md5sum < "$1" | cut -c1-8; }
saves() { find "$SD" -type f -print0 | sort -z | xargs -0 md5sum | md5sum | cut -c1-16; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: not started"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -f "$R/$TAG.log" ] && { echo "tag $TAG already used: not started"; exit 1; }
[ "$(m "$LAUNCH_SRC")" = "$EXPECT_LAUNCH" ] || { echo "$LAUNCH_SRC is md5 $(m "$LAUNCH_SRC"), not $EXPECT_LAUNCH: check it, not started (EXPECT_LAUNCH=... to accept)"; exit 1; }
[ -x "$BIN" ] || { echo "no emulator $BIN"; exit 1; }
# the private launcher: the log line only
sed -e "s#^LOG=~/bc5-work/play-last.log\$#LOG=$L  \# exp 0363: own log#" "$LAUNCH_SRC" > "$LAUNCH"
grep -q "^LOG=$L" "$LAUNCH" || { echo "the launcher's LOG line was not replaced"; exit 1; }
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-astro-0363.diff"; [ "$(grep -c '^[-+][^-+]' "$R/play-astro-0363.diff")" = 2 ] || { echo "the launcher diff is not the one line: stop"; cat "$R/play-astro-0363.diff"; exit 1; }
chmod +x "$LAUNCH"
# the private saves copy (the live ones compared only)
S0=$(saves); rm -rf "$SROOT"; mkdir -p "$SROOT"; cp -a "$SD" "$SROOT/PPSA21564" || exit 1
echo "$(date '+%F %T') $TAG: live saves $S0 (compared only; private copy $SROOT/PPSA21564)" | tee -a "$R/saves.txt"
# the route (tools/scripts/astro-route.sh, 2026-10-21): the title screen, X, the save loads, X, then walking and jumping
{
  echo "wait 40000"; echo "press cross"; echo "wait 25000"; echo "press cross"; echo "wait 15000"
  for i in $(seq 1 20); do
    echo "stick l 128 0"; echo "wait 1500"; echo "press cross"; echo "wait 600"
    echo "stick l 255 128"; echo "wait 1000"; echo "press cross"; echo "wait 400"
  done
  echo "stick l 128 128"
} > "$E/in-$TAG.cmd"
# the per-window summary of the fps counter's per-second lines, as a file (no quoting in the shell line)
cat > "$E/fps-windows.awk" <<'EOF'
{ b = int($1 / 20) * 20; f = $2 / $3; s[b] += f; n[b]++; if (!(b in mn) || f < mn[b]) mn[b] = f; if ($4 > g[b]) g[b] = $4 }
END { for (b in s) printf "%4d-%4d s: %5.1f fps (min %4.1f, gap %6.1f ms)\n", b, b + 20, s[b] / n[b], mn[b], g[b] }
EOF
echo "bvh exp 0363 | astro run: ASTRO BOT's scripted route, the build $(m "$BIN"), $SECS s, private saves copy, $TAG | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 3))min" +%H:%M)" > "$LOCK"
# On any exit: this script's own emulator (if it still runs) is stopped BEFORE the lock line is cleared, so a failure of
# the script after the launch never leaves an emulator running under an empty lock (the aborted A1 of 16:25 did).
EP=""
trap 'if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP" 2> /dev/null; sleep 3; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; grep -q "^bvh exp 0363 | astro run" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
timeout $((SECS + 90)) sudo -n dmesg -w > "$R/$TAG-kernel-stream.txt" 2>&1 &
SP=$!
{ date '+%F %T'; echo "$TAG: $SECS s, emulator $BIN md5 $(m "$BIN"), launcher $LAUNCH (from $LAUNCH_SRC $EXPECT_LAUNCH), env: KYTY_BC5_SAVEDATA_DIR=$SROOT KYTY_BC5_INPUT_CMD=$E/in-$TAG.cmd KYTY_BC5_FPS_COUNTER=1 $ENVS"; echo "kernel $(uname -r); input.cfg RayTracing.PPSA21564: $(grep -i 'RayTracing.PPSA21564' "$W/input.cfg" || echo unset)"; } > "$R/$TAG.log"
# shellcheck disable=SC2086
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_SAVEDATA_DIR="$SROOT" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" KYTY_BC5_FPS_COUNTER=1 BC5_EMU="$BIN" $ENVS "$LAUNCH" > "$R/$TAG-launcher.out" 2>&1 < /dev/null &
for _ in $(seq 1 90); do pgrep -x kyty_emulator > /dev/null && break; sleep 1; done
EP=$(pgrep -x kyty_emulator | head -1); [ -n "$EP" ] || { echo "the emulator did not start: see $R/$TAG-launcher.out"; tail -5 "$R/$TAG-launcher.out"; exit 1; }
echo "emulator pid $EP, md5 $(md5sum < /proc/$EP/exe | cut -c1-8); environ: $(tr '\0' '\n' < /proc/$EP/environ | grep -E '^(KYTY_BC5_SAVEDATA_DIR|KYTY_BC5_RT|KYTY_BC5_INPUT_CMD|BC5_EMU)=' | tr '\n' ' ')" | tee -a "$R/$TAG.log"
T0=$(date +%s); ENDED=""
while [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  if sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -qi "amdgpu"; then ENDED="KERNEL: an amdgpu line at $(($(date +%s) - T0)) s"; break; fi
  if [ -f "$L" ] && grep -aq "Stack trace \[thread\|Exception\|EXIT:" "$L"; then sleep 3; ENDED="CRASH: a crash line in the log at $(($(date +%s) - T0)) s"; break; fi
  sleep 2
done
DUR=$(($(date +%s) - T0))
if [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; kill "$SP" 2> /dev/null
NC=$(grep -a -c "Stack trace \[thread\|Exception" "$L" 2> /dev/null); NT=$(grep -a -c "TIMEOUT" "$L" 2> /dev/null); NK=$(sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -ci "amdgpu")
echo "== $TAG: ${ENDED:-stopped at $SECS s} after $DUR s; crash lines $NC, TIMEOUT lines $NT, kernel amdgpu lines $NK" | tee -a "$R/$TAG.log"
echo "== game fix line:" | tee -a "$R/$TAG.log"; grep -a "game fix" "$L" | head -3 | tee -a "$R/$TAG.log"
echo "== fps per 20-s window (mean flips/s, min second, longest gap ms):" | tee -a "$R/$TAG.log"
grep -a "^fps counter: t" "$L" | sed -n 's/^fps counter: t \([0-9.]*\) s: \([0-9]*\) flips in \([0-9.]*\) s, longest gap \([0-9.]*\) ms.*/\1 \2 \3 \4/p' | awk -f "$E/fps-windows.awk" | sort -n | tee -a "$R/$TAG.log"
S1=$(saves); echo "$(date '+%F %T') $TAG: live saves $S1 (want $S0)" | tee -a "$R/saves.txt" "$R/$TAG.log"
[ "$S1" = "$S0" ] || echo "THE LIVE SAVES CHANGED: tell the maintainer"
