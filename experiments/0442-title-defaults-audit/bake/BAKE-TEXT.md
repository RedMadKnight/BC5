# Bake 1 (exp 0442, tag bake442): text for README, HANDOFF and CLAUDE.md, written before the run

The values in ‹›, such as the md5s, the word counts and the A/B figures, are filled in from the swap's log. Nothing
below has happened yet.

**Bake 1a (the top session, 2026-11-22, after bake 1's lean A/B and D28).** The kit now swaps bake 1a, not bake 1.
It is built with `MK0442_KEEP=BC5_DIRECT_DMA_SNAPSHOT MK0442_LEAN_GONE_OUT=1`: header `bca8a81f` (bake 1:
`3f9ee1d9`), private normal `fabfdc1c`, lean `eca99879`, archive `17fb5b25` (`priv3`).
- `BC5_DIRECT_DMA_SNAPSHOT=4096` stays a TITLE2 row, marked D28. It is console timing kept by a host measure with
  a cost on the first title: its fixed 64 MiB GTT ring is about +64 MiB GTT, recovered in 3 of 3 runs of run 2's off-arm.
  The cause is being looked for; it is not a permanent per-title row. So the README's list below has 27 rows, not 28,
  and TITLE2 keeps six.
- `kGone0442` and its report are `#ifndef BC5_LEAN`. Lean gains no word and loses the 4 gone words the shared lean
  still held (ALIASES, HOST_INDIRECT, GUARD_LEARN_LOG, GUARD_SPLIT): 505 → 501. Normal is as in bake 1: 638 → 636.
- The det test runs with `KEEP=BC5_DIRECT_DMA_SNAPSHOT LEAN_GONE=1` and passes 289 of 289.
- Run 2's flips/s cost is not pinned on any one row. Run 1 showed all five G6+G7 off recover it; no single off-arm did.
- Box facts for this boot (249ac5d2): the kernel's job timeout is 10 s. The starter is start0413g.sh `1d7f34c2`. Each
  A/B run logs one RA24 display line, which the top session excluded by name. Absolute flips/s may differ from
  earlier boots.

## README section (goes after "E: the repo's tools")

### Bake 1: the every-title, nothing-learned build in the shared builds (tag bake442)

The order came from the maintainer on 2026-11-22: start by deploying the work that already exists
and is not yet on for every game. This bake comes first. Exp 0439's set (its chain, end-of-pipe, flat-aperture, prefix
and DMA-sync fixes) follows as bake 2, on top of this one.

**What changes for every title:**
- **28 rows move from TITLE2 to `kGeneric0442`, applied to every title after `kSoft` with `setenv(…, 0)`.** Each
  one is turned off per run with `NAME=0`, no build needed.
  - The library words: `KYTY_BC5_SAVEDATA_MEMORY_FIXES`, `_SAVEDATA_DELETE_BUSY`, `_SAVEDATA_ALIASES`, `_HTTP2_FIXES`,
    `_PAD_OPEN_EXT`, `_JSON2_FIXES`, `_ULT_FIXES`, `_USERSERVICE_VALUES`, `_SYSTEMSERVICE_VALUES`,
    `_SYSTEMSERVICE_PARAMS_7_1000`, `_AUDIOOUT_CHECKS`, `_AUDIOIN_CHECKS`, `_NGS2_RACK_FIX`, `_FW_PAD`, `_LOAD_ZLIB`,
    `_LOAD_JPEG`, `_LOAD_IME`, `_LOAD_NPCOMMON`, `_LOAD_NPMANAGER`, `_LOAD_NPTROPHY`.
  - The direct-path words: `BC5_DIRECT_MEC_INDIRECT`, `BC5_DIRECT_REMEMBER_UNMAPPED`, `KYTY_BC5_APR_PARALLEL`,
    `BC5_DIRECT_GPU_CHECK`, `BC5_DIRECT_DMA_SNAPSHOT`, `BC5_DIRECT_CS_PREFIX`, `BC5_DIRECT_INDIRECT_DRAWS=multi`,
    `BC5_DIRECT_LAZY_RELEASE=30,eager`.
  - **Off-words fixed first.** `BC5_DIRECT_INDIRECT_DRAWS=0` now turns the drop off (through `bc5/idraws0442.hpp`).
    `BC5_DIRECT_SHADOW_LABELS=0` now turns the shadow labels off (`env_on`).
