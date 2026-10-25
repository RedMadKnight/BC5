# 0292 — The night lake depth writers' indirect arguments: which dispatch writes them, and from what

**Question.** Exps 0287/0289 (F350, F352): in the frozen view the lake depth writers' GPU-written indirect arguments
change in steps, never without the depth memory changing, and all four adjacent hole switches seen fell on such a
step. The 32_FLOAT pyramid the writers read does not carry the hole state. So what writes the arguments, and which of
its inputs change at the steps?

**Plan** (the top session, 2026-10-25 ~01:55: offline and journal-reading work at night; box reads on a BOX REQUEST;
a bench run in the morning).
- **The arguments' addresses.** Three SET_BASE index-1 bases, 0x11934d3900, 0x11935d3900 and 0x1193ad3900, offsets
  below 0x1000 (exp 0287's `raw/base0283.txt`, from edit0194.py's "draw journal args" lines).
- **The journal's reach** (patch 0001, read offline).
  - `BC5_DIRECT_DRAW_JOURNAL_FIND` journals every draw or dispatch whose user data holds one of the given 32-bit
    values, directly or among the first 64 dwords of a table behind a user-data pair (experiment 0092).
  - For a dispatch it adds its 16 user-data dwords ("find ud cs") and that table's 64 dwords ("find table";
    experiment 0156).
  - Only the table where the value was found is dumped.
