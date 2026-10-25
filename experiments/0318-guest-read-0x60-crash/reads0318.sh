#!/usr/bin/env bash
# BC5 experiment 0318, R1: read-only. What the 2026-10-25 16:33:22 crash log of the maintainer's session says beyond
# the register dump: whether logging was on (the exception handler's code bytes, module, guest stack trace, register
# qwords and the last stubbed imports go out through LOGF, which BC5_LOGGING=0 / the quiet launcher silences), where
# the buffered "AJM codec=" stdout line sits, and the crash block itself. Targeted greps of one log (~MB), output
# a few KB; nothing written. Stops at once if any emulator runs.
# usage: reads0318.sh [log] [crash line]   (on the box)
set -u
L=${1:-$HOME/bc5-work/exp0315/play-try2.log}
C=${2:-18580}
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: no reads"; exit 1; }
[ -r "$L" ] || { echo "no $L"; exit 1; }
echo "== $(date '+%F %T') $L: $(wc -l < "$L") lines, $(stat -c '%s bytes, modified %y' "$L" | cut -c1-60)"
echo "== header (launcher, binary, logging switch):"
head -60 "$L" | grep -a -n '^== \|BC5_LOGGING\|BC5_EMU\|KYTY_BC5_AT9\|LEAN\|quiet' | cut -c1-200
echo "== logging switched in the session (menu or environment):"
grep -a -n -m5 'logging off\|Logging off\|logging on\|Bc5SetLogging\|BC5_LOGGING' "$L" | cut -c1-200
echo "== the AJM stdout line(s):"
grep -a -n 'AJM codec=\|AJM unsupported' "$L" | head -5
echo "== unresolved imports called, and the handler's last-stubbed list:"
grep -a -n 'Unresolved import stub called\|recent stubbed import\|Late-resolved import' "$L" | tail -15 | cut -c1-220
echo "== the exception handler's LOGF diagnostics (present only with logging on):"
grep -a -n 'kyty_exception_handler\|exception module\|^code-32\|^code:\|^exception: \|^regs: \|^stack:\|Stack trace \[thread\|off=.*,\|guest r.. = \|guest r..\[0\] code\|stack\[[0-9]*\] code\|host-pointer leak' "$L" | tail -70 | cut -c1-260
echo "== lines $((C - 40))..$((C + 25)):"
sed -n "$((C - 40)),$((C + 25))p" "$L" | cut -c1-240
