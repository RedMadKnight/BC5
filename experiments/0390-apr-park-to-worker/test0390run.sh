#!/usr/bin/env bash
# Exp 0390 tests, laptop only: the real go0390.sh, run0390.sh, s6n0390.sh and check0390.py on a stand-in tree under a
# d19-test- path, with the real pinned launcher text. Stand-ins replace ssh, scp and the box's reads (/proc, kernel,
# pgrep, setsid); a small script plays the emulator. HOME changes for the child shells only. The run's clock is a
# counter that moves 15 s at each pause, so a loaded laptop cannot change a result.
# usage: bash test0390.sh [name filter]
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
BR=$(cd "$HERE/../.." && pwd)
PIN=${D19_PIN_DIR:-C:/Users/kjani/Documents/ChatGPT/BC5/coordination/box-read}
FILTER=${1:-}
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
F=$T/f; H=$(cygpath -m "$T/h"); W=$H/bc5-work; RUND=$T/run; EX=$W/exp0390; R=$EX/run/raw
mkdir -p "$F/emus" "$RUND"
P=0; N=0
ok() { P=$((P+1)); echo "ok   $1"; }
bad() { N=$((N+1)); echo "FAIL $1"; }
m() { md5sum < "$1" | cut -d' ' -f1; }
stop_all() {
  local p
  for p in $(ps -ef | grep -F "$(basename "$T")" | grep -v grep | grep -v 'test0390' | awk '{print $2}'); do kill -9 "$p" 2> /dev/null; done
  for p in $(ls "$F/emus" 2> /dev/null); do kill -9 "$p" 2> /dev/null; done
  [ ! -s "$F/sentinel" ] || kill -9 "$(cat "$F/sentinel")" 2> /dev/null
}
trap 'stop_all; [ -n "${D19_KEEP:-}" ] && echo "kept $T" || rm -rf "$T"' EXIT
cp "$HERE"/run0390.sh "$HERE"/go0390.sh "$HERE"/series0390.sh "$HERE"/s6n0390.sh "$HERE"/prestart0390.sh "$HERE"/check0390.py "$HERE"/d19gates.py "$HERE"/d19manifest.py "$RUND/"

cat > "$F/mkenv.py" <<'EOF'
# The emulator's environment as the tables want it, plus lines of added names.
import os, re, sys
sys.dont_write_bytecode = True
run, out, tag, fix, home, cfgtok, gc, addf = sys.argv[1:9]
sys.path.insert(0, run)
import check0390 as c
m = c.m
c.tables(fix, tag)
SAMPLE = {"KYTY_BC5_INPUT_CONFIG": cfgtok, "BC5_0358_INPUT_CONFIG": cfgtok, "KYTY_BC5_INPUT_CMD": home + "/bc5-work/exp0390/run/in-" + tag + ".cmd",
          "BC5_EMU": home + "/bc5-work/exp0390/kyty_emulator", "XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "wayland-0",
          "DISPLAY": ":0", "BC5_GC_DUMP_DIR": gc, "D19_OWNER": os.environ["D19_OWNER"]}
env = [("HOME", home), ("PATH", "/usr/bin")]
for k, v in m.table("normal", home, tag).items():
    env.append((k, v if isinstance(v, str) else SAMPLE[k]))
try:
    for x in open(addf):
        k, v = x.rstrip("\n").split("=", 1)
        env = [e for e in env if e[0] != k] + [(k, v)]
except OSError:
    pass
open(out, "wb").write(b"".join(f"{k}={v}".encode() + b"\0" for k, v in env))
EOF

cat > "$F/emu.sh" <<'EOF'
# The emulator: a journal, a log, the crash of the scenario. Arguments: dir of stand-ins, journal, log, token.
F=$1; J=$2; L=$3; TOK=$4; me=$$
mv "$F/env-new" "$F/env-$me"; echo "$TOK" > "$F/emus/$me"
S=$(cat "$F/scn" 2> /dev/null)
case " $S " in *" no-journal "*) J=/dev/null ;; esac
if case " $S " in *" no-log "*) false ;; *) true ;; esac; then
  { echo "game fix (temporary, exp 0359): job-arena fix $(cat "$F/fixline") for PPSA03671 (environment)"
    for i in 0 1 2 3 4 5 6 7 8 9; do echo "[bc5] stubbed import #0x$i: abc$i[LibX] (program eboot)"; done
    for i in $(seq 1 180); do echo "fps counter: t $i.000 s: 30 flips in 1.000 s, longest gap 40.0 ms, gaps over 40 ms 1, over 70 ms 0"; done
  } > "$L"
