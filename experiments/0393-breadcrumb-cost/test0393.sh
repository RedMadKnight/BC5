#!/usr/bin/env bash
# Exp 0393 tests, laptop only: the real go0393.sh, run0393.sh, s6n0393.sh and series0393.sh on a stand-in tree under a
# d19-test- path, with the real pinned launcher text and the real unit from patch 0001. Made smaller from exp 0388's
# test0388run.sh. Stand-ins replace ssh, scp and the box's reads; a small script plays the emulator. The run's clock is a
# counter that moves 15 s at each pause.
# usage: bash test0393.sh [name filter]
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
BR=$(cd "$HERE/../.." && pwd)
PIN=${D19_PIN_DIR:-C:/Users/kjani/Documents/ChatGPT/BC5/coordination/box-read}
FILTER=${1:-}
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
F=$T/f; H=$(cygpath -m "$T/h"); W=$H/bc5-work; RUND=$T/run; EX=$W/exp0393; R=$EX/run/raw
mkdir -p "$F/emus" "$RUND"
P=0; N=0
ok() { P=$((P+1)); echo "ok   $1"; }
bad() { N=$((N+1)); echo "FAIL $1"; }
m() { md5sum < "$1" | cut -d' ' -f1; }
stop_all() {
  local p
  for p in $(ls "$F/emus" 2> /dev/null); do kill -9 "$p" 2> /dev/null; done
}
trap 'stop_all; [ -n "${D19_KEEP:-}" ] && echo "kept $T" || rm -rf "$T"' EXIT
cp "$HERE"/run0393.sh "$HERE"/go0393.sh "$HERE"/series0393.sh "$HERE"/s6n0393.sh "$HERE"/prestart0393.sh "$HERE"/patch0393.py "$HERE"/patch0277.py "$HERE"/build0393.py "$RUND/"

cat > "$F/emu.sh" <<'EOF'
# The emulator. Arguments: dir of stand-ins, journal, log, token, breadcrumb level.
F=$1; J=$2; L=$3; TOK=$4; LV=$5; me=$$
mv "$F/env-new" "$F/env-$me"; echo "$TOK" > "$F/emus/$me"
S=$(cat "$F/scn" 2> /dev/null)
echo "started" > "$L"
[ "$LV" = 0 ] || case " $S " in *" bc-none "*) ;; *) echo "breadcrumbs (exp 0277): level $LV, 1048576 slots at 0x7f0000000000 (device 1)" >> "$J" ;; esac
case " $S " in *" bc-stray "*) echo "breadcrumbs (exp 0277): level 1, 1048576 slots at 0x7f0000000000 (device 1)" >> "$J" ;; esac
case " $S " in *" rt-off "*) echo "ray tracing off: dropped" >> "$J" ;; esac
n=0
while :; do
  n=$((n + 1))
  for i in 1 2 3 4 5; do echo "frame profile: t $n.$i s, 24.5 ms since the last flip; game thread inside the host 3.0 ms (sync 0.1, hints 0.1, prepare 2.5, list 0.2, cs 1.5, fence 0.0, cap 0.0, label waits 0.0, event waits 0.0), at the flip 0.3, outside -1.0; GPU busy 19.0 ms in 12 jobs (+3 from the ring thread); soft-CP passes 0.4 ms in 5, waits polled 9 (0.2 ms, 0 timed out); prepare = filter 1.0 + tracker 0.2 + cu 0.1 + nested 0.1 + copy 0.5"; echo "timing: t $n.$i s, VideoOutSubmitFlip took 1.0 ms"; done >> "$J"
  [ "$LV" = 0 ] || case " $S " in *" bc-none "*) ;; *) echo "breadcrumbs (exp 0277): $((n * 100)) inserted, 40000 a second; of 4096 that followed the previous line, 4096 reached and 4096 done" >> "$J" ;; esac
  case " $S " in
    *" kern "*) [ "$n" -lt 3 ] || { echo 'amdgpu ring timeout' >> "$F/kern"; S=done; } ;;
    *" crash "*) [ "$n" -lt 3 ] || { echo "Access violation: Read [000000000000000c] " >> "$L"; rm -f "$F/emus/$me"; exit 65; } ;;
  esac
  touch "$L"; sleep 0.5
done
EOF

