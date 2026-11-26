# PHASES — roadmap with gates

Each phase ends with a gate: an experiment whose recorded result decides whether the next phase starts. A gate is "passed" only when an `experiments/NNNN-*/README.md` says so with evidence. No dates.

## Where the roadmap stands (table of 2026-10-24; checked 2026-11-24, no gate has changed)

| Phase | Gate | State |
| --- | --- | --- |
| 0a — `bc5-mount` | G0a | **Passed** (experiment 0002) |
| 0b — RPCSX baseline | G0b | **Retired** by D18 / ADR 0012 (no firmware boot); tasks 1–2 done (0003, 0006) |
| 1b — track B, Sony's `libSceAgc` in KytyPlus | G1b | **Passed** (0011, 0012) |
| 1 — AGC decoder and tap | G1 | Not recorded as a gate; its substance was shown on track B (0011: Sony's frames decode with zero unknown opcodes); the RPCSX tap is retired by D18 |
| 2 — native shaders | G2 | **Passed** (0013, 0014) |
| 3 — direct submission | G3 | **Passed** (0016) |
| 4 — integration into RPCSX | G4 | **Retired** by D18; its aim, a game through the native path, was reached on track B instead (F85: the first title fully playable) |
| 5 — play: both titles on the direct path | G5 (proposed) | **Current**; since 2026-11-21 a third title is being brought up inside it |

Since D18 there is one road: the KytyPlus host with every system library written in the host, BC5's direct GPU path behind `/dev/gc`, and the work driven by the maintainer's play (phase 5).

## Phase 0a — Input: `bc5-mount`

Goal: one canonical input for everything downstream. A read-only FUSE mount that exposes a `.ffpfsc` container as a plain `app0` directory.

Tasks
1. Derive the container layout from public implementations (PS5PKGTool managed PFS/PFSC/exFAT; FFPFS CLI). Write `docs/formats/ffpfsc.md` (PFS v2 superblock, block size, inode/dirent layout, PFSC compression framing, exFAT wrapper). Every field cites the file it was read from.
2. Build a **synthetic fixture generator** (`bc5-fixture`, a module and binary in the `bc5-mount` crate; ADR 0003): generated directory tree → exFAT image → PFSC → PFS v2, written by us from `docs/formats/ffpfsc.md` (the public implementations are GPL-3.0 and cannot be ported). MkPFS is used only as an external cross-check in the gate experiment. Fixtures are generated in tests, never committed.
3. Implement readers bottom-up with unit tests at each layer: `pfs` → `pfsc` → `exfat`. Property tests for headers; round-trip tests against the generator.
4. FUSE layer with `fuser`: `bc5-mount mount <container> <mountpoint>`. Read-only. `bc5-mount verify <container>` walks the tree and prints SHA-256 per file without FUSE; `ls` and `cat` work everywhere.
5. `bc5-mount inspect <container>`: prints superblock, compression ratio, file count, title metadata from `sce_sys/param.json` if present.

Gate G0a: mounting a synthetic container yields a file tree and per-file SHA-256 identical to the source directory; `cargo test` passes; throughput ≥ 300 MB/s sequential read on the dev box (record the number). *Passed, experiment 0002 (≥ 1.4 GB/s sequential read through the mount; MkPFS accepts every generated container).*

Needs: any Linux with FUSE. No BC-250, no game.

## Phase 0b — Foundation: RPCSX baseline on the BC-250

Tasks
1. Experiment `NNNN-dev-box-inventory` (next free number): kernel, Mesa, RADV, libdrm versions; presence of BC-250 PSP/CCP patches; BIOS memory split; disk type and free space.
2. Build RPCSX inside the `fedora` distrobox per `.github/BUILDING.md`. Record exact commands and the commit hash.
3. Boot PS5 VSH / safe mode through the stock Vulkan backend. Record FPS, `RADV_DEBUG` logs, any hangs.
4. Report results on the RPCSX Discord (human does this) — establish contact before any PR.

Gate G0b: VSH boots on the BC-250 through stock RPCSX; baseline numbers recorded. *Retired 2026-10-19 by D18 / ADR 0012: the project does not boot PS5 firmware or system software. Tasks 1–2 were done (experiments 0003 and 0006: RPCSX builds unmodified in the `ubuntu` distrobox); task 3 never ran; RPCSX stays a reference for the AGC/GPU side only.*

## Phase 1b — Track B: Sony's `libSceAgc` in an HLE host (D11)

Runs in parallel with 0b, which waits for the maintainer's firmware dump. Host: KytyPlus (GPL-2.0-only), with the game's own `fakelib/libSceAgc.sprx` and `libSceAgcDriver.sprx` LLE-loaded from the maintainer's dump (experiments 0009, 0010).

Tasks
1. Implement in KytyPlus the 29 imports listed in `experiments/0010-lle-libsceagc-in-kytyplus/raw/unresolved-imports.txt` so that Sony's driver initialises (its context pointer at `libSceAgcDriver+0x22c10` becomes non-NULL). Patches under `backend/kytyplus-patches/`; upstream PRs when stable.
2. Route the `/dev/gc` ioctls (`0xc0488131` submit header, `0xc0188132`; RPCSX is the reference, F12) to a capture that writes every DCB/CCB as raw dwords (env-gated), and to a stub that completes them immediately.
3. `bc5-agc report` over the captures: first DCBs built by Sony's code.
4. Fix, one at a time, whatever KytyPlus still blocks on before the game reaches its first load milestone (experiment 0009: a `PthreadCondWait` deadlock after `fiber init`).

5. A minimal BC5 command processor for the synchronisation packets (`WRITE_DATA`, `RELEASE_MEM`, `COND_EXEC`, `ATOMIC_MEM`, `WAIT_REG_MEM`, `COPY_DATA`, `INDIRECT_BUFFER`) behind `/dev/gc`, completing each submit immediately and firing the `EVFILT_GRAPHICS` events, so the game keeps producing frames; everything else is skipped by packet length. KytyPlus's own interpreter is not used for these buffers (it models gfx9/PS4).

Gate G1b: a DCB built by Sony's `libSceAgc` is captured from the first title on the BC-250 and decodes with `bc5-agc`; the list of `/dev/gc` ioctls seen, with counts, is recorded. *Passed 2026-09-30, experiment 0011; tasks 4–5 done in experiment 0012 (fiber fix, soft CP, queue consumer: whole frames captured).*

## Phase 1 — Validation: AGC decoder and tap

Tasks
1. Answer Q2 (how RPCSX handles AGC) by reading its GPU sources; document paths in `docs/formats/agc.md`.
2. `tools/bc5-agc`: standalone PM4/AGC decoder (Rust) that reads a raw command-buffer capture and prints packets, register writes (resolved against Mesa gfx10 register tables), and unknown opcodes/offsets. Fixtures: hand-built PM4 streams; captures from RPCSX once the tap exists.
3. Tap in RPCSX (C++): dump every submitted DCB/CCB to files, gated by an env var. Kept as a small patch under `backend/rpcsx-patches/` until upstreamed.
4. Count mask-register writes (Q3) and unknown register offsets (Q4).

Gate G1: a full VSH frame (track A) or a full the first title frame from track B decodes with zero unknown opcodes; unknown register offsets are listed with counts. *Not recorded as passed. Track B showed its substance in experiments 0011–0012 (Sony-built DCBs captured at `/dev/gc` decode with `bc5-agc` with zero unknown opcodes; whole frames captured through the soft CP); task 3 (the RPCSX tap) is retired by D18.*

## Phase 2 — Native shaders

Tasks
1. Experiment `dev-box-inventory` refresh if anything changed.
2. Port libdrm `tests/amdgpu` dispatch test into `backend/experiments/dispatch-min`: allocate BOs, load a compute shader binary, `SET_SH_REG` PGM/RSRC, `DISPATCH_DIRECT`, fence, read back. GFX ring only. *Done 2026-09-30, experiment 0008 (IGT sequence, 16 KiB–256 MiB filled on the GFX ring).*
3. Replace the test shader with a compute shader extracted from a phase-1 capture. Run the same shader through Kyty's recompiler on a PC for comparison. *Done 2026-09-30 for the first captured program (experiment 0013: Sony's fill program = IGT's buffer clear, run with console RSRC1/V# values, bit-exact vs a CPU reference instead of Kyty's recompiler). Replaying the other 19 captured programs needs their input buffers captured.*
4. Experiment for Q1: `AMDGPU_GEM_USERPTR` + chosen VA; measure. *Done 2026-09-30, experiment 0014 (`backend/experiments/userptr-min`): GPU VA == CPU VA works, 64 and 512 MiB, zero copies.*