fi
case " $S " in *" rt-off "*) echo "ray tracing off: dropped" >> "$J" ;; esac
while :; do
  p2=$(cat "$F/p2")
  if grep -q 'slow 1' "${p2%-done.txt}.txt" 2> /dev/null; then v=25.0; else v=70.0; fi
  case " $S " in *" no-load "*) v=30.0 ;; esac
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do echo "frame profile: t 1.0 s, $v ms since last flip, busy 10 ms"; done >> "$J"
  case " $S " in
    *" kern-late "*) if [ -e "$p2" ]; then echo 'amdgpu ring timeout' >> "$F/kern"; S=done; fi ;;
    *" core-late "*) if [ -e "$p2" ]; then echo 'dump' >> "$F/devcore"; S=done; fi ;;
    *" lock-late "*) if [ -e "$p2" ]; then cat "$F/lock-late" > "$F/../h/bc5-work/BOX-LOCK"; S=done; fi ;;
    *" disk-late "*) if [ -e "$p2" ]; then echo 85 > "$F/disk"; S=done; fi ;;
    *" nodisk-late "*) if [ -e "$p2" ]; then : > "$F/disk"; S=done; fi ;;
    *" queue-late "*) if [ -e "$p2" ]; then rm -f "$F/../h/bc5-work/BOX-QUEUE"; mkdir "$F/../h/bc5-work/BOX-QUEUE"; S=done; fi ;;
  esac
  if [ -e "$p2" ]; then
    case " $S " in *" time-line "*) echo "bc5-direct: TIMEOUT on ring" >> "$L" ;; esac
    case " $S " in *" stub-new "*) echo "[bc5] stubbed import #0xa: fresh[LibY] (program x)" >> "$L" ;; esac
    case " $S " in *" stub-bad "*) echo "[bc5] stubbed import #0xb: 5Xa2ACNECdo[libc] (program x)" >> "$L" ;; esac
    case " $S " in *" kern-bad "*) touch "$F/no-kern" ;; esac
  fi
  case " $S " in
    *" crash-target "*) if [ -e "$p2" ]; then
        { echo "Access violation: Read [000000000000000c] "; echo "kyty_exception_handler: 0000000903d7eca0"; echo "exception rip code: addr=0000000903d7eca0, off=0000000003d7eca0, module=eboot.bin: 83 c1"; } >> "$L"
        rm -f "$F/emus/$me"; exit 65; fi ;;
    *" crash-other "*) if [ -e "$p2" ]; then
        { echo "Access violation: Read [0000000000000000] "; echo "kyty_exception_handler: 0000000903a05f35"; echo "exception rip code: addr=0000000903a05f35, off=0000000003a05f35, module=eboot.bin: 83 c1"; } >> "$L"
        rm -f "$F/emus/$me"; exit 65; fi ;;
  esac
  [ ! -e "$L" ] || touch "$L"; sleep 0.1
done
EOF

cat > "$F/fake.sh" <<EOF
apr_threads() { cat "$F/apr-threads" 2> /dev/null; }
F=$F
EOF
cat >> "$F/fake.sh" <<'EOF'
T_ROUTE=15; T_FD=60; T_P2=30; T_P2_WAIT=120; T_POLL=1; T_POLL_P2=1; T_KERN=1; T_KILL=0.1; T_SETTLE=0.1
REAP_TERM=4; REAP_KILL=4
el() { cat "$F/clock" 2> /dev/null || echo 0; }
pause() { [ "${1:-}" = 0.5 ] || echo $(($(el) + 15)) > "$F/clock"; sleep 0.3; }
emu_pids() { local p; for p in $(ls "$F/emus" 2> /dev/null); do if kill -0 "$p" 2> /dev/null; then echo "$p"; else rm -f "$F/emus/$p" "$F/env-$p"; fi; done; return 0; }
work_pids() { return 0; }
compress_state() { cat "$F/svc"; }
disk_pct() { cat "$F/disk"; }
session() { "$@"; }
kstream() { local i; for i in $(seq 1 "$1"); do cat "$F/kern" 2> /dev/null; sleep 1; done; }
clear_lock() { [ ! -e "$F/no-clear" ] && : > "$LOCK"; }
own_pids() { local p; for p in $(emu_pids); do [ "$(cat "$F/emus/$p" 2> /dev/null)" = "$TOK" ] && echo "$p"; done; return 0; }
hook() { [ ! -e "$F/hook-$1" ] || . "$F/hook-$1"; return 0; }
env_raw() { cat "$F/env-$1"; }
exe_of() { echo "$D19_BIN"; }
exe_md5() { if [ -e "$F/exe-wrong" ]; then echo deadbeef; else echo "$WANT"; fi; }
cwd_of() { readlink -f "$WD"; }
alive() { kill -0 "$1" 2> /dev/null; }
fdinfo_of() { printf '      1 drm-engine-gfx:\t%d000000000 ns\n' "$(($(el) + 1))"; }
kern() { [ ! -e "$F/no-kern" ] || return 1; cat "$F/kern" 2> /dev/null; return 0; }
mount_opts() { echo rw,relatime; }
route_read() { [ -e "$F/no-route" ] || echo "$SROOT/PPSA03671/a"; }
sampler() { SP=""; [ ! -e "$F/lock-at-sampler" ] || cat "$F/lock-at-sampler" > "$LOCK"; }
disk_pct() { cat "$F/disk"; }
devcores() { cat "$F/devcore" 2> /dev/null; return 0; }
box_settings() { echo settings; }
boot_line() { echo "boot abcd1234, up since 2026-10-31 10:00:00"; }
launch() {
  local n GC
  n=$(cat "$F/gcn" 2> /dev/null || echo 1000); echo $((n + 1)) > "$F/gcn"
  GC=$HOME/bc5-data/captures/play-20261031-$n/gc
  [ -e "$F/old-gc" ] && GC=$(cat "$F/old-gc") || mkdir -p "$GC"
  python "$F/mkenv.py" "$(dirname "$F")/run" "$F/env-new" "$TAG" "$FIX" "$HOME" "$CFG" "$GC" "$F/env-add"
  [ ! -e "$F/foreign-now" ] || { bash -c 'sleep 300' & p=$!; echo "$p" > "$F/sentinel"; echo 999 > "$F/emus/$p"; printf 'D19_OWNER=999\0' > "$F/env-$p"; }
  echo "launcher exit 0" > "$R/$TAG-launch.out"
  echo "$R/$TAG-phase2-done.txt" > "$F/p2"
  nohup bash "$F/emu.sh" "$F" "$GC/direct.log" "$LOG" "$OWNER" > /dev/null 2>&1 < /dev/null &
}
EOF