- **Step A, read-only greps of kept journals** (a BOX REQUEST; no emulator).
  - Exp 0274's two journals (`~/bc5-data/captures/play-20261024-2106/gc`, `-2113/gc`) had `_FIND` on the writers'
    images. Their dispatch hits include CS 0x11d0288800 (DISPATCH_DIRECT 6144 × 1 × 1, table at user data 0; exp 0274,
    `raw/W274ab.find-detail.txt`), which reads the pyramid and the textures: a candidate for the culling pass.
  - `vs0292.py` reads their "find: dispatch", "find ud cs" and "find table" lines. It lists every buffer descriptor
    (V#: base, size from records and stride, type 0) among the user data and the dumped tables whose range covers an
    argument range.
  - Checked on a synthetic snippet: a V# planted at table dword 8 over 0x11935d3000 + 0x2000 is found.
- **Step B, a journal-only bench run (morning, on its own BOX REQUEST)**, since step A showed no writer (below).
  - `ab0292.sh` / `bench0292.sh` (exp 0289's, renamed): exp 0251's private binary, exp 0283's journal switches (for
    the run's own argument lines), plus:
    - `BC5_DIRECT_DRAW_JOURNAL_FIND=934d3900,935d3900,93ad3900`: the argument bases' low dwords, as a V#'s word 0
      holds them when its buffer starts at a base;
    - `BC5_DIRECT_FIND_VA=1193400000:1193c00000` (experiment 0059): every dispatch, in every submitted buffer, whose
      compute user-data pair points into the 8 MiB around the bases, at most 4 lines per program and offset.
  - `fva0292.py` groups the FIND_VA lines by program and user-data pair and marks the addresses against the bases
    (checked on two synthetic lines). `vs0292.py` lists the `_FIND` hits' covering V#s.
  - No memory reads.

**Step A, as run** (the top session's GO of 01:57; read-only, nice and ionice idle, no emulator; 01:57:29–01:58:20
under our lock line).
- `~/bc5-work/exp0292` claimed. The "draw journal find: dispatch", "find ud cs" and "find table" lines of exp 0274's
  two journals (92 MB and 91 MB) were grepped into `~/bc5-data/priv/exp0292` (2,689 and 3,097 lines), summarised by
  `vs0292.py` and `vbuf0292.py`, and deleted.
- Results (`raw/W274-2106.vs.txt`, `raw/W274-2113.vs.txt`, `raw/W274a.vbuf.txt`, `raw/W274b.vbuf.txt`):
  - Two dispatch kinds hold the writers' images: CS 0x11d03ab400 (DISPATCH_DIRECT 8 × 4 × 1, 12 hits in each
    journal) and CS 0x11d0288800 (6144 × 1 × 1, 12 hits; in W274b 10 of them and 2 at 8192 × 1 × 1).
  - No buffer descriptor in their user data or in their dumped tables covers an argument range.
  - CS 0x11d0288800 binds:
    - 12 per-frame ring blocks (0x2c00 bytes, stride 16, at 0x1122a0e640 … 0x1122f6fb40);
    - a constant 1.5-MiB buffer at 0x1162c60000 (stride 4, the same in all 12 dispatches), next to the writers' 256²
      image at 0x1162e60000;
    - small ring constants at 0x11e0…f708/f750.
  - CS 0x11d03ab400 binds 12 small per-frame buffers (0x40, stride 16).
  - Caveats:
    - only the table where `_FIND` matched is dumped, so another table of these passes could still hold the
      arguments;
    - exp 0274's binary (cd17ab79) journals no arguments (0 "draw journal args" lines), so that run's argument bases
      are assumed to equal those of exps 0283–0289, not shown.

**Step B, as run** (the top session's GO of 02:25; W292a 02:25–02:33).
- BC-250, boot 831e5915. Exp 0251's private binary (5227c025), the bench's private save copy, the 3-s dmesg poll and
  the kernel stream.
- Saves c0ee58b92c0cadc2 before and after (snapshot taken and removed, nothing restored).
- Journal: exp 0283's switches plus `_FIND=934d3900,935d3900,93ad3900` and `BC5_DIRECT_FIND_VA=1193400000:1193c00000`;
  both were in the emulator's environment.
- The FIND_VA and `_FIND` lines were grepped into `~/bc5-data/priv/exp0292` (5,507 and 1,590 lines), summarised and
  deleted.
- The box's amdgpu dmesg count was 307 at the start: 50 lines more than at 01:41. They are another session's run at
  about 01:44 (gfxhub page faults of the emulator's Render Thread, a gfx ring reset that succeeded, devcoredump
  `20261025-014442-devcd4.txt`). The count stayed at 307 through W292a.

**Result** (`raw/`).
- **Box state.** W292a had no fault, timeout or reset: 0 fault lines in `raw/W292a.out`, only routine lines in
  `raw/W292a.kern.txt`, no new devcoredump.
- **The lake was clean in all 26 shots** (0.6–1.0 %, `raw/W292a.bench.txt`). Clean runs happen on this binary
  (exp 0266's W266b was clean throughout); most runs on it had a patched phase. Whether FIND_VA's extra work in the
  submission path or chance made this one clean is not known.
- **The argument bases** are those of exps 0283–0289 (`raw/W292a.base.txt`):
  - 0x11935d3900 for most writers (0x11d090d900, 0x11d1d88300, 0x11d29e9c00, …);
  - 0x1193ad3900 and 0x11935d3900 for 0x11d29c…;
  - 0x11934d3900 for the depth-only writer 0x11d373f100.
- **One program gets the bases themselves** (`raw/W292a.fva.txt`). FIND_VA's lines name CS 0x11d0376b00 alone, with
  user data 4:5 holding 0x11934d3900 (929 lines), 0x11935d3900 (504), 0x1193ad3900 (3,932) and a fourth base,
  0x11939d3900 (142). It runs in async-compute (3,784) and graphics (1,723) buffers.
  - Its dispatches are DISPATCH_DIRECT 1 × 1 × 1 (396 `_FIND` hits) and 2 × 1 × 1 (200).
- **Four more programs bind the argument buffers as buffers** (`raw/W292a.vs.txt`, V#s in their descriptor tables):

  | program | DISPATCH_DIRECT groups | V# |
  |---|---|---|
  | CS 0x11d0415700 | 32 | base 0x11935d3900, 4 MiB, stride 4 |
  | CS 0x11d0375600 | 0x61–0x66 (97–102) and 0x451–0x457 (1105–1111) | 0x11935d3900 (4 MiB) and 0x11934d3900 (1 MiB) |
  | CS 0x11d04f0c00 | 5 | 0x11934d3900, 1 MiB |
  | CS 0x11d0288a00 (F310's HTILE fill kernel) | 2752–7168 (by render size) | 0x11934d3900, 1 MiB, at table dwords 0 and 16 |

- **CS 0x11d0375600's group counts vary in the frozen view.** Over W292a's journal windows they take at least 11
  values (0x61, 0x64, 0x65, 0x66, 0x451–0x457; the most frequent 20 dispatch kinds are listed). The counts are set
  by the CPU in DISPATCH_DIRECT, so a CPU-side count over the lake's objects changes from frame to frame in a static
  view.
- **No draw holds the bases in its descriptors.** The writers reach the arguments through SET_BASE only.

**Verdict.**
- **The lake writers' indirect arguments live in 1–4 MiB buffers** at 0x11934d3900, 0x11935d3900, 0x11939d3900
  and 0x1193ad3900. These are prepared by a small chain of compute passes:
  - CS 0x11d0376b00 (1–2 groups) gets the bases in user data;
  - CS 0x11d0415700, 0x11d0375600, 0x11d04f0c00 and F310's 0x11d0288a00 bind them as buffers.
- Which of them writes the arguments is not shown: a descriptor does not say whether a pass reads or writes, and the
  shaders are not disassembled.
- **A lead for the steps of F350/F352:** CS 0x11d0375600's CPU-set group counts change between frames in the frozen
  view. If its output feeds the arguments, a change in that count would change them in the same step.
- W292a's clean lake is noted but not explained.
- **Next:**
  - a run that sets each frame's dispatch counts of CS 0x11d0375600 (the `find ud cs` lines carry the journal time)
    against frame-timed reads of the arguments and holes, as exps 0287/0289;
  - with the maintainer's OK, dropping CS 0x11d0376b00 or 0x11d0375600 (KYTY_BC5_RT_BUILD_PGM-style drop list) to
    see what stops writing the arguments. That is an intervention, and it could fault.