Gate G2: a captured compute shader runs natively and produces bit-identical output to the recompiled path; userptr mapping verdict recorded. *Passed 2026-09-30 (experiments 0013 + 0014), with the recorded deviation that the reference for the captured program is a CPU model of its semantics, not Kyty's recompiler.*

## Phase 3 — Direct submission

Tasks
1. `backend/`: libdrm client — BO manager, VA mapper (1:1 where possible), packet rewriter (addresses, context registers), submit with fences. `--submit` flag, default off.
2. Clear screen → one triangle with a PS5 vertex/pixel shader pair from a capture.
3. CU mask switch (36/40): `COMPUTE_STATIC_THREAD_MGMT_*`, `RSRC3.CU_EN`; ANDed with game masks. Measure FPS and desktop responsiveness in both settings.

Gate G3: image on screen, no GPU hang across 100 consecutive frames; 36/40 numbers recorded. *Passed 2026-10-01 (experiment 0016, runs 79–88), with two recorded deviations: the game image is the first title's loading screen and opening card at ~3 fps from the track-B host (frame time is kernel/host work, F38), so FPS does not differ between CU masks — the GPU time per frame does and is recorded; and the bit layout of a 36-CU mask on this board was open (F39, Q8) — answered for compute by experiment 0019: 0x0003ffff per shader-engine register.*

## Phase 4 — Integration

Tasks
1. Backend as a build option in RPCSX (`-DRPCSX_GPU_BACKEND=bc5`) or a `rpcsx-bc5` fork if upstream declines.
2. First 2D title from Kyty's compatibility list, using the maintainer's own dump via `bc5-mount`.
3. Fallback path: packets the backend cannot handle go through the stock Vulkan backend (per-packet or per-frame switch).

