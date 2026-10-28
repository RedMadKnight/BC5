# 0357 — The night lake's depth pyramid: which frame's pyramid does the culling read, and does it differ between the two hole states?

**Question.** The night lake's holes are two complementary hole states, X and Y. Each holds for one to several frames
(F342, F344; frame by frame in exp 0354, F436). The culling buffers do not carry the state (F436, F440). The lead left
in Q21 is the depth pyramid's generation. The lake's depth writers read a 32-bit-float, far-is-high depth pyramid
(F352): five single-level images, mip 0 (128 × 64) at 0x11d0886000 down to 8 × 4 at 0x11d0892000. It is bound,
among others, by CS 0x11d0288800 (6,144 groups) and by the writers (exp 0274). In GPU-driven two-phase occlusion
culling, a frame's late pass must test against the pyramid built from that frame's early depth. If on our host it
sometimes reads the previous frame's pyramid, the culling of that frame works from stale occlusion. Within a frame,
does the culling output that the lake's draws consume change after the pyramid is rebuilt, or before? And does that
order, or whether the pyramid is rebuilt at all, differ between X frames and Y frames?

What is known and what is not:
- F352 compared the pyramid's content with the holes. It matches X and Y about equally, because one mip-0 texel covers
  about 24 × 27 depth pixels. So content cannot tell the generation; timing can.
- F350 (30 ms reads) saw the pyramid change in the same read interval as the writers' arguments (33 of 36). It never
  led them by a read, so their order within a frame was below its resolution. Twice the pyramid did not change.
- F344: each depth-only writer's argument offset takes one of two values 0x20 apart, a per-frame double buffer whose
  slot the CPU picks. The hole state does not follow the slot. CS 0x11d0375600 runs twice per frame (F357).

**Expectation.**
- **If the pyramid's generation decides the state,** frames of one state differ from frames of the other in their
  GPU order:
  - the culling output updates before the frame's pyramid rebuild (a stale pyramid) in one state and after it in the
    other;
  - or the pyramid is not rebuilt in the frames of one state;
  - and the state switches fall where that order changes.
- **If not,** the order is the same in X and Y frames, or varies independently of the state.

**Plan** (the maintainer's "Tak, zleć" through the top session, 2026-10-28 ~10:15; RT ON, the standing rule; one
run, a second only if the first cannot label the states).
- **The bench:** the lake bench of exps 0354/0355 on the shared normal build at the time.
  - The launcher is exp 0353's checked copy renamed (`setup0357.sh`); the config is RT on, MangoHud off (exp 0355's).
  - 24 frozen-view shots. The draw journal `210:3000` with `_PS=11d01d7100` sizes the full depth reads, as in J1
    (`fr0354.py`).
- **`pl0357.py`, beside it:** from the frozen view and the emulator's 212th second, for 60 s, reads in a tight loop
  through `/proc/<pid>/mem`, read-only, and timestamps every change (`time.monotonic` and wall clock). Every poll reads:
  - **D:** 256 KiB of the depth image in the lake's block rows (depth base 0x1129ec0000 + 0x980000), as the frame's
    depth activity;
  - **P:** the pyramid's five mips (0x11d0886000–0x11d0892fff), a hash per mip;
  - **A:** the first 4 KiB at each of the four culling bases (F440), 128 records of 32 bytes each, and which records
    changed.
  - Every 0.5 s it takes one full depth read (25 MiB, ~13 ms) for the hole state, kept in `~/bc5-data/priv/exp0357`.
  - The poll period is printed (expected ~1 ms).
- **The states:** `rdj0312.py` → `fr0354.py` → `rdj0354.py`, as J1, size each full read. `ph0357.py` (`ph0354.py`'s
  masks) splits the reads' hole masks by the leading eigenvector into two states and writes a label per read.
