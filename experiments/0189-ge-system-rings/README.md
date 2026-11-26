# 0189 — The rings the console's system programs: the second title's TF ring reaches the host by /dev/gc and was never programmed

**Question.** The second title's geometry engine reads pages in the first 64–256 KiB of the address
space (F207/F208: client GE2, a stream in the night scene), and its ray-traced reflections stay
skipped (F234: 0x11d049aa00, 0x11d04a6000, 0x909974400). The review of 15 analogous projects
(`docs/ports/related-projects-review.md` §7) named three GPU registers the console's system sets
and our host may leave at 0: the tessellation-factor ring (`VGT_TF_RING_SIZE`,
`VGT_TF_MEMORY_BASE(_HI)`), `VGT_HS_OFFCHIP_PARAM`, and `GE_PC_ALLOC`. Does any of them explain
the address-0 reads, and does fixing it let the reflections run without the skips?

**Setup.**
- BC-250 dev box, 2026-10-21 from 17:30. Host: kernel 7.2.9-ogc3.1, Mesa 26.2.4, libdrm 2.4.134;
  the `ubuntu` distrobox the emulator runs in: Mesa 26.0.8 (RADV), libdrm_amdgpu 2.4.131.
  KytyPlus `f266548` with patch 0001 as committed in `8c0f80c` plus the two scripts here
  (`patch_0189.py`, `patch_0189b.py`), built with
  `distrobox enter ubuntu -- cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8`
  and synced to disk before each run (D16). Backups of the sources and the previous binary:
  `~/bc5-work/exp0189/*.before0189`.
- Runs: `run-0189.sh <tag> [secs]` (here): the idle night run of exp 0185–0188 (slot 1 loaded by
  `idle-cmd.txt`, no input afterwards), the switches in `ENVX`, the saves restored from
  `~/bc5-work/save-backup-0180-0953` before and after. It summarises the kernel log of the run
  (GPU page faults by client and page, 5-s windows, ring timeouts/resets), the direct journal
  (fence timeouts, flips per 10 s) and the new trace lines. Raw output per run in `raw/`.
- Register offsets and fields: Mesa's gfx10 register JSON (`tools/bc5-agc/regdb/gfx10.json`):
  `VGT_TF_RING_SIZE` 0x30938 (uconfig 0x24e, SIZE bits 0–15 in dwords), `VGT_HS_OFFCHIP_PARAM`
  0x3093c (0x24f; OFFCHIP_BUFFERING bits 0–8, OFFCHIP_GRANULARITY bits 9–10 on gfx10.1),
  `VGT_TF_MEMORY_BASE` 0x30940 (0x250), `VGT_TF_MEMORY_BASE_HI` 0x30984 (0x261), **`GE_PC_ALLOC`
  0x30980 (0x260)**, `GE_STEREO_CNTL` 0x3097c (0x25f), `VGT_SHADER_STAGES_EN` 0x28b54 (context
  0x2d5; LS_EN bits 0–1, HS_EN bit 2), `VGT_LS_HS_CONFIG` 0x28b58 (0x2d6), `VGT_TF_PARAM` 0x28b6c
  (0x2db).

New switches (patch 0001):

| Switch | Kind | What it does |
|---|---|---|
| `BC5_GC_IOCTL_TRACE=1` | diagnostic | the first 8 calls of each `/dev/gc` request code to stderr, with the bytes passed in |
| `BC5_DIRECT_REG_CENSUS=1` | diagnostic | per submitted buffer, the stage/tessellation/`GE_PC_ALLOC` state in force at each draw and every write of the ring registers (SET and LOAD_*_INDEX tables), cumulative counts to stderr every 60 s |
| `BC5_DIRECT_TF_DEFAULT=1` | behaviour | a host TF ring (256 KiB guest flexible memory at 0xff0000000, AnyPS5's system default) programmed when the title gave none; `_SIZE`, `BC5_DIRECT_HS_OFFCHIP=<hex>` |
| `BC5_DIRECT_OFFCHIP_SECOND=1` | behaviour | `VGT_HS_OFFCHIP_PARAM` from the HLE `SetHsOffchipParam`'s second value (ps5-vulkan's reading) |
| `BC5_DIRECT_GE_PC_ALLOC=<hex>\|radv` | behaviour | `GE_PC_ALLOC` in every prefix (`radv` = 0x1ff) |
| `BC5_DIRECT_GC_TF_RING=1` | behaviour | the TF ring the title's own driver sends `/dev/gc` (ioctl 0x80108128) programmed in the prefix |
| `BC5_DIRECT_GC_HS_OFFCHIP=1` | behaviour | `VGT_HS_OFFCHIP_PARAM` from the dword of ioctl 0x8004812a |

