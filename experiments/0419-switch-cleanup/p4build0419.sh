#!/usr/bin/env bash
# BC5 exp 0419, build W = V + the lean build without its diagnostic switches (mklean0419.py): ONE build round on the
# private tree (exp0413/p, at build V). CPU only, no emulator, one lock line.
#   1. the private tree must be V's (treeV.md5); the whole src/ is saved to $P/p4-before-src with V's two binaries
#   2. mklean0419.py rewrites the reads (the normal build's code is unchanged: the macros expand to what stood there)
#   3. normal and lean are rebuilt, nice 19
#   4. the lean binary's words (strings) are listed against the words lean is meant to read (lean-keep.txt)
# A build error stops it with the error lines; `p4build0419.sh back` puts V's src/ and binaries' sources back.
# usage (on the box): p4build0419.sh [back]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; HERE=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "p4build0419: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 build W: the lean build without diagnostic switches; the private tree rewritten, one rebuild of normal and lean (CPU only, no emulator)" 30 || { echo "p4build0419: NOT STARTED"; exit 1; }
trap chain_release EXIT
if [ -d "$P/p4-before-src" ]; then
    echo "putting V's src back first"
    rm -rf "${P:?}/tree/src" && cp -a "$P/p4-before-src" "$P/tree/src" || { echo "p4build0419 STOP: cannot restore src"; exit 1; }
fi
[ "${1:-}" = back ] && { echo "p4build0419: V's src is back; rebuild with p3build0419.sh's last step or ninja"; exit 0; }
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/treeV.md5"
[ "$bad" = 0 ] || { echo "p4build0419 STOP: $bad files of the private tree are not V's"; exit 1; }
if [ ! -d "$P/p4-before-src" ]; then
    cp -a "$P/tree/src" "$P/p4-before-src" || { echo "p4build0419 STOP: cannot save src"; exit 1; }
    mkdir -p "$P/p4-before-bin" && cp -p "$P/build-normal/src/kyty_emulator" "$P/p4-before-bin/kyty_emulator.normal" && cp -p "$P/build-lean/src/kyty_emulator" "$P/p4-before-bin/kyty_emulator.lean"
fi
python3 "$HERE/mklean0419.py" "$P/tree" "$HERE/lean-classes.tsv" "$P/backend-src/src/direct.cpp" || { echo "p4build0419 STOP: mklean0419.py refused"; exit 1; }
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || bad=$((bad + 1)); done < "$HERE/treeW.md5"
echo "against the laptop's W: $bad of $(wc -l < "$HERE/treeW.md5") files differ"
for v in normal lean; do
    d=$P/build-$v
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1; then
        grep -m12 -E "error:" "$d.build.log" | cut -c1-260
        echo "p4build0419 STOP: build $v failed"
        exit 1
    fi
    echo "$v: $(md5sum < "$d/src/kyty_emulator" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log")"
done
for v in normal lean; do
    nice -n 19 strings "$P/build-$v/src/kyty_emulator" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | LC_ALL=C sort -u > "$HERE/words-bin-$v.txt"
done
echo "lean binary: of the words V's source reads ($(wc -l < "$HERE/words-build-V.txt")), still in it: $(LC_ALL=C comm -12 "$HERE/words-build-V.txt" "$HERE/words-bin-lean.txt" | wc -l); normal: $(LC_ALL=C comm -12 "$HERE/words-build-V.txt" "$HERE/words-bin-normal.txt" | wc -l)"
echo "lean binary, in it and NOT meant to be read by lean: $(LC_ALL=C comm -12 "$HERE/words-build-V.txt" "$HERE/words-bin-lean.txt" | LC_ALL=C comm -23 - "$HERE/lean-keep.txt" | tr '\n' ' ')"
echo "lean binary, meant to be read and NOT in it: $(LC_ALL=C comm -13 "$HERE/words-bin-lean.txt" "$HERE/lean-keep.txt" | tr '\n' ' ')"
echo "p4build0419 done $(date +%T): normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
