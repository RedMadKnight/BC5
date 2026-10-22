# 0206 — the machine-downs' label is cleared by nothing the host tracks, and a given-up wait is dropped, not left to the GPU

**Question.** F262 found that three machine-downs follow, within 29–71 ms, a graphics wait on label
0x12004b3c38 that the host gave up on. Who clears that label: a GPU job the host has queued, the
APR engine's write-address commands, or something else?

**Setup.**
- One scripted run, tcpW1, 16:52–17:02 on 2026-10-22. It was granted by the box supervisor; the
  maintainer was away.
- Script: the water session's bench, `~/bc5-work/exp0201/bench0201.sh tcpW1 600` (private copy of
  the lake save, into gameplay, Photo Mode after ~5 min).
- Switches: `ENVX="BC5_EMU=~/bc5-work/kytyplus-build/src/kyty_emulator BC5_DIRECT_WAIT_TRACE=1
  KYTY_BC5_AMM_TRACE=1"`. That is the shared build and the launcher's defaults plus two logging
  switches, neither of which changes what the GPU runs:
  - `BC5_DIRECT_WAIT_TRACE` (exp 0133) logs every unsatisfied game-thread wait with its label,
    compare function, reference, current value and the GPU jobs the host has queued to write that
    label (`describe_pending`);
  - `KYTY_BC5_AMM_TRACE` logs every APR write-address command the title records, with its target
    and value.
- Box: kernel 7.2.9-ogc3.1, boot ac5dab11 (the one after the 16:36 machine-down).
- Journal: `~/bc5-data/captures/play-20261022-1652/gc/direct.log`. Emulator log:
  `~/bc5-work/exp0206/tcpW1-play-pkg.log`. Excerpts in `raw/tcpW1-summary.txt`.

**Result.**
1. No timeout, no fault, no machine-down in 600 s. 17 game-thread waits were given up, 6 of them on
   0x12004b3c38.
2. **No queued GPU job writes the label.** 6,697 wait-trace lines name 0x12004b3c38 (graphics
   buffers, dwords 379, 418, 5,855, 5,907, 8,994 and others). Every one of them reads:
   - function 3 (equal), reference 0x0, value 0x907616589;
   - "no pending write".
3. **The APR engine does not write it either.** Of the 19,139 write-address commands the title
   recorded, none targets 0x12004b3c38 or any 0x12004b3xxx address. Most go to 0x90adf7f98 and its
   neighbours.
4. Together with experiment 0204 (no PM4 packet in 202 timeout dumps writes the label), the label is
   cleared to 0 by something the host does not track: the title's own CPU code, or a shader store.
5. **A given-up wait does not stay on the GPU.** This corrects F262. The filter's `self_waits_only`
   (on by default, `backend/src/policy.cpp`, the WAIT_REG_MEM branch of the filter) drops a
   WAIT_REG_MEM[64] whose label nothing in the same buffer writes. The only exceptions are the
   waits the host keeps for the GPU (`keep_wait_offsets`), and those are kept only when a queued
   job will satisfy them (`ring_will_satisfy`), which never holds here.
   - So after a give-up, the buffer runs on the GPU without waiting at all: ahead of whatever the
     title meant to wait for.
   - The timing link of F262 (three of three, against a give-up every 15–20 s) therefore points to a
     race: work that consumes data before its producer is done. It does not point to a GPU wait that
     never ends.
6. For context, memory pressure without a hang: exp 0203's O2 (16:42–16:52) had up to ~44k
   swap-ins/s, PSI memory full 10–18 % and a ~1-s stall of all emulator threads, and ended
   normally (that session's `raw/O2-ana.txt`). Swap is zram (7.4 GB) and the guest memory holds
   11.1 GB of 15.2 GB (the box supervisor's snapshot at 16:57).

**Verdict.** Answered for the writer's kind; the mechanism is corrected and narrowed.
- The label 0x12004b3c38 is cleared by the title's CPU code or a shader, which the host cannot
  see. The host's 8-ms game-thread limit (`BC5_DIRECT_DCB_WAIT_MS`, default 8) lets the following
  work run ahead of it.
- The 8 ms was set for true cycles a single ring cannot resolve (run 124). This wait is no such
  cycle: the writer runs elsewhere and does arrive. Most of the label's waits are served within
  the 4–8 ms; only a few a minute are not.
- Next, with no build, one scripted run: the same bench with `BC5_DIRECT_DCB_WAIT_MS=100`.
  - Expected: the give-ups on 0x12004b3c38 disappear or nearly so, at a small frame cost.
  - Measure: give-ups by label, and frames over 50 ms against tcpW1.
  - A 12-minute run cannot show the machine-downs going away (about one an hour of play). Only
    longer use can, and a launcher change needs the maintainer.
- If the longer limit costs too much elsewhere, a targeted host change behind a switch (off by
  default): a longer CPU-side wait only for labels with no pending GPU writer.
