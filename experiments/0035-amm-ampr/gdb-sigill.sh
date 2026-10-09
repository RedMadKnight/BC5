#!/usr/bin/env bash
# BC5: run the emulator under gdb, passing the signals it handles itself, stopping on SIGILL and
# printing what GDB_CMDS (a file of gdb commands) asks. Output: ~/bc5-work/gdb-sigill.txt
OUT=$HOME/bc5-work/gdb-sigill.txt
CMDS=${GDB_CMDS:-$HOME/bc5-work/gdb-cmds.txt}
exec gdb -q -batch \
  -ex "set pagination off" \
  -ex "set debuginfod enabled off" \
  -ex "handle SIGSEGV nostop noprint pass" \
  -ex "handle SIGBUS nostop noprint pass" \
  -ex "handle SIGUSR1 nostop noprint pass" \
  -ex "handle SIGUSR2 nostop noprint pass" \
  -ex "handle SIGPIPE nostop noprint pass" \
  -ex "handle SIG32 nostop noprint pass" \
  -ex "handle SIG33 nostop noprint pass" \
  -ex "handle SIG34 nostop noprint pass" \
  -ex "handle SIGILL stop print" \
  -ex run \
  -x "$CMDS" \
  --args "$@" > "$OUT" 2>&1
