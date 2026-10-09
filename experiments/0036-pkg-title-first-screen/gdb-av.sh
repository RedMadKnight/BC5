#!/usr/bin/env bash
# BC5: run the emulator under gdb, passing its own signals, with a breakpoint on the host's
# "Access violation" exit (runtimeLinker.cpp), then run the commands in GDB_CMDS there.
# Output: ~/bc5-work/gdb-av.txt
OUT=$HOME/bc5-work/gdb-av.txt
CMDS=${GDB_CMDS:-$HOME/bc5-work/gdb-av-cmds.txt}
exec gdb -q -batch \
  -ex "set pagination off" \
  -ex "set debuginfod enabled off" \
  -ex "handle SIGSEGV nostop noprint pass" \
  -ex "handle SIGBUS nostop noprint pass" \
  -ex "handle SIGILL nostop noprint pass" \
  -ex "handle SIGUSR1 nostop noprint pass" \
  -ex "handle SIGUSR2 nostop noprint pass" \
  -ex "handle SIGPIPE nostop noprint pass" \
  -ex "handle SIG32 nostop noprint pass" \
  -ex "handle SIG33 nostop noprint pass" \
  -ex "handle SIG34 nostop noprint pass" \
  -ex "break runtimeLinker.cpp:1097" \
  -ex run \
  -x "$CMDS" \
  --args "$@" > "$OUT" 2>&1
