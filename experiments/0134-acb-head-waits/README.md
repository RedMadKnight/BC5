# 0134 — ASTRO BOT's black blocks: the compute heads dropped their waits on graphics; no ring order needed

**Question.**
- Experiment 0132 removed ASTRO BOT's black blocks on two rings with `BC5_DIRECT_RING_DEPS=acb`:
  compute starts after earlier graphics.
- Is it that order the game relies on, or something the host drops?

**Setup.**
- BC-250 dev box, 2026-10-16 13:37–13:50, maintainer present.
- Title screen with a copy of the maintainer's save, as in experiment 0132 (`exp0131.sh`).
- **Run 554:** compute ring, `all`, no ring dependency, and graphics without a GDS partition
  (`BC5_DIRECT_GDS_ALL` left out). This tested whether the shared GDS was the cause.
- **Host fix** (KytyPlus patch, 639b50d):
  - `submit_segment` sends the head of a compute buffer that `acb_ready` splits off ahead of an
    unready wait;
  - it now keeps for the GPU the head's waits that a pending write will satisfy, as `submit_split`
    does;
  - before, it called `submit_one` directly, and the filter dropped those waits (it keeps only
    waits on labels the same buffer writes).
- **Run 555:** compute ring, `all`, no ring dependency, the host fix.
- **Session 1346:** the maintainer played with the second ASTRO BOT shortcut, ring dependency
  removed.
- Raw: `raw/runs-554-555.txt`.

**Result.**
- **Run 554 (graphics without GDS):**
  - ASTRO BOT's graphics hang: 10 host timeouts, 0.1 fps;
  - the kernel reset only the rings (`gfx_0.0.0` and `comp_1.2.0` "reset succeeded"), and the
    machine stayed up.
  - The GDS partition is needed for the graphics, so this run says nothing about the blocks.
- **Run 555 (host fix):**
  - no blocks: 0–0.7 % in the robots' region, against up to 6.8 % in experiment 0132;
  - the 100 % at 40 s is a black transition screen;
  - the maintainer was moving with the pad, and the screenshots run from the galaxy map into Sky
    Garden, all clean;
  - 0 timeouts, 0 faults.
- **Session 1346:**
  - the maintainer saw no blocks, in the menu or in the game;
  - the geyser ran about 33 fps, as with the ring dependency;
  - 721 waits given up, 0 timeouts.

**Verdict.**
- **The blocks were the host's.** A compute buffer's head lost its waits on graphics, so on two rings
  it ran before the graphics that writes what it reads. On one ring the order hid it.
- `BC5_DIRECT_RING_DEPS=acb` is not needed and has been removed from both compute shortcuts. The
  knob stays as a diagnostic.
- A graphics ring hang now resets that ring alone on this kernel (run 554), unlike F110's
  machine-downs; F110's cases had no page fault either. TODO(verify) which kernel change made the
  difference.
