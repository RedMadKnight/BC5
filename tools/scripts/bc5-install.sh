#!/usr/bin/env bash
# bc5-install.sh — BC5 on a BC-250 from nothing: checks the machine, makes the build container, builds the lean
# emulator and bc5-mount, puts the launchers in ~/bc5-work and a "BC5 emulator (lean)" shortcut on the desktop.
# Run it on the host (not inside a container), as your own user, from a clone of the repository:
#
#   git clone https://github.com/RedMadKnight/BC5.git ~/src/bc5
#   bash ~/src/bc5/tools/scripts/bc5-install.sh
#
#   bc5-install.sh                 everything below; a re-run redoes only what changed
#   bc5-install.sh check           only the machine checks (step 1); changes nothing
#   bc5-install.sh kargs           add the two kernel arguments BC5 needs (rpm-ostree systems; asks for your
#                                  password through sudo; a reboot follows)
#   bc5-install.sh pack <image|folder>
#                                  the module pack the second title needs, from another game's fakelib/
#                                  (ASTRO BOT's): an installed game's folder, or a .ffpfsc/.pkg image (mounted
#                                  read-only for the copy)
#
# Steps of the full run:
#   1. checks: a BC-250 GPU (1002:13fe), the kernel arguments ttm.pages_limit and udmabuf.size_limit_mb, GTT size,
#      /dev/udmabuf writable, the memlock limit, git/distrobox/podman, free space. A missing kernel argument stops
#      the run (fix: bc5-install.sh kargs, reboot, run again); the rest are warnings.
#   2. the Ubuntu 26.04 distrobox "$BOX" (default ubuntu), created when missing;
#   3. tools/scripts/bc5-build.sh with BC5_BUILD_MOUNT=1 and, unless BC5_INSTALL_NORMAL=1, BC5_BUILD_NORMAL=0:
#      KytyPlus at its pinned commit plus patch 0001, the backend, the lean emulator, bc5-mount;
#   4. the launchers of tools/scripts/launchers into $WORK (an existing different file is kept as *.bak-<time>),
#      bc5-run.env from its template, an input.cfg, the empty learned-windows file, the data folders;
#   5. the desktop shortcut "BC5 emulator (lean)" (and "BC5 emulator" with BC5_INSTALL_NORMAL=1), on the desktop
#      and in the application menu.
#
# Knobs (environment): BOX, WORK (~/bc5-work), DATA (~/bc5-data), KYTY_SRC (~/src/KytyPlus), JOBS, MIN_FREE_GB
# (default 15; a lean install takes about 3 GB, your games come on top), BC5_INSTALL_NORMAL=1 (also the normal build with its
# measurements and its shortcut), BC5_INSTALL_SKIP_BUILD=1 (steps 4-5 only), BC5_INSTALL_FORCE=1 (go on past a
# failed check), DESKTOP_DIR, APPS_DIR. The game files are yours: BC5 ships none and needs no firmware.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
LAUNCHERS=$HERE/launchers
BOX=${BOX:-ubuntu}
IMAGE=${BC5_BOX_IMAGE:-docker.io/library/ubuntu:26.04}
WORK=${WORK:-$HOME/bc5-work}
DATA=${DATA:-$HOME/bc5-data}
KYTY_SRC=${KYTY_SRC:-$HOME/src/KytyPlus}
MIN_FREE_GB=${MIN_FREE_GB:-15}
NORMAL=${BC5_INSTALL_NORMAL:-0}
TS=$(date +%Y%m%d-%H%M%S)
PAGES_LIMIT=3407872     # 13 GiB of GTT on the 16 GB board (D12)
UDMABUF_MB=1024         # one dma-buf import up to 1 GiB (F125)
PACK=$DATA/sysmodules-pack-hle-ampr-noplaygo
PACK_FILES="libSceAgc.sprx libSceAgcDriver.sprx libScePsml.sprx"

