#!/usr/bin/env bash
# bc5-build.sh — fetch BC5 and KytyPlus on the BC-250 and build a runnable emulator.
#
# Idempotent: a re-run only redoes what changed. Steps:
#   1. clone or fast-forward this repository (origin main) into $BC5_SRC;
#   2. clone KytyPlus (GPL-2.0) at $KYTY_COMMIT into $KYTY_SRC, or check that commit out on a
#      clean tree, and apply backend/kytyplus-patches/0001-bc5-lle-agc.patch;
#   3. inside the `ubuntu` distrobox: apt packages, the backend library (BC5_WITH_AMDGPU=ON,
#      Release) into $WORK/backend-ubuntu and kyty_emulator (Ninja, clang, Release) into
#      $WORK/kytyplus-build, then the lean variant (KYTY_BC5_LEAN=ON: no tracing, journals or
#      measurements, experiment 0177) into $WORK/kytyplus-build-lean;
#   4. keep the previous binary as kyty_emulator.prev and print what was built.
# Local changes in either checkout are never discarded silently: they go to a diff file under
# $WORK (and a git stash for the BC5 checkout) and the script says where.
# Everything is logged to $LOG; the script exits non-zero on the first failure and names the log.
#
# Knobs (environment): BC5_SRC, KYTY_SRC, WORK, BC5_REPO, KYTY_REPO, KYTY_COMMIT, BOX (distrobox
# name), JOBS, MIN_FREE_GB (refuse below this, default 15), BC5_BUILD_WAIT (seconds to wait for a
# running emulator before replacing its binary, 0 = forever), BC5_BUILD_KEEP_KYTY=1 (build the
# KytyPlus tree as it is, for host-side experiments), BC5_BUILD_MOUNT=1 (also build bc5-mount with
# cargo; off by default because cargo may need the network for crates and overwrites a binary a
# running mount may use), BC5_BUILD_LEAN=0 (skip the lean variant).
set -euo pipefail