cat > "$F/ssh" <<EOF
#!/usr/bin/env bash
F=$F; H=$H
EOF
cat >> "$F/ssh" <<'EOF'
while [ "${1:-}" = -o ]; do shift 2; done
shift
c=$(cat "$F/ssh-n" 2> /dev/null || echo 0); echo $((c + 1)) > "$F/ssh-n"
if [ -e "$F/ssh-drop" ]; then a=$(cat "$F/ssh-drop"); case "$c" in *) if [ "$c" -ge "$a" ] && { [ ! -e "$F/ssh-back" ] || [ "$c" -lt "$(cat "$F/ssh-back")" ]; }; then exit 255; fi ;; esac; fi
HOME=$H D19_WORK=$H/bc5-work D19_FAKE=$F/fake.sh exec bash -c "$*"
EOF
cat > "$F/scp" <<EOF
#!/usr/bin/env bash
H=$H; F=$F
EOF
cat >> "$F/scp" <<'EOF'
[ ! -e "$F/scp-fail" ] || exit 1
shift
files=(); d=""
for a in "$@"; do case "$a" in bc250:*) d=${a#bc250:} ;; *) files+=("$a") ;; esac; done
cp "${files[@]}" "$H/$d"
EOF
chmod +x "$F/ssh" "$F/scp"
cat > "$F/runfake.sh" <<EOF
SSH=$F/ssh; SCP=$F/scp; POLL=1; RESULT_GRACE=6; SHORT=120
EOF

mkdir -p "$W/kytyplus-build/src" "$W/_SaveData/PPSA03671" "$W/exp0358/saves-live-47aefd45/PPSA03671" "$W/exp0360" "$W/exp0330/wd" "$W/d19/raw" "$H/bc5-data/captures/devcoredump"
echo live > "$W/_SaveData/PPSA03671/a"
echo route > "$W/exp0358/saves-live-47aefd45/PPSA03671/a"
mkdir -p "$W/exp0390"; echo binary > "$W/exp0390/kyty_emulator"
cp "$PIN/play-pkg.sh" "$W/play-pkg.sh"; cp "$PIN/bc5-run.env" "$W/bc5-run.env"
echo 'wait 85000' > "$W/exp0360/fight1450-menu.cmd"; echo 'press x' > "$W/exp0360/fight1450-play.cmd"
echo 'RayTracing.PPSA03671=on' > "$W/input.cfg"; echo 0x1100000000 > "$W/direct-learned-pkg.txt"
for i in 0 1 2 3 4 5 6 7 8 9; do echo "abc$i"; done > "$W/d19/raw/stubs-baseline.txt"
printf '#!/bin/sh\n' > "$W/exp0330/sample0330.sh"; chmod +x "$W/exp0330/sample0330.sh" "$W/play-pkg.sh"
route_c() { (cd "$W/exp0358/saves-live-47aefd45" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }
{ echo "NORMAL=$(m "$W/exp0390/kyty_emulator")"; echo "LAUNCHER=$(m "$W/play-pkg.sh")"; echo "RUN_ENV=$(m "$W/bc5-run.env")"
  echo "ROUTE_SAVES=$(route_c)"; echo "MENU_CMD=$(m "$W/exp0360/fight1450-menu.cmd")"; echo "PLAY_CMD=$(m "$W/exp0360/fight1450-play.cmd")"
  echo "INPUT_CFG=$(m "$W/input.cfg")"; echo "LEARNED=$(m "$W/direct-learned-pkg.txt")"; echo "STUB_BASE=$(m "$W/d19/raw/stubs-baseline.txt")"
} > "$RUND/pins0390.env"
cp "$RUND/pins0390.env" "$F/pins.good"

[ "$(m "$PIN/play-pkg.sh" | cut -c1-8)" = 55531ab6 ] && ok "the launcher text is the pinned one" || bad "launcher pin"
TN=0
reset() {
  stop_all; sleep 0.1
  rm -rf "$F/emus" "$F"/env-* "$F"/hook-* "$F/scn" "$F/kern" "$F/devcore" "$F/no-route" "$F/exe-wrong" "$F/old-gc" "$F/foreign-now" "$F/ssh-drop" "$F/ssh-back" "$F/ssh-n" "$F/scp-fail" "$F/sentinel" "$F/clock" "$F/p2" "$F/no-kern" "$F/no-clear" "$F/lock-at-sampler" "$EX" "$RUND/raw"
  mkdir -p "$F/emus"
  mkdir -p "$EX"; echo binary > "$EX/kyty_emulator"
  : > "$W/BOX-LOCK"; echo q > "$W/BOX-QUEUE"; rm -rf "$W/BOX-LOCK.d19-claim"
  echo inactive > "$F/svc"; echo 50 > "$F/disk"; echo ON > "$F/fixline"; printf '      1 bc5-apr-q1
' > "$F/apr-threads"
  cp "$F/pins.good" "$RUND/pins0390.env"
  cp "$PIN/play-pkg.sh" "$W/play-pkg.sh"; echo live > "$W/_SaveData/PPSA03671/a"
}
go() {  # tag fix: sets out and rc
  out=$(D19_RUN_FAKE=$F/runfake.sh timeout 300 bash "$RUND/go0390.sh" "$1" "$2" "$(($(date +%s) + ${DLS:-700}))" 2>&1); rc=$?
}
want() {  # name, expected rc, text in the output, expected lock text ('' free)
  local lk; lk=$(cat "$W/BOX-LOCK" 2> /dev/null)
  case "$out" in *"$3"*) ;; *) bad "$1: output lacks [$3] rc $rc: $(echo "$out" | tail -4 | cut -c1-200 | tr '\n' '~')"; return ;; esac
  [ "$rc" = "$2" ] || { bad "$1: rc $rc, want $2: $(echo "$out" | tail -3 | cut -c1-200 | tr '\n' '~')"; return; }
  [ "$lk" = "${4:-}" ] || { bad "$1: lock [$lk]"; return; }
  ok "$1"
}
clean() { [ -z "$(ls "$F/emus" 2> /dev/null)" ] || { sleep 1; for p in $(ls "$F/emus"); do kill -0 "$p" 2> /dev/null && return 1; done; }; return 0; }
t() { case "$1" in *"$FILTER"*) return 0 ;; *) return 1 ;; esac; }
FOREIGN='other session | its run'
fixarm() { [ "$1" = on ] && echo ON > "$F/fixline" || echo OFF > "$F/fixline"; }

