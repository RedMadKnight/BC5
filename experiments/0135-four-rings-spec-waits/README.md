# 0135 — Four compute rings and speculative graphics waits: ASTRO BOT's geyser cycle gone, the second title took the machine down

**Question.** ADR 0009's 2026-10-16 amendment. Does giving each busy guest compute queue its own
kernel compute ring, and leaving graphics waits on compute-written labels to the GPU before their
writer is submitted, resolve the geyser's cycle (experiment 0133)?

**Setup.**
- BC-250 dev box, 2026-10-16 13:54–14:13, maintainer present.
- **Backend (639b50d):** compute rings 0–3, 128 scratch slots in per-ring pools, fences and
  `wait_idle` per ring.
- **Host:**
  - `BC5_DIRECT_COMPUTE_RINGS=4`: a guest queue moves from the shared ring to a ring of its own
    after 64 buffers, the GPU idle first. The first version mapped queues in the order of first
    use (run 556).
  - `BC5_DIRECT_SPEC_WAIT_MS=100`:
    - a graphics wait on a label that a compute ring wrote last stays for the GPU even before
      its writer is submitted;
    - a watchdog thread writes the awaited value into the label if the wait is unserved after
      100 ms.
- **Runs:**
  - the ladder (`direct-selftest --compute-ring 1/2/3`);
  - 556 and 557: ASTRO BOT's title with the save copy;
  - session 1350: the maintainer's two-ring limit at 2 ms, no new knobs;
  - session 1402: the maintainer at the geyser with the new knobs;
  - 558: the second title's start screen with the new knobs (`exp0129.sh`).
- Raw: `raw/runs-556-558-and-sessions.txt`.

**Result.**
- **Ladder:** all seven steps pass on compute rings 1, 2 and 3 (ring 0 in experiment 0127). No
  kernel message.
- **Run 556 (mapping by first use):** the title's eight idle queues took the rings first, so the
  busy queues 32 and 40 shared ring 0, and 26 and 38 shared ring 2. Clean, 0 timeouts.
- **Run 557 (mapping by activity):**
  - queue 40 got ring 1, queue 32 ring 2, queue 26 ring 3; queue 38 stayed on the shared ring 0;
  - 2,049 speculative waits, the watchdog never fired;
  - no blocks, 0 timeouts;
  - the title screen ran 50.8 fps against 57 before. The GFX ring waits on the GPU now, and the
    game's thread spends 11.3 ms in the host against 6.4.
- **Geyser:**

  | session | setting | waits given up | fps, last part |
  |---|---|---|---|
  | 1350 | two-ring limit 2 ms | 913 | ~35 |
  | 1402 | four rings, speculative waits | 6 | ~34–38 |

  - In session 1402, at the geyser: the game's thread spends 10.8 ms in the host per frame (5.8 ms
    label waits) and 14.0 ms outside it. The GPU is busy about 9 ms.
  - The watchdog fired twice in the session, on counters of the 0x40368… group.
  - The maintainer found the game no worse.
- **Run 558, the second title** (start screen, New Game at 100 s):
  - its busy queues 0 and 8 moved to rings 1 and 2;
  - the watchdog fired twice on semaphore labels at 0x12004b3c38 and 0x12004b4438. They awaited 0
    while holding 0x907616589, and the watchdog wrote 0;
  - at about 132–134 s a compute buffer and a graphics buffer passed the host's 2 s fence timeout;
  - **the machine went down.** The display was black, ping answered, SSH did not. The kernel
    journal of that boot ends before it, and the maintainer reset the box (cold).

**Verdict.**
- **The four rings work** (ladder, ASTRO BOT), and mapping by activity puts the cycle's two queues
  apart.
- **Speculative waits resolve the geyser's cycle:** waits given up fell from about 900 to 6. The
  frame rate stays where it was, because the geyser is now bound by the game's own CPU work
  (14 ms outside the host).
- **The watchdog is not safe.**
  - Writing an awaited value is a guess. On ASTRO BOT's counters it was harmless.
  - On the second title's semaphores it broke the protocol that its compute and graphics queues
    keep, and the GPU hung hard.
- **Both play shortcuts are back to experiment 0134's settings:**
  - one compute ring, `CROSS_RING_WAITS=all`, two-ring limit 4 ms (second title) or 2 ms
    (ASTRO BOT);
  - no speculative waits.
  - The knobs stay, off by default.
- **Before speculative waits come back:**
  - no watchdog write: release the GPU another way, or never speculate on a label whose values
    are not a counter;
  - a test on the second title with its own semaphores, unattended runs only after that.
