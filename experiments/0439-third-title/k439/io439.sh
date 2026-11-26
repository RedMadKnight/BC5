#!/usr/bin/env bash
# BC5 exp 0439 (tag io439, 11-25, the top session's step 2: where the I/O pressure comes from). Every IO_EVERY s (5)
# while an emulator runs, one line: time, the emulator's /proc/<pid>/io (rchar wchar read_bytes write_bytes, cumulative),
# meminfo Dirty and Writeback (kB), IO and memory PSI full avg10, and the sizes (bytes) of what the run writes: the
# capture's journal (newest ~/bc5-data/captures/play-*/gc/direct.log), ~/bc5-work/play-last.log and play-lean-last.log,
# the frame dump directory, the memory samplers. At the start and every 60 s: the emulator's open regular files outside
# /proc and /dev with the mount they live on (findmnt -T), for the game files' source.
#   io439.sh <out file>
set -u
O=${1:?out}; EVERY=${IO_EVERY:-5}
t=0; until p=$(pgrep -o "^kyty_emulator") || [ $t -gt 600 ]; do sleep 0.5; t=$((t + 1)); done
[ -n "${p:-}" ] || exit 1
sz() { stat -Lc %s "$1" 2> /dev/null || echo 0; }
n=0
{
echo "# io439 pid $p every $EVERY s: time rchar wchar read_bytes write_bytes dirty_kB writeback_kB io_full10 mem_full10 journal_B play_last_B play_lean_B frames_B memsample_B"
while kill -0 "$p" 2> /dev/null; do
    io=$(awk '/^(rchar|wchar|read_bytes|write_bytes):/ {printf "%s ", $2}' "/proc/$p/io" 2> /dev/null)
    dw=$(awk '/^Dirty:|^Writeback:/ {printf "%s ", $2}' /proc/meminfo)
    iof=$(awk '/^full/ {split($2, a, "="); print a[2]}' /proc/pressure/io); mf=$(awk '/^full/ {split($2, a, "="); print a[2]}' /proc/pressure/memory)
    j=$(ls -td "$HOME"/bc5-data/captures/play-*/gc/direct.log 2> /dev/null | head -1)
    echo "$(date +%T) $io$dw$iof $mf $(sz "$j") $(sz "$HOME/bc5-work/play-last.log") $(sz "$HOME/bc5-work/play-lean-last.log") $(du -sb "$HOME/bc5-data/priv/frames" 2> /dev/null | cut -f1) $(du -sb "$HOME/bc5-data/captures/memsample" 2> /dev/null | cut -f1)"
    if [ $((n % (60 / EVERY))) = 0 ]; then
        for fd in /proc/$p/fd/*; do l=$(readlink "$fd" 2> /dev/null) || continue; case $l in /proc/*|/dev/*|/memfd:*|/dmabuf*|socket:*|pipe:*|anon_inode:*) continue ;; esac; [ -f "$l" ] && echo "#   open $(findmnt -no SOURCE,TARGET -T "$l" | tr -s ' ' ':') $(stat -Lc %s "$l") $l"; done | sort -u | head -40
    fi
    n=$((n + 1)); sleep "$EVERY"
done
} > "$O" 2>&1