if t positive; then
  reset; go P1N on; want "positive on: no crash through the cap" 0 "CLASS NO_CRASH fix on crash none reached 1"
  grep -q 'done: P1N' "$W/BOX-QUEUE" && grep -q 'token' "$W/BOX-QUEUE" && ok "positive on: queue lines" || bad "positive on: queue"
  clean && ok "positive on: no process left" || bad "positive on: processes"
  grep -q 'KYTY_BC5_JOB_ARENA_FIX=1' "$R/P1N-start.txt" && ok "positive on: the arm is in the start file" || bad "arm on"
  grep -q 'phase2 appended' "$R/P1N-phase2-done.txt" && [ "$(grep -c 'press x' "$EX/run/in-P1N.cmd")" = 1 ] && ok "positive on: the gameplay inputs were appended once" || bad "phase2"
  [ "$(cat "$W/_SaveData/PPSA03671/a")" = live ] && ok "positive on: live saves untouched" || bad "live saves"
  [ "$(cat "$R/P1N-savecopy.txt")" = "$(route_c)" ] && ok "positive on: the private copy's sum is the snapshot's" || bad "copy sum"
  grep -q 'saves() {\|WANT_SAVES\|LIVE=' "$RUND/s6n0390.sh" && bad "a live-save read is left" || ok "no live-save read in the runner"
fi
if t target; then
  reset; echo crash-target > "$F/scn"; go P1F on; want "off: crash at the site" 0 "CLASS CRASH_TARGET fix on crash target reached 1"
  clean && ok "off: no process left" || bad "off: processes"
  reset; echo crash-target > "$F/scn"; go P9N on; want "on: crash at the site is classified" 0 "CLASS CRASH_TARGET fix on crash target reached 1"
fi
if t other; then
  reset; echo crash-other > "$F/scn"; go P2F on; want "crash elsewhere is not the site" 0 "CLASS CRASH_OTHER fix on crash other reached 1"
fi
if t pins; then
  reset; echo x >> "$W/exp0390/kyty_emulator"; go P3N on; want "wrong binary stops" 2 "no result file"; grep -q 'binary is not' "$R/P3N-done.txt" && ok "wrong binary: named" || bad "wrong binary reason"; [ ! -e "$R/P3N-start.txt" ] && ok "wrong binary: nothing launched" || bad "launched"
  printf 'binary\n' > "$W/exp0390/kyty_emulator"
  reset; echo x >> "$W/play-pkg.sh"; go P3N on; want "wrong launcher stops" 2 "no result file"; grep -q 'launcher is not' "$R/P3N-done.txt" && ok "wrong launcher: named" || bad "launcher reason"
  reset; sed -i 's/^MENU_CMD=.*/MENU_CMD=FILL/' "$RUND/pins0390.env"; go P3N on; want "an unfilled pin stops" 2 "no result file"; grep -q 'not filled' "$R/P3N-done.txt" && ok "FILL: named" || bad "fill reason"
  reset; echo active > "$F/svc"; go P3N on; want "compression active: not claimed" 2 "compression job"
  reset; echo 85 > "$F/disk"; go P3N on; want "disk over 80 %: not claimed" 2 "the disk is at"
