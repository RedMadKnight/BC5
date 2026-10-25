# 0312 — The night lake's culling buffers: does a two-phase occlusion-culling state carry the hole halves?

**Question.** The night lake's patches are one half of a checkerboard of water cells per frame, and the halves swap
between two states, X and Y (F342, F372). The state is decided GPU-side and held for one to eight or more frames
(F344). Nothing the CPU submits separates the states (F346, F348), nor do the writers' argument values (F359), a
cross-ring race (F374), a frame-swapped descriptor (F374) or the water's 256 × 256 grid (F376).

Prior-art research (the maintainer's request, 2026-10-25) found no emulator report of this. It found one published
technique that fits the data: GPU-driven two-phase occlusion culling.
- An early depth prepass draws what was visible last frame, and a Hi-Z is built from it.
- Every bound is tested against the Hi-Z; a late prepass draws what became visible.
- Compute stages fill each phase's indirect arguments, and a per-object "visible last frame" state is kept GPU-side.

That maps onto the lake as follows:
- the culling compute 0x11d0375600 runs twice per frame, about 100 and about 1,000 groups (F355, F357);
- each writer has two argument slots 0x20 apart (F344);
- the writers read a far-is-high depth pyramid (F352).

If the per-cell state or the visible-cell lists carry the halves, they are written by the culling chain into its
buffers. Those are F355's four buffers, of which only the argument records at small offsets were ever read. Do any
pages of those buffers hold the same content within one state and a different one across states?

**Plan** (the maintainer's yes to continue, 2026-10-25 ~15:40; the top session claimed 0312; a slot on request; RT
off).
- **The bench:** exp 0311's lake bench on today's setup (`bench0312.sh`): the launcher copy derived by exp 0299's three
  edits, RT off by `input-0312.cfg`, two rings, 20 frozen-view shots 5 s apart, no journal.
- **`buf0312.py`**, beside it:
  - in the frozen view, bursts of K reads 30 ms apart of the 8 MiB from 0x11934d3900 (the four buffers are
    contiguous, and their bases were the same in exps 0289, 0293 and 0295) and of the depth image;
  - read-only through `/proc/<pid>/mem`, capa0287.py's file layout;
  - `rd0312.py` (exp 0289's `rd0289.py`) labels the depth reads with their families.
- **`pg0312.py`**:
  - per 4-KiB page and read, an order-insensitive content key (sorted dwords; a visible list may come in any order);
  - over pairs of labelled reads, the share whose keys differ among same-state pairs and among X–Y pairs;
  - the page's score is the difference, against a null of shuffled labels.
  - `--selftest`: a planted page holding one of two cell lists by state scores ~1 on top; a page rewritten every
    read scores ~0. It runs on the box (numpy).
- **The reading:**
  - a page that follows the state names the culling output that decides the halves. Decoding it (cell indices, a
    bitset) is the next step, and then what our path does to it.
  - none means the state is not in these buffers, and the depth pyramid's generation (the top session's idea: a late
    phase reading a pyramid one frame old) comes next.
- **Rules:** the live saves are never used and are checked before and after; the kernel stream; stop at the first
  reset. Reads go to `~/bc5-data/priv/exp0312` and are deleted after the analysis; numbers only in the repo.

**Sources** (prior art, public):
- Bevy's documentation of two-phase occlusion culling:
  https://doc.qu1x.dev/bevy_trackball/bevy/render/experimental/occlusion_culling/struct.OcclusionCulling.html
- U. Haar, S. Aaltonen, "GPU-Driven Rendering Pipelines", SIGGRAPH 2015 Advances in Real-Time Rendering:
  https://advances.realtimerendering.com/s2015/aaltonenhaar_siggraph2015_combined_final_footer_220dpi.pdf
- No emulator report matches:
  - shadPS4: https://github.com/shadps4-emu/shadPS4/issues?q=is%3Aissue+checkerboard (only #4573, closed without a
    cause) and https://github.com/shadps4-emu/shadPS4/issues?q=is%3Aissue+water (Bloodborne's NVIDIA-specific
    regression #3589);
  - RPCSX: https://github.com/RPCSX/rpcsx/issues?q=is%3Aissue+water (none).
