#!/usr/bin/env bash
# Exp 0391 tests, laptop only, no box: the real run0391.sh on a stand-in tree under a d19-test- path (its claim, start, run,
# result, release and the refusals), with stand-in s6n0391.sh and replug0391.sh that play back exp 0372's P1 files; and
# check0391.py on P1/P2 (PASS), on a read with a pad stream on the dock (FAIL), on a run without a DualSense (NO_TEST) and on
# a missing file (INVALID). The box's reads (pgrep, /proc, setsid, df, systemctl) are replaced through run0391.sh's own
# D19_FAKE hook, which loads only from a d19-test- path. usage: bash test0391.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
P0372=$HERE/../0372-pad-haptics-replug/raw
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-XXXXXX") || exit 1
case "$T" in *d19-test-*) ;; *) echo "no d19-test- path"; exit 1 ;; esac
trap 'rm -rf "$T"' EXIT
P=0; N=0
ok() { P=$((P + 1)); echo "ok   $1"; }
bad() { N=$((N + 1)); echo "FAIL $1"; }
m() { md5sum < "$1" | cut -d' ' -f1; }

# 1. check0391.py on the real files of exp 0372 and on three broken variants.
C=$T/c; mkdir -p "$C"
for X in P1 P2; do
  for f in verdict end replug summary; do cp "$P0372/$X-$f.txt" "$C/"; done
  gzip -dc "$P0372/$X-audio-lines.txt.gz" > "$C/$X-audio-lines.txt"
done
out=$(python -I "$HERE/check0391.py" run P1 pulls 0 "$C"); rc=$?
[ $rc = 0 ] && [ "$(tail -1 <<< "$out")" = "CLASS PASS mode pulls pulls 3" ] && ok "check: P1 is PASS with 3 pulls" || bad "check P1: rc $rc: $(tail -1 <<< "$out")"
out=$(python -I "$HERE/check0391.py" run P2 late 0 "$C"); rc=$?
[ $rc = 0 ] && [ "$(tail -1 <<< "$out")" = "CLASS PASS mode late pulls 1" ] && ok "check: P2 is PASS with 1 pull" || bad "check P2: rc $rc: $(tail -1 <<< "$out")"
# a pad stream linked to the dock in one read
for f in verdict end summary audio-lines; do cp "$C/P1-$f.txt" "$C/D1-$f.txt"; done
sed 's/\(target\.object=alsa_output[^ ]*DualSense[^ ]* .* -> \)[0-9]*:DualSense[^;]*/\154:ThinkPad USB 3.0 Pro Dock Analogowe stereo/' "$C/P1-replug.txt" > "$C/D1-replug.txt"
grep -q "DualSense.* -> 54:ThinkPad" "$C/D1-replug.txt" || bad "the dock variant was not made"
out=$(python -I "$HERE/check0391.py" run D1 pulls 0 "$C"); rc=$?
[ $rc = 1 ] && grep -q "linked to a sink other than the DualSense" <<< "$out" && [ "$(tail -1 <<< "$out")" = "CLASS FAIL mode pulls pulls 3" ] && ok "check: a pad stream on the dock is FAIL" || bad "check D1: rc $rc: $(tail -1 <<< "$out")"
# no DualSense card: the replug script stopped at once
for f in verdict end summary audio-lines; do cp "$C/P1-$f.txt" "$C/N1-$f.txt"; done
echo "01:26:00.000 no DualSense ALSA card in PipeWire: not started" > "$C/N1-replug.txt"
out=$(python -I "$HERE/check0391.py" run N1 pulls 0 "$C"); rc=$?
[ $rc = 0 ] && [ "$(tail -1 <<< "$out")" = "CLASS NO_TEST mode pulls pulls 0" ] && ok "check: no DualSense is NO_TEST" || bad "check N1: rc $rc: $(tail -1 <<< "$out")"
# a failed S6N run with no pulls is FAIL, not NO_TEST
cp "$C/N1-replug.txt" "$C/N2-replug.txt"; for f in end summary audio-lines; do cp "$C/P1-$f.txt" "$C/N2-$f.txt"; done; echo "CRASH: crash lines (1 crash lines)" > "$C/N2-verdict.txt"
out=$(python -I "$HERE/check0391.py" run N2 pulls 1 "$C"); rc=$?
[ $rc = 1 ] && [ "$(tail -1 <<< "$out")" = "CLASS FAIL mode pulls pulls 0" ] && ok "check: a crashed run without pulls is FAIL" || bad "check N2: rc $rc: $(tail -1 <<< "$out")"
# a missing file
out=$(python -I "$HERE/check0391.py" run P9 pulls 0 "$C"); rc=$?
[ $rc = 1 ] && [ "$(tail -1 <<< "$out")" = "CLASS INVALID mode pulls pulls 0" ] && ok "check: a missing file is INVALID" || bad "check P9: rc $rc: $(tail -1 <<< "$out")"
# two pulls instead of three
awk 'BEGIN{n=0} /profile -> 0/{n++; if(n==3){skip=1}} !(skip && /profile -> /){print} /profile -> 1/{if(skip){skip=0}}' "$C/P1-replug.txt" > "$C/T2-replug.txt"
for f in verdict end summary audio-lines; do cp "$C/P1-$f.txt" "$C/T2-$f.txt"; done
out=$(python -I "$HERE/check0391.py" run T2 pulls 0 "$C"); rc=$?
[ $rc = 1 ] && grep -q "2 pulls, want 3" <<< "$out" && ok "check: two pulls of three is FAIL" || bad "check T2: rc $rc: $(tail -1 <<< "$out")"

