#!/usr/bin/env bash
# REVIEW-PORTS-32 items 1 and 2, laptop only, no HOME or PATH change.
# Item 2: the real derivation lines of s6n0386.sh on the pinned launcher text, then its real settings loop, start checks and
# restart loop with a stand-in emulator; the test directory stands in for ~/bc5-work by text only.
# Item 1: the real box0386.sh claim with a junction, a file and a dangling path in place of the experiment's directories.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PIN=${D19_PIN_DIR:-C:/Users/kjani/Documents/ChatGPT/BC5/coordination/box-read}
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
P=0; N=0
ok() { P=$((P+1)); echo "ok   $1"; }
bad() { N=$((N+1)); echo "FAIL $1"; }
W=$(cygpath -m "$T/w"); E=$W/exp0386/run; R=$E/raw
mkdir -p "$R" "$W/exp0386/s"
cp "$PIN/play-pkg.sh" "$W/play-pkg.sh"; cp "$PIN/bc5-run.env" "$W/bc5-run.env"
sed -n '/^PLAY_PKG_MD5=/,/^bash -n "\$LAUNCH"/p' "$HERE/s6n0386.sh" > "$T/block.sh"
grep -q 'prestart0386' "$T/block.sh" && ok "the block is the real one" || bad "block"
derive() { LAUNCH_SRC=$1 LAUNCH=$2 R=$R bash -c '. "$1"' _ "$T/block.sh"; }
derive "$W/play-pkg.sh" "$E/l.sh" > "$T/d.out" 2>&1; rc=$?
[ "$rc" = 0 ] && ok "the derivation passes on the pinned text" || bad "derive rc $rc: $(tail -2 "$T/d.out")"
L=$E/l.sh
[ "$(grep -c 'prestart0386.sh || exit 97' "$L")" = 2 ] && ok "two start checks" || bad "checks"
a=$(grep -n 'prestart0386.sh' "$L" | head -1 | cut -d: -f1); b=$(grep -n '^  done < "\$PKG_ENV"$' "$L" | cut -d: -f1); c=$(grep -n '^  "\$EMU" --game' "$L" | cut -d: -f1); d=$(grep -n 'prestart0386.sh' "$L" | tail -1 | cut -d: -f1)
[ "$a" -gt "$b" ] && [ "$d" = $((c - 1)) ] && ok "after the last load, and just before the emulator inside the loop" || bad "order $a $b $c $d"
for m in "the pad line missing:/^~\/bc5-work\/pad-volume/d" "the emulator line missing:/^  \"\$EMU\" --game/d" "the emulator line twice:/^  \"\$EMU\" --game/p"; do
  sed "${m#*:}" "$W/play-pkg.sh" > "$T/mut.sh"; s=$(md5sum < "$T/mut.sh" | cut -c1-8); sed "s/^PLAY_PKG_MD5=.*/PLAY_PKG_MD5=$s/" "$T/block.sh" > "$T/block2.sh"
  if o=$(LAUNCH_SRC=$T/mut.sh LAUNCH=$E/m.sh R=$R bash -c '. "$1"' _ "$T/block2.sh" 2>&1); then bad "${m%%:*}: passed"; else case "$o" in *"not started"*) ok "${m%%:*}: not started" ;; *) bad "${m%%:*}: $o" ;; esac; fi
done

# The checks list against the manifest's list.
n=$(python -c "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import d19manifest as m; print(' '.join(m.FORBIDDEN))" "$(cygpath -m "$HERE")")
d=$(sed -n 's/^E0386_DENY="\(.*\)"$/\1/p' "$HERE/prestart0386.sh")
[ "$n" = "$d" ] && ok "the forbidden names are the manifest's" || bad "names differ"

