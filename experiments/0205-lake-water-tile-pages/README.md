# 0205 — The night lake's flat cells: the water's streamed tiles while the patches show

**Question.** Exp 0201 (F261) found that the water's pixel stage samples two sparse textures that
the host streams tile by tile into the AMM window, and that a flat cell is most likely a tile
sampled while empty. While the patches grow in a frozen view, are those tiles mapped with data
(then the GPU sees stale memory), or do they turn into holes, zero pages or re-maps (then the title
evicts them and the data comes back late or never)? And does a faster APR read path (the cutscene
session's `KYTY_BC5_APR_READAHEAD`, F259) change the patch share?

**Setup.**
- BC-250 dev box, 2026-10-22 16:45–19:10, boot ac5dab11 (kernel 7.2.9-ogc3.1, exp 0204), every
  run granted by the top session (the box supervisor) and holding `~/bc5-work/BOX-LOCK`. Runs:
  X5 (17:07), A1/B1 (17:22), B1b and S2 (18:11), B2/A2/A3/B3 (18:25–18:45), S2b (19:02). No
  run raised a kernel fault, timeout or reboot.
- The exp 0194 bench with its private copy of the maintainer's lake save; the live saves are never
  touched. Binaries:
  - the exp 0194 diagnostic build (the bench default: X5, S2, S2b);
  - the cutscene session's exp 0203 build with `KYTY_BC5_APR_READAHEAD` (v1 at 17:03, v2 at
    17:54; off by default): the A/B runs;
  - the TCP session's runs on the shared build, scored here.
- `bench0205.sh`: exp 0201's `bench0201.sh` (box lock, shot series, `ROUTE`/`SLOTWAIT`/`LOADWAIT`)
  plus `PAGES=1`, which runs `pg0205.py` for the whole run into `r-<tag>/pages.txt`.
- `pg0205.py`: a read-only outside sampler, no ptrace attach. Every 5 s, at nice 10, it preads the
  emulator's memory through `/proc/<pid>/mem` (yama `ptrace_scope` 0, as exp 0200's sampler) and
  reads `/proc/<pid>/maps`.
  - Ranges: 8 MiB at 0x8492504000 and 2 MiB at 0x80907c4000, the two pixel-stage textures of PS
    0x11d01ff900 (exp 0201 X2), as 640 tiles of 16 KiB (the smallest automatic AMM map).
  - Per tile: `.` a hole (no readable VMA: the AMM window's holes are `---p` anonymous), `z`
    mapped and all zero, `d` mapped with data. A mapped tile is a `rw-s` VMA of
    `/memfd:KytyDirectMemory` whose file offset is the dmem offset; a changed offset is counted
    as a re-map.
  - The host maps automatic AMM pages at the title's address (`KernelMapDirectMemory2` at
    `command.va` in `libAmpr.cpp`), so the CPU view is the one the APR reads write.
  - Dry-tested on a `sleep` process (heap range: one `d`, one `z` tile).
  - `PAGES_RANGES="<hex base>:<hex size> ..."` in the bench overrides the ranges.
- `ana0205.py`: the samples against the shots' patch share, and the tile maps of the frozen view.
- `amm0205.py`: from a play log's AMM trace, maps, unmaps and reads per 10 s, and whether every live
  automatic map was filled by a later read.
- `res0205.py`: a texture's residency per mip and block, from its descriptor fields and a
  `pg0205.py` tile map or an AMM trace. It uses the gfx10 layout from Mesa's addrlib (laptop
  sparse clone `refs/mesa_mesa` @ ab2374a, cited in the script), with a self-test against
  layouts worked out by hand.
- `s2-0205.sh`: run S2. The bench with the water shaders' journal and `KYTY_BC5_AMM_TRACE=2`
  (one `amm trace: call <function>` line per AMM library call). Afterwards it copies the log,
  decodes the descriptors and counts the calls of the two suspect functions of
  `raw/review-3b.txt`.
- `desc0205.py`: the image descriptors in a shader's journalled user data, decoded, with the
  `res0205.py` arguments for each. Tested on X2's journal, where it reproduces exp 0201's
  descriptors.
- Drivers: `ab0205.sh` (A/B runs, one lock each, stops on a kernel line or a failed bench),
  `b1b-s2.sh`, `part2.sh`. The repo copies differ from the box's only in their header comments.
- The patch share is exp 0197's `patch0197.py` (clean 1–2 %). Every run's view was checked on
  its first frozen-view shot. A camera that lands at another angle can score wet rock as
  patches (B3), and an open Photo Mode menu adds its pixels (S2b).

