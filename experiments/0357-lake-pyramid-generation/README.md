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
