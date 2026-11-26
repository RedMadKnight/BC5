#!/usr/bin/env bash
# BC5 exp 0419: a dry run of int0419f.sh (candidate F's swap, which also changes the shared backend archive) on the
# laptop with stand-ins; no box, no real build. After exp 0417's dryswap0417b.sh.
#   stand-in HOME: ~/src/KytyPlus = a clone of the scratch tree at its tag `base` (KytyPlus f266548's content) with
#   0001-new14 applied; the shared backend source = the repository's backend/ (direct.hpp a9fcb26b, direct.cpp 51279eae);
#   the shared and private "binaries" and the archive are small files; `pgrep` finds nothing; `distrobox` is a stand-in:
#   its backend "build" writes a new archive, its emulator "build" writes a file made of the tree's own sources.
#   cases:  ok         everything as expected
#           backend    the backend build fails          -> source files, archive, binaries and tree restored
#           badarch    the rebuilt archive is not the expected one -> the same restore
#           emu        the lean emulator build fails AFTER the archive and the normal binary changed -> the same restore
# The pins of the stand-in files are patched into a COPY of the script (two lines: the binaries' and the archive's).
# usage: dryswap0419f.sh <scratch tree (git, tag base)> <kit dir: 0001-new14/new17.patch, tree18.md5, backend-direct.hpp/.cpp> <repo root> <work dir>
set -u
SRC=$1; KIT=$2; REPO=$3; D=$4; HERE=$(cd "$(dirname "$0")" && pwd)
pass=0; failn=0
t() { if [ "$2" = "$3" ]; then pass=$((pass + 1)); else failn=$((failn + 1)); echo "FAIL $1: got [$2] want [$3]"; fi; }
m() { md5sum < "$1" | cut -d' ' -f1; }
for mode in ok backend badarch emu; do
    H=$D/$mode; W=$H/bc5-work; rm -rf "$H"
    mkdir -p "$H/bin" "$H/src" "$H/kit" "$W/kytyplus-build/src" "$W/kytyplus-build-lean/src" "$W/backend-ubuntu" "$W/exp0413/p/build-normal/src" "$W/exp0413/p/build-lean/src" "$W/d19/export/backend/include/bc5" "$W/d19/export/backend/src"
    git clone -q -c core.autocrlf=false -c core.filemode=false "$SRC" "$H/src/KytyPlus" 2> /dev/null && (cd "$H/src/KytyPlus" && git checkout -q base 2> /dev/null && git tag f266548 base && git apply --whitespace=nowarn "$KIT/0001-new14.patch" && git add -N .) || { echo "cannot make the stand-in tree"; exit 1; }
    cp "$KIT/0001-new14.patch" "$KIT/0001-new18.patch" "$KIT/tree18.md5" "$KIT/backend-direct.hpp" "$KIT/backend-direct.cpp" "$H/kit/"
    cp "$REPO/backend/include/bc5/direct.hpp" "$W/d19/export/backend/include/bc5/direct.hpp"; cp "$REPO/backend/src/direct.cpp" "$W/d19/export/backend/src/direct.cpp"
    echo old-normal > "$W/kytyplus-build/src/kyty_emulator"; echo old-lean > "$W/kytyplus-build-lean/src/kyty_emulator"
    echo archive-old > "$W/backend-ubuntu/libbc5_backend.a"; : > "$W/backend-ubuntu/build.ninja"
    printf '#!/bin/sh\nexit 1\n' > "$H/bin/pgrep"
    cat > "$H/bin/distrobox" <<STUB
#!/bin/sh
# stand-in: distrobox enter ubuntu -- sh -c "cd '<dir>' && nice -n 19 ninja [kyty_emulator]"
dir=\$(echo "\$6" | sed "s/^cd '\\(.*\\)' && .*/\\1/")
case "\$6" in
  *"ninja kyty_emulator")
    case "$mode:\$dir" in emu:*-lean) echo "error: stand-in emulator build failure"; exit 1 ;; esac
    { echo "\$dir"; echo "NpCppWebApi SessionManager V2 on (10 exports registered)"; cd "$H/src/KytyPlus" && git ls-files -z src | xargs -0 cat | grep -av KYTY_BC5_AMM_SETBUFFER_TEST; true; } > "\$dir/src/kyty_emulator" ;;
  *)
    [ "$mode" = backend ] && { echo "error: stand-in backend build failure"; exit 1; }
    if [ "$mode" = badarch ]; then echo archive-other > "\$dir/libbc5_backend.a"; else echo archive-new > "\$dir/libbc5_backend.a"; fi ;;
