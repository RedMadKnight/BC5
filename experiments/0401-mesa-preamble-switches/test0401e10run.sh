#!/usr/bin/env bash
# Laptop stand-in checks of the e10 runner words (edit_run_e10.py's run0401t.sh): the word parse (each refusal and one
# accepted set), the launcher derivation with and without a private mount, the walk script, the I/O reader.
# usage: test_run_e10.sh <edited run0401t.sh> <laptop copy of the box's play-pkg.sh (97835f88)> <work dir>
set -u
RUN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); PKG=$2; WK=$3
rm -rf "$WK"; mkdir -p "$WK/home"; cd "$WK" || exit 1
pass=0; fail=0
ok() { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1: $2"; }
H=$WK/home
# 1. the parse: run the real script with a fake HOME; every refusal comes before the box's files are needed
parse() {   # <expected text> <args...>
  local want=$1; shift
  local out; out=$(HOME=$H MODE=${M:-route} bash "$RUN" s0 t1 900 600 /nonexistent/kyty_emulator 0123456789abcdef0123456789abcdef "$@" 2>&1 | tail -1)
  case "$out" in *"$want"*) ok "parse [$*] -> $want" ;; *) bad "parse [$*]" "got [$out], want [$want]" ;; esac
}
MB="$H/bc5-work/exp0401e10/mount/bc5-mount"; MD=0123456789abcdef0123456789abcdef
parse "BC5_0401T_LEARNED takes only empty" BC5_0401T_LEARNED=yes
parse "is not md5" BC5_0401T_LEARNED=empty
parse "BC5_0401T_MOUNT names a bc5-mount under" BC5_0401T_MOUNT=/usr/bin/bc5-mount BC5_0401T_MOUNT_MD5=$MD
parse "BC5_0401T_MOUNT names a bc5-mount under" "BC5_0401T_MOUNT=$H/bc5-work/exp0402/bc5-mount" BC5_0401T_MOUNT_MD5=$MD
parse "BC5_0401T_MOUNT is a plain path" "BC5_0401T_MOUNT=$H/bc5-work/exp0401e10/../x/bc5-mount" BC5_0401T_MOUNT_MD5=$MD
parse "BC5_0401T_MOUNT is a plain path" "BC5_0401T_MOUNT=$H/bc5-work/exp0401e10/a b/bc5-mount" BC5_0401T_MOUNT_MD5=$MD
parse "BC5_0401T_MOUNT_MD5 is an md5" "BC5_0401T_MOUNT=$MB" BC5_0401T_MOUNT_MD5=xyz
parse "come together" "BC5_0401T_MOUNT=$MB"
parse "come together" BC5_0401T_MOUNT_MD5=$MD
parse "a BC5_MOUNT_* word needs BC5_0401T_MOUNT" BC5_MOUNT_DIRECT_IO=1
parse "a BC5_MOUNT_* word needs BC5_0401T_MOUNT" BC5_MOUNT_CACHE_MIB=512
parse "BC5_0401T_WALK is 60-1200 s" BC5_0401T_WALK=30
parse "BC5_0401T_WALK is 60-1200 s" BC5_0401T_WALK=1201
parse "BC5_0401T_WALK is 60-1200 s" BC5_0401T_WALK=6x0
parse "the walk is longer than the play" BC5_0401T_WALK=700
M=start parse "BC5_0401T_WALK is for route arms" BC5_0401T_WALK=60
parse "is not md5" "BC5_0401T_MOUNT=$MB" BC5_0401T_MOUNT_MD5=$MD BC5_MOUNT_DIRECT_IO=1 BC5_MOUNT_CACHE_MIB=512 BC5_0401T_WALK=600 BC5_0401T_LEARNED=empty
parse "is not md5" BC5_DIRECT_PROT_CENSUS=1
# the private mount's own pre-check: a mount binary that is not its md5
mkdir -p "$(dirname "$MB")"; printf '#!/bin/sh
# a stand-in mount
' > "$MB";   # Git Bash's -x wants a shebang
 chmod +x "$MB"; RB=$H/bin/kyty; mkdir -p "$H/bin"; printf 'y' > "$RB"
