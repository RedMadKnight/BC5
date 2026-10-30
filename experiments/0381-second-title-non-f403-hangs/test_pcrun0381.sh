#!/usr/bin/env bash
# BC5 exp 0381: dry run of pcrun0381.sh + pcbox0381.sh with stand-ins (a temporary HOME, distrobox, pgrep): no box, no
# ssh, no GPU. It checks what today's slip got wrong: an outcome line appears only after a passed guard, and done only
# when everything passed. usage (in a git checkout): bash test_pcrun0381.sh
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
cat > "$T/bin/pgrep" <<'EOF'
#!/usr/bin/env bash
[ -e "$STAND/emulator" ] && { echo 4242; exit 0; }
exit 1
EOF
cat > "$T/bin/distrobox" <<'EOF'
#!/usr/bin/env bash
c="$*"
[ -n "${FAIL_AT:-}" ] && case "$c" in *"$FAIL_AT"*) echo "stand-in failure"; exit 7 ;; esac
case "$c" in
*direct-selftest*) [ "${NO_NOTHING:-}" = 1 ] && echo "something done" || echo "direct-selftest: nothing done without --submit" ;;
*bc5_backend_tests*) [ "${NO_TESTS:-}" = 1 ] && echo "No tests ran" || echo "All tests passed (1 assertion in 1 test case)" ;;
*clang++*) echo "stand-in clang" ;;
esac
exit 0
EOF
cat > "$T/remote" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "bash -s" ]; then exec bash -s; fi
exec bash -c "$1"
EOF
chmod +x "$T/bin/"* "$T/remote"
export STAND=$T PATH=$T/bin:$PATH PC_REMOTE="$T/remote" HOME_REAL=$HOME
fail=0
setup() {
    export HOME=$T/home
    rm -rf "$HOME" "$T/emulator"; mkdir -p "$HOME/bc5-work/exp0381"
    : > "$HOME/bc5-work/BOX-LOCK"; : > "$HOME/bc5-work/BOX-QUEUE"
    unset FAIL_AT NO_TESTS NO_NOTHING
}
run() { (cd "$HERE" && bash pcrun0381.sh "${1:-HEAD}") > "$T/out" 2>&1; echo $?; }
q() { cat "$HOME/bc5-work/BOX-QUEUE"; }
expect() { if eval "$2"; then echo "ok: $1"; else echo "FAIL: $1"; cat "$T/out"; q; fail=1; fi; }

setup; touch "$T/emulator"; r=$(run)
expect "an emulator: stops, nothing recorded" "[ $r != 0 ] && [ ! -s '$HOME/bc5-work/BOX-QUEUE' ]"
setup; echo "top exp 0380 | B loop" > "$HOME/bc5-work/BOX-LOCK"; r=$(run)
expect "a foreign lock: stops, nothing recorded, the lock kept" "[ $r != 0 ] && [ ! -s '$HOME/bc5-work/BOX-QUEUE' ] && grep -q 'exp 0380' '$HOME/bc5-work/BOX-LOCK'"
setup; r=$(run no-such-commit)
expect "a tree that does not arrive: stops, nothing recorded, no lock left" "[ $r != 0 ] && [ ! -s '$HOME/bc5-work/BOX-QUEUE' ] && [ ! -s '$HOME/bc5-work/BOX-LOCK' ]"
setup; r=$(run)
expect "all pass: done, and the lock cleared" "[ $r = 0 ] && q | grep -q 'check done' && [ ! -s '$HOME/bc5-work/BOX-LOCK' ]"
for f in "cmake -S" "cmake --build" "bc5_backend_tests" "direct-selftest"; do
    setup; export FAIL_AT="$f"; r=$(run)
    expect "[$f] fails: FAILED, no done, the lock cleared" "[ $r != 0 ] && q | grep -q 'check FAILED' && ! q | grep -q 'check done' && [ ! -s '$HOME/bc5-work/BOX-LOCK' ]"
done
setup; export NO_TESTS=1; r=$(run)
expect "no tests ran: FAILED, no done" "[ $r != 0 ] && q | grep -q 'check FAILED' && ! q | grep -q 'check done'"
setup; export NO_NOTHING=1; r=$(run)
expect "selftest did not do nothing: FAILED, no done" "[ $r != 0 ] && q | grep -q 'check FAILED' && ! q | grep -q 'check done'"
setup; r=$(run)
expect "both selftests keep their own log" "[ -s '$HOME/bc5-work/exp0381/pc/selftest-1.log' ] && [ -s '$HOME/bc5-work/exp0381/pc/selftest-2.log' ]"
exit $fail