BC5_SRC=${BC5_SRC:-$HOME/src/bc5}
KYTY_SRC=${KYTY_SRC:-$HOME/src/KytyPlus}
WORK=${WORK:-$HOME/bc5-work}
BC5_REPO=${BC5_REPO:-https://github.com/RedMadKnight/BC5.git}
KYTY_REPO=${KYTY_REPO:-https://github.com/Coder787-source/KytyPlus.git}
KYTY_COMMIT=${KYTY_COMMIT:-f266548}
BOX=${BOX:-ubuntu}
JOBS=${JOBS:-8}
MIN_FREE_GB=${MIN_FREE_GB:-15}
BC5_BUILD_WAIT=${BC5_BUILD_WAIT:-0}
LOG=$WORK/bc5-build.log
TS=$(date +%Y%m%d-%H%M%S)
PATCH_REL=backend/kytyplus-patches/0001-bc5-lle-agc.patch
BACKEND_BUILD=$WORK/backend-ubuntu
EMU_BUILD=$WORK/kytyplus-build
EMU=$EMU_BUILD/src/kyty_emulator
LEAN_BUILD=$WORK/kytyplus-build-lean
BC5_BUILD_LEAN=${BC5_BUILD_LEAN:-1}

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
for t in git distrobox df; do command -v "$t" >/dev/null || fail "$t is not installed on the host"; done
distrobox list --no-color 2>/dev/null | awk -F'|' 'NR>1 {gsub(/^ +| +$/, "", $2); print $2}' | grep -qx "$BOX" || fail "no distrobox named '$BOX' (README: How to start, 2)"
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
PATCH=$BC5_SRC/$PATCH_REL
[ -r "$PATCH" ] || fail "patch $PATCH missing"

step kytyplus-checkout
if [ ! -d "$KYTY_SRC/.git" ]; then
  say "cloning $KYTY_REPO into $KYTY_SRC"
  git clone "$KYTY_REPO" "$KYTY_SRC"
fi
git -C "$KYTY_SRC" cat-file -e "$KYTY_COMMIT^{commit}" 2>/dev/null || git -C "$KYTY_SRC" fetch origin
KYTY_FULL=$(git -C "$KYTY_SRC" rev-parse "$KYTY_COMMIT^{commit}") || fail "commit $KYTY_COMMIT not in $KYTY_SRC"
kyty_head=$(git -C "$KYTY_SRC" rev-parse HEAD)
# Up to date when HEAD is the pinned commit and the working tree holds exactly the patch: the
# patch applies in reverse and the changed files, with their line counts, are the patch's.
patched_ok=0
if [ "$kyty_head" = "$KYTY_FULL" ] \
   && git -C "$KYTY_SRC" apply --check -R "$PATCH" 2>/dev/null \
   && cmp -s <(git -C "$KYTY_SRC" diff --numstat | sort) <(git -C "$KYTY_SRC" apply --numstat "$PATCH" | sort); then
  patched_ok=1
fi
if [ "$patched_ok" = 1 ]; then
  say "KytyPlus at ${KYTY_COMMIT} with $PATCH_REL already applied; tree unchanged"
elif [ "${BC5_BUILD_KEEP_KYTY:-0}" = 1 ]; then
  say "BC5_BUILD_KEEP_KYTY=1: building $KYTY_SRC as it is (HEAD ${kyty_head:0:7}; the patch is NOT re-applied)"
else
  if [ -n "$(git -C "$KYTY_SRC" status --porcelain)" ]; then
    bk=$WORK/kytyplus-local-$TS.diff
    git -C "$KYTY_SRC" status --porcelain > "$bk.files"
    git -C "$KYTY_SRC" diff --binary > "$bk" || true
    say "LOCAL CHANGES in $KYTY_SRC (HEAD ${kyty_head:0:7}) saved to $bk (file list: $bk.files); the tree is reset to ${KYTY_COMMIT} + $PATCH_REL. Untracked files other than the patch's are left in place."
  fi
  git -C "$KYTY_SRC" reset -q
  git -C "$KYTY_SRC" checkout -q -f "$KYTY_FULL"
  # files the patch creates must not pre-exist (an earlier version of the patch, or the saved tree)
  git -C "$KYTY_SRC" apply --summary "$PATCH" | awk '/^ create mode/ {print $NF}' | while read -r f; do
    [ -n "$f" ] && rm -f "${KYTY_SRC:?}/${f:?}"
  done
  git -C "$KYTY_SRC" apply --intent-to-add "$PATCH" || fail "$PATCH_REL does not apply to KytyPlus $KYTY_COMMIT"
  say "KytyPlus checked out at ${KYTY_FULL:0:7} and patched"
fi
git -C "$KYTY_SRC" submodule update --init --recursive --depth 1 2>&1 | tail -3 || true
if git -C "$KYTY_SRC" submodule status --recursive | grep -q '^[-+]'; then
  fail "KytyPlus submodules are not at their recorded commits (see 'git submodule status')"
fi
PATCH_SHA=$(sha256sum "$PATCH" | cut -c1-12)

step wait-for-emulator
waited=0
while pgrep -x kyty_emulator >/dev/null; do
  if [ "$BC5_BUILD_WAIT" != 0 ] && [ "$waited" -ge "$BC5_BUILD_WAIT" ]; then
    fail "kyty_emulator is still running after ${waited} s (pid $(pgrep -x kyty_emulator | head -1)); not replacing its binary. Re-run later."
  fi
  [ $((waited % 300)) -eq 0 ] && say "kyty_emulator is running (pid $(pgrep -x kyty_emulator | head -1)); waiting before the binary is replaced (${waited} s)"
  sleep 30; waited=$((waited + 30))
done
if [ -x "$EMU" ]; then
  cp -p "$EMU" "$EMU.prev"
  say "previous binary kept as $EMU.prev ($(stat -c '%y %s' "$EMU.prev"))"
fi

step build-in-distrobox
INNER=$WORK/.bc5-build.inner.sh
cat > "$INNER" <<INNER_EOF
#!/usr/bin/env bash
set -euo pipefail
say() { printf '[bc5-build %s] %s\n' "\$(date +%H:%M:%S)" "\$*"; }
# The package list of README "How to start", 2 (the KytyPlus and BC5 build dependencies).
PKGS="git cmake pkg-config cargo fuse3 libfuse3-dev libdrm-dev clang lld ninja-build glslang-tools libasound2-dev libdbus-1-dev libgl1-mesa-dev libpulse-dev libudev-dev libwayland-dev libx11-dev libxcursor-dev libxext-dev libxfixes-dev libxi-dev libxkbcommon-dev libxrandr-dev libxss-dev wayland-protocols libedit-dev libevdev-dev libjack-dev libopenal-dev libpng-dev libsdl2-dev libsndio-dev libssl-dev libvulkan-dev zlib1g-dev"
say "apt packages (no-op when installed)"
if ! sudo apt-get install --no-install-recommends --yes \$PKGS > "$WORK/bc5-build-apt.log" 2>&1; then
  say "apt-get install failed (no network?); continuing with what is installed, see $WORK/bc5-build-apt.log"
fi
for t in cmake ninja clang clang++; do command -v \$t >/dev/null || { say "\$t missing in the $BOX distrobox"; exit 1; }; done
say "backend: cmake configure"
cmake -S "$BC5_SRC/backend" -B "$BACKEND_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \\
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF > "$WORK/bc5-build-backend-configure.log" 2>&1 \\
  || { tail -30 "$WORK/bc5-build-backend-configure.log"; say "backend configure failed"; exit 1; }
say "backend: build"
cmake --build "$BACKEND_BUILD" -j$JOBS
say "emulator: cmake configure"
cmake -S "$KYTY_SRC" -B "$EMU_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \\
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \\
  -DKYTY_BC5_BACKEND_SRC="$BC5_SRC/backend" -DKYTY_BC5_BACKEND_BUILD="$BACKEND_BUILD" > "$WORK/bc5-build-emulator-configure.log" 2>&1 \\
  || { tail -30 "$WORK/bc5-build-emulator-configure.log"; say "emulator configure failed"; exit 1; }
say "emulator: build kyty_emulator -j$JOBS"
cmake --build "$EMU_BUILD" --target kyty_emulator -j$JOBS
if [ "$BC5_BUILD_LEAN" = 1 ]; then
  # Experiment 0177: the same tree without tracing, journals and measurements, next to the normal
  # build (the "BC5 emulator (lean)" shortcut, BC5_LEAN=1 in the play-*.sh launchers).
  say "lean emulator: cmake configure (KYTY_BC5_LEAN=ON)"
  cmake -S "$KYTY_SRC" -B "$LEAN_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \\
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \\
    -DKYTY_BC5_BACKEND_SRC="$BC5_SRC/backend" -DKYTY_BC5_BACKEND_BUILD="$BACKEND_BUILD" -DKYTY_BC5_LEAN=ON > "$WORK/bc5-build-lean-configure.log" 2>&1 \\
    || { tail -30 "$WORK/bc5-build-lean-configure.log"; say "lean emulator configure failed"; exit 1; }
  say "lean emulator: build kyty_emulator -j$JOBS"
  cmake --build "$LEAN_BUILD" --target kyty_emulator -j$JOBS
fi
if [ "${BC5_BUILD_MOUNT:-0}" = 1 ]; then
  say "bc5-mount: cargo build"
  (cd "$BC5_SRC/tools" && CARGO_TARGET_DIR="$WORK/bc5-tools-ubuntu" cargo build --release --locked -p bc5-mount)
fi
INNER_EOF
t0=$(date +%s)
distrobox enter "$BOX" -- bash "$INNER" || fail "build inside the $BOX distrobox failed (see above)"
say "build finished in $(( $(date +%s) - t0 )) s"

step report
[ -x "$EMU" ] || fail "$EMU was not produced"
if [ -x "$EMU.prev" ] && cmp -s "$EMU" "$EMU.prev"; then
  say "binary unchanged (identical to $EMU.prev)"
fi
say "emulator: $EMU"
say "  built:   $(stat -c %y "$EMU")"
say "  size:    $(stat -c %s "$EMU") bytes"
say "  bc5:     $BC5_HEAD ($(git -C "$BC5_SRC" log -1 --format=%s | cut -c1-70))"
say "  kytyplus: $(git -C "$KYTY_SRC" rev-parse HEAD) + $PATCH_REL (sha256 $PATCH_SHA...)"
say "  backend: $BACKEND_BUILD   emulator build: $EMU_BUILD"
if [ "$BC5_BUILD_LEAN" = 1 ]; then
  [ -x "$LEAN_BUILD/src/kyty_emulator" ] || fail "$LEAN_BUILD/src/kyty_emulator was not produced"
  say "  lean:    $LEAN_BUILD/src/kyty_emulator ($(stat -c %y "$LEAN_BUILD/src/kyty_emulator" | cut -c1-19))"
fi
say "OK; log: $LOG"
