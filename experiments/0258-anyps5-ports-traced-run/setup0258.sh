#!/usr/bin/env bash
# BC5 experiment 0258: prepare a private working directory for the traced save/list/delete runs of the
# second title, as exp 0194's bench does. Nothing here touches the live saves (~/bc5-work/_SaveData) or
# the shared launchers; everything is created under ~/bc5-work/exp0258.
#   wd/                 private working directory: its _SaveData holds a copy of the maintainer's lake save
#                       (~/bc5-work/saves-lake-1153), every other entry of ~/bc5-work is a symlink
#   play-pkg-0258.sh    exp0194/play-pkg-0194.sh with exp0194 -> exp0258, its own log, and KYTY_BC5_SAVE_TRACE=1 added
# Idempotent. Run on the box: bash ~/bc5-work/exp0258/setup0258.sh
set -u
cd ~/bc5-work || exit 1
E=~/bc5-work/exp0258
mkdir -p "$E/wd"
# the working directory: symlinks for everything but _SaveData and the private pkg save dir
for p in ~/bc5-work/* ~/bc5-work/.[!.]*; do
  n=$(basename "$p")
  case "$n" in _SaveData|_SaveData-pkg-play|exp0258|BOX-LOCK|BOX-QUEUE) continue ;; esac
  [ -e "$E/wd/$n" ] || ln -s "$p" "$E/wd/$n"
done
mkdir -p "$E/wd/_SaveData-pkg-play"
# the private save copy (reset to the lake save when RESET=1 or absent)
W=$E/wd/_SaveData/PPSA03671
if [ "${RESET:-0}" = 1 ] || [ ! -d "$W" ]; then
  rm -rf "$W"; mkdir -p "$E/wd/_SaveData"; cp -a ~/bc5-work/saves-lake-1153 "$W"
  echo "private save copy reset to saves-lake-1153"
fi
echo "private copy: $(find "$W" -maxdepth 1 -mindepth 1 | wc -l) entries: $(ls "$W" | tr '\n' ' ')"
# the launcher copy
sed -e 's|exp0194|exp0258|g' \
    -e '/^export KYTY_BC5_SAVEDATA_DIR=/a export KYTY_BC5_SAVE_TRACE=1  # exp 0258: the save-data trace on (the bench launcher has no such line)' \
    -e 's|^LOG=.*play-pkg-last.log|LOG=~/bc5-work/exp0258/play-pkg-last.log|' \
    ~/bc5-work/exp0194/play-pkg-0194.sh > "$E/play-pkg-0258.sh"
chmod +x "$E/play-pkg-0258.sh"
echo "launcher checks:"
grep -n "KYTY_BC5_SAVE_TRACE\|^LOG=\|^cd \|KYTY_BC5_SAVEDATA_DIR=\|INPUT_CONFIG" "$E/play-pkg-0258.sh" | cut -c1-160
grep -q "^export KYTY_BC5_SAVE_TRACE=1" "$E/play-pkg-0258.sh" || echo "WARNING: the save trace line was not added"
grep -q "^cd ~/bc5-work/exp0258/wd" "$E/play-pkg-0258.sh" || echo "WARNING: the launcher does not cd into the private working directory"
echo "setup done"
