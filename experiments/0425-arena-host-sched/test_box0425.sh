#!/usr/bin/env bash
# BC5 exp 0425: box0425.sh on stand-ins, on the laptop (after exp 0388's test_box0388.sh). A temporary HOME, a stand-in
# pgrep, distrobox and strings, the real patch0425.py on a copy of the laptop's f266548 + 4945ef1b units, and a fake
# build0425.py run (the compile itself is the box's). Not covered: ninja, the compiler, the link.
# usage: test_box0425.sh <tree: f266548 + patch 4945ef1b>
set -u
HERE=$(cd "$(dirname "$0")" && pwd); TREE0=${1:?tree}
PY="/c/Program Files/Python314/python"
PASS=0; FAILS=0
ok() { if [ "$2" = 0 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAILS=$((FAILS + 1)); echo "FAIL $1"; [ -n "${3:-}" ] && printf '%s\n' "$3" | tail -15 | sed 's/^/     /'; fi; }
T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-0425b.XXXXXX") || exit 1
export HOME=$T/home FAKE_T=$T
mkdir -p "$T/bin" "$HOME/bc5-work/kytyplus-build/src" "$HOME/src/KytyPlus/src/kernel" "$HOME/src/KytyPlus/src/loader" "$HOME/src/KytyPlus/src/libs" "$T/kit"
cp "$TREE0/src/kernel/semaphore.cpp" "$TREE0/src/kernel/pthread.cpp" "$HOME/src/KytyPlus/src/kernel/"
cp "$TREE0/src/loader/gamePatch.cpp" "$HOME/src/KytyPlus/src/loader/"; cp "$TREE0/src/libs/libPlayGo.cpp" "$HOME/src/KytyPlus/src/libs/"
echo shared > "$HOME/bc5-work/kytyplus-build/src/kyty_emulator"
cp "$HERE/box0425.sh" "$HERE/patch0425.py" "$HERE/units.sha256" "$T/kit/"
# the fake build: the compdb and the "binary", which holds the strings the build checks for (from the patched units)
cat > "$T/kit/build0425.py" << 'EOF'
import sys
db, src, out, build, binp = sys.argv[1:6]
units = ["src/kernel/semaphore.cpp", "src/kernel/pthread.cpp", "src/loader/gamePatch.cpp", "src/libs/libPlayGo.cpp"]
open(binp, "w").write("#!/bin/sh" + chr(10) + "".join(open(src + "/" + u, encoding="utf-8").read() for u in units))
print("fake build: wrote", binp)
EOF
printf '#!/usr/bin/bash\n[ -s "$FAKE_T/emu-running" ] && exit 0\nexit 1\n' > "$T/bin/pgrep"
{ echo '#!/usr/bin/bash'; echo '[ "$1 $2 $3" = "enter ubuntu --" ] || exit 1; shift 3'
  echo 'case "$*" in *"ninja -t compdb"*) echo "[]"; exit 0 ;; esac'
  echo 'a=(); for x in "$@"; do case "$x" in /*) a+=("$(cygpath -w "$x")") ;; python3) a+=("'"$PY"'") ;; *) a+=("$x") ;; esac; done'
  echo 'exec "${a[@]}"'; } > "$T/bin/distrobox"
{ echo '#!/usr/bin/bash'; echo 'a=(); for x in "$@"; do case "$x" in /*) a+=("$(cygpath -w "$x")") ;; *) a+=("$x") ;; esac; done'
  echo '"'"$PY"'" "${a[@]}" | tr -d "\r"'; } > "$T/bin/python3"
printf '#!/usr/bin/bash\ncat "$@"\n' > "$T/bin/strings"
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH"
B="bash $T/kit/box0425.sh"; L=$HOME/bc5-work/BOX-LOCK
o=$($B build 2>&1); [ $? != 0 ] && printf '%s' "$o" | grep -q "no lock held"; ok "build without the lock stops" $? "$o"
o=$($B release 2>&1); [ $? != 0 ] && printf '%s' "$o" | grep -q "not ours"; ok "release without a claim stops, nothing touched" $? "$o"
echo "foreign session line" > "$L"
o=$($B claim "x" 5 2>&1); [ $? != 0 ] && [ "$(cat "$L")" = "foreign session line" ]; ok "a foreign lock is not overwritten" $? "$o"
o=$($B release 2>&1); [ "$(cat "$L")" = "foreign session line" ]; ok "release leaves a foreign line" $? "$o"
: > "$L"; echo 1 > "$T/emu-running"
o=$($B claim "x" 5 2>&1); [ $? != 0 ] && [ ! -s "$L" ]; ok "no claim while an emulator runs" $? "$o"
rm -f "$T/emu-running"
o=$($B claim "exp 0425 private build" 20 2>&1); [ $? = 0 ] && grep -q "top exp 0425 | token" "$L"; ok "claim on an empty lock" $? "$o"
o=$($B claim "again" 5 2>&1); [ $? != 0 ]; ok "a second claim is refused" $? "$o"
o=$($B build 2>&1); rc=$?
[ $rc = 0 ] && printf '%s' "$o" | grep -q "patch0425: done" && printf '%s' "$o" | grep -q "private binary [0-9a-f]\{32\}, shared before" && [ -s "$HOME/bc5-work/exp0425/binary.md5" ]
ok "build: pins, patch, the strings gate, binary.md5, the shared binary unchanged" $? "$o"
cp "$HOME/bc5-work/exp0425/kyty_emulator" "$T/bin1"
o=$($B build 2>&1); [ $? = 0 ] && ls "$HOME/bc5-work/exp0425/" | grep -q '^kyty_emulator\.[0-9a-f]\{8\}$'; ok "a second build keeps the first binary aside" $? "$o"
echo "// changed" >> "$HOME/src/KytyPlus/src/kernel/semaphore.cpp"
o=$($B build 2>&1); [ $? != 0 ] && printf '%s' "$o" | grep -q "not the pins"; ok "a shared unit off its pin stops the build" $? "$o"
o=$($B release 2>&1); [ $? = 0 ] && [ ! -s "$L" ] && [ ! -e "$HOME/bc5-work/exp0425/lock.line" ]; ok "release of our own line" $? "$o"
echo "== $PASS passed, $FAILS failed"
[ "$FAILS" = 0 ]
