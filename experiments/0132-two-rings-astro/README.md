# 0132 — ASTRO BOT on two rings: black blocks need compute to start after earlier graphics; the geyser cycle 30 fps (one ring 26)

**Question.** The maintainer played ASTRO BOT on the compute ring (experiment 0129's settings) and
reported two things:
- black blocks over the picture, alternating with the right image, from the title screen on;
- a much lower frame rate at a geyser.

What causes each, and what fixes them?

**Setup.**
- BC-250 dev box, 2026-10-16 07:39–13:25, maintainer present.
- **Sessions:** the maintainer played with the play shortcut and the journal on (`PLAY_CAPTURE`).
  The frame rate per 15 s is counted from the frame-profile lines.
- **Runs 546–553:**
  - `exp0131.sh` (experiment 0131): the title screen, 70 s, no input, screenshots every 2 s;
  - `exp0129.sh`: the second title's start screen.
- **Title screen with the maintainer's save** (`KYTY_BC5_SAVEDATA_DIR` set to a copy): ASTRO and
  other robots fly on a pad. Without a save it shows the logo only, and the blocks do not show.
- **`blockshare.py`:** the share of near-black pixels in the region of the robots and the pad.
- **Host changes** (KytyPlus patch):
  - **Two-ring split.** With `CROSS_RING_WAITS=all` and the compute ring, a graphics wait that is
    neither satisfied nor kept is split at once (ADR 0008's pieces). The head goes, then the rest
    keeps the wait for the GPU as soon as the compute writer is submitted. It gives up after
    `BC5_DIRECT_TWO_RING_WAIT_MS`, at first 50 ms and finally 8 ms.
  - **Waits kept inside prefixed pieces** are moved into the copied piece. They were lost before.
  - **`BC5_DIRECT_WAIT_TRACE=1`** journals each wait served on the CPU, and each compute buffer
    held back by its wait, with the last pending write of the label.
- Raw: `raw/runs-546-553-and-sessions.txt`.

**Result.**

Black blocks (title screen with the save; the highest block share over 20 screenshots):

| run | setting | highest share | screenshots |
|---|---|---|---|
| 549 | one ring | 0.6 % | clean |
| 548 | compute ring, `all` | 6.5 % | black blocks on the robots and the pad |
| 550 | + `RING_DEPS=both` | 1.0 % | clean |
| 551 | + `RING_DEPS=acb` (compute after the GFX ring's last job) | 0.5 % | clean |
| 552 | + `RING_DEPS=dcb` (graphics after the compute ring's last job) | 6.8 % | black blocks |

- **The blocks come from compute starting before graphics submitted earlier has finished.** Given-up waits do not cause them: run 546 gave up none on the title screen and the
  maintainer still saw blocks.
- Turning off the deferred flip did not remove them either (maintainer, by eye).
- With `RING_DEPS=acb` the maintainer saw no blocks (session 1117).
- The second title's start screen keeps most of its gain with `acb`: run 553, 40.6 / 39.4 fps,
  against 41.8 / 41.4 without and 33.6 / 31.6 on one ring (experiment 0129).

The geyser (fps per 15 s, from 165 s on, where the maintainer stood at it):

| session | setting | at the geyser | waits given up |
|---|---|---|---|
| 1318 | one ring | 26–27 | 916 (8 ms each) |
| 1312 | compute ring, `acb`, two-ring limit 50 ms | 13 | 924 |
| 1322 | compute ring, `acb`, two-ring limit 8 ms | **30–31** | 1,472 |

- **The geyser is a cycle, as the water is (ADR 0008).**
  - The main graphics buffer waits, at dwords ~20,234–20,309, for three counters that a compute
    buffer of 1,332 dwords increments. The value is always 3 below the reference, and no write is
    pending.
  - A compute buffer of 3,624 dwords is held back by its waits at dwords 87 and 3,575 (reference 1,
    value 0, no write pending). Those labels are written only after the graphics buffer's wait, and
    the buffer stands ahead of the 1,332-dword one.
  - Each side waits for the other until a limit gives up, every frame, on one ring as on two.
- No session or run had a host timeout, a page fault or a ring reset.

**Verdict.**
- **For the compute ring, `BC5_DIRECT_RING_DEPS=acb` is needed.** A compute job starts after the
  graphics jobs submitted before it. Graphics submitted after it may still overlap: about 26 % of
  the time on the second title's start screen.
  - Both play shortcuts with the compute ring have it since 2026-10-16:
    - the second title's (`play-pkg.sh`);
    - ASTRO BOT's second shortcut (`play-astro-compute.sh`).
  - What the game relies on there is not known yet. It is either an order the console gives
    (e.g. separate GDS partitions per queue) or a wait the host drops.
- **The two-ring split** keeps for the GPU almost every wait that has a writer. Its limit is
  8 ms, as for one ring. Longer only loses time on the cycle, because a writer, when there is one,
  comes within a millisecond.
- **The geyser's cycle needs the compute queues to block one at a time,** as on the console. Today
  all of them go through one host thread and one ring in doorbell order.
  - The next step: one kernel compute ring per guest compute queue (the BC-250 has four).
  - Their waits are left to the GPU only when the writer is submitted; otherwise the queue waits
    alone.
  - This is an ADR 0009 amendment to write first.
