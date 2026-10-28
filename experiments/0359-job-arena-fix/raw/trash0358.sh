#!/usr/bin/env bash
# BC5 experiment 0359: the test 0358 desktop shortcut goes to the desktop's trash folder (KDE's
# ~/.local/share/Trash, with the .trashinfo the file manager expects), replaced by the test 0359 shortcut.
# Nothing else is touched (the 0358 binaries, logs and launchers stay under ~/bc5-work/exp0358).
# usage: trash0358.sh   (on the box)
set -u
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
D="$DESK/BC5 emulator (test 0358).desktop"
T=$HOME/.local/share/Trash
[ -f "$D" ] || { echo "no $D (already gone)"; exit 0; }
mkdir -p "$T/files" "$T/info"
N="BC5 emulator (test 0358).desktop"; k=0
while [ -e "$T/files/$N" ]; do k=$((k + 1)); N="BC5 emulator (test 0358) ($k).desktop"; done
printf '[Trash Info]\nPath=%s\nDeletionDate=%s\n' "$(printf '%s' "$D" | sed 's/ /%20/g; s/(/%28/g; s/)/%29/g')" "$(date +%Y-%m-%dT%H:%M:%S)" > "$T/info/$N.trashinfo"
mv "$D" "$T/files/$N" && echo "moved to the trash: $T/files/$N"
