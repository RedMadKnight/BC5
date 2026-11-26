#!/usr/bin/env bash
# BC5 exp 0417: a dry run of int0417b.sh on the laptop with stand-ins (no box, no real build).
#   stand-in HOME: ~/src/KytyPlus = a clone of the scratch tree at f266548 with 0001-new9 applied; the shared and
#   private "binaries" are small files; `pgrep` finds nothing; `distrobox` is a stand-in whose "build" writes a file
#   made of the tree's sources (so the words a real binary would hold are the tree's own), in one of three modes:
#     ok      as above, without the two words that a real build compiles out (the hook's word; K1R is not in the tree)
#     fail    the build fails                     -> the script must restore and read the restore back
#     k1r     the "binary" holds BC5_GUARD_K1R    -> the script must refuse it and restore
# The pins of the stand-in binaries are patched into a COPY of the script (the real pins are the box's binaries).
# The scratch tree's tag `base` is KytyPlus f266548's content; the stand-in tree gets a tag of that name for the script's diff.
# usage: dryswap0417b.sh <scratch tree (git, tag base)> <kit dir with 0001-new9/new14.patch, tree14.md5> <work dir>
set -u
SRC=$1; KIT=$2; D=$3; HERE=$(cd "$(dirname "$0")" && pwd)
pass=0; failn=0
t() { if [ "$2" = "$3" ]; then pass=$((pass + 1)); else failn=$((failn + 1)); echo "FAIL $1: got [$2] want [$3]"; fi; }
for mode in ok fail k1r; do
    H=$D/$mode; rm -rf "$H"; mkdir -p "$H/bin" "$H/src" "$H/kit" "$H/bc5-work/kytyplus-build/src" "$H/bc5-work/kytyplus-build-lean/src" "$H/bc5-work/backend-ubuntu" "$H/bc5-work/exp0413/p/build-normal/src" "$H/bc5-work/exp0413/p/build-lean/src"
    git clone -q -c core.autocrlf=false -c core.filemode=false "$SRC" "$H/src/KytyPlus" 2> /dev/null && (cd "$H/src/KytyPlus" && git checkout -q base 2> /dev/null && git tag f266548 base && git apply --whitespace=nowarn "$KIT/0001-new9.patch" && git add -N .) || { echo "cannot make the stand-in tree"; exit 1; }
    cp "$KIT/0001-new9.patch" "$KIT/0001-new14.patch" "$KIT/tree14.md5" "$H/kit/"
    echo old-normal > "$H/bc5-work/kytyplus-build/src/kyty_emulator"; echo old-lean > "$H/bc5-work/kytyplus-build-lean/src/kyty_emulator"
    echo archive > "$H/bc5-work/backend-ubuntu/libbc5_backend.a"
    printf '#!/bin/sh\nexit 1\n' > "$H/bin/pgrep"
    cat > "$H/bin/distrobox" <<STUB
#!/bin/sh
# stand-in: distrobox enter ubuntu -- sh -c "cd '<dir>' && nice -n 19 ninja kyty_emulator"
dir=\$(echo "\$6" | sed "s/^cd '\(.*\)' && .*/\1/")
[ "$mode" = fail ] && { echo "error: stand-in build failure"; exit 1; }
{ echo "\$dir"; echo "NpCppWebApi SessionManager V2 on (10 exports registered)"; cd "$H/src/KytyPlus" && git ls-files -z src | xargs -0 cat | grep -av KYTY_BC5_AMM_SETBUFFER_TEST; [ "$mode" = k1r ] && echo BC5_GUARD_K1R; true; } > "\$dir/src/kyty_emulator"
STUB
    chmod +x "$H/bin/pgrep" "$H/bin/distrobox"
    # the private builds: what the stand-in build will give (ok mode), so the result line can say "byte-identical"
    for v in normal lean; do
        d=$H/bc5-work/kytyplus-build; [ $v = lean ] && d=$d-lean
        { echo "$d"; echo "NpCppWebApi SessionManager V2 on (10 exports registered)"; (cd "$H/src/KytyPlus" && git apply -R --whitespace=nowarn "$KIT/0001-new9.patch" && git apply --whitespace=nowarn "$KIT/0001-new14.patch" && git add -N . && git ls-files -z src | xargs -0 cat | grep -av KYTY_BC5_AMM_SETBUFFER_TEST; git apply -R --whitespace=nowarn "$KIT/0001-new14.patch" && git apply --whitespace=nowarn "$KIT/0001-new9.patch" && git add -N .) ; } > "$H/bc5-work/exp0413/p/build-$v/src/kyty_emulator"
    done
    m() { md5sum < "$1" | cut -d' ' -f1; }
    pn=$(m "$H/bc5-work/kytyplus-build/src/kyty_emulator"); pl=$(m "$H/bc5-work/kytyplus-build-lean/src/kyty_emulator"); pa=$(m "$H/bc5-work/backend-ubuntu/libbc5_backend.a" | cut -c1-8)
    sed -e "s/^PIN_NORMAL=[0-9a-f]*; PIN_LEAN=[0-9a-f]*; PIN_ARCHIVE=[0-9a-f]*;/PIN_NORMAL=$pn; PIN_LEAN=$pl; PIN_ARCHIVE=$pa;/" "$HERE/int0417b.sh" > "$H/kit/int0417b.sh"
    t "$mode: only the pins line differs" "$(diff "$HERE/int0417b.sh" "$H/kit/int0417b.sh" | grep -c '^[<>]')" 2
    sn=$(md5sum < "$KIT/0001-new14.patch" | cut -c1-8)
    out=$(HOME=$H PATH=$H/bin:$PATH S_NEW=$sn S_PRIV_N=$(m "$H/bc5-work/exp0413/p/build-normal/src/kyty_emulator") S_PRIV_L=$(m "$H/bc5-work/exp0413/p/build-lean/src/kyty_emulator") bash "$H/kit/int0417b.sh" 2>&1); rc=$?
    echo "--- $mode (exit $rc)"; echo "$out" | cut -c1-200
    td=$(git -C "$H/src/KytyPlus" diff --no-color f266548 | md5sum | cut -c1-8)
    lock=$(cat "$H/bc5-work/BOX-LOCK" 2> /dev/null)
    case $mode in
        ok)   t "ok exit" "$rc" 0; t "ok tree" "$td" "$sn"; t "ok identical" "$(echo "$out" | grep -c 'byte-identical to the private builds')" 1
              t "ok kept copy" "$(m "$H/bc5-work/exp0413/swap/kyty_emulator.before-0417b")" "$pn" ;;
        fail) t "fail exit" "$rc" 1; t "fail tree back" "$td" 4651d1d3; t "fail normal back" "$(m "$H/bc5-work/kytyplus-build/src/kyty_emulator")" "$pn"; t "fail restored line" "$(echo "$out" | grep -c '^restored and read back')" 1 ;;
        k1r)  t "k1r exit" "$rc" 1; t "k1r tree back" "$td" 4651d1d3; t "k1r lean back" "$(m "$H/bc5-work/kytyplus-build-lean/src/kyty_emulator")" "$pl"; t "k1r named" "$(echo "$out" | grep -c 'holds \[BC5_GUARD_K1R\]')" 1 ;;
    esac
    t "$mode lock empty" "$lock" ""
    t "$mode lock released line" "$(echo "$out" | grep -c '^lock released')" 1
done
echo "dryswap0417b: $pass passed, $failn failed"
[ "$failn" = 0 ]
