# The next bake's list (after bake 1c + 1d), for review by the top session; no action yet

Sources:
- the n1d header's kTitleDefaults;
- the repo's `tools/scripts/launchers/play-pkg.sh` and `play-t1.sh`, as of branch exp/0442-title-defaults-audit. The box copies of his launchers may differ.

Exp 0439's kit (DMA_SYNC, FLAT_APERTURE, the chain fixes) goes in together with this list.

The proposals sort each word into one of three kinds:
- **universal default** — a default in the patch for every title;
- **needs a second-title run** — it can only be judged on TITLE2, which is not installed now;
- **goes away**.

## TITLE2 rows left in the header (kTitleDefaults)

| Word | Proposal | Why |
|---|---|---|
| BC5_DIRECT_DMA_SYNC=1 (F107) | universal default | Exp 0439's bake 2. A DMA_DATA without CP_SYNC must finish before the dispatches that read it, on any title. |
| BC5_DIRECT_FLAT_APERTURE=1 (F249) | universal default | Exp 0439's bake 2. The generic `=1`/`all` form scans every program by pattern (n1c/bc5LleAgc.cpp:14637-14660); no title data is involved. |
| BC5_DIRECT_AMM_PRT=1 (F260) | needs a second-title run | It guards the PRT (sparse) mappings seen only on that title. It needs a run on that title to show it is harmless to set for all, or the PRT path made correct. |
| BC5_DIRECT_GPU_CHECK_PRODUCT=1 (F414, F415) | needs a second-title run | The RT-on staircase guard for the product of the dispatch dimensions. Its limits come from that title's hang (exp 0342). Source fix first, then universal or gone. |
| BC5_DIRECT_SHADOW_LABELS=1 (F414, F415) | needs a second-title run | Host-owned shadow labels for that title's RT-on syncs. Same as above. |

Once these five are gone, so are kTitleDefaults, kTitleForced (empty), DetectTitle, TitleIdOf, GamePathOf and KYTY_BC5_TITLE_DEFAULTS.

## Words only play-pkg.sh sets (the second title's launcher)

| Word (play-pkg.sh line) | Proposal | Why |
|---|---|---|
| BC5_DIRECT_CP_COHER_START_DELAY=1 (:66) | universal default, after one first-title smoke | "On in every play since 11-03; never A/B'd". It is a coherence-timing fix, not title data. |
| BC5_DIRECT_GC_TF_RING=1 (:111) | universal default, after one first-title smoke | A tessellation-factor ring of our own; any title that tessellates needs it. |
| BC5_DIRECT_GC_HS_OFFCHIP=1 (:112, exp 0399) | universal default | It uses the title's own VGT_HS_OFFCHIP_PARAM: console behaviour. |
| BC5_DIRECT_CROSS_RING_WAITS=all (:152, F412/F415) | needs a second-title run | It is tied to the one-ring decision. Check it against today's way 2 and multi-ring for all titles. |
| BC5_DIRECT_RING_DEPS=dcb (:154, F385) | needs a second-title run | It orders GFX jobs after the compute rings' last jobs (the BVH build split). Check against way 2. |
| BC5_DIRECT_TWO_RING_WAIT_MS=4 (:158) | needs a second-title run | A wait timeout tuned on that title; it should come from the console's own wait behaviour. |
| BC5_DIRECT_CHAIN=2 (:132; also play-t1.sh:57) | universal default | Both launchers set it, so it belongs in the patch. |
| BC5_MOUNT_DISK_CACHE (:96) | universal default (mount option) | A mount cache, the same for any title. |
| MALLOC_ARENA_MAX=2 on the mount (F353) | universal default (mount) | Memory only; not title data. |
| KYTY_BC5_APR_READAHEAD=4 (play-t1.sh:62, the first title only) | universal default | An I/O policy; the other title lacks it only because it was never set there. |
| BC5_DIRECT_LAZY_NAMES / BC5_DIRECT_EAGER_NAMES (:41, :62; bc5-run.env.in:9-10 for the first title) | goes away, needs both titles | Name lists taken from each title's heaps. Replace them with a rule from the heap's GPU-access flags, then check both titles. |
| SHADPS4_SYSMODULES_PACK_DIR (:46, the no-PlayGo/Ampr pack; play-t1.sh:100, the first title's fakelib) | goes away, needs both titles | One rule for all: the title's own image, with PlayGo/Ampr in the host. |
| BC5_DIRECT_SKIP_PGM=0 (:124) and the drop in the unit | goes away | Idle. It is also read in lean. |
| KYTY_BC5_RT_BUILD_PGM (:128) | goes away | Bake 1d made it a gone word. The launcher line stays harmless until his word to tidy the launcher. |
| The 20 library words, MEC_INDIRECT, GPU_CHECK, REMEMBER_UNMAPPED, APR_PARALLEL=8, DMA_SNAPSHOT, CS_PREFIX, INDIRECT_DRAWS=multi, LAZY_RELEASE=30,eager (:67-99, 135, 149) | goes away from the launcher | Bake 1c makes them every title's defaults, so the launcher copies are redundant. |
| --fullscreen (:42) | goes away | Exp 0435's per-title window file holds it. |
| KYTY_BC5_SAVEDATA_DIR=_SaveData-pkg-play (:63) | his word | His saves; it is a user preference. |
| ~/bc5-work/bc5-pkg.env (:172-178) | goes away, or becomes a per-title user file read by the shared script | It is a side channel for one title. |
| play-any.sh SECOND_TITLE split (:50, :118) | goes away last | Once the words above are universal, one title script serves both titles. |

The launcher items are in his scripts and are changed only on his word.

## Added 2026-11-24 evening (the host-toolchain slot, and exp 0439 through the top session)

- **`#include <cstdint>` in KytyPlus's `src/graphics/guest_gpu/gpu_translator.h`.**
  - The host's libstdc++ 16 no longer pulls `<cstdint>` in through other headers.
  - Until the patch carries the include, `bc5-build.sh` forces it with `-include cstdint` (F928).
- **`-Wreturn-type` in `pm4Handlers.cpp`.**
  - The host build shows 16 cases (`non-void function does not return a value in all control paths`), the first at lines 1943 and 1959.
  - Falling off the end of a non-void function is undefined behaviour. Each case needs a return value or an
    unreachable marker, checked against what the caller expects.
- **From exp 0439, confirmed on the chip** (relayed by the top session):
  - BC5's forced `CONTEXT_CONTROL` 0x80000000/0x80000000 disables the CP's register shadowing, so a title's
    `LOAD_CONTEXT_REG`/`LOAD_SH_REG` restores load zeros (the third title's edge blocks).
  - The guest's own value ran 4 clean runs. The row goes to every title once exp 0439 has the guarded patch.
  - Also from exp 0439: BC5 turns a conditional `CLEAR_STATE` pop into a full clear.
- **The universal import of GPU-written views** (F920, Q45; the design note of 2026-11-24): the second title's
  three launcher words and the third title's place on the shared builds wait for it.

