#!/usr/bin/env bash
# BC5 exp 0381: dry run of tb2run0381.sh build + build0381tb2.sh with stand-ins: a temporary HOME with made-up shared files and a
# tiny git tree for KytyPlus, and stand-ins for distrobox, pgrep, python3 and strings. No box, no ssh, no GPU. It checks the
# outcome line, the lock and each stop. The real compile and link are not exercised. usage (in a git checkout): bash test_tb2run0381.sh
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
*build0380y.py*) o=$(echo "$c" | sed 's/.*obj //; s/ .*//'); printf 'x\n' > "$o"; chmod +x "$o" ;;
*bc5_backend_tests*) [ "${NO_TESTS:-}" = 1 ] && echo "No tests ran" || { echo "All tests passed (1 assertion in 1 test case)"; echo; } ;;
esac
exit 0
EOF
cat > "$T/bin/strings" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$T/bin/python3" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -I ] && shift
if [ -n "${UNIT_BAD:-}" ]; then echo bad > "$3"; else cp "$2" "$3"; fi
EOF
cat > "$T/remote" <<'EOF'
#!/usr/bin/env bash
exec bash -c "$1"
EOF
chmod +x "$T/bin/"* "$T/remote"
export STAND=$T PATH=$T/bin:$PATH PC_REMOTE="$T/remote"
REAL_HOME=$HOME
X=$T/home
m() { md5sum < "$1" | cut -c1-8; }
setup() {
    export HOME=$X
    rm -rf "$X" "$T/emulator"; W=$X/bc5-work
    mkdir -p "$W/exp0381" "$W/kytyplus-build/src" "$W/kytyplus-build-lean/src" "$W/backend-ubuntu" "$W/exp0380r1/bin" "$W/exp0380r1/src/libs/bc5" "$W/exp0380r1/src/loader" "$X/src/KytyPlus/src/libs" "$X/src/KytyPlus/src/bc5"
    : > "$W/BOX-LOCK"; : > "$W/BOX-QUEUE"
    echo a > "$W/kytyplus-build/src/kyty_emulator"; echo b > "$W/kytyplus-build-lean/src/kyty_emulator"; echo c > "$W/backend-ubuntu/libbc5_backend.a"; echo d > "$W/play-pkg.sh"
    echo e > "$W/exp0380r1/bin/kyty_emulator"; echo f > "$W/exp0380r1/src/libs/bc5LleAgc.cpp"; echo g > "$W/exp0380r1/src/loader/runtimeLinker.cpp"; echo h > "$W/exp0380r1/src/libs/bc5/zero_skip.hpp"
    echo z > "$W/exp0380r1/build0380y.py"; echo z > "$W/exp0380r1/zero-list-20261029-120000.txt"; echo z > "$W/exp0380r1/play-sample0379t.sh"
    printf '%s\n' 'cd ~/bc5-work' 'while read x; do :; done < /dev/null' 'done < "$ENVF"' 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt' 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play' 'export BC5_CRASH_FRAMES=1 BC5_0380_REC=1' > "$W/exp0380r1/play-pkg-0380r1.sh"
    sed -i '/^done < "\$ENVF"$/d' "$W/exp0380r1/play-pkg-0380r1.sh"; sed -i 's/^while read x; do :; done < \/dev\/null$/while read x; do :\ndone < "$ENVF"/' "$W/exp0380r1/play-pkg-0380r1.sh"
    K=$X/src/KytyPlus; echo one > "$K/src/libs/libC.cpp"; echo one > "$K/src/libs/libNpCppWebApi.cpp"; echo keep > "$K/src/libs/bc5LleAgc.cpp"; echo 'exp 0372' > "$K/src/bc5/pad_audio_route.hpp"
    git -C "$K" init -q; git -C "$K" config core.autocrlf false; git -C "$K" add -A; git -C "$K" -c user.email=a@b -c user.name=a commit -q -m base
    BC=$(git -C "$K" rev-parse HEAD)
    echo two > "$K/src/libs/libC.cpp"; echo two > "$K/src/libs/libNpCppWebApi.cpp"; git -C "$K" diff > "$T/fake.patch"
    git -C "$K" checkout -q .
    # What the shared tree holds is the patched tree with the two files unfixed, as on the box.
    git -C "$K" apply --check "$T/fake.patch" || exit 9
    TK=$T/tk; rm -rf "$TK"; mkdir -p "$TK"; git -C "$K" archive "$BC" | tar -x -C "$TK"; git -C "$TK" init -q; git -C "$TK" config core.autocrlf false; git -C "$TK" config core.safecrlf false; git -C "$TK" apply "$T/fake.patch"; git -C "$TK" add -A src; STREE=$(git -C "$TK" write-tree --prefix=src/)
    cat > "$T/pins.env" <<PINS
PIN_SHARED=$(m "$W/kytyplus-build/src/kyty_emulator")
PIN_LEAN=$(m "$W/kytyplus-build-lean/src/kyty_emulator")
PIN_ARCHIVE=$(m "$W/backend-ubuntu/libbc5_backend.a")
PIN_TREE_UNIT=$(m "$K/src/libs/bc5LleAgc.cpp")
PIN_PLAY_PKG=$(m "$W/play-pkg.sh")
PIN_R1_BIN=$(m "$W/exp0380r1/bin/kyty_emulator")
PIN_R1_UNIT=$(m "$W/exp0380r1/src/libs/bc5LleAgc.cpp")
PIN_R1_LINKER=$(m "$W/exp0380r1/src/loader/runtimeLinker.cpp")
PIN_R1_ZERO=$(m "$W/exp0380r1/src/libs/bc5/zero_skip.hpp")
PIN_R1_LAUNCHER=$(m "$W/exp0380r1/play-pkg-0380r1.sh")
PIN_UNIT=$(m "$W/exp0380r1/src/libs/bc5LleAgc.cpp")
PIN_HEADER=$(git -C "$HERE" show d6fa368:backend/include/bc5/acb_restore.hpp | md5sum | cut -c1-8)
PIN_PATCH=$(md5sum < "$T/fake.patch" | cut -d' ' -f1)
PIN_BASE_COMMIT=$BC
PIN_SRC_TREE=$STREE
PIN_0372_LINES=1
PINS
    git -C "$HERE" show 4968372:backend/kytyplus-patches/0001-bc5-lle-agc.patch > /dev/null
    unset FAIL_AT NO_TESTS UNIT_BAD TB2_PINS
}
# The real driver, with one change: the fake patch goes over in place of the real one, and the box scripts see the test's pins.
run() {
    sed -e 's#git -C "$TOP" show "$NP:$PATCHFILE" > "$X/patch0001-np.patch"#cp "$STAND/fake.patch" "$X/patch0001-np.patch"#' \
        -e "s#timeout \${PC_TIMEOUT:-900} \$REMOTE \"bash#timeout \${PC_TIMEOUT:-900} \$REMOTE \"TB2_PINS=$T/pins.env bash#" "$HERE/tb2run0381.sh" > "$HERE/.tb2run-test.sh"
    (cd "$HERE" && HERE_OVERRIDE=1 bash .tb2run-test.sh build "$T") > "$T/out" 2>&1
    r=$?
    rm -f "$HERE/.tb2run-test.sh"
    echo $r
}
q() { cat "$X/bc5-work/BOX-QUEUE"; }
lock() { cat "$X/bc5-work/BOX-LOCK"; }
fail=0
expect() { if eval "$2"; then echo "ok: $1"; else echo "FAIL: $1"; tail -8 "$T/out"; q; fail=1; fi; }

