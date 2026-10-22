#!/usr/bin/env bash
# Experiment 0199 (prepared, NOT run; GPU, only with the maintainer present, D16: one short run):
# the maintainer's normal shortcut ("BC5 emulator": play-any.sh with the shared binary and the
# launcher's settings) plus BC5_DIRECT_AMM_PRT=1, which maps the title's AMM window
# (0x8000000000 + 64 GiB) as PRT pages at device open and at every reopen (experiment 0102): pages
# the title leaves unbacked read 0 and drop writes instead of having no PTE. Expected: no TCP write
# fault at the title's first-use clears of its sparse UI targets (experiment 0199). The kernel
# baseline is taken first, so the run's amdgpu lines can be told apart afterwards.
set -u
echo "$(date '+%F %T') start, kernel log lines before: $(journalctl -k -b 0 --no-pager 2>/dev/null | wc -l)" >> ~/bc5-work/exp0199/prt-runs.txt
/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_DIRECT_AMM_PRT=1 /home/kjaniszewski/bc5-work/play-any.sh "$@"
echo "$(date '+%F %T') end" >> ~/bc5-work/exp0199/prt-runs.txt
