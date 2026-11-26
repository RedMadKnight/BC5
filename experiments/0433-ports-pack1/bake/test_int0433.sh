#!/usr/bin/env bash
# BC5 exp 0433: a stand-in dry run of int0433.sh and undo0433.sh on a COPY (no box). The world: a git tree that is
# KytyPlus at f266548 with patch 0001 d1388db0 in its working tree (from a local tree that reproduces d1388db0), main's
# policy.cpp as the shared backend source, fake binaries and archive carrying a few BC5_ words, and fakes for pgrep (no
# emulator), distrobox (runs the command), ninja (compdb names the backend include; bc5_backend and kyty_emulator write
# files from the sources so a change shows), strings and the chain lock.
# Cases, one world in sequence:
#   ok      int0433.sh succeeds: the real baked patch gives PATCH_NEW, all checks pass
#   undo    undo0433.sh alone: everything back by md5, the tree's diff d1388db0, the new header gone, own lock slot
#   again   int0433.sh refuses nothing on the restored world (the copies dir moved aside) and succeeds again
#   fail    after a second undo: the lean build fails, int0433.sh undoes by itself; everything back
#   wrongtree  the tree's diff is not d1388db0: int0433.sh stops before the lock, nothing changes
# usage: test_int0433.sh <KytyPlus tree whose root commit is f266548> <empty scratch directory> <patch 0001 d1388db0>
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${1:?a tree}; BASE=${2:?a scratch directory}; P0001=${3:?patch 0001 d1388db0}
PASS=0; FAIL=0
ok() { if [ "$2" = 1 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAIL=$((FAIL + 1)); echo "FAIL $1"; fi; }
m8() { md5sum < "$1" | cut -c1-8; }
T=$BASE/w; mkdir -p "$T/bin" "$T/bc5-work/exp0413/n" "$T/bc5-work/kytyplus-build/src" "$T/bc5-work/kytyplus-build-lean/src" \
  "$T/bc5-work/backend-ubuntu" "$T/bc5-work/d19/export/backend/src" "$T/bc5-work/d19/export/backend/include" "$T/cwd"
W=$T/bc5-work; K=$T/src/KytyPlus; BES=$W/d19/export/backend
# fakes
printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"
printf '#!/bin/sh\nshift 3\nexec "$@"\n' > "$T/bin/distrobox"
printf '#!/bin/sh\ntr -c "[:print:]" "\\n" < "$1" | grep -aE ".{4,}"\n' > "$T/bin/strings"
cat > "$T/bin/ninja" << EOF
#!/bin/sh
case "\$*" in
  "-t compdb -x") echo "[{\"command\": \"c++ -I$BES/include -c x.cpp\"}]" ;;
  bc5_backend) { echo ARCH; md5sum < "$BES/src/policy.cpp"; grep -o 'CONTEXT_REG_RMW (0x51)' "$BES/src/policy.cpp" | head -1; } > libbc5_backend.a ;;
  kyty_emulator)
    case "\$(pwd)" in *-lean) lean=1; [ -n "\${FAIL_LEAN:-}" ] && { echo "x.cpp: error: stand-in failure"; exit 1; } ;; *) lean=0 ;; esac
    { printf 'BC5_DIRECT_ACB_RINGS\nKYTY_BC5_0429_RR\n'; cat "$W/backend-ubuntu/libbc5_backend.a"
      git -C "$K" diff --no-color f266548 | md5sum
      [ -e "$K/src/bc5/ports_pack1.hpp" ] && [ \$lean = 0 ] && echo "[bc5] ports pack 1 hits: %s"; true; } > src/kyty_emulator ;;
  *) echo "fake ninja: \$*"; exit 1 ;;
