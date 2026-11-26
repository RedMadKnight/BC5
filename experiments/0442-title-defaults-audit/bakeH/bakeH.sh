#!/usr/bin/env bash
# BC5 bake H (2026-11-24, D31, the top session's order): the shared builds rebuilt with the host toolchain
# (~/bc5-toolchain, F928), source UNCHANGED: KytyPlus tree 8a9ed0cf (~/src/KytyPlus, checked by kytyplus-tree.sh), the
# backend export ~/bc5-work/d19/export/backend, bc5-mount from main's tools/ (unchanged since 91cbf0c3, the source of
# the shared 1aa3866a). No functional row. Options as the accepted host builds (F928): SDL_SNDIO=OFF, -include cstdint,
# glslang/lzma/opus from the toolchain.
# CMake build directories hold absolute paths and cannot be moved, so the swap moves the container-built directories
# aside as <dir>.container-1124 (kept whole: the undo) and builds fresh ones at the shared paths:
#   ~/bc5-work/backend-ubuntu (archive), kytyplus-build (normal), kytyplus-build-lean (lean), bc5-tools-ubuntu (bc5-mount)
#   bakeH.sh check    pins, toolchain, tree, free space, no emulator, no lock line; writes nothing
#   bakeH.sh swap     check, lock, move aside, build, host-deps-check, md5s; any failure undoes by itself
#   bakeH.sh undo     the fresh directories to ~/bc5-work/bakeH/undone-<time>/, the .container-1124 ones back, md5s checked
set -uo pipefail
export LC_ALL=C
W=$HOME/bc5-work; HERE=$(cd "$(dirname "$0")" && pwd); BC5=$HERE/bc5; T=$HOME/bc5-toolchain; X=$W/bakeH
K=$HOME/src/KytyPlus; E=$W/d19/export/backend; LOCK=$W/BOX-LOCK; SUF=container-1124
DIRS="backend-ubuntu kytyplus-build kytyplus-build-lean bc5-tools-ubuntu"
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
SA=$W/backend-ubuntu/libbc5_backend.a; SM=$W/bc5-tools-ubuntu/release/bc5-mount
OLD_N=fd8e44e1 OLD_L=1e47486a OLD_A=ba25f31c OLD_M=1aa3866a EXPORT_SUM=59c877fa  # relative paths; = 9264fa2e by hb.sh's absolute-path method (F928)
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
say() { mkdir -p "$X"; echo "$(date +%T) bakeH: $*" | tee -a "$X/bakeH.log"; }
die() { say "STOP: $*"; exit 1; }
export_sum() { (cd "$E" && find src include -type f | sort | xargs md5sum | md5sum | cut -c1-8); }
check() {
    (cd "$HERE" && md5sum -c --quiet MANIFEST.md5) || die "the kit does not match its MANIFEST.md5"
    pgrep -x kyty_emulator > /dev/null && die "an emulator runs"
    pgrep -x bc5-mount > /dev/null && die "a bc5-mount runs"
    [ -s "$LOCK" ] && die "BOX-LOCK holds a line: $(cat "$LOCK")"
    [ -r "$T/env.sh" ] || die "no toolchain at $T (tools/scripts/bc5-toolchain.sh)"
    BC5_SRC=$BC5 bash "$BC5/tools/scripts/kytyplus-tree.sh" check "$K" > /dev/null || die "the shared tree is not 8a9ed0cf"
    [ "$(export_sum)" = "$EXPORT_SUM" ] || die "the backend export is $(export_sum), not $EXPORT_SUM"
    local avail; avail=$(( $(df --output=avail -B1 "$W" | tail -1) / 1024 / 1024 / 1024 )); [ "$avail" -ge 10 ] || die "only $avail GB free"
}
pins_old() { [ "$(m8 "$NB")" = $OLD_N ] && [ "$(m8 "$LB")" = $OLD_L ] && [ "$(m8 "$SA")" = $OLD_A ] && [ "$(m8 "$SM")" = $OLD_M ]; }
lock() {
    LINE="bake H | host-toolchain rebuild of the shared builds (source unchanged), token $(date +%s)$$ | $(date '+%F %T')"
    local tl=$LOCK.bakeH-$$.new al=$LOCK.bakeH-$$.aside
    [ -e "$LOCK" ] || touch "$LOCK"
    printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the lock claim failed"; }
    if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign lock line arrived"; fi
    rm -f "$al" "$tl"; trap unlock EXIT
}
unlock() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.bakeH-$$.rel"; mv -fT "$LOCK.bakeH-$$.rel" "$LOCK"; fi; }
undo() {
    local u=$X/undone-$(date +%H%M%S) d ok=1
    for d in $DIRS; do [ -d "$W/$d.$SUF" ] || die "no $W/$d.$SUF to put back"; done
    pgrep -x kyty_emulator > /dev/null && die "an emulator runs"
    mkdir -p "$u"
    for d in $DIRS; do
        [ -e "$W/$d" ] && { mv -T "$W/$d" "$u/$d" || { say "cannot move $W/$d aside"; ok=0; continue; }; }
        mv -T "$W/$d.$SUF" "$W/$d" || { say "cannot put $d back"; ok=0; }
    done
    pins_old && say "undo: back to normal $OLD_N, lean $OLD_L, archive $OLD_A, bc5-mount $OLD_M (the host-built dirs in $u)" || { say "undo: the binaries do not read back as the pins"; ok=0; }
    [ $ok = 1 ]
}
build() {
    . "$T/env.sh"
    local NJ="nice -n 10" L=$X/logs; mkdir -p "$L"
    $NJ cmake -S "$E" -B "$W/backend-ubuntu" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF -DBC5_REIMPL_NAME_TABLES=anyps5 > "$L/backend-configure.log" 2>&1 || return 1
    $NJ cmake --build "$W/backend-ubuntu" -j16 > "$L/backend-build.log" 2>&1 || return 1
    local v dir lean
    for v in normal lean; do
        if [ $v = normal ]; then dir=$W/kytyplus-build lean=OFF; else dir=$W/kytyplus-build-lean lean=ON; fi
        $NJ cmake -S "$K" -B "$dir" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
            -DKYTY_BUILD_LAUNCHER=OFF -DKYTY_BC5_BACKEND_SRC="$E" -DKYTY_BC5_BACKEND_BUILD="$W/backend-ubuntu" -DKYTY_BC5_LEAN=$lean \
            -DCMAKE_CXX_FLAGS="-include cstdint" -DSDL_SNDIO=OFF -DKYTY_GLSLANG_VALIDATOR="$T/bin/glslangValidator" \
            -DKYTY_LZMA_LIBRARY="$T/sysroot/usr/lib64/liblzma.so" -DKYTY_OPUS_LIBRARY="$T/sysroot/usr/lib64/libopus.so" \
            > "$L/$v-configure.log" 2>&1 || return 1
        $NJ cmake --build "$dir" --target kyty_emulator -j16 > "$L/$v-build.log" 2>&1 || return 1
    done
    (cd "$BC5/tools" && CARGO_TARGET_DIR="$W/bc5-tools-ubuntu" $NJ cargo build --release --locked -p bc5-mount) > "$L/mount-build.log" 2>&1 || return 1
}
case "${1:-}" in
  check) check; pins_old || die "the shared builds are not $OLD_N/$OLD_L/$OLD_A/$OLD_M"
         for d in $DIRS; do [ -e "$W/$d.$SUF" ] && die "$W/$d.$SUF exists already"; done
         say "check: OK (tree 8a9ed0cf, export $EXPORT_SUM, shared $OLD_N/$OLD_L/$OLD_A/$OLD_M, $(. "$T/env.sh"; clang --version | head -1))" ;;
  swap)
    check; pins_old || die "the shared builds are not the pinned container-built ones"
    for d in $DIRS; do [ -e "$W/$d.$SUF" ] && die "$W/$d.$SUF exists already"; done
    lock; say "swap: lock taken; moving the container-built directories aside"
    for d in $DIRS; do mv -T "$W/$d" "$W/$d.$SUF" || { say "cannot move $d aside"; undo; exit 1; }; done
    t0=$(date +%s)
    if ! build; then say "the build failed (logs in $X/logs): undo"; undo; exit 1; fi
    say "built in $(( $(date +%s) - t0 )) s"
    if ! bash "$BC5/tools/scripts/host-deps-check.sh" "$NB" "$LB" "$SM" | tee -a "$X/bakeH.log"; then say "host-deps-check failed: undo"; undo; exit 1; fi
    say "swap done: normal $(m8 "$NB") $(stat -c %s "$NB") B, lean $(m8 "$LB") $(stat -c %s "$LB") B, archive $(m8 "$SA"), bc5-mount $(m8 "$SM"); undo files: $W/*.$SUF; warnings normal $(grep -c 'warning:' "$X/logs/normal-build.log"), lean $(grep -c 'warning:' "$X/logs/lean-build.log")" ;;
  undo) lock; undo ;;
  *) echo "usage: bakeH.sh check|swap|undo"; exit 2 ;;
esac
