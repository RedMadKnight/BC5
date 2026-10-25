# 0304 — The night lake with the maintainer's actual setup: does the RT reflection traversal add to the patches?

**Question.** The maintainer asked whether the lab findings (F362, F366) help with the patches on the water. Every
lake-bench run so far (exps 0194–0295) went through exp 0194's copy of the launcher from 10-22
(`play-pkg-0194.sh`). Its default skip list is the pre-0218 one, `11d049aa00,11d04a6000,909974400,11d04bb900`, so the
RT reflection traversal never ran on the bench. His own play uses today's `play-pkg.sh`, where the traversal runs
(F218), and his `input.cfg` has `RayTracing.PPSA03671=off`. So in his lake the traversal walks never-built trees, the
case that whitens the lab (F362). Does the lake look different, with more or other patches, when the traversal runs?

**Plan** (the top session, 2026-10-25 ~12:30; one slot after exp 0302; RT off only).
- **The bench:**
  - Exp 0299's scheme (today's launcher `play-pkg-0299.sh` in its private working directory), the shared normal build
    e62a97c6, a private copy of the lake save (`~/bc5-work/saves-lake-1153`, as exp 0194's bench).
  - `input-0304.cfg`: exp 0194's keyboard-off file plus `RayTracing.PPSA03671=off`, as in the maintainer's own
    `input.cfg`. `ab0304.sh` refuses to run without that line.
  - `bench0304.sh` is exp 0293's `bench0293.sh` route on that bench:
    - the first ✕ at 90 s (the start-up load took 47–73 s in exp 0299);
    - slot 3 from the save list, then the lake bench's load and Photo Mode steps and its camera move;
    - 13 frozen-view shots 5 s apart, exp 0197's `patch0197.py` patch share.
  - `ab0304.sh`: the lock line, the 3-s dmesg stop, the live saves checksum before and after.
- **Runs:**
  - W1, the maintainer's play setup: RT off, the launcher's defaults (traversal running; 0x909974400 skipped).
  - W2, the same with the traversal skipped (`BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`).
    This is the old bench's setting on today's build.
  - Each run's journal shows the RT state (the "ray tracing off" drops of the build list) and the skip lines.
- **Measured:**
  - the patch share per frozen-view shot, W1 against W2 (exp 0197's metric: clean < 5 %, patched ≥ 8 %);
  - one shot per run viewed in the session scratchpad and deleted right after.
- **Rules:** the live saves are never used; the kernel stream; stop at the first reset or machine-down; no images in
  the repo.
- **Reading:**
  - If W1 shows more or different patches than W2, the traversal adds to the water in the maintainer's play, and F362's
    RT-off launcher change would help there too.
  - If W1 equals W2, the lake's patches are only the depth-writer holes of F342–F359.

**Setup as run** (the top session's GO of 12:50 CET; boot 664515e3; launcher `play-pkg.sh` ac7a9a57 since 12:49, with
the MangoHud integration (F367); the shared normal build 226bcb82).
- **12:51.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after each run).
  - `play-pkg-0304.sh` was derived from ac7a9a57 by exp 0299's three edits; its diff is the four expected lines
    (`raw/play-pkg-0304.diff`).
  - `input-0304.cfg` sets RT off (`raw/input-0304.cfg`). Exp 0299's working directory got 5 new symlinks for
    entries made since 10:22.
  - The kernel stream ran throughout (`raw/window.kern.txt`).
- **W1, 12:52–12:56:** the launcher's defaults, so the traversal ran.
- **W2, 12:56–13:01:** `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`.
- **Both runs:**
  - RT off: about 2,850 "ray tracing off" drops of the build list in each journal;
  - skip lines only as asked: 0x909974400 in W1; 0x11d049aa00, 0x11d04bb900 and 0x909974400 in W2's sampled lines;
  - route and Photo Mode as planned, 13 frozen-view shots each (`raw/W1.out.txt`, `raw/W2.out.txt`).
- **Shots viewed** in the session scratchpad and deleted right after: W1 ts02, W2 ts03 and ts10. No image is in the
  repo.
- **Released 13:01:53** (BOX-QUEUE line 94).

**Result** (`raw/`).
- **No kernel event:** 0 fault lines in both runs, the amdgpu dmesg count 120 before and after, no stream lines.
- **The patch share per frozen-view shot** (exp 0197's metric):

  | run | traversal | ts00–ts06 | ts07–ts12 |
  |---|---|---|---|
  | W1 | running | 28.0, 26.7, 27.2, 28.5, 22.0, 27.1, 29.8 % | 29.0, 25.0, 12.8, 9.9, 16.3, 13.1 % |
  | W2 | skipped | 6.6, 0.7, 0.8, 0.7, 0.7, 2.4, 1.5 % | 12.6, 19.2, 18.7, 18.8, 18.9, 20.2 % |

- **The views:**
  - W1 ts02 (traversal running, 28 %) shows the lake's known artefact: a checkerboard of flat, lighter tiles over the
    water, with the rippled surface between them.
  - W2 ts10 (traversal skipped, 18.8 %) shows the same checkerboard.
  - W2 ts03 (0.7 %) shows dark, unbroken water.
  - Neither run shows white or any other artefact of its own on the water.
  - The two runs' frozen camera stood slightly differently: W1 looks further out over the lake.

**Verdict.**
- **The lake's patches do not depend on the RT reflection traversal.**
  - The same checkerboard appears with the traversal running (W1, the maintainer's setup) and skipped (W2, the old
    bench's setting on today's build).
  - The difference in the shares is the lake's usual switch between patched and clean phases within and across runs
    (F342–F359; exp 0295's W295a went from patched to clean, W292a was clean throughout). One run each cannot rank
    them.
- **Answer to the maintainer's question:** the lab's findings (F362, F366) do not explain the water's patches, and
  F362's RT-off launcher change would not fix them. They are the depth-writer holes of F342–F359.
- **For the lake work, a useful by-product:** today's launcher and build reach the lake view by the old route, so the
  lake bench can move to today's setup (exp 0299's scheme) for further runs.