# The sequence of the derived launcher, as text: the settings load to the emulator, ~/bc5-work replaced by the test directory.
pa=$(sed -n 's/^PLAY_ARGS=//p' "$W/bc5-run.env" | tail -1)
mkdir -p "$W/exp0386/s"; sed "s#~/bc5-work#$W#g" "$HERE/prestart0386.sh" > "$W/exp0386/s/prestart0386.sh"
LOCKL='top exp0386 | token 123 | J1N fix on'
{ echo "lock=$LOCKL"
  for w in BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_RING_DEPS=dcb BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8 \
    KYTY_BC5_JOB_ARENA_FIX=1 "KYTY_BC5_INPUT_CONFIG=$E/input-rton.cfg" "KYTY_BC5_SAVEDATA_DIR=$E/wd/_SaveData-pkg-play" "BC5_DIRECT_LEARNED=$E/direct-learned-pkg.txt" D19_OWNER=123 \
    "KYTY_BC5_INPUT_CMD=$E/in-J1N.cmd" "BC5_0358_INPUT_CONFIG=$E/input-rton.cfg" "BC5_EMU=$T/emu" "EMU=$T/emu" "LOG=$E/play-last.log" "ENVF=$W/bc5-run.env" "M=$T/m" "PKG=$T/g.pkg" "HOME=$HOME"; do echo "want=$w"; done
  echo "want=PLAY_ARGS=$pa --fullscreen"
} > "$E/prestart.want"
cat > "$T/emu" <<EOF
#!/usr/bin/env bash
echo run >> "$T/sentinel"
exit \$(cat "$T/emu-rc" 2> /dev/null || echo 0)
EOF
chmod +x "$T/emu"
{ echo 'set -u'
  echo 'export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_RING_DEPS=dcb BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8'
  echo "export KYTY_BC5_JOB_ARENA_FIX=1 KYTY_BC5_INPUT_CONFIG=$E/input-rton.cfg KYTY_BC5_SAVEDATA_DIR=$E/wd/_SaveData-pkg-play BC5_DIRECT_LEARNED=$E/direct-learned-pkg.txt D19_OWNER=123"
  echo "export KYTY_BC5_INPUT_CMD=$E/in-J1N.cmd BC5_0358_INPUT_CONFIG=$E/input-rton.cfg BC5_EMU=$T/emu"
  echo "EMU=$T/emu LOG=$E/play-last.log ENVF=$W/bc5-run.env M=$T/m PKG=$T/g.pkg PLAY_ARGS='$pa --fullscreen'"
  sed -n '/^PKG_ENV=~\/bc5-work\/bc5-pkg.env$/,/prestart0386.sh/p' "$L"
  echo 'echo after-first-check'
  sed -n '/^while :; do$/,/^done$/p' "$L" | grep -v '^done < '
  echo 'exit $RC'
} | sed "s#~/bc5-work#$W#g; s#--game \"\$M\" .*#--game \"\$M\"#" > "$T/seq.sh"
grep -q 'bc5-pkg.env' "$T/seq.sh" && grep -q '"\$EMU" --game' "$T/seq.sh" && ok "the sequence holds the real lines" || bad "sequence"
base() { echo "$LOCKL" > "$W/BOX-LOCK"; rm -f "$T/sentinel" "$T/emu-rc" "$W/bc5-pkg.env" "$E/prestart.out"; }
run() { bash "$T/seq.sh" > "$T/seq.out" 2>&1; }
base; run; rc=$?; [ "$rc" = 0 ] && [ "$(grep -c run "$T/sentinel")" = 1 ] && ok "positive: no bc5-pkg.env, the emulator starts" || bad "positive rc $rc: $(tail -2 "$T/seq.out") $(cat "$E/prestart.out" 2> /dev/null)"
base; printf '# comment\nBC5_DIRECT_DMA_SNAPSHOT=4096\n' > "$W/bc5-pkg.env"; run; rc=$?; [ "$rc" = 0 ] && [ -e "$T/sentinel" ] && ok "positive: a harmless bc5-pkg.env, the emulator starts" || bad "harmless rc $rc: $(cat "$E/prestart.out" 2> /dev/null)"
stop() {  # name, line for bc5-pkg.env
  base; printf '%s\n' "$2" > "$W/bc5-pkg.env"; run; rc=$?
  if [ "$rc" = 97 ] && [ ! -e "$T/sentinel" ] && ! grep -q after-first-check "$T/seq.out" && [ -s "$E/prestart.out" ]; then ok "$1: stopped before any emulator"; else bad "$1: rc $rc sentinel $([ -e "$T/sentinel" ] && echo yes || echo no) $(tail -1 "$T/seq.out" | cut -c1-120)"; fi
}
stop "the save directory redirected" "KYTY_BC5_SAVEDATA_DIR=$W/_SaveData-pkg-play"
stop "the learned file redirected" "BC5_DIRECT_LEARNED=$W/direct-learned-pkg.txt"
stop "the input configuration redirected" "KYTY_BC5_INPUT_CONFIG=$W/input.cfg"
stop "the input script redirected" "KYTY_BC5_INPUT_CMD=$W/x.cmd"
stop "the arm flipped" "KYTY_BC5_JOB_ARENA_FIX=0"
stop "a guard off" "BC5_DIRECT_GPU_CHECK_PRODUCT=0"
stop "the ring changed" "BC5_DIRECT_COMPUTE_RING=0"
stop "RT off" "KYTY_BC5_RT=0"
stop "a forbidden switch, even at 0" "BC5_DIRECT_ZERO_SKIP=0"
stop "the log redirected" "LOG=$W/play-pkg-last.log"
stop "the binary redirected" "EMU=$T/other"
stop "the arguments changed" "PLAY_ARGS=--other"
stop "the token changed" "D19_OWNER=999"
stop "HOME moved" "HOME=$T/elsewhere"
base; echo 'other session | its run' > "$W/BOX-LOCK"; run; rc=$?
[ "$rc" = 97 ] && [ ! -e "$T/sentinel" ] && ok "a foreign lock line at the start: no emulator" || bad "foreign lock rc $rc"
base; : > "$W/BOX-LOCK"; run; rc=$?; [ "$rc" = 97 ] && [ ! -e "$T/sentinel" ] && ok "an empty lock at the start: no emulator" || bad "empty lock rc $rc"
base; rm "$E/prestart.want"; run; rc=$?; [ "$rc" = 97 ] && [ ! -e "$T/sentinel" ] && ok "no want file: no emulator" || bad "no want rc $rc"
# The F2 restart: the second start checks again.
cat > "$T/emu" <<EOF
#!/usr/bin/env bash
echo run >> "$T/sentinel"
echo 'other session | its run' > "$W/BOX-LOCK"
exit 75
EOF
{ echo "lock=$LOCKL"
  for w in BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_RING_DEPS=dcb BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8 \
    KYTY_BC5_JOB_ARENA_FIX=1 "KYTY_BC5_INPUT_CONFIG=$E/input-rton.cfg" "KYTY_BC5_SAVEDATA_DIR=$E/wd/_SaveData-pkg-play" "BC5_DIRECT_LEARNED=$E/direct-learned-pkg.txt" D19_OWNER=123 "EMU=$T/emu"; do echo "want=$w"; done
} > "$E/prestart.want"
base; run; rc=$?; [ "$rc" = 97 ] && [ "$(grep -c run "$T/sentinel")" = 1 ] && ok "the restart checks again: a lost lock stops the second start" || bad "restart rc $rc, runs $(grep -c run "$T/sentinel" 2> /dev/null)"
base; sed -i 's/^want=EMU=.*/want=EMU=wrong/' "$E/prestart.want"; run; rc=$?; [ "$rc" = 97 ] && ok "a wanted value that differs stops" || bad "wrong want rc $rc"

