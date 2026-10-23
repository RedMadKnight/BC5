# History rewrite of 2026-10-23

On 2026-10-23 the maintainer had four game screenshots removed from the whole history of `main`:
`docs/images/g3-first-screen.png`, `docs/images/intro-video-frame.png`,
`experiments/0171-flip-defer-retest/run824-slot-menu.jpg` and `experiments/0175-play-stalls-watcher-pause/paused-banner.jpg`.
The repository carries no game imagery (README, Legal). The final tree did not change. The old pull requests #6 and #7 still show three of the images; the maintainer closed them and left them there.

Commits up to 2026-09-30 kept their ids. Every commit from `485cea4` (2026-10-01, the first one that added an image) on got a new id.
The commit that only removed the last two images (`41a09cc`) became empty and was dropped.
Commit ids quoted in `docs/HANDOFF.md`, `experiments/*/README.md` and older commit messages are the old ones; look them up below.

| old | new | date | subject |
| --- | --- | --- | --- |
| `485cea48d8` | `d6c0ade021` | 2026-10-01 | docs: README — status after run 79 and the first-screen screenshot (emulator window, BC... |
| `c0456457b9` | `e1e3a5c83f` | 2026-10-01 | exp: 0016 run 80 — 302 consecutive frames; frame time is userptr validation in the CS i... |
| `709ba89934` | `26b946ac76` | 2026-10-01 | feat(direct): short BO lists for submissions without draws and dispatches; exp: 0016 ru... |
| `5658b89c95` | `98a3df914a` | 2026-10-01 | feat(direct): CU mask for registers loaded from memory (cu_tables), lazy mapping sync i... |
| `ca8b260722` | `6e694e343d` | 2026-10-01 | docs: ADR 0006 — direct memory as dma-bufs of KytyPlus's memfd; feat(direct): Device::i... |
| `dfe39ba31d` | `ca253a5f25` | 2026-10-01 | exp: 0017 dmabuf-min --submit — GPU access through imported memfd ranges works, CS 0.26... |
| `24a437139e` | `0c0b5ceabf` | 2026-10-01 | exp: 0017 run 89 — the dma-buf backing under the game: CS 2.6 ms, 12 fps, then a machin... |
| `cbf5a98c80` | `92f77f7b61` | 2026-10-01 | exp: 0017 run 90 — passed: the game on the dma-buf backing, 7,454 submissions without a... |
| `b1580d4f77` | `3f13cbb824` | 2026-10-01 | exp tools: dispatch-min --cu-mask/--repeat with timing (CU-bit probe), dmabuf-min fix a... |
| `3ed74bcb87` | `d09b1b5682` | 2026-10-01 | exp: 0018 — the 510-frame stall: the driver library reads its ring read pointer behind ... |
| `e8bfaf2fe0` | `3f31880e6f` | 2026-10-01 | exp: 0019 — CU mask measured with a CU-bound probe: bits 0-19 per shader engine live, 3... |
| `e8ed70006e` | `515575b415` | 2026-10-01 | docs: README open questions — three answered (1:1 mapping, AGC submission path, CU mask... |
| `e65f976137` | `83eefc1ad9` | 2026-10-01 | docs: README — AGC question wording (F12) |
| `9b6f57ffd3` | `4589a3f3e3` | 2026-10-01 | exp: 0018 closed — run 93: 935 frames, 14,238 submissions without a failure, the whole ... |
| `03829b0179` | `ad300b9d0a` | 2026-10-01 | host: 28 sce::Json functions the game imports added to KytyPlus's HLE library (patch 00... |
| `1033cee7a4` | `a8a9a1c135` | 2026-10-01 | exp: 0020 — past the intro: run 94 reaches the game's own JSON assertion; host: JSON ca... |
| `4dd640876d` | `7b50a5f265` | 2026-10-01 | exp: 0020 run 95 — the JSON trace names the cause: referValue is the game's existence t... |
| `8a0216d312` | `e4c44e2d27` | 2026-10-01 | exp: 0020 run 96 — the game's first own scene; the limit is the driver's GTT accounting... |
| `0086bfa923` | `9477174fdb` | 2026-10-01 | exp: 0020 — the emulator's own GTT share measured per DRM client (map-only) |
| `b0136d3933` | `e2d37594ce` | 2026-10-01 | exp: 0020 run 97 — the game reaches its title screen on the BC-250 (F45) |
| `f8780673c0` | `4a8cf6b498` | 2026-10-01 | exp: 0020 run 98 — controller input works, the first level starts loading; the GTT ceil... |
| `144f6e6c63` | `74c53d3097` | 2026-10-01 | exp: 0021 — the emulator's own GTT share: 1.15 GiB down to 0.12 GiB with two host setti... |
| `0aac110e95` | `349323e09f` | 2026-10-01 | exp: 0021 run 99 — with the slimmed host the level load no longer hits the GTT ceiling;... |
| `b15b5bbc80` | `88a09bc812` | 2026-10-01 | docs: D12 — ttm.pages_limit raised to 13 GiB on the dev box by the maintainer; GTT is 1... |
| `289e727369` | `da7a71b1b2` | 2026-10-01 | exp: 0022 run 100 — the first level loads, the opening cutscene plays at 6 fps; frame-t... |
| `355bbac6ca` | `b63a4ca44e` | 2026-10-01 | direct: minimal journal mode, merged imports, kept BO list (experiment 0022, steps 1-2) |
| `4c349eb5fb` | `ae4aa91a35` | 2026-10-01 | exp: 0022 run 101 — title-screen scene at 19.8 fps instead of 8 with the minimal journa... |
| `1d2ba8dd91` | `53aefa94d1` | 2026-10-01 | host: cheaper mapping sync, learned regions and hints (experiment 0022, step 3) |
| `6d9a7608c5` | `323e59fc19` | 2026-10-01 | exp: 0022 run 102 — title screen and loading at 27 fps with the cheaper sync (F50); the... |
| `823f9c283b` | `a9d89dfa29` | 2026-10-01 | exp: 0022 run 103 — first interactive scene at 23.5 fps; the slow load is a directory s... |
| `10dcc3519c` | `acd8cb2a76` | 2026-10-01 | exp: 0022 — raw summary of run 103 without the game's file names |
| `0bc96a643c` | `b71fd5482d` | 2026-10-01 | exp: 0022 run 104 — the game reaches gameplay at 24 fps; motion input works, the level ... |
| `595d1ff8ee` | `477784899e` | 2026-10-01 | host: eager import of the game's GPU heaps; F53 — the Options freeze was a page fault, ... |
| `3f659a940e` | `12e1925f4c` | 2026-10-01 | patch 0001: comment corrected (17 of the 18 learned regions) |
| `37292b0871` | `34cf10092b` | 2026-10-01 | exp: 0022 runs 105-106 — no fault and no freeze with the GPU heaps imported in full; wa... |
| `bb244c174b` | `da41191f67` | 2026-10-01 | exp: 0022 — the submission ioctl's cost is the userptr page walk (F54); the maintainer'... |
| `4251332b75` | `e991b5df31` | 2026-10-01 | exp: 0023 — private guest memory from a sealed memfd, imported like the direct memory (... |
| `cc0fbce45b` | `6c5aae70ea` | 2026-10-01 | exp: 0023 run 107 — no userptr left: title screen 47 fps, cutscene 41 fps (F55) |
| `31eb3d2156` | `f46af5cb32` | 2026-10-01 | exp: 0023 — the controller was unplugged on purpose in run 107 (hot-plug test), not dro... |
| `4deb747464` | `8a894626ca` | 2026-10-01 | exp: 0024 — jobs in flight (BC5_DIRECT_ASYNC, off by default); F56 — the GPU clock on t... |
| `0ee5855a87` | `3e4ece8692` | 2026-10-01 | exp: 0024 run 108 — jobs in flight: title screen 54 fps instead of 44 (F57) |
| `25bf9df304` | `d459b7c518` | 2026-10-01 | exp: 0024 run 109 — the same two runs at 2000 MHz: 56 fps with jobs in flight, 143 W, 7... |
| `98f292ee23` | `01113ae72a` | 2026-10-01 | exp: 0024 run 110 — the first design stalls in the cutscene; reworked (consumer waits f... |
| `6b845ab673` | `8d16275f31` | 2026-10-01 | exp: 0024 run 111 — jobs in flight break the cutscene's queue handshake; the mode stays... |
| `bbd0ef4587` | `9f85f8e802` | 2026-10-01 | exp: 0024 run 112 — the synchronous path of the same build is clean through the cutscen... |
| `0ec24fcad8` | `7b033af1c6` | 2026-10-01 | exp: 0024 — the restart after run 112 was an orderly one |
| `1b759a8dcc` | `0e386b765a` | 2026-10-01 | exp: 0024 run 113 — label trace: the doorbell consumer served a queue all or nothing; i... |
| `8122fef14d` | `bf5220ca2a` | 2026-10-01 | exp: 0024 run 114 — with the queue served in order the cutscene runs at 50–53 fps with ... |
| `24847762fa` | `7e5244f09b` | 2026-10-02 | exp: 0024 run 115 — the first level at 47–55 fps with jobs in flight, on to the galaxy ... |
| `e5669fa9c6` | `25dd9aaee3` | 2026-10-02 | exp: 0024 run 116 — the second level loads and plays (35–43 fps); 30 minutes, 1.3 milli... |
| `f7db0623f4` | `75b8b97ed4` | 2026-10-02 | host: pad orientation from the sensors, no doubled joystick events, a trigger dead zone... |
| `799925cfbb` | `50f5537a29` | 2026-10-02 | docs: README brought up to runs 114–116 and the pad findings; HANDOFF F61 |
| `0162787893` | `cd74c41e18` | 2026-10-02 | docs: README — how to start: preparing a BC-250, building the host and running a game |
| `2050a103dd` | `ab1948fe26` | 2026-10-06 | exp: 0025 — the second level's frame is the GPU's first (18.6 ms); a census of the game... |
| `e6cd89c71f` | `de52ca2ef2` | 2026-10-06 | exp: 0026 — the water: two cycles between the queues; a stopgap (8 ms wait limit, cycle... |
| `4eb578589b` | `52fcd030c3` | 2026-10-06 | exp: 0027 — prepare offline: the walk is 0.1 ms per 10k dwords; the scratch is assemble... |
| `d3f37b9a99` | `e53cc59220` | 2026-10-06 | exp: 0028 — deferring the flip gives nothing; 0027 — the filter is three times its offl... |
| `632242aca1` | `82dbf7fa7e` | 2026-10-06 | host: haptics — the game's pad-speaker and vibration audio ports go to the DualSense's ... |
| `f73bf49b54` | `d70f65cc2d` | 2026-10-06 | docs: F69 haptics result on the test controller, F70 run 128 unattended title screen |
| `033216e283` | `e3dc011860` | 2026-10-06 | docs: F69 haptics result on the test controller, F70 title screen from run 128 |
| `9a528b87ce` | `cf9e987d48` | 2026-10-06 | exp: 0026 run 129 raw summary (unattended, ended by the launching session) |
| `4f8bf11356` | `0f91a6f0c5` | 2026-10-06 | fix(mount): index directory names and cache negative lookups; exp 0029 missing-file loo... |
| `5ffd58e948` | `8b58b3e58c` | 2026-10-06 | feat(host): input configuration file: bindings, disabled pad inputs, keyboard layout (D14) |
| `59fa4fd040` | `5a75e76694` | 2026-10-06 | fix(host): letter key names in the input configuration match the key events |
| `2c673d19c6` | `812c9c69a3` | 2026-10-07 | fix(host): input trace, minimum key hold, newest pad states; F73 |
| `7454c06f55` | `9a106f170d` | 2026-10-07 | host: quieter logs and the per-flip sampling off by default (F75); F74 GPU fault noted |
| `3bea6f1c54` | `574913beb1` | 2026-10-07 | host: the per-IB header line logs its first 16 (F75) |
| `7b77683cad` | `395a010ad5` | 2026-10-08 | exp: run 132, the per-flip sampling was not the time at the flip (F75) |
| `9e045c0500` | `93a7e42ee7` | 2026-10-08 | docs: F72 audio confirmed by the maintainer |
| `46bc4511aa` | `0ff7061424` | 2026-10-08 | docs: run 132 was played by the maintainer from the start of gameplay |
| `ca5ffb00fc` | `1d4ac04815` | 2026-10-08 | feat(host): F2 settings menu over the game edits the input configuration (D14) |
| `c4f483b285` | `371aef5e56` | 2026-10-08 | docs: the F2 menu and its binding confirmed by the maintainer |
| `7788aa54ad` | `345d5356b5` | 2026-10-08 | host: two KytyPS5 ports: short sleeps block, unmapped guest paths stay off the host (F76) |
| `487fee14fa` | `28429cd16c` | 2026-10-08 | host: revert the blocking-sleep port (the game's command-buffer writer asserts), add gu... |
| `ee6832c7ba` | `c079608655` | 2026-10-08 | host: one logged-in user by default; the game read a second pad handle every frame (F77) |
| `82dbc5f19d` | `5f58b24f76` | 2026-10-08 | host: adaptive-trigger state answered from the trigger's analog value and the last effe... |
| `c796d0b5be` | `2662f0dbd2` | 2026-10-08 | host: adaptive-trigger state with libScePad's documented values (duaLib header, KytyPS5... |
| `456f0379db` | `e041c2a1d2` | 2026-10-08 | docs: haptics felt on the replacement controller once the sink is at full volume (F79) |
| `2c1c1af069` | `29feb14a62` | 2026-10-08 | host: pad-speaker knob, haptics gain and a pad-audio level trace; F78 confirmed by the ... |
| `b9b6c1390a` | `c1b2565366` | 2026-10-08 | host: six-channel pad stream so the actuators get the game's haptics under SDL's pulsea... |
| `f1ba08e434` | `4774696211` | 2026-10-08 | host, docs: haptics confirmed in the game; the pad stream is six channels unconditional... |
| `ce01f25e7c` | `f79305e19e` | 2026-10-08 | exp: 0030 CPU per thread in the maintainer's play; neither the load nor play is CPU-bou... |
| `dc1eb7a80c` | `7531187e77` | 2026-10-08 | feat(mount): read PS5 packages (outer PFS, naps layout, Kraken blocks, inner tree) behi... |
| `9a1cde8560` | `75be343350` | 2026-10-08 | fix(mount): the plaintext seed of a package's outer PFS reads PPRPLAIN-NOAUTH!; add the... |
| `e133218ed1` | `c8fc719b3f` | 2026-10-08 | exp: 0031 bc5-mount reads the maintainer's package on the box (inspect, ls, cat, FUSE m... |
| `a3a19cfa8b` | `e55dc6a859` | 2026-10-08 | exp: 0032 the level load waits on the single bc5-mount thread (F83); host threads named |
| `2f7951767e` | `266ccd7e08` | 2026-10-08 | feat(mount): answer reads from a worker pool, share a sharded block cache, decode files... |
| `47f91b1f8b` | `7c3b2a49d8` | 2026-10-08 | docs: the parallel bc5-mount confirmed in the maintainer's play (F84) |
| `4b3b656bee` | `4e945d8b8f` | 2026-10-09 | docs, host: ASTRO BOT fully playable (F85); open questions closed or parked; the game's... |
| `f56ccaa189` | `aab7a0a170` | 2026-10-09 | exp: 0034 a second title starts from its PS5 package and stops at AMM (F86) |
| `be0e1d063f` | `ad6d42aaa2` | 2026-10-09 | host: AMM window placed where the host has room, DMA-written AMM pages host-writable, A... |
| `181ebf8e58` | `922f746e35` | 2026-10-09 | fix(mount), host: the second title loads and renders 3D from its package (F88) |
| `f87fbd9f08` | `26af9706c6` | 2026-10-09 | perf(host, direct): the second title from 7 to 24 fps; KytyPS5's APR, ATRAC9 and entitl... |
| `5265ea1921` | `9fc2e8ec37` | 2026-10-09 | docs, host, backend: the second title's stops (F90); README and HANDOFF brought up to date |
| `c8f34d7fe6` | `cb6504ae88` | 2026-10-09 | exp: 0038 the second title's semaphore is a graphics RELEASE_MEM against a compute wait... |
| `95f6f2f415` | `2ec58e4a4e` | 2026-10-09 | host: keep the growth-report counter across a device reopen; SET_BASE for converted dis... |
| `251456b20d` | `fb40db278f` | 2026-10-09 | exp: 0038 runs 72-74: why the title cannot recover after a fault, run 64's hang explain... |
| `85f09cfc4c` | `6213b2f4fc` | 2026-10-09 | host, backend, exp: 0039 the second title's compute IBs' indirect dispatches run on the... |
| `be7a0ae708` | `7d893b8d7c` | 2026-10-09 | docs, host, exp: 0040 the second title's fault addresses (F92); a replugged pad keeps h... |
| `8ef6b557e7` | `232143d081` | 2026-10-09 | fix(host): the controller's ALSA volume is set from the container too and kept after a ... |
| `062c786d2e` | `ec8d6a89e6` | 2026-10-09 | host, docs: haptics confirmed by the maintainer (F94); the diagnostic log lines and the... |
| `38e1311894` | `210a8c6dfe` | 2026-10-09 | exp: 0041 the second title's dropped LOAD_SH_REG_INDEX is a no-op; trusting stale dispa... |
| `d5a13466ab` | `794a535d53` | 2026-10-09 | docs: README run statistics for the second title (nine of twelve clean since F91) |
| `8e46975e5d` | `7c19ecfb78` | 2026-10-10 | exp: 0042 the second title's GPU-only heaps were never imported; importing them removes... |
| `eea00c5e39` | `f64f87ed8a` | 2026-10-10 | exp: 0043 ASTRO BOT's first level is GPU-bound at 17.1 of 18 ms; 4.3 ms are serialised ... |
| `eae312dedb` | `29da7d895d` | 2026-10-10 | exp: 0044 ASTRO BOT's compute buffers write L2 back after every dispatch, and the write... |
| `cc044dca1d` | `18588905a7` | 2026-10-10 | exp: 0045 ASTRO BOT's first level at 57 fps: the flip deferred and up to 24 jobs in fli... |
| `3a442041bb` | `0cedc51b44` | 2026-10-10 | exp: 0046 ASTRO BOT's dynamic resolution follows its GPU timestamps; scaled by 1.2 the ... |
| `2419d73aa3` | `afe3dc13ca` | 2026-10-10 | host, exp: 0047 a resolution choice in the F2 menu (Video tab) and a restart from it (F... |
| `462371b5e9` | `f2e1e1403e` | 2026-10-10 | host, exp: 0048 the usual resolution names in the F2 menu and fullscreen at the display... |
| `843d44726a` | `468851d43b` | 2026-10-11 | exp: 0049 the second title uses base-PS5 ray tracing, no PS5 Pro features; fixed 936p v... |
| `132a94f2b8` | `5e40657fa0` | 2026-10-11 | exp: 0050 the second title's tree refit hangs on empty leaf lists, built by dispatches ... |
| `81b514321b` | `0263aa6345` | 2026-10-12 | exp: 0051 second title load, F105 |
| `ec4de56fce` | `eca8185143` | 2026-10-12 | exp: 0052 indirect dispatch arguments checked by the CP, F106 |
| `60c213ef09` | `1afeb79a8e` | 2026-10-12 | exp: 0053 the second title's tree refit runs, F107 |
| `818c3db18c` | `2b2cbe3110` | 2026-10-12 | wip(0054): indirect draws opt-in, CP check for draws, 12-channel audio |
| `4f43cb9514` | `a75229389f` | 2026-10-12 | exp: 0054 indirect draws and sound, 0055 ring-ordered waits; F108, F109 |
| `18741dc310` | `1c004767d0` | 2026-10-12 | wip(0056): map guest memory again under a non-zero address byte 47:40 |
| `8afafa20f4` | `3bdaf94ec4` | 2026-10-12 | exp: 0056 address-byte aliases; HANDOFF F110, Q10 closed, Q11; README |
| `dd61833a48` | `91353c7058` | 2026-10-12 | exp: launcher copies belong to 0056 (0055 has its verdict) |
| `0b0089474c` | `3898de580f` | 2026-10-12 | exp: 0057 the second title's hanging graphics buffer; F111 |
| `90ddadb27c` | `1ec23a552d` | 2026-10-12 | docs: HANDOFF F112, Q11; README: the scene renders with DRAW_INDIRECT + aliases |
| `c19d24c451` | `e0996b6b08` | 2026-10-12 | exp: 0058 the second title's hang state; F113 |
| `9f08e43621` | `d4c2b2f858` | 2026-10-12 | docs: HANDOFF F114 (the self-referencing BVH node); host probes |
| `5404a3847e` | `ae55708243` | 2026-10-13 | exp: 0059 the traversal's trees are not broken; F115 (F114 corrected) |
| `af0b2c23a4` | `568071d943` | 2026-10-13 | docs: HANDOFF F116, the reflection traversal is two-level; instance records suspected |
| `528bb1dcd6` | `234463028e` | 2026-10-13 | exp: 0060 ASTRO BOT's 8 ms waits served by the ring order; F117 |
| `c6877956f6` | `7f0ad44c38` | 2026-10-13 | docs: HANDOFF F118, the menus need the multi-draw packets |
| `661e77c8c1` | `1c9eb4a2e6` | 2026-10-13 | perf(policy): decide a SET packet's register span in one step; exp: 0061 ASTRO BOT late... |
| `de479c97c6` | `1d0d97713c` | 2026-10-13 | exp: 0062 where ASTRO BOT's CPU time goes with the host path at 6 ms; F120 |
| `1619eb3a90` | `f307e89f7d` | 2026-10-13 | exp: 0063 submission off the game's thread: buffers stable, cross-queue order not; F121 |
| `b6bf89d29e` | `2e9c59a5f2` | 2026-10-13 | perf(state_stack): apply the tracker in place; exp: 0064 ASTRO later level 41.7 -> 43.6... |
| `a7131ff6b3` | `01ce055bcf` | 2026-10-13 | exp: 0065 render-target hint pass at half the cost; ASTRO later level 44.2 fps; F123 |
| `4369cce818` | `80347df40e` | 2026-10-13 | docs: HANDOFF F124, the CS cost is the BO count set by udmabuf's import limit |
| `1fff2c6702` | `afa271fc9a` | 2026-10-13 | exp: 0066 larger udmabuf imports, merge runs cut at the budget; ASTRO later level 45.9 ... |
| `a88130d486` | `991a8471a3` | 2026-10-13 | perf(policy): fast path for plain SET packets the table passes whole; exp: 0067 |
| `417ee4a72c` | `b706a01692` | 2026-10-13 | exp: 0068 clean repeat of the filter fast path: ASTRO later level 46.5 fps; F126 |
| `7f0c34c0bd` | `7b78a3e792` | 2026-10-13 | docs: README on ASTRO BOT's frame rates after 2026-10-13, the udmabuf import limit |
| `80d9926e7a` | `7e9aeeaf52` | 2026-10-13 | feat(host): KYTY_BC5_INPUT_RECORD records the real pad as input-script lines; HANDOFF F127 |
| `1fde38fb11` | `e2b738cbae` | 2026-10-13 | fix(host): the deferred flip's label is not released while the flip is queued; exp: 006... |
| `0d5a471a06` | `6d9c83b704` | 2026-10-13 | fix(host): give the display buffer back once KytyPlus has copied the flip; exp: 0070, F129 |
| `e4a92cf89b` | `57433a4f1d` | 2026-10-13 | docs: HANDOFF F129, where a flip's 2.8 ms preparation goes; host: KYTY_BC5_FLIP_TIMING ... |
| `d210e1d3b1` | `0f6b1b55d0` | 2026-10-13 | exp: 0071 flip-label wait left to the GPU took the machine down twice (off); F130 |
| `2ca3c918cb` | `98887e6162` | 2026-10-13 | docs: HANDOFF F131, the display buffer is tiled; what is left in the flip copy |
| `21deeaab5c` | `abfd46ddde` | 2026-10-13 | docs: ADR 0008 (proposed), graphics buffers split at cross-queue waits with tracked sta... |
| `ff28b44ca2` | `723960bc99` | 2026-10-13 | exp: 0072 a graphics piece replaying its own packets would lose 1,000+ registers (ADR 0... |
| `33c6e7e08b` | `577c75f08d` | 2026-10-13 | feat(backend): full register state tracker for graphics pieces (ADR 0008 step 1) |
| `03f31128e9` | `0a742b48ea` | 2026-10-13 | fix(backend): split check adopts the open pushes' saved contexts |
| `662bb77e61` | `1621a3439e` | 2026-10-13 | exp: 0073 full-state prefix checked in the running game (ADR 0008 step 1 passed) |
| `35d98d4e37` | `3cb4b3e770` | 2026-10-13 | exp: 0074 graphics pieces built but not submitted (ADR 0008 step 2, outside the water) |
| `94cf73c38e` | `40fa76e5af` | 2026-10-13 | perf(backend): full-state tracker on flat arrays; exp 0075 |
| `f95e9e4441` | `f1fa38f3e2` | 2026-10-14 | host: BC5_DIRECT_PIECES_FULL, graphics pieces behind the full-state prefix (ADR 0008 st... |
| `401d8fd336` | `5ffdb4bddf` | 2026-10-14 | exp: 0076 graphics pieces built but not submitted, in the water (ADR 0008 step 2 done) |
| `7a71c21bbe` | `366e8409ef` | 2026-10-14 | exp: 0077 graphics pieces on the GPU outside the water (ADR 0008 step 3 passed) |
| `2bbfacf330` | `0da97a69b4` | 2026-10-14 | exp: 0078 graphics pieces on the GPU in the water (ADR 0008 accepted) |
| `5c83ee5651` | `1a7b28a527` | 2026-10-14 | exp: 0079 the second title with graphics pieces on |
| `e6e68de38a` | `c910931061` | 2026-10-14 | exp: 0080 the second title's menu text: letters lost to asynchronous submission |
| `90f1c4a8ca` | `1fd15d1641` | 2026-10-14 | exp: 0081 the second title's text race is the deferred flip |
| `db74a1f644` | `d1b0780e2b` | 2026-10-14 | exp: 0082 counting deferred flips as pending does not stop the text race (reverted) |
| `b48d8708f4` | `0a3f4e316c` | 2026-10-14 | exp: 0083 soft CP of IB-packet submissions after completion (knob, partial fix) |
| `18274ceb26` | `8ee24ed123` | 2026-10-14 | exp: 0084 the second title never asks the driver for an idle GPU (knob kept, off) |
| `61b2955bed` | `ec1d4bc00b` | 2026-10-14 | exp: 0085 deferred flips with 3 jobs in flight: menu glyphs still missing (atlas upload... |
| `ce41409742` | `5c0687a003` | 2026-10-14 | exp: 0086 the copies around the second title's menu: per-frame CP DMA uploads from CPU ... |
| `726db4896f` | `9385a7ff47` | 2026-10-14 | feat(backend,host): DMA_DATA source snapshots at submission (experiment 0087, not run) |
| `57b8dd89b3` | `13466457a8` | 2026-10-14 | exp: 0087 DMA_DATA source snapshots: ring not mappable yet (inconclusive) |
| `30405cebfa` | `9f3c13bbdd` | 2026-10-14 | exp: 0088 black menu background: not the draw limits, not the aliases |
| `2a025ced10` | `c1a2ced2c6` | 2026-10-14 | exp: 0089 per-draw journal of the second title's menu frame |
| `a989903896` | `8f4ebc4f8e` | 2026-10-14 | exp: 0090 the second title's menu scene is rendered but lost in the final composition |
| `3c341cd75c` | `9e9e0f69bf` | 2026-10-14 | exp: 0091 the second title's menu composition: finished scene and UI layer exist apart |
| `c144aac50f` | `4147fb2069` | 2026-10-14 | exp: 0092 who writes the second title's UI layer (nested draw journal, value finder) |
| `931d2c292c` | `c1e60e5e6f` | 2026-10-14 | exp: 0093 the second title's UI layer: no draw writes it; the final pass always binds i... |
| `cab1d142c4` | `10e62f37d6` | 2026-10-14 | exp: 0094 the second title's final pass blends UI layers over the display target's content |
| `46d680e7e3` | `df7e68b4dd` | 2026-10-14 | exp: 0095 the second title's display buffers are 0x1125f00000 / 0x1127ee0000 (correction) |
| `27dbd0ab5e` | `88144c4505` | 2026-10-14 | exp: 0096 no display-size pass; async compute reuses the composition target's memory |
| `fa47a41ed8` | `ed590140cc` | 2026-10-14 | exp: 0097 the order of the second title's large passes in a menu frame |
| `3ca0bdb7b4` | `06d249bd06` | 2026-10-14 | exp: 0098 without pass 0x11d0404200 the second title shows its menu scene |
| `3b720fa504` | `de09ea56f3` | 2026-10-14 | exp: 0099 the second title's UI layers live in AMM memory that our path does not map |
| `95251175a1` | `10ea6b957c` | 2026-10-14 | exp: 0100 the second title's UI layer 0 is almost entirely unmapped in the AMM window |
| `9bb5cdac81` | `4a7b500379` | 2026-10-14 | docs: fix quoting in F160 |
| `e3bdfd1e07` | `92276af9f4` | 2026-10-14 | exp: 0101 the second title's UI layer is a sparse surface (8 mapped tiles) |
| `f9d392bf04` | `d266d760e8` | 2026-10-14 | feat(backend,host): PRT windows for the AMM window (experiment 0102, not run) |
| `1c01eded47` | `6b448830c1` | 2026-10-14 | exp: 0102 the AMM window as PRT pages: no fault, background still black |
| `3661de97d9` | `72035a7f25` | 2026-10-14 | exp: 0102 the maintainer's observation: the scene flickers through now and then |
| `9965cf9c67` | `8518a9ff8f` | 2026-10-14 | exp: 0102 the maintainer closed the window |
| `816a8f13bf` | `26eb22960d` | 2026-10-14 | exp: 0103 second title's intro frame: 9 ms host sync removed, one 34 ms post buffer left |
| `0ceb1669d1` | `191e55628f` | 2026-10-15 | exp: 0104 opaque UI layer (Gameface's own clear), 0105 frame pacing fixed: intro 18 -> ... |
| `aa2af80dd7` | `9aa422f7d8` | 2026-10-15 | exp: 0106 pacing follow-ups: TS scale irrelevant in the intro, menu CPU-bound (18 ms in... |
| `e885800e74` | `c76bb1ca6e` | 2026-10-15 | exp: 0107 menu at 37 fps waits for the device lock held by the ring thread; init_once f... |
| `001b72a56b` | `854986f99a` | 2026-10-15 | exp: 0108 pacing/sync fixes hold 600 s in the menu at 37 fps; ASTRO unchanged at 60 fps |
| `d2310e5af8` | `7d676fcac4` | 2026-10-15 | exp: 0109 no mapping-list copy per submission: menu 37 -> 49 fps |
| `f7fe185a4b` | `f6d75c3106` | 2026-10-15 | exp: 0110 lock-free sorted mappings: no gain, reverted |
| `cf58b4a6fd` | `31d63e7145` | 2026-10-15 | exp: 0111 getenv cache on the submission path: 2.5 fps slower in the menu, reverted |
| `dfc850cd5b` | `d2ec4c74f5` | 2026-10-15 | feat(mount),exp: 0112 one decode per package block, decode counters; parallel APR reads... |
| `39ad030215` | `d28f6de5a1` | 2026-10-15 | feat(mount),exp: 0113 on-disk cache of decoded package blocks (BC5_MOUNT_DISK_CACHE): l... |
| `f2609eb6d1` | `a723a64a10` | 2026-10-15 | exp: 0114 one inflate per PFSC block: ASTRO loads slower and hits GPU timeouts, reverted |
| `a8d45c0fc9` | `45854034bf` | 2026-10-15 | docs: all optimisation targets the BC-250's own architecture (maintainer's decision) |
| `176f68caa5` | `3a87f48566` | 2026-10-15 | feat(mount): one decode per block with per-block in-flight slots; 256 MiB PFSC cache |
| `d28b47f0b5` | `947848dee2` | 2026-10-15 | exp: 0116 per-block in-flight PFSC inflates, 256 MiB cache: offline 13-18 % faster with... |
| `d0e173eea8` | `8c587b8ac6` | 2026-10-15 | Revert "feat(mount): one decode per block with per-block in-flight slots; 256 MiB PFSC ... |
| `dc21b29351` | `820b71f85f` | 2026-10-15 | exp: 0117 ASTRO hangs the GPU when its second load phase is served differently; 0116 re... |
| `8bb36e6423` | `b100408310` | 2026-10-15 | exp: 0117 fix the revert hash |
| `7b61e023c3` | `6148a6ebc5` | 2026-10-15 | fix(ci): Rust 1.99 clippy assert_is_empty; dispatch-min builds without amdgpu |
| `df86a88d3e` | `98b2e285e1` | 2026-10-15 | exp: 0115 per-title timestamp scale; 0118 ASTRO faults follow graphics pieces |
| `9eff66a32f` | `3a8c8735fd` | 2026-10-15 | docs: no title id in the KytyPlus run example |
| `b3ad4a9460` | `8fd2058512` | 2026-10-15 | exp: 0119 graphics pieces as one job with their prefix: ASTRO faults gone |
| `1be005564f` | `05244ffdfa` | 2026-10-15 | exp: 0120 0116's PFSC reader on ASTRO again with pieces fixed: clean, ~1 s |
| `38e07176c1` | `094d4eaae1` | 2026-10-15 | Reapply "feat(mount): one decode per block with per-block in-flight slots; 256 MiB PFSC... |
| `703d3a4b2f` | `5770c14f5d` | 2026-10-15 | perf(mount),exp: 0121 PFSC block cache 1 GiB by default |
| `383a931ea4` | `b405abd86e` | 2026-10-15 | refactor(host): cleanup batch 1, seven dead knobs removed from the KytyPlus patch |
| `66594ac964` | `9e35b37e7b` | 2026-10-15 | refactor(host): cleanup batch 2, phase-3 bring-up probes removed (~320 lines) |
| `80b580154f` | `26e6085b62` | 2026-10-15 | refactor(host): cleanup batch 3, memory surveys, flip sampling and AMM lazy commit removed |
| `dd8a627955` | `f7fa5b4eec` | 2026-10-15 | refactor(host): cleanup batch 4, refit-hunt and trust-era tools removed (~350 lines) |
| `a0c57c1033` | `a02d21d066` | 2026-10-15 | refactor(host): cleanup batch 5, PACE_FIX, the TS_SCALE env start value and PIECE_CHECK... |
| `913baa8965` | `dfd345651c` | 2026-10-15 | refactor(host): cleanup batch 6, hot-path journal lines sampled |
| `232fc4c3f9` | `e5f6db37dc` | 2026-10-15 | feat(backend),exp: 0122 DMA_DATA source snapshot ring: the second title's menu text clean |
| `7249802723` | `7df69c3406` | 2026-10-15 | exp: 0123 New Game hangs in the reflection traversal; skipped, the start screen loads |
| `f73edb6af0` | `81a86f3c2e` | 2026-10-15 | docs: README rewritten: what BC5 is up front, status table, sections refreshed |
| `71f256c3dc` | `220f3611c1` | 2026-10-15 | feat(backend),exp: 0124 job timestamps: the start screen's GPU idles 27.5 % between jobs |
| `42da538349` | `2a5c62299a` | 2026-10-15 | exp: 0125 start screen: fewer submissions are not faster, the ring order decides |
| `6c7ddb5858` | `9b10712cc7` | 2026-10-15 | exp: 0126 GPU ceiling 2150 MHz: +6-7 % on the start screen, stable, 81 C |
| `3a88f157b6` | `2cae0184b8` | 2026-10-15 | exp: 0127 the compute rings work: F31's machine-down was our CONTEXT_CONTROL |
| `7fef25e5fa` | `c27fc588ae` | 2026-10-15 | docs: ADR 0009 (proposed) asynchronous compute buffers on a compute ring |
| `c45e123df6` | `a0c937db17` | 2026-10-15 | feat(backend): jobs on a compute ring (ADR 0009 step 1) |
| `74ead13cde` | `d1681c732f` | 2026-10-15 | exp: 0128 the second title's compute buffers fit a compute ring as they are |
| `963e125dca` | `f6d3f54a6c` | 2026-10-15 | feat(selftest): compute-ring ladder (ADR 0009 step 2), not run yet |
| `7070a904e3` | `54f0a69875` | 2026-10-15 | feat(kytyplus): BC5_DIRECT_COMPUTE_RING routes compute buffers to a compute ring |
| `a45f25af27` | `5a456258e3` | 2026-10-15 | feat: cross-ring waits and ring dependencies (experiment 0129 knobs) |
| `75283b3500` | `37870ca9cf` | 2026-10-15 | exp: 0129 compute ring for the second title: start screen 32-34 -> 41-42 fps |
| `782209ca76` | `a7be87a2ff` | 2026-10-15 | exp: 0130 the menu breakage is not the compute ring's: one ring breaks as often |
| `0c8e0ef228` | `e869e284a2` | 2026-10-16 | exp: 0131 ASTRO BOT on the compute ring: unchanged at 60 fps, water not reached |
| `99efa64f48` | `c7b7d704d7` | 2026-10-16 | exp: 0132 ASTRO BOT on two rings: compute after earlier graphics; geyser 30 fps |
| `1bbb64d565` | `796927b9c9` | 2026-10-16 | exp: 0133 the geyser cycle crosses guest compute queues; two-ring limit 4 ms |
| `639b50db58` | `56fb4a5ac0` | 2026-10-16 | feat: four compute rings, speculative graphics waits, acb head waits kept |
| `be7a0b9014` | `c786c522ce` | 2026-10-16 | exp: 0134 compute heads kept their waits; 0135 four rings and speculative waits |
| `5e38498847` | `89dfdcd3c3` | 2026-10-16 | exp: 0136 the second title's opening keeps its first shot; traversal suspect |
| `609220c8d4` | `9e9f23a8a9` | 2026-10-16 | exp: 0137 bounding the reflection traversal in a patched copy: copy runs, hang stays |
| `c9033a1708` | `e0c15f8473` | 2026-10-16 | exp: 0138 traversal hang inputs: no bad instance record at the hang |
| `af2d0ca210` | `226c45d7e2` | 2026-10-16 | exp: 0139 the traversal walks per-frame trees with the hardware BVH instruction |
| `21580f9a3d` | `8729d1614a` | 2026-10-16 | exp: 0140 traversal hang: not our order, and the walked trees have no cycle |
| `c992384f81` | `654f9984e1` | 2026-10-16 | exp: 0141 ray queries that hit nothing: no hang at New Game, opening still stuck |
| `e9f19cdf2e` | `c04b5953c2` | 2026-10-16 | exp: 0142 the opening: no dropped readback and no failed load behind it |
| `069240d757` | `707c01e0c3` | 2026-10-16 | exp: 0143 upstream KytyPS5 needs fragment shader barycentrics, absent on gfx1013 |
| `ae1aba7118` | `cc36f4b820` | 2026-10-16 | exp: 0144 KytyPS5 HLE vs ours after X in the second title's opening |
| `08dce4547e` | `1c768d6ae1` | 2026-10-16 | exp: 0145 second title saves: answer SaveData_native 2mfSRGdshtk with NOT_FOUND |
| `4b7c5b603d` | `559dbf39ec` | 2026-10-16 | docs: F190 second title loads its saves at the next start (run 573) |
| `8b7abcdf1a` | `987116e55b` | 2026-10-17 | exp: 0146 save slot dates: SaveDataParam mtime from the directory, libRtc local time |
| `8e9f9a3f70` | `b263f63d95` | 2026-10-17 | exp: 0147 the opening after New Game keeps its first shot with saves working (F192) |
| `dd299f7c9d` | `c88f260a1c` | 2026-10-17 | feat(mount): synthesise sce_sys/param.json for packages from the content ID |
| `593dbbee4c` | `1c6bcbe354` | 2026-10-17 | exp: 0148 the second title's saves under PPSA03671 via the synthesised param.json (F193) |
| `bbf97e2ca2` | `2c30d05e6a` | 2026-10-17 | feat(mount): show the CNT container's files under sce_sys (param.json, icons, PlayGo, n... |
| `3548918ad5` | `4eb5f2a7a2` | 2026-10-17 | exp: 0149 the CNT container's files under sce_sys; the host reads the title's own param... |
| `dc4ffb1b1b` | `f19e81a140` | 2026-10-17 | docs: README: the second title saves, bc5-mount shows the CNT files, the opening still ... |
| `dabeb77015` | `df6325dbc8` | 2026-10-17 | exp: 0150 the opening: game thread ticks, audio streams, the animation stream stops aft... |
| `f4756b4f2e` | `74b40c47cb` | 2026-10-17 | exp: 0151 the APR engine does not hold the animation stream; serial reads change nothin... |
| `979c95d40e` | `b59e03e6c9` | 2026-10-17 | exp: 0152 APR caller journal (KYTY_BC5_APR_CALLERS): all reads go through one queue flu... |
| `1c3bd995e3` | `c71b01fc45` | 2026-10-17 | exp: 0153 the opening's clock is Wwise's play position of its audio event, frozen at 4.... |
| `5fc923659f` | `386116359e` | 2026-10-17 | exp: 0154 the opening plays: the AJM Opus decoder was a stub; libopus with packet frami... |
| `5ab584f794` | `8f6738a629` | 2026-10-17 | docs: the AJM Opus job contract as derived in 0154 (docs/formats/ajm-opus.md); F200: pu... |
| `0a2f6a98cf` | `806e2a06e6` | 2026-10-17 | docs: F201 the opening plays through and ends in a GPU reset ~90 s in (maintainer's run... |
| `34aef89670` | `1cbb356834` | 2026-10-17 | docs: F201 — the opening is much longer than 90 s; the reset is not the gameplay entry |
| `1360e50967` | `41acd0d076` | 2026-10-17 | docs: F199 — ASTRO BOT regression run 625 after the AJM changes (title screen 59-60 fps) |
| `5b5e2bf00a` | `b7aa601c33` | 2026-10-17 | exp: 0155 the second title's menu artefact is a wrong bake of new text; fourteen host v... |
| `a6f2c8b46b` | `03fef0c711` | 2026-10-18 | exp: 0156 the second title's start-up card at a few fps was the host holding its thread... |
| `6fbda1a780` | `b6a30a5ae6` | 2026-10-18 | exp: 0157 the second title's menu artefact is GPU state inherited from other processes'... |
| `26e40628f8` | `8354eacd97` | 2026-10-18 | docs: F204 — ASTRO BOT run 626 on the prefix build (title screen 59/56 fps) |
| `ac255824d8` | `1f7b19ecbc` | 2026-10-18 | exp: 0158 save delete stuck on the progress dialog: dialog stand-ins report running unt... |
| `8ba797ef66` | `1136085204` | 2026-10-18 | fix(host): web-browser and invitation dialog stand-ins get the common-dialog status mac... |
| `190656c5cf` | `9cd8632475` | 2026-10-18 | exp: 0159 the opening's hang was the AMM automatic pool never recycled; a GPU index-fet... |
| `2ccea41982` | `d17151ba2e` | 2026-10-18 | exp: 0159 — the remaining opening fault comes from the night scene's compute dispatches... |
| `e478150797` | `3a0f43a538` | 2026-10-18 | docs: F207 — the fault is in the engine's eleven indirect-dispatch programs (runs 729–7... |
| `d50ca072a8` | `e579abc99c` | 2026-10-18 | exp: 0159 — the opening's GPU fault is one BVH compaction dispatch (0x909974400); skipp... |
| `f927d97d34` | `8e248626bf` | 2026-10-18 | exp: 0160 — the F207 fault is the geometry engine reading address 0 through a system-pr... |
| `9dbfcc1a6b` | `cdac9b6315` | 2026-10-18 | exp: 0160 continued — the compacted list's consumers write nothing for the GE; without ... |
| `780a13f827` | `daac274045` | 2026-10-18 | exp: 0160 — run 782: the hang is not the prefix's CLEAR_STATE; fence-timeout knob for t... |
| `5aadeb0223` | `ba88d859f9` | 2026-10-18 | host: BC5_DIRECT_FENCE_TIMEOUT_MS in the patch (exp 0160) |
| `ecc3226ccf` | `565cd5b8a9` | 2026-10-18 | exp: 0160 — runs 783-784: the kernel's 2-s ring reset beats the register dump; WD/TF ba... |
| `050fb01b9c` | `130c27f8ea` | 2026-10-18 | exp: 0160 — run 785: the GE's address-0 read is survivable once, a repeat hangs a job a... |
| `1d97cc3ea7` | `682f5158b6` | 2026-10-19 | host: carry SET_BASE, program and user data across a queue's buffers (F209) |
| `ddb1a1ee45` | `7cb9777c71` | 2026-10-19 | exp: 0162 — the second title's speed changes are frame-time changes from the host's per... |
| `3036c73e48` | `d7d0df0fa8` | 2026-10-19 | fix(host): zero pages for a learned window at address 0 start above amdgpu's reserved b... |
| `6257ec1bf7` | `f9f4bed833` | 2026-10-19 | feat(host): submission chains behind BC5_DIRECT_CHAIN=1 (ADR 0010), unmeasured |
| `432c2d551a` | `b9c60a57b5` | 2026-10-19 | exp: 0160 — run 788: amdgpu.noretry=1 does not make the first-64-KiB read survivable; v... |
| `d2fa813785` | `92b88fc5cd` | 2026-10-19 | docs: review AnyPS5's system libraries for ports into the KytyPlus host |
| `eb16869284` | `4201ec50bd` | 2026-10-19 | exp: 0163 — submission chains: the ring thread's ACBs chain (submissions 4,400 → 2,700/... |
| `ea977d0444` | `c6188346c1` | 2026-10-19 | feat(scripts): bc5-build.sh, one idempotent fetch-and-build for the BC-250 |
| `811454836e` | `ca19242a4f` | 2026-10-19 | feat(kytyplus): rumble from the vibration ports when the pad has no audio sink (AnyPS5 ... |
| `8c13d1f096` | `dfba0210fd` | 2026-10-19 | feat(kytyplus): NpManager state-callback delivery for a signed-out user (AnyPS5 port 2) |
| `2b2c2cf89d` | `3d7dbd70d3` | 2026-10-19 | feat(kytyplus): the three NpTrophy2 exports KytyPlus lacked (AnyPS5 port 3) |
| `38902a1429` | `0b3bfcb3d9` | 2026-10-19 | feat(kytyplus): save-data search sort keys, patterns and blocks accounting (AnyPS5 port 4) |
| `e86abf2ce7` | `e2f8666faf` | 2026-10-19 | fix(kytyplus): make GameController::InstanceId public and non-const (port 1 follow-up) |
| `13bc0a9d9b` | `91018b7647` | 2026-10-19 | Merge remote-tracking branch 'origin/main' into ports/anyps5-1-4 |
| `5cc7565c95` | `1b108f4347` | 2026-10-19 | feat(host): a menu bar in the emulator window (ADR 0011, experiment 0164) |
| `8efd798aac` | `273e8a5392` | 2026-10-19 | Merge origin/main (AnyPS5 ports 1-4) into the window-menu work |
| `c69f14131b` | `e2632e0027` | 2026-10-19 | exp: 0165 — submission chains reach the game thread: COND_EXEC segment-local (ADR 0010 ... |
| `27338e4052` | `de397f155f` | 2026-10-19 | feat(host): one logging switch for the session (ADR 0011 §6): Emulation > Logging, BC5_... |
| `b19430d2f0` | `4d4357d1e1` | 2026-10-19 | docs: HANDOFF as of 2026-10-19 — open questions answered or reworded, D18 and ADR 0012 ... |
| `4df0afcf0f` | `dc9e9d7768` | 2026-10-19 | exp: 0164 — the union patch (27338e4) built on the box, empty window verified |
| `ff45ba2dca` | `c547b44079` | 2026-10-19 | fix(host): the window's pause stops the title's clocks; audio PCM dump; pause/resume in... |
| `702b9c9d59` | `ab9e628b42` | 2026-10-19 | exp: 0168 — the chains across ioctls (BC5_DIRECT_CHAIN=2) do not change the audio push ... |
| `849fa7e318` | `bbdb7743c6` | 2026-10-19 | fix(host): the virtual-range table is edited in place, no full sort per AMM map (exp 01... |
| `f7496d68fc` | `739938d50e` | 2026-10-19 | exp: 0160 — the F208 hang also comes with both skips on (maintainer's 12:19 play); the ... |
| `6a06a39af3` | `4f98231985` | 2026-10-19 | fix(host): the direct mapper's BO merge moves at most 512 mappings a pass (exp 0167, F222) |
| `1973e7b597` | `e20a59f1dc` | 2026-10-19 | exp: 0160 — the 12:39 hang's buffer has no indexed draw; the timeout probe now journals... |
| `29469e458a` | `25b5679f1e` | 2026-10-19 | exp: 0160 — the GE's address-0 read comes with a one-point GS fast-launch draw (13:01 p... |
| `551d0a1c2b` | `b26f0584c2` | 2026-10-19 | exp: 0160 — dropping the fast-launch point draws by state is too broad (the engine's ma... |
| `6093cadedb` | `6ba1af989f` | 2026-10-19 | exp: 0160 — 13:17 hang: the same fast-launch draw with 14 records; the probe dumps the ... |
| `2758b58ab8` | `83080a5a05` | 2026-10-19 | exp: 0160 — 13:54 hang: the address-0 reads are a two-minute non-fatal stream, the time... |
| `19dc16f12a` | `950afd6226` | 2026-10-19 | exp: 0160 — 14:52 session: no GPU hang; the transition stalls are the title's own threa... |
| `47c279fbd6` | `98fd5f97f7` | 2026-10-19 | fix(host): the mapping rebuild handles only new mappings, not all ~17,000 against every... |
| `96955b69f9` | `40f4f97406` | 2026-10-19 | exp: 0169 addendum — chains across ioctls on the F221-F223 build: 33 -> 48 flips/s, aud... |
| `a5a97106d0` | `f7ba38f76d` | 2026-10-19 | perf(direct): mappings kept sorted and counted per BO; the BO lists no longer walk ever... |
| `c1c8691c88` | `a5533d04a6` | 2026-10-19 | exp: 0171 — deferred flips retried for the second title: menu text intact, no frame gai... |
| `d7b12d7e0d` | `087dad45bb` | 2026-10-19 | exp: 0172 — logging off, timing only: 43.5 fps without chains, 49.4 with them (F227); K... |
| `1819274bc5` | `c33d045d97` | 2026-10-19 | exp: 0173 — the game thread's label waits are the title submitting the writer after the... |
| `8190146e0a` | `6140111111` | 2026-10-19 | exp: 0174 — measurements that survive the logging switch (KYTY_BC5_MEASURE), on in the ... |
| `64483cfa6f` | `c60b414fee` | 2026-10-19 | exp: 0160 — warning: the looping hang watcher (halt_waves at 0.6-s stalls) manufactures... |
| `6d57956a17` | `f3735327b5` | 2026-10-19 | exp: 0175 — real play: frame-rate drops drag the audio; the GPU watcher froze the GPU (... |
| `b5b8ff32e2` | `a67275fb84` | 2026-10-19 | exp: 0160 — the reproducible post-save hang is a second copy of the reflection traversa... |
| `bca28aff25` | `f6938ae1ae` | 2026-10-19 | docs: HANDOFF — the post-save traversal-copy finding is F232 (F209 was taken), tied to ... |
| `bea274a7e7` | `8e37be69df` | 2026-10-19 | fix(host): the window no longer pauses on SDL background events or Space autorepeat; ea... |
| `fb5406cee1` | `e5b421b147` | 2026-10-19 | exp: 0160 — runs 836–838: with the compaction running every reflection-traversal varian... |
| `0dea9020eb` | `b3ea4edc3e` | 2026-10-19 | feat(host): lean build without tracing, journals and measurements; start screen still a... |
| `6872792c23` | `b18092cda4` | 2026-10-19 | exp: 0178 — the box has run the second title 1.5-2x slower since 17:57 for any build; g... |
| `21d2c45522` | `1a400a219a` | 2026-10-19 | exp: 0160 — caveat: the box runs the title 1.5–2× slower since the 17:57 halt_waves dum... |
| `0fdd889b42` | `1be0ceab94` | 2026-10-19 | exp: 0160 — the slow-box caveat corrected: RenderScale 1.70 in input.cfg (F237), not th... |
| `53ed4767e4` | `bb0e7401d6` | 2026-10-19 | exp: 0179 — the second title's halved frame rate was its timestamp scale 1.70 saved fro... |
| `5ac72bb5bd` | `8a95c534b9` | 2026-10-20 | fix(host): the audio output holds like the console's instead of dropping its queue afte... |
| `8c9dccb942` | `a8f726ff1d` | 2026-10-20 | feat(host): SDL's native PipeWire audio backend by default, a downmix that cannot clip;... |
| `3ef4048e86` | `c7a4db2e83` | 2026-10-20 | fix(host): a pause holds the title's sound with its clocks; chains by default for the s... |
| `86731057f7` | `cb4c81e4bc` | 2026-10-20 | exp: 0183 — the second title's looped sounds and cutscene run 1.3-2x fast: per frame (1... |
| `aa73775c00` | `15cc6d185b` | 2026-10-20 | exp: 0184 — 30 fps by default for the second title: its clock runs at real time in nigh... |
| `eac3b93747` | `e531d75205` | 2026-10-20 | exp: 0185 — the second title's clock drifts in night scenes with varying frame times (s... |
| `b535bdac94` | `1027bbb999` | 2026-10-20 | exp: 0186 — the second title's night drift is older than every change since 10-19 09:06... |
| `beff2c369a` | `e8ab6c828c` | 2026-10-21 | exp: 0187 — the second title's clock already ran fast on the builds of 2026-10-18 morni... |
| `6dd4f136e7` | `08d4f1b0a5` | 2026-10-21 | docs: review of 15 analogous PS4/PS5 projects for the host (F246) |
| `dccbd868c8` | `6c3607633e` | 2026-10-21 | exp: 0188 — the second title's speed-ups were its Wwise sink rendering ahead: the Audio... |
| `8c0f80c009` | `1a91088a55` | 2026-10-21 | docs: the maintainer confirms the second title plays smoothly with correct sound, pause... |
| `3ff9260d64` | `a00bee1a2c` | 2026-10-21 | exp: 0189 — the GE's address-0 reads were the tessellation-factor fetch: the title's TF... |
| `eaa8862b07` | `c20664d61a` | 2026-10-21 | docs: the second title's launcher programs its TF ring and skips traversal variant 0x11... |
| `8d0669eb23` | `52c84b8291` | 2026-10-21 | feat(host): an on-screen counter of the title's frame rate and a MangoHud setup for rec... |
| `4cf2848893` | `51e787ea37` | 2026-10-21 | feat(scripts): an OBS Studio profile for recording on the BC-250 (software x264) |
| `c2f38e5d33` | `f7d7b217ae` | 2026-10-22 | feat(scripts): astro-route.sh, ASTRO BOT into gameplay by script with saves restored |
| `d6700677c1` | `d457aa921f` | 2026-10-22 | exp: 0193 — the DualSense touchpad press was dropped by the host's button table (F252) |
| `a9916340c6` | `0fa52c2594` | 2026-10-22 | exp: 0190-0192, 0195, 0196, 0198 — the reflection traversal's FLAT apertures (F249-F251... |
| `75e84a8c15` | `deb8a085fa` | 2026-10-22 | exp: 0199 — the TCP write faults are the title's first-use clears over AMM pages it nev... |
| `6fed2445ce` | `e7f533e338` | 2026-10-22 | exp: 0194, 0197 — the night lake's patchwork: surface the title stops drawing in patche... |
| `8359e91623` | `0d3c50f76b` | 2026-10-22 | exp: 0202 — a watched play session with BC5_DIRECT_AMM_PRT=1: 19 minutes without a GPU ... |
| `5c13c238c7` | `b3a81d033d` | 2026-10-22 | exp: 0200 — the cutscene slow motion is the clock voice stopping at a loop end when its... |
| `056657c46a` | `14f6035774` | 2026-10-22 | exp: 0201 — the lake's flat cells are streamed sparse texture tiles sampled while empty... |
| `7ea2b0ad1c` | `17f0014b94` | 2026-10-22 | exp: 0204 — the 16:36 machine-down caught by the off-box stream: three of four follow a... |
| `1fe54cc3a4` | `e76025d200` | 2026-10-22 | exp: 0206 — the given-up wait's label 0x12004b3c38 is cleared by the title's CPU code o... |
| `f5e3142c0e` | `1029c0f0b3` | 2026-10-22 | exp: 0207 — a 100-ms game-thread wait (BC5_DIRECT_DCB_WAIT_MS=100) serves 16 of 17 give... |
| `567f65037d` | `3a942a9ace` | 2026-10-22 | exp: 0208 — repeat pair for the 100-ms game-thread wait: given-up waits 29 -> 1 in 20 m... |
| `3d172b9a64` | `cb6c0c24bc` | 2026-10-22 | exp: 0203 — the host serves the clock voice's reads correctly; the stall follows a late... |
| `1645dd2003` | `f1ccd42bad` | 2026-10-22 | docs: F266 — the multi-second GPU stretches are not caused by the compute-state prefix |
| `ac7d76c363` | `07a77a275c` | 2026-10-22 | exp: 0210 — the maintainer's 15-min play with the reflections on and AMM_PRT: no hang, ... |
| `5297d2521f` | `14ffce595d` | 2026-10-22 | exp: 0205 — the night lake's patchwork is not a missing input the host failed to serve ... |
| `f2c2bc5bf9` | `da87a0b1da` | 2026-10-22 | exp: 0209 — label-wait latency: 98-99 % end within 4 ms, the tail is the host's state; ... |
| `2749715774` | `46b71dceee` | 2026-10-22 | exp: 0213 — a 400-ms wait limit acts like 100 ms; the wait limit costs no visible frame... |
| `7f840c46cf` | `2a06a7f6a7` | 2026-10-22 | exp: 0212 — the lake goes clean when the title lowers MIN_LOD in its bindless texture t... |
| `9a2d11845a` | `858bb819b9` | 2026-10-22 | feat(kytyplus): APR read-ahead v2 on by default in the shared builds (exp 0214, F273) |
| `0c618631e7` | `2af8c4ae75` | 2026-10-22 | exp: 0215 — the slow label waits are not host stalls: the title runs (2.2 cores) while ... |
| `30b9782b6a` | `91d92c6c4c` | 2026-10-22 | exp: 0211 — on the frozen lake view the reflection traversal costs ~nothing; the BVH co... |
| `92b1115267` | `a8aeeada05` | 2026-10-22 | exp: 0216 — a condition-variable wait removes the APR readers' idle polling cost; frame... |
| `4fea6c3437` | `8c2acb5d3f` | 2026-10-22 | docs: F276 — the APR readers' condition-variable wait removes their idle polling cost (... |
| `71dd72ba4a` | `8e615abd5d` | 2026-10-22 | exp: 0218 — in real play the reflections run at 37.5 flips/s with only the BVH compacti... |
| `96aaf4b14f` | `8ce6cb2c87` | 2026-10-22 | docs: F277 caveat — the reflections are drawn at least in part with the compaction skip... |
| `16fc66fa6d` | `0a1544cf34` | 2026-10-22 | docs: F277 — reflections on by default in the second title's launcher (the maintainer's... |
| `c57b727d6b` | `a418e3614d` | 2026-10-22 | docs: F277 note — BC5_DIRECT_AMM_PRT=0 needs the launcher's unset (presence turns PRT on) |
| `6649dc5205` | `0c51be0928` | 2026-10-22 | docs: F277 — screenshots show the traversals' reflections reach the image with the comp... |
| `fa6148e2a7` | `ffafd7cc16` | 2026-10-22 | exp: 0217 — none of the lake water's shaders writes texture feedback; the four umin+sto... |
| `7b90cd100c` | `c65e23cee6` | 2026-10-22 | exp: 0219 — at every give-up the GPU had nothing of ours to run; the label's writer is ... |
| `f554432007` | `ebebd8cc20` | 2026-10-22 | exp: 0220 — back-to-back pair: the APR readers' condition-variable wait saves CPU and s... |
| `9f61963459` | `4c531dbb8b` | 2026-10-22 | feat(kytyplus): APR read-ahead readers wait on a condition variable instead of polling ... |
| `cee0463b5b` | `a96a298eb9` | 2026-10-22 | exp: 0221 — the given-up label is GPU-written and the compute buffer behind it is alrea... |
| `5e5edbb953` | `2f321d4a9b` | 2026-10-22 | exp: 0223 — nothing in the give-up chain waits on the title's CPU; the wait is for GPU ... |
| `c28e01266d` | `e067ca9954` | 2026-10-22 | docs: rewrite README — PS5 emulator pitch first, status, then technical |
| `5c6e4762bd` | `5f6ffe6018` | 2026-10-22 | exp: 0224 — no doorbell is rung while the game thread waits: the host's synchronous wai... |
| `5df3c74150` | `4733ea6e88` | 2026-10-22 | docs: ADR 0013 (proposed) — at a cross-queue wait, hold the buffer's tail, not the subm... |
| `27d9d90320` | `e9ec1d7c3f` | 2026-10-22 | exp: 0225 — at a 100-ms limit no wait is given up and the F284 chain does not form; the... |
| `0fc1ab5cf2` | `1686ca8d66` | 2026-10-23 | docs: ADR 0013 amended — the test build holds the submission through ADR 0010's held ch... |
| `09458118eb` | `ada2ac9d54` | 2026-10-23 | tools: daily lossless compression of old capture journals on the box (bc5-compress-capt... |
| `1373372760` | `b02a2c603f` | 2026-10-23 | exp: 0227 — slow loads: not the 10-22 code; the start is latency-bound on ~8,000 small ... |
| `39eb56f331` | `38217de431` | 2026-10-23 | exp: 0228 — loads are equal with the fixed read-ahead, and a cold start is ~12 s once t... |
| `dad92cc343` | `0f9f231ce6` | 2026-10-23 | feat(kytyplus): APR read-ahead back on with its fix (exp 0229, F288); launchers default... |
| `22ea5f4738` | `d53e575524` | 2026-10-23 | exp: 0230 — bc5-mount startup preload works but gains ASTRO BOT only ~1 s; not adopted ... |
| `961ba52488` | `486e8d418e` | 2026-10-23 | exp: 0231 — the lake's clean and patched runs don't differ in the host-side journals, a... |
| `dcb3d50501` | `a63010b664` | 2026-10-23 | exp: 0232 — the lake clears when the title streams the next mip and lowers MIN_LOD (4→3... |
| `000bd4dccf` | `c1c96b7e59` | 2026-10-23 | exp: 0233 — the lake's clean/patched state doesn't follow the title's MIN_LOD drops; a ... |
| `f9aa4f3ea6` | `d39298376c` | 2026-10-23 | docs: README names Marvel's Wolverine in the compatibility table; trademark notice; gam... |
| `41a09cce37` | (dropped) | 2026-10-23 | docs: remove the last two game screenshots from the tree (second title's save-slot menu... |
| `0da3e36e62` | `949a23150f` | 2026-10-23 | exp: 0234 — the water's per-frame constants don't differ between clean and patched fram... |
