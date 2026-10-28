# 0350 — exp 0349's build into the shared builds

The top session, 2026-10-28, on the maintainer's word after his 18-minute RT-on play of the test shortcut (F432):
"Tak, całość z 0349". Box work under the BOX-LOCK, claimed in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0350/CLAIM.txt`.

**Question.** Does exactly what the test binary fadeebd9 was built from integrate into both shared builds (normal and
lean)? That is exp 0349's IB cut, 0348's carried register, 0346 v3 and 0343's soft-CP bound. And does the integrated
normal build pass the S6N regression with RT off and with RT on?

**Setup.**
- `int0350.sh` (after exp 0342's `int0342.sh`). It refuses to start unless every input has the expected md5:
  - normal ddfb9456, lean 03337c24, archive 44ba4435, `play-pkg.sh` 5b469087;
  - `~/src/bc5` a clean d0c2668;
  - the tree's `bc5LleAgc.cpp` cfeec2f8 and exp 0343's patched copy e7cc2f60;
  - exp 0349's eight backend files as on branch exp/0300-rt-dispatch-sync d37726e, with every other source file of
    that copy equal to the shared checkout.

  Then:
  1. the eight files go over `~/src/bc5/backend`;
  2. exp 0343's unit goes over `~/src/KytyPlus`;
  3. the archive and both emulators are rebuilt with ninja;
  4. `play-pkg.sh` gets one line after the 0341 guards, the test launcher's
     `BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8` (the cut needs no switch; its default is
     0xf0000 dwords);
  5. the tree's diff against f266548 is written out as the candidate patch 0001 (D19).

  Backups and the undo are in `~/bc5-work/exp0350/integration/`. `input.cfg` is not touched: RT on and Polish since
  exp 0342.
- The tree's diff before the change is 12716e3b, equal to main's `backend/kytyplus-patches/0001-bc5-lle-agc.patch`.
- `s6n0350.sh` is derived from `s6n0342.sh` by `mk-s6n0350.pl`: the paths become 0350's, and two variables are
  required in the emulator's environment, `BC5_DIRECT_HOST_INDIRECT=learn:1100000000` and `BC5_DIRECT_SOFT_WAIT_MS=8`.
  The run's `-0341.txt` summary also keeps the 0346, 0349 and `cs refused` lines.
- The regression runs: R1, RT off, 600 s, then R2, RT on, 600 s, on the S6N route through the integrated launcher, with
  the kernel log streamed to the laptop.

**Result.**
- **The integration (07:51–07:52, `raw/int0350.out`).** Every input check passed, and the tree's diff before was 12716e3b, main's patch 0001.
  - The archive is now bb50b2e0 (0 warnings; `ib_split.cpp.o` and `host_indirect.cpp.o` in it).
  - normal ddfb9456 → **affa0c22** and lean 03337c24 → **cd7ea936**, each with one unit recompiled and relinked. The warnings were 5 and 8, among them an unused `IT_DMA_DATA` constant in `bc5LleAgc.cpp`.
  - Both binaries carry the 0349 cut line, the 0346 switch line, the 0348 `cs refused` line and the 0341 switches. The `soft-cp wait` journal line is in the normal build only: the lean build compiles every trace out, while the 8-ms bound itself is in both.
  - `play-pkg.sh` 5b469087 → **55531ab6**, one line added (`raw/play-pkg-0350.diff`).
  - The candidate patch 0001 is **6ac6cc16** (58,742 lines). It is now main's `backend/kytyplus-patches/0001-bc5-lle-agc.patch`, and main's backend holds the eight files, so main matches the shared builds again (D19, Q19).
- **R1 (S6N, RT off, 600 s), 07:53 → pass.**
  - 36.0 flips/s.
  - No crash line, no kernel line, no TIMEOUT, gfx engine only; 5,384 RT-off drop lines.
  - Live saves unchanged (3f8412c4884ddf14).
- **R2 (S6N, RT on, 600 s), 08:03 → pass**, with no crash, kernel or TIMEOUT line and the live saves unchanged.
  - At t 102 s the route's big frames needed the cut twice: 1,212,560 dwords (title 196,681) and 1,153,776 (title 224,251), each into 2 IBs, 0 refused. These are frames the kernel would have refused without the cut.
  - 29.2 flips/s over 596 s: ~38 a second until t ≈ 268 s, then a steady **~26.5 a second to the end** (`raw/R2-flips-per-10s.txt`). Nothing in the play log marks the change: no refusal, no TIMEOUT, no soft-cp line. The box had been up 12 hours, with MemAvailable ~650 MB and ~1 GB of zram swap in use (`raw/R2-mem.txt`). 0349's R2 and R3 and 0346's R2v3b held ~38–39 after 270 s.
  - The kernel stream holds one `clocksource: Watchdog remote CPU 3 read timed out` line at 08:10:19 and no amdgpu line.
- **R2b (the same, repeated), 08:15 → pass.**
  - **35.8 flips/s**, ~38 a second from t 110 s to the end, with no plateau.
  - One cut: 1,153,808 dwords (title 223,666) into 2 IBs.
  - No crash, kernel or TIMEOUT line; live saves unchanged.

**Verdict.** Integrated. Both shared builds and `play-pkg.sh` now carry exactly what the maintainer played in F432. The integrated normal build passed S6N with RT off and twice with RT on. In each RT-on run the cut kept the route's big frame (title ~200–224k dwords, grown ×5–6) under the kernel's limit, where the same frame was refused at 12:37 the day before. Open: R2's one ~26.5 flips/s plateau from t ≈ 268 s. It is not reproduced in R2b; it resembles 0349 R1b's 26.2 after a refused frame, but here no frame was refused. The cause is not analysed.
