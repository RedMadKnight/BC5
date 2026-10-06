# 0025 — The second level: where the frame goes, and what the shaders are made of

**Question.** The second level runs at 35–43 fps with jobs in flight (experiment 0024, run 116)
where the first runs at 47–55. Is the difference the GPU's own time or the host's? And, for the
question which other hardware could take the game's stream untranslated (README, "Why the
BC-250"): which instructions do the game's shaders actually use?

**Setup.** BC-250 dev box, 2026-10-06, as experiment 0024 but on the synchronous path
(`BC5_DIRECT_ASYNC` unset), so that the wait for each submission's fence is the GPU's own time,
and with `BC5_DIRECT_SHADER_DUMP=1`. The maintainer at the controller, from the saved game through
the first level into the second; stopped by the maintainer after 740 s. **The box had come up from
a cold start with 6 cores / 12 threads**: the 8-core unlock sets a mask that a warm reboot keeps and
a cold boot loses, and the service only re-arms it for the next reboot (HANDOFF D13). Runs 100–116
ran on 16 threads (the journal of those boots says so); this one did not. Capture
`kytyplus-20261006-1617`, `raw/run117-summary.txt`.

**Result, frame time** (run 117: 375,063 submissions, none failed, no wait timed out, no
controller disconnect in 12 minutes).

| Per frame, synchronous | First level, 210–265 s | Second level, 300–570 s |
|---|---|---|
| frames per second | 48.3 | 27.4 |
| frame | 20.7 ms | 36.4 ms |
| GPU (fence waited for) | 12.9 ms | 18.6 ms |
| host, inside the submit path (prepare, CS ioctl, sync, hints) | 3.3 ms | 7.1 ms |
| outside the host's path (the game's own work, the flip) | 3.2 ms | 8.8 ms |
| submissions a frame | 16 | 16 |

The second level is heavier on every side: the GPU needs 18.6 ms a frame (54 fps at best at this
clock, 1850–2000 MHz), the host's pass over the buffers takes twice as long (the frame's main
buffer is 25,000 dwords; `prepare` alone is 3.5 ms), and the game's own thread needs 8.8 ms between
submissions — on 6 cores. With jobs in flight (run 116) the same level took 23–28 ms a frame, so
there the GPU's 18.6 ms and the CPU side's roughly 16 ms overlap but neither hides the other fully.

**Result, shader census.** 485 shader programs were dumped (32 KiB windows from each program's
address; 281 end in `s_code_end`, 204 run to the window's end, so their counts may include what
follows the program). Disassembled with `llvm-objdump --mcpu=gfx1013` (LLVM 21):

| Instruction | Occurrences | Shaders using it (of 485) | Exists on |
|---|---|---|---|
| `v_mad_f32`, `v_mac_f32`, `v_madak_f32`, `v_madmk_f32` | 225,219 | 449 | GFX10.1 only — removed in GFX10.3 (RDNA2) |
| `v_mac_legacy_f32`, `v_mad_legacy_f32` | 8,159 | 333 | GFX10.1; the same opcodes are `v_fmac_legacy`/`v_fma_legacy` on GFX10.3 |
| `s_scratch_*`, `s_atomic_*`, `s_store_*` | 852 | 246 | GFX10.1 only |
| `image_msaa_load` | 85 | 69 | gfx1013 and GFX10.3 — **not** Navi 10/12/14 |
| `image_bvh*` (ray tracing) | 0 | 0 | — |
| `v_mul_lo_i32`, `s_get_waveid_in_workgroup`, `ds_*_src2` | 0 | 0 | — |
| `v_fma_f32`, `v_fmac_f32` | 7,530 | 336 | all GFX10 |

Sources for the right-hand column: LLVM `AMDGPU.td` (`FeatureISAVersion10_1_Common`,
`10_1_3`, `10_3_0`), Mesa `aco_opcodes.py` and `ac_gpu_info.c` (`has_mad32`), read 2026-10-02.

**Verdict (2026-10-06).** Answered on both counts. (1) The second level's rate is first the GPU's
own time — 18.6 ms a frame, which caps it at about 54 fps — and then the CPU side, which with jobs
in flight is roughly 16 ms of host pass and game work on the critical path; 60 fps needs both
below 16.7 ms. The next levers are the host's `prepare` pass over large buffers (3.5 ms) and the
GPU clock; the measurement should be repeated on 16 threads. (2) The game's shaders use, in
practically every program, the multiply-add instructions that RDNA2 removed, and in 69 of 485
programs an instruction Navi 10/12/14 lack. For this title the untranslated path exists on
gfx1013 and nowhere else; every other GPU means rewriting shader binaries.
