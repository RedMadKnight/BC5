# 0233 — The night lake: how often it clears, and what a camera nudge does

**Question.** Exp 0232 (F291) found that the lake cleared in the two runs where the title issued a
few more mip requests right after the camera stopped and lowered those textures' `MIN_LOD`. It stayed
patched in the run without them. How often does a run clear? If a patched frozen view gets a small
camera move, does the title make those requests then, and does the lake clear?

**Setup.**
- BC-250 dev box, 2026-10-23 13:02–13:27, granted by the top session. Analysis under a short lock
  13:49–13:53. Boot 31c1a6ac, unchanged; `/var/home` at 69 % before and after.
- `ab0233.sh N1 N2 N3 N4`: four runs of `bench0233.sh`, which is exp 0212's `bench0212.sh` with a
  camera nudge added. Same build and instruments as exp 0232: the exp 0194 build (comm
  `kyty_emulator`), its launcher copy with the old values (no PRT, the old skip list),
  `KYTY_BC5_AMM_TRACE=1`, the water shaders' draw journal, and `DUMPS=1`. The table hashing runs
  once per second; the table dumps come before each shot.
  - Each run lasts 360 s. The first series of frozen-view shots, ts00–ts12, is 5 s apart, as in exp
    0232. Then comes the nudge, scripted pad input through `KYTY_BC5_INPUT_CMD`: right stick left
    for 400 ms, a 1.5 s wait, right stick right for 400 ms, a 1.5 s wait. A second series, ts20–ts32,
    follows. `r-<tag>/nudge.txt` stamps the nudge, which came 66–73 s after the first shot.
  - The driver's checks are exp 0232's: before each run, no lock, no emulator, the same boot and
    `/var/home` under 80 %. During the run it polls `dmesg` every 3 s and stops on any new amdgpu
    fault, timeout or reset line. It checksums the live saves before and after; the bench uses
    only its private copy.
  - The kernel log was also streamed to the laptop (`raw/kernel-stream.txt`). A network drop on
    the laptop cut that stream at 13:13:49, during N2. N2's second half, N3 and N4 ran with the
    driver's own checks only. Their game shots were checked afterwards.
- `ana0233.py` is exp 0232's `ana0232.py`, run on the box because the dumps are the title's memory.
  With `ANCHOR=nudge` it puts time zero at the nudge and compares the ts12 and ts32 table dumps.
  The nudge stamp maps to `CLOCK_MONOTONIC` through `hash.txt`'s wall-clock second, so times
  relative to the nudge are good to about ±1 s.
- The table dumps were grouped by md5 per run (`raw/table-dumps.txt`).

**Result** (`raw/ab.txt`, `raw/N*.bench.txt`, `raw/N*.ana.txt` from the first shot,
`raw/N*.nudge.txt` from the nudge, `raw/table-dumps.txt`).
- **Box state.** All four runs loaded the lake save. No kernel fault, timeout or reset: the box's
  amdgpu count stayed at 578, and each run's `.out` has 0 fault lines. The live saves' checksum was
  the same before and after (f6475842373bf369). The runs wrote about 0.78 GB: run directories
  104–105 MB each and journals 88–90 MB each.
- **N1: patched throughout.** 23–30 % before the nudge, 25–30 % after. The table was byte-identical
  from ts00 to ts12. Within a second of the nudge the title made 4 maps and 6 reads (3.3 MiB) into
  four 2048² textures (fmt 169/170/170/177). It then lowered their `MIN_LOD` from 3 to 1. The lake
  stayed patched.
- **N2: mostly patched, one clean shot.** 9–27 % in the first series, with ts03 clean at 1.1 %.
  - Right after the camera stopped, the title made the late requests of exp 0232: 4 maps and 2.8 MiB
    at +0.8 s. At +1 s it lowered four 2048² textures' `MIN_LOD` from 2 to 1. After that the table
    stayed byte-identical to the end of the run.
  - The lake stayed patched (20 % at ts01) apart from the one clean shot 16 s in.
  - After the nudge: 11–25 %, with no AMM activity and no table change.
- **N3: patched, clean, then patched again, with the same table throughout.** ts00–01 22–23 %,
  ts02–05 0.8–1.0 %, ts06–12 16–26 %.
  - The table dumps ts00–ts12 are byte-identical. The 70 per-second samples from +1 s to the nudge
    show no changed page.
  - AMM activity in that time was the background rate of 1–2 package reads per 5 s.
  - The ts03 (clean) and ts12 (patched) shots show the same view.
  - Within a second of the nudge the title made 3 maps and lowered three clamps: one 2048² fmt 181
    from 4 to 3, and two 1024² (fmt 181/182) from 3 to 2. It stayed patched at 22–30 %.
- **N4: patched throughout.** 22–31 % before the nudge, 23–30 % after. The table was byte-identical
  from ts00 to ts12. Within a second of the nudge, 2 maps, and two 2048² clamps dropped: fmt 182
  from 4 to 2, fmt 177 from 3 to 2. The lake stayed patched.
- **The nudge returned the camera to its framing.** N1's ts12 and ts20 show the same view, with a
  slightly different set of flat cells. The AMM bursts at the nudge in N1, N3 and N4 were the only
  maps in the frozen views after the first seconds, so the input took effect there. N2 has no such
  trace of the nudge.
- **Rate, with exp 0232's three runs (same build and bench, seven runs).**
  - 22 of 91 first-series shots were clean (under 5 %): G2 12, G3 5, N3 4, N2 1, and G1, N1, N4
    none.
  - 1 run of 7 (G2) was clean at the end of its first series.
  - After the nudge, 0 of 52 shots were clean.
- The two other dumped ranges, the water draws' buffers 0x11e04c0000 and 0x11e0c2b000, change
  nearly every second in every run. Whether they changed doesn't tell clean from patched.

**Verdict.**
- **F291's lead is refuted. The title's `MIN_LOD` drops do not decide whether the lake is clean.**
  - Clamp drops without clearing: N2 after the stop, and N1, N3 and N4 at the nudge. That makes four
    of four drops in this series, against exp 0232's two drops that came with clearing.
  - Clearing and going back without any table change: N3 went clean for 20 s and patched again with
    a byte-identical table and no streaming. G2's and G3's clearing a second after a drop may be
    coincidence, since the lake also switches without any drop (N3, and G3's later flips).
- **The camera nudge works as streaming should.** Within a second the title requests finer mips of
  a few large textures and lowers their clamps. It clears nothing: 0 of 52 shots after the nudge.
- **The clean/patched state is set per frame, outside the texture table and the title's
  streaming.** This joins F258/F272's flashes and G3's switches without table change.
- **Open, with a next step:**
  1. What differs on the GPU side between clean and patched frames with the same table. The dumps
     already on the box allow a byte compare of the two per-frame buffers between N3's clean
     (ts02–05) and patched (ts06–12) dumps, and G3's.
  2. What the flat cells sample. That needs a capture of one water draw in a clean and a patched
     frame of the same run.