fi
if t lock; then
  reset; echo "$FOREIGN" > "$W/BOX-LOCK"; go P4N on; want "busy lock: not claimed, line kept" 2 "foreign lock" "$FOREIGN"
  reset; printf 'echo "%s" > "$LOCK"\n' "$FOREIGN" > "$F/hook-before-claim"; go P4N on; want "claim after a free look: line kept" 2 "foreign lock" "$FOREIGN"
  reset; printf 'echo "%s" > "$a"\n' "$FOREIGN" > "$F/hook-after-aside"; go P4N on; want "foreign line during the claim: restored" 2 "foreign lock arrived" "$FOREIGN"
  reset; printf 'echo "%s" > "$LOCK"\n' "$FOREIGN" > "$F/hook-after-aside"; go P4N on; want "foreign file during the claim: kept" 2 "lost the claim" "$FOREIGN"
  reset; rm "$W/BOX-LOCK"; mkdir "$W/BOX-LOCK"; go P4N on; rc0=$rc; rmdir "$W/BOX-LOCK" && { case "$out" in *"not a plain file"*) [ "$rc0" = 2 ] && ok "directory lock stops" || bad "dir lock rc" ;; *) bad "dir lock: $out" ;; esac; } || bad "dir lock kept"
  : > "$W/BOX-LOCK"
  reset; printf 'echo "%s" > "$LOCK"\n' "$FOREIGN" > "$F/hook-after-inputs"; go P4N on; want "lock lost before the launch: no launch, line kept" 2 "not ours" "$FOREIGN"; [ ! -e "$R/P4N-start.txt" ] && ok "lock lost: nothing launched" || bad "launched after loss"
  reset; printf '%s\n' "$FOREIGN" > "$F/lock-late"; echo lock-late > "$F/scn"; go P4N on; want "lock lost during the run: run stops, line kept" 2 "CLASS" "$FOREIGN"
  clean && ok "lock lost: our emulator stopped" || bad "lock lost: emulator stays"
  reset; bash -c 'sleep 300' & sp=$!; echo "$sp" > "$F/sentinel"; echo 999 > "$F/emus/$sp"; printf 'D19_OWNER=999\0' > "$F/env-$sp"; go P4N on; want "foreign emulator at the start: not claimed" 2 "an emulator runs"; kill -0 "$sp" 2> /dev/null && ok "foreign emulator: alive" || bad "foreign emulator killed"
  reset; touch "$F/foreign-now"; go P5N on; want "foreign emulator during the start: invalid, stopped" 0 "CLASS INVALID"; kill -0 "$(cat "$F/sentinel")" 2> /dev/null && ok "foreign emulator during the start: alive" || bad "foreign killed"
fi
if t route; then
  reset; touch "$F/no-route"; go P6N on; want "route save not read: not routed" 0 "CLASS NOT_ROUTED"
  reset; echo no-load > "$F/scn"; go P6N on; want "no load, no gameplay: not routed" 0 "CLASS NOT_ROUTED"
  grep -q 'phase2 appended' "$R/P6N-phase2-done.txt" 2> /dev/null && bad "inputs appended without a load" || ok "no load: inputs not appended"
fi
if t evidence; then
  reset; echo rt-off > "$F/scn"; go P7N on; want "RT-off line: invalid" 0 "CLASS INVALID"
  reset; echo "crash-target rt-off" > "$F/scn"; go P7F on; want "RT-off line with the crash: invalid" 0 "CLASS INVALID"
  reset; echo "no-journal" > "$F/scn"; go P7N on; want "no journal: invalid" 0 "CLASS INVALID"
  reset; echo no-log > "$F/scn"; echo oldlog > "$W/old.log"; go P7N on; want "no log of this run: invalid" 0 "CLASS INVALID"; grep -q 'no play log of this run\|fix line' "$R/P7N-check.txt" && ok "no log: named" || bad "no log reason"
  reset; mkdir -p "$H/bc5-data/captures/play-20261031-0001/gc"; echo "$H/bc5-data/captures/play-20261031-0001/gc" > "$F/old-gc"; go P7N on; want "a journal directory from before: invalid" 0 "CLASS INVALID"; grep -q 'older than this run' "$R/P7N-end.txt" && ok "old journal: named" || bad "old journal reason"
  rm -rf "$H/bc5-data/captures/play-20261031-0001"
  reset; echo OFF > "$F/fixline"; go P7F on; want "the log says the other arm: invalid" 0 "CLASS INVALID"
  reset; echo 'BC5_DIRECT_ZERO_SKIP=1' > "$F/env-add"; go P7N on; want "a forbidden option: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; echo 'KYTY_BC5_RT=0' > "$F/env-add"; go P7N on; want "RT off in the environment: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; echo 'KYTY_BC5_JOB_ARENA_FIX=0' > "$F/env-add"; go P7N on; want "the environment says the other arm: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; touch "$F/exe-wrong"; go P7N on; want "another exe: invalid" 0 "CLASS INVALID"
fi
if t kernel; then
  reset; echo kern-late > "$F/scn"; go P8N on; want "a kernel line: stop, the whole stream has it" 2 "an amdgpu line in the kernel stream"; case "$out" in *"CLASS KERNEL"*) ok "a kernel line: classed" ;; *) bad "kernel class" ;; esac
  reset; echo core-late > "$F/scn"; go P8N on; want "a devcoredump: stop" 0 "CLASS KERNEL"
