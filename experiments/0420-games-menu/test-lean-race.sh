#!/usr/bin/env bash
# BC5 exp 0420: the lean session's race (Codex 2026-11-15 10:07 UTC in codex-to-claude.md, LESSONS R56), on stand-ins:
# a temporary HOME, a systemctl that keeps each unit's state in a file, a pgrep that sees the fake emulator, a setsid
# that just runs its command. No desktop, no box, no GPU.
#   (a) launcher A (BC5_LEAN=1) runs; launcher B is refused by pgrep and changes nothing (the state still names the
#       shell, A still owns it); a direct stop for a live pid is refused (exit 3); A ends and its watcher starts the
#       shell again, then the claim is gone
#   (b) two stops at once: one owner (one exit 0, one exit 3), the state names the shell, one restore when the
#       owner ends
#   (c) a dead owner is taken over and the unit it noted (and could not start again) is kept in the state
# usage: bash test-lean-race.sh   or   LAUNCHER=<launcher> bash test-lean-race.sh
#          (prints "test-lean-race: N of N", exit 0 when every check holds)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LEAN=${LEAN:-$HERE/../0412-memory-guardian/lean-session.sh}   # LEAN=<file>: another lean-session.sh
LAUNCHER=${LAUNCHER:-$HERE/play-any.sh}   # LAUNCHER=<file>: another launcher (the shared one made by fix-lean-race.sh make)
T=$(mktemp -d) || exit 1
KIDS=""
trap 'for k in $KIDS; do kill "$k" 2> /dev/null; done; rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/bc5-work" "$T/units" "$T/menu" "$T/games"
cat > "$T/bin/systemctl" << 'EOF'
#!/usr/bin/env bash
[ "$1" = --user ] && shift
cmd=$1; shift
case "$cmd" in
  is-active) s=$(cat "$FAKE_UNITS/$1" 2> /dev/null || echo inactive); echo "$s"; [ "$s" = active ] ;;
  stop) echo inactive > "$FAKE_UNITS/$1"; echo "stop $1" >> "$FAKE_UNITS/calls" ;;
  start)
    echo "start $1" >> "$FAKE_UNITS/calls"
    n=$(cat "$FAKE_UNITS/$1.fail" 2> /dev/null || echo 0)
    if [ "$n" -gt 0 ]; then echo $((n - 1)) > "$FAKE_UNITS/$1.fail"; exit 1; fi
    echo active > "$FAKE_UNITS/$1" ;;
  show) echo 0 ;;
  *) exit 2 ;;
