#!/usr/bin/env bash
# Experiment 0439: the second title out (saves kept), the third title (PPSA26344) in, its first runs.
# Runs on the BC-250 host as the maintainer's user, from ~/bc5-work/exp0439/ (a copy of this file).
# Every step writes its output under $E and prints it. Nothing here touches a save, the shared builds,
# the shared launchers or input.cfg / menu/titles/*.
#
#   e0439.sh lock [what] / unlock   BOX-LOCK line "exp0439 ...", taken only when the lock is empty and no emulator runs
#   e0439.sh check2           read-only: the NAS package of the second title, its install, saves, shortcut, cache
#   e0439.sh md5 <file> <expected-md5|md5-file> <tag>
#                             md5 of a file in a systemd --user unit (idle I/O); result in $E/md5-<tag>.txt
#   e0439.sh inventory <tag>  md5 of every save file and kept setting -> $E/saves-<tag>.md5
#   e0439.sh backup           tar of the second title's live saves and its settings into ~/bc5-data/saves/
#   e0439.sh uninstall2       gated: md5-second MATCH, inventory "before", backup present, no emulator, our lock;
#                             bc5-mount uninstall, then the dead shortcut (and the cache if > 1 GiB) to trash
#   e0439.sh check3           read-only: the third title's package (inspect), free space against its unpacked size
#   e0439.sh install3         gated: md5-third MATCH, space; bc5-mount install --verify in a systemd --user unit
#   e0439.sh after3           the installed folder: record, count, size, title id, fakelib modules
#
# BC5_DRY=1 prints the commands of the changing steps instead of running them.
set -euo pipefail
umask 077
E=${E:-$HOME/bc5-work/exp0439}
GAMES=${GAMES:-$HOME/bc5-data/games}
G2=$GAMES/PPSA03671
G3=$GAMES/PPSA26344
NAS=${NAS:-/var/mnt/nas-bc5}
PKG2=${PKG2:-$NAS/game.pkg}
PKG3=${PKG3:-"$NAS/Ghost of Yotei UP9000-PPSA26344_00-GHOST2SHIP000000-A01512-V01512.pkg"}
MD5_3=8d5c6c3cebdd89187cbee34a95aa7d9f
SIZE_3=118467058394
BM=${BM:-$HOME/bc5-work/bc5-tools-ubuntu/release/bc5-mount}
LOCK=${LOCK:-$HOME/bc5-work/BOX-LOCK}
TRASH=${TRASH:-$HOME/bc5-work/trash-20261121}
PULPIT=${PULPIT:-$HOME/Pulpit}
CACHE=${CACHE:-$HOME/bc5-data/cache/bc5-mount}
BACKUP=${BACKUP:-$HOME/bc5-data/saves/PPSA03671-live-saves-20261121.tgz}
# The second title's saves and settings: hashed before and after, never moved or changed.
SAVE_PATHS=("$HOME/bc5-work/_SaveData-pkg-play" "$HOME/bc5-work/_SaveData/PPSA03671" "$HOME/bc5-data/saves" "$HOME/bc5-work/menu/titles/PPSA03671" "$HOME/bc5-work/input.cfg")
# What goes into the tar (the snapshot under ~/bc5-data/saves stays where it is, hashed only).
TAR_PATHS=("bc5-work/_SaveData-pkg-play" "bc5-work/_SaveData/PPSA03671" "bc5-work/menu/titles/PPSA03671" "bc5-work/input.cfg")
mkdir -p "$E"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$E/e0439.log"; }
die() { log "STOP: $*"; exit 1; }
run() { if [ "${BC5_DRY:-0}" = 1 ]; then echo "[dry] $*"; else "$@"; fi; }
emu_running() { pgrep -f '[k]yty_emulator' >/dev/null; }
our_lock() { [ -e "$LOCK" ] && grep -q '^exp0439 ' "$LOCK" 2>/dev/null && ! grep -q '^MAINTAINER PLAYING' "$LOCK"; }
# The lock: one line, taken only when BOX-LOCK is empty or absent; check and write under one flock.
take_lock() {
  exec 9>> "$LOCK.flock"; flock -n 9 || die "lock busy"
  if [ -s "$LOCK" ]; then cat "$LOCK"; die "BOX-LOCK is held"; fi
  emu_running && die "an emulator runs without a lock: he plays"
  printf 'exp0439 %s %s
' "$(date '+%F %T')" "${1:-third title}" > "$LOCK"; log "lock taken: $(cat "$LOCK")"
}
drop_lock() { exec 9>> "$LOCK.flock"; flock 9; our_lock && : > "$LOCK" && log "lock dropped"; }
# The second title's shortcuts: desktop files that start it by name or through its own script.
second_shortcuts() { grep -l -E 'PPSA03671|play-pkg\.sh' "$PULPIT"/*.desktop 2>/dev/null || true; }  # one path a line

case "${1:-}" in
lock) take_lock "${2:-}" ;;
unlock) drop_lock ;;
check2)
  {
    echo "== $(date '+%F %T') check2"
    ls -la "$NAS/"
    echo "-- inspect $PKG2"; "$BM" inspect "$PKG2" || echo "inspect failed: $?"
    echo "-- NAS package size: $(stat -c %s "$PKG2")"
    echo "-- md5 files on the NAS:"; ls -la "$NAS"/*.md5 2>/dev/null || echo "(none)"
    for f in "$NAS"/*.md5; do [ -f "$f" ] && { echo "$f:"; head -c 400 "$f"; echo; }; done
    echo "-- install record (head):"; head -c 600 "$G2/.bc5-install.json"; echo
    echo "-- installed: $(find "$G2" -type f ! -name .bc5-install.json | wc -l) files, $(find "$G2" -type f ! -name .bc5-install.json -printf '%s\n' | awk '{s+=$1} END {print s}') bytes"
    echo "-- files newer than the record (not from the package?):"; find "$G2" -newer "$G2/.bc5-install.json" ! -type d | head -50
    echo "-- dry uninstall:"; "$BM" uninstall "$G2" --games "$GAMES" --dry-run || echo "dry-run refused: $?"
    echo "-- df:"; df -B1 /var "$GAMES"
    echo "-- saves and settings:"
    for p in "${SAVE_PATHS[@]}"; do [ -e "$p" ] && du -sh "$p" && find "$p" -type f | wc -l || echo "missing: $p"; done
    ls -la "$HOME/bc5-data/saves/" 2>/dev/null
    echo "-- other save dirs that name the title:"; find "$HOME/bc5-work" "$HOME/bc5-data" -maxdepth 3 \( -iname '*SaveData*' -o -iname '*PPSA03671*' \) 2>/dev/null | grep -v "^$G2" | head -40
    echo "-- shortcuts:"; second_shortcuts | while IFS= read -r f; do echo "$f"; grep -E '^(Name|Exec)=' "$f"; done
    echo "-- bc5-mount cache:"; du -sb "$CACHE" 2>/dev/null || echo "(none)"
    echo "-- emulator running: $(emu_running && echo yes || echo no)"
  } 2>&1 | tee "$E/check2.txt"
  ;;
md5)
  f=$2 want=$3 tag=$4 out=$E/md5-$4.txt
  [ -f "$want" ] && want=$(awk '{print $1; exit}' "$want")
  [[ $want =~ ^[0-9a-f]{32}$ ]] || die "no expected md5 for $tag"
  rm -f "$out"
  log "md5 $tag of $f (expected $want) in unit bc5-0439-md5-$tag"
  run systemd-run --user --collect --unit="bc5-0439-md5-$tag" -p IOSchedulingClass=idle -p Nice=10 \
    /usr/bin/bash -c 'got=$(md5sum "$1" | cut -d" " -f1); if [ "$got" = "$2" ]; then r=MATCH; else r=MISMATCH; fi; printf "%s %s got %s expected %s %s\n" "$(date "+%F %T")" "$r" "$got" "$2" "$1" > "$3"' _ "$f" "$want" "$out"
  ;;
inventory)
  tag=$2 out=$E/saves-$2.md5
  : > "$out"
  for p in "${SAVE_PATHS[@]}"; do
    [ -e "$p" ] || { echo "missing $p" >> "$out"; continue; }
    find "$p" -type f ! -path "$BACKUP" -print0 | sort -z | xargs -0 -r md5sum >> "$out"
  done
  log "inventory $tag: $(grep -c . "$out") lines in $out"
  ;;
backup)
  [ -e "$BACKUP" ] && die "$BACKUP already there"
  have=(); for p in "${TAR_PATHS[@]}"; do [ -e "$HOME/$p" ] && have+=("$p") || log "backup: no $p"; done
  [ ${#have[@]} -gt 0 ] || die "nothing to back up"
  run tar -C "$HOME" -czf "$BACKUP" "${have[@]}"
  [ "${BC5_DRY:-0}" = 1 ] || { tar -tzf "$BACKUP" | wc -l; ls -la "$BACKUP"; }
  log "backup $BACKUP"
  ;;
uninstall2)
  grep -q ' MATCH ' "$E/md5-second.txt" 2>/dev/null || die "the NAS package's md5 is not a MATCH ($E/md5-second.txt)"
  "$BM" inspect "$PKG2" | grep -q 'title id: *PPSA03671' || die "the NAS package is not PPSA03671"
  [ -s "$E/saves-before.md5" ] || die "no inventory 'before'"
  [ -s "$BACKUP" ] || [ "${BC5_DRY:-0}" = 1 ] || die "no backup $BACKUP"
  # Top, 2026-11-21: the tar's file count must equal the inventory's files under the tarred paths.
  if [ "${BC5_DRY:-0}" != 1 ]; then
    in_tar=$(tar -tzf "$BACKUP" | grep -vc '/$' || true)
    in_inv=0
    for p in "${TAR_PATHS[@]}"; do
      n=$(awk -v q="$HOME/$p" '{f = substr($0, 35)} f == q || index(f, q "/") == 1 {c++} END {print c + 0}' "$E/saves-before.md5")
      in_inv=$((in_inv + n))
    done
    log "backup check: $in_tar files in the tar, $in_inv in the inventory under the tarred paths"
    [ "$in_tar" = "$in_inv" ] || die "the tar's file count ($in_tar) differs from the inventory ($in_inv)"
  fi
  emu_running && die "an emulator is running"
  our_lock || die "BOX-LOCK is not ours"
  log "uninstall $G2"
  run "$BM" uninstall "$G2" --games "$GAMES" 2>&1 | tee -a "$E/e0439.log"
  run mkdir -p "$TRASH/pulpit"
  second_shortcuts | while IFS= read -r f; do log "shortcut $f -> $TRASH/pulpit/"; run mv -n "$f" "$TRASH/pulpit/"; done
  c=$(du -sb "$CACHE" 2>/dev/null | cut -f1); c=${c:-0}
  log "bc5-mount cache: $c bytes"
  if [ "$c" -gt 1073741824 ]; then run mv -n "$CACHE" "$TRASH/bc5-mount-cache"; log "cache -> $TRASH/bc5-mount-cache"; fi
  "$0" inventory after
  if diff "$E/saves-before.md5" "$E/saves-after.md5" > "$E/saves-diff.txt"; then log "saves unchanged"; else log "SAVES DIFFER: $E/saves-diff.txt"; fi
  df -B1 /var | tee -a "$E/e0439.log"
  ;;
check3)
  {
    echo "== $(date '+%F %T') check3"
    ls -la "$PKG3"
    s=$(stat -c %s "$PKG3"); echo "size $s (expected $SIZE_3): $([ "$s" = "$SIZE_3" ] && echo OK || echo DIFFERENT)"
    "$BM" inspect "$PKG3" || echo "inspect failed: $?"
    df -B1 /var "$GAMES"
  } 2>&1 | tee "$E/check3.txt"
  ;;
install3)
  grep -q ' MATCH ' "$E/md5-third.txt" 2>/dev/null || die "the third title's md5 is not a MATCH"
  grep -q 'title id: *PPSA26344' "$E/check3.txt" || die "check3 did not read PPSA26344"
  need=$(sed -n 's/^files: .* directories, \([0-9]*\) bytes$/\1/p' "$E/check3.txt" | head -n1)
  [ -n "$need" ] || die "no unpacked size in check3.txt"
  free=$(df -B1 --output=avail "$GAMES" | tail -n1 | tr -d ' ')
  [ "$free" -gt $((need + 20 * 1024 * 1024 * 1024)) ] || die "free $free < unpacked $need + 20 GiB"
  [ -e "$G3" ] && die "$G3 exists (resume by hand with --resume)"
  emu_running && die "an emulator is running"
  our_lock || die "BOX-LOCK is not ours"
  log "install $PKG3 -> $G3 (need $need, free $free)"
  run systemd-run --user --collect --unit=bc5-0439-install3 -p IOSchedulingClass=idle -p Nice=10 \
    /usr/bin/bash -c '"$1" install --verify "$2" "$3" > "$4" 2>&1; echo "exit $?" >> "$4"' _ "$BM" "$PKG3" "$G3" "$E/install3.log"
  ;;
after3)
  {
    echo "== $(date '+%F %T') after3"
    tail -n 5 "$E/install3.log"
    head -c 400 "$G3/.bc5-install.json"; echo
    echo "files $(find "$G3" -type f | wc -l), $(du -sb "$G3" | cut -f1) bytes"
    sed -n 's/.*"titleId" *: *"\([A-Za-z0-9]*\)".*/title id \1/p' "$G3/sce_sys/param.json" | head -n1
    echo "-- fakelib:"; ls "$G3/fakelib" 2>/dev/null || echo "(no fakelib)"
    for m in libSceAgc libSceAgcDriver libScePsml; do [ -f "$G3/fakelib/$m.sprx" ] && echo "has $m" || echo "lacks $m"; done
    df -B1 /var
  } 2>&1 | tee "$E/after3.txt"
  ;;
*) sed -n '2,20p' "$0"; exit 2 ;;
esac