RBM=$(md5sum < "$RB" | cut -d' ' -f1); MBM=$(md5sum < "$MB" | cut -d' ' -f1)
mkdir -p "$H/bc5-work/exp0330" "$H/bc5-work/exp0401e3"; printf '#!/bin/sh\n' > "$H/bc5-work/play-pkg.sh"; cp "$H/bc5-work/play-pkg.sh" "$H/bc5-work/exp0330/sample0330.sh"
chmod +x "$H/bc5-work/play-pkg.sh" "$H/bc5-work/exp0330/sample0330.sh"; : > "$H/bc5-work/direct-learned-pkg.txt"; : > "$H/bc5-work/exp0401e3/freeze-watch.sh"; : > "$H/bc5-work/exp0401e3/freeze-dump.sh"
out=$(HOME=$H MODE=route bash "$RUN" s0 t2 900 600 "$RB" "$RBM" "BC5_0401T_MOUNT=$MB" BC5_0401T_MOUNT_MD5=$MD 2>&1 | tail -1)
case "$out" in *"$MB is not md5 $MD: not started"*) ok "the mount's md5 is checked before the claim" ;; *) bad "mount md5" "[$out]" ;; esac
out=$(HOME=$H MODE=route bash "$RUN" s0 t3 900 600 "$RB" "$RBM" "BC5_0401T_MOUNT=$MB" BC5_0401T_MOUNT_MD5=$MBM 2>&1 | tail -1)
case "$out" in *"no named snapshot"*) ok "a right mount md5 passes to the saves check" ;; *) bad "mount md5 pass" "[$out]" ;; esac
[ ! -e "$H/bc5-work/BOX-LOCK" ] && ok "nothing claimed by the refused starts" || bad "lock" "a BOX-LOCK was made"

# 2. the launcher derivation, as the runner runs it (its own text between chk() and bash -n)
derive() {   # <mount bin or empty> <tag>
  local E=$H/bc5-work/exp0401t R=$WK/r LAUNCH_SRC=${3:-$PKG} LAUNCH=$WK/d.sh MOUNT_BIN=$1 TAG=$2
  local LOGA=${4:-LOG=~/bc5-work/play-pkg-last.log}
  mkdir -p "$R"; cp "$LAUNCH_SRC" "$LAUNCH"
  eval "$(sed -n '/^chk() {/,/^bash -n "\$LAUNCH"/p' "$RUN")"
  echo "NL $NL $(grep -c '^[-+][^-+]' "$R/play-pkg-0401t.diff")"
  grep -n '^BM=\|^MLOG=' "$LAUNCH"
}
o=$(derive "" t4)
case "$o" in *"NL 10 10"*) ok "no mount: the diff is 10 lines" ;; *) bad "derive plain" "$o" ;; esac
echo "$o" | grep -qxF '25:BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount' && ok "no mount: BM unchanged" || bad "BM plain" "$o"
o=$(derive "$MB" t5)
case "$o" in *"NL 14 14"*) ok "a private mount: the diff is 14 lines" ;; *) bad "derive mount" "$o" ;; esac
echo "$o" | grep -qF "BM=$MB  # exp 0401 e10: a private mount" && ok "BM is the private mount" || bad "BM" "$o"
echo "$o" | grep -qF "MLOG=$H/bc5-work/exp0401t/mount-t5.log  # exp 0401 e10: its own mount log" && ok "MLOG is the arm's own" || bad "MLOG" "$o"
bash -n "$WK/d.sh" && ok "the derived launcher parses" || bad "parse" "d.sh"
# the derived launcher, run up to the mount line with a fake mount: does it start the private binary?
grep -n '"$BM" mount' "$WK/d.sh" | grep -q 'MALLOC_ARENA_MAX=2 "$BM" mount "$PKG" "$M"' && ok "the mount line uses \$BM" || bad "mount line" "$(grep -n 'BM' "$WK/d.sh")"

# 2b. exp 0409's launcher (BC5_0401T_LAUNCHER=exp0409): its own LOG line, the same 10-line diff
P409=${P409:-}
if [ -n "$P409" ]; then
  o=$(derive "" t9 "$P409" 'LOG=/home/kjaniszewski/bc5-work/exp0409/play-last.log  # exp 0409: own log')
  case "$o" in *"NL 10 10"*) ok "exp0409 launcher: the diff is 10 lines" ;; *) bad "derive 0409" "$o" ;; esac
  grep -qxF 'LOG=~/bc5-work/exp0401t/play-last.log  # exp 0401t: own log' "$WK/d.sh" && ok "exp0409 launcher: the arm's own log" || bad "LOG 0409" "$(grep -n '^LOG=' "$WK/d.sh")"
  grep -q 'BC5_GAME_DIR' "$WK/d.sh" && bash -n "$WK/d.sh" && ok "exp0409 launcher: BC5_GAME_DIR kept, parses" || bad "0409 parse" "d.sh"
  o=$(HOME=$H MODE=route bash "$RUN" s0 t10 900 600 /nonexistent/kyty_emulator 0123456789abcdef0123456789abcdef BC5_0401T_LAUNCHER=exp0408 2>&1 | tail -1)
  case "$o" in *"BC5_0401T_LAUNCHER takes only exp0409"*) ok "exp0409 launcher: other values refused" ;; *) bad "launcher word" "$o" ;; esac