esac
EOF
printf '#!/usr/bin/env bash\n[ -e "$HOME/emu.running" ] && { cat "$HOME/emu.running"; exit 0; }; exit 1\n' > "$T/bin/pgrep"
printf '#!/usr/bin/env bash\nexec "$@"\n' > "$T/bin/setsid"
# the lean emulator: says it runs, waits for emu.release
cat > "$T/emu-lean" << 'EOF'
#!/usr/bin/env bash
echo $$ > "$HOME/emu.running"
for _ in $(seq 1 300); do [ -e "$HOME/emu.release" ] && break; sleep 0.1; done
rm -f "$HOME/emu.running"; exit 0
EOF
cp "$T/emu-lean" "$T/emu"
mkdir -p "$T/home/bc5-work/kytyplus-build-lean/src"; cp "$T/emu-lean" "$T/home/bc5-work/kytyplus-build-lean/src/kyty_emulator"   # the shared launcher's fixed path
chmod +x "$T/home/bc5-work/kytyplus-build-lean/src/kyty_emulator"
chmod +x "$T"/bin/* "$T/emu-lean" "$T/emu"
cp "$LEAN" "$T/home/bc5-work/lean-session.sh"; chmod +x "$T/home/bc5-work/lean-session.sh"
printf 'VIDEO_DRIVER=wayland\n' > "$T/bc5-run.env"
export PATH="$T/bin:$PATH" HOME="$T/home" FAKE_UNITS="$T/units" LEAN_RETRY_S=0
export BC5_RUN_ENV=$T/bc5-run.env KYTY_BC5_MENU_DIR=$T/menu BC5_GAMES_DIR=$T/games BC5_EMU=$T/emu BC5_EMU_LEAN=$T/emu-lean
LS=$HOME/bc5-work/lean-session.sh S=$HOME/bc5-work/lean-session.state; O=$S.owner; U=plasma-plasmashell.service
N=0; OK=0
check() { N=$((N + 1)); if eval "$1"; then OK=$((OK + 1)); echo "ok   $2"; else echo "FAIL $2"; fi; }
waitfor() { for _ in $(seq 1 100); do eval "$1" && return 0; sleep 0.1; done; return 1; }
fresh() { rm -rf "$S" "$S.done" "$S.left" "$O" "$HOME/emu.release" "$HOME/emu.running" "$FAKE_UNITS/calls"; echo active > "$FAKE_UNITS/$U"; echo 0 > "$FAKE_UNITS/$U.fail"; }

# (a)
fresh
BC5_LEAN=1 bash "$LAUNCHER" > "$T/a.out" 2>&1 &
A=$!; KIDS="$KIDS $A"
waitfor '[ -e "$HOME/emu.running" ]'
check '[ "$(cat "$FAKE_UNITS/$U")" = inactive ] && grep -qx "$U" "$S" && [ "$(cut -d" " -f1 "$O/pid")" = "$A" ]' "(a) A runs: the shell is stopped, noted, A owns the session"
BC5_LEAN=1 bash "$LAUNCHER" > "$T/b.out" 2>&1; rcb=$?
check '[ "$rcb" = 1 ] && grep -q "already running" "$T/b.out"' "(a) B is refused by pgrep"
check 'grep -qx "$U" "$S" && [ "$(cut -d" " -f1 "$O/pid")" = "$A" ] && [ "$(grep -c "^stop" "$FAKE_UNITS/calls")" = 1 ]' "(a) B changed nothing: the state names the shell, A owns it, one stop"
sleep 300 & L=$!; KIDS="$KIDS $L"
bash "$LS" stop "$L" > "$T/c.out" 2>&1; rcc=$?
check '[ "$rcc" = 3 ] && grep -qx "$U" "$S" && [ "$(cut -d" " -f1 "$O/pid")" = "$A" ]' "(a) a direct stop for another live pid: exit 3, nothing changed"
kill "$L" 2> /dev/null
touch "$HOME/emu.release"; wait "$A"
waitfor '[ ! -e "$O" ] && [ "$(cat "$FAKE_UNITS/$U")" = active ]'
check '[ "$(cat "$FAKE_UNITS/$U")" = active ] && [ "$(grep -c "^start" "$FAKE_UNITS/calls")" = 1 ] && [ -e "$S.done" ] && [ ! -e "$S" ]' "(a) A ended: the watcher started the shell once"
check '[ ! -e "$O" ]' "(a) and the claim is gone"

# (b) two stops at once, for two live pids
fresh
sleep 300 & P1=$!; sleep 300 & P2=$!; KIDS="$KIDS $P1 $P2"
bash "$LS" stop "$P1" > "$T/s1.out" 2>&1 & J1=$!
bash "$LS" stop "$P2" > "$T/s2.out" 2>&1 & J2=$!
wait "$J1"; r1=$?; wait "$J2"; r2=$?
check '{ [ "$r1" = 0 ] && [ "$r2" = 3 ]; } || { [ "$r1" = 3 ] && [ "$r2" = 0 ]; }' "(b) one owner: exits $r1 and $r2"
W=$P1; [ "$r2" = 0 ] && W=$P2; Lz=$P1; [ "$W" = "$P1" ] && Lz=$P2
check '[ "$(cut -d" " -f1 "$O/pid")" = "$W" ] && [ "$(cat "$S")" = "$U" ] && [ "$(cat "$FAKE_UNITS/$U")" = inactive ]' "(b) the winner owns it and the state names the shell (not empty)"
kill "$Lz"; sleep 1.5
check '[ "$(cat "$FAKE_UNITS/$U")" = inactive ] && [ -e "$O" ]' "(b) the loser's end restores nothing"
kill "$W"
waitfor '[ ! -e "$O" ] && [ "$(cat "$FAKE_UNITS/$U")" = active ]'
check '[ "$(cat "$FAKE_UNITS/$U")" = active ] && [ "$(grep -c "^start" "$FAKE_UNITS/calls")" = 1 ] && [ ! -e "$O" ]' "(b) the winner's end: one restore, the claim is gone"

# (c) a dead owner, whose restore could not start the shell, is taken over
fresh
echo inactive > "$FAKE_UNITS/$U"; echo "$U" > "$S"; mkdir -p "$O"; echo "999999 1" > "$O/pid"
sleep 300 & P3=$!; KIDS="$KIDS $P3"
bash "$LS" stop "$P3" > "$T/s3.out" 2>&1; r3=$?
check '[ "$r3" = 0 ] && [ "$(cut -d" " -f1 "$O/pid")" = "$P3" ] && [ "$(cat "$S")" = "$U" ] && grep -q "takes the session over" "$T/s3.out"' "(c) taken over, the noted shell is kept"
kill "$P3"
waitfor '[ ! -e "$O" ] && [ "$(cat "$FAKE_UNITS/$U")" = active ]'
check '[ "$(cat "$FAKE_UNITS/$U")" = active ] && [ ! -e "$O" ]' "(c) its end starts the shell again"
# (c2) a restore by hand while the owner lives keeps the claim
fresh
sleep 300 & P4=$!; KIDS="$KIDS $P4"
bash "$LS" stop "$P4" > /dev/null 2>&1; bash "$LS" restore > /dev/null 2>&1
check '[ "$(cat "$FAKE_UNITS/$U")" = active ] && [ "$(cut -d" " -f1 "$O/pid")" = "$P4" ]' "(c2) a restore by hand starts the shell, the live owner keeps the claim"
kill "$P4"; waitfor '[ ! -e "$O" ]'
check '[ ! -e "$O" ]' "(c2) the owner's end releases it"

echo "test-lean-race: $OK of $N"
[ "$OK" = "$N" ]
