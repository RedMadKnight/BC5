#!/usr/bin/env bash
# BC5 exp 0412 (README section 43): the LEAN play of the second title, beside the normal shortcut (the maintainer,
# 2026-11-12: "zbuduj wersje obok - lean - ... lacznie z przelacznikami i martwym kodem oraz wylacz jeszcze sledzenia").
#   - the binary is bin-lean/kyty_emulator (mk0412L.sh: g412d's unit + the zero skip's poll only, compiled with BC5_LEAN:
#     no journal, traces, tallies, frame profile; none of this experiment's catchers and counters);
#   - the launcher is play-pkg-0412-lean.sh (mklean0412.py: play-pkg-0412.sh with the lean binary and its BC5_LEAN branch
#     open): no direct.log, no timing, no frame profile, no FPS counter, audio trace, measure lines, input recorder or
#     timeout probe; the emulator's output goes nowhere;
#   - the words are arm fast7's since 2026-11-12 01:35 (fast5's own words; fast6 with the release at 10 s hung the GPU in its check run) WITHOUT the five that only write or count:
#     BC5_GUARD_LEDGER, BC5_DIRECT_TABLE_CATCHER, KYTY_BC5_EVENT_PENDING_LOG, BC5_DIRECT_RESET_LABEL_JOURNAL,
#     BC5_DIRECT_JOURNAL_QUIET, and without BC5_DIRECT_ACB_INHERIT=journal (mode 1 of acb_inherit_mode(): journal only);
#     plus BC5_LEAN=1, BC5_LOGGING=0 (the logging switch of the objects that are not built lean) and KYTY_BC5_MANGOHUD=0;
#   - beside the emulator NOTHING runs: no sampler, no catcher's sampler, no hard stop. The fuse stays (fuse0412.sh:
#     a memory limit on the container's cgroup, set once; it measures nothing): without it a run past the wall takes
#     the box down instead of the emulator.
# What is NOT lean here, said plainly: e8's other 47 private objects and the shared objects are the normal builds
# (their traces are switched off at run time by BC5_LOGGING=0, not compiled out), and the unit still carries the
# switches of earlier experiments.
# usage: play-lean-0412.sh [dry|words]
set -u
E=$HOME/bc5-work/exp0412; BIN=$E/bin-lean/kyty_emulator; L=$E/play-pkg-0412-lean.sh; F=$E/fuse0412.sh; FLOG=$E/fuse.log
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pinned() { [ "$(m "$E/$1")" = "$(awk -v f="$1" '$2 == f { print $1 }' "$2" 2> /dev/null)" ]; }
pinned bin-lean/kyty_emulator "$E/built-lean.md5" || { say "0412 lean: $BIN is not the build in built-lean.md5; not started"; exit 1; }
pinned play-pkg-0412-lean.sh "$E/built-lean.md5" || { say "0412 lean: $L is not the launcher in built-lean.md5; not started"; exit 1; }
grep -q '^ulimit -c 0' "$L" || { say "0412 lean: $L does not set ulimit -c 0; not started"; exit 1; }
WORDS=()
while IFS= read -r w; do
  case "$w" in
    '' | BC5_GUARD_LEDGER=* | BC5_DIRECT_TABLE_CATCHER=* | KYTY_BC5_EVENT_PENDING_LOG=* | BC5_DIRECT_RESET_LABEL_JOURNAL=* | BC5_DIRECT_JOURNAL_QUIET=* | BC5_DIRECT_ACB_INHERIT=journal) ;;
    *=*) WORDS+=("$w") ;;
    *) say "0412 lean: a word of arm fast7 is not KEY=VALUE ($w); not started"; exit 1 ;;
  esac
done < <(/usr/bin/bash "$E/play-guard-0412.sh" fast7 words 2> /dev/null)
[ "${#WORDS[@]}" = 74 ] || { say "0412 lean: ${#WORDS[@]} words, not fast7's 80 less 6; not started"; exit 1; }
WORDS+=(BC5_LEAN=1 BC5_LOGGING=0 KYTY_BC5_MANGOHUD=0)
case "${1:-}" in
  words) printf '%s\n' "${WORDS[@]}"; exit 0 ;;
  dry) echo "dry: binary $(m "$BIN"), launcher $(m "$L"), ${#WORDS[@]} words, fuse $([ -x "$F" ] || [ -f "$F" ] && echo "13000 2048" || echo "MISSING"), nothing beside the emulator"; exit 0 ;;
  '') ;;
  *) echo "usage: play-lean-0412.sh [dry|words]"; exit 1 ;;
esac
pgrep '^kyty_emulator' > /dev/null && { say "0412 lean: an emulator runs already; not started"; exit 1; }
if pinned fuse0412.sh "$E/tools.md5"; then
  /usr/bin/bash "$F" restore "$FLOG"
  nohup /usr/bin/bash "$F" set 13000 2048 "$FLOG" > /dev/null 2>&1 < /dev/null &
else
  say "0412 lean: the fuse $F is not the installed one; playing without it"
fi
/usr/bin/distrobox enter ubuntu -- /usr/bin/bash -c 'ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"' lean0412 "${WORDS[@]}" "$L"
