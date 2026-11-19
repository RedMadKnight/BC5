#!/usr/bin/env bash
# BC5 experiment 0435: an md5 fingerprint of everything the private build must leave byte-identical (top's condition,
# 2026-11-19): the shared tree, both shared build directories (binaries, and a listing of every file with size and
# mtime), the patch in ~/src/bc5, the launchers, bc5-run.env, input.cfg and the desktop shortcuts. Read only.
#   snap0435.sh > before.txt ... snap0435.sh > after.txt; diff before.txt after.txt
set -u
export LC_ALL=C
cd "$HOME" || exit 1
echo "tree-head $(git -C src/KytyPlus rev-parse HEAD)"
echo "tree-status $(git -C src/KytyPlus status --porcelain=v1 | md5sum | cut -c1-32)"
echo "tree-files $(cd src/KytyPlus && find src -type f -print0 | sort -z | xargs -0 md5sum | md5sum | cut -c1-32)"
for b in bc5-work/kytyplus-build bc5-work/kytyplus-build-lean; do
    echo "$b/src/kyty_emulator $(md5sum < "$b/src/kyty_emulator" | cut -c1-32)"
    echo "$b listing $(find "$b" -printf '%P %s %T@\n' | sort | md5sum | cut -c1-32)"
done
for f in src/bc5/backend/kytyplus-patches/0001-bc5-lle-agc.patch bc5-work/play-any.sh bc5-work/play-pkg.sh \
    bc5-work/play-astro.sh bc5-work/lean-session.sh bc5-work/bc5-run.env bc5-work/input.cfg Pulpit/*.desktop; do
    echo "$f $(md5sum < "$f" | cut -c1-32)"
done
