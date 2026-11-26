#!/usr/bin/env bash
# BC5 exp 0439 (tag id439): the title-free GPU tests of the clean-boot plan (the top session, 11-22 ~07:40), one case per
# call, each in its own unit: dispatch-min (backend/experiments/dispatch-min, extended with --indirect/--waves-limit/
# --two-rings) built in the ubuntu distrobox, on compute ring 0 (and 1). CLAUDE.md hard rule 5: --submit can hang or
# reset the machine; only in TOP's slot on a clean boot, gate first (k439/gate439.sh), one case, no chain.
#   id439.sh <case>    step 3 (expected to pass): sync      = async-sync, limit 0
#                                                  sync7d    = async-sync, limit 0x7d
#                                                  gdssync   = the title's GDS path (fill GDS, copy GDS -> memory
#                                                              with control 0x20306000), the CP_SYNC wait, the dispatch
#                      step 5 (may hang):          zero      = x = 0, no copy
#                                                  async     = the copy without CP_SYNC, at once the indirect dispatch
#                                                  async7d   = the same, limit 0x7d (the title's)
#                                                  gds       = the GDS path without the wait, limit 0x7d
#                                                  two       = async-sync on comp rings 0 and 1 at once, limit 0x7d
#                      step 5, last (ends with a kernel reset by design: ring A's program never ends):
#                                                  endless   = ring 0: 4096 groups of an endless program under limit
#                                                              0x7d; ring 1 at the same time: async-sync (the second
#                                                              stuck queue's shape: does ring 1's dispatch launch?)
#                                                  endless0  = the same with ring 0's limit 0
# Start: systemd-run --user --unit=id439-<case> -p RuntimeMaxSec=120 --working-directory=$HOME/bc5-work/exp0439 \
#        bash k439/id439.sh <case>
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
C=${1:?case}
case "$C" in
    sync) A="--indirect async-sync" ;;
    sync7d) A="--indirect async-sync --waves-limit 7d" ;;
    zero) A="--indirect zero" ;;
    async) A="--indirect async" ;;
    async7d) A="--indirect async --waves-limit 7d" ;;
    two) A="--indirect async-sync --waves-limit 7d --two-rings" ;;
    gdssync) A="--indirect gds-sync --waves-limit 7d" ;;
    gds) A="--indirect gds --waves-limit 7d" ;;
    endless) A="--indirect async-sync --endless-a 4096 --endless-limit 7d" ;;
    endless0) A="--indirect async-sync --endless-a 4096 --endless-limit 0" ;;
    *) echo "case is sync, sync7d, gdssync, zero, async, async7d, gds, two, endless or endless0"; exit 1 ;;
esac
ulimit -c 0
echo "== id439 $C: $(date '+%F %T'), kernel $(uname -r), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up $(cut -d' ' -f1 /proc/uptime) s"
bash k439/gate439.sh || exit $?
BIN=$HOME/bc5-work/exp0439/k439/id439/dispatch-min-id439
[ -x "$BIN" ] || { echo "no $BIN"; exit 1; }
pgrep "^kyty_emulator" > /dev/null && { echo "REFUSED: an emulator runs"; exit 1; }
distrobox enter ubuntu -- "$BIN" --submit --ip compute --ring 0 --bytes 16384 $A 2>&1
echo "== exit $?; kernel lines after it:"
sleep 3
bash k439/gate439.sh
