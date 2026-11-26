#!/usr/bin/env bash
# BC5 exp 0446 stage-1 bake (DRAFT, 2026-11-26; deployment only on the top session's and the maintainer's word).
# Puts the cleaned stage-1 candidate's sources (exp0446/s2/{new,be}, made by prep446s1.sh with S1_DIR=s2 S1_PCC=1) into
# the shared KytyPlus tree and the shared backend export, and rebuilds the three shared build directories in place with
# their own ninja (host toolchain). The current shared set stays beside it for the undo:
#   ~/bc5-work/bake446/orig/   the tree's and the export's files as they were (their md5s in orig.md5)
#   <build dir>/...bakeH       kyty_emulator (normal, lean) and libbc5_backend.a as they were (5727b07f / 94a6513c / 09567e4a)
#   bake446.sh check   pins (shared set, tree diff, export files, the kit's files against s2.md5), no emulator, no lock; writes nothing
#   bake446.sh swap    check, lock, keep the originals, copy the kit in, ninja the archive, normal and lean, md5s and word lists
#   bake446.sh undo    the original sources back, the kept binaries and archive back, md5s checked
# After a swap the repository needs patch 0001/0002 and TREE-DIFF regenerated from the tree (the bake's commit, not here).
set -uo pipefail
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0446; S=$X/${BAKE_KIT:-s3}; B=$W/bake446; T=$HOME/bc5-toolchain
K=$HOME/src/KytyPlus; E=$W/d19/export/backend; LOCK=$W/BOX-LOCK
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; SA=$W/backend-ubuntu/libbc5_backend.a
OLD_N=5727b07f OLD_L=94a6513c OLD_A=09567e4a
# bc5-mount: exp 0447's candidate (the package cache limit, 32 GiB floor; branch exp/0447-bake-candidate 6b1fd7cd),
# copied to <kit>/bin/bc5-mount from ~/bc5-work/exp0447/bin/bc5-mount.bake4; a binary swap (its source lands on main with exp 0447)
SM=$W/bc5-tools-ubuntu/release/bc5-mount; OLD_M=3ef38b1d NEW_M=31d9bbfa
# kit file -> shared path
TREE_FILES="bc5LleAgc.cpp:src/libs/bc5LleAgc.cpp videoOut.cpp:src/graphics/presentation/videoOut.cpp ajm.cpp:src/libs/ajm.cpp
atrac9_decoder.h:src/libs/ajm/atrac9_decoder.h switch_defaults.hpp:src/bc5/switch_defaults.hpp dc0439.hpp:src/bc5/dc0439.hpp
cw0439.hpp:src/bc5/cw0439.hpp fp0439.hpp:src/bc5/fp0439.hpp dm0439.hpp:src/bc5/dm0439.hpp bc5Reimpl.cpp:src/libs/bc5Reimpl.cpp
runtimeLinker.cpp:src/loader/runtimeLinker.cpp"
BE_FILES="src/direct.cpp src/full_state.cpp src/policy.cpp src/reimpl/select.cpp include/bc5/ib_chain.hpp include/bc5/ds0439.hpp include/bc5/reimpl/select.hpp"
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
say() { mkdir -p "$B"; echo "$(date +%T) bake446: $*" | tee -a "$B/bake446.log"; }
die() { say "STOP: $*"; exit 1; }
pins_old() { [ "$(m8 "$NB")" = $OLD_N ] && [ "$(m8 "$LB")" = $OLD_L ] && [ "$(m8 "$SA")" = $OLD_A ] && [ "$(m8 "$SM")" = $OLD_M ]; }
check() {
    pgrep -x kyty_emulator > /dev/null && die "an emulator runs"
    [ -s "$LOCK" ] && die "BOX-LOCK holds a line: $(cat "$LOCK")"
    [ -r "$T/env.sh" ] || die "no toolchain"
    [ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 8a9ed0cf ] || die "the tree is not 8a9ed0cf"
    [ "$(m8 "$E/src/direct.cpp")" = 9956715f ] && [ "$(m8 "$E/src/policy.cpp")" = 99303017 ] || die "the export is not 9956715f / 99303017"
    [ -s "$S/$(basename "$S").md5" ] && (cd "$S" && md5sum -c --quiet "$(basename "$S").md5") || die "the kit $S does not match its md5 list"
    [ "$(m8 "$S/bin/bc5-mount")" = $NEW_M ] || die "the kit's bc5-mount is not $NEW_M"
    pgrep -x bc5-mount > /dev/null && die "a bc5-mount runs"
    pins_old || die "the shared set is not $OLD_N / $OLD_L / $OLD_A / bc5-mount $OLD_M"
}
lock() {
    LINE="exp 0446 | stage-1 bake swap, token $(date +%s)$$ | $(date '+%F %T')"
    [ -e "$LOCK" ] || touch "$LOCK"
    local tl=$LOCK.b446-$$.new al=$LOCK.b446-$$.aside
    printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the lock claim failed"; }
    if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign lock line arrived"; fi
    rm -f "$al" "$tl"; trap unlock EXIT
}
unlock() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.b446-$$.rel"; mv -fT "$LOCK.b446-$$.rel" "$LOCK"; fi; }
keep() {
    mkdir -p "$B/orig/tree" "$B/orig/export" || die mkdir
    for p in $TREE_FILES; do d=${p#*:}; [ -f "$K/$d" ] && { mkdir -p "$B/orig/tree/$(dirname "$d")"; cp -p "$K/$d" "$B/orig/tree/$d"; } || echo "new $d" >> "$B/orig/new-files.txt"; done
    for d in $BE_FILES; do [ -f "$E/$d" ] && { mkdir -p "$B/orig/export/$(dirname "$d")"; cp -p "$E/$d" "$B/orig/export/$d"; } || echo "new export/$d" >> "$B/orig/new-files.txt"; done
    (cd "$B/orig" && find . -type f | sort | xargs md5sum) > "$B/orig.md5"
    cp -p "$NB" "$NB.bakeH" && cp -p "$LB" "$LB.bakeH" && cp -p "$SA" "$SA.bakeH" && cp -p "$SM" "$SM.bakeH" || die "keep the binaries"
}
undo() { # sources copied back with a fresh mtime, so a later ninja rebuilds their objects from them
    pgrep -x kyty_emulator > /dev/null && die "an emulator runs"
    [ -s "$B/orig.md5" ] && (cd "$B/orig" && md5sum -c --quiet ../orig.md5) || die "the kept originals do not match orig.md5"
    for p in $TREE_FILES; do d=${p#*:}; if [ -f "$B/orig/tree/$d" ]; then cp "$B/orig/tree/$d" "$K/$d"; else rm -f "$K/$d"; fi; done
    for d in $BE_FILES; do if [ -f "$B/orig/export/$d" ]; then cp "$B/orig/export/$d" "$E/$d"; else rm -f "$E/$d"; fi; done
    cp -p "$NB.bakeH" "$NB" && cp -p "$LB.bakeH" "$LB" && cp -p "$SA.bakeH" "$SA" && cp -p "$SM.bakeH" "$SM" || die "put the binaries back"
    [ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 8a9ed0cf ] && pins_old && say "undo: tree 8a9ed0cf, normal $OLD_N, lean $OLD_L, archive $OLD_A, bc5-mount $OLD_M" || die "undo did not read back as the pins"
}
swap() {
    check; lock; keep
    for p in $TREE_FILES; do cp -p "$S/new/${p%%:*}" "$K/${p#*:}" || { undo; die "copy ${p%%:*}"; }; done
    for d in $BE_FILES; do mkdir -p "$(dirname "$E/$d")"; cp -p "$S/be/$d" "$E/$d" || { undo; die "copy $d"; }; done
    . "$T/env.sh"
    for d in backend-ubuntu kytyplus-build kytyplus-build-lean; do
        (cd "$W/$d" && nice -n 10 ninja > "$B/ninja-$d.out" 2>&1) || { tail -20 "$B/ninja-$d.out"; undo; die "ninja $d"; }
    done
    cp -p "$S/bin/bc5-mount" "$SM" && [ "$(m8 "$SM")" = $NEW_M ] || { undo; die "bc5-mount"; }
    say "swap: bc5-mount $(m8 "$SM"),  normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$SA"), tree diff $(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)"
}
case "${1:-}" in check) check && say "check: ok" ;; swap) swap ;; undo) undo ;; *) echo "usage: bake446.sh check|swap|undo"; exit 2 ;; esac
