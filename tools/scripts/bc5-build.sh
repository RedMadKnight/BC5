#!/usr/bin/env bash
# bc5-build.sh — fetch BC5 and KytyPlus on the BC-250 and build a runnable emulator.
#
# Idempotent: a re-run only redoes what changed. Steps:
#   1. clone or fast-forward this repository (origin main) into $BC5_SRC;
#   2. clone KytyPlus (GPL-2.0) at $KYTY_COMMIT into $KYTY_SRC, or check that commit out on a
#      clean tree, and apply every patch of backend/kytyplus-patches/series in order (0001, then 0002:
#      BC5's own libSceAgc, libSceAgcDriver, libScePsml) through tools/scripts/kytyplus-tree.sh, which
#      refuses a tree whose diff is not the one recorded in backend/kytyplus-patches/TREE-DIFF;
#   3. on the host, with the private toolchain ~/bc5-toolchain (tools/scripts/bc5-toolchain.sh, made on the first run;
#      ADR 0015 amended 2026-11-24: no container, no layering, no sudo): the backend library (BC5_WITH_AMDGPU=ON,
#      Release) into $WORK/backend-ubuntu and kyty_emulator (Ninja, clang 21.1.8, Release) into $WORK/kytyplus-build,
#      then the lean variant (KYTY_BC5_LEAN=ON: no tracing, journals or measurements, experiment 0177) into
#      $WORK/kytyplus-build-lean; a build directory configured by another compiler (the old container's) is
#      refused, never overwritten;
#   4. keep the previous binary as kyty_emulator.prev and print what was built.
# Before resetting KytyPlus, tracked/index patches and untracked files are backed up under
# $WORK. BC5 changes also go to a git stash. The script says where each backup lives.
# Everything is logged to $LOG; the script exits non-zero on the first failure and names the log.
#
# Knobs (environment): BC5_SRC, KYTY_SRC, WORK, BC5_REPO, KYTY_REPO, KYTY_COMMIT, BC5_TOOLCHAIN (default
# ~/bc5-toolchain), JOBS, MIN_FREE_GB (refuse below this, default 15), BC5_BUILD_WAIT (seconds to wait for a
# running emulator before replacing its binary, 0 = forever), BC5_BUILD_KEEP_KYTY=1 (build the
# KytyPlus tree as it is, for host-side experiments), BC5_BUILD_MOUNT=1 (also build bc5-mount with
# cargo; off by default because cargo may need the network for crates and overwrites a binary a
# running mount may use), BC5_BUILD_LEAN=0 (skip the lean variant), BC5_BUILD_NORMAL=0 (skip the normal
# emulator: lean only, as bc5-install.sh does by default; the backend is built either way).
set -euo pipefail

