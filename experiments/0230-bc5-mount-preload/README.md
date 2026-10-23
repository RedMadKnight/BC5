# 0230 — bc5-mount: trace a title's startup reads, preload them at mount (ADR 0014)

**Question.** Exp 0227 (F286) found ASTRO BOT's start bound by latency: ~8,000 small dependent reads of the game image
through `bc5-mount`. ADR 0014 proposed tracing those reads once and preloading them into the page cache, in large
chunks, at every mount. Does that shorten the start, and does it hurt anything?

**Setup.**
- **Code** (committed off by default, in `tools/bc5-mount`; ADR 0014):
  - `src/preload.rs`:
    - `BC5_MOUNT_TRACE=<file>` (+ `BC5_MOUNT_TRACE_SECS`, default 120) appends every image read `FileSource` makes as
      `<ms> <offset> <length>`;
    - `BC5_MOUNT_PRELOAD=<file>` makes `bc5-mount mount` start a background thread. It merges the traced ranges (1-MiB
      gaps, 8-MiB chunks), orders them by first use and reads them through its own untraced handle, so the page cache
      holds them;
    - 8 unit tests.
  - Hooks: `io.rs` (`FileSource` traces its reads; `open_untraced`), `main.rs` (the preload starts with the mount),
    `lib.rs`. Standard library only.
- **A2, the build and the traces (2026-10-23 11:43–11:54).**
  - My local `tools/` tree was built in `~/bc5-work/exp0230` with `CARGO_TARGET_DIR` there; the shared
    `bc5-tools-ubuntu` is untouched.
  - `cargo test --offline -p bc5-mount`: lib 67 passed (the 8 preload tests among them); integration 15 and 10
    passed, 1 ignored.
  - `cargo clippy --all-targets -- -D warnings`: clean (one old warning in the vendored `oozextract`).
  - `cargo fmt --check`: clean, on the laptop's own toolchain; the box has no `rustfmt`.
  - The first build caught two borrow errors in `preload.rs`, fixed.
  - Release binary md5 `12fe9883…` (`raw/cargo-*.txt`).
  - Launcher copies `play-astro-0230.sh` and `play-pkg-0230.sh` take `BM=${BC5_MOUNT_BIN:-…}`, so every run uses this
    build.
  - One cold traced start per title (`raw/trace-summary.txt`; the traces stay on the box: 1.9 MB, and they describe
    the images' layout):
    - ASTRO BOT (TA1): 82,539 reads in 35 s, 1,270 MiB, median 11 KiB. The plan is 1,692 MiB in 1,079 chunks; the
      first 12 s take 1,046 MiB in 927 chunks.
    - The second title (TP1): 1,826 reads, 472 MiB, median 256 KiB → 479 MiB in 123 chunks. Its startup comes mostly
      from `bc5-mount`'s disk cache file, which is not traced.
- **A3, ASTRO BOT, 11:56–12:21.**
  - Arms: cold BASE, PRE, PRE, BASE, then after a full run BASEW, PREW, PREW, BASEW. The PRE arms use TA1's trace.
  - 160 s each, presses at 70 and 95 s (the title is up by ~40 s), screenshots throughout.
  - Measured: "presents" from the shots (as in exps 0227/0228), the startup reads' end and the level load after the
    95-s press from `/proc/<pid>/io`, the drive probe, and the preload's own log line.

**Result.**
1. **The preload works.** It read 1,079 chunks, 1,692 MiB, in 6.6 and 6.7 s cold and in 4.7 and 4.8 s after a full run
   (`raw/PA*-mount.log`).
2. **Its effect is small** (`raw/load-A3.txt`, `raw/presents-A3.txt`). Seconds from the launcher's start:

   | run | arm | emulator start | "presents" | intro | title | startup reads end (from emulator start) | level load (after the press) |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | PA1 | BASE, cold | 3.7 | 13.2 | 18.3 | 42.2 | 13.2 | 28.2 |
   | PA2 | PRE, cold | 4.1 | 12.5 | 17.8 | 39.2 | 12.2 | 27.2 |
   | PA3 | PRE, cold | 4.3 | 12.9 | 18.0 | 39.9 | 11.6 | 28.6 |
   | PA4 | BASE, cold | 2.6 | 12.4 | 17.5 | 39.5 | 13.1 | 26.1 |
   | PA5 | BASEW | 1.5 | 10.2 | 16.0 | 37.8 | 12.2 | 27.2 |
   | PA6 | PREW | 2.5 | 10.0 | 15.5 | 38.1 | 11.2 | 27.2 |
   | PA7 | PREW | 2.5 | 9.8 | 15.4 | 37.6 | 11.2 | 26.2 |
   | PA8 | BASEW | 1.4 | 10.3 | 15.5 | 37.9 | 12.2 | 27.2 |

   - With the preload the startup reads end about 1 s sooner (cold 11.6–12.2 against 13.1–13.2 s; after a run 11.2
     against 12.2 s).
   - "presents" moves by 0.5 s at most, within the shots' ~1.1-s resolution.
   - The level load is unchanged: the list covers only the startup.
   - Drive probe 589–642 MB/s, except PA1 at 137 MB/s, which was no slower.
   - All 8 runs: no crash or kernel line, the live saves back identical, every run reached the hub (~12 GB read).
3. **Texture pop-in.** The route loads the hub (the space map), not a 3D level. Three PA4 shots at ~125–140 s show it
   stable, with no pop-in visible at 640 px. A pop-in test needs a route into a level and full-resolution shots.

**Verdict.**
- **The preload works but gains about 1 s at the startup reads' end, and ≤ 0.5 s at "presents".** It is not worth a
  shared `bc5-mount` change plus per-title lists to maintain.
- Since the drive was freed (F286, F287), ASTRO BOT's startup reads run at ~300 MiB/s. Its ~10–13 s to "presents" is
  mostly not I/O any more.
- ADR 0014 is marked "measured, not adopted". The code is committed off by default (the top session's call): it is inert
  without its two variables, and the trace is kept as a diagnostic for later load studies.
- The second title's A3 was not run: its startup is served by the disk cache, and ASTRO BOT showed ~1 s.
