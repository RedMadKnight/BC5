#!/usr/bin/env bash
# BC5 exp 0424: the PRIVATE test build (the top session's GO, 2026-11-15 21:06): patch 4945ef1b's tree copied to
# ~/bc5-work/exp0424/tree (no .git), mk0424.py (the fix aq424 behind BC5_DIRECT_ACB_QUEUE_STATE, off by default; the
# catcher aq424c, normal only), then configured and built from scratch in exp0424/build-normal and exp0424/build-lean
# with the shared builds' options (CMakeCache of ~/bc5-work/kytyplus-build). ~/src/KytyPlus, the shared build
# directories, the backend source and archive are only read. CPU only, no emulator; one BOX-LOCK line.
# usage (on the box, detached, in ~/bc5-work/exp0424): bash b0424.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; E=$W/exp0424; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
m8() { md5sum < "$1" | cut -c1-8; }
stop() { echo "b0424 STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 4945ef1b ] || stop "the shared tree is not 4945ef1b"
[ "$(m8 "$K/src/libs/bc5LleAgc.cpp")" = 3e847e03 ] || stop "the shared unit is not 3e847e03"
[ "$(m8 "$ARCH")" = 9aab722c ] || stop "the archive is not 9aab722c"
[ -s "$W/kytyplus-build/externals/ffmpeg-94dde08.zip" ] || stop "no shared ffmpeg prebuilt"
. "$N/chainlock0417.inc"
chain_claim "exp 0424: private test build (acb queue state + refit catcher) under exp0424, configure + full build of normal and lean, CPU only" 60 || stop "no lock"
if [ -e "$E/tree" ]; then  # a second round: the tree of the first, already edited
    [ "$(m8 "$E/tree/src/libs/bc5LleAgc.cpp")" = 11e0de65 ] || stop "$E/tree exists and its unit is not 11e0de65"
else
    mkdir -p "$E/tree" && (cd "$K" && tar --exclude=./.git -cf - .) | (cd "$E/tree" && tar -xf -) || stop "cannot copy the tree"
    [ "$(m8 "$E/tree/src/libs/bc5LleAgc.cpp")" = 3e847e03 ] || stop "the copied unit is not 3e847e03"
    python3 "$HERE/mk0424.py" "$E/tree" || stop "mk0424.py refused"
fi
[ "$(m8 "$E/tree/src/libs/bc5LleAgc.cpp")" = 11e0de65 ] || stop "the new unit is $(m8 "$E/tree/src/libs/bc5LleAgc.cpp"), not the laptop's 11e0de65"
echo "$(date +%T) tree ready: the unit 3e847e03 -> 11e0de65"
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator started; stopped before $v"
    d=$E/build-$v; x="-DKYTY_BC5_LEAN=OFF"; [ $v = lean ] && x="-DKYTY_BC5_LEAN=ON"
    # 3rdparty/ffmpeg-core names its prebuilt by the submodule's git SHA and downloads it when absent; the tree has no .git
    # (the SHA reads empty), so the shared build's own copy (ffmpeg-94dde08.zip) is put under the name it then looks for.
    # Nothing is downloaded.
    mkdir -p "$d/externals" && cp -p "$W/kytyplus-build/externals/ffmpeg-94dde08.zip" "$d/externals/ffmpeg-.zip" || stop "cannot place the ffmpeg prebuilt"
    echo "== $(date +%T) configure $v"
    distrobox enter ubuntu -- cmake -S "$E/tree" -B "$d" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $x < /dev/null > "$d.configure.log" 2>&1 || { tail -5 "$d.configure.log"; stop "configure $v"; }
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m12 -E "error:" "$d.build.log" | cut -c1-260; stop "build $v"; }
    b=$d/src/kyty_emulator
    echo "$v: $(m8 "$b"), warnings $(grep -c 'warning:' "$d.build.log"), in bc5LleAgc: $(grep 'warning:' "$d.build.log" | grep -c bc5LleAgc); word BC5_DIRECT_ACB_QUEUE_STATE $(strings "$b" | grep -cx BC5_DIRECT_ACB_QUEUE_STATE), catcher text $(strings "$b" | grep -c 'tag aq424c')"
done
[ "$(strings "$E/build-normal/src/kyty_emulator" | grep -c 'tag aq424c')" -ge 1 ] || stop "normal lacks the catcher"
[ "$(strings "$E/build-lean/src/kyty_emulator" | grep -c 'tag aq424')" = 0 ] || stop "lean holds aq424 text (symbol names like aq424_on are not text)"
[ "$(strings "$E/build-lean/src/kyty_emulator" | grep -cx BC5_DIRECT_ACB_QUEUE_STATE)" = 1 ] || stop "lean does not read the switch"
[ "$(m8 "$ARCH")" = 9aab722c ] || stop "the archive changed"
echo "b0424 done $(date +%T): normal $(m8 "$E/build-normal/src/kyty_emulator"), lean $(m8 "$E/build-lean/src/kyty_emulator")"
