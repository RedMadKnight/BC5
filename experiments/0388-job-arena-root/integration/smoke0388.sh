#!/usr/bin/env bash
# BC5 exp 0388, the integration, after the swap: the lean build's start and ASTRO BOT's start, on the shared builds, under the
# lock. Lean runs on the route runner's private launcher, working directory and saves, with no prestart check; ASTRO BOT by its
# own launcher with no input. Each runs a fixed time, then the emulator gets TERM. Prints what the log shows.
# usage: ssh bc250 'bash -s' < smoke0388.sh   (after series0388.sh post, which leaves exp0388r/run ready)
set -u
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0388r/run; S=$W/exp0388/s; L=$E/play-lean.sh; LEAN_S=150; ASTRO_S=90
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
[ -f "$E/play-pkg-0388.sh" ] && [ -f "$E/input-rton.cfg" ] || { echo "no route run left its launcher"; exit 1; }
bash "$S/box0388.sh" claim "exp 0388: lean and ASTRO BOT starts on the shared builds" 12 || exit 1
stop_emu() {
    local p; p=$(pgrep '^kyty_emulator' | head -1)
    [ -n "$p" ] && kill -TERM "$p"
    for _ in 1 2 3 4 5 6 7 8 9 10; do pgrep '^kyty_emulator' > /dev/null || return 0; sleep 1; done
    p=$(pgrep '^kyty_emulator' | head -1); [ -n "$p" ] && kill -KILL "$p"
    sleep 2
}
trap 'stop_emu; bash "$S/box0388.sh" release' EXIT
kbase=$(sudo -n dmesg | wc -l)
report() {  # name, log
    echo "== $1: $(grep -a -c 'Access violation' "$2") access violations, $(sudo -n dmesg | tail -n +"$((kbase + 1))" | grep -ci amdgpu) amdgpu lines"
    grep -a 'job push wait [OF]\|job-arena fix [OF]\|job-arena fix APPLIED' "$2" | head -4 | cut -c1-120
    grep -a 'fps counter' "$2" | tail -1 | cut -c1-90
    tail -1 "$2" | cut -c1-120
}
grep -v 'prestart0388.sh' "$E/play-pkg-0388.sh" > "$L"
cp "$W/exp0360/fight1450-menu.cmd" "$E/in-L1.cmd"
: > "$E/play-last.log"
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ BC5_LEAN=1 BC5_LOGS=1 KYTY_BC5_JOB_ARENA_FIX=1 BC5_0358_INPUT_CONFIG="$E/input-rton.cfg" KYTY_BC5_INPUT_CMD="$E/in-L1.cmd" bash "$L" < /dev/null > "$E/L1-launch.out" 2>&1 &
sleep "$LEAN_S"
echo "lean emulator: $(readlink /proc/"$(pgrep '^kyty_emulator' | head -1)"/exe 2> /dev/null)"
report lean "$E/play-last.log"
stop_emu
sleep 8
tail -1 "$E/L1-launch.out" | cut -c1-100
setsid nohup bash -c 'distrobox enter ubuntu -- "$@"; echo "launcher exit $?"' _ "$W/play-astro.sh" < /dev/null > "$E/A1-launch.out" 2>&1 &
sleep "$ASTRO_S"
echo "astro emulator: $(readlink /proc/"$(pgrep '^kyty_emulator' | head -1)"/exe 2> /dev/null)"
report astro "$W/play-last.log"
stop_emu
sleep 8
tail -1 "$E/A1-launch.out" | cut -c1-100