BC5_SRC=${BC5_SRC:-$HOME/src/bc5}
KYTY_SRC=${KYTY_SRC:-$HOME/src/KytyPlus}
WORK=${WORK:-$HOME/bc5-work}
BC5_REPO=${BC5_REPO:-https://github.com/RedMadKnight/BC5.git}
KYTY_REPO=${KYTY_REPO:-https://github.com/Coder787-source/KytyPlus.git}
KYTY_COMMIT=${KYTY_COMMIT:-f266548}
T=${BC5_TOOLCHAIN:-$HOME/bc5-toolchain}
JOBS=${JOBS:-8}
MIN_FREE_GB=${MIN_FREE_GB:-15}
BC5_BUILD_WAIT=${BC5_BUILD_WAIT:-0}
LOG=$WORK/bc5-build.log
TS=$(date +%Y%m%d-%H%M%S)
SERIES_REL=backend/kytyplus-patches/series  # the patches, in order; TREE-DIFF beside it holds the resulting tree diff
BACKEND_BUILD=$WORK/backend-ubuntu
EMU_BUILD=$WORK/kytyplus-build
EMU=$EMU_BUILD/src/kyty_emulator
LEAN_BUILD=$WORK/kytyplus-build-lean
BC5_BUILD_LEAN=${BC5_BUILD_LEAN:-1}
BC5_BUILD_NORMAL=${BC5_BUILD_NORMAL:-1}
[ "$BC5_BUILD_NORMAL" = 1 ] || [ "$BC5_BUILD_LEAN" = 1 ] || { echo "bc5-build: BC5_BUILD_NORMAL=0 and BC5_BUILD_LEAN=0 build no emulator" >&2; exit 1; }

# The script may live inside the checkout it fast-forwards; run from a copy so that git cannot
# change the file bash is reading.
if [ -z "${BC5_BUILD_REEXEC:-}" ]; then
  mkdir -p "$WORK"
  cp "$0" "$WORK/.bc5-build.running.sh"
  BC5_BUILD_REEXEC=1 exec bash "$WORK/.bc5-build.running.sh" "$@"
fi

mkdir -p "$WORK"
exec > >(tee -a "$LOG") 2>&1
STEP=start
say() { printf '[bc5-build %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fail() { say "FAILED ($STEP): $*"; say "log: $LOG"; exit 1; }
trap 'rc=$?; if [ $rc -ne 0 ]; then say "FAILED ($STEP), exit $rc; log: $LOG"; fi' EXIT
step() { STEP=$1; say "== $1"; }

say "start $TS  host=$(hostname)  user=$USER  args: $*"

step prerequisites
for t in git df mktemp tar curl rpm2cpio cpio; do command -v "$t" >/dev/null || fail "$t is not installed on the host"; done
[ -e /run/.containerenv ] && fail "run it on the host, not in a container (ADR 0015)"
avail_gb=$(( $(df --output=avail -B1 "$WORK" | tail -1) / 1024 / 1024 / 1024 ))
say "free space on $WORK: ${avail_gb} GB (minimum ${MIN_FREE_GB})"
[ "$avail_gb" -ge "$MIN_FREE_GB" ] || fail "only ${avail_gb} GB free, below the ${MIN_FREE_GB} GB minimum; free space first (nothing is deleted by this script)"

step bc5-repository
if [ ! -d "$BC5_SRC/.git" ]; then
  say "cloning $BC5_REPO into $BC5_SRC"
  git clone "$BC5_REPO" "$BC5_SRC"
else
  git -C "$BC5_SRC" fetch origin
  branch=$(git -C "$BC5_SRC" symbolic-ref --short -q HEAD || true)
  [ "$branch" = main ] || fail "$BC5_SRC is on '${branch:-a detached HEAD}', not main; switch it yourself (git -C $BC5_SRC checkout main) and re-run"
  if [ -n "$(git -C "$BC5_SRC" status --porcelain)" ]; then
    bk=$WORK/bc5-local-$TS.diff
    git -C "$BC5_SRC" status --porcelain > "$bk.files"
    git -C "$BC5_SRC" diff HEAD > "$bk" || true
    git -C "$BC5_SRC" stash push --include-untracked -m "bc5-build $TS before fast-forward" >/dev/null
    say "LOCAL CHANGES in $BC5_SRC were set aside: diff $bk, file list $bk.files, and 'git stash list' entry 'bc5-build $TS' (git stash pop restores them)"
  fi
  before=$(git -C "$BC5_SRC" rev-parse HEAD)
  git -C "$BC5_SRC" merge --ff-only origin/main || fail "main in $BC5_SRC cannot be fast-forwarded to origin/main (local commits?); resolve by hand"
  after=$(git -C "$BC5_SRC" rev-parse HEAD)
  if [ "$before" = "$after" ]; then say "bc5 already at origin/main"; else say "bc5 ${before:0:7} -> ${after:0:7}"; fi
fi
BC5_HEAD=$(git -C "$BC5_SRC" rev-parse HEAD)
KT=$BC5_SRC/tools/scripts/kytyplus-tree.sh
[ -r "$KT" ] && [ -r "$BC5_SRC/$SERIES_REL" ] || fail "$KT or $SERIES_REL missing"
kt() { BC5_SRC="$BC5_SRC" bash "$KT" "$@"; }

step kytyplus-checkout
if [ ! -d "$KYTY_SRC/.git" ]; then
  say "cloning $KYTY_REPO into $KYTY_SRC"
  git clone "$KYTY_REPO" "$KYTY_SRC"
fi
git -C "$KYTY_SRC" cat-file -e "$KYTY_COMMIT^{commit}" 2>/dev/null || git -C "$KYTY_SRC" fetch origin
KYTY_FULL=$(git -C "$KYTY_SRC" rev-parse "$KYTY_COMMIT^{commit}") || fail "commit $KYTY_COMMIT not in $KYTY_SRC"
kyty_head=$(git -C "$KYTY_SRC" rev-parse HEAD)
# Up to date when HEAD is the pinned commit and the tree diff is the recorded one (every patch of the series, nothing else).
patched_ok=0
if [ "$kyty_head" = "$KYTY_FULL" ] && kt check "$KYTY_SRC" > /dev/null 2>&1; then
  patched_ok=1
fi
if [ "$patched_ok" = 1 ]; then
  say "KytyPlus at ${KYTY_COMMIT} with the series already applied (tree diff $(kt hash "$KYTY_SRC") as recorded); tree unchanged"
elif [ "${BC5_BUILD_KEEP_KYTY:-0}" = 1 ]; then
  say "BC5_BUILD_KEEP_KYTY=1: building $KYTY_SRC as it is (HEAD ${kyty_head:0:7}; the patch is NOT re-applied)"
else
  # Complete the backup before any reset, checkout or removal. A plain `git diff`
  # omits staged content, and no Git diff holds untracked files.
  bk=$(mktemp -d "$WORK/kytyplus-local-$TS.XXXXXX") || fail "cannot create backup directory"
  git -C "$KYTY_SRC" rev-parse HEAD > "$bk/HEAD" || fail "cannot save backup HEAD"
  git -C "$KYTY_SRC" status --porcelain=v1 -z > "$bk/status.z" || fail "cannot save status"
  git -C "$KYTY_SRC" diff HEAD --binary > "$bk/worktree.patch" || fail "cannot save worktree"
  git -C "$KYTY_SRC" diff --cached --binary > "$bk/index.patch" || fail "cannot save index"
  git -C "$KYTY_SRC" ls-files --others --exclude-standard -z > "$bk/untracked.z" || fail "cannot list untracked files"
  # A patch-created path can already exist as an ignored file; the cleanup below
  # would remove it too. Include ignored collisions, without archiving build trees.
  kt paths "$KYTY_SRC" > "$bk/patch-paths.z" || fail "cannot list patch paths"
  while IFS= read -r -d '' record; do
    path=${record#*$'\t'}
    path=${path#*$'\t'}
    if [ -e "$KYTY_SRC/$path" ] || [ -L "$KYTY_SRC/$path" ]; then
      ignored_rc=0
      git -C "$KYTY_SRC" check-ignore -q -- "$path" || ignored_rc=$?
      [ "$ignored_rc" -le 1 ] || fail "cannot check ignored path: $path"
      if [ "$ignored_rc" = 0 ]; then
        printf '%s\0' "$path" >> "$bk/untracked.z" || fail "cannot list ignored collision"
      fi
    fi
  done < "$bk/patch-paths.z"
  tar -C "$KYTY_SRC" --null --verbatim-files-from -T "$bk/untracked.z" -cf "$bk/untracked.tar" || fail "cannot archive untracked files"
  tar -tf "$bk/untracked.tar" > "$bk/archive-list.txt" || fail "cannot verify backup archive"
  # Restore in a clean checkout at HEAD: apply worktree.patch to the worktree,
  # index.patch with `git apply --cached`, then extract untracked.tar. Skip empty
  # patches. Intent-to-add contents survive, but that index flag is not restored.
  printf '%s\n' 'backup complete' > "$bk/COMPLETE" || fail "cannot finish backup"
  say "KytyPlus backup complete at $bk; HEAD, staged/worktree patches and untracked archive saved"
  git -C "$KYTY_SRC" reset -q
  git -C "$KYTY_SRC" checkout -q -f "$KYTY_FULL"
  # files the patch creates must not pre-exist (an earlier version of the patch, or the saved tree)
  kt apply "$KYTY_SRC" || fail "the series ($SERIES_REL) does not give the recorded tree on KytyPlus $KYTY_COMMIT"
  say "KytyPlus checked out at ${KYTY_FULL:0:7} and patched"
fi
git -C "$KYTY_SRC" submodule update --init --recursive --depth 1 2>&1 | tail -3 || true
if git -C "$KYTY_SRC" submodule status --recursive | grep -q '^[-+]'; then
  fail "KytyPlus submodules are not at their recorded commits (see 'git submodule status')"
fi
PATCH_SHA=$(cd "$BC5_SRC/backend/kytyplus-patches" && grep -v '^#' series | grep . | xargs cat | sha256sum | cut -c1-12)

step wait-for-emulator
waited=0
while pgrep -x kyty_emulator >/dev/null; do
  if [ "$BC5_BUILD_WAIT" != 0 ] && [ "$waited" -ge "$BC5_BUILD_WAIT" ]; then
    fail "kyty_emulator is still running after ${waited} s (pid $(pgrep -x kyty_emulator | head -1)); not replacing its binary. Re-run later."
  fi
  [ $((waited % 300)) -eq 0 ] && say "kyty_emulator is running (pid $(pgrep -x kyty_emulator | head -1)); waiting before the binary is replaced (${waited} s)"
  sleep 30; waited=$((waited + 30))
done
if [ "$BC5_BUILD_NORMAL" = 1 ] && [ -x "$EMU" ]; then
  cp -p "$EMU" "$EMU.prev"
  say "previous binary kept as $EMU.prev ($(stat -c '%y %s' "$EMU.prev"))"
fi

step build
[ -r "$T/env.sh" ] || BC5_TOOLCHAIN=$T bash "$BC5_SRC/tools/scripts/bc5-toolchain.sh" || fail "the host toolchain could not be made (tools/scripts/bc5-toolchain.sh)"
# A build directory another compiler configured (the old ubuntu container's /usr/bin/clang++) is not reused.
for d in "$BACKEND_BUILD" "$EMU_BUILD" "$LEAN_BUILD"; do
  c=$(sed -n 's/^CMAKE_CXX_COMPILER:[A-Z]*=//p' "$d/CMakeCache.txt" 2>/dev/null)
  [ -z "$c" ] || [ "$c" = "$(. "$T/env.sh"; command -v clang++)" ] || fail "$d was configured with $c, not the host toolchain: move it aside yourself (it may be a shared build) and re-run"
done
# The host's libstdc++ 16 no longer pulls <cstdint> in through other headers; KytyPlus's gpu_translator.h relies on it.
# Until a patch adds the include there (next bake), it is forced for every C++ unit.
KYTY_HOST_FLAGS=(-DCMAKE_CXX_FLAGS="-include cstdint" -DSDL_SNDIO=OFF -DKYTY_GLSLANG_VALIDATOR="$T/bin/glslangValidator"
  -DKYTY_LZMA_LIBRARY="$T/sysroot/usr/lib64/liblzma.so" -DKYTY_OPUS_LIBRARY="$T/sysroot/usr/lib64/libopus.so")
t0=$(date +%s)
(
  . "$T/env.sh"
  for t in cmake ninja clang clang++ ld.lld cargo; do command -v $t >/dev/null || fail "$t missing in $T"; done
  say "backend: cmake configure"
  cmake -S "$BC5_SRC/backend" -B "$BACKEND_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF > "$WORK/bc5-build-backend-configure.log" 2>&1 \
    || { tail -30 "$WORK/bc5-build-backend-configure.log"; fail "backend configure failed"; }
  say "backend: build"
  cmake --build "$BACKEND_BUILD" -j$JOBS
  for v in normal lean; do
    if [ "$v" = normal ]; then [ "$BC5_BUILD_NORMAL" = 1 ] || continue; dir=$EMU_BUILD; lean=OFF
    else [ "$BC5_BUILD_LEAN" = 1 ] || continue; dir=$LEAN_BUILD; lean=ON; fi  # lean: experiment 0177
    say "$v emulator: cmake configure (KYTY_BC5_LEAN=$lean)"
    cmake -S "$KYTY_SRC" -B "$dir" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF "${KYTY_HOST_FLAGS[@]}" \
      -DKYTY_BC5_BACKEND_SRC="$BC5_SRC/backend" -DKYTY_BC5_BACKEND_BUILD="$BACKEND_BUILD" -DKYTY_BC5_LEAN=$lean > "$WORK/bc5-build-$v-configure.log" 2>&1 \
      || { tail -30 "$WORK/bc5-build-$v-configure.log"; fail "$v emulator configure failed"; }
    say "$v emulator: build kyty_emulator -j$JOBS"
    cmake --build "$dir" --target kyty_emulator -j$JOBS
  done
  if [ "${BC5_BUILD_MOUNT:-0}" = 1 ]; then
    say "bc5-mount: cargo build (Rust pinned by $T/env.sh)"
    (cd "$BC5_SRC/tools" && CARGO_TARGET_DIR="$WORK/bc5-tools-ubuntu" cargo build --release --locked -p bc5-mount)
  fi
) || fail "the host build failed (see above)"
say "build finished in $(( $(date +%s) - t0 )) s"

step report
if [ "$BC5_BUILD_NORMAL" = 1 ]; then
  [ -x "$EMU" ] || fail "$EMU was not produced"
  if [ -x "$EMU.prev" ] && cmp -s "$EMU" "$EMU.prev"; then
    say "binary unchanged (identical to $EMU.prev)"
  fi
  say "emulator: $EMU"
  say "  built:   $(stat -c %y "$EMU")"
  say "  size:    $(stat -c %s "$EMU") bytes"
else
  say "emulator: not built (BC5_BUILD_NORMAL=0)"
fi
say "  bc5:     $BC5_HEAD ($(git -C "$BC5_SRC" log -1 --format=%s | cut -c1-70))"
say "  kytyplus: $(git -C "$KYTY_SRC" rev-parse HEAD) + $(grep -v '^#' "$BC5_SRC/$SERIES_REL" | grep . | tr '\n' ' ')(sha256 $PATCH_SHA..., tree diff $(kt hash "$KYTY_SRC"))"
say "  backend: $BACKEND_BUILD   emulator build: $EMU_BUILD"
if [ "$BC5_BUILD_LEAN" = 1 ]; then
  [ -x "$LEAN_BUILD/src/kyty_emulator" ] || fail "$LEAN_BUILD/src/kyty_emulator was not produced"
  say "  lean:    $LEAN_BUILD/src/kyty_emulator ($(stat -c %y "$LEAN_BUILD/src/kyty_emulator" | cut -c1-19))"
fi
# ADR 0015: every binary must need only the host's own libraries (host-deps-check.sh, the gate).
hosts=""
[ "$BC5_BUILD_NORMAL" = 1 ] && hosts="$hosts $EMU"
[ "$BC5_BUILD_LEAN" = 1 ] && hosts="$hosts $LEAN_BUILD/src/kyty_emulator"
# shellcheck disable=SC2086
HDC=$(dirname "$0")/host-deps-check.sh
[ -r "$HDC" ] || HDC=$BC5_SRC/tools/scripts/host-deps-check.sh
[ -z "$hosts" ] || bash "$HDC" $hosts || fail "a build needs what the host does not have (host-deps-check.sh above)"
say "OK; log: $LOG"
