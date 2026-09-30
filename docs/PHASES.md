# PHASES — roadmap with gates

Each phase ends with a gate: an experiment whose recorded result decides whether the next phase starts. A gate is "passed" only when an `experiments/NNNN-*/README.md` says so with evidence. No dates.

## Phase 0a — Input: `bc5-mount`

Goal: one canonical input for everything downstream. A read-only FUSE mount that exposes a `.ffpfsc` container as a plain `app0` directory.

Tasks
1. Derive the container layout from public implementations (PS5PKGTool managed PFS/PFSC/exFAT; FFPFS CLI). Write `docs/formats/ffpfsc.md` (PFS v2 superblock, block size, inode/dirent layout, PFSC compression framing, exFAT wrapper). Every field cites the file it was read from.
2. Build a **synthetic fixture generator** (`bc5-fixture`, a module and binary in the `bc5-mount` crate; ADR 0003): generated directory tree → exFAT image → PFSC → PFS v2, written by us from `docs/formats/ffpfsc.md` (the public implementations are GPL-3.0 and cannot be ported). MkPFS is used only as an external cross-check in the gate experiment. Fixtures are generated in tests, never committed.
3. Implement readers bottom-up with unit tests at each layer: `pfs` → `pfsc` → `exfat`. Property tests for headers; round-trip tests against the generator.
4. FUSE layer with `fuser`: `bc5-mount mount <container> <mountpoint>`. Read-only. `bc5-mount verify <container>` walks the tree and prints SHA-256 per file without FUSE; `ls` and `cat` work everywhere.
5. `bc5-mount inspect <container>`: prints superblock, compression ratio, file count, title metadata from `sce_sys/param.json` if present.

Gate G0a: mounting a synthetic container yields a file tree and per-file SHA-256 identical to the source directory; `cargo test` passes; throughput ≥ 300 MB/s sequential read on the dev box (record the number).

Needs: any Linux with FUSE. No BC-250, no game.

## Phase 0b — Foundation: RPCSX baseline on the BC-250

Tasks
1. Experiment `NNNN-dev-box-inventory` (next free number): kernel, Mesa, RADV, libdrm versions; presence of BC-250 PSP/CCP patches; BIOS memory split; disk type and free space.
2. Build RPCSX inside the `fedora` distrobox per `.github/BUILDING.md`. Record exact commands and the commit hash.
3. Boot PS5 VSH / safe mode through the stock Vulkan backend. Record FPS, `RADV_DEBUG` logs, any hangs.
4. Report results on the RPCSX Discord (human does this) — establish contact before any PR.

Gate G0b: VSH boots on the BC-250 through stock RPCSX; baseline numbers recorded.

## Phase 1b — Track B: Sony's `libSceAgc` in an HLE host (D11)

Runs in parallel with 0b, which waits for the maintainer's firmware dump. Host: KytyPlus (GPL-2.0-only), with the game's own `fakelib/libSceAgc.sprx` and `libSceAgcDriver.sprx` LLE-loaded from the maintainer's dump (experiments 0009, 0010).

Tasks
1. Implement in KytyPlus the 29 imports listed in `experiments/0010-lle-libsceagc-in-kytyplus/raw/unresolved-imports.txt` so that Sony's driver initialises (its context pointer at `libSceAgcDriver+0x22c10` becomes non-NULL). Patches under `backend/kytyplus-patches/`; upstream PRs when stable.
2. Route the `/dev/gc` ioctls (`0xc0488131` submit header, `0xc0188132`; RPCSX is the reference, F12) to a capture that writes every DCB/CCB as raw dwords (env-gated), and to a stub that completes them immediately.
3. `bc5-agc report` over the captures: first DCBs built by Sony's code.
4. Fix, one at a time, whatever KytyPlus still blocks on before the game reaches its first load milestone (experiment 0009: a `PthreadCondWait` deadlock after `fiber init`).