# Item 1: the real claim. Only the box's process reads are replaced.
F=$T/f; mkdir -p "$F" "$T/out"
cat > "$F/fake.sh" <<EOF
emu_pids() { return 0; }
work_pids() { return 0; }
compress_state() { echo inactive; }
disk_pct() { echo 50; }
hook() { [ ! -e "$F/hook-\$1" ] || . "$F/hook-\$1"; return 0; }
EOF
B=$T/b
claimrun() { D19_WORK=$B D19_FAKE=$F/fake.sh bash -s -- claim JK1 on $(($(date +%s) + 700)) < "$HERE/box0386.sh" 2>&1; }
fresh() { rm -rf "$B" "$T/out" "$F"/hook-*; cmd //c rmdir "$(cygpath -w "$B/exp0386")" > /dev/null 2>&1; mkdir -p "$B" "$T/out"; : > "$B/BOX-LOCK"; echo q > "$B/BOX-QUEUE"; echo sentinel > "$T/out/keep"; }
outside() { [ "$(ls -A "$T/out" | tr -d '\n')" = keep ] && [ "$(cat "$T/out/keep")" = sentinel ]; }
fresh; o=$(claimrun); rc=$?; [ "$rc" = 0 ] && [ -d "$B/exp0386/run/raw" ] && [ -d "$B/exp0386/s" ] && ok "positive: a fresh claim makes its directories" || bad "fresh claim rc $rc: $o"
fresh; touch "$B/exp0386"; o=$(claimrun); rc=$?; case "$rc:$o" in 1:*"is not a directory"*) [ ! -s "$B/BOX-LOCK" ] && ok "a file in the place of the directory: stopped before the lock" || bad "file lock" ;; *) bad "file: $rc $o" ;; esac
rm -f "$B/exp0386"
fresh; cmd //c mklink //J "$(cygpath -w "$B/exp0386")" "$(cygpath -w "$T/out")" > /dev/null 2>&1
if [ -d "$B/exp0386" ]; then
  o=$(claimrun); rc=$?
  case "$rc:$o" in 1:*"is a link"* | 1:*"really elsewhere"*) outside && [ ! -s "$B/BOX-LOCK" ] && ok "a junction at the experiment: stopped, the outside untouched, no lock" || bad "junction: outside or lock changed" ;; *) bad "junction: $rc $o" ;; esac
