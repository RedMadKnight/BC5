#!/usr/bin/env bash
# BC5 exp 0381: dry run of tb2run0381.sh build + build0381tb2.sh with stand-ins: a temporary HOME with made-up shared files and a
# tiny git tree for KytyPlus, and stand-ins for distrobox, pgrep, python3 and strings. No box, no ssh, no GPU. It checks the
# outcome line, the lock and each stop. The real compile and link are not exercised. usage (in a git checkout): bash test_tb2run0381.sh
HERE=$(cd "$(dirname "$0")" && pwd)
# These tests need r1's launcher itself, read from the box by agreement after the maintainer's play, and the two PIN_TB2_ pins it gives.
[ -f "$HERE/raw/play-pkg-0380r1.sh" ] && [ "$(md5sum < "$HERE/raw/play-pkg-0380r1.sh" | cut -c1-8)" = 299a2519 ] || { echo "NOT RUN: no raw/play-pkg-0380r1.sh at 299a2519"; exit 3; }
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
*build0380y.py*) o=$(echo "$c" | sed 's/.*obj //; s/ .*//'); printf '#!/bin/sh\n' > "$o"; chmod +x "$o" ;;
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
REAL_HOME=$HOME REAL_PATH=${PATH#"$T/bin:"}
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
    # r1's launcher itself (299a2519, raw/play-pkg-0380r1.sh), so the order is tested on the real file.
    cp "$HERE/raw/play-pkg-0380r1.sh" "$W/exp0380r1/play-pkg-0380r1.sh"
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
$(grep '^PIN_TB2_' "$HERE/pins0381tb2.env")
PINS
    git -C "$HERE" show 4968372:backend/kytyplus-patches/0001-bc5-lle-agc.patch > /dev/null
    unset FAIL_AT NO_TESTS UNIT_BAD TB2_PINS
}
# The real driver, with one change: the fake patch goes over in place of the real one, and the box scripts see the test's pins.
run() {
    sed -e 's#git -C "$TOP" show "$NP:$PATCHFILE" > "$X/patch0001-np.patch"#cp "$STAND/fake.patch" "$X/patch0001-np.patch"#' "$HERE/tb2run0381.sh" > "$HERE/.tb2run-test.sh"
    (cd "$HERE" && TB2_PINS_ABS=$T/pins.env bash .tb2run-test.sh build "$T") > "$T/out" 2>&1
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
setup; sed -i 's/^PIN_SRC_TREE=.*/PIN_SRC_TREE=0000000000000000000000000000000000000000/' "$T/pins.env"; r=$(run)
expect "the tree is not the pinned one: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'not the pinned src tree' '$T/out'"
setup; echo x > "$X/src/KytyPlus/src/libs/extra.cpp"; r=$(run)
expect "the shared tree differs beyond the two files: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'beyond the two approved' '$T/out'"
setup; echo x > "$T/pins.tmp"; sed -i 's/^PIN_0372_LINES=.*/PIN_0372_LINES=9/' "$T/pins.env"; r=$(run)
expect "exp 0372's pieces are not all there: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'exp 0372' '$T/out'"
setup; mkdir -p "$X/bc5-work/exp0381/tb2/bin"; echo x > "$X/bc5-work/exp0381/tb2/bin/kyty_emulator"; r=$(run)
expect "an existing binary is not overwritten" "[ $r != 0 ] && [ \"\$(cat '$X/bc5-work/exp0381/tb2/bin/kyty_emulator')\" = x ]"
# The switches: reset first, read as data by name and value, the log says the effective state. The block runs as built, with only its input path changed.
setup; r=$(run)
L=$X/bc5-work/exp0381/tb2/play-pkg-0381tb2.sh; S2=$X/bc5-work/exp0381/tb2/play-pkg-0381tb2s.sh; SW=$X/bc5-work/exp0381/tb2/switches.env
expect "switches: the file is there, every line commented" "[ $r = 0 ] && [ -f '$SW' ] && ! grep -q '^BC5' '$SW' && grep -q '^# BC5_DIRECT_ARGS_WB=first' '$SW'"
expect "switches: after both settings files, the log next, the check right before the emulator" "[ \$(grep -n '  done < \"\$PKG_ENV\"' '$L' | cut -d: -f1) -lt \$(grep -n '^SWF=' '$L' | cut -d: -f1) ] && grep -A1 '^# end of exp 0381 test build 2' '$L' | grep -qx '{' && grep -A2 '^  tb2_check$' '$L' | grep -q '^  \"\$EMU\" --game'"
expect "switches: the log's own reads of the two files stay, and do not stop the build" "tail -n +\$(grep -n '^# end of exp 0381 test build 2' '$L' | cut -d: -f1) '$L' | grep -q 'grep -v .*\"\$PKG_ENV\"'"
expect "switches: the smoke reads none" "grep -q '^SWF=/dev/null$' '$S2'"
sed -n '/the switches, read from/,/^# end of exp 0381 test build 2/p' "$L" > "$T/block"
blk() {
    f=$1; shift
    sed "s#^SWF=.*#SWF=$f#" "$T/block" > "$T/b2"
    env HOME="$REAL_HOME" PATH="$REAL_PATH" "$@" bash -c 'set -u; . "$1"; echo "[$TB2_SW] wb=${BC5_DIRECT_ARGS_WB:-} fl=${BC5_DIRECT_ARGS_FLUSH:-} dr=${BC5_DIRECT_ARGS_FLUSH_DRAWS:-} j=${BC5_DIRECT_DRAW_ARGS_JOURNAL:-} copy=${BC5_DIRECT_ARGS_COPY:-} yz=${BC5_DIRECT_GPU_CHECK_YZ:-} fs=${BC5_DIRECT_FORCE_START_000:-} keep=${BC5_DIRECT_ACB_STATE_RESTORE:-}${BC5_CRASH_FRAMES:-}"' _ "$T/b2"
}
OFF='wb= fl= dr= j= copy= yz= fs='
INH='BC5_DIRECT_ARGS_FLUSH=all BC5_DIRECT_ARGS_FLUSH_DRAWS=1 BC5_DIRECT_DRAW_ARGS_JOURNAL=1 BC5_DIRECT_ARGS_WB=all'
res=$(blk "$SW" $INH)
expect "switches: inherited on, file commented: all off, the log empty" "[ \"\$res\" = '[] $OFF keep=' ]"
res=$(blk "$T/no-such-file" $INH)
expect "switches: inherited on, no file: all off, the log empty" "[ \"\$res\" = '[] $OFF keep=' ]"
res=$(blk "$T/no-such-file" BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_CRASH_FRAMES=1)
expect "switches: restore and crash frames are kept" "[ \"\$res\" = '[] $OFF keep=11' ]"
printf '%s\n' '# a comment' '' 'BC5_DIRECT_ARGS_WB=first' 'BC5_DIRECT_GPU_CHECK_YZ=256:64' > "$T/sw1"
res=$(blk "$T/sw1")
expect "switches: file on, the log gives the effective state" "[ \"\$res\" = '[ BC5_DIRECT_GPU_CHECK_YZ=256:64 BC5_DIRECT_ARGS_WB=first] wb=first fl= dr= j= copy= yz=256:64 fs= keep=' ]"
printf '%s\n' 'BC5_DIRECT_ARGS_WB=firts' 'BC5_DIRECT_ARGS_FLUSH=$(id)' 'BC5_DIRECT_FORCE_START_000=2' 'BC5_DIRECT_REBASE_DISPATCH=1' 'BC5_DIRECT_GPU_CHECK_YZ=0' ' BC5_DIRECT_ARGS_COPY=1' 'BC5_DIRECT_DRAW_ARGS_JOURNAL=1' 'BC5_DIRECT_GPU_CHECK_ZERO=1;id' > "$T/sw2"
res=$(blk "$T/sw2")
expect "switches: bad names and values refused by line number" "[ \"\$res\" = '[ REJECTED-LINES: 1 2 3 4 5 6 7 8] $OFF keep=' ]"
printf '%s\n' 'BC5_DIRECT_ARGS_WB=first' 'BC5_DIRECT_ARGS_WB=all' 'BC5_DIRECT_ARGS_FLUSH=all' 'BC5_DIRECT_ARGS_FLUSH=bad' > "$T/sw3"
res=$(blk "$T/sw3")
expect "switches: duplicates: the last valid line wins, and the log says so" "[ \"\$res\" = '[ BC5_DIRECT_ARGS_WB=all BC5_DIRECT_ARGS_FLUSH=all REJECTED-LINES: 4] wb=all fl=all dr= j= copy= yz= fs= keep=' ]"
printf 'BC5_DIRECT_ARGS_COPY=1' > "$T/sw4"
res=$(blk "$T/sw4")
expect "switches: a last line with no newline counts" "[ \"\$res\" = '[ BC5_DIRECT_ARGS_COPY=1] wb= fl= dr= j= copy=1 yz= fs= keep=' ]"
printf 'BC5_DIRECT_ARGS_COPY=1\r\n' > "$T/sw5"
res=$(blk "$T/sw5")
expect "switches: a CRLF line is refused" "[ \"\$res\" = '[ REJECTED-LINES: 1] $OFF keep=' ]"
setup; echo 'BC5_DIRECT_ARGS_WB=first' > "$T/keep"; mkdir -p "$X/bc5-work/exp0381/tb2"; cp "$T/keep" "$X/bc5-work/exp0381/tb2/switches.env"; r=$(run)
expect "switches: a rebuild keeps his file" "[ $r = 0 ] && cmp -s '$T/keep' '$X/bc5-work/exp0381/tb2/switches.env'"
setup; echo 'export BC5_DIRECT_ARGS_FLUSH=all' >> "$X/bc5-work/exp0380r1/play-pkg-0380r1.sh"; sed -i "s/^PIN_R1_LAUNCHER=.*/PIN_R1_LAUNCHER=$(m "$X/bc5-work/exp0380r1/play-pkg-0380r1.sh")/" "$T/pins.env"; r=$(run)
expect "switches: one set after the block stops the build" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'touched after the block' '$T/out'"
# The launcher as built, run whole on stand-ins for the emulator, the mount's two commands and pad-volume.sh, with HOME and PATH left alone: only the paths in its text move.
NAMES=$(sed -n 's/^TB2_NAMES="\(.*\)"$/\1/p' "$HERE/switches0381tb2.inc")
runl() {
    l=$1; shift
    R=$T/rt; rm -rf "$R"; RW=$R/bc5-work; RT=$RW/exp0381/tb2
    mkdir -p "$RT/bin" "$RW/exp0381/wd" "$R/bc5-data/pkg"; : > "$R/bc5-data/pkg/game.pkg"; : > "$RT/zero-list-20261029-120000.txt"
    printf '#!/usr/bin/env bash\nexit 0\n' > "$RW/pad-volume.sh"; cp "$RW/pad-volume.sh" "$RT/play-sample0379t.sh"
    printf '%s\n' '#!/usr/bin/env bash' '[ -e "$0.first" ] || { touch "$0.first"; env | sort > "$0.env1"; exit 75; }' 'env | sort > "$0.env2"; echo "$*" > "$0.args"; exit 0' > "$RT/bin/kyty_emulator"
    chmod +x "$RW/pad-volume.sh" "$RT/bin/kyty_emulator"
    cp "$T/run.env" "$RW/bc5-run.env"; [ -f "$T/pkg.env" ] && cp "$T/pkg.env" "$RW/bc5-pkg.env"; [ -f "$T/sw.env" ] && cp "$T/sw.env" "$RT/switches.env"
    { echo '#!/usr/bin/env bash'; echo 'pgrep() { return 1; }; mountpoint() { return 0; }'; tail -n +2 "$l"; } | sed -e "s#~/#$R/#g" -e "s#\$HOME#$R#g" > "$R/l.sh"
    env HOME="$REAL_HOME" PATH="$REAL_PATH" "$@" bash "$R/l.sh" > "$R/out" 2>&1
    echo $?
}
# What the log's first line says, and what the emulator's environment holds, in the same form.
logsw() { sed -n '1s/.*switches:\(.*\); binary .*/\1/p' "$R"/bc5-work/exp0381/tb2/play/play-*.log; }
gotsw() { o=""; for n in $NAMES; do v=$(grep "^$n=" "$1" | cut -d= -f2-) && o="$o $n=$v"; done; echo "${o:- none}"; }
KEPT='BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8'
kept() { for k in $KEPT; do grep -qx "$k" "$1" || return 1; done; }
# The emulator's first start (it asks for a restart) and its second: same switches, the same as the log, and the launcher's other settings kept.
same() { [ "$rl" = 0 ] && [ "$(logsw)" = "$1" ] && [ "$(gotsw "$E1")" = "$1" ] && [ "$(gotsw "$E2")" = "$1" ] && kept "$E1" && kept "$E2"; }
E1=$T/rt/bc5-work/exp0381/tb2/bin/kyty_emulator.env1; E2=$T/rt/bc5-work/exp0381/tb2/bin/kyty_emulator.env2
setup; r=$(run); LR=$T/l-real; SR=$T/s-real; cp "$L" "$LR"; cp "$S2" "$SR"
[ -z "${TB2_KEEP:-}" ] || { cp "$L" "$TB2_KEEP/play-pkg-0381tb2.sh"; cp "$S2" "$TB2_KEEP/play-pkg-0381tb2s.sh"; }
ON='BC5_DIRECT_ARGS_WB=all
BC5_DIRECT_ARGS_FLUSH=all
BC5_DIRECT_ARGS_FLUSH_DRAWS=1
BC5_DIRECT_DRAW_ARGS_JOURNAL=1
BC5_DIRECT_FORCE_START_000=1
BC5_DIRECT_GPU_CHECK_ZERO=1
BC5_DIRECT_GPU_CHECK_YZ=256
BC5_DIRECT_ARGS_COPY=1
BC5_DIRECT_REBASE_DISPATCH=1'
{ echo "PLAY_ARGS=--from-run-env"; echo "$ON"; } > "$T/run.env"; { echo "BC5_TB2_PKG_KEPT=1"; echo "$ON"; } > "$T/pkg.env"; cp "$HERE/switches0381tb2.env" "$T/sw.env"
rl=$(runl "$LR" $ON)
expect "launcher: outside, run.env and a late pkg.env all on, file commented: all off, log and emulator agree, the rest kept" "same ' none' && grep -qx BC5_TB2_PKG_KEPT=1 '$E1'"
expect "launcher: the arguments reach the emulator" "grep -q -- '--game .*--from-run-env --fullscreen' '$T/rt/bc5-work/exp0381/tb2/bin/kyty_emulator.args'"
rm -f "$T/sw.env"; rl=$(runl "$LR" $ON)
expect "launcher: the same with no switches file" "same ' none'"
printf '%s\n' 'BC5_DIRECT_ARGS_WB=first' 'BC5_DIRECT_GPU_CHECK_YZ=256:64' 'BC5_DIRECT_ARGS_FLUSH=bad' > "$T/sw.env"; rl=$(runl "$LR" $ON)
expect "launcher: the file beats both, and the emulator gets what the log says" "[ \"\$rl\" = 0 ] && [ \"\$(logsw)\" = ' BC5_DIRECT_GPU_CHECK_YZ=256:64 BC5_DIRECT_ARGS_WB=first REJECTED-LINES: 3' ] && [ \"\$(gotsw '$E1')\" = ' BC5_DIRECT_GPU_CHECK_YZ=256:64 BC5_DIRECT_ARGS_WB=first' ] && [ \"\$(gotsw '$E2')\" = \"\$(gotsw '$E1')\" ] && kept '$E1'"
rl=$(runl "$SR" $ON)
expect "launcher: the smoke runs with all off whatever the files say" "same ' none'"
sed '/^} > "\$LOG"$/a export BC5_DIRECT_ARGS_FLUSH=all' "$LR" > "$T/l-late"; rl=$(runl "$T/l-late")
expect "launcher: a switch set after the block: the emulator does not start, and the log says why" "[ \"\$rl\" = 1 ] && [ ! -e '$E1' ] && grep -q 'changed after the block, not started: BC5_DIRECT_ARGS_FLUSH=all' $T/rt/bc5-work/exp0381/tb2/play/play-*.log"
r1=$X/bc5-work/exp0380r1/play-pkg-0380r1.sh
repin() { sed -i "s/^PIN_R1_LAUNCHER=.*/PIN_R1_LAUNCHER=$(m "$r1")/" "$T/pins.env"; }
setup; sed -n '/^if \[ -r "\$PKG_ENV" \]; then$/,/^fi$/p' "$r1" > "$T/loop"; sed -i '/^if \[ -r "\$PKG_ENV" \]; then$/,/^fi$/d' "$r1"; sed -i "/^} > \"\\\$LOG\"$/r $T/loop" "$r1"; repin; r=$(run)
expect "generator: pkg.env loaded after the block stops the build" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'not after both settings files' '$T/out'"
setup; sed -i '/^cd ~\/bc5-work$/i while IFS= read -r x; do :; done < "$HOME/other.env"' "$r1"; repin; r=$(run)
expect "generator: another file loaded after the block stops the build" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'touched after the block' '$T/out'"
setup; sed -i '/^  # shellcheck disable=SC2086$/d' "$r1"; repin; r=$(run)
expect "generator: no place for the check stops the build" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'tb2_check' '$T/out'"
setup; sed -i '2i # a changed line' "$r1"; repin; r=$(run)
expect "generator: launchers that are not the reviewed text stop the build" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'not the reviewed text' '$T/out'"
# The rebased mode: the shared tree holds the fixes, and only two units are compiled.
rebased() {
    setup
    K=$X/src/KytyPlus
    echo two > "$K/src/libs/libC.cpp"; echo two > "$K/src/libs/libNpCppWebApi.cpp"
    { echo "PIN_MODE=rebased"; echo "PIN_LIBC=$(m "$K/src/libs/libC.cpp")"; echo "PIN_NP=$(m "$K/src/libs/libNpCppWebApi.cpp")"; } >> "$T/pins.env"
}
rebased; r=$(run)
expect "rebased: done, with no patched tree and two units" "[ $r = 0 ] && q | grep -q 'build done' && [ ! -e '$X/bc5-work/exp0381/tb2/tree' ] && [ ! -e '$X/bc5-work/exp0381/tb2/src/libs/libC.cpp' ]"
rebased; echo three > "$X/src/KytyPlus/src/libs/libC.cpp"; r=$(run)
expect "rebased: the shared tree lacks the fix: FAILED" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'does not hold the NP and libc' '$T/out'"
rebased; sed -i 's/^PIN_LIBC=.*/PIN_LIBC=FILL/' "$T/pins.env"; r=$(run)
expect "rebased: unfilled pins: FAILED, the lock cleared" "[ $r != 0 ] && q | grep -q 'build FAILED' && grep -q 'not filled in' '$T/out' && [ -z \"\$(lock)\" ]"
export HOME=$REAL_HOME
exit $fail
