# 0422 — ASTRO BOT's transferring-mount save fix, fixed on in the code

## Question

Exp 0417 found F833's cause (F835): ASTRO BOT calls `sceSaveDataTransferringMount` for another title's save
(PPSA01325, `sce_sdmemory`). The host ignored the title id, created that directory under the running title and
answered "created". The title then read its own save memory as the other title's save and crashed at 5 s
(eboot+0x29c385) on every start after a first save made from an empty directory.

The fix (tag sdt417) was in the shared builds (patch `e3fd8b55`) behind `KYTY_BC5_SAVEDATA_TRANSFER_FIX`, which is
read with `BC5_DIAG_ENV`. It was off by default and compiled out of the lean build, so a fresh install still met F833.

The maintainer, 2026-11-15, to the top session: "Włącz poprawkę zapisu na stałe w kodzie." Once the fix is always
taken, with no switch, do the shared normal and lean builds:

- build;
- start ASTRO BOT on the kept bad save;
- survive F833's own sequence;
- leave the second title as it was?

## Setup

- **`mk0422.py`** (tag sdt422), applied to the shared tree `~/src/KytyPlus` with patch `e3fd8b55`. The generator
  replaces the block from the switch's comment to the end of `SaveDataTransferringMount`; the old block must match
  e3fd8b55's byte for byte (md5 `3721b9e5…`).
  - `bc5_sdt_on()` and the word `KYTY_BC5_SAVEDATA_TRANSFER_FIX` are gone.
  - The directory is always the one of the title the call names.
  - When the save does not exist, the call answers NOT_FOUND and creates nothing.
  - When it exists, the save is mounted as "not created" (`mount_save_data(..., 0u, ...)`).
  - The `CreateDirectories` branch is gone, since it is dead code now.
  - The two `[bc5] sdt417` stderr lines are under `#ifndef BC5_LEAN`.

  Dry run on the laptop: one edit, brace balance 0, and a second application refused.