cat > "$F/fake.sh" <<EOF
F=$F
EOF
cat >> "$F/fake.sh" <<'EOF'
T_ROUTE=15; T_FD=60; T_POLL=1; T_KERN=1; T_KILL=0.1; T_SETTLE=0.1
REAP_TERM=4; REAP_KILL=4
el() { cat "$F/clock" 2> /dev/null || echo 0; }
pause() { [ "${1:-}" = 0.5 ] || echo $(($(el) + 15)) > "$F/clock"; sleep 0.05; }
emu_pids() { local p; for p in $(ls "$F/emus" 2> /dev/null); do if kill -0 "$p" 2> /dev/null; then echo "$p"; else rm -f "$F/emus/$p" "$F/env-$p"; fi; done; return 0; }
work_pids() { return 0; }
nice() { shift 2; "$@"; }
compress_state() { cat "$F/svc"; }
disk_pct() { cat "$F/disk"; }
session() { "$@"; }
kstream() { local i; for i in $(seq 1 "$1"); do cat "$F/kern" 2> /dev/null; sleep 1; done; }
clear_lock() { : > "$LOCK"; }
own_pids() { local p; for p in $(emu_pids); do [ "$(cat "$F/emus/$p" 2> /dev/null)" = "$TOK" ] && echo "$p"; done; return 0; }
hook() { return 0; }
env_raw() { cat "$F/env-$1"; }
exe_of() { echo "$D19_BIN"; }
exe_md5() { echo "$WANT"; }
cwd_of() { readlink -f "$WD"; }
alive() { kill -0 "$1" 2> /dev/null; }
fdinfo_of() { printf '      1 drm-engine-gfx:\t%d000000000 ns\n' "$(($(el) + 1))"; }
kern() { cat "$F/kern" 2> /dev/null; return 0; }
mount_opts() { echo rw,relatime; }
route_read() { [ -e "$F/no-route" ] || echo "$SROOT/PPSA03671/a"; }
sampler() { SP=""; }
devcores() { cat "$F/devcore" 2> /dev/null; return 0; }
box_settings() { echo settings; }
boot_line() { echo "boot abcd1234, up since 2026-10-31 10:00:00"; }
strings() { echo "breadcrumbs (exp 0277): x"; }
distrobox() {
  case " $* " in
    *" ninja -t compdb "*) printf '%s\n' '[{ "command": "c++ -c x", "output": "src/kyty_emulator" }]' ;;
    *) [ -e "$F/build-bad" ] && return 1; [ -e "$F/build-eats-shared" ] && echo changed >> "$W/kytyplus-build/src/kyty_emulator"; printf "#!/bin/sh
" > "$EX/kyty_emulator"; echo "warning: one" ;;
  esac
}
launch() {
  local n GC w lv=0; rm -f "$F/clock"
  n=$(cat "$F/gcn" 2> /dev/null || echo 1000); echo $((n + 1)) > "$F/gcn"
  GC=$HOME/bc5-data/captures/play-20261101-$n/gc; mkdir -p "$GC"
  case "$SWITCHES" in *=1) lv=1 ;; *=2) lv=2 ;; esac
  { for w in "${WANTENV[@]}"; do printf '%s\0' "$w"; done; printf 'BC5_GC_DUMP_DIR=%s\0' "$GC"
    [ ! -e "$F/env-add" ] || printf '%s\0' "$(cat "$F/env-add")"; } > "$F/env-new"
  echo "launcher exit 0" > "$R/$TAG-launch.out"
  nohup bash "$F/emu.sh" "$F" "$GC/direct.log" "$LOG" "$OWNER" "$lv" > /dev/null 2>&1 < /dev/null &
}
EOF

