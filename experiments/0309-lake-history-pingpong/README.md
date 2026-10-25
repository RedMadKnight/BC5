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