esac
STUB
    chmod +x "$H/bin/pgrep" "$H/bin/distrobox"
    for v in normal lean; do   # the private builds: what the stand-in emulator build gives
        d=$W/kytyplus-build; [ $v = lean ] && d=$d-lean
        { echo "$d"; echo "NpCppWebApi SessionManager V2 on (10 exports registered)"; (cd "$H/src/KytyPlus" && git apply -R --whitespace=nowarn "$KIT/0001-new14.patch" && git apply --whitespace=nowarn "$KIT/0001-new18.patch" && git add -N . && git ls-files -z src | xargs -0 cat | grep -av KYTY_BC5_AMM_SETBUFFER_TEST; git reset -q; git apply -R --whitespace=nowarn "$KIT/0001-new18.patch" && git apply --whitespace=nowarn "$KIT/0001-new14.patch" && git add -N .); } > "$W/exp0413/p/build-$v/src/kyty_emulator"
    done
    pn=$(m "$W/kytyplus-build/src/kyty_emulator"); pl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); pa=$(m "$W/backend-ubuntu/libbc5_backend.a"); na=$(echo archive-new | md5sum | cut -c1-8)
    sed -e "s/^PIN_NORMAL=[0-9a-f]*; PIN_LEAN=[0-9a-f]*; PIN_ARCHIVE=[0-9a-f]*;/PIN_NORMAL=$pn; PIN_LEAN=$pl; PIN_ARCHIVE=${pa:0:8};/" \
        -e "s/^PIN_ARCH_FULL=[0-9a-f]*; NEW_ARCHIVE=[0-9a-f]*/PIN_ARCH_FULL=$pa; NEW_ARCHIVE=$na/" "$HERE/int0419f.sh" > "$H/kit/int0419f.sh"
    t "$mode: only the two pin lines differ" "$(diff "$HERE/int0419f.sh" "$H/kit/int0419f.sh" | grep -c '^[<>]')" 4
    sn=$(md5sum < "$KIT/0001-new18.patch" | cut -c1-8)
    out=$(HOME=$H PATH=$H/bin:$PATH S_NEW=$sn S_PRIV_N=$(m "$W/exp0413/p/build-normal/src/kyty_emulator") S_PRIV_L=$(m "$W/exp0413/p/build-lean/src/kyty_emulator") bash "$H/kit/int0419f.sh" 2>&1); rc=$?
    echo "--- $mode (exit $rc)"; echo "$out" | grep -v "^claimed\|^20\|^==" | cut -c1-170
    td=$(git -C "$H/src/KytyPlus" diff --no-color f266548 | md5sum | cut -c1-8)
    hs=$(m "$W/d19/export/backend/include/bc5/direct.hpp" | cut -c1-8); cs=$(m "$W/d19/export/backend/src/direct.cpp" | cut -c1-8)
    case $mode in
        ok) t "ok exit" "$rc" 0; t "ok tree" "$td" "$sn"; t "ok identical" "$(echo "$out" | grep -c 'byte-identical to the private builds')" 1
            t "ok archive new" "$(m "$W/backend-ubuntu/libbc5_backend.a" | cut -c1-8)" "$na"; t "ok archive kept beside" "$(m "$W/backend-ubuntu/libbc5_backend.a.before-0419")" "$pa"
            t "ok backend files" "$hs $cs" "e96e5c73 28100ce5"; t "ok kept normal" "$(m "$W/exp0413/swap/kyty_emulator.before-0419")" "$pn" ;;
        *)  t "$mode exit" "$rc" 1; t "$mode tree back" "$td" 27b6416f; t "$mode archive back" "$(m "$W/backend-ubuntu/libbc5_backend.a")" "$pa"
            t "$mode backend files back" "$hs $cs" "a9fcb26b 51279eae"; t "$mode normal back" "$(m "$W/kytyplus-build/src/kyty_emulator")" "$pn"
            t "$mode lean back" "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" "$pl"; t "$mode restored line" "$(echo "$out" | grep -c '^restored and read back')" 1 ;;
    esac
    t "$mode lock empty" "$(cat "$W/BOX-LOCK" 2> /dev/null)" ""
    t "$mode lock released line" "$(echo "$out" | grep -c '^lock released')" 1
done
echo "dryswap0419f: $pass passed, $failn failed"
[ "$failn" = 0 ]