cat > "$F/ssh" <<EOF
#!/usr/bin/env bash
F=$F; H=$H
EOF
cat >> "$F/ssh" <<'EOF'
while [ "${1:-}" = -o ]; do shift 2; done
shift
HOME=$H D19_WORK=$H/bc5-work D19_FAKE=$F/fake.sh exec bash -c "$*"
EOF
cat > "$F/scp" <<EOF
#!/usr/bin/env bash
H=$H; F=$F
EOF
cat >> "$F/scp" <<'EOF'
shift
files=(); d=""
for a in "$@"; do case "$a" in bc250:*) d=${a#bc250:} ;; *) files+=("$a") ;; esac; done
cp "${files[@]}" "$H/$d"
EOF
chmod +x "$F/ssh" "$F/scp"
cat > "$F/runfake.sh" <<EOF
SSH=$F/ssh; SCP=$F/scp; POLL=1; RESULT_GRACE=6; SHORT=120
EOF

mkdir -p "$W/kytyplus-build/src/CMakeFiles/kyty_emulator.dir/libs" "$H/src/KytyPlus/src/libs" "$W/_SaveData/PPSA03671" "$W/exp0196/saves-before-152617/PPSA03671" "$W/exp0203" "$W/exp0330/wd" "$H/bc5-data/captures/devcoredump"
echo live > "$W/_SaveData/PPSA03671/a"
echo route > "$W/exp0196/saves-before-152617/PPSA03671/a"
mkdir -p "$EX"; echo built > "$EX/kyty_emulator"
echo shared > "$W/kytyplus-build/src/kyty_emulator"; echo o > "$W/kytyplus-build/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
cp "$PIN/play-pkg.sh" "$W/play-pkg.sh"; cp "$PIN/bc5-run.env" "$W/bc5-run.env"
echo 'wait 85000' > "$W/exp0203/o2-continue.cmd"
echo 'RayTracing.PPSA03671=on' > "$W/input.cfg"; echo 0x1100000000 > "$W/direct-learned-pkg.txt"
printf '#!/bin/sh\n' > "$W/exp0330/sample0330.sh"; chmod +x "$W/exp0330/sample0330.sh" "$W/play-pkg.sh"
python - "$BR/backend/kytyplus-patches/0001-bc5-lle-agc.patch" "$H/src/KytyPlus/src/libs/bc5LleAgc.cpp" <<'EOF'
import sys
b = open(sys.argv[1], 'rb').read().split(b'\n')
i = next(n for n, l in enumerate(b) if l.startswith(b'diff --git a/src/libs/bc5LleAgc.cpp'))
j = next(n for n in range(i, i + 12) if b[n].startswith(b'@@'))
c = int(b[j].split(b'+')[1].split(b',')[1].split(b' ')[0])
open(sys.argv[2], 'wb').write(b'\n'.join(l[1:] for l in b[j + 1:j + 1 + c]) + b'\n')
EOF
route_c() { (cd "$W/exp0196/saves-before-152617" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }
{ echo "BINARY=$(m "$EX/kyty_emulator")"; echo "LAUNCHER=$(m "$W/play-pkg.sh")"; echo "RUN_ENV=$(m "$W/bc5-run.env")"
  echo "ROUTE_SAVES=$(route_c)"; echo "MENU_CMD=$(m "$W/exp0203/o2-continue.cmd")"
  echo "INPUT_CFG=$(m "$W/input.cfg")"; echo "LEARNED=$(m "$W/direct-learned-pkg.txt")"
} > "$RUND/pins0393.env"
cp "$RUND/pins0393.env" "$F/pins.good"

[ "$(m "$PIN/play-pkg.sh" | cut -c1-8)" = 55531ab6 ] && ok "the launcher text is the pinned one" || bad "launcher pin"
reset() {
  stop_all; sleep 0.1
  rm -rf "$F/emus" "$F"/env-* "$F/scn" "$F/kern" "$F/devcore" "$F/no-route" "$F/clock" "$F/build-bad" "$F/build-eats-shared" "$EX/run"
  mkdir -p "$F/emus"; echo built > "$EX/kyty_emulator"; echo shared > "$W/kytyplus-build/src/kyty_emulator"
  : > "$W/BOX-LOCK"; echo q > "$W/BOX-QUEUE"; rm -rf "$W/BOX-LOCK.d19-claim"
  echo inactive > "$F/svc"; echo 50 > "$F/disk"
  cp "$F/pins.good" "$RUND/pins0393.env"; echo live > "$W/_SaveData/PPSA03671/a"
}
go() {  # tag: sets out and rc
  out=$(D19_RUN_FAKE=$F/runfake.sh timeout 280 bash "$RUND/go0393.sh" "$1" "$(($(date +%s) + ${DLS:-900}))" 2>&1); rc=$?
}
want() {  # name, expected rc, text in the output, expected lock text ('' free)
  local lk; lk=$(cat "$W/BOX-LOCK" 2> /dev/null)
  case "$out" in *"$3"*) ;; *) bad "$1: output lacks [$3] rc $rc: $(echo "$out" | tail -4 | cut -c1-200 | tr '\n' '~')"; return ;; esac
  [ "$rc" = "$2" ] || { bad "$1: rc $rc, want $2: $(echo "$out" | tail -3 | cut -c1-200 | tr '\n' '~')"; return; }
  [ "$lk" = "${4:-}" ] || { bad "$1: lock [$lk]"; return; }
  ok "$1"
}
t() { case "$1" in *"$FILTER"*) return 0 ;; *) return 1 ;; esac; }

if t arms; then
  reset; go O1; want "off arm passes" 0 "verdict pass"
  ! grep -q BREADCRUMBS "$R/O1-start.txt" && ok "off arm: no switch in the start file" || bad "off arm switch"
  [ "$(cat "$W/_SaveData/PPSA03671/a")" = live ] && ok "off arm: live saves untouched" || bad "live saves"
  [ -s "$R/O1-frames.txt" ] && [ ! -s "$R/O1-bc.txt" ] && ok "off arm: frames kept, no breadcrumb line" || bad "off arm files"
  grep -q 'done: O1' "$W/BOX-QUEUE" && ok "off arm: queue line" || bad "off queue"
  reset; go L1; want "level 1 passes" 0 "verdict pass"
  grep -q 'BC5_DIRECT_BREADCRUMBS=1' "$R/L1-start.txt" && [ -s "$R/L1-bc.txt" ] && ok "level 1: the switch and health lines" || bad "level 1 files"
  reset; go T1; want "level 2 passes" 0 "verdict pass"
  grep -q 'level 2, ' "$R/T1-bc.txt" && ok "level 2: its level line" || bad "level 2 files"
  [ "$(grep -c 'exp0393/run/' "$EX/run/play-pkg-0393.sh")" -ge 5 ] && ok "the derived launcher has its private paths" || bad "launcher paths"
