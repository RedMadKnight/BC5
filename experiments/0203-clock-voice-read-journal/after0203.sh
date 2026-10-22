#!/usr/bin/env bash
# BC5 (experiment 0203): after a launch0203.sh session has ended. Puts the maintainer's saves back (the copy
# ab-restore.sh kept at the launch; the session's own saves are kept in turn), and collects into raw/: the play
# log, the pad recording, the journal's frame-profile lines (read with O_DIRECT, so the page cache is left alone)
# and the kernel lines since the launch, and the "apr journal" lines into raw/<tag>-apr-journal.txt.
# usage: after0203.sh <tag>
set -u
TAG=${1:?tag}
E=$HOME/bc5-work/exp0203; R=$E/raw
pgrep -x kyty_emulator > /dev/null && { echo "the emulator still runs: nothing done"; exit 1; }
KEEP=$(sed -n 's/.*(previous saves in \(.*\))$/\1/p' "$R/$TAG-restore.txt")
[ -d "$KEEP" ] || { echo "no kept saves named in $R/$TAG-restore.txt"; exit 1; }
~/bc5-work/exp0196/ab-restore.sh "$KEEP" | tee "$R/$TAG-restore-back.txt"
cp -p ~/bc5-work/play-pkg-last.log "$R/$TAG-play-pkg.log"
grep -a "^apr journal (exp 0203)" "$R/$TAG-play-pkg.log" > "$R/$TAG-apr-journal.txt"  # KYTY_BC5_APR_FILE_JOURNAL lines
cp -p ~/bc5-work/route-record.txt "$R/$TAG-route-record.txt"
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
echo "$J" > "$R/$TAG-journal-path.txt"
dd if="$J" iflag=direct bs=4M 2> /dev/null | grep -a "^frame profile: t \|TIMEOUT\|^fps counter" > "$R/$TAG-frames.txt"
N=$(cat "$R/$TAG-dmesg-before.txt")
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung" > "$R/$TAG-dmesg-after.txt"
LOCK=$HOME/bc5-work/BOX-LOCK
grep -q "^exp 0203 | maintainer play $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
ls -la "$R" | grep " $TAG-"