Gate G4: a game reaches its menu through the native path; deviations from the Vulkan path listed. *Retired 2026-10-19 by D18 together with RPCSX integration. Its aim was reached on track B: the first title is fully playable through the direct path (F85), and the second title plays from its menus into gameplay (F207, F212, F277).*

## Phase 5 — Play: both titles on the direct path (current)

The maintainer plays the first title and the second title on the shared builds (normal and lean, `~/bc5-work/kytyplus-build[-lean]`). What he sees in play becomes an experiment; a fix is a diff in its experiment directory, built privately, tested in play or on the bench, and integrated into both shared builds only with his yes (the procedure is in `PROMPT.md`; since 2026-11-21 the top session decides a swap itself on a lean A/B, HANDOFF D25 and D29). The top session owns the box and commits; the standing policy is that a speed-up with no regression goes into use even when the root cause is not found.

Done in this phase (selection; details in `docs/HANDOFF.md` and `README.md`): the first title fully playable with motion, haptics and adaptive triggers (F85); the second title from menus into gameplay with sound, saves, pause and ray-traced reflections (F207–F277); DualSense haptics from its ATRAC9 tracks (F301); loading and stall fixes (APR read-ahead, tiler pool, held tail; F287–F312); SaveData sidecars (F319); DualShock 4 rumble and pad speaker (F330); a live Ray tracing switch (F343); timeout probe, dispatch grids and saved GPU coredumps for hang analysis (F317, F334, CLAUDE.md).

Done since 2026-10-24 (selection): the cut of oversized frames under the kernel's limit (F427–F433); the night lake (F786); the builds carry their own defaults, for every title since 2026-11-22 (F827, F896, F907); a GPU fault ends the game with a record (F834); compute buffers on the compute rings with each queue's own state, every title (F846, F850); the second title's GPU hang family from stale cross-queue waits (F848, F859); real-time priority for the game's job workers (F857); port pack 1 (F861); label writes registered before the submit (F865–F868); BC5's own `libSceAgc`, `libSceAgcDriver` and `libScePsml`, so no module from a dump is needed for them (F916); the emulator on the host instead of in the build container (ADR 0015, F920).

Open as of 2026-11-24, in the order of work (the list of record is the state paragraph at the top of `docs/HANDOFF.md`):
1. **Memory only the GPU writes is not imported** (F920): it keeps three settings in the second title's launcher and keeps the third title off the shared builds; the rule for every title costs too much on the first title (F924, Q45).
2. **The third title**, on a private build: blocks at object borders and wrong wet-surface reflections (F923, Q47), silent machine freezes at the memory wall (F921, Q46), and the console's own order of its graphics and compute jobs on the GPU (F917, F918).
3. **Bake 2**, a candidate that is not deployed (F924), and the unexplained 1 % lean cost of the previous bake on the first title (F907).
4. **The build on the host**, decided and not done (HANDOFF D31, ADR 0015's amendment).
5. **Rare hangs of the second title** whose cause is not known (Q20, Q25, Q48) and its job-system crash, not counted in long runs since the fix (Q24, Q31).

Open as of 2026-10-24 (history; each item's later state is in the brackets):
1. **Hangs and machine-downs of the second title.** Every hang caught on 2026-10-24 stood in the title's BVH build work, with the other ring waiting (F332, F336, F339); stray TCP writes also occur with that work dropped (F338). Next: the breadcrumb build (experiments 0277/0281) to name the hung dispatch; a long RT-off session. [The main family's cause was found and fixed in the shared builds on 2026-11-18: F848, F859. Rare classes remain: Q20, Q25, Q48.]
2. **The night lake's patchwork** (F305–F342): holes where no depth was written, switching between two fixed pixel sets; not cleared by RT off (F341). [Fixed on 2026-11-01: F786.]
3. **Reflections incomplete**: the BVH compaction 0x909974400 stays skipped (F207, F268, F325). [The compaction runs since 2026-10-25: F384, F388. The Ray tracing switch was removed on 2026-11-22: F907. Whether the reflections are complete has not been examined: Q11.]
4. **The host's library code is behind upstream**: KytyPlus has 328 library commits since `f266548` (`docs/ports/upstream-sync-review.md`); two ports are in experiment 0276. [Port pack 1 brought 14 fixes from related projects on 2026-11-19: F861. The gap to upstream itself has not been measured again.]
5. **The backend archive** the shared builds link (Q19). [Answered on 2026-10-24: F345.]

Gate G5 (proposed, for the maintainer to confirm): the second title plays a 60-minute session on the default shared build with no GPU hang, fault or machine-down, recorded in an experiment with the kernel stream.

## Later

- I/O layer: prefetch/cache to hide SSD/Kraken assumptions (Q5); `bc5-mount`'s startup preload (ADR 0014) and the APR read-ahead (F273) cover the loading paths measured so far.
- Rebasing patch 0001 onto upstream KytyPlus (55 of its 83 files conflict with upstream HEAD).
