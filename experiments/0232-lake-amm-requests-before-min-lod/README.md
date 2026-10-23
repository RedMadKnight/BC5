# 0232 — The night lake: the title's streaming requests around its detail-clamp changes

**Question.** Exp 0212 (F272) found that a patched lake turned clean seconds after the title
lowered some textures' `MIN_LOD` in its bindless table. Exp 0231 (F290) found that the existing
clean/patched journals had no record of the title's requests. With the AMM trace on, what does the
title request before such a drop, and does a run that stays patched lack it?

**Setup.**
- BC-250 dev box, 2026-10-23 12:41–12:56, granted by the top session. Boot 31c1a6ac, unchanged
  through the series; `/var/home` at 69 % before and after.
- `ab0232.sh G1 G2 G3`: three runs of exp 0212's `bench0212.sh` on its default exp 0194 build
  (comm `kyty_emulator`). Its launcher copy keeps the old values: no PRT, the old skip list.
  - Each run: `KYTY_BC5_AMM_TRACE=1`, the water shaders' draw journal, and `DUMPS=1` (a CRC per
    4-KiB page of the texture table every second, the table dumped before each frozen-view shot).
  - Per run the driver checks no lock, no emulator, the same boot and `/var/home` under 80 %.
    During the run it polls `dmesg` every 3 s, stopping on any new amdgpu fault, timeout or reset
    line. The kernel log was also streamed to the laptop.
  - It checksums the live saves before and after; the bench only uses its private copy.
  - The game shot of each run was copied and checked live, for an early stop on a wrong save.
- `ana0232.py` (on the box; the dumps are the title's memory): the AMM maps, unmaps and reads per
  5 s around the first frozen-view shot, and each table change with the AMM events of the 10 s
  before it. Both are on `CLOCK_MONOTONIC`, so they align exactly. It also lists the textures
  whose `MIN_LOD`/`LAST_LEVEL` differ between the first and last dump, with the AMM events in
  their range. The range is approximated by width × height bytes from the base.

**Result** (`raw/ab.txt`, `raw/G*.bench.txt`, `raw/G*.ana.txt`).
- All three loaded the lake save. No kernel fault, timeout or reset. The live saves' checksum was
  the same before and after (f6475842373bf369). The runs wrote about 140 MB each: run directory
  about 62 MB, journal about 70 MB, AMM trace 12 MB.
- **G1, patched throughout (21–27 %).** The streaming burst of the camera move into the view
  (-15 to 0 s: about 110 maps and 100–260 MiB of package reads per 5 s) ended before the first
  shot. The table's last change came at -1 s. No texture's `MIN_LOD` changed during the frozen
  view.
- **G2, patched at the first shot (14.4 %), clean from the next (1.3 %) to the end.** At the first
  shot (±0 s) the title still mapped and read 32 KiB into each of three 1024×2048 textures
  (0x80ae444000 and 0x80ae6f4000, fmt 182; 0x80ae9a4000, fmt 181). At +1 s it lowered their
  `MIN_LOD` from 4.0 to 3.0, the table's last change. Five seconds later the lake was clean.
- **G3, 12–13 % at first, then flipping (1–15 %).** Maps and reads went on to +0.7 s: 8 maps, 10
  reads, 2.9 MiB. Then seven textures' `MIN_LOD` dropped: the same three 1024×2048 ones (4→3), one
  2048² (4→3), and four 2048² ones (fmt 169/170/177, 2→1). The share fell to 1–3 %. Later shots
  went patched again (9–15 % at +42, +57 and +62 s) **with no table change and no AMM activity**.
- In all three, AMM activity in the frozen view after the first seconds was 1–2 package reads per
  5 s, the same as in exp 0205.
- Texture addresses differ per run (G1's table has none of G2's and G3's three), so runs can't be
  compared texture by texture.

**Verdict.**
- **The lead of F272 is strengthened.** In both runs where the title issued a few more mip
  requests right after the camera stopped, the clamps dropped a second later and the lake
  improved: G2 went clean, G3 mostly clean. In the run without them, G1, it stayed patched. Three
  runs, so still a lead.
- **The flashes are a separate effect.** G3 went patched again three times with no table change
  and no streaming, so they are not the clamps (as exps 0205/0212 suggested).
- **Open:** why the title sometimes doesn't issue those last requests (G1), and what the flat cells
  sample. Next steps:
  1. More runs with the same instruments, so the rate is known.
  2. A run that waits longer in the frozen view (`SECS`) and nudges the camera after a while, to
     see whether a camera change makes a patched run request and clear.
