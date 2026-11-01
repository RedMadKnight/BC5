#!/usr/bin/env bash
# BC5 exp 0388, the integration: int0388j.sh against stand-ins of the box in a temporary HOME; nothing real is touched.
# usage: test_int.sh <tree of main's patch 0001, with the edits NOT applied, as a directory> (run from this directory)
set -u
HERE=$(pwd); BASE=$1; T=$(mktemp -d); ok=0; bad=0
m() { md5sum < "$1" | cut -c1-8; }
check() { if eval "$2"; then ok=$((ok + 1)); echo "ok   $1"; else bad=$((bad + 1)); echo "FAIL $1"; fi; }
setup() {
    rm -rf "$T/h" "$T/bin"; H=$T/h; W=$H/bc5-work; K=$H/src/KytyPlus; S=$W/exp0388/s
    mkdir -p "$W/kytyplus-build/src" "$W/kytyplus-build-lean/src" "$W/backend-ubuntu" "$S" "$T/bin" "$K/src/bc5"
    echo normal > "$W/kytyplus-build/src/kyty_emulator"; echo lean > "$W/kytyplus-build-lean/src/kyty_emulator"; echo arch > "$W/backend-ubuntu/libbc5_backend.a"
    for f in src/kernel/semaphore.cpp src/loader/gamePatch.cpp src/loader/gamePatch.h src/loader/runtimeLinker.cpp src/graphics/presentation/hostMenu.cpp src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/hostInput.h src/bc5/job_arena_fix.hpp; do mkdir -p "$K/$(dirname "$f")"; cp "$BASE/$f" "$K/$f"; done
    cp "$HERE/mkhost.py" "$HERE/../../../backend/include/bc5/job_push_wait.hpp" "$S/"
    printf 'old patch\n' > "$T/old.diff"
    { echo "new patch"; echo "exp 0372"; echo "exp 0372"; echo "exp 0372"; echo "exp 0372"; echo "exp 0372"; echo "+++ b/src/bc5/pad_audio_route.hpp"; } > "$S/0001-new.patch"
    sed -e "s/^EXPECT_NORMAL=78f25172; EXPECT_LEAN=7b246487; EXPECT_ARCHIVE=3292bdaf; EXPECT_PATCH=716dcaf6; EXPECT_NEW=[0-9a-f]*;/EXPECT_NORMAL=$(m "$W/kytyplus-build/src/kyty_emulator"); EXPECT_LEAN=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); EXPECT_ARCHIVE=$(m "$W/backend-ubuntu/libbc5_backend.a"); EXPECT_PATCH=$(m "$T/old.diff"); EXPECT_NEW=$(m "$S/0001-new.patch");/" "$HERE/int0388j.sh" > "$S/int0388j.sh"
    cat > "$S/box0388.sh" << 'EOS'
#!/bin/sh
echo "box0388 $1" >> "$HOME/lock.log"
EOS
    cat > "$T/bin/pgrep" << 'EOS'
#!/bin/sh
exit 1
EOS
    cat > "$T/bin/python3" << 'EOS'
#!/bin/sh
shift
exec python "$@"
EOS
    cat > "$T/bin/git" << EOS
#!/bin/sh
case "\$3" in
    diff) if [ -e "\$2/src/bc5/job_push_wait.hpp" ]; then cat "\${TEST_DIFF:-$S/0001-new.patch}"; else cat "$T/old.diff"; fi ;;
    *) exit 0 ;;
esac
EOS
    cat > "$T/bin/strings" << 'EOS'
#!/bin/sh
cat "$1"
EOS
    cat > "$T/bin/distrobox" << EOS
#!/bin/sh
case "\$*" in
    *build-lean*) [ "\${TEST_FAIL:-}" = lean ] && exit 1; printf 'lean2\njob push wait %%s\nKYTY_BC5_JOB_PUSH_WAIT\n' > "$W/kytyplus-build-lean/src/kyty_emulator" ;;
    *) printf 'normal2\njob push wait %%s\njob push wait: pushes\nKYTY_BC5_JOB_PUSH_WAIT\n' > "$W/kytyplus-build/src/kyty_emulator" ;;
esac
EOS
    chmod +x "$T"/bin/*
}
run() { ( cd "$S" && PATH="$T/bin:$PATH" HOME="$H" bash int0388j.sh ) > "$T/out" 2>&1; rc=$?; }

setup; run
check "success: exit 0" '[ $rc = 0 ]'
check "success: claimed and released" 'grep -q claim $H/lock.log && grep -q release $H/lock.log'
check "success: the new binaries" 'grep -q normal2 $W/kytyplus-build/src/kyty_emulator && grep -q lean2 $W/kytyplus-build-lean/src/kyty_emulator'
check "success: the rollback copies" 'grep -qx normal $W/exp0388/integration/kyty_emulator.before-j && grep -qx lean $W/exp0388/integration/kyty_emulator-lean.before-j'
check "success: the wait is in the tree, the fix is not" 'grep -q Bc5JobPushWait $K/src/kernel/semaphore.cpp && [ ! -e $K/src/bc5/job_arena_fix.hpp ]'

setup; echo other > "$W/kytyplus-build/src/kyty_emulator"; run
check "a wrong binary: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; touch "$K/src/bc5/job_push_wait.hpp"; run
check "a header already there: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; echo x >> "$K/src/kernel/semaphore.cpp"; run
check "another semaphore.cpp: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; sed -i '/exp 0372/d' "$S/0001-new.patch"; sed -i "s/EXPECT_NEW=[0-9a-f]*;/EXPECT_NEW=$(m "$S/0001-new.patch");/" "$S/int0388j.sh"; run
check "a candidate without exp 0372: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; before=$(m "$K/src/kernel/semaphore.cpp"); TEST_FAIL=lean; export TEST_FAIL; run; unset TEST_FAIL
check "a failed lean build restores all" '[ $rc != 0 ] && [ -e $K/src/bc5/job_arena_fix.hpp ] && grep -qx normal $W/kytyplus-build/src/kyty_emulator && [ "$(m $K/src/kernel/semaphore.cpp)" = $before ] && [ ! -e $K/src/bc5/job_push_wait.hpp ] && grep -q release $H/lock.log'
setup; before=$(m "$K/src/kernel/semaphore.cpp"); TEST_DIFF=$T/old.diff; export TEST_DIFF; run; unset TEST_DIFF
check "a tree diff that is not the candidate restores all" '[ $rc != 0 ] && grep -qx lean $W/kytyplus-build-lean/src/kyty_emulator && [ "$(m $K/src/kernel/semaphore.cpp)" = $before ] && grep -q release $H/lock.log'
echo "== $ok passed, $bad failed"
rm -rf "$T"
[ "$bad" = 0 ]