- **G0: two rows deleted, nothing replaces them.** `BC5_GUARD_LEARN_LOG` did nothing. `BC5_DIRECT_SKIP_PGM=0` acted
  instead of turning the skip off. `kTitleForced` is emptied.
- **Nothing learned stays (nl442, zl442):**
  - the aliases and their file;
  - `BC5_GUARD_SPLIT`, `BC5_GUARD_LEARN_LOG` and `alias_learn`;
  - `BC5_DIRECT_HOST_INDIRECT` whole;
  - the zero skip's learned-window guard and seam, and the m11 learn refusal;
  - exp 0379's zero list whole: the scan, the canary, the skip and the zp412 poll;
  - in the backend: `map_alias`, `unmap_aliases`, `host_indirect.{cpp,hpp}` and `zero_skip.hpp` with their tests.
- **The gone words.** `kGone0442` lists them: `BC5_DIRECT_ALIASES`, `BC5_GUARD_SPLIT`, `BC5_GUARD_LEARN_LOG`,
  `BC5_DIRECT_HOST_INDIRECT`, `BC5_DIRECT_LEARNED`, `BC5_DIRECT_LEARN_GUEST_ONLY`. A gone word still set in the
  environment gets one stderr line and is unset; it has no off-word because nothing reads it. The zero list's own
  words left the binaries with its code (‹the lost words from the swap log›).
- **Renames, behaviour unchanged (rn442):** `learned_apply` becomes `heap_guards_apply`, `mr412_would_learn` becomes
  `mr412_fault_record`, and `load_stat`'s `kLearned*` become `kHeapGuards*`. The journal texts that change are tabled
  under C.
- **The overlay's warning compares against the first title's run-time id TITLE1B (F863), not the image name.**

**Left for TITLE2 only:**
- `BC5_DIRECT_DMA_SYNC` and `BC5_DIRECT_FLAT_APERTURE` move to every title with exp 0439's bake 2.
- `BC5_DIRECT_AMM_PRT`, `BC5_DIRECT_GPU_CHECK_PRODUCT` and `BC5_DIRECT_SHADOW_LABELS` are G8's open questions. The last
  two now have a `count` mode that keeps guarding.