else echo "skip junction: mklink did not work"; fi
cmd //c rmdir "$(cygpath -w "$B/exp0386")" > /dev/null 2>&1
fresh; mkdir -p "$B/exp0386/run"; cmd //c mklink //J "$(cygpath -w "$B/exp0386/run/raw")" "$(cygpath -w "$T/out")" > /dev/null 2>&1
if [ -d "$B/exp0386/run/raw" ]; then o=$(claimrun); rc=$?; case "$rc" in 1) outside && ok "a junction deeper down: stopped, the outside untouched" || bad "deep junction outside" ;; *) bad "deep junction: $rc $o" ;; esac; else echo "skip deep junction"; fi
cmd //c rmdir "$(cygpath -w "$B/exp0386/run/raw")" > /dev/null 2>&1
fresh; mkdir -p "$B/exp0386/run"; cmd //c mklink //J "$(cygpath -w "$B/exp0386/run/raw")" "$(cygpath -w "$T/gone")" > /dev/null 2>&1
if [ -L "$B/exp0386/run/raw" ]; then o=$(claimrun); rc=$?; [ "$rc" = 1 ] && ok "a dangling junction: stopped" || bad "dangling: $rc $o"; else echo "skip dangling junction: not seen as a link"; fi
cmd //c rmdir "$(cygpath -w "$B/exp0386/run/raw")" > /dev/null 2>&1
fresh; printf 'mkdir -p "%s/x"; rm -rf "$EX"; cmd //c mklink //J "$(cygpath -w "$EX")" "$(cygpath -w "%s")" > /dev/null 2>&1\n' "$T/out" "$T/out" > "$F/hook-after-claim"; rmdir "$T/out/x" 2> /dev/null
o=$(claimrun); rc=$?; rmdir "$T/out/x" 2> /dev/null
[ "$rc" = 1 ] && outside && [ ! -s "$B/BOX-LOCK" ] && ok "a junction appears after the claim: stopped, own lock freed" || bad "late junction: rc $rc [$(ls -A "$T/out" | tr '\n' ' ')] lock [$(cat "$B/BOX-LOCK")] $o"
cmd //c rmdir "$(cygpath -w "$B/exp0386")" > /dev/null 2>&1
fresh; printf 'echo "other session" > "$LOCK"\n' > "$F/hook-after-claim"; o=$(claimrun); rc=$?; [ "$rc" = 1 ] && [ "$(cat "$B/BOX-LOCK")" = "other session" ] && [ ! -e "$B/exp0386" ] && ok "the lock lost after the claim: nothing made, line kept" || bad "lost after claim: rc $rc $o"
echo "== $P passed, $N failed"
[ "$N" = 0 ]