Also: HLE `GraphicsDriverGetTFRing` / `GetHsOffchipParam` registered (NIDs `e-YMQ+2tj9M`,
`r28hEh6cNH0`); the one-register `SET_UCONFIG_REG` packets of exp 0160's TF-ring prefix fixed
(see Result); the timeout probe prints `GE_STEREO_CNTL` and `GE_PC_ALLOC` under their names.

| Run | Switches (skips 11d049aa00, 11d04a6000, 909974400 unless said) | Length | GPU faults | Fence timeouts / ring resets | Night flips per 10 s |
|---|---|---|---|---|---|
| R0 | `IOCTL_TRACE`, `REG_CENSUS` | 300 s | 360 records, client GE2, pages 0x0–0xf000, t 124–300 s | 0 / 0 | 280–296 |
| R1 | R0 + `GC_TF_RING` | 300 s | 0 | 1 / 1 at t 122.5 s | stops at t 121 |
| R2 | R1 + `GC_HS_OFFCHIP` (0x1ff) | 300 s | 0 | 1 / 1 at t ≈ 121 s | stops |
| R3 | `GC_TF_RING`, shader dump | 160 s | 0 | 1 / 1 | stops |
| R4 | `GC_TF_RING` (root watcher armed at +100 s; it wrote nothing) | 160 s | 0 | 1 / 1 | stops |
| R5 | `GC_TF_RING`, `UCONFIG_FORCE=260:1ff` (GE_PC_ALLOC past the title's own writes) | 160 s | 0 | 2 / 2 | stops |
| R6 | `GC_TF_RING`, `UCONFIG_FORCE=24f:5f` (RADV's offchip value), wave dump at the stall | 160 s | 0 | 2 / 2 | stops |
| R7 | `GC_TF_RING`, `REG_CENSUS`, skips + **11d04bb900** | 300 s | **0** | **0 / 0** | 228–293 |
| R8 | R7 + `GC_HS_OFFCHIP` (0x1ff) | 300 s | **0** | **0 / 0** | 219–293 |
| S1 | `GC_TF_RING`, skips 11d049aa00, 11d04a6000, 11d04bb900 (**compaction 909974400 runs**) | 160 s | 0 | 2 / 2 at t ≈ 130 s | stops |
| S2 | `GC_TF_RING`, skips 11d04a6000, 909974400, 11d04bb900 (**11d049aa00 runs**) | 160 s | 0 | 2 / 2 at t ≈ 35 s (start screen) | stops |
| S3 | `GC_TF_RING`, skips 11d049aa00, 909974400, 11d04bb900 (**11d04a6000 runs**) | 480 s | 0 | 2 / 2 at t ≈ 130 s | stops |

Raw: `raw/runs.txt` (all runs; R1/R2's journal excerpts were taken before the script grepped
the host's upper-case `TIMEOUT`, their journals have one each, #141990 and #138597),
`raw/R0-ioctl-trace.txt`, `raw/R0-census.txt`, `raw/R0-dmesg-first.txt`, `raw/R3-timeout-probe.txt`,
`raw/R3-devcoredump-gfx.txt`, `raw/R6-waves.txt`, `raw/R6-traversal-dispatch.txt`,
`raw/R7-census-last.txt`, `raw/R8-census-last.txt`, `raw/S1-waves.txt`, `raw/S2-traversal-dispatch.txt`,
`raw/S3-waves.txt`. S1–S3 ran on the maintainer's yes (2026-10-21, relayed by the session that started this one). The title's shader code and its disassembly
stay on the box (`~/bc5-work/exp0189/dis-*.txt`, `~/bc5-data/captures/exp0189-shaders/`).

**Result.**
- **The title does set a TF ring and an offchip parameter, through `/dev/gc`, and the host
  dropped both (R0).** Its `libSceAgcDriver` runs LLE from the module pack, so the HLE
  `GraphicsDriverSetTFRing` / `SetHsOffchipParam` hooks of exp 0160 never see its calls; that
  is why no log ever had a `[bc5-tess]` line (217 run logs on the box), and F208's "the title
  never calls SetTFRing" was not established. The ioctl trace shows, once each and before the
  first submission: `0x80108128` (16 bytes in) = {u64 0x1120000000, u32 0x3fff8, 0} (by its
  shape the arguments of `sceAgcDriverSetTFRing`: a 256 KiB ring) and `0x8004812a` (4 bytes in)
  = 0x1ff (sent right after it; by its place the HS offchip parameter, TODO(verify) which
  register value it is). The host's ioctl handler answered both as unhandled: nothing was
  programmed. No GetTFRing-shaped request follows.
- **The night scene tessellates, and its draws began exactly where the GE2 stream begins (R0).**
  The census finds 4,815 `DRAW_INDEX_2` with `VGT_SHADER_STAGES_EN` 0x0200210d (LS and HS on,
  ES = domain shader, NGG primitive generator, dynamic HS), `VGT_LS_HS_CONFIG` 0x1043f (63
  patches, 4 control points in and out), `VGT_TF_PARAM` 0x4004e (triangles); none in the first
  two 60-s reports, then from the third, whose window holds the first fault at t 124.2 s. All
  other draws are NGG (fast launch 0x482030, pass-through 0x02002000/0x02402000). The title never
  writes `VGT_TF_RING_SIZE`/`VGT_HS_OFFCHIP_PARAM`/`VGT_TF_MEMORY_BASE(_HI)` itself. So the GE
  fetched the patches' factors through `VGT_TF_MEMORY_BASE` = 0 (the faulting pages are offsets
  inside the title's 256 KiB ring; above 64 KiB the host's zero pages answered, F208), read
  zeros, and culled every patch.
- **Exp 0160's TF-ring prefix never wrote the base.** Its one-register `SET_UCONFIG_REG` packets
  for `VGT_TF_MEMORY_BASE` and `_HI` had the header 0xC0007900 (COUNT 0: an offset and no value;
  PKT3 COUNT is the body's dwords minus one, Mesa's `PKT3()` and its `radeon_set_uconfig_reg`).
  The CP wrote nothing, and the value dword parsed as a type-0 header, which the filter drops
  (`pm4-policy.tsv`: type0 drop) together with the next five dwords, the first two of the title's
  buffer. Run 770's "the TF base is not the register the GE reads" therefore tested nothing; its
  earlier fault came from the corrupted stream. Fixed (COUNT 1).
- **With the title's ring programmed (`BC5_DIRECT_GC_TF_RING=1`) the GE's address-0 reads are
  gone (R1–R8: 0 fault records), and the GE really tessellates.** At the R3/R4 timeouts the ring
  holds 59,520 non-zero dwords up to dword 63,162 of 65,534, sane factors (1.15–2.0), written by
  the HS. But the first buffer with tessellated draws (t ≈ 121.5 s) then times out every time
  (R1–R6). The device coredump at the hang (R3): `GRBM_STATUS` 0xa0403028 = SPI busy, CP busy,
  GE idle. The wave dump 0.7 s into the stall (R6, `umr -O halt_waves -wa` triggered by the
  journal standing still): **all 80 waves are in compute program 0x11d04bb900 at +0x1a34–0x1aa0**,
  74 of them with EXEC = 0 on an `s_cbranch_execz` of a BVH traversal stack loop (node-type
  tests, a link buffer, an LDS/scratch stack; the program holds BVH intersection instructions).
  It is dispatched (`DISPATCH_DIRECT`) inside the same graphics buffer. A fourth variant of the
  reflection traversal, then, with the F113/F234 loop, reached once the tessellated surfaces are
  drawn, **with the compaction 0x909974400 still skipped**.
- **Not the offchip value, not `GE_PC_ALLOC`.** The stall is identical with
  `VGT_HS_OFFCHIP_PARAM` left as the GPU had it (R1, R3, R4), the title's 0x1ff (R2), RADV's
  0x5f for this chip (R6, `ac_gpu_info.c:1395-1450`: 96 workgroups of 32 KiB on 2 SE × 2 SA × 6 CU),
  and with `GE_PC_ALLOC` forced to RADV's 0x1ff past every write (R5).
- **With that variant skipped too, the night scene runs clean with tessellation (R7, R8):** 300 s,
  0 faults, 0 timeouts, no ring reset, 4,769/4,793 tessellated draws, 28–29 flips/s in the night
  as in R0. The title's offchip value 0x1ff is harmless (R8).
- **`GE_PC_ALLOC` is the title's, not the system's (lead 3).** It is uconfig **0x260**
  (0x30980, Mesa's gfx10 register JSON); 0x25f, which the review and our journal labels named, is
  `GE_STEREO_CNTL`. The title writes 0x260 = 0 itself in nearly every buffer (R0: 118,102 SET and
  212,390 LOAD_UCONFIG_REG_INDEX table writes, all 0), after any prefix; forcing 0x1ff (R5)
  changes nothing.
- **Lead 2 cannot be checked as stated**: there are no `[bc5-tess] SetHsOffchipParam` lines for
  this title (LLE driver). Its only offchip datum is the 0x1ff of ioctl 0x8004812a; whichever
  reading (first/second value) is right, 0x1ff, 0x5f and the GPU's own value behave the same here.
- The root watcher `bc5-gpu-hang-watch` armed for R4 caught nothing during a 2-s stall that the
  kernel reset at 18:26:56 (it watches `amdgpu_fence_info`, which a user cannot read to see why);
  the journal-stall trigger (`stall-waves.sh`) worked in R6 and the box recovered (per-queue ring
  reset, "Ring gfx_0.0.0 reset succeeded", after each of the eight timeouts of R1–R6). No halt_waves outside R6.
- **Removing the skips one by one, with the TF ring on (S1–S3, the maintainer's yes): every
  removal hangs in the traversal loop.** S1 (the compaction 0x909974400 runs): the night scene
  stalls at t ≈ 130 s, the waves (27) at +0x1298–0x1480 of 0x11d040e200, F234's run-836 variant and
  loop. S2 (0x11d049aa00 runs): the stall comes at t ≈ 35 s on the start screen, before any
  tessellation; the timed-out graphics buffer holds that program's `DISPATCH_INDIRECT` (the
  trigger was not armed that early; the compute ring stalled behind it, F109). S3 (0x11d04a6000
  runs): 228 waves at +0x1cfc/+0x1d50 of 0x11d04a6000, the PC F232 found (0x11d04a7cfc), now at the
  start of the night instead of 5–6 min into it. The kernel's per-queue ring reset recovered all
  six; the box stayed up; the saves were restored after each run.

**Verdict.**
- **Lead 1 (TF ring): confirmed, in a different form than the review proposed.** F207/F208's
  address-0 reads were the geometry engine fetching tessellation factors through a
  `VGT_TF_MEMORY_BASE` the host never programmed. The console's system does program it, but from
  the ring the title itself sends `/dev/gc` (ioctl 0x80108128), not from a system default ring;
  `BC5_DIRECT_GC_TF_RING=1` does that, removes the faults and makes the night scene's tessellated
  patches visible (they were all culled). A host default ring (`BC5_DIRECT_TF_DEFAULT`) is not
  needed by this title. Exp 0160's ring prefix had a packet bug, now fixed.
- **Lead 2 (offchip parameter): no effect here.** The title's driver sends 0x1ff (ioctl
  0x8004812a, `BC5_DIRECT_GC_HS_OFFCHIP=1`); it, RADV's 0x5f and the GPU's leftover value behave
  the same. Its exact meaning stays TODO(verify).
- **Lead 3 (`GE_PC_ALLOC`): ruled out.** Wrong offset in the review (0x260, not 0x25f), and the
  title writes the register itself; forcing RADV's value changes nothing.
- **The ray-traced reflections do not run again.** With the TF ring right, the tessellated
  surfaces send a fourth traversal variant (0x11d04bb900) into the F113/F234 loop even with the
  compaction skipped, and each of the three skips, removed alone, hangs in the same loop
  (0x11d040e200 with the compaction on; 0x11d049aa00 on the start screen; 0x11d04a6000 in the
  night). The GPU-side system state of the review is not the reflections' cause; the traversal
  loop is (F113–F116, F184, F234), and it is now the one open lead for the reflections.
- Stable configuration found: `BC5_DIRECT_GC_TF_RING=1` with 0x11d04bb900 added to the skips
  (R7, R8: no faults, no timeouts, tessellation drawn, frame rate unchanged). It stays off by
  default; turning it on in the launchers is the maintainer's call.
