# 0307 — The night lake's patches: two complementary halves of one cell grid?

**Question.** The night lake's depth holes switch between two fixed, disjoint pixel sets, X and Y (F342). The state
holds for one to eight or more frames and switches at irregular times (F344). Nothing the CPU submits tells the
states apart (F346, F348), nor do the GPU-written indirect arguments (F357, F359). Exp 0304's viewed shots show the
patches as a checkerboard of cells on the water plane. A hypothesis that fits all of it:
- the water renderer updates half its cells per frame, a checkerboard of cells, and fills the other half from the
  previous frame's history;
- when that fill fails, one half or the other is empty, so X and Y are the two complementary halves;
- the "state" is the renderer's own phase, kept GPU-side.

Do the visible patches of one frozen view fall into two families that are disjoint and together make up the patched
water?

**Plan** (the top session's yes of 2026-10-25 ~13:20; a slot after exp 0306; RT off; ~8 min).
- **The bench:** exp 0304's (today's launcher in exp 0299's private working directory, the lake save's private copy,
  RT off by the private input configuration, the lake bench's route and Photo Mode freeze). `bench0307.sh` takes
  `SERIES=40` frozen-view shots about 1 s apart instead of 13 at 5 s.
- **W3:** one run, the launcher's defaults (as the maintainer plays: RT off, traversal dropped since int0299).
  A second run follows only if W3 has no patched phase.
- **`cm0307.py`** (on the box):
  - per shot, exp 0283's patch mask in the lake window;
  - families of patched shots by phi ≥ 0.6, each family's union;
  - for each pair of families, their shared pixels against the null of two random masks of the same shares, and
    what they cover together;
  - the families' sequence in time.
- **The reading:**
  - two large families that share almost no pixels (far below the random null) and alternate in time → the
    two-halves hypothesis holds. The next step is the pass that should fill the missing half.
  - one family only, or overlapping families → the hypothesis is dropped.
- **Viewed shots:** a handful, at least one of each family, in the session scratchpad, deleted right after.
- **Rules:** the live saves are never used and are checked before and after; the kernel stream; stop at the first
  reset; numbers only in the repo.

**Setup as run** (the top session's GO of 13:37 CET, after exp 0306; boot 664515e3; launcher `play-pkg.sh` 628b2714;
build 226bcb82).
- **13:37.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after).
- **Step 1, no emulator:** `cm0307.py` on exp 0304's kept shots, W1 and W2 (13 each, 5 s apart; `raw/W0304-W1.cm.txt`,
  `raw/W0304-W2.cm.txt`).
- **Step 2, W3, 13:38–13:42:**
  - `play-pkg-0307.sh` derived from 628b2714 by exp 0299's three edits, the four expected lines
    (`raw/play-pkg-0307.diff`); `input-0307.cfg` sets RT off.
  - The launcher's defaults: RT off by the configuration, 2,869 build-list drops in the journal; 0x909974400
    skipped.
  - 40 frozen-view shots about 1 s apart (ts00–ts39; `raw/W3.out.txt`), then `cm0307.py` (`raw/W3.cm.txt`).
  - The kernel stream ran throughout (`raw/window.kern.txt`).
- **Shots viewed** in the session scratchpad and deleted right after: W3 ts07 (family B) and ts08 (family A). No image
  is in the repo.
- **Released 13:43:15** (BOX-QUEUE line 102).

**Result** (`raw/`).
- **No kernel event:** 0 fault lines, the amdgpu dmesg count 152 before and after (the earlier lines are exp
  0306's); one routine perf line.
- **W3's patch shares:** 12.4–26.5 % in ts00–ts28 (one 2.9 % shot at ts24), then 0.7–8.5 % from ts29.
- **W3's families** (patched shots, phi ≥ 0.6 to a family's first shot):
  - A, 17 shots (mean share 0.207, union 0.297 of the lake window); B, 7 shots (0.186, union 0.252); F3, F4 and F5
    with 4, 3 and 2 shots.
  - F3 and F5 lie inside A (0.99 and 0.98 of their pixels in A), and F4 inside B (0.98). That leaves two
    super-families, {A, F3, F5} and {B, F4}.
  - A–B share 0.223 of the smaller union, where two random masks of these shares would share ~0.297; phi −0.095;
    together they cover 0.493 of the window.
  - The other cross pairs are alike: A–F4 0.193 (null 0.297), B–F3 0.156 (null 0.252), F3–F4 0.137 (null 0.171),
    phi −0.04 to −0.10.
- **W3's sequence** (1 s apart, `.` clean): `B A A A A A A B A B A A F4 A A B A A A A B A F4 A . B B F3 F3 F5 F3 F4
  F5 . . . F3 . . .`
  - B and F4 come as single shots, at most two in a row, amid runs of A.
  - Consecutive patched shots: the same family 12 times, a different one 18 times.
- **Exp 0304's shots:**
  - W2: two families of 3 and 2 shots, A and F3, share 0.134 against a null of 0.222 (phi −0.106) and alternate:
    `A F3 A F3 A` after the clean phase. A third family, B, lies inside A.
  - W1 (another camera position) has three families that all overlap (0.66–0.98), so nothing complementary shows
    there.
- **The views (W3 ts07, family B; ts08, family A; one second apart, the same frozen camera):**
  - Each shot is a checkerboard on the water plane: about half the cells are flat and lighter (the patches), the
    other half show the rippled, rain-flecked water.
  - Between the two shots the flat and the rippled halves swap places on the same grid of cells.

**Verdict.**
- **The night lake's patches are, in each frame, one half of a checkerboard of water cells, and which half swaps
  between the two states.**
  - This is what a water renderer that draws half its cells per frame leaves when the other half, which should come
    from the previous frame, shows a flat fill instead.
  - It ties together F342's two disjoint depth-hole sets X and Y, their holding for one to eight or more frames
    (F344), and the absence of any CPU-side or argument-side separator (F346, F348, F357, F359). The phase is the
    renderer's own, and the failing part is the history fill.
- **Supported, not proven.**
  - The two families are anti-correlated and overlap less than chance (0.13–0.22 against 0.22–0.30), and the views
    show the swap.
  - But colour-threshold masks overlap at tile edges and in the distance, so "disjoint" is not shown at pixel level.
    TODO(verify): on the depth image (F342's X and Y shared 0.1–0.8 % of their pixels), with both halves in one burst.
- **Next:** find the pass that should fill the missing half: the water's temporal or history step, a draw or dispatch
  that reads the previous frame's water target or depth. Then find what it reads that our path does not keep, for
  example a buffer from the previous frame that is cleared, aliased or never written.
