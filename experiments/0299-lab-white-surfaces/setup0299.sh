#!/usr/bin/env bash
# BC5 experiment 0299: one-time setup of the lab bench (no emulator). The maintainer's live saves are never run on: a
# snapshot of them (checked at the start and end, the restore point if they ever change), and one copy of them as the
# bench's lab save (saves-lab-1001: the newest save is slot 4's autosave of 10:01:03, the lab), which run0299.sh resets
# into a private working directory before each run (exp 0194's scheme: ~/bc5-work/exp0299/wd holds its own _SaveData
# and _SaveData-pkg-play, every other entry of ~/bc5-work is a symlink). The launcher play-pkg-0299.sh is today's
# play-pkg.sh with exactly three changes, made here by sed and shown as a diff: the working directory, its own log
# file, and the bench's input configuration (exp 0194's input-0194.cfg: keyboard layout off for scripted runs).
# usage: setup0299.sh <expected live saves checksum>   (on the box, from SSH; refuses if anything is off)
set -u
E=$HOME/bc5-work/exp0299
REF=$1
cd ~/bc5-work || exit 1
saves() { (cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
pgrep "^kyty_emulator" > /dev/null && { echo "an emulator is running: stop"; exit 1; }
S=$(saves); echo "live saves $S"
[ "$S" = "$REF" ] || { echo "live saves differ from $REF: stop"; exit 1; }
mkdir -p "$E"
[ -e "$E/saves-live-snap" ] || { cp -a _SaveData/PPSA03671 "$E/saves-live-snap" && echo "live snapshot: $(find "$E/saves-live-snap" -type f | wc -l) files"; }
[ -e "$E/saves-lab-1001" ] || { cp -a _SaveData/PPSA03671 "$E/saves-lab-1001" && echo "lab save copy: $(find "$E/saves-lab-1001" -type f | wc -l) files"; }
echo "lab save copy checksum $(cd "$E" && find saves-lab-1001 -type f -exec md5sum {} + | sed 's# saves-lab-1001/# PPSA03671/#' | sort -k2 | md5sum | cut -c1-16)"
mkdir -p "$E/wd/_SaveData" "$E/wd/_SaveData-pkg-play"
shopt -s nullglob dotglob
for f in ~/bc5-work/*; do
  b=$(basename "$f")
  case "$b" in _SaveData|_SaveData-pkg-play|exp0299) continue ;; esac
  [ -e "$E/wd/$b" ] || [ -L "$E/wd/$b" ] || ln -s "$f" "$E/wd/$b"
done
echo "wd: $(find "$E/wd" -maxdepth 1 -type l | wc -l) symlinks, own _SaveData and _SaveData-pkg-play"
sed -e 's#^LOG=~/bc5-work/play-pkg-last.log$#LOG=~/bc5-work/exp0299/play-last.log#' \
    -e 's#^export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0299/wd/_SaveData-pkg-play  \# exp 0299: private#' \
    -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0299/wd  \# exp 0299: the private working directory (its own _SaveData)#' \
    -e 's#^PLAY_ARGS="$PLAY_ARGS --fullscreen"#[ -n "${BC5_0299_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0299_INPUT_CONFIG  \# exp 0299: keyboard layout off for scripted runs\n&#' \
    play-pkg.sh > "$E/play-pkg-0299.sh"
chmod +x "$E/play-pkg-0299.sh"
diff play-pkg.sh "$E/play-pkg-0299.sh" > "$E/play-pkg-0299.diff"
echo "launcher diff: $(grep -c '^>' "$E/play-pkg-0299.diff") lines changed or added (expect 4)"
cat "$E/play-pkg-0299.diff"
grep -q '^cd ~/bc5-work/exp0299/wd' "$E/play-pkg-0299.sh" && grep -q '^LOG=~/bc5-work/exp0299/play-last.log' "$E/play-pkg-0299.sh" || { echo "launcher edit failed: stop"; exit 1; }
md5sum ~/bc5-work/kytyplus-build/src/kyty_emulator | cut -c1-8
