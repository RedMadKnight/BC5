# BC5 exp 0381: test build 2's rollback, on a go for this step. Sent after pathcheck0381tb2.inc and lock0381tb2.inc, with TB2_TOKEN set (tb2run0381.sh recover).
# Renames only: nothing is deleted, nothing shared and no live save is touched, and it never signals a process. It runs under the series' exact lock line. An empty lock is
# claimed first, under a new token; any other line stops it, untouched. Each target must be exactly itself under the canonical home, hold no link and no mount, and no emulator, build or cap may run.
ROLLBACK_TARGETS="bc5-work/exp0381/tb2 bc5-work/exp0381/backend-build-tb2 bc5-work/exp0381/in-tb2 bc5-work/exp0381/saves-sample bc5-work/exp0381/saves-sample.tmp"
STAMP=$(date +%Y%m%d-%H%M%S)
ROOT=$(readlink -f "${TB2_ROOT:-$HOME}")
idle() {
    pgrep '^kyty_emulator' > /dev/null && { echo "TB2 STOP: an emulator runs"; exit 3; }
    pgrep -x 'ninja|cmake' > /dev/null && { echo "TB2 STOP: a build runs"; exit 3; }
    pgrep -f 'boxcap0381' > /dev/null && { echo "TB2 STOP: the cap still runs"; exit 3; }
    return 0
}
check() {
    local n a
    for n in $ROLLBACK_TARGETS; do
        a=$ROOT/$n
        [ -e "$a" ] || [ -L "$a" ] || continue
        tb2_private "$n" tree || { echo "TB2 STOP: $n is not itself, or holds a link"; exit 5; }
        [ "$(find "$a" | wc -l)" = "$(find "$a" -xdev | wc -l)" ] || { echo "TB2 STOP: $n holds a mount"; exit 5; }
        [ ! -e "$a.rolledback-$STAMP" ] && [ ! -L "$a.rolledback-$STAMP" ] || { echo "TB2 STOP: $n.rolledback-$STAMP exists"; exit 5; }
    done
}
idle
trap tb2_held_release EXIT
if tb2_own_q; then
    TB2_HELD=1
elif [ ! -L "$TB2_LOCK" ] && [ ! -s "$TB2_LOCK" ]; then
    TB2_TOKEN=$TB2_TOKEN-recovery-$STAMP; TB2_LINE="top exp 0381 | test build 2 | token $TB2_TOKEN"
    tb2_claim
else
    echo "TB2 STOP: the lock is not ours: $(cat "$TB2_LOCK" 2> /dev/null)"; exit 4
fi
tb2_own
idle
check
tb2_queue "$TB2_LINE: rollback, rename only | $(date '+%F %T')"
for n in $ROLLBACK_TARGETS; do
    a=$ROOT/$n
    [ -e "$a" ] || continue
    tb2_hook before-rename
    tb2_own; idle; check
    mv -T -n "$a" "$a.rolledback-$STAMP" && [ ! -e "$a" ] || { echo "TB2 STOP: the rename of $n failed"; exit 5; }
    echo "renamed $n"
done
tb2_own
tb2_queue "$TB2_LINE: rollback done | $(date '+%F %T')"
