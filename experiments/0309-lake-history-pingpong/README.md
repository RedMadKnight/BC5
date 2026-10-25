# 0309 — The night lake's water: is there a history buffer swapped every frame, and who reads it?

**Question.** Exp 0307 (F372): the night lake's visible patches are one half of a checkerboard of water cells per
frame, and the halves swap between the two states. Within a run the depth writers are issued identically in both
states (F318–F323, F359), and the holes are pixels nothing drew that frame (F299, F333). So the GPU decides which half
is drawn, from data the writers read.

A renderer that draws half its cells per frame and fills the other half from the previous frame reads its history
through a descriptor or pointer that alternates between two buffers, frame to frame. Is there such a ping-pong among
the lake writers' inputs, and which writer reads it?

**Plan** (the top session's yes of 2026-10-25 ~13:50; step A read-only after the BVH session's exp 0308; step B on
its own request later).
- **Step A, read-only, no emulator:** `pp0309.py` (stdlib) on exp 0283's two kept journals
  (`~/bc5-data/captures/play-20261024-2210/gc`, W283a; `-2224/gc`, W283b).
  - They hold every depth writer's and the full-screen draw's user data and table dwords per frame (exp 0251's private
    binary, `_EVERY` windows, `_PS` on the writers).
  - Parsed with `xy0285.py`'s line formats and frame rules. Writer draws are keyed by shader and their order from the
    frame's end.
  - Each dword is scored by the share of its frame triplets within a window that alternate, v(f) = v(f+2) ≠ v(f+1).
    A frame counter, a constant or a many-slot ring (the per-frame constant pool's ~27 blocks, F293) do not score.
  - Checked on a synthetic journal: a planted ping-pong table dword scores 1.00, with nothing else listed.
  - Output: keys, dword positions, scores, value counts and relative differences. Addresses stay in the summary on
    the box.
- **Step B, a bench run on its own request:** read the ping-pong pair found in step A (and the depth image) in clean
  and patched frames, to see whether the history half is empty or stale when the lake is patched.
- **Reading:**
  - a ping-pong dword in one or a few writers names the history pass and its two buffers;
  - none means the half is decided some other way, for example by a per-frame parity in the constants (F293 found no
    dword that separates the states, but a parity flips every frame regardless of the state), and step B changes
    accordingly.

**Step A as run** (the top session's GO of 14:00 CET, after exp 0308; read-only, no emulator, nice 10 and ionice idle;
14:01–14:02 under our lock line).
- `pp0309.py` on W283a's journal (`play-20261024-2210/gc/direct.log`, 283 MB: 428 windows, 190 frames, 17,621 writer
  draws, 74,560 dwords followed) and W283b's (`-2224`, 230 MB: 431 windows, 190 frames, 12,996 writer draws, 55,040
  dwords followed). Summaries: `raw/W283a.pp.txt`, `raw/W283b.pp.txt`.
- Released 14:02:59 (BOX-QUEUE line 106).

**Step A result.**
- **One ping-pong in each run, the same one.** The full-screen water draw (PS 0x11d01d7100, "fs") reads, in its
  geometry stage's tables, one value that alternates every frame:
  - GS user-data pair 4's table, dword 0, and GS user-data pair 6's table, dword 1, carry the same value;
  - score 1.00 over 152 triplets in both runs, two values each 95 times, 0x200000 apart.
  - The values differ between the runs (low dwords …5810 in W283a, …54b0 in W283b) but keep the same 0x200000 spacing.
- **None in the depth writers**: no user-data or table dword of any writer draw alternates with period 2 (score
  ≥ 0.80), among the first 32 dwords of each table.
- **What this means for the hypothesis:**
  - The pair swaps every frame, whatever the hole state. The hole state holds for one to eight or more frames and
    switches irregularly (F344), so a per-frame swap cannot make it.
  - The writers that make the holes read no swapped descriptor or pointer.
  - So the period-2 history version of F372's mechanism is not supported. The full-screen draw's pair looks like
    ordinary per-frame double-buffered data.
  - What decides the half is still GPU-side. Irregular holding and the clean/patched variation between runs fit a
    timing race between a compute pass and the graphics writers better. Step B is to test that (on its own request).

**Step B plan** (the top session's yes of ~14:08 CET; a slot after exp 0308's run 2; RT off; ~27 min).
- **The question:** is the hole state a cross-ring timing race between the title's compute work and the lake's
  graphics writers? Exp 0132 (F180) is the analogue: ASTRO BOT on two rings drew black blocks on its models, from a
  graphics/compute cycle like the water's, until the rings were ordered.
- **One ring, how:**
  - `BC5_DIRECT_RINGS` is not the switch. Without it the title's compute queues are not run on the GPU at all; they
    stay on the soft CP (patch 0001, `submit()`).
  - The switch is `BC5_DIRECT_COMPUTE_RING`. Unset, the ring thread's compute buffers go to the GFX ring in submission
    order, as before exp 0129 (ADR 0009). `play-pkg.sh` always exports it as 0.
  - So `play-pkg-0309.sh` gets a fifth edit beside exp 0299's three: that export is skipped when
    `BC5_0309_ONE_RING=1`. The diff is kept; the shared files are untouched.
