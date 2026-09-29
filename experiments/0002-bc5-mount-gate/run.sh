#!/usr/bin/env bash
# Gate G0a for bc5-mount (docs/PHASES.md): build a synthetic container, mount
# it with FUSE, compare the mounted tree and per-file SHA-256 with the source
# directory, and measure sequential read throughput. Linux with FUSE only.
#
# Usage: experiments/0002-bc5-mount-gate/run.sh [preset] [workdir]
#   preset   fixture preset (default: sparse-1g; use one-small for a smoke test)
#   workdir  scratch directory (default: mktemp)
# Optional oracle: if `python -m mkpfs` is available, the container is also
# verified with MkPFS (never vendored; separate process).
set -euo pipefail

PRESET="${1:-sparse-1g}"
WORK="${2:-$(mktemp -d)}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/experiments/0002-bc5-mount-gate/raw"
mkdir -p "$LOG" "$WORK"
echo "work dir: $WORK; preset: $PRESET" | tee "$LOG/run.log"

(cd "$ROOT/tools" && cargo build --release -q)
BIN="$ROOT/tools/target/release"

# 1. Fixture: container + the directory it was built from.
"$BIN/bc5-fixture" build "$PRESET" "$WORK/fixture.ffpfsc" | tee -a "$LOG/run.log"
"$BIN/bc5-fixture" tree "$PRESET" "$WORK/source"
"$BIN/bc5-fixture" hashes "$PRESET" > "$WORK/expected.txt"

# 2. Reader path without FUSE.
"$BIN/bc5-mount" inspect "$WORK/fixture.ffpfsc" | tee -a "$LOG/run.log"
"$BIN/bc5-mount" verify "$WORK/fixture.ffpfsc" > "$WORK/verify.txt"
diff -u "$WORK/expected.txt" "$WORK/verify.txt" && echo "verify: OK" | tee -a "$LOG/run.log"

# 3. FUSE mount: tree and hashes must equal the source directory.
mkdir -p "$WORK/mnt"
"$BIN/bc5-mount" mount "$WORK/fixture.ffpfsc" "$WORK/mnt" &
MOUNT_PID=$!
trap 'fusermount3 -u "$WORK/mnt" 2>/dev/null || fusermount -u "$WORK/mnt" 2>/dev/null || true; wait $MOUNT_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do mountpoint -q "$WORK/mnt" && break; sleep 0.1; done
mountpoint -q "$WORK/mnt"

(cd "$WORK/source" && find . -type f | sort) > "$WORK/tree.source"
(cd "$WORK/mnt" && find . -type f | sort) > "$WORK/tree.mnt"
diff -u "$WORK/tree.source" "$WORK/tree.mnt" && echo "tree: OK" | tee -a "$LOG/run.log"
(cd "$WORK/source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$WORK/sha.source"
(cd "$WORK/mnt" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$WORK/sha.mnt"
diff -u "$WORK/sha.source" "$WORK/sha.mnt" && echo "sha256: OK" | tee -a "$LOG/run.log"

# 4. Sequential read throughput of the largest file through the mount.
BIG="$(cd "$WORK/mnt" && find . -type f -printf '%s %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
echo "throughput file: $BIG" | tee -a "$LOG/run.log"
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
dd if="$WORK/mnt/$BIG" of=/dev/null bs=1M 2>&1 | tail -1 | tee -a "$LOG/run.log"

# 5. Optional oracle.
if python3 -c 'import mkpfs' 2>/dev/null; then
    python3 -m mkpfs verify "$WORK/fixture.ffpfsc" 2>&1 | tail -5 | tee -a "$LOG/run.log"
else
    echo "mkpfs not installed; oracle skipped" | tee -a "$LOG/run.log"
fi
echo "done" | tee -a "$LOG/run.log"