fi
# 3. the walk script
eval "$(sed -n '/^wk() {/,/^}/p' "$RUN")"
CMD=$WK/in.cmd; : > "$CMD"; WALK=60; n=$(wk)
[ "$n" = 3 ] && ok "60 s: 3 cycles" || bad "wk 60" "$n"
[ "$(grep -c '^stick l 128 0 15000$' "$CMD")" = 3 ] && [ "$(tail -2 "$CMD" | tr '\n' '|')" = "stick l 128 128|stick r 128 128|" ] && ok "60 s: the lines and the centring" || bad "wk lines" "$(cat "$CMD")"
: > "$CMD"; WALK=600; n=$(wk)
[ "$n" = 36 ] && ok "600 s: 36 cycles (36 x 16.5 s = 594 s)" || bad "wk 600" "$n"
sides=$(grep '^stick r ' "$CMD" | grep -v '128 128$' | awk '{print $3}' | head -12 | tr '\n' ' ')
[ "$sides" = "255 255 255 255 0 0 0 0 255 255 255 255 " ] && ok "the turn changes side every fourth cycle" || bad "sides" "$sides"
w=$(awk '$1 == "wait" {s += $2} $1 == "stick" && NF == 5 {s += $5} END {print s}' "$CMD"); [ "$w" = 594000 ] && ok "the walk's script lasts 594 s" || bad "duration" "$w"
grep -qv '^stick \|^wait ' "$CMD" && bad "commands" "$(grep -v '^stick \|^wait ' "$CMD")" || ok "only stick and wait lines"