- **`cy0357.py`, the test:**
  - It segments the poll log into GPU frame cycles: a cycle starts at a D change after at least G ms without one
    (G from the log's own gaps).
  - Per cycle: the first and last D change; whether each mip changed, and when; the first and last A change and
    which records.
  - The order classes: P before A, A before P, no P, no A.
  - Each full read gets the latest cycle whose D activity ended before the read began, and that cycle's order; then
    the state × order table, with a permutation p (state labels shuffled over reads in blocks of a burst, so the
    state's hold is kept).
  - It also prints the cycles around each state switch.
  - `--selftest`: a synthetic log in which X cycles have A before P and Y cycles P before A must come out with p near
    0; a log with the order independent of the state must not.
- **The reading:**
  - p < 0.01 in the state × order table (or no P rebuild in one state) supports the generation lead. Then the cycle
    order tells which dispatch runs early, and the next step names it in the stream.
  - The same order in both states, with both states labelled in enough cycles, closes this lead for the culling.
  - The order's own distribution (always P before A, or mixed) is a result either way.
- **Rules:**
  - the guard (an empty BOX-LOCK, our own lock line, no emulator; the bvh session's exp 0356 shares the box);
  - the kernel stream; stop at the first reset;
  - live saves 3f8412c4884ddf14, compared only.
  - Reads and shots are deleted after the analysis, unviewed; the journal stays private.
- **Why RT on is fine:** the measurement reads memory and needs no RT setting; RT on is the standing rule.

**Setup as run** (the top session's GO of 2026-10-28 ~10:15; boot 6d79bc01; build affa0c22; launcher 55531ab6).
- **10:22.** The guard found exp 0356's emulator running (the bvh session) and touched nothing. The laptop watcher
  (lock and `pgrep` every 60 s) saw the box free at 10:34:10.
- **10:34:25.** Our lock line went into the empty BOX-LOCK, `~/bc5-work/exp0357/CLAIM.txt` was written and a
  BOX-QUEUE line added. Live saves 3f8412c4884ddf14.
  - `setup0357.sh`: `play-pkg-0357.sh` 9a1ba52c with exp 0353's five edits (`raw/play-pkg-0357.diff`);
    `input-0357.cfg` RT on, MangoHud off (`raw/input-0357.cfg`).
  - `cy0357.py --selftest` on the box gave planted p 0.0005, null p 0.57. The kernel stream ran throughout
    (`raw/kernel-stream.txt`).
- **P1, 10:34:49–10:40:09** (`raw/P1.ab.txt`, `raw/P1.out`):
  - RT on (0 ray-tracing-off lines), one ring;
  - the journal `210:3000`, `_PS=11d01d7100`; 24 frozen-view shots.
  - `pl0357.py P1 60 0.5 … 212` (`raw/P1.pl.txt`): the frozen view and the emulator at 212.0 s, then 60 s of
    polling. 745,606 polls (a mean period of 0.080 ms, largest gap 230 ms at a full read).
  - Polls with a change: D 12,518, the five mips 1,747 / 1,618 / 1,609 / 1,606 / 1,602, the culling records 9,515.
  - 119 full depth reads, 2.9 GB.
- **Analysis, 10:40–10:46:**
  - `rdj0312.py` (`raw/P1.rd.txt`, `raw/P1.rd.json`), `fr0354.py` (`raw/P1.fr.txt`, `raw/P1.frames.json`) and
    `rdj0354.py` (`raw/P1.rdj.txt`);
  - `ph0357.py` (`raw/P1.ph.txt`, `raw/P1.labels.json`), then `cy0357.py` (`raw/P1.cy.txt`).
- **Changes after seeing the data:**
  - **`cy0357.py`'s cycles were wrong.** At G 3 ms they came out at a median of 16.7 ms, half a frame: the depth
    sample changes in two short bursts per frame, about 10 ms apart. A look at the poll log (an excerpt printed on
    the box) showed the frame's structure, below.
  - `cyp0357.py` (`raw/P1.cyp.txt`, with a self-test: planted p 0.0005, null p 0.17) cuts the frames at the pyramid's
    rebuild instead.
  - **The first labels split holes from none:** 69 of the 118 sized reads had few or no holes. `ph0357.py` gained a
    hole-share floor (0.03): `raw/P1.ph2.txt`, `raw/P1.labels2.json`.
  - `nr0357.py` (`raw/P1.nr.txt`) counts the frames whose pyramid was rebuilt late.
- **Cleanup:** the full reads and the 26 shots were deleted at 10:46, unviewed. The poll log is kept
  (`raw/P1.events.txt.gz`, 250 KB: times, change flags and record indices, no data).
  - The journal stays private: `~/bc5-data/captures/play-20261028-1034/gc/direct.log`, 125,972,930 bytes.
- **Released 10:46:26:** the lock line removed, no emulator, launcher or bc5-mount left, a BOX-QUEUE line.

**Result** (`raw/`).
- **No kernel event:** 0 fault lines and 0 ring timeout or reset lines; the stream holds IPv6 lines only.
- **Live saves:** 3f8412c4884ddf14 before, after and at the release.
- **The frame rate:** 30 flips in 1.014 s at t 307 s, with RT on.
- **The lake was patched in 23 of 24 shots, mostly lightly:** 7.9–9.1 %, with 12.2–27.4 % at ts12–ts17.
- **Sizing:** 2,714 full-screen water draws from t 210.0 to 305.8 s, 34 ms apart (median), at widths 2560 (1,559),
  2304 (845), 2048 (307) and 2816 (3). All 63 clear reads agree with their frame's width at +10 ms, so all 119 full
  reads were sized.
- **The states:** with the floor, 49 reads have holes. They split into A (24) and B (25), mean φ 0.41 and 0.60 within
  and −0.12 between (eigenvalue share 0.46); 69 reads have none.
- **Each frame's GPU order** (the poll log, frames cut at the rebuild; `raw/P1.cyp.txt`):
  1. All five pyramid mips change in one poll, once per frame. 1,600 cycles, median 33.7 ms (quartiles
     32.9 / 34.7).
  2. The culling records change in clusters over the next ~1–6 ms.
  3. The depth writes begin a median 5.1 ms after the rebuild, with a ~100-record change at that moment.
  4. A second depth burst follows ~10 ms later, then the next rebuild.
  - So the pyramid each frame's culling reads was built from the previous frame's finished depth, holes
    included. There is no second rebuild within a frame.
- **Late culling occurs but does not follow the holes.**
  - In 629 of 1,600 frames (39 %) culling records change more than 1 ms after the depth writes began: a median
    1.8 ms after, with 95 records at the start and 122 later (medians), and none before.
  - Against the 116 placed full reads, the share of reads whose frame was late:
    - 14 of the 49 reads with holes, 21 of the 67 without (p 0.85);
    - 5 of the 24 A reads, 9 of the 25 B reads (p 0.36).
- **Late rebuilds do not either:** 104 cycles (6.5 %) last 51–55 ms, a rebuild late by about half a frame. A skipped
  rebuild would show as ~67 ms. Only one full read followed such a cycle, and it had no holes.
- **The planned `cy0357.py`** (frames halved, the first labels) gives p 0.44 and 0.75; its cycles are not frames, so
  its tables are not read.

**Verdict.**
- **The depth pyramid's generation does not decide the lake's holes.** The pyramid the writers and the culling read
  is rebuilt once per frame, in one step, from the previous frame's finished depth, before that frame's culling and
  draws.
  - That order holds in frames with and without holes and in both hole states. There is no second, mid-frame
    rebuild for a late phase in these five images.
  - The rebuild was late in 6.5 % of frames, never before a read with holes.
- **A new fact, not the cause:** in 39 % of frames the culling records keep changing after the draws began, but just
  as often in clean frames as in patched ones, and in both states.
- **Limits:**
  - one run, lightly patched for most of it (49 reads with holes);
  - the depth sample is 256 KiB of the lake's block rows. Only the five known pyramid images and the culling ranges'
    first 4 KiB were polled, so a late phase using another image would not show.
  - The analysis changes (frames cut at the rebuild, the label floor) were made after seeing P1, and are marked.
- **With the culling buffers (F436, F440) and now the pyramid's generation ruled out, the remaining lead is F372's
  history fill:** the water renderer draws half its cells per frame and should fill the other half from the previous
  frame. Where that history comes from, and whether our path gives it the wrong frame, is next.
