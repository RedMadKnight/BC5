#!/usr/bin/env bash
# test-kytyplus-tree.sh: kytyplus-tree.sh against a real KytyPlus history, in a throw-away clone (the source repository
# is only read). Passes when: the series applies to the base and gives the recorded tree diff; check then passes; a
# one-line change in a patched file, and one in a file the series creates, each make check fail; and a tree with
# only the first patch fails too (the defect of 2026-11-24: bc5-build.sh applied 0001 alone).
#   test-kytyplus-tree.sh <a KytyPlus repository holding the base commit>
set -euo pipefail
export LC_ALL=C
SRC=${1:?a KytyPlus repository}
HERE=$(cd "$(dirname "$0")" && pwd); KT=$HERE/kytyplus-tree.sh
P=$(cd "$HERE/../.." && pwd)/backend/kytyplus-patches
BASE=$(grep -v '^#' "$P/TREE-DIFF" | grep . | head -1 | awk '{print $1}')
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# the base commit alone, by its full id (a shallow source cannot be cloned --shared)
FULL=$(git -C "$SRC" rev-parse "$BASE^{commit}")
git init -q "$W/k" && git -C "$W/k" config core.autocrlf false
git -C "$W/k" fetch -q --depth 1 "file://$(cd "$SRC" && pwd)" "$FULL"
git -c core.autocrlf=false -C "$W/k" checkout -q FETCH_HEAD
fails=0
ok() { echo "PASS: $1"; }
no() { echo "FAIL: $1"; fails=$((fails + 1)); }
bash "$KT" apply "$W/k" > /dev/null 2>&1 && ok "the series applies and gives the recorded tree diff ($(bash "$KT" hash "$W/k"))" || no "apply + check ($(bash "$KT" hash "$W/k"))"
bash "$KT" check "$W/k" > /dev/null 2>&1 && ok "check passes on that tree" || no "check on the applied tree"
f=$(git -C "$W/k" diff --name-only "$BASE" | grep -m1 '\.cpp$')
cp "$W/k/$f" "$W/f.bak"; echo "// test" >> "$W/k/$f"
bash "$KT" check "$W/k" > /dev/null 2>&1 && no "check passed with $f changed" || ok "check fails with one line added to $f"
cp "$W/f.bak" "$W/k/$f"
n=$(git -C "$W/k" diff --name-only --diff-filter=A "$BASE" | head -1)
cp "$W/k/$n" "$W/n.bak"; echo "// test" >> "$W/k/$n"
bash "$KT" check "$W/k" > /dev/null 2>&1 && no "check passed with the new file $n changed" || ok "check fails with one line added to the new file $n"
cp "$W/n.bak" "$W/k/$n"
bash "$KT" check "$W/k" > /dev/null 2>&1 && ok "check passes again once both are restored" || no "check after the restore"
git -C "$W/k" reset -q --hard "$BASE"; git -C "$W/k" clean -qfdx
first=$(grep -v '^#' "$P/series" | grep . | head -1)
git -c core.autocrlf=false -C "$W/k" apply --whitespace=nowarn --intent-to-add "$P/$first"
bash "$KT" check "$W/k" > /dev/null 2>&1 && no "check passed with $first alone" || ok "check fails with $first alone ($(bash "$KT" hash "$W/k"))"
[ "$fails" = 0 ] && echo "test-kytyplus-tree: all PASS" || { echo "test-kytyplus-tree: $fails FAILED"; exit 1; }
