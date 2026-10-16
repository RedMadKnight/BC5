# 0142 — The second title's opening: no dropped readback and no failed load behind its first shot

**Question.** After experiment 0141 the opening (F182) does not wait for the reflections. Two
further suspects:
- packets the host drops as unmapped, possibly readback writes the game's CPU waits for;
- loads the game's "Archive Loose IO" thread waits for through its "Loose Load EQueue", whose wait
  times out hundreds of thousands of times a session.

**Setup.**
- BC-250 dev box, 2026-10-16 20:19–20:24.
- **Run 572:** as experiment 0141's run 571 (`BC5_DIRECT_BVH_MISS`, New Game at 100 s, ✕ at
  140 s, 230 s), with a new host knob, `BC5_DIRECT_UNMAPPED_TRACE=1`. Each packet with a memory
  operand outside the mapped ranges (the ones the filter drops) is journaled once per buffer kind,
  size and offset, with its opcode, operand and dwords.
- The guest log (the emulator's HLE trace) was read for the equeue's setup and for AMPR read or
  event failures. libAmpr journals both (`APR … failed`).
- Raw: `raw/run572.txt`.

**Result.**
- **The run never timed out.**
- **Only two packets are dropped as unmapped,** both on the same 8 bytes at 0x7f819c744000,
  host memory:
  - a `RELEASE_MEM` at dword 22 of an 84-dword graphics buffer;
  - the `WAIT_REG_MEM64` for 0 at dword 3 of a 40-dword one.
  - That is a flip label. The host keeps it itself, performs the dropped write in its soft CP, and
    clears the label at the flip (ADR 0005).
- **The Loose Load EQueue:**
  - created by the "Archive Loose IO" thread with four AMPR events (ids 0–3);
  - its wait timed out 658,644 times in the run;
  - no AMPR read or event failure appears.
  - The timeouts are the thread's idle polling.

**Verdict.**
- **Neither suspect holds the opening.** No readback is dropped and no load fails.
- What the game's threads wait for (F182: condition variables in its own code) needs the game's
  side:
  - sample the waiting threads' guest PCs over time;
  - follow the condition variable's signaller (which thread should wake them, and on what event,
    callback or GPU result).
- **Still possible:** a GPU result the CPU polls in memory without any packet of ours being dropped
  (a value a shader writes), for example the character visibility or streaming feedback. The missing
  characters point there.
- `BC5_DIRECT_UNMAPPED_TRACE` stays as a diagnostic, off by default.