**Bake 2 on top of bake 1** (checked on the laptop, 2026-11-22, against exp 0439's branch at `04cab114`):
- **`mkbk439.py`** pins the old unit by md5 (`ed489aca`). With that one assertion relaxed it runs on bake 1's unit
  (`3b28b024`), header (`3f9ee1d9`) and the tree's `videoOut.cpp` with no failed anchor.
  - Its output: unit `05df195d`, header `30fab40b`, which still holds `kGeneric0442` and `kGone0442`.
  - So bake 2 has to pin `3b28b024` in place of `ed489aca`.
- **The backend diffs `direct439-on-eacf8d2a.diff`, `be-ds439.diff` and `be-pw439.diff`** apply in that order on main's
  `direct.cpp` (`1b8b55ec`). On bake 1's (`35fca52f`), 2 of `direct439`'s 6 hunks fail, and both only on context
  lines bake 1 removed:
  - the `#include "bc5/host_indirect.hpp"` line, so `ib_chain.hpp`'s include goes between `env_flag.hpp` and
    `ib_split.hpp`;
  - the exp 0346 comment that opened HOST_INDIRECT's block, so the `fl439` block goes right after
    `executed_offsets_of(ib, main_out.data(), r.executed_offsets);`.
  - Neither touches code that bake 1 changed. Bake 2 regenerates its three diffs on `35fca52f`.

**Not in bake 1:** exp 0439's set, and D (`BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG`: dead code, a separate decision).

**Shared builds:**

| | patch | normal | lean | archive |
|---|---|---|---|---|
| before | `589ef163` | `30546370` | `05fd749d` | `a548a249` |
| after | ‹› | ‹› | ‹› | ‹› |

- **Switch words** (`(KYTY_)BC5_*` strings):
  - normal: ‹n› → ‹n›;
  - lean: ‹n› → ‹n›.
  - Both gained only kGone0442's names and lost only the zero list's family, exactly as the private build did.
- **Backend source** (`~/bc5-work/d19/export/backend` and main's `backend/`):
  - `direct.cpp` `1b8b55ec` → `35fca52f`;
  - `indirect_check.cpp` `6c0adc0a` → `4530fe2b`;
  - `shadow_labels.cpp` `2cfbea8b` → `1fd2ec16`;
  - the three headers `18c66de8`/`06bc795e`/`a8bf0059` → `77523d93`/`c7eb9855`/`575f120b`;
  - five files deleted.
- **Kit:** `bake/` (`swap0442.sh`, `undo0442.sh`, `dry0442.sh`, `pins0442.inc`).
- **Undo:** `bash ~/bc5-work/exp0442/bake442kit/undo0442.sh` restores `589ef163` / `30546370` / `05fd749d` / `a548a249`
  by md5.

**Evidence:**
- **Det test `test0442.sh`:** ‹result›. It applies the header the way the emulator does, title by title.
- **R72 display check:** ‹›.
- **The first title lean smoke:** ‹›.
- **Lean A/B against the shared lean `05fd749d`:** the first title, 1920x1080, one discarded warm-up and 5 pairs, MangoHud
  log: ‹median, p95, p99, flips/s per pair›.
- **D25 verdict:** ‹›.
- **Post-bake smoke of the shared lean and normal:** ‹›.
- **The second title is uninstalled.** Its row-by-row equivalence rests on the det test alone (T4: every word as before
  except the deleted rows and the gone words). No run of the second title was made on bake 1.

## HANDOFF row (§2, next free F number on landing)

| F‹n› | **Bake 1 (exp 0442, tag bake442): the shared builds apply TITLE2's 28 generic rows to every title, and nothing learned is left in them (2026-11-22).** The 28 rows (20 library words and 8 direct-path words) moved from `kTitleDefaults` to `kGeneric0442`, each with a working off-word (`NAME=0`; `INDIRECT_DRAWS` and `SHADOW_LABELS` fixed first). Deleted with no replacement: `GUARD_LEARN_LOG`, `SKIP_PGM`, the aliases, `GUARD_SPLIT`, `HOST_INDIRECT` and exp 0379's zero list. Six gone words are reported and unset (`kGone0442`). TITLE2 keeps five rows: `DMA_SYNC` and `FLAT_APERTURE`, which go to every title in bake 2, and `AMM_PRT`, `GPU_CHECK_PRODUCT` and `SHADOW_LABELS` (G8). Patch `589ef163` → ‹›, normal ‹›, lean ‹›, archive ‹›. Lean A/B on the first title at 1920x1080: ‹›. The second title is not installed, so its equivalence rests on the det test only. | `experiments/0442-title-defaults-audit/README.md` (Bake 1), `bake/` | high for the code and the det test; the second title untested on the bake |

## CLAUDE.md, machine context (the shared builds' sentence, newest first)

since 2026-11-22 ‹hh:mm› the shared builds are patch ‹›: exp 0442's bake 1 (F‹n›, D26: TITLE2's 28 generic rows
for every title through `kGeneric0442`, each off with `NAME=0`; nothing learned left: the aliases, GUARD_SPLIT,
GUARD_LEARN_LOG, HOST_INDIRECT and exp 0379's zero list removed, their words reported and unset by `kGone0442`;
TITLE2 keeps DMA_SYNC, FLAT_APERTURE, AMM_PRT, GPU_CHECK_PRODUCT, SHADOW_LABELS), normal ‹›, lean ‹›, archive ‹›
(backend direct.cpp `35fca52f`); lean A/B on the first title ‹›; undo `bash ~/bc5-work/exp0442/bake442kit/undo0442.sh` to
`589ef163`;