say() { printf '[bc5-install] %s\n' "$*"; }
warn() { printf '[bc5-install] WARNING: %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
bad() { printf '[bc5-install] PROBLEM: %s\n' "$*"; PROBLEMS=$((PROBLEMS + 1)); }
die() { printf '[bc5-install] FAILED: %s\n' "$*" >&2; exit 1; }
WARNINGS=0 PROBLEMS=0

in_container() { [ -e /run/.containerenv ] || [ -e /.dockerenv ]; }
CMDLINE=${BC5_CMDLINE:-/proc/cmdline} # tests: another file
karg() { tr ' ' '\n' < "$CMDLINE" | sed -n "s/^$1=//p" | tail -n1; }

# ---- 1. checks ----
checks() {
  local gpu="" d v n gtt vram lim avail
  in_container && die "run this on the host, not inside a container"
  [ "$(id -u)" != 0 ] || die "run this as your own user, not as root"
  for d in /sys/class/drm/card*/device; do
    [ -r "$d/vendor" ] || continue
    [ "$(cat "$d/vendor")" = 0x1002 ] && [ "$(cat "$d/device")" = 0x13fe ] && gpu=$d
  done
  if [ -n "$gpu" ]; then say "GPU: AMD BC-250 (1002:13fe) at $gpu"; else bad "no AMD BC-250 GPU (PCI 1002:13fe) found: BC5 runs on that board only"; fi
  v=$(karg ttm.pages_limit)
  if [ -z "$v" ]; then bad "kernel argument ttm.pages_limit is not set (BC5 needs $PAGES_LIMIT: 13 GiB of GTT); fix: bash $0 kargs, then reboot"
  elif [ "$v" -lt "$PAGES_LIMIT" ]; then warn "ttm.pages_limit=$v is below $PAGES_LIMIT; the second title may run out of GPU memory"
  else say "kernel: ttm.pages_limit=$v"; fi
  v=$(karg udmabuf.size_limit_mb)
  if [ -z "$v" ]; then bad "kernel argument udmabuf.size_limit_mb is not set (BC5 needs $UDMABUF_MB); fix: bash $0 kargs, then reboot"
  elif [ "$v" -lt "$UDMABUF_MB" ]; then warn "udmabuf.size_limit_mb=$v is below $UDMABUF_MB (slower submissions, F124)"
  else say "kernel: udmabuf.size_limit_mb=$v"; fi
  if [ -n "$gpu" ]; then
    gtt=$(( $(cat "$gpu/mem_info_gtt_total" 2> /dev/null || echo 0) / 1048576 ))
    vram=$(( $(cat "$gpu/mem_info_vram_total" 2> /dev/null || echo 0) / 1048576 ))
    say "GPU memory: GTT ${gtt} MiB, VRAM carve-out ${vram} MiB"
    [ "$gtt" -ge 12288 ] || warn "GTT is ${gtt} MiB; with ttm.pages_limit=$PAGES_LIMIT after a reboot it is 13312"
    [ "$vram" -le 1024 ] || warn "the VRAM carve-out is ${vram} MiB; BC5 is tuned for the BIOS's dynamic split with 512 MiB (D8)"
  fi
  if [ -e /dev/udmabuf ]; then
    if [ -w /dev/udmabuf ]; then say "/dev/udmabuf: writable"; else bad "/dev/udmabuf is not writable for $(id -un) (log in on the desktop seat: the uaccess rule gives the seat's user access)"; fi
  else
    bad "no /dev/udmabuf (fix: sudo modprobe udmabuf, and echo udmabuf | sudo tee /etc/modules-load.d/udmabuf.conf)"
  fi
  lim=$(ulimit -l)
  if [ "$lim" != unlimited ] && [ "$lim" -lt 2097152 ]; then
    warn "the locked-memory limit is $lim KiB; games that lock memory get an error (a line '* hard memlock 2147484' and '* soft memlock 2147484' in /etc/security/limits.d/memlock.conf raises it)"
  else say "memlock limit: $lim"; fi
  n=$(nproc)
  [ "$n" -ge 12 ] || warn "$n CPU threads; the BC-250 with the community CPU unlock has 16 (README: Requirements)"
  for t in git distrobox podman; do command -v "$t" > /dev/null || bad "$t is not installed (Bazzite has all three)"; done
  mkdir -p "$WORK"
  avail=$(( $(df --output=avail -B1 "$WORK" | tail -1) / 1073741824 ))
  if [ "$avail" -lt "$MIN_FREE_GB" ]; then bad "only $avail GB free under $WORK; the install needs about $MIN_FREE_GB GB"; else say "free space: $avail GB"; fi
  [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] || warn "no desktop session in this shell (fine over ssh; the shortcut runs on the desktop)"
  say "checks: $PROBLEMS problem(s), $WARNINGS warning(s)"
  [ "$PROBLEMS" = 0 ]
}

# ---- kernel arguments ----
add_kargs() {
  local add=()
  [ -n "$(karg ttm.pages_limit)" ] || add+=("--append-if-missing=ttm.pages_limit=$PAGES_LIMIT")
  [ -n "$(karg udmabuf.size_limit_mb)" ] || add+=("--append-if-missing=udmabuf.size_limit_mb=$UDMABUF_MB")
  [ "${#add[@]}" -gt 0 ] || { say "both kernel arguments are set already"; return 0; }
  if command -v rpm-ostree > /dev/null; then
    say "running: sudo rpm-ostree kargs ${add[*]}"
    sudo rpm-ostree kargs "${add[@]}"
    say "done; reboot, then run bash $0 again"
  else
    say "this system has no rpm-ostree; add these to the kernel command line yourself (GRUB_CMDLINE_LINUX in /etc/default/grub, then regenerate the grub configuration), and reboot:"
    say "  ttm.pages_limit=$PAGES_LIMIT udmabuf.size_limit_mb=$UDMABUF_MB"
  fi
}

# ---- 2. the container ----
container() {
  if distrobox list --no-color 2> /dev/null | awk -F'|' 'NR>1 {gsub(/^ +| +$/, "", $2); print $2}' | grep -qx "$BOX"; then
    say "distrobox '$BOX' exists"
  else
    say "creating distrobox '$BOX' from $IMAGE (downloads the image)"
    distrobox create --yes --name "$BOX" --image "$IMAGE"
    distrobox enter "$BOX" -- true
  fi
}

# ---- 3. the build ----
build() {
  local normal=0 what="the lean emulator"
  [ "$NORMAL" = 1 ] && normal=1 what="the lean and the normal emulator"
  say "building $what and bc5-mount; the first build takes a while (about an hour), log: $WORK/bc5-build.log"
  BC5_SRC=$REPO KYTY_SRC=$KYTY_SRC WORK=$WORK BOX=$BOX BC5_BUILD_MOUNT=1 BC5_BUILD_LEAN=1 BC5_BUILD_NORMAL=$normal \
    bash "$HERE/bc5-build.sh"
  [ -x "$WORK/kytyplus-build-lean/src/kyty_emulator" ] || die "no lean emulator at $WORK/kytyplus-build-lean/src/kyty_emulator"
  [ -x "$WORK/bc5-tools-ubuntu/release/bc5-mount" ] || die "no bc5-mount at $WORK/bc5-tools-ubuntu/release/bc5-mount"
}

# A file into place: unchanged when equal, else the old one is kept as <file>.bak-<time>.
put() {
  local src=$1 dst=$2 mode=$3
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then return 0; fi
  if [ -e "$dst" ]; then cp -p "$dst" "$dst.bak-$TS"; say "kept the old $(basename "$dst") as $dst.bak-$TS"; fi
  install -m "$mode" "$src" "$dst"
  say "installed $dst"
}

# ---- 4. launchers, settings, folders ----
launchers() {
  local f tmp
  mkdir -p "$WORK" "$DATA/games" "$DATA/mnt" "$DATA/cache" "$DATA/captures/faults" "$WORK/menu"
  for f in play-any.sh play-astro.sh play-pkg.sh lean-session.sh pad-volume.sh; do
    put "$LAUNCHERS/$f" "$WORK/$f" 755
  done
  tmp=$(mktemp)
  sed "s#@HOME@#$HOME#g" "$LAUNCHERS/bc5-run.env.in" > "$tmp"
  put "$tmp" "$WORK/bc5-run.env" 644
  rm -f "$tmp"
  if [ ! -e "$WORK/input.cfg" ]; then
    printf '%s\n' "# BC5 input configuration, written by the settings overlay (F2). Hand edits are fine;" \
      "# the grammar and the names are in backend/kytyplus-patches/input.example.cfg." > "$WORK/input.cfg"
    say "installed $WORK/input.cfg"
  fi
  # The second title runs with no learned windows (2026-11-13): an empty, read-only file.
  [ -e "$WORK/direct-learned-none.txt" ] || { : > "$WORK/direct-learned-none.txt"; chmod 444 "$WORK/direct-learned-none.txt"; }
}

# ---- 5. shortcuts ----
desktop_entry() { # name comment env
  printf '%s\n' "[Desktop Entry]" "Type=Application" "Version=1.0" "Name=$1" "Comment=$2" \
    "Exec=/usr/bin/distrobox enter $BOX -- /usr/bin/env $3 $WORK/play-any.sh" \
    "Icon=applications-games" "Terminal=false" "Categories=Game;" "StartupNotify=false"
}
shortcuts() {
  local desk apps tmp d
  desk=${DESKTOP_DIR:-$(xdg-user-dir DESKTOP 2> /dev/null || true)}
  [ -n "$desk" ] && [ "$desk" != "$HOME" ] || desk=$HOME/Desktop
  apps=${APPS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}
  mkdir -p "$desk" "$apps"
  tmp=$(mktemp)
  desktop_entry "BC5 emulator (lean)" "BC5: the emulator built without measurements, with its menu (File > Open game / Install game)" "BC5_LEAN=1" > "$tmp"
  for d in "$desk" "$apps"; do put "$tmp" "$d/BC5 emulator (lean).desktop" 755; done
  if [ "$NORMAL" = 1 ]; then
    desktop_entry "BC5 emulator" "BC5: the emulator with its measurements and logs, with its menu" "BC5_LEAN=0" > "$tmp"
    for d in "$desk" "$apps"; do put "$tmp" "$d/BC5 emulator.desktop" 755; done
  fi
  rm -f "$tmp"
  command -v update-desktop-database > /dev/null && update-desktop-database "$apps" 2> /dev/null || true
}

# ---- the module pack of the second title ----
# From a folder: copied on the host. From an image: the mount runs inside the container (its FUSE mount is seen
# only there), so the copy does too (pack-in).
make_pack() {
  local src=${1:?usage: bc5-install.sh pack <image or folder>}
  if [ -d "$src" ]; then copy_pack "$src/fakelib"; return; fi
  [ -f "$src" ] || die "no such file: $src"
  src=$(cd "$(dirname "$src")" && pwd)/$(basename "$src")
  distrobox enter "$BOX" -- env WORK="$WORK" DATA="$DATA" bash "$HERE/bc5-install.sh" pack-in "$src"
}
copy_pack() {
  local f=$1 m
  for m in $PACK_FILES; do [ -f "$f/$m" ] || die "$f does not hold $PACK_FILES; use a game whose dump has them (ASTRO BOT's does)"; done
  mkdir -p "$PACK"
  for m in $PACK_FILES; do install -m 644 "$f/$m" "$PACK/$m"; done # the image's files are read-only
  say "module pack made in $PACK from $f"
}
pack_in() { # inside the container: mount the image read-only, copy, unmount
  local src=$1 bm=$WORK/bc5-tools-ubuntu/release/bc5-mount mnt pid rc=0
  [ -x "$bm" ] || die "no bc5-mount at $bm (run the full install first)"
  mkdir -p "$DATA/mnt"
  mnt=$(mktemp -d "$DATA/mnt/pack-XXXXXX")
  "$bm" mount "$src" "$mnt" > "$WORK/pack-mount.log" 2>&1 &
  pid=$!
  for _ in $(seq 1 150); do mountpoint -q "$mnt" && break; sleep 0.2; done
  if mountpoint -q "$mnt"; then
    ( copy_pack "$mnt/fakelib" ) || rc=1
    fusermount3 -u "$mnt" || fusermount3 -u -z "$mnt" || true
  else
    say "could not mount $src (see $WORK/pack-mount.log)"; rc=1
  fi
  kill "$pid" 2> /dev/null || true; wait "$pid" 2> /dev/null || true
  rmdir "$mnt" 2> /dev/null || true
  return "$rc"
}

case "${1:-all}" in
  check) checks ;;
  kargs) add_kargs ;;
  pack) shift; make_pack "${1:-}" ;;
  pack-in) shift; pack_in "${1:?}" ;;
  all)
    say "BC5 install $TS: repository $REPO ($(git -C "$REPO" log -1 --format='%h %cs' 2> /dev/null || echo 'not a git clone'))"
    say "== 1. checks"
    checks || [ "${BC5_INSTALL_FORCE:-0}" = 1 ] || die "fix the problems above and run again (BC5_INSTALL_FORCE=1 goes on anyway)"
    say "== 2. build container"
    container
    if [ "${BC5_INSTALL_SKIP_BUILD:-0}" = 1 ]; then say "== 3. build skipped (BC5_INSTALL_SKIP_BUILD=1)"; else say "== 3. build"; build; fi
    say "== 4. launchers and settings"
    launchers
    say "== 5. shortcuts"
    shortcuts
    say "done. Start 'BC5 emulator (lean)' from the desktop or the application menu, then File > Open game... or"
    say "File > Install game... with your own game image (.ffpfsc or .pkg). The second title also needs the module"
    say "pack from ASTRO BOT: it is made by itself once ASTRO BOT is installed, or: bash $0 pack <ASTRO BOT image>."
    ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
