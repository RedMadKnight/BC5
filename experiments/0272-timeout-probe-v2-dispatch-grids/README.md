# 0272 — timeout probe v2: the group counts of a stuck buffer's dispatches

**Question.** Exp 0265 (F332) caught a machine-down with exp 0260's synced timeout probe. A compute chain of the title's
"Ray Tracing Update" pass hung inside its dispatches before offset 9872, with no wait kept. That window holds 286
indirect dispatches of 0x909936c00 and 153 of 0x909939900, whose group counts come from GPU memory. The probe recorded
neither those counts nor the direct ones, and the counts died with the process. Can the probe record each dispatch's grid
at a timeout, so that the next such hang shows whether a dispatch was given a grid it cannot finish?

**Known before this experiment.**
- The probe (exp 0160, exp 0260) runs after a fence timeout. It is on in every play of the second title
  (`play-pkg.sh`, `BC5_DIRECT_TIMEOUT_PROBE=1`) and has been in the shared builds since 2026-10-24 16:21 (F317). It
  journals each dispatch's program, but not its group counts. For indirect draws it already reads the arguments in
  memory at the SET_BASE index 1 base plus the packet's offset.
- The title's compute buffers carry DISPATCH_INDIRECT in the compute-queue form of 4 dwords, with the address in dwords
  1–2. This file's `mec_expand_ib` (experiment 0038) can rebuild it into the graphics form: SET_BASE index 1, then a
  3-dword DISPATCH_INDIRECT with an offset. W266a's dump (exp 0265) shows the 4-dword form (`indirect +0xd0571900`).
- In a machine-down the probe's synced lines and dumps are the only record (F332: the devcoredump copy was lost).

**Setup.** `patch0272.py` makes `patch_0272.diff` (65 lines, 4 hunks) against the shared tree's `bc5LleAgc.cpp` after
exp 0260's integration (md5 daca24cc; out md5 a2a2c2df). It changes only `timeout_probe()`, at daca24cc lines
5895–5900, 6012–6017, 6086–6096 and 6136–6142.
- **DISPATCH_DIRECT** (0x15): the group counts from the packet, dwords 1–3.
- **DISPATCH_INDIRECT** (0x16): three dwords in memory as the GPU left them, at the address the packet names, read as
  `mec_expand_ib` reads and writes the two forms:
  - the 4-dword compute-queue form, with the address in the packet;
  - the 3-dword form, with an offset from the SET_BASE index 1 base the probe already tracks.

  Memory outside the device's mappings is reported as "not mapped" and not read.
- **Output:** every indirect dispatch is journaled ("timeout probe: dispatch op 16 at <offset>: program <address>,
  groups X x Y x Z (arguments at <address>)"), up to 2,000 a buffer; the direct ones up to 200, as before. The count
  line adds the indirect count and the largest grid in groups, with its offset.
- **Build** (a compile check, no runs): `run0272.sh build` makes a private `~/bc5-work/exp0272/kyty_emulator` from the
  shared normal objects, as exp 0260's was (`build0272.py`, a fresh `ninja -t compdb -x`). Then the maintainer decides
  whether it goes into the shared builds.
- **No overlap with the BVH session's proposal** (its message of 2026-10-24 ~18:40). That proposal is not a clamp in
  `bc5LleAgc.cpp`. It is a six-line refusal in `backend/src/policy.cpp` `refusal_in()`: a DISPATCH_INDIRECT keeps a
  buffer off the compute ring until the MEC COND_WRITE/COND_EXEC check is verified (ADR 0009 step 5), so the BVH build
  runs on the GFX ring. It is a diff in the shared note `exp0160-f332-bvh-chain-analysis.md`, not applied.
- **The group counts would separate its two suspects:** sane counts point at the refit looping on its own lists or
  copy (F104/F107), and a garbage count points at a builder writing it on the compute queue.

**Result.**
- Prepared 2026-10-24 ~18:20 on the laptop. The diff applies to daca24cc and reproduces the full file, and the braces
  in `timeout_probe()` balance.
- **Compiled** 18:28:05–18:28:31 on the box supervisor's GO, under my lock line, with no emulator (`raw/build.out`,
  `raw/build-inputs.txt`):
  - rc 0, with only the 4 warnings the file already had and none in the new code;
  - the private `~/bc5-work/exp0272/kyty_emulator`, 166,445,800 bytes, md5 **cfab60f6**, carrying the new count-line
    format;
  - `bc5LleAgc.v2.cpp` md5 a2a2c2df.
  - The tree's `bc5LleAgc.cpp` (daca24cc) and the shared normal binary (da4d3b0a, with the 0267 pad fix) were the same
    before and after. The private binary links the shared objects as they are now, so apart from this unit it is the
    shared normal build.
- Not run: the probe acts only at a fence timeout, so its new lines will first show at the next hang, in whatever
  binary carries it.

**Verdict.** Probe v2 compiles cleanly as a one-unit change to the shared file. Whether it goes into the shared builds
(as exp 0260's did, with `int0260.sh`'s procedure) is the maintainer's decision. Until then, the next machine-down
recorded by the shared builds' probe still lacks the group counts.
