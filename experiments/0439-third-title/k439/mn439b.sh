#!/usr/bin/env bash
# BC5 exp 0439 (tag mn439b, 11-22 ~23:15, the top session's order): which difference between the maintainer's shortcut
# starts (noisy intro movie, twice) and mn439's scripted starts (clean, three times) makes the noise. mn439 used the
# shortcut's own launcher and words, plus a fresh save root and PLAY_CAPTURE=0; his starts had his save folder
# (~/bc5-work/_SaveData) and PLAY_CAPTURE=1 (which also sets BC5_DIRECT_FRAME_PROFILE=1, BC5_DIRECT_TIMING=1 and the
# capture directory, play439.sh). Starts, each one screenshot 4 s after the emulator appears, SIGTERM at 8 s:
#   L  = his launcher as the shortcut runs it (t3-test.sh.before-28ae20cf: ce23a3eb, his save folder, PLAY_CAPTURE=1;
#        the top session's word: his folder for this one start, no input)
#   S  = ce23a3eb, a COPY of his save folder as the save root, PLAY_CAPTURE=0
#   P  = ce23a3eb, a fresh save root, PLAY_CAPTURE=1
#   mn439b.sh L|S|P ...      (in that order; a GPU kernel line stops the series)
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; DIR=$HOME/bc5-data/games/TITLE3; LOCK=$HOME/bc5-work/BOX-LOCK
SH=$HOME/bc5-data/priv/t3-screens/mn439b-$(date +%H%M); mkdir -p "$SH"; chmod 700 "$SH"
BIN=$K/normal/kyty_emulator.ce23a3eb
EXTRA="BC5_SYSMODULES_PACK_DIR=$DIR/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_IB_CHAIN_FLAT=1
BC5_DIRECT_AGC_EOP_IDENT=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_UMR_ON_TIMEOUT=1
BC5_0439_PIECE_DUMP=1 BC5_0439_IMPORT_PIECES=1 BC5_0439_XQ_COUNT=1 BC5_0439_ACB_DEEP=1 BC5_0439_ACB_REFUSE=1 BC5_0439_SEMA_TRACE=1
BC5_0439_THREAD_LOG=1 BC5_0439_AUDIO_CATCH=1 BC5_0439_ARGS_PROBE=1 BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000
BC5_0439_COPY_LAYOUT=1 BC5_0439_WAIT_MS=12000 BC5_RUN_ENV=$E/run-log.env"
wl=$(ls -1 "/run/user/$(id -u)/" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
stop() { echo "mn439b STOP: $*"; exit 1; }
shot() { env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1; }
gpu_lines() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
watch_and_end() { # $1 label: wait for the emulator, shot at 4 s, SIGTERM at 8 s
	local t=0 t0
	while ! pgrep "^kyty_emulator" > /dev/null && [ $t -lt 600 ]; do sleep 0.1; t=$((t + 1)); done
	pgrep "^kyty_emulator" > /dev/null || { echo "$1: no emulator within 60 s"; return 1; }
	t0=$(date +%s.%N)
	sleep 4; shot "mn-$1-t4"
	sleep "$(awk -v a="$t0" -v b="$(date +%s.%N)" 'BEGIN { d = a + 8 - b; print (d > 0 ? d : 0) }')"
	pkill -TERM "^kyty_emulator"
	t=0; while pgrep "^kyty_emulator" > /dev/null && [ $t -lt 100 ]; do sleep 0.1; t=$((t + 1)); done
	pgrep "^kyty_emulator" > /dev/null && pkill -KILL "^kyty_emulator" && echo "$1: needed SIGKILL"
	return 0
}
[ "$(md5sum < "$BIN" | cut -c1-8)" = ce23a3eb ] || stop "$BIN is not ce23a3eb"
cd "$E" || exit 1
g0=$(gpu_lines)
for v in "$@"; do
	pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs before $v"
	[ -s "$LOCK" ] && stop "BOX-LOCK holds before $v: $(cat "$LOCK")"
	bash "$K/gate439.sh" > /dev/null 2>&1 || stop "gate439 refuses before $v"
	case $v in
	L) # the launcher takes and drops the lock itself and collects its logs to runs/play-<time>
		[ "$(grep -c 'kyty_emulator.ce23a3eb' "$K/t3-test.sh.before-28ae20cf")" -ge 1 ] || stop "the kept launcher is not the ce23a3eb one"
		nohup bash "$K/t3-test.sh.before-28ae20cf" > /dev/null 2>&1 &
		watch_and_end L
		for k in $(seq 1 60); do [ -s "$LOCK" ] || break; sleep 1; done ;;
	S | P)
		bash e0439.sh lock "exp0439 mn439b $v: one 8-s intro start" > /dev/null 2>&1
		grep -q '^exp0439 ' "$LOCK" || stop "could not take BOX-LOCK"
		SAVE=$E/save-mn439b-$v-$(date +%H%M%S); mkdir -p "$SAVE"
		if [ "$v" = S ]; then cp -a "$HOME/bc5-work/_SaveData/TITLE3" "$SAVE/" || stop "copy his save"; CAP=0; else CAP=1; fi
		unit=bc5-0439-mn439b-$v-$(date +%H%M%S)
		# shellcheck disable=SC2086
		systemd-run --user --collect --unit="$unit" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
			/usr/bin/bash -c 'ulimit -c 0; l=$1; d=$2; shift 2; exec distrobox enter ubuntu -- env "$@" "$l" "$d"' \
			_ "$K/play439.sh" "$DIR" BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=$CAP WAYLAND_DISPLAY="$wl" KYTY_BC5_SAVEDATA_DIR="$SAVE" $EXTRA > /dev/null 2>&1
		watch_and_end "$v"
		cp -p "$HOME/bc5-work/play-last.log" "$SH/play-$v.log" 2> /dev/null
		bash e0439.sh unlock > /dev/null 2>&1 ;;
	*) stop "unknown variant $v" ;;
	esac
	sleep 2
	g=$(gpu_lines)
	echo "$v: shot $(stat -c %s "$SH/mn-$v-t4.png" 2> /dev/null) bytes, GPU kernel lines $g0 -> $g"
	[ "$g" = "$g0" ] || stop "a GPU kernel line after $v"
done
echo "mn439b: done, shots in $SH"