- **`int0422.sh`** (from exp 0421's `int0421.sh`): copies (`~/bc5-work/exp0422/swap/*.before-0422`), the generator,
  the new patch and its checks:
  - `exp 0372` = 5;
  - the same file list;
  - `BC5_GUARD_MAP_RULE` / `BC5_GUARD_PRT_BG` / learned unchanged;
  - no `KYTY_BC5_SAVEDATA_TRANSFER_FIX`.

  It then runs `ninja` in both shared build directories, checks that the backend archive is unchanged, and compares
  switch words by `strings`: normal loses exactly that one word, lean gains and loses none, and the sdt417 text is in
  normal only. Any failure runs `undo0422.sh`.
- **`undo0422.sh`**: back to `e3fd8b55` (normal `50d0885e`, lean `7998d6a4`), checked by md5. It chains before
  exp 0421's `undo0421.sh`.
- **`chk0422.sh`**: runs on the swapped shared binaries with no switch set, RT on, `ulimit -c 0`, private save
  directories only. A real pad key (evtest) stops the chain.
  - ASTRO BOT runs on the private `exp0413/n/wda` copies.
  - The second title's runs reset their private copy from exp 0412's one named snapshot
    (`exp0412/night/saves-named`, hashed by its own method under LC_ALL=C; LESSONS R45).
  - Corrected after the run (Codex, 15:40 UTC). The version that ran also copied the maintainer's live saves and
    compared their sums before and after, against R45. Both are removed from `chk0422.sh` and `walk0422.sh`. The copy
    `~/bc5-work/exp0422/saves-live-before` was made and is not used.
  - `a1n`, `a1l`: 30 s on the kept bad save (`wda/_SaveData.sm0`), normal and lean.
  - `a2l`, `a2n`: 120 s from an empty save directory with a cross at 30, 45, 60, 75 and 90 s (exp 0417's
    `save0417k.sh`, the way F833's large first save is written), then a 30 s second start (`a2ln`, `a2nn`).
  - `w1n`: the second title's walk to G+240 on normal (`run0413p.sh`, the route gated on the journal).
  - `w2l`: the second title on lean, 420 s. Lean writes no journal and no log, so `run0413p.sh`'s gated route
    cannot run on it. The route goes by time instead: a cross at 90, 100 and 108 s, then exp 0379's walk from 170 s
    for about 240 s. Pass means still running at the end with no kernel line and no crash text. This shows the start,
    the menus and the load did not regress; it gives no frame numbers, and it cannot prove gameplay was reached.
- **`chain0422.sh`**: one BOX-LOCK line for everything. The top's waiting NAS line is taken out first, as its GO says.
- **`r0422.sh`**: the laptop driver; the kernel log is streamed to `raw/kern-0422.txt`.

## Result

### The swap: `chain0422.sh`, 2026-11-15 16:25:41–16:26:27

Raw output: `raw/chain0422.out`.

| | before | after |
|---|---|---|
| patch 0001 | `e3fd8b55` | **`4945ef1b`** (40 lines differ, exp 0372 lines 5, no `KYTY_BC5_SAVEDATA_TRANSFER_FIX`) |
| shared normal | `50d0885e` | **`9da2a9d5`** |
| shared lean | `7998d6a4` | **`f942676c`** |
| backend archive | `9aab722c` | `9aab722c` (unchanged) |

- The unit `libSaveData.cpp` was compiled once per build.
- Warnings: normal 1, lean 2. The lean `libSaveData` warnings are older than this change: the deprecated
  `wstring_convert` in `stringUtils.h` and the unused `bc5_sdm_switch`. None comes from the new text.
- Switch words: normal −[`KYTY_BC5_SAVEDATA_TRANSFER_FIX`] +[]; lean −[] +[].
- The text "sdt417: transferring mount" is in normal 2 times and in lean 0 times. The switch's report line
  ("transferring mount fix") is in neither binary.

### ASTRO BOT on the swapped shared binaries, no switch set, 16:26:28–16:34

| Run | Build | Save directory | Result | The save-memory file afterwards |
|---|---|---|---|---|
| a1n | normal | the kept bad save (`.sm0`) | PASS 30 s; "PPSA01325/sce_sdmemory: no such save, NOT_FOUND (nothing created)" | 83dce7e2 |
| a1l | lean | the kept bad save | PASS 30 s | 83dce7e2 |
| a2l | lean | empty, a cross at 30/45/60/75/90 s | PASS 120 s | **97fb2aba**, 164,965 bytes (F833's large first save) |
| a2ln | lean | what a2l wrote | **PASS 30 s** (F833: ended at 5 s) | 83dce7e2 |
| a2n | normal | empty, five crosses | PASS 120 s; NOT_FOUND line | 97fb2aba |
| a2nn | normal | what a2n wrote | **PASS 30 s**; NOT_FOUND line | 83dce7e2 |

- No kernel line and no crash text in any of the six runs. The laptop's kernel stream holds one `perf: interrupt
  took too long` line and nothing from amdgpu.
- No real pad key in any run.
- The two live-save sums in `raw/chain0422.out` come from the comparison that R45 forbids. They are no result of this
  experiment.

### The second title: not run yet

At 16:26 the top session reported that the maintainer was reinstalling the second title from the NAS
(`BOX-LOCK.nas`). Its note said: run the walk only after that lock is gone. The two runs w1n and w2l were therefore
blocked on purpose by tag files in `exp0413/n/raw`, and `run0413p.sh` refused to start w1n. The "stopped: a kernel
line in w1n" in `chain0422.out` is only the empty result line of that refused run; no emulator started. They run
later as `walk0422.sh` (tags w1nb, w2lb), which refuses while `BOX-LOCK.nas` exists.

## Verdict

**The fix is in the code, always on, in both shared builds: patch `4945ef1b`, normal `9da2a9d5`, lean `f942676c`.**
F833's case passes on lean and on normal:

1. a first save from an empty directory, taken past the first screen, writes the same large file as before;
2. the next start runs, where before it ended at 5 s.

The kept bad save passes on both builds with no switch. Not yet shown: the second title on the new builds (walk0422.sh).

Undo, newest first:

```bash
bash ~/bc5-work/exp0422/undo0422.sh
```

That returns to `e3fd8b55`, normal `50d0885e`, lean `7998d6a4`. One step further back is
`bash ~/bc5-work/exp0421/undo0421.sh`.
