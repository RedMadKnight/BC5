#!/usr/bin/env bash
# BC5 exp 0388, the integration: int0388j.sh against stand-ins of the box in a temporary HOME; nothing real is touched.
# A small kit of its own: a changed, a removed and a new host file, a backend file, a mount file.
# usage: test_int.sh   (from this directory)
set -u
HERE=$(pwd); T=$(mktemp -d); ok=0; bad=0
m() { md5sum < "$1" | cut -c1-8; }
check() { if eval "$2"; then ok=$((ok + 1)); echo "ok   $1"; else bad=$((bad + 1)); echo "FAIL $1"; fi; }
setup() {
    rm -rf "$T/h" "$T/bin"; H=$T/h; W=$H/bc5-work; K=$H/src/KytyPlus; TL=$H/src/bc5/tools; BS=$W/export/backend; S=$W/exp0388/s; KIT=$S/kit
    mkdir -p "$W/kytyplus-build/src" "$W/kytyplus-build-lean/src" "$W/backend-ubuntu" "$W/bc5-tools-ubuntu/release" "$S" "$T/bin" "$K/src/bc5" "$TL/m" "$BS/src" "$KIT/H/src/bc5" "$KIT/B/src" "$KIT/T/m"
    echo normal > "$W/kytyplus-build/src/kyty_emulator"; echo lean > "$W/kytyplus-build-lean/src/kyty_emulator"; echo arch > "$W/backend-ubuntu/libbc5_backend.a"
    echo mount > "$W/bc5-tools-ubuntu/release/bc5-mount"; chmod +x "$W/bc5-tools-ubuntu/release/bc5-mount"
    echo "KYTY_BC5_BACKEND_SRC:PATH=$BS" > "$W/kytyplus-build/CMakeCache.txt"; echo x > "$BS/CMakeLists.txt"
    echo a0 > "$K/src/a.cpp"; echo o0 > "$K/src/old.hpp"; echo d0 > "$BS/src/d.cpp"; echo r0 > "$TL/m/r.rs"
    echo a1 > "$KIT/H/src/a.cpp"; echo n1 > "$KIT/H/src/bc5/job_push_wait.hpp"; echo d1 > "$KIT/B/src/d.cpp"; echo r1 > "$KIT/T/m/r.rs"
    { echo "H src/a.cpp $(m "$K/src/a.cpp") $(m "$KIT/H/src/a.cpp")"; echo "H src/old.hpp $(m "$K/src/old.hpp") -"; echo "H src/bc5/job_push_wait.hpp - $(m "$KIT/H/src/bc5/job_push_wait.hpp")"
      echo "B src/d.cpp $(m "$BS/src/d.cpp") $(m "$KIT/B/src/d.cpp")"; echo "T m/r.rs $(m "$TL/m/r.rs") $(m "$KIT/T/m/r.rs")"; } > "$KIT/manifest.txt"
    printf 'old patch\n' > "$T/old.diff"
    { echo "new patch"; for i in 1 2 3 4 5; do echo "exp 0372"; done; echo "+++ b/src/bc5/pad_audio_route.hpp"; } > "$S/0001-new.patch"
    pins
    cat > "$S/box0388.sh" << 'EOS'
#!/bin/sh
echo "box0388 $1" >> "$HOME/lock.log"
EOS
    printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"
    cat > "$T/bin/git" << EOS
#!/bin/sh
case "\$3" in
    diff) if [ -e "\$2/src/bc5/job_push_wait.hpp" ]; then cat "\${TEST_DIFF:-$S/0001-new.patch}"; else cat "$T/old.diff"; fi ;;
    *) exit 0 ;;
esac
EOS
    printf '#!/bin/sh\ncat "$1"\n' > "$T/bin/strings"
    cat > "$T/bin/distrobox" << EOS
#!/bin/sh
case "\$*" in
    *"cmake --build"*) [ "\${TEST_FAIL:-}" = archive ] && exit 1; [ "\${TEST_FAIL:-}" = archchange ] && echo arch2 > "$W/backend-ubuntu/libbc5_backend.a"; exit 0 ;;
    *build-lean*) [ "\${TEST_FAIL:-}" = lean ] && exit 1; printf 'lean2\njob push wait %%s\nKYTY_BC5_JOB_PUSH_WAIT\njob-arena fix APPLIED\n' > "$W/kytyplus-build-lean/src/kyty_emulator" ;;
    *) printf 'normal2\njob push wait %%s\njob push wait: pushes\nKYTY_BC5_JOB_PUSH_WAIT\njob-arena fix APPLIED\n' > "$W/kytyplus-build/src/kyty_emulator" ;;