- **Proof per run:** the journal logs "compute ring N: … jobs so far" at a run's first compute-ring job. A one-ring run
  must have none; a two-ring run has at least one. `bench0309.sh` prints that count.
- **Runs** (exp 0307's lake bench, `bench0309.sh` with 13 frozen-view shots 5 s apart, the launcher's defaults
  otherwise, RT off by `input-0309.cfg`): R1 one ring, C1 two rings (a same-session control), R2 one ring, R3 one ring.
- **Reading:**
  - if R1–R3 stay clean (patch share < 5 % in every shot) while C1 and today's two-ring runs (exp 0304's W1, exp
    0307's W3) are patched, the patches are a cross-ring ordering race, and the fix lies in the water's
    compute→graphics hand-off on two rings;
  - if one-ring runs are patched too, the race is not across rings.

**Step B as run** (the top session's GO of 14:12 CET, after exp 0308's run 2; boot 664515e3; launcher 628b2714; build
226bcb82; RT off by `input-0309.cfg`).
- **14:14.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after each run).
  - `play-pkg-0309.sh` was derived as planned: exp 0299's three edits plus the gated compute-ring export, six added
    lines (`raw/play-pkg-0309.diff`). Nothing else on the box sets `BC5_DIRECT_COMPUTE_RING` (`bc5-run.env` no;
    `bc5-pkg.env` absent).
  - The kernel stream ran throughout (`raw/stepB.kern.txt`).
- **Runs** (`raw/R1.out.txt`, `raw/C1.out.txt`, `raw/R2.out.txt`): R1 14:15–14:19, one ring; C1 14:20–14:24, two
  rings; R2 14:24–14:28, one ring.
- **R3 was skipped:** R1 and R2 already agreed (below).
- **Shot viewed** in the session scratchpad and deleted right after: R2 ts08. No image is in the repo.
- **Released 14:29:30** (BOX-QUEUE line 110).

**Step B result.**
- **The ring mode as asked:** the journal's "compute ring N: … jobs so far" lines number 0 in R1 and R2 (every
  compute buffer on the GFX ring) and 3 in C1 (the compute ring in use). Every run is RT off (2,060–2,911 build-list
  drops) and has only 0x909974400 skipped.
- **No kernel event:** 0 fault lines, the amdgpu dmesg count 225 before and after (the earlier lines are exp 0308's).
- **The patch share per frozen-view shot** (exp 0197's metric; patched ≥ 8 %):

  | run | rings | ts00–ts12 | patched shots | flips/s (last 30 s) |
  |---|---|---|---|---|
  | R1 | one | 15.8, 17.6, 11.1, 11.8, 0.9, 0.8, 20.0, 1.0, 0.9, 0.9, 0.9, 0.9, 0.8 | 5 of 13 | 29.5 |
  | C1 | two | 0.9, 0.9, 0.6, 0.7, 1.0, 0.9, 1.0, 12.3, 13.7, 5.0, 15.1, 3.4, 5.1 | 3 of 13 | 29.5 |
  | R2 | one | 21.1, 3.9, 12.2, 17.4, 0.9, 0.8, 19.8, 19.5, 23.4, 22.7, 19.6, 18.9, 19.7 | 10 of 13 | 29.6 |

- **The view:** R2 ts08 (one ring, 23.4 %) shows the same checkerboard of flat tiles on the water as the two-ring runs
  of exps 0304 and 0307.

**Verdict.**
- **The night lake's patches are neither a frame-swapped history buffer read by the depth writers (step A) nor a
  cross-ring timing race (step B).**
  - With every compute buffer on the GFX ring, in submission order, the lake is patched as often as or more often than
    with two rings (5 and 10 of 13 shots against 3), with the same checkerboard.
  - So F180's mechanism does not apply here, and nothing in the ring split decides the halves.
- **Still standing** (F342–F359, F372):
  - the two halves of one cell grid, chosen GPU-side and held irregularly;
  - the same draws, arguments and constants in both states.
  - With timing across rings ruled out, what is left is data the writers read that is wrong rather than late: a
    compute or graphics result produced earlier in the same ordered stream, or GPU state carried between frames.
- **Next candidates:**
  - the lake depth writers' shaders' other inputs beyond the first 32 dwords of their tables (the bindless table of
    F272, image contents);
  - the HTILE/stencil route reopened only if new evidence points there (F310 closed it for the HTILE).
  - A lead worth a try: a cell-level look at which writer draws cover the X half and which the Y half. If each half
    belongs to fixed draws, the state is which draws reach the depth test or pass it; F333 showed the holes have no
    write at all.