fi
if t ssh; then
  reset; echo 8 > "$F/ssh-drop"; echo 11 > "$F/ssh-back"; go PAN on; want "a dropped ssh during the polls: the result arrives" 0 "CLASS NO_CRASH"; case "$out" in *"polls had no answer"*) ok "dropped ssh: reported" || true ;; *) bad "dropped ssh not reported: $(echo "$out" | tail -2)" ;; esac
  reset; echo 8 > "$F/ssh-drop"; out=$(D19_RUN_FAKE=$F/runfake.sh; sed 's/RESULT_GRACE=6/RESULT_GRACE=-430/' "$F/runfake.sh" > "$F/runfake2.sh"; D19_RUN_FAKE=$F/runfake2.sh timeout 200 bash "$RUND/go0390.sh" PBN on $(($(date +%s) + 440)) 2>&1); rc=$?
  case "$rc:$out" in 3:*UNKNOWN*) ok "ssh gone for good: unknown, no retry" ;; *) bad "ssh gone: rc $rc $(echo "$out" | tail -2 | cut -c1-160)" ;; esac
  for i in $(seq 1 240); do [ -e "$R/PBN-done.txt" ] && break; sleep 0.5; done
  [ ! -s "$W/BOX-LOCK" ] && grep -q 'lock released' "$R/PBN-done.txt" && ok "ssh gone: the box ended the run and freed its lock" || bad "ssh gone: box [$(cat "$W/BOX-LOCK")] $(cat "$R/PBN-done.txt" 2> /dev/null)"
  clean && ok "ssh gone: no process left" || bad "ssh gone: processes"
  reset; touch "$F/scp-fail"; go PCN on; want "a failed send gives the lock back" 2 "the send failed"
  reset; echo 1 > "$F/ssh-drop"; echo 2 > "$F/ssh-back"; go PDN on; want "the compare of the sent files lost: lock back" 2 "the sent files differ"
fi
if t signal; then
  reset; echo > "$F/x"; TOK=""; D19_RUN_FAKE=$F/runfake.sh timeout 200 bash "$RUND/go0390.sh" PEN on $(($(date +%s) + 700)) > "$F/go.out" 2>&1 & gp=$!
  for i in $(seq 1 1000); do [ -n "$(ls "$F/emus" 2> /dev/null)" ] && break; sleep 0.1; done
  sleep 1
  for p in $(ps -ef | grep "run0390.sh run" | grep -F "$(basename "$T")" | grep -v 'timeout -k' | grep -v grep | awk '{print $2}'); do kill -TERM "$p" 2> /dev/null; done
  wait "$gp"; rc=$?
  [ "$rc" = 2 ] && grep -q 'signal\|ABORT\|no result' "$F/go.out" && [ ! -s "$W/BOX-LOCK" ] && ok "a stop signal: emulator reaped, lock freed" || bad "signal: rc $rc lock [$(cat "$W/BOX-LOCK")] $(tail -2 "$F/go.out" | cut -c1-160)"
  clean && ok "a stop signal: no process left" || bad "signal: processes"
fi
if t recover; then
  reset; TOK=$(HOME=$H D19_WORK=$W D19_FAKE=$F/fake.sh bash -s -- claim PFN on $(($(date +%s) + 700)) < "$RUND/run0390.sh" | sed -n 's/^TOK=//p')
  [ -n "$TOK" ] && [ -s "$W/BOX-LOCK" ] && ok "claim alone holds the lock" || bad "claim"
  r=$(HOME=$H D19_WORK=$W D19_FAKE=$F/fake.sh bash -s -- release "$TOK" < "$RUND/run0390.sh" 2>&1); [ ! -s "$W/BOX-LOCK" ] && ok "release frees its own lock" || bad "release: $r"
  echo "$FOREIGN" > "$W/BOX-LOCK"; r=$(HOME=$H D19_WORK=$W D19_FAKE=$F/fake.sh bash -s -- release "$TOK" < "$RUND/run0390.sh" 2>&1)
  [ "$(cat "$W/BOX-LOCK")" = "$FOREIGN" ] && ok "release never touches a foreign line" || bad "release foreign"
fi
if t contain; then
  sed -n '/^contained() {/,/^}/p' "$HERE/s6n0390.sh" > "$F/contained.sh"
  ( . "$F/contained.sh"; EX=$T/cx; mkdir -p "$EX/a" "$T/out"; contained "$EX/a" ) && ok "contained: inside" || bad "contained inside"
  ( . "$F/contained.sh"; EX=$T/cx; contained "$T/out" ) && bad "contained: outside passed" || ok "contained: outside stops"
  ( . "$F/contained.sh"; EX=$T/cx; contained "$EX/a/none" ) && ok "contained: a new path passes" || bad "contained: new"
  MSYS=winsymlinks:nativestrict ln -s "$T/out" "$T/cx/l" 2> /dev/null
  if [ -L "$T/cx/l" ]; then ( . "$F/contained.sh"; EX=$T/cx; contained "$T/cx/l" ) && bad "contained: link passed" || ok "contained: a link stops"; else echo "skip contained link: this filesystem made no symlink"; fi
