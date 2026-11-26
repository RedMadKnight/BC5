# 0152 — Who streams `animstrm`: the title's APR calls all go through one queue flush, so the stack does not name the requester

**Question.** Experiment 0151 left the stalled animation stream to the title's code. Which code
submits the `animstrm` reads, and what does it check after their completion event?

**Setup.**
- Host (KytyPlus patch, `libAmpr.cpp`): `KYTY_BC5_APR_CALLERS=1` journals, once per distinct
  (caller, file id), the guest return address of `sceAmprCommandBufferReadFile` and of the three
  submit calls, plus the caller one frame up (the frame-pointer chain: `[rbp+8]` of the frame that
  called us). `bc5 apr: ReadFile file <id> size <n> +<offset> from <ra> caller <ra1>` on stderr.
- Static: `readelf` reads nothing of the title's ELF (PS5 format), so the import stubs cannot be
  listed offline; the title's code was read from the private dump
  (`~/bc5-data/priv/eboot-text-900000000.bin`, `objdump -D -b binary`).
- Runs 581–583, 2026-10-17 11:00–11:26, maintainer's OK given: run 579's input (New Game on an
  empty slot) with the journal; a detached watchdog on the box (`~/bc5-work/watch583.sh`:
  screenshots at +110 and +130 s, kill at +137 s), because the laptop's SSH session dropped
  mid-run twice (run 581 ran unattended for 90 s at the slot list before a manual kill; run 582 was
  killed by hand at the slot list after a misread of the clock). Run 583 completed as scripted,
  killed at +140 s, 16 s into the opening.

**Result.**
- Run 581 (first journal): every read comes "from 0x900000194", every submit "from
  0x9000001d9": those are the title's own wrappers at the start of its text (0x900000170: a
  frame-pointer function that reorders the arguments and calls the PLT stub of the read; 0x9000001d0:
  the submit wrapper with the errno conversion).
- Run 583 (one frame up): all 99 (caller, file) pairs name **one** caller of the read wrapper,
  0x903c7c1ba, and one of the submit wrapper, 0x903c7c789. The code there is a loop over 32-byte
  request records (`add $0x20,%r14`, `jne 0x903c7c130`): a generic flush of a queued-request list
  into one APR command buffer (`call 0x900000120` = a measure call per record, then the read, then
  the submit at 0x903c7c784 once per buffer with a state word set from 1 to 2). The requester of
  the `animstrm` chunks enqueues a record elsewhere and is not on this stack.
- The chunk headers in `animstrm` (`04 00 11 11 …`, `74 01 11 11 …`, `e8 02 11 11 …` at the
  three consecutive chunk offsets, the 16-bit index rising by 0x170 per chunk) have the magic
  0x1111 at +2; the text compares a 16-bit value with 0x1110 and 0x1111 at ten sites
  (0x90051bbd5, 0x900545a2f, 0x90058b844, 0x9005eed7b, …), each a case in a large type switch
  (`cmp $0x1110; je; cmp $0x1111; jne`) with 64-byte records (`shl $6`) — a resource-type
  dispatcher, not a stream parser by itself.

**Verdict.**
- **The APR caller journal is kept** (`KYTY_BC5_APR_CALLERS`, off by default): it names the
  title's flush function and shows that every file read of this title goes through one queue.
  Finding the `animstrm` requester needs the enqueue site: a data watchpoint on a queue record
  (the 32-byte entry whose file id is 0x628c6db3) in a live run with the maintainer, or the
  journal extended to walk the queue's producer (the record's fields may hold a callback or an
  owner pointer).
- Offline, the resource-type switch sites with 0x1111 are the next reading: which one handles the
  streamed-animation type, and what it does when the index of the next chunk is wanted.
- Unattended runs: the watchdog on the box is now the rule (the SSH session is not reliable for
  the kill), with a pattern that does not match its own command line (`pkill -f "watch58[3]"`).
