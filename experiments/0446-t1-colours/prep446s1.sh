#!/usr/bin/env bash
# exp 0446 (tag s1, 2026-11-26): the stage-1 bake candidate's sources (the top session's order of 11-26 ~08:10), from
# the shared tree (8a9ed0cf: ~/src/KytyPlus, backend ~/bc5-work/d19/export/backend) with exp 0439's kit steps, copied
# into exp0446/s1/k (never run from exp 0439's directory), in exp 0439's order (its note stage1-kit-steps.md):
#   unit:    mkb2439.py (+ mkb2439_add.py, mkfp439.py): the kSoft rows (IB_CHAIN, IB_CHAIN_FLAT, AGC_EOP_IDENT,
#            FLAT_APERTURE, DMA_SYNC, DMA_SYNC_MEC, DMA_SYNC_LABEL, PREFIX_CHAINS, CHAIN_WRITERS, AT9_DMC, DCC_PRESENT=2)
#            and the BC5_T2 FLAT_APERTURE / DMA_SYNC rows removed; then the EAGER_GPU_WRITE row taken out again here
#            (stage 1 leaves the memory question out); mkvl439.py + mkvlon439.py (FLIP_LABEL_PIECES, on by default);
#            mkdm439b.py (ajm: AT9_DMC); host-fakelib.diff (bc5Reimpl.cpp, runtimeLinker.cpp: fakelib/ precedence, pair rule)
#   backend: b2-ib-be.diff + b2be439.py (IB chain, ds439); mkcs439be.py (PASS_CONTEXT_CONTROL and its bundle, all off);
#            select-fakelib.diff (reimpl/select.cpp/.hpp)
# Not in stage 1 (reported): EAGER_GPU_WRITE and the descriptor import, every diagnostic step, the job-slot fix (g442,
# exp/0442 63ee9b53, not ported to 9956715f), EXIT noreturn (no source step found), -include cstdint (already a flag).
# Writes exp0446/s1/{new,be,tmp} only.
set -u
export LC_ALL=C
X=$HOME/bc5-work/exp0446; D=$X/${S1_DIR:-s1}; K=$X/s1/k; TREE=$HOME/src/KytyPlus; BTREE=$HOME/bc5-work/d19/export/backend; L=$HOME/bc5-work/exp0439/k439
stop() { echo "prep446s1 STOP: $*"; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
[ "$(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8)" = 8a9ed0cf ] || stop "the tree's diff is not 8a9ed0cf"
[ "$(m8 "$TREE/src/libs/bc5LleAgc.cpp")" = ea564dbd ] || stop "unit not ea564dbd"
[ "$(m8 "$BTREE/src/direct.cpp")" = 9956715f ] && [ "$(m8 "$BTREE/src/policy.cpp")" = 99303017 ] || stop "backend not 9956715f / 99303017"
mkdir -p "$K" || stop mkdir
for f in mkb2439.py mkb2439_add.py mkfp439.py fp0439.hpp dc0439.hpp cw0439.hpp mkvl439.py mkvlon439.py mkdm439b.py dm0439.hpp \
         b2-ib-be.diff b2be439.py mkcs439be.py mkpcc439be.py cs0439.hpp ds0439.hpp build0438.py; do
    [ -f "$K/$f" ] || cp -p "$L/$f" "$K/$f" || stop "copy $f"
done
for f in select-fakelib.diff host-fakelib.diff; do [ -f "$K/$f" ] || stop "$f missing (copied from the repo's exp 0439 bake2-fakelib)"; done
rm -rf "$D/tmp" "$D/new" "$D/be"; mkdir -p "$D/tmp/orig" "$D/new" "$D/be/src/reimpl" "$D/be/include/bc5/reimpl" "$D/tmp/bt/backend" "$D/tmp/b1/src" "$D/tmp/dm" "$D/tmp/hf" || stop mkdir
# unit
cp "$TREE/src/libs/bc5LleAgc.cpp" "$TREE/src/graphics/presentation/videoOut.cpp" "$D/tmp/orig/" || stop "copy units"
MKB2439_UNIT=ea564dbd MKB2439_HDR=$(m8 "$TREE/src/bc5/switch_defaults.hpp") python3 -I "$K/mkb2439.py" "$D/tmp/orig" "$TREE/src/bc5/switch_defaults.hpp" "$D/tmp/out" || stop mkb2439
n=$(grep -c '{"BC5_DIRECT_EAGER_GPU_WRITE", "1"}' "$D/tmp/out/switch_defaults.hpp"); [ "$n" = 1 ] || stop "EAGER row count $n"
grep -v '{"BC5_DIRECT_EAGER_GPU_WRITE", "1"}' "$D/tmp/out/switch_defaults.hpp" > "$D/new/switch_defaults.hpp" || stop "drop EAGER"
grep -c 'BC5_T2, "BC5_DIRECT_\(DMA_SYNC\|FLAT_APERTURE\)"' "$D/new/switch_defaults.hpp" | grep -qx 0 || stop "a T2 DMA_SYNC/FLAT_APERTURE row is left"
python3 -I "$K/mkvl439.py" "$D/tmp/out/bc5LleAgc.cpp" "$D/new/bc5LleAgc.cpp" || stop mkvl439
cp "$D/tmp/out/videoOut.cpp" "$D/tmp/out/dc0439.hpp" "$D/tmp/out/cw0439.hpp" "$D/new/" && cp "$K/fp0439.hpp" "$D/new/fp0439.hpp" || stop "kit headers"
python3 -I "$K/mkvlon439.py" "$D/new" || stop mkvlon439
# S1_TRIM=1 (the top session, 11-26 12:30): the flip-label arm a (BC5_0439_FLIP_LABEL_GPU), not adopted, is not compiled
if [ "${S1_TRIM:-0}" = 1 ]; then python3 -I "$K/mkvlg446.py" "$D/new/bc5LleAgc.cpp" || stop mkvlg446; fi
cp "$TREE/src/libs/ajm/atrac9_decoder.h" "$TREE/src/libs/ajm.cpp" "$D/tmp/dm/" && python3 -I "$K/mkdm439b.py" "$D/tmp/dm" "$D/new" || stop mkdm439b
cp "$TREE/src/main.cpp" "$TREE/src/kernel/pthread.cpp" "$TREE/src/libs/libAmpr.cpp" "$D/new/" || stop "units that include switch_defaults.hpp"
mkdir -p "$D/tmp/hf/src/libs" "$D/tmp/hf/src/loader" && cp "$TREE/src/libs/bc5Reimpl.cpp" "$D/tmp/hf/src/libs/" && cp "$TREE/src/loader/runtimeLinker.cpp" "$D/tmp/hf/src/loader/" \
    && (cd "$D/tmp/hf" && git apply -p1 "$K/host-fakelib.diff") && cp "$D/tmp/hf/src/libs/bc5Reimpl.cpp" "$D/tmp/hf/src/loader/runtimeLinker.cpp" "$D/new/" || stop host-fakelib
# backend
cp -r "$BTREE/src" "$BTREE/include" "$D/tmp/bt/backend/" && cp "$BTREE/src/direct.cpp" "$BTREE/src/policy.cpp" "$BTREE/src/full_state.cpp" "$D/tmp/b1/src/" || stop "copy backend"
(cd "$D/tmp/bt" && git apply --reject -p1 "$K/b2-ib-be.diff" > "$D/tmp/patch.out" 2>&1); echo "b2-ib-be hunks rejected (3 expected): $(grep -c 'Rejected hunk' "$D/tmp/patch.out")"
B2BE_DIRECT=9956715f B2BE_POLICY=99303017 python3 -I "$K/b2be439.py" "$D/tmp/b1" "$D/tmp/bt/backend" || stop b2be439
(cd "$D/tmp/bt" && git apply -p1 --include=backend/src/reimpl/select.cpp --include=backend/include/bc5/reimpl/select.hpp "$K/select-fakelib.diff") || stop select-fakelib
cp "$D/tmp/bt/backend/src/direct.cpp" "$D/tmp/bt/backend/src/policy.cpp" "$D/tmp/bt/backend/src/full_state.cpp" "$D/tmp/bt/backend/src/state_stack.cpp" "$D/be/src/" \
    && cp "$D/tmp/bt/backend/src/reimpl/select.cpp" "$D/be/src/reimpl/" && cp "$D/tmp/bt/backend/include/bc5/reimpl/select.hpp" "$D/be/include/bc5/reimpl/" \
    && cp "$D/tmp/bt/backend/include/bc5/ib_chain.hpp" "$K/ds0439.hpp" "$D/be/include/bc5/" || stop "backend kit"
# S1_PCC=1 (the cleaned stage-1 kit, S1_DIR=s2): exp 0439's PASS_CONTEXT_CONTROL-only step instead of the cs439 bundle,
# so no diagnostic word or code (CS_COUNT, REGTAB_*, CC_CENSUS ...); the word unset or "0" leaves the backend as shared
if [ "${S1_PCC:-0}" = 1 ]; then
    python3 -I "$K/mkpcc439be.py" "$D/be" || stop mkpcc439be
else
    cp "$K/cs0439.hpp" "$D/be/include/bc5/" && python3 -I "$K/mkcs439be.py" "$D/be" || stop mkcs439be
fi
# S1_G442=1 (stage 2): exp 0442's job-slot fix (63ee9b53, BC5_DIRECT_0442_SLOT_KEEP, on unless "0") ported to this kit:
# g442-s2.diff is 63ee9b53's direct.cpp change regenerated against the cleaned kit's direct.cpp (its one rejected hunk,
# the switch's read at Device::open, placed after SNAP_GROW's: its context named a GC_FAST block the shared backend lacks)
if [ "${S1_G442:-0}" = 1 ]; then [ "${S1_PCC:-0}" = 1 ] || stop "S1_G442 needs S1_PCC=1 (its diff is against the cleaned kit)"
    mkdir -p "$D/tmp/g4/backend/src" && cp "$D/be/src/direct.cpp" "$D/tmp/g4/backend/src/" && (cd "$D/tmp/g4" && git apply -p1 "$K/g442-s2.diff") \
        && cp "$D/tmp/g4/backend/src/direct.cpp" "$D/be/src/direct.cpp" && cp "$K/slot_grow.hpp" "$D/be/include/bc5/slot_grow.hpp" || stop g442
fi
echo "new:"; (cd "$D/new" && for f in *; do echo "$f=$(m8 "$f")"; done) | tr '\n' ' '; echo
echo "be:"; (cd "$D/be" && find . -type f | sort | while read -r f; do echo "${f#./}=$(m8 "$f")"; done) | tr '\n' ' '; echo
echo "rows:"; grep -n -E '"(BC5_DIRECT_(IB_CHAIN|IB_CHAIN_FLAT|AGC_EOP_IDENT|FLAT_APERTURE|DMA_SYNC|DMA_SYNC_MEC|DMA_SYNC_LABEL|PREFIX_CHAINS|CHAIN_WRITERS|DCC_PRESENT|EAGER_GPU_WRITE)|KYTY_BC5_AT9_DMC|BC5_0439_FLIP_LABEL_PIECES)"' "$D/new/switch_defaults.hpp" "$D/new/bc5LleAgc.cpp" | cut -c1-160