fi
if t gates; then
  crash() {  # name, added scenario word
    reset; echo "crash-target $2" > "$F/scn"; go PG1 on; want "$1: invalid" 0 "CLASS INVALID"
  }
  crash "a crash with a TIMEOUT line" time-line
  crash "a crash with a new stub" stub-new
  crash "a crash with a forbidden stub" stub-bad
  crash "a crash with an unreadable kernel log" kern-bad
  reset; echo crash-target > "$F/scn"; go PG2 on; want "a clean crash still classes" 0 "CLASS CRASH_TARGET fix on crash target reached 1"
  [ ! -e "$R/PG2-fdinfo.txt" ] || rm "$R/PG2-fdinfo.txt"
  bl=$W/d19/raw/stubs-baseline.txt; chk() { (cd "$RUND" && python check0390.py run PG2 on 1 "$(cygpath -m "$R")" "$bl" | tail -1); }
  case "$(chk)" in *"CLASS CRASH_TARGET"*) ok "a crash needs no second fdinfo read" ;; *) bad "fdinfo: $(chk)" ;; esac
  mv "$R/PG2-probe.txt" "$F/k"; case "$(chk)" in *"CLASS INVALID"*) ok "a crash with a file missing: invalid" ;; *) bad "probe: $(chk)" ;; esac; mv "$F/k" "$R/PG2-probe.txt"
  cp "$R/PG2-reads.txt" "$F/k"; echo "kernel 0 devcore 1" > "$R/PG2-reads.txt"; case "$(chk)" in *"CLASS INVALID"*) ok "a failed read with an empty kernel file: invalid" ;; *) bad "reads: $(chk)" ;; esac; cp "$F/k" "$R/PG2-reads.txt"
  rm "$R/PG2-reads.txt"; case "$(chk)" in *"CLASS INVALID"*) ok "no read record: invalid" ;; *) bad "no reads: $(chk)" ;; esac; cp "$F/k" "$R/PG2-reads.txt"
  echo "bc5-direct: TIMEOUT" > "$R/PG2-probe.txt"; case "$(chk)" in *"CLASS INVALID"*) ok "a crash with a TIMEOUT probe: invalid" ;; *) bad "probe line: $(chk)" ;; esac
fi
if t release; then
  reset; touch "$F/no-clear"; go PH1 on; rm -f "$F/no-clear"; lk=$(cat "$W/BOX-LOCK"); case "$rc:$out" in 2:*"not released cleanly"*) ok "a failed release is not clean" ;; *) bad "no-clear: rc $rc $(echo "$out" | tail -2 | cut -c1-160)" ;; esac; case "$lk" in *"token "*) ok "a failed release: the line stays for recovery" ;; *) bad "no-clear lock [$lk]" ;; esac
  reset; echo queue-late > "$F/scn"; go PH2 on; rmdir "$W/BOX-QUEUE"; case "$rc:$out" in 2:*"not released cleanly"*) ok "a failed queue write is not clean" ;; *) bad "queue: rc $rc $(echo "$out" | tail -2 | cut -c1-160)" ;; esac; case "$(cat "$R/PH2-done.txt")" in *"lock kept"*) ok "a failed queue write: lock kept, said so" ;; *) bad "queue done: $(cat "$R/PH2-done.txt")" ;; esac
fi
if t storage; then
  reset; echo disk-late > "$F/scn"; go PI1 on; want "the disk crosses 80 % during the run: stopped" 0 "CLASS INVALID"; grep -q 'the disk is at 85' "$R/PI1-end.txt" && ok "disk: named" || bad "disk reason"; clean && ok "disk: emulator stopped" || bad "disk: processes"
  reset; echo nodisk-late > "$F/scn"; go PI2 on; want "the disk cannot be read: stopped" 0 "CLASS INVALID"; grep -q 'the disk is at unknown' "$R/PI2-end.txt" && ok "disk unread: named" || bad "disk unread reason"
  reset; printf '%s\n' "$FOREIGN" > "$F/lock-at-sampler"; go PI3 on; want "lock lost just before the launch: no launch, line kept" 2 "not ours" "$FOREIGN"; [ ! -e "$F/clock" ] && ok "lock lost before the launch: no emulator" || bad "launched after the loss"; rm -f "$F/lock-at-sampler"
  o=$(grep -c 'box "bash ~/$S/run0390.sh stream' "$RUND/go0390.sh"); [ "$o" = 0 ] && ok "the stream is not under the short ssh cap" || bad "stream cap"
  a=$(sed -n 's/^SECS=\([0-9]*\); RUN_MIN=\([0-9]*\); RUN_CAP=\([0-9]*\); KEEP=\([0-9]*\); OUTER_END=\([0-9]*\).*/\3 \4 \5/p' "$RUND/run0390.sh"); set -- $a; [ $((30 + 30 + 40)) -le $(($2 - $3 + 60)) ] && ok "the kill, reap and release fit inside the outer limit" || bad "budget $a"