# 4. the I/O reader, on a stand-in /proc
eval "$(sed -n '/^iof() {/p' "$RUN" | sed "s#/proc/#$WK/proc/#g")"
mkdir -p "$WK/proc/42"; printf 'rchar: 1234\nwchar: 5\nsyscr: 1\nsyscw: 1\nread_bytes: 4096\nwrite_bytes: 0\ncancelled_write_bytes: 0\n' > "$WK/proc/42/io"
[ "$(iof 42)" = "1234 4096" ] && ok "iof reads rchar and read_bytes" || bad "iof" "$(iof 42)"
[ "$(iof 43)" = "? ?" ] && ok "iof: no process gives ? ?" || bad "iof missing" "$(iof 43)"
[ "$(iof "")" = "? ?" ] && ok "iof: no pid gives ? ?" || bad "iof empty" "$(iof "")"
# 5. The named snapshot (exp 0401 e10, LESSONS R45): MODE=name, its refusals, and the gate. The live saves directory is a
# trap here: any read of it shows in the access check at the end.
LIVE_TRAP=$H/bc5-work/_SaveData/PPSA03671; mkdir -p "$LIVE_TRAP"; printf 'live\n' > "$LIVE_TRAP/trap.bin"; chmod 000 "$LIVE_TRAP" 2> /dev/null
ET=$H/bc5-work/exp0401t; mkdir -p "$ET/saves-prev"; printf 'slot four\n' > "$ET/saves-prev/sdata.bin"; mkdir -p "$ET/saves-prev/sub"; printf 'x\n' > "$ET/saves-prev/sub/param.sfo"
WANT=$(cd "$WK" && mkdir -p sumchk/PPSA03671 && cp -a "$ET/saves-prev/." sumchk/PPSA03671/ && cd sumchk && LC_ALL=C find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)
nm() { HOME=$H MODE=name bash "$RUN" "$@" 2>&1 | tail -1; }
o=$(nm "$WANT" nosuch); case "$o" in *"no snapshot $ET/saves-nosuch"*) ok "name: no source snapshot" ;; *) bad "name nosrc" "$o" ;; esac
o=$(nm 0000000000000000 prev); case "$o" in *"not 0000000000000000: removed"*) ok "name: a wrong sum is refused and removed" ;; *) bad "name wrong" "$o" ;; esac
[ ! -e "$ET/saves-named" ] && ok "name: nothing left after a wrong sum" || bad "name left" "$(ls "$ET")"
o=$(nm "$WANT" 'pr ev'); case "$o" in *"letters and digits"*) ok "name: the tag is checked" ;; *) bad "name tag" "$o" ;; esac
o=$(nm "$WANT" prev); case "$o" in *"named snapshot $ET/saves-named/PPSA03671: $WANT"*) ok "name: made, sum $WANT" ;; *) bad "name make" "$o" ;; esac
o=$(nm "$WANT" prev); case "$o" in *"exists: not made again"*) ok "name: never made twice" ;; *) bad "name twice" "$o" ;; esac
# the gate: a wrong sum stops before the claim; the right one passes it
o=$(HOME=$H MODE=route bash "$RUN" 1111111111111111 t6 900 600 "$RB" "$RBM" 2>&1 | tail -1)
case "$o" in *"the named snapshot reads $WANT (LC_ALL=C), not 1111111111111111: not started"*) ok "gate: a wrong sum is refused" ;; *) bad "gate wrong" "$o" ;; esac
[ ! -s "$H/bc5-work/BOX-LOCK" ] && ok "gate: nothing claimed" || bad "gate lock" "$(cat "$H/bc5-work/BOX-LOCK")"
# the right sum: an end-to-end stand-in run with the box's launcher text (97835f88), no emulator ever appearing; shims stand
# in for pgrep/sudo/setsid/distrobox (none of them on the laptop)
mkdir -p "$WK/shim"; for t in pgrep sudo distrobox; do printf '#!/bin/sh\nexit 1\n' > "$WK/shim/$t"; done; printf '#!/bin/sh\nexit 0\n' > "$WK/shim/setsid"; chmod +x "$WK/shim/"*
cp "$PKG" "$H/bc5-work/play-pkg.sh"; mkdir -p "$H/bc5-work/exp0330/wd" "$H/bc5-work/input-dummy"; : > "$H/bc5-work/input.cfg"
o=$(PATH="$WK/shim:$PATH" HOME=$H MODE=route bash "$RUN" "$WANT" t7 900 600 "$RB" "$RBM" 2>&1 | tail -3 | tr '\n' '|')
case "$o" in *"t7 (route): SETUP: no emulator started"*) ok "gate: the right sum runs to the arm's end (no emulator here)" ;; *) bad "gate run" "$o" ;; esac
grep -q "t7 the private copy reset from the named snapshot $WANT" "$ET/raw/saves.txt" && ok "the private copy was reset and hashed" || bad "reset" "$(cat "$ET/raw/saves.txt" 2> /dev/null)"
grep -q "t7 the private copy after the arm: $WANT (unchanged; the named snapshot $WANT)" "$ET/raw/saves.txt" && ok "the copy is hashed after the arm" || bad "after" "$(cat "$ET/raw/saves.txt" 2> /dev/null)"
cmp -s "$ET/saves-prev/sdata.bin" "$ET/wd/_SaveData/PPSA03671/sdata.bin" && ok "the wd holds the named snapshot's files" || bad "wd" "$(ls -R "$ET/wd/_SaveData" | head)"
grep -q "whole run: no fps lines" "$ET/raw/t7-summary.txt" && ok "the summary labels the fps figure whole-run" || bad "label" "$(cat "$ET/raw/t7-summary.txt")"
[ ! -e "$ET/saves-t7" ] && ok "no per-arm snapshot of the live saves" || bad "snap" "saves-t7 exists"
[ ! -s "$H/bc5-work/BOX-LOCK" ] && ok "the lock is free again" || bad "lock after" "$(cat "$H/bc5-work/BOX-LOCK")"
chmod 755 "$LIVE_TRAP" 2> /dev/null
grep -qF "_SaveData/PPSA03671" "$ET/raw/saves.txt" && bad "live path" "saves.txt names the live saves" || ok "saves.txt never names the live saves"
grep -n 'W/_SaveData\|LIVE\|saves()' "$RUN" > /dev/null && bad "live code" "$(grep -n 'W/_SaveData\|LIVE\|saves()' "$RUN")" || ok "no live-save read is left in the runner"

# 6. FPSL, on a stand-in play log: whole run, as labelled
printf 'x [bc5] fps counter: t 10.0 s: 300 flips in 10.0 s, longest gap 50.0 ms\ny [bc5] fps counter: t 20.0 s: 200 flips in 10.0 s, longest gap 150.0 ms\n' > "$WK/fps.log"
R=$WK; TAG=x; eval "$(sed -n '/^FPSL=\$(grep -a "fps counter"/,/^  awk /p' "$RUN" | sed 's#"\$R/\$TAG-play.log"#"$WK/fps.log"#')"
[ "$FPSL" = "whole run: 25.0 flips/s over 20 s, 1 seconds with a gap over 100 ms, longest 150 ms" ] && ok "FPSL: whole run, both lines" || bad "FPSL" "$FPSL"

echo "test_run_e10: $pass of $((pass + fail)); $([ "$fail" = 0 ] && echo end || echo FAILED)"
[ "$fail" = 0 ]