esac
EOF
chmod +x "$T/bin/"*
printf 'chain_claim() { echo "CLAIM" >> "%s/lock.log"; }\nchain_release() { echo RELEASE >> "%s/lock.log"; }\n' "$T" "$T" > "$W/exp0413/n/chainlock0417.inc"
# the tree: the base commit with patch 0001 (d1388db0) applied
git -c core.autocrlf=false clone -q "$SRC" "$K" || exit 1
git -C "$K" config core.autocrlf false
top=$(git -C "$K" rev-parse HEAD); base=$(git -C "$K" rev-list --max-parents=0 HEAD)
git -C "$K" reset -q --hard "$base"; git -C "$K" tag f266548 "$base"
(cd "$K" && git apply --index --whitespace=nowarn "$P0001") || exit 1  # 0001 applied, as on the box
d0=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok "world: the tree's diff is d1388db0 ($d0)" "$([ "$d0" = d1388db0 ] && echo 1)"
REPO=$(cd "$HERE/../../.." && pwd)
git -C "$REPO" show ba402356:backend/src/policy.cpp > "$BES/src/policy.cpp"
ok "world: policy.cpp is d5ae7298" "$([ "$(m8 "$BES/src/policy.cpp")" = d5ae7298 ] && echo 1)"
printf 'BC5_DIRECT_ACB_RINGS\nKYTY_BC5_0429_RR\nCONTEXT_REG_RMW\n' > "$W/kytyplus-build/src/kyty_emulator"
printf 'BC5_DIRECT_ACB_RINGS\nKYTY_BC5_0429_RR\nlean\n' > "$W/kytyplus-build-lean/src/kyty_emulator"
echo "ARCH old" > "$W/backend-ubuntu/libbc5_backend.a"
N0=$(m8 "$W/kytyplus-build/src/kyty_emulator"); L0=$(m8 "$W/kytyplus-build-lean/src/kyty_emulator"); A0=$(m8 "$W/backend-ubuntu/libbc5_backend.a")
(cd "$K" && md5sum src/common/hostException.cpp src/libs/ajm.cpp src/kernel/pthread.cpp) > "$T/units0.md5"
run() { (cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH INT_W=$W INT_K=$K UNDO_W=$W UNDO_K=$K NORMAL_OLD=$N0 LEAN_OLD=$L0 ARCH_OLD=$A0 "$@" 2>&1); }
back() {
  [ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = d1388db0 ] && [ ! -e "$K/src/bc5/ports_pack1.hpp" ] \
    && (cd "$K" && md5sum -c --quiet "$T/units0.md5") && [ "$(m8 "$BES/src/policy.cpp")" = d5ae7298 ] \
    && [ "$(m8 "$W/kytyplus-build/src/kyty_emulator")" = "$N0" ] && [ "$(m8 "$W/kytyplus-build-lean/src/kyty_emulator")" = "$L0" ] \
    && [ "$(m8 "$W/backend-ubuntu/libbc5_backend.a")" = "$A0" ] && echo 1 || echo 0
}

out=$(run bash "$HERE/int0433.sh"); rc=$?
echo "$out" | sed 's/^/    | /' | tail -12
ok "ok: exit 0" "$([ $rc = 0 ] && echo 1)"
ok "ok: the patch is 59f00d27" "$(echo "$out" | grep -q 'the patch: d1388db0 -> 59f00d27' && echo 1)"
ok "ok: the header is in the tree and in the index" "$([ -e "$K/src/bc5/ports_pack1.hpp" ] && git -C "$K" ls-files --error-unmatch src/bc5/ports_pack1.hpp > /dev/null 2>&1 && echo 1)"
ok "ok: policy.cpp is the kit's" "$([ "$(m8 "$BES/src/policy.cpp")" = 107bb1b6 ] && echo 1)"
ok "ok: one claim, one release" "$([ "$(tr '\n' ' ' < "$T/lock.log")" = "CLAIM RELEASE " ] && echo 1)"
rm -f "$T/lock.log"

out=$(run bash "$HERE/undo0433.sh"); rc=$?
ok "undo: exit 0 ($(echo "$out" | tail -1 | cut -c1-100))" "$([ $rc = 0 ] && echo 1)"
ok "undo: everything back" "$(back)"
ok "undo: claimed and released its own slot" "$([ "$(tr '\n' ' ' < "$T/lock.log" 2> /dev/null)" = "CLAIM RELEASE " ] && echo 1)"
ok "undo: no stray files in the working directory" "$([ -z "$(ls "$T/cwd")" ] && echo 1)"
rm -f "$T/lock.log"

out=$(run bash "$HERE/int0433.sh"); rc=$?
ok "again: refuses while the old copies are there" "$([ $rc != 0 ] && echo "$out" | grep -q 'already holds' && echo 1)"
ok "again: the refusal changed nothing" "$(back)"
mv "$W/exp0433/swap" "$W/exp0433/swap.1"; rm -f "$T/lock.log"
out=$(run bash "$HERE/int0433.sh"); rc=$?
ok "again: exit 0 after the copies moved aside" "$([ $rc = 0 ] && echo 1)"
run bash "$HERE/undo0433.sh" > /dev/null; mv "$W/exp0433/swap" "$W/exp0433/swap.2"; rm -f "$T/lock.log"

out=$(run env FAIL_LEAN=1 bash "$HERE/int0433.sh"); rc=$?
ok "fail: exit not 0" "$([ $rc != 0 ] && echo 1)"
ok "fail: undid by itself ($(echo "$out" | grep -m1 'undo0433:' | cut -c1-90))" "$(echo "$out" | grep -q 'undo0433: back' && echo 1)"
ok "fail: everything back" "$(back)"
ok "fail: one claim, one release (the undo ran in int's slot)" "$([ "$(tr '\n' ' ' < "$T/lock.log")" = "CLAIM RELEASE " ] && echo 1)"
mv "$W/exp0433/swap" "$W/exp0433/swap.3"; rm -f "$T/lock.log"

echo "// stray" >> "$K/src/libs/ajm.cpp"
out=$(run bash "$HERE/int0433.sh"); rc=$?
ok "wrongtree: stops ($(echo "$out" | tail -1 | cut -c1-80))" "$([ $rc != 0 ] && echo "$out" | grep -q 'diff is' && echo 1)"
ok "wrongtree: no claim, no copies" "$([ ! -e "$T/lock.log" ] && [ ! -e "$W/exp0433/swap" ] && echo 1)"

echo "passed $PASS, failed $FAIL"
[ $FAIL = 0 ]
