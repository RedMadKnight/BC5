#!/usr/bin/env bash
# kytyplus-tree.sh: the KytyPlus tree BC5 builds is the base commit plus every patch of backend/kytyplus-patches/series,
# in order, and nothing else. Its tree diff (`git diff --no-color <base> | md5sum`, first 8 hex; new files are added
# intent-to-add so the diff shows them) must equal the one recorded in backend/kytyplus-patches/TREE-DIFF.
#   kytyplus-tree.sh hash  <kyty>          print the tree's diff hash against the recorded base
#   kytyplus-tree.sh check <kyty>          exit 0 when HEAD is the base and the hash is the recorded one, else 1
#   kytyplus-tree.sh apply <kyty>          on a clean checkout of the base: apply the series, then check
#   kytyplus-tree.sh paths <kyty>          every path the series touches (NUL-separated), for a backup before a reset
# BC5_SRC (default: this script's repository) names the patches.
set -euo pipefail
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
BC5_SRC=${BC5_SRC:-$(cd "$HERE/../.." && pwd)}
P=$BC5_SRC/backend/kytyplus-patches
CMD=${1:?hash|check|apply|paths}; K=${2:?the KytyPlus checkout}
read -r BASE WANT < <(grep -v '^#' "$P/TREE-DIFF" | grep . | head -1)
[ -n "$BASE" ] && [ -n "$WANT" ] || { echo "kytyplus-tree: $P/TREE-DIFF holds no '<base> <hash>' line" >&2; exit 2; }
mapfile -t SERIES < <(grep -v '^#' "$P/series" | grep .)
[ "${#SERIES[@]}" -ge 1 ] || { echo "kytyplus-tree: $P/series lists no patch" >&2; exit 2; }
g() { git -c core.autocrlf=false -C "$K" "$@"; }
hash() { g diff --no-color "$BASE" | md5sum | cut -c1-8; }
case "$CMD" in
  hash) hash ;;
  check)
    full=$(g rev-parse "$BASE^{commit}") || { echo "kytyplus-tree: $BASE is not in $K" >&2; exit 1; }
    head=$(g rev-parse HEAD)
    [ "$head" = "$full" ] || { echo "kytyplus-tree: HEAD is ${head:0:7}, not the base $BASE" >&2; exit 1; }
    h=$(hash)
    [ "$h" = "$WANT" ] || { echo "kytyplus-tree: the tree diff is $h, not the recorded $WANT (series: ${SERIES[*]})" >&2; exit 1; }
    echo "kytyplus-tree: $K = $BASE + ${SERIES[*]}, tree diff $h as recorded" ;;
  paths) for s in "${SERIES[@]}"; do g apply --numstat -z "$P/$s"; done ;;
  apply)
    [ -z "$(g status --porcelain --untracked-files=no)" ] || { echo "kytyplus-tree: $K has local changes: not applied" >&2; exit 1; }
    for s in "${SERIES[@]}"; do
      [ -r "$P/$s" ] || { echo "kytyplus-tree: $P/$s missing" >&2; exit 1; }
      # files the patch creates must not pre-exist (an earlier version of the patch, or a saved tree)
      g apply --summary "$P/$s" | awk '/^ create mode/ {print $NF}' | while read -r f; do [ -n "$f" ] && rm -f "${K:?}/${f:?}"; done
      g apply --whitespace=nowarn --intent-to-add "$P/$s" || { echo "kytyplus-tree: $s does not apply" >&2; exit 1; }
    done
    exec bash "$0" check "$K" ;;
  *) echo "usage: kytyplus-tree.sh hash|check|apply|paths <kyty>" >&2; exit 2 ;;
esac