fi
if t arms; then
  reset; go Q1N on; want "arm Q: no crash through the cap" 0 "CLASS NO_CRASH fix on crash none reached 1"
  grep -q 'KYTY_BC5_APR_PARK_TO_WORKER=1' "$R/Q1N-start.txt" && ok "arm Q: the switch is in the start file" || bad "arm Q: start file"
  grep -q 'APR wait thread: absent' "$R/Q1N-check.txt" && ok "arm Q: the thread list says absent" || bad "arm Q: thread list"
  reset; go P2N on; want "arm P: no crash through the cap" 0 "CLASS NO_CRASH fix on crash none reached 1"
  grep -q 'KYTY_BC5_APR_PARK_TO_WORKER' "$R/P2N-start.txt" && bad "arm P: the switch is set" || ok "arm P: no switch"
  reset; echo 'KYTY_BC5_APR_PARK_TO_WORKER=1' > "$F/env-add"; go P3N on; want "arm P with the switch in the environment: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; echo 'KYTY_BC5_APR_PARK_TO_WORKER=0' > "$F/env-add"; go Q3N on; want "arm Q with the switch at 0: invalid" 0 "CLASS INVALID"; rm -f "$F/env-add"
  reset; printf '      1 bc5-apr-q1\n      1 bc5-apr-wait\n' > "$F/apr-threads"; go P4N on; want "the wait thread ran: the run still classes" 0 "CLASS NO_CRASH"
  grep -q 'APR wait thread: present' "$R/P4N-check.txt" && ok "the wait thread ran: reported" || bad "wait thread: not reported"
  reset; : > "$F/apr-threads"; go P5N on; want "no thread list: the run still classes" 0 "CLASS NO_CRASH"
  grep -q 'APR wait thread: not read' "$R/P5N-check.txt" && ok "no thread list: not read, not absent" || bad "thread list: reported as a zero"
  reset; go P6N on; touch -d '2020-01-01 00:00:00' "$R/P6N-apr-threads.txt"; (cd "$RUND" && python check0390.py run P6N on 0 "$(cygpath -m "$R")" "$W/d19/raw/stubs-baseline.txt") > "$F/stale" 2>&1
  grep -q 'APR wait thread: not read' "$F/stale" && ok "a thread list older than the run: not read" || bad "stale thread list: $(grep 'APR wait' "$F/stale")"
fi
if t rule; then
  ru() { printf '%s\n' "$@" > "$F/rows"; python "$RUND/check0390.py" rule "$F/rows"; }
  A="P1 on NO_CRASH none"; B="Q1 on NO_CRASH none"
  case "$(ru "$A" "$B")" in *"RULE PASS"*) ok "rule: both arms clean" ;; *) bad "rule pass" ;; esac
  case "$(ru "$A" "Q1 on CRASH_OTHER other")" in *"RULE FAIL Q1"*) ok "rule: a crash in one arm" ;; *) bad "rule fail" ;; esac
  case "$(ru "$A" "Q1 on NOT_ROUTED none")" in *"RULE FAIL Q1"*) ok "rule: a run that did not reach the fight is no pass" ;; *) bad "rule not routed" ;; esac
  case "$(ru "$A")" in *"RULE OPEN no run of arm Q"*) ok "rule: one arm proves nothing" ;; *) bad "rule open" ;; esac
fi
if t series; then
  cat > "$F/go-stub.sh" <<EOF
#!/usr/bin/env bash
echo "\$1 \$2" >> "$F/go-calls"
c=\$(cat "$F/go-plan-\$1" 2> /dev/null); [ -n "\$c" ] || c="NO_CRASH none"
echo "RESULT \$1 runner 0 check 0 CLASS \${c% *} fix \$2 crash \${c#* } reached 1"
[ ! -e "$F/go-rc-\$1" ] || exit "\$(cat "$F/go-rc-\$1")"
EOF
  sed "s#^GO=.*#GO=$F/go-stub.sh#" "$RUND/series0390.sh" > "$F/series.sh"; sed -i 's#HERE=$(cd "$(dirname "$0")" \&\& pwd)#HERE='"$RUND"'#' "$F/series.sh"
  rm -f "$F"/go-calls "$F"/go-plan-* "$F"/go-rc-*
  o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 0 ] && [ "$(tr '\n' ' ' < "$F/go-calls")" = "P1 on Q1 on " ] && case "$o" in *"RULE PASS"*) true ;; *) false ;; esac && ok "series: one run of each arm, the rule" || bad "series: rc $rc $(echo "$o" | tail -2 | cut -c1-160)"
  rm -f "$F/go-calls"; echo "CRASH_TARGET target" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 1 ] && ok "series: a crash at the site stops it" || bad "series target: rc $rc"
  rm -f "$F/go-calls" "$F/go-plan-P1"; echo "NOT_ROUTED none" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); [ "$(grep -c '^P1R' "$F/go-calls")" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 3 ] && case "$o" in *"RULE PASS"*) true ;; *) false ;; esac && ok "series: one replacement" || bad "series replacement: $(tr '\n' ' ' < "$F/go-calls")"
  rm -f "$F/go-calls"; echo "NOT_ROUTED none" > "$F/go-plan-Q1"; o=$(bash "$F/series.sh" 2>&1); [ "$(grep -c 'R ' "$F/go-calls")" = 1 ] && ok "series: only one replacement in all" || bad "series two: $(tr '\n' ' ' < "$F/go-calls")"
  rm -f "$F/go-calls" "$F"/go-plan-*; echo 2 > "$F/go-rc-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && [ "$(grep -c . "$F/go-calls")" = 1 ] && ok "series: a stopped run ends it, no retry" || bad "series stop: rc $rc"
  rm -f "$F/go-calls" "$F"/go-rc-*; echo "KERNEL none" > "$F/go-plan-P1"; o=$(bash "$F/series.sh" 2>&1); rc=$?; [ "$rc" = 1 ] && ok "series: a kernel class ends it" || bad "series kernel: rc $rc"
fi
echo "== $P passed, $N failed"
[ "$N" = 0 ]