setup; touch "$T/emulator"; r=$(run)
expect "an emulator: stops, nothing recorded" "[ $r != 0 ] && [ -z \"\$(q)\" ] && [ -z \"\$(lock)\" ]"
setup; echo "top exp 0380 | B loop" > "$X/bc5-work/BOX-LOCK"; r=$(run)
expect "a foreign lock: stops, nothing recorded, the lock kept" "[ $r != 0 ] && [ -z \"\$(q)\" ] && lock | grep -q 'exp 0380'"
setup; r=$(run)
expect "all pass: done, and the lock stays for the smoke" "[ $r = 0 ] && q | grep -q 'build done' && lock | grep -q 'test build 2'"
expect "the launcher has the switch" "grep -q 'BC5_DIRECT_ACB_STATE_RESTORE=1' '$X/bc5-work/exp0381/tb2/play-pkg-0381tb2.sh'"
expect "the smoke launcher is on private saves" "grep -q 'exp0381/wd/_SaveData-pkg-play' '$X/bc5-work/exp0381/tb2/play-pkg-0381tb2s.sh' && ! grep -q '^cd ~/bc5-work\$' '$X/bc5-work/exp0381/tb2/play-pkg-0381tb2s.sh'"
for f in "cmake -S" "bc5_backend_tests" "ninja -t compdb" "build0380y.py"; do
    setup; export FAIL_AT="$f"; r=$(run)
    expect "[$f] fails: FAILED, no done, the lock cleared" "[ $r != 0 ] && q | grep -q 'build FAILED' && ! q | grep -q 'build done' && [ -z \"\$(lock)\" ]"
done
setup; export NO_TESTS=1; r=$(run)
expect "no tests ran: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED'"
setup; export UNIT_BAD=1; r=$(run)
expect "the unit is not the pinned one: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED'"
setup; echo x >> "$X/bc5-work/play-pkg.sh"; r=$(run)
expect "a shared pin differs: FAILED, nothing built" "[ $r != 0 ] && q | grep -q 'build FAILED' && [ ! -e '$X/bc5-work/exp0381/tb2/bin/kyty_emulator' ]"
setup; echo x >> "$X/src/KytyPlus/src/libs/libC.cpp"; git -C "$X/src/KytyPlus" -c user.email=a@b -c user.name=a commit -qam other; r=$(run)
expect "the tree is not the pinned one: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED'"
setup; mkdir -p "$X/bc5-work/exp0381/tb2/bin"; echo x > "$X/bc5-work/exp0381/tb2/bin/kyty_emulator"; r=$(run)
expect "an existing binary is not overwritten" "[ $r != 0 ] && [ \"\$(cat '$X/bc5-work/exp0381/tb2/bin/kyty_emulator')\" = x ]"
export HOME=$REAL_HOME
exit $fail