esac
EOS
    chmod +x "$T"/bin/*
}
pins() {
    python - "$HERE/int0388j.sh" "$S/int0388j.sh" "$(m "$W/kytyplus-build/src/kyty_emulator")" "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" "$(m "$W/backend-ubuntu/libbc5_backend.a")" "$(grep -v '^index ' "$T/old.diff" | md5sum | cut -c1-8)" "$(m "$S/0001-new.patch")" "$(m "$KIT/manifest.txt")" << 'EOS'
import re, sys
s = open(sys.argv[1], encoding="utf-8", newline="").read()
s, n = re.subn(r"^EXPECT_NORMAL=.*$", "EXPECT_NORMAL=%s; EXPECT_LEAN=%s; EXPECT_ARCHIVE=%s; EXPECT_PATCH=%s; EXPECT_NEW=%s; EXPECT_KIT=%s" % tuple(sys.argv[3:9]), s, flags=re.M)
assert n == 1
open(sys.argv[2], "w", encoding="utf-8", newline="").write(s)
EOS
}
run() { ( cd "$S" && PATH="$T/bin:$PATH" HOME="$H" bash int0388j.sh ) > "$T/out" 2>&1; rc=$?; }
restored='[ $rc != 0 ] && grep -qx normal $W/kytyplus-build/src/kyty_emulator && grep -qx lean $W/kytyplus-build-lean/src/kyty_emulator && grep -qx arch $W/backend-ubuntu/libbc5_backend.a && grep -qx a0 $K/src/a.cpp && grep -qx o0 $K/src/old.hpp && [ ! -e $K/src/bc5/job_push_wait.hpp ] && grep -qx d0 $BS/src/d.cpp && grep -qx r0 $TL/m/r.rs && grep -q release $H/lock.log'

setup; run
check "success: exit 0" '[ $rc = 0 ]'
check "success: claimed and released" 'grep -q claim $H/lock.log && grep -q release $H/lock.log'
check "success: both binaries, the archive as it was" 'grep -q normal2 $W/kytyplus-build/src/kyty_emulator && grep -q lean2 $W/kytyplus-build-lean/src/kyty_emulator && grep -qx arch $W/backend-ubuntu/libbc5_backend.a'
check "success: the rollback copies" 'grep -qx normal $W/exp0388/integration2/kyty_emulator.before-j && grep -qx arch $W/exp0388/integration2/libbc5_backend.a.before-j'
check "success: changed, removed and new files" 'grep -qx a1 $K/src/a.cpp && [ ! -e $K/src/old.hpp ] && [ -e $K/src/bc5/job_push_wait.hpp ] && grep -qx d1 $BS/src/d.cpp && grep -qx r1 $TL/m/r.rs'

setup; echo other > "$W/kytyplus-build/src/kyty_emulator"; run
check "a wrong binary: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; echo x > "$K/src/bc5/job_push_wait.hpp"; run
check "a new file already there: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; echo x >> "$BS/src/d.cpp"; run
check "another backend file: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; echo x >> "$KIT/T/m/r.rs"; run
check "a damaged kit: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; python -c "import sys;p=sys.argv[1];s=open(p).read().replace('exp 0372\n','');open(p,'w').write(s)" "$S/0001-new.patch"; pins; run
check "a candidate without exp 0372: stops before the lock" '[ $rc != 0 ] && [ ! -e $H/lock.log ]'
setup; TEST_FAIL=archive; export TEST_FAIL; run; unset TEST_FAIL
check "a failed archive build restores all" "$restored"
setup; TEST_FAIL=lean; export TEST_FAIL; run; unset TEST_FAIL
check "a failed lean build restores all" "$restored"
setup; TEST_FAIL=archchange; export TEST_FAIL; run; unset TEST_FAIL
check "a changed archive restores all" "$restored"
setup; TEST_DIFF=$T/old.diff; export TEST_DIFF; run; unset TEST_DIFF
check "a tree diff that is not the candidate restores all" "$restored"
echo "== $ok passed, $bad failed"
rm -rf "$T"
[ "$bad" = 0 ]
