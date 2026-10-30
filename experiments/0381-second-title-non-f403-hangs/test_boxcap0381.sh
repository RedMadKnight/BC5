#!/usr/bin/env bash
# BC5 exp 0381: boxcap0381.sh against a stand-in. A real `sleep` plays the emulator; pgrep, ps and readlink are stand-ins
# on PATH, so that this runs on the laptop or on Linux with no GPU and no emulator. usage: bash test_boxcap0381.sh
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/pgrep" <<'EOF'
#!/usr/bin/env bash
cat "$STAND/pid" 2> /dev/null
EOF
cat > "$T/bin/ps" <<'EOF'
#!/usr/bin/env bash
s=$(cat "$STAND/start"); echo $(( $(date +%s) - s ))
EOF
cat > "$T/bin/readlink" <<'EOF'
#!/usr/bin/env bash
cat "$STAND/exe"
EOF
chmod +x "$T/bin/"*
export STAND=$T PATH=$T/bin:$PATH BOXCAP_TICK=1
fail=0
check() { if eval "$2"; then echo "ok: $1"; else echo "FAIL: $1"; cat "$T/log" 2> /dev/null; fail=1; fi; }

# 1. It stops the right process at the cap.
sleep 30 & P=$!
echo $P > "$T/pid"; date +%s > "$T/start"; echo /x/kyty_emulator > "$T/exe"
bash "$HERE/boxcap0381.sh" /x/kyty_emulator 2 "$T/log" 5
wait $P 2> /dev/null
check "TERM at the cap" "grep -q 'boxcap: TERM to $P' '$T/log'"
check "the process is gone" "! kill -0 $P 2> /dev/null"

# 2. It never touches another executable.
: > "$T/log"
sleep 4 & P=$!
echo $P > "$T/pid"; date +%s > "$T/start"; echo /y/other > "$T/exe"
bash "$HERE/boxcap0381.sh" /x/kyty_emulator 1 "$T/log" 2
check "another executable is left alone" "kill -0 $P 2> /dev/null"
check "it says no emulator" "grep -q 'no emulator' '$T/log'"
kill $P 2> /dev/null; wait $P 2> /dev/null

# 3. It ends by itself when the emulator ends before the cap.
: > "$T/log"
sleep 2 & P=$!
echo $P > "$T/pid"; date +%s > "$T/start"; echo /x/kyty_emulator > "$T/exe"
bash "$HERE/boxcap0381.sh" /x/kyty_emulator 100 "$T/log" 5
check "no signal when it ends first" "! grep -q TERM '$T/log'"
exit $fail