5. A minimal BC5 command processor for the synchronisation packets (`WRITE_DATA`, `RELEASE_MEM`, `COND_EXEC`, `ATOMIC_MEM`, `WAIT_REG_MEM`, `COPY_DATA`, `INDIRECT_BUFFER`) behind `/dev/gc`, completing each submit immediately and firing the `EVFILT_GRAPHICS` events, so the game keeps producing frames; everything else is skipped by packet length. KytyPlus's own interpreter is not used for these buffers (it models gfx9/PS4).

Gate G1b: a DCB built by Sony's `libSceAgc` is captured from ASTRO BOT on the BC-250 and decodes with `bc5-agc`; the list of `/dev/gc` ioctls seen, with counts, is recorded. *Passed 2026-09-30, experiment 0011; tasks 4–5 done in experiment 0012 (fiber fix, soft CP, queue consumer: whole frames captured).*

## Phase 1 — Validation: AGC decoder and tap

Tasks
1. Answer Q2 (how RPCSX handles AGC) by reading its GPU sources; document paths in `docs/formats/agc.md`.
2. `tools/bc5-agc`: standalone PM4/AGC decoder (Rust) that reads a raw command-buffer capture and prints packets, register writes (resolved against Mesa gfx10 register tables), and unknown opcodes/offsets. Fixtures: hand-built PM4 streams; captures from RPCSX once the tap exists.
3. Tap in RPCSX (C++): dump every submitted DCB/CCB to files, gated by an env var. Kept as a small patch under `backend/rpcsx-patches/` until upstreamed.
4. Count mask-register writes (Q3) and unknown register offsets (Q4).

Gate G1: a full VSH frame (track A) or a full ASTRO BOT frame from track B decodes with zero unknown opcodes; unknown register offsets are listed with counts.

## Phase 2 — Native shaders

Tasks
1. Experiment `dev-box-inventory` refresh if anything changed.
2. Port libdrm `tests/amdgpu` dispatch test into `backend/experiments/dispatch-min`: allocate BOs, load a compute shader binary, `SET_SH_REG` PGM/RSRC, `DISPATCH_DIRECT`, fence, read back. GFX ring only. *Done 2026-09-30, experiment 0008 (IGT sequence, 16 KiB–256 MiB filled on the GFX ring).*
3. Replace the test shader with a compute shader extracted from a phase-1 capture. Run the same shader through Kyty's recompiler on a PC for comparison. *Done 2026-09-30 for the first captured program (experiment 0013: Sony's fill program = IGT's buffer clear, run with console RSRC1/V# values, bit-exact vs a CPU reference instead of Kyty's recompiler). Replaying the other 19 captured programs needs their input buffers captured.*
4. Experiment for Q1: `AMDGPU_GEM_USERPTR` + chosen VA; measure.

Gate G2: a captured compute shader runs natively and produces bit-identical output to the recompiled path; userptr mapping verdict recorded.

## Phase 3 — Direct submission

Tasks
1. `backend/`: libdrm client — BO manager, VA mapper (1:1 where possible), packet rewriter (addresses, context registers), submit with fences. `--submit` flag, default off.
2. Clear screen → one triangle with a PS5 vertex/pixel shader pair from a capture.
3. CU mask switch (36/40): `COMPUTE_STATIC_THREAD_MGMT_*`, `RSRC3.CU_EN`; ANDed with game masks. Measure FPS and desktop responsiveness in both settings.

Gate G3: image on screen, no GPU hang across 100 consecutive frames; 36/40 numbers recorded.

## Phase 4 — Integration

Tasks
1. Backend as a build option in RPCSX (`-DRPCSX_GPU_BACKEND=bc5`) or a `rpcsx-bc5` fork if upstream declines.
2. First 2D title from Kyty's compatibility list, using the maintainer's own dump via `bc5-mount`.
3. Fallback path: packets the backend cannot handle go through the stock Vulkan backend (per-packet or per-frame switch).

Gate G4: a game reaches its menu through the native path; deviations from the Vulkan path listed.

## Later

- I/O layer: prefetch/cache to hide SSD/Kraken assumptions (Q5).
- Audio/input polish inherited from RPCSX.
