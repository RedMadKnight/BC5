#!/usr/bin/env bash
# BC5 exp 0439 (tag d439): the kit of the diagnosis build on bake 2, over the shared tree of bake 1c+1d (unit ea564dbd,
# backend direct.cpp 9956715f; 11-22 night, the rebase the old private base needed). Writes ~/bc5-work/exp0439/d2/{new,be}
# only; nothing shared. Then box439b2.sh builds it with EXTRA_KY (libAmpr ap439, libVideoDec2 vd439) into d2/priv.
#   unit:    mkb2439.py (bake 2: ib/fl/ae/pc/cw/lw/fw/ds/fp439 and the defaults rows) + mkbl439.py (the black trigger,
#            the soft-CP lines, the effective words, the indirect-draw count, BC5_0439_SOFT_WAIT_MS) + mkvl439.py (the
#            flip label, both off)
#   ajm:     mkdm439b.py (dm439) ; libAmpr: mkap439.py (ap439) ; libVideoDec2: mkvd439.py (vd439)
#   backend: b2-ib-be.diff + b2be439.py on bake 1c+1d's backend (B2BE_DIRECT=9956715f)
#   prep439d.sh        (on the box, in ~/bc5-work/exp0439/k439)
set -u
K=$(cd "$(dirname "$0")" && pwd); D=$HOME/bc5-work/exp0439/d2; TREE=$HOME/src/KytyPlus; BTREE=$HOME/bc5-work/d19/export/backend
stop() { echo "prep439d STOP: $*"; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
[ "$(m8 "$TREE/src/libs/bc5LleAgc.cpp")" = ea564dbd ] || stop "the tree's unit is not ea564dbd"
[ "$(m8 "$BTREE/src/direct.cpp")" = 9956715f ] || stop "the backend's direct.cpp is not 9956715f"
[ "$(m8 "$BTREE/src/policy.cpp")" = 99303017 ] || stop "the backend's policy.cpp is not bakeR's 99303017" # 11-23: bakeR (the register catcher); b2be439 places the include hunk
rm -rf "$D/tmp" "$D/new" "$D/be"; mkdir -p "$D/tmp/orig" "$D/new" "$D/be/src" "$D/be/include/bc5" "$D/tmp/bt/backend" "$D/tmp/b1/src" || stop mkdir
cp "$TREE/src/libs/bc5LleAgc.cpp" "$TREE/src/graphics/presentation/videoOut.cpp" "$D/tmp/orig/" || stop "copy the units"
H=$(m8 "$TREE/src/bc5/switch_defaults.hpp")
MKB2439_UNIT=ea564dbd MKB2439_HDR=$H python3 -I "$K/mkb2439.py" "$D/tmp/orig" "$TREE/src/bc5/switch_defaults.hpp" "$D/tmp/out" || stop mkb2439
python3 -I "$K/mkbl439.py" "$D/tmp/out/bc5LleAgc.cpp" "$D/tmp/u1.cpp" && python3 -I "$K/mkvl439.py" "$D/tmp/u1.cpp" "$D/new/bc5LleAgc.cpp" || stop "mkbl/mkvl"
cp "$D/tmp/out/videoOut.cpp" "$D/tmp/out/switch_defaults.hpp" "$D/tmp/out/dc0439.hpp" "$D/tmp/out/cw0439.hpp" "$D/tmp/out/fp0439.hpp" "$D/new/" || stop "copy the kit headers"
cp "$K/fp0439.hpp" "$D/new/fp0439.hpp" || stop "fp0439.hpp (with vl439's flip_label_waits)"
mkdir -p "$D/tmp/dm" && cp "$TREE/src/libs/ajm/atrac9_decoder.h" "$TREE/src/libs/ajm.cpp" "$D/tmp/dm/" || stop "copy ajm"
python3 -I "$K/mkdm439b.py" "$D/tmp/dm" "$D/new" || stop mkdm439b
python3 -I "$K/mkap439.py" "$TREE/src/libs/libAmpr.cpp" "$D/new/libAmpr.cpp" || stop mkap439
cp "$TREE/src/main.cpp" "$TREE/src/kernel/pthread.cpp" "$D/new/" || stop "copy main.cpp / pthread.cpp (b2fix: the units that include switch_defaults.hpp)"
python3 -I "$K/mkwt439.py" "$TREE/src/graphics/presentation/window/window.cpp" "$D/new/window.cpp" || stop mkwt439 # exp 0439 (tag wt439)
python3 -I "$K/mktc439.py" "$TREE/src/libs/controller.cpp" "$D/new/window.cpp" "$D/new" && cp "$K/tc0439.hpp" "$D/new/" || stop mktc439 # exp 0439 (tag tc439): the touchpad fingers (EXTRA_KY += src/libs/controller.cpp)
python3 -I "$K/mksr439b.py" "$D/new/bc5LleAgc.cpp" "$D/new/controller.cpp" "$D/new" && cp "$K/sr0439b.hpp" "$D/new/" || stop mksr439b # exp 0439 (tag sr439b): the frame-dump catcher, BC5_0439_FRAME_DUMP
python3 -I "$K/mkpw439.py" "$D/new/bc5LleAgc.cpp" "$D/tmp/upw.cpp" && mv "$D/tmp/upw.cpp" "$D/new/bc5LleAgc.cpp" || stop mkpw439 # exp 0439 (tag pw439, mode 3, 11-23): the host hook, the per-frame counts, the timeout probe's piece dump
python3 -I "$K/mkph439.py" "$D/new/bc5LleAgc.cpp" "$D/tmp/uph.cpp" && mv "$D/tmp/uph.cpp" "$D/new/bc5LleAgc.cpp" && cp "$K/pw0439.hpp" "$D/new/" || stop mkph439 # exp 0439 (tag ph439, 11-23): the dcb hold for open piece waits
python3 -I "$K/mksr439c.py" "$D/new/bc5LleAgc.cpp" "$D/tmp/usc.cpp" && mv "$D/tmp/usc.cpp" "$D/new/bc5LleAgc.cpp" && cp "$K/sr0439c.hpp" "$K/f4p0439.hpp" "$D/new/" || stop mksr439c # exp 0439 (tag sr439c, 11-23): the pass census
python3 -I "$K/mkvf439.py" "$TREE/src/libs/videoDec2Decoder.cpp" "$D/new/videoDec2Decoder.cpp" && cp "$K/vf0439.hpp" "$D/new/" || stop mkvf439 # exp 0439 (tag vf439): the decode slot written whole (EXTRA_KY += src/libs/videoDec2Decoder.cpp)
python3 -I "$K/mkvd439.py" "$TREE/src/libs/libVideoDec2.cpp" "$D/new/libVideoDec2.cpp" || stop mkvd439
cp -r "$BTREE/src" "$BTREE/include" "$D/tmp/bt/backend/" && cp "$BTREE/src/direct.cpp" "$BTREE/src/policy.cpp" "$BTREE/src/full_state.cpp" "$D/tmp/b1/src/" || stop "copy the backend"
(cd "$D/tmp/bt" && git apply --reject -p1 "$K/b2-ib-be.diff" > "$D/tmp/patch.out" 2>&1); grep -c "Rejected hunk" "$D/tmp/patch.out" | sed 's/^/hunks failed (3 expected since bakeR, placed by b2be439): /'
B2BE_DIRECT=9956715f B2BE_POLICY=99303017 python3 -I "$K/b2be439.py" "$D/tmp/b1" "$D/tmp/bt/backend" || stop b2be439
python3 -I "$K/pw439patch.py" "$D/tmp/bt/backend/src/direct.cpp" && python3 -I "$K/mkdk439be.py" "$D/tmp/bt/backend/src/direct.cpp" && python3 -I "$K/mksr439cbe.py" "$D/tmp/bt/backend/src/direct.cpp" && python3 -I "$K/mkfn439be.py" "$D/tmp/bt/backend/src/direct.cpp" && python3 -I "$K/mkvd439be.py" "$D/tmp/bt/backend/src/direct.cpp" || stop "pw439patch / mkdk439be / mksr439cbe / mkfn439be / mkvd439be" # exp 0439 (tag pw439, 11-23): BC5_0439_PIECE_WAITS 1/2 on the bake-2 backend (it was only in the pre-rebase private backend)
cp "$D/tmp/bt/backend/src/direct.cpp" "$D/tmp/bt/backend/src/policy.cpp" "$D/tmp/bt/backend/src/full_state.cpp" "$D/be/src/" \
    && cp "$D/tmp/bt/backend/include/bc5/ib_chain.hpp" "$K/ds0439.hpp" "$K/pw0439.hpp" "$K/dk0439.hpp" "$K/sr0439c.hpp" "$D/be/include/bc5/" || stop "copy the backend kit"
cp "$K/box439b2.sh" "$K/build0438.py" "$D/" || stop "copy the build scripts"
echo "new:"; (cd "$D/new" && for f in *; do echo "$f=$(m8 "$f")"; done) | tr '\n' ' '; echo
echo "be:"; (cd "$D/be" && for f in src/direct.cpp src/full_state.cpp src/policy.cpp include/bc5/ib_chain.hpp include/bc5/ds0439.hpp include/bc5/pw0439.hpp include/bc5/dk0439.hpp include/bc5/sr0439c.hpp; do echo "$f=$(m8 "$f")"; done) | tr '\n' ' '; echo
