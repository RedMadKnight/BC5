#!/usr/bin/env bash
# BC5 exp 0412: test of lean-session.sh's restore path with a stand-in systemctl (no desktop, no GPU).
# The stand-in keeps each unit's state in a file and fails the first N starts (FAKE_FAIL_STARTS).
#   1. stop notes the active unit and stops it; a restore whose start FAILS keeps the unit in the state file and
#      returns non-zero; the next restore (the start succeeds) starts it, returns 0 and moves the file to .done;
#   2. a restore with nothing noted returns 0 and says so;
#   3. the watcher tries again after a failed start and ends with the unit active;
#   4. two units, one fails: only the failed one is kept.
# usage: test-lean-session.sh   (prints "test-lean-session: N of N" and returns 0 when every check holds)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/bc5-work" "$T/units"
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# stand-in: systemctl --user is-active|start|stop|show <unit>
[ "$1" = --user ] && shift
cmd=$1; shift
case "$cmd" in
  is-active) u=$1; s=$(cat "$FAKE_UNITS/$u" 2> /dev/null || echo inactive); echo "$s"; [ "$s" = active ] ;;
  stop) echo inactive > "$FAKE_UNITS/$1" ;;
  start)
    n=$(cat "$FAKE_UNITS/$1.fail" 2> /dev/null || echo 0)
    if [ "$n" -gt 0 ]; then echo $((n - 1)) > "$FAKE_UNITS/$1.fail"; exit 1; fi
    echo active > "$FAKE_UNITS/$1" ;;
  show) echo 0 ;;
  *) exit 2 ;;
esac
EOF
chmod +x "$T/bin/systemctl"
export PATH="$T/bin:$PATH" HOME="$T/home" FAKE_UNITS="$T/units" LEAN_RETRY_S=0
S="$T/home/bc5-work/lean-session.state"; U=plasma-plasmashell.service
N=0; OK=0
check() { N=$((N + 1)); if eval "$1"; then OK=$((OK + 1)); else echo "FAIL: $2"; fi; }
run() { bash "$HERE/lean-session.sh" "$@" > "$T/out" 2>&1; }

# 1
echo active > "$T/units/$U"; echo 1 > "$T/units/$U.fail"
(sleep 30 &); P=$(pgrep -n sleep 2> /dev/null || echo $$)   # a pid that lives: the watcher must not restore yet
run stop "$P"; check '[ "$(cat "$T/units/$U")" = inactive ] && grep -qx "$U" "$S"' "stop notes and stops the unit"
run restore; rc=$?
check '[ "$rc" != 0 ]' "a failed start returns non-zero"
check 'grep -qx "$U" "$S" && [ ! -e "$S.done" ]' "the failed unit stays in the state file"
check '[ "$(cat "$T/units/$U")" = inactive ]' "and is still inactive"
run restore; rc=$?
check '[ "$rc" = 0 ] && [ "$(cat "$T/units/$U")" = active ]' "the next restore starts it"
check '[ ! -e "$S" ] && [ -e "$S.done" ] && [ ! -e "$S.left" ]' "then the state file is done"
# 2
run restore; rc=$?
check '[ "$rc" = 0 ] && grep -q "nothing to restore" "$T/out"' "nothing noted: returns 0"
# 3: the watcher, with a pid that is already gone, and two failing starts
rm -f "$S.done"; echo inactive > "$T/units/$U"; echo "$U" > "$S"; echo 2 > "$T/units/$U.fail"
run watch 999999999; rc=$?
check '[ "$rc" = 0 ] && [ "$(cat "$T/units/$U")" = active ] && [ ! -e "$S" ]' "the watcher tries again until the start succeeds"
# 3b: it gives up after six tries and keeps the file
rm -f "$S.done"; echo inactive > "$T/units/$U"; echo "$U" > "$S"; echo 99 > "$T/units/$U.fail"
run watch 999999999; rc=$?
check '[ "$rc" != 0 ] && grep -qx "$U" "$S" && [ "$(cat "$T/units/$U.fail")" = 93 ]' "six tries, then it gives up and keeps the unit"
# 4: two units, one fails
rm -f "$S.done"; printf 'a.service\nb.service\n' > "$S"; echo inactive > "$T/units/a.service"; echo inactive > "$T/units/b.service"; echo 1 > "$T/units/b.service.fail"; echo 0 > "$T/units/a.service.fail"
run restore; rc=$?
check '[ "$rc" != 0 ] && [ "$(cat "$S")" = b.service ] && [ "$(cat "$T/units/a.service")" = active ]' "only the failed unit is kept"
echo "test-lean-session: $OK of $N"
[ "$OK" = "$N" ]