# 2. run0391.sh on a stand-in tree.
H=$T/h; W=$H/bc5-work; F=$T/f; mkdir -p "$W/kytyplus-build/src" "$W/exp0196/saves-before-152617" "$F"
printf 'shared binary stand-in\n' > "$W/kytyplus-build/src/kyty_emulator"
printf 'launcher stand-in\n' > "$W/play-pkg.sh"; printf 'PLAY_ARGS=x\n' > "$W/bc5-run.env"; printf 'cfg\n' > "$W/input.cfg"; printf 'learned\n' > "$W/direct-learned-pkg.txt"
: > "$W/BOX-LOCK"; : > "$W/BOX-QUEUE"
S=$W/exp0413r/s; mkdir -p "$S"
cp "$HERE/run0391.sh" "$HERE/check0391.py" "$S/"
{ echo "NORMAL8=$(m "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8)"; echo "LAUNCHER=$(m "$W/play-pkg.sh")"; echo "RUN_ENV=$(m "$W/bc5-run.env")"; } > "$S/pins0391.env"
: > "$S/streams0391.py"
# the stand-in S6N run: proves its environment, plays back P1's files under its tag, waits a little
cat > "$S/s6n0391.sh" <<EOF
#!/usr/bin/env bash
TAG=\$1; R=\$D19_WORK/exp0413r/run/raw; mkdir -p "\$R"
{ echo "owner \${D19_OWNER:?} bin \${D19_BIN:?} want \${BC5_0380_WANT:?} lock [\${E0391_LOCKLINE:?}] launcher \${PLAY_PKG_MD5:?} secs \$2"; } > "\$R/\$TAG-env.txt"
[ "\$(cat "\$D19_WORK/BOX-LOCK")" = "\$E0391_LOCKLINE" ] || { echo "lock not ours" > "\$R/\$TAG-verdict.txt"; exit 1; }
echo \$\$ >> "$F/owned"
for f in verdict end summary; do cp "$P0372/P1-\$f.txt" "\$R/\$TAG-\$f.txt"; done
gzip -dc "$P0372/P1-audio-lines.txt.gz" > "\$R/\$TAG-audio-lines.txt"
sleep 2
exit 0
EOF
cat > "$S/replug0391.sh" <<EOF
#!/usr/bin/env bash
TAG=\$1; R=\$D19_WORK/exp0413r/run/raw; mkdir -p "\$R"
echo \$\$ >> "$F/owned"
echo "mode \$2 owner \${D19_OWNER:?} lock [\${E0391_LOCKLINE:?}]" > "\$R/\$TAG-replug-env.txt"
cp "$P0372/P1-replug.txt" "\$R/\$TAG-replug.txt"
exit 0
EOF
chmod +x "$S"/*.sh
# the stand-ins for the box's reads: no emulator, no build, the disk at 10 %, no setsid, our processes from a file
cat > "$T/fake.sh" <<EOF
emu_pids() { cat "$F/emus" 2> /dev/null; return 0; }
work_pids() { :; }
compress_state() { echo inactive; }
disk_pct() { echo 10; }
session() { "\$@"; }
kstream() { sleep "\$1"; }
own_pids() { local p; for p in \$(cat "$F/owned" 2> /dev/null); do [ -d "/proc/\$p" ] && echo "\$p"; done; return 0; }
EOF
run() { D19_WORK=$W D19_FAKE=$T/fake.sh bash "$S/run0391.sh" "$@"; }
DL=$(($(date +%s) + 900))
# a foreign lock refuses the claim and leaves the line
echo "water exp 0389 | N1 lake bench | until 07:13" > "$W/BOX-LOCK"
out=$(run claim T1 pulls "$DL" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "foreign lock" <<< "$out" && [ "$(cat "$W/BOX-LOCK")" = "water exp 0389 | N1 lake bench | until 07:13" ] && ok "claim: a foreign lock is refused and kept" || bad "claim under a foreign lock: rc $rc: $out"
: > "$W/BOX-LOCK"
# an emulator refuses the claim
echo 4242 > "$F/emus"
out=$(run claim T1 pulls "$DL" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "an emulator runs" <<< "$out" && ok "claim: an emulator refuses it" || bad "claim with an emulator: rc $rc: $out"
rm -f "$F/emus"
# too short a deadline
out=$(run claim T1 pulls $(($(date +%s) + 100)) < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "under 840 s left" <<< "$out" && ok "claim: 100 s to the deadline is refused" || bad "claim short: rc $rc: $out"
# a bad mode
out=$(run claim T1 fight "$DL" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "pulls or late" <<< "$out" && ok "claim: a bad mode is refused" || bad "claim bad mode: rc $rc: $out"
# the claim
out=$(run claim T1 pulls "$DL" < /dev/null); rc=$?
TOK=$(sed -n 's/^TOK=\([0-9]*\)$/\1/p' <<< "$out")
L=$(cat "$W/BOX-LOCK")
[ $rc = 0 ] && [ -n "$TOK" ] && case "$L" in "anyps5-ports exp0413r | token $TOK | T1 software replug (pulls), shared 78f25172, RT on, until "*) true ;; *) false ;; esac && ok "claim: the lock holds our line with the token" || bad "claim: rc $rc, token [$TOK], lock [$L]"
grep -qxF -- "$L" "$W/BOX-QUEUE" && ok "claim: the queue has the line" || bad "claim: no queue line"
[ "$(cat "$W/exp0413r/lock-$TOK.line")" = "$L" ] && ok "claim: the token file holds the line" || bad "claim: token file"
# a second claim while ours is held is refused
out=$(run claim T2 pulls "$DL" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "foreign lock" <<< "$out" && ok "claim: a second claim under our lock is refused" || bad "second claim: rc $rc: $out"
# the run (start detaches `run` under timeout; here session is plain)
out=$(run start "$TOK" T1 pulls "$DL"); rc=$?
[ $rc = 0 ] && [ "$out" = started ] && ok "start: confirmed" || bad "start: rc $rc: $out"
R=$W/exp0413r/run/raw
for _ in $(seq 1 60); do [ -s "$R/T1-done.txt" ] && break; sleep 1; done
[ -s "$R/T1-done.txt" ] && ok "run: done file written" || bad "run: no done file; box.out: $(cat "$R/T1-box.out" 2> /dev/null)"
d=$(cat "$R/T1-done.txt" 2> /dev/null); r=$(cat "$R/T1-result.txt" 2> /dev/null)
[ "$(tail -1 <<< "$d")" = "lock released" ] && ok "run: the lock was released ($d)" || bad "run: done says [$d]; box.out: $(cat "$R/T1-box.out" 2> /dev/null)"
[ "$r" = "RESULT T1 runner 0 check 0 CLASS PASS mode pulls pulls 3" ] && ok "run: $r" || bad "run: result [$r]; check: $(tail -3 "$R/T1-check.txt" 2> /dev/null)"
[ ! -s "$W/BOX-LOCK" ] && ok "run: BOX-LOCK is empty afterwards" || bad "run: BOX-LOCK is [$(cat "$W/BOX-LOCK")]"
grep -q "owner $TOK bin $W/kytyplus-build/src/kyty_emulator want $(cut -c1-8 < "$S/pins0391.env" | sed -n 's/^NORMAL8=//p')" "$R/T1-env.txt" 2> /dev/null && ok "run: the S6N stand-in got the token, the shared binary and its md5" || bad "run: env: $(cat "$R/T1-env.txt" 2> /dev/null)"
grep -q "launcher $(sed -n 's/^LAUNCHER=//p' "$S/pins0391.env" | cut -c1-8) secs 420" "$R/T1-env.txt" 2> /dev/null && ok "run: the launcher md5 and 420 s were passed" || bad "run: env: $(cat "$R/T1-env.txt" 2> /dev/null)"
grep -q "mode pulls owner $TOK lock \[$L\]" "$R/T1-replug-env.txt" 2> /dev/null && ok "run: the replug stand-in got the mode, the token and the lock line" || bad "run: replug env: $(cat "$R/T1-replug-env.txt" 2> /dev/null)"
grep -q "pins: shared $(m "$W/kytyplus-build/src/kyty_emulator"), launcher" "$R/T1-pins.txt" 2> /dev/null && ok "run: the pins file records the full md5" || bad "run: pins: $(cat "$R/T1-pins.txt" 2> /dev/null)"
grep -q "anyps5-ports exp0413r | done: T1 token $TOK" "$W/BOX-QUEUE" && ok "run: the queue has the done line" || bad "run: queue: $(cat "$W/BOX-QUEUE")"
# the same tag again is refused at the claim
out=$(run claim T1 pulls "$DL" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "tag T1 was used" <<< "$out" && ok "claim: a used tag is refused" || bad "claim used tag: rc $rc: $out"
[ ! -s "$W/BOX-LOCK" ] && ok "claim: the refused claim left the lock empty" || bad "refused claim left [$(cat "$W/BOX-LOCK")]"
# a release of a token whose lock is someone else's is refused and leaves the line
out=$(run claim T3 pulls "$DL" < /dev/null); TOK3=$(sed -n 's/^TOK=\([0-9]*\)$/\1/p' <<< "$out")
echo "water exp 0389 | N2 | until 07:30" > "$W/BOX-LOCK"
out=$(run release "$TOK3" < /dev/null); rc=$?
[ $rc != 0 ] && grep -q "the lock is not ours" <<< "$out" && [ "$(cat "$W/BOX-LOCK")" = "water exp 0389 | N2 | until 07:30" ] && ok "release: a foreign line is refused and kept" || bad "release foreign: rc $rc: $out"
# the pin gate: a changed launcher stops the run before the launch, the lock is still released
: > "$W/BOX-LOCK"; : > "$F/owned"
out=$(run claim T4 pulls "$DL" < /dev/null); TOK4=$(sed -n 's/^TOK=\([0-9]*\)$/\1/p' <<< "$out")
printf 'launcher changed\n' > "$W/play-pkg.sh"
run start "$TOK4" T4 pulls "$DL" > /dev/null
for _ in $(seq 1 30); do [ -s "$R/T4-done.txt" ] && break; sleep 1; done
grep -q "the launcher is not" "$R/T4-done.txt" 2> /dev/null && [ "$(tail -1 "$R/T4-done.txt")" = "lock released" ] && [ ! -e "$R/T4-env.txt" ] && ok "run: a changed launcher stops before the launch and releases" || bad "run: T4 done: $(cat "$R/T4-done.txt" 2> /dev/null)"
echo "passed $P, failed $N"
[ "$N" = 0 ]
