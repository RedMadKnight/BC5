# 0119 — Graphics pieces sent as one job with their prefix: ASTRO BOT's tagged-address faults gone

**Question.** Experiment 0118 tied ASTRO BOT's CB/DB and SQC faults (addresses tagged 0x80 in bits
47:40) to `BC5_DIRECT_PIECES_FULL`. Is the full-state prefix itself wrong, or how it reaches the GPU?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present, `nproc` 16 before every run. ASTRO BOT with its
  play settings (`bc5-run.env`), 70 s, no input.
- **Step 1, runs 449–450 (11:33, 11:35).** Pieces off, `BC5_DIRECT_PIECES_DRY=1` (prefixes built at
  every unsatisfied wait, nothing submitted differently). New host diagnostic
  `BC5_DIRECT_TAG_WATCH=1` journals every address register with a non-zero bits 47:40 byte, in each
  dry prefix and in the stream tracker after each graphics buffer. The registers:
  - `CB_COLOR0..7_BASE_EXT`, CMASK/FMASK/DCC `_BASE_EXT` (ctx 0x390–0x3af);
  - DB `_BASE_HI` (ctx 0x01a–0x01e);
  - `SPI_SHADER_PGM_HI_PS/GS/ES`, `COMPUTE_PGM_HI` (sh 0x9, 0x89, 0xc9, 0x20d).
  - Offsets from the Mesa gfx10 register JSON via `tools/bc5-agc/regdb`.
- **The change.** Until now, a split sent the prefix (`dcb-state`) and the piece as two
  `submit_one` jobs. The ring thread (`bc5-ring`, the title's asynchronous compute) could submit
  between them.
  - The comment at the piece code (run 123) already reported 0x800000005000 shader fetches "with
    foreign state" for the older pieces.
  - The kernel names `bc5-ring` as the task in 0118's CB/DB faults.
  - Now prefix and piece go to the GPU as one job. `BC5_DIRECT_PIECES_TWO_JOBS=1` restores the old
    way.
  - Host built 2026-10-15 11:38 (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`).
- **Step 2, runs 451–456 (11:50–12:01).** `BC5_DIRECT_PIECES_FULL=1` with the change. Script
  `series-onejob.sh 451 456`, which stops at the first GPU page fault.
- Raw:
  - `raw/runs-449-450-tag-watch.txt`;
  - `raw/series-451-456.txt`;
  - `raw/piece-lines-sample.txt`.

**Result.**
- **Step 1.**
  - Runs 449 and 450 built 1,972 and 2,018 dry prefixes (mean 1,261 dwords) and journaled no
    tagged register.
  - The stream tracker never held one either.
  - No fault; 55.2 fps.
  - So the prefix, as the tracker builds it, never carries 0x80.
- **Step 2:**

| run | piece splits | GPU page faults | timeouts | fps (t 40–65 s) |
|---|---|---|---|---|
| 451 | 26 | 0 | 0 | 59.96 |
| 452 | 16 | 0 | 0 | 59.96 |
| 453 | 20 | 0 | 0 | 59.84 |
| 454 | 25 | 0 | 0 | 59.92 |
| 455 | 25 | 0 | 0 | 59.96 |
| 456 | 22 | 0 | 0 | 59.96 |

- That is 134 splits, including the ~25,000–27,000-dword buffers of the second load phase where
  0118's faults came, with no fault.
- Before the change, with pieces, 6 of 12 captures had a fault or a lost journal (0118).
- These runs split more often (16–26 against 2–17 before). In the sampled `piece:` lines, the wait
  was satisfied within 4.1 ms after the head went, except one given up at 8.1 ms.
- The 60 fps over t 40–65 s, against 55 in 0118's runs without pieces, is an observation in the
  same window. It was not measured as a gain.

**Verdict.**
- Passed. ASTRO BOT's tagged-address faults came from the prefix and its piece running as two jobs
  with the ring thread's work allowed in between, not from the prefix's contents.
- One job removes them: 0 of 6 runs, against 6 of 12 captures.
- `BC5_DIRECT_PIECES_FULL=1` can go back into ASTRO BOT's play settings, with the maintainer's yes.
  That brings back F137's water benefit.
- Open:
  - which of the ring thread's state reached the piece (not needed for the fix);
  - a longer play session with pieces, including the water.
- 0117's PFSC readers (0114, 0116) were reverted on 0117's wrong reading. They can be retested on
  ASTRO BOT now.