fi
if t proof; then
  reset; echo bc-none > "$F/scn"; go L2; want "level 1 without lines fails" 0 "no level 1 breadcrumb lines"
  reset; echo bc-stray > "$F/scn"; go O2; want "off arm with lines fails" 0 "breadcrumb lines in an off arm"
  reset; echo 'BC5_DIRECT_BREADCRUMBS=1' > "$F/env-add"; go O3; want "off arm with the variable stops" 0 "breadcrumbs are set in an off arm"
  rm -f "$F/env-add"
  reset; echo rt-off > "$F/scn"; go L3; want "RT off stops" 0 "ray tracing is not on"
fi
if t stops; then
  reset; echo kern > "$F/scn"; go L4; want "a kernel line ends the run" 2 "an amdgpu line in the kernel stream"
  case "$out" in *"verdict HANG"*) ok "kernel line: HANG in the result" ;; *) bad "kernel line result" ;; esac
  reset; echo crash > "$F/scn"; go L5; want "a crash is reported" 0 "verdict CRASH"
  reset; touch "$F/no-route"; go L6; want "no route save read stops" 0 "route save was not read"
  reset; echo x >> "$EX/kyty_emulator"; go L7; want "wrong binary stops" 2 "no result file"
  grep -q 'binary is not' "$R/L7-done.txt" && ok "wrong binary: named" || bad "wrong binary reason"
  reset; sed -i 's/^MENU_CMD=.*/MENU_CMD=FILL/' "$RUND/pins0393.env"; go L8; want "an unfilled pin stops" 2 "no result file"
  reset; echo active > "$F/svc"; go L9; want "compression active: not claimed" 2 "compression job"
  reset; echo 'other session | its run' > "$W/BOX-LOCK"; go O4; want "a foreign lock is left alone" 2 "foreign lock" 'other session | its run'
  reset; go O5; go O5; want "a used tag is refused" 2 "was used"
fi
if t build; then
  reset; rm -f "$EX/kyty_emulator"; go build; want "the build passes" 0 "RESULT build binary"
  [ -s "$EX/src/bc5LleAgc.bc.cpp" ] && [ "$(m "$EX/src/bc5LleAgc.bc.cpp")" = 1ed25bdfab48521854033f702b3bfc20 ] && ok "build: the patched unit" || bad "patched unit"
  grep -q '^+.*bc_emit' "$R/patch_0393.diff" && ok "build: the diff" || bad "build diff"
  reset; touch "$F/build-bad"; go build2; want "a failed build releases" 2 "no result file"
  grep -q 'the build failed' "$R/build2-done.txt" && ok "failed build: named" || bad "failed build reason"
  reset; touch "$F/build-eats-shared"; go build3; want "a changed shared binary stops" 2 "no result file"
  cp "$H/src/KytyPlus/src/libs/bc5LleAgc.cpp" "$F/unit"; echo x >> "$H/src/KytyPlus/src/libs/bc5LleAgc.cpp"
  reset; go build4; want "another tree stops" 2 "no result file"
  grep -q "is not 29b3d8c6" "$R/build4-done.txt" && ok "another tree: named" || bad "tree reason"
  cp "$F/unit" "$H/src/KytyPlus/src/libs/bc5LleAgc.cpp"
fi
if t series; then
  reset; rm -f "$RUND/raw/series.txt"; o=$(D19_RUN_FAKE=$F/runfake.sh timeout 280 bash "$RUND/series0393.sh" O6 L10 2>&1); rc=$?
  [ "$rc" = 0 ] && case "$o" in *"every run passed"*) true ;; *) false ;; esac && ok "the series runs its tags" || bad "series: rc $rc $(echo "$o" | tail -2 | cut -c1-200 | tr '\n' '~')"
  reset; echo kern > "$F/scn"; o=$(D19_RUN_FAKE=$F/runfake.sh timeout 280 bash "$RUND/series0393.sh" L11 O7 2>&1); rc=$?
  [ "$rc" = 1 ] && [ ! -e "$R/O7-start.txt" ] && ok "the series stops at the first kernel line" || bad "series stop: rc $rc"
fi
stop_all
echo "$P passed, $N failed"
[ "$N" = 0 ]
