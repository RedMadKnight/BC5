# 0198 — A/B of the compute-state prefix in the same scenes (interrupted: a machine-down without the prefix, memory pressure)

**Question.** Experiment 0196 left open whether `BC5_DIRECT_CS_PREFIX=1` lengthens the long GPU stretches seen in
play. Does the same route from one save show more GPU stretches over 1 s with the prefix than without it?

**Setup.**
- BC-250 dev box, 2026-10-22 13:20–13:57. Kernel 7.2.9-ogc3.1, Mesa 26.2.4.
- Binary: experiment 0195's `~/bc5-work/exp0195/kyty_emulator` in both arms. The normal launcher, with its skips and the
  TF ring.
- Arm A: "BC5 emulator (sonda 0195)", `BC5_DIRECT_CS_PREFIX=journal`, so the GPU work is unchanged.
- Arm B: "BC5 emulator (prefiks CS 0195)", `=1`.
- Starting state: `~/bc5-work/saves-pre-1136`, the slot 3 autosave of 11:03, put back with
  `~/bc5-work/exp0196/ab-restore.sh`. The maintainer's own saves were set aside in `exp0196/saves-before-132023` and
  put back at 13:56:50.
- The maintainer played both arms. The water (exp 0197) and TCP-fault sessions held their emulator runs.
- Raw: `raw/armA-1337-crash.txt` (the end of arm A's journal, the kernel log and the reset reason) and
  `raw/armB-frames.txt` (arm B's flips per 30 s, long frames by kind, memory figures). The journals are on the box,
  `~/bc5-data/captures/play-20261022-1337` and `-1345`; the screenshots are `~/bc5-work/exp0192/shots/1354*-armB-*`.

**Result.**
- **Arm A, prefix only journaled: the GPU hung and the machine went down.**
  - At journal t 251.362 s a 5,245-dword graphics buffer (#315050) timed out (2 s). The next submission failed (rc −1)
    and the machine froze.
  - The kernel log of that boot has no amdgpu line after 12:47 and ends at 13:40:45. The next boot names the reset "a
    parity error occurred", as at 07:44 (F250).
  - The timeout probe's dump of the buffer did not reach the disk.
  - Before the hang the session showed nothing unusual: a 4.0-s frame at 217.8 s, a 1.7-s one at 183.2 s.
  - **So the machine-downs happen with the prefix off.** Which program hung is unknown.
- **Arm B, prefix on: 677 s without a fault.**
  - At least 64 buffers got the prefix. No fence timeout, no amdgpu fault or timeout in the kernel log.
  - 21–49 flips a second per 30-s window.
  - GPU stretches over 1 s at 95.8, 109.8, 471.2 and 531.9 s (1.3–1.9 s).
  - Stalls with the game thread outside the host and the GPU idle: 3.3, 1.8, 1.4 and 1.0 s, and 10.0 s at 629.8 s.
    That last one may coincide with the screenshots taken then (the first `spectacle` capture took about 60 s); not
    checked.
  - The maintainer reported the same symptom as in the probe session and in arm A. In cutscenes the characters lag
    or move slowly while effects and hair are current, now at 45–50 flips a second as well.
  - **So it is not a low frame rate alone, and not the prefix.** Cause open.
- **Memory pressure during play** (arm B, 13:48–13:56):
  - About 880–907 MB of 15,192 MB available, 0.8–1.2 GB in swap, `kcompactd0` at 99 % of a core early on.
  - Direct-compaction stalls rose from 1,061 to 18,558 in about three minutes (about 255 a second).
  - The disk read about 720 MB/s. Of that, the game and `bc5-mount` read only 0–8 MB/s; at 13:53 another session's
    `grep` over every play journal took about 115 MB/s and `journalctl` about 55 MB/s.
  - GTT is not the limit: 12,054 of 13,312 MiB used, with `ttm.pages_limit` at 13 GiB (D12). The game's guest memory
    is 11.9 GB of shmem.

**Verdict.**
- **Inconclusive for the question.** The A/B was interrupted: arm A ended in a machine-down at 4 minutes, and the
  maintainer stopped arm B at 11 minutes and postponed the A/B until the TCP-fault session has a fix. The prefix's
  effect on GPU stretches is not measured: across arm B and sessions 1056 and 1136 the stretches vary between 1.2 and
  9 s, with the prefix and without it.
- **Established:**
  - The machine-downs and the cutscene slow motion both occur with the prefix off.
  - In play the box runs with under 1 GB of memory free and stalls in compaction. Heavy reads by other sessions during
    play make that worse, so they must stay off the box while the maintainer plays.
- Next, after the TCP fix: the same A/B from `saves-pre-1136`, with no other session's I/O on the box and no
  screenshots during the measured part.
- Until then `patch_0195.diff` stays out of the shared tree and the launchers. The two test shortcuts stay on the
  desktop for that A/B, then move to `~/bc5-work/old-shortcuts/`.
- The cutscene slow motion is its own question.
