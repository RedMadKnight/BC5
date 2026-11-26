# BC5 exp 0439: gdb's batch file for the SIGFPE run (play439.sh P439_GDB). The emulator's own fault handling uses SIGSEGV,
# SIGBUS, SIGILL (KytyPlus f266548 src/common/hostException.cpp), SIGUSR1 and SIGRTMIN+3 (libKernel.cpp
# thread signals), SIGXCPU (pthread.cpp, RLIMIT_RTTIME): all passed silently; only SIGFPE stops. SIGTRAP keeps gdb's
# default: gdb's own breakpoints use it (passing it killed the emulator at start, 22:48:40); the trap log is off here.
set debuginfod enabled off
set pagination off
set confirm off
set print thread-events off
set width 0
handle SIGSEGV nostop noprint pass
handle SIGBUS nostop noprint pass
handle SIGILL nostop noprint pass
handle SIGUSR1 nostop noprint pass
handle SIGUSR2 nostop noprint pass
handle SIGXCPU nostop noprint pass
handle SIGPIPE nostop noprint pass
handle SIGCHLD nostop noprint pass
handle SIG32 SIG33 SIG34 SIG35 SIG36 SIG37 SIG38 SIG39 SIG40 nostop noprint pass
handle SIGFPE stop print nopass
run
echo \n=== fpe439: the stop ===\n
info program
echo \n=== fpe439: the thread ===\n
thread
echo \n=== fpe439: pc ===\n
p/x $pc
info symbol $pc
echo \n=== fpe439: code at pc ===\n
x/12i $pc
x/48xb $pc-24
echo \n=== fpe439: registers ===\n
info registers
echo \n=== fpe439: the object at r14, 0x400 bytes ===\n
x/256xw $r14
echo \n=== fpe439: code before pc (bytes) ===\n
x/256xb $pc-256
echo \n=== fpe439: instructions from pc-0x100 (gdb's guess, may start misaligned) ===\n
x/72i $pc-0x100
echo \n=== fpe439: the stack's top 0x200 bytes ===\n
x/64gx $rsp
echo \n=== fpe439: stack words that point into the eboot (0x900000000-0x901780000) ===\n
python
import gdb
inf = gdb.selected_inferior()
for reg in ("rsp", "rbp"):
    base = int(gdb.parse_and_eval("$" + reg))
    try:
        m = inf.read_memory(base, 0x400 if reg == "rsp" else 0x100).tobytes()
    except gdb.MemoryError:
        print("%s: unreadable" % reg)
        continue
    for i in range(0, len(m), 8):
        v = int.from_bytes(m[i:i + 8], "little")
        if 0x900000000 <= v < 0x901780000:
            print("%s+0x%03x: 0x%x = eboot+0x%x" % (reg, i, v, v - 0x900000000))
print("rbp chain:")
rbp = int(gdb.parse_and_eval("$rbp"))
for k in range(16):
    try:
        m = inf.read_memory(rbp, 16).tobytes()
    except gdb.MemoryError:
        break
    nxt, ret = int.from_bytes(m[0:8], "little"), int.from_bytes(m[8:16], "little")
    tag = ("eboot+0x%x" % (ret - 0x900000000)) if 0x900000000 <= ret < 0x901780000 else "outside the eboot"
    print("  frame %d: rbp 0x%x ret 0x%x (%s)" % (k, rbp, ret, tag))
    if nxt <= rbp or nxt - rbp > 0x100000:
        break
    rbp = nxt
end
echo \n=== fpe439: the faulting thread's last AJM/AudioOut2 calls (BC5_0439_AUDIO_CATCH) ===\n
call (void)bc5_fz439_dump()
echo \n=== fpe439: backtrace ===\n
bt 40
echo \n=== fpe439: threads ===\n
info threads
echo \n=== fpe439: mappings ===\n
info proc mappings
echo \n=== fpe439: end ===\n
kill
quit