**Result.**
- **tcpW1** (the TCP session's run on this bench, shared build, `raw/tcpW1-observation.txt`): the
  same frozen view at 23–31 %. The patchwork is not specific to the diagnostic builds.
- **X5** (17:07–17:12, the exp 0194 build, launcher defaults, `raw/X5.txt`): the lake view, patch
  share 18–23.5 % in the 66-s frozen view, no growth.
  - Of the 2048² texture's 8 MiB at 0x8492504000, 512 tiles were holes until the load. 21 tiles
    were mapped at 17:08:40, zero, and held data 15 s later. 7 more were mapped with data at
    17:09:45. From then to the end: 484 holes, 28 data, 0 zero, no re-map.
  - The 512² texture's 2 MiB range: 102 data, 26 holes from 17:09:10 on, unchanged.
  - So nothing changes on the CPU side while the patches show, and no mapped tile is still empty.
    The reading then was that the flat cells are holes, or data the GPU does not see. S2b refutes
    it (below): this range was not the texture in X5.
  - Caveat: the shader journal did not run (`BC5_DIRECT_DRAW_JOURNAL_PS` needs
    `BC5_DIRECT_DRAW_JOURNAL`), so the addresses are X2's, not re-read in this run.
- **tcpW1's AMM trace** (`raw/tcpW1-observation.txt`, `raw/tcpW1-amm.txt`, `amm0205.py`): through
  the whole patchy frozen view the title made no map and no unmap, and 2–3 reads per 10 s. Every
  streamed map (prot 0x90) still live at the end, 9,289 maps / 1,962.6 MiB, was filled by reads
  logged after it, and every map, unmap and read returned 0. The host served everything the title
  asked for, so the missing surface is in tiles the title did not ask for.
- **A1/B1, the readahead A/B part 1** (`raw/A1-B1.txt`), on the cutscene session's binary:
  - A1, switch off: 6.3–14.8 %. The 2048² texture's range at X2's address held 8 data tiles
    (X5: 28), so that address probably moves between runs. The two vertex-stage maps stayed all
    zero from the title to the end. "AMM" views are imported eagerly as the same pages (ADR 0006),
    so the GPU wrote nothing non-zero there; whether that is wrong is open.
  - B1, `KYTY_BC5_APR_READAHEAD=4`: the emulator crashed on the host at 16 s, writing into an
    unmapped AMM address (a readahead copy ahead of its map). No result for B.
- **B1b, arm B again on the v2 binary** (`raw/B1b-S2.txt`; 12 reader threads, no crash):
  - The frozen lake was clean (0.9–1.1 %) in 9 of 13 shots. A full checkerboard flashed in
    one shot (25.4 %) and partial ones in three (10–14 %), each gone within about 5 s.
  - No sampled tile changed state meanwhile, so the flashes are a per-frame GPU-side effect.
  - Against A1's 6.3–14.8 % in every shot that is a clear move, but one run per arm.
- **The A/B part 2** (`raw/part2.txt`; B2, A2, A3, B3 on the v2 binary, views checked):
  - A2 and A3, switch off, were clean in all 26 shots. B2 showed a checkerboard in its first three
    shots and was clean after. B3 landed at another camera angle; its water looks clean, but its
    8 % score is wet rock inside the metric's window.
  - Over both parts, arm A had 26 of 39 shots clean and arm B 19 of 26. **No effect of the
    read-ahead:** each arm has clean runs and patchy runs, and the run-to-run spread swamps the
    difference.
  - At X2's address, the 2048² BC4 texture's layout was fully resident in the two clean runs A2
    and A3. In patchy X5 its mips 1 and 0 were missing. That suggested "a flat cell is a page the
    title did not stream"; S2b refutes it (below).
  - The AMM pool the title gives is the same 0xbda00000 bytes in every logged run.
- **The given-up game-thread waits** (F263–F265) do not make the steady patchwork
  (`raw/tcp-runs-water.txt`). The TCP session's four runs on this bench, scored for the water:
  - 8 ms limit: tcpW1 (17 give-ups) 27.7 %, tcpW1b (12) 22.6 %.
  - 100 ms limit: tcpW2 (1) 26.5 %, tcpW2b (0) 22.0 %. tcpW2b had no give-up in 600 s and was
    patched in every shot.
  - Flashes go both ways: in tcpW1b one shot of the patched bench view was fully clean.
  - Nor do they explain the flashes (`raw/flash-giveups.txt`; give-up times from the TCP
    session, exp 0209 `raw/giveups-wall-tcpW1b-B1b-B2.txt`). One of three clean-to-patched onsets
    has a give-up 2–7 s before it, and B2's first patched shot coincides with one. None of the
    four patched-to-clean ends has a give-up near it.
- **S2** gave no residency result. Its tag reused exp 0194's run directory `r-S2`; a stale input
  counter sent the slot keys early, and the game loaded an outpost. The bench now refuses a used
  tag, and the rerun is S2b.
  - Box files of exp 0194 overwritten by S2, from its run S2 of 11:08: `~/bc5-work/exp0194/r-S2/`
    `emu.log`, `env.txt`, `input.cmd`, `input.cmd.done`, `journal-dir.txt`, `launcher.out` and
    `dmesg.txt`. Its `wj.txt` and the shots `t050`–`t180` remain. Nothing committed depends on
    them: exp 0194's README sums up S1–S4 as runs that never reached the lake.
  - Its level-2 AMM trace did show the title never calling `AmmGetUsageStatsData` or
    `AmmSetPageTablePoolOccupancyNotificationThreshold` in 4.5 min of active streaming
    (`raw/B1b-S2-ana.txt`).
- **S2b, the residency test** (`raw/S2b.txt`). The lake was heavily patched in all 13 shots;
  Photo Mode's menu stayed open over the left half, so the scores of 17–26 % include menu pixels.
  - The journal put the 2048² BC4 texture at 0x8495c84000 in this run, not at X2's address.
  - The AMM trace shows it loaded whole: one map of its full 0x2ac000-byte chain, one package read
    of the same size about 4.5 s later, never unmapped. That was more than a minute before the
    frozen view.
  - The 512² texture was fully resident too.
  - So **the patchwork is not missing pages of the pixel-stage textures**. The tile-by-tile
    streaming seen near X2's address in X3, X5, A2 and A3 was other data, or the texture loaded
    whole at that address.
  - The vertex-stage maps were all zero here, as in the clean runs A2 and A3, so they don't tell
    clean runs from patched ones.
  - The title made no call to the two AMM stubs on this lake run either.
- **The water's textures, decoded** (`raw/formats.txt`, Mesa `gfx10-rsrc.json` @ 0866ae7):
  - Pixel stage: 2048² `BC4_UNORM` with 8 levels (2.7 MiB) and 512² `16_FLOAT` with 7 levels
    (0.7 MiB), both single-channel and loaded from the package. The samplers' 8 MiB / 2 MiB
    windows were wider than the textures.
  - Vertex stage: 2048² `16_FLOAT` and 512² `16_16_16_16_FLOAT`, one level each, exactly the size
    of their GPU-only automatic maps. These are the two maps that stayed all zero in A1.
  - Swizzle modes: 5 = `ADDR_SW_4KB_S` (pixel stage), 27 = `ADDR_SW_64KB_R_X` (vertex stage)
    (addrlib `inc/addrtypes.h` @ ab2374a).
  - A side lead, TODO(verify): a missing writer for the two vertex-stage maps. A simulation at
    rest would still write its rest state, typically non-zero for an RGBA16F map. But the maps are
    all zero in clean runs too (A2, A3), so a missing writer would not explain the patchwork.
- **Residency at X2's addresses** (`res0205.py`, `raw/residency-X5-A1.txt`):
  - The 512² `16_FLOAT` texture is fully resident in every mip in X5 and A1, from the title on.
  - The 2048² BC4 texture in X5: mips 4 and 3 resident, mip 2 half, mips 1 and 0 not at all. That
    is the shape of a sparse texture.
  - In A1 the same range held 8 scattered mip-0 blocks and no low mips. That does not look like
    this texture, which fits the address moving between runs.

**Verdict.**
- **Narrowed further, not named.** The night lake's patchwork is not a missing input the host
  failed to serve. Ruled out here:
  - missing pages of the water's pixel-stage textures: both were fully resident through a
    patched frozen view (S2b);
  - the host's AMM map, fill and ordering: every streamed map was filled, every call returned 0
    (tcpW1);
  - the APR read speed: no effect of `KYTY_BC5_APR_READAHEAD` in 3 runs per arm;
  - the given-up game-thread waits (F263–F265): steady patches with none at all (tcpW2b), and no
    consistent link to the flashes;
  - the AMM usage-stats and occupancy-threshold stubs: never called;
  - the two vertex-stage maps: all zero in clean and patched runs alike.

  Exp 0201 had already ruled out the shared zero buffer, and exps 0194/0197 the GPU check, the
  `COND_EXEC` fallback, chains, DMA snapshots and the AMM zero-fill.
- **What the runs show.** Whole runs come out clean (A2, A3) or patched (A1, X5, S2b, tcpW1,
  tcpW1b, tcpW2, tcpW2b), from the same save, bench and binaries. Within one frozen view the
  patchwork can also switch on or off within seconds (B1b, B2, tcpW1b). No sampled memory changes
  meanwhile, and the AMM side is idle. So the cause is state chosen per run, plus something that
  varies from frame to frame on the GPU side.
- **The read-ahead is not a water fix.** Its own case (the clock voice, F259/F267) is unaffected.
- **Next.** The inputs of the water's two draws not yet looked at:
  - the buffer at 0x11e0007aa0 (V#: stride 32, 25,534 records), which both stages of PS
    0x11d01ff900 read, and the per-draw pointers next to it (0x11e04cc…, changing per draw);
  - the three 16-byte-record buffers of the full-screen pass PS 0x11d01d7100.

  A read-only run would hash them per sample in a clean and a patched frozen view. It would show
  whether they are GPU-written each frame and whether they differ. `pg0205.py` would need a
  content hash per tile for that.
- Nothing of this is in patch 0001 or the shared build. The bench and drivers write only under
  `~/bc5-work/exp0205` and the shared run directories `~/bc5-work/exp0194/r-<tag>`.
