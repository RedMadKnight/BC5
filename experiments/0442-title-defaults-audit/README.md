# 0442 — audit of the per-title defaults table (`kTitleDefaults`)

**Status: audit done (2026-11-22). Code reading only: no box GPU use, no run, no deployment.** The top session decides
the bakes.

## Question

The maintainer, 2026-11-22: fixes must be universal, never workarounds for one game. The shared patch
(main `120153fc`, `backend/kytyplus-patches/0001-bc5-lle-agc.patch`, `src/bc5/switch_defaults.hpp`, patch lines
6155-6210) still forces 38 switches for TITLE2 only (`kTitleDefaults`).

Two of the third title's blockers this week were rows of this table that the third title did not get:
- `BC5_DIRECT_FLAT_APERTURE` (F249 → F893);
- `BC5_DIRECT_DMA_SYNC` (F107 → F894).

For each row:
- What does it do, and where is the code?
- What class is it?
- What evidence is there for every-title use, and what is the risk for the first title?
- In what order can the rows move to every title?

## Setup

Read-only. The sources:
- the patch on main `120153fc`;
- `backend/src/direct.cpp`;
- `docs/HANDOFF.md`;
- the experiment READMEs;
- branch `exp/0439-third-title` at `ca9bda02` (worktree `wt0439`), for exp 0439's kit.

Three read-only agents gathered the per-row facts, and this session checked the surprising claims in the code itself
(marked ✔ below). Their full notes, with every citation, are kept here:
- `notes-direct.md` (the 18 direct-path rows);
- `notes-library.md` (the 20 library rows and the exp 0413 history);
- `notes-keyed.md` (other title-keyed code, exp 0439's kit, the current kFixes/kDefaults/kSoft rows).

"P:n" is line n of the patch on main `120153fc`.

Title ids:
- TITLE2 is the second title;
- The first title is image TITLE1, with run-time TITLE_ID TITLE1B (F863);
- TITLE3 is the third title.

## Result

### Findings that change the brief's premises

1. **The table's own comment is stale (✔).** P:6145-6147 says "four or more of the twenty library words together end
   the first title at 5-6 s (exp 0413)". That reading was refuted in exp 0413 itself:
   - 20 dummy variables alone made the crash pass (e4dum), and with the five rows out it crashed again (h1t1);
   - the cause was F816: `CommandBufferSetBuffer` read its map flavour from leftover registers;
   - the fix has been on in the code since 2026-11-12 and has had no option since exp 0419.
   So no recorded failure of any library word on the first title remains. The same comment also says
   `KYTY_BC5_SWITCH_DEFAULTS=0` skips the table. That word is in `kIgnored` (P:6134) and is removed before `Apply` reads
   anything, so only `KYTY_BC5_TITLE_DEFAULTS=0` skips the table (✔, P:6307-6322).
2. **Two rows cannot be turned off with `NAME=0` (✔).** `kTitleForced` (P:6255) removes `BC5_DIRECT_LAZY_RELEASE` and
   `BC5_GUARD_SPLIT` from the environment for every process (P:6310-6312), and the TITLE2 row sets them with
   overwrite (P:6271). So the second title always has them, and every other title can never have them, not even from
   the environment.
3. **"=0" does not mean off for three rows (✔):**
   - `BC5_DIRECT_SHADOW_LABELS` is read as presence only (`direct.cpp:588`), so `=0` turns it on (a bug; F767 fixed
     seven other words, not this one);
   - `BC5_DIRECT_INDIRECT_DRAWS=0` lets DRAW_INDIRECT through and turns on the given-up-wait draw drop
     (P:53924, P:54086);
   - the row's own `BC5_DIRECT_SKIP_PGM=0` parses to the set {0} (P:53981-53993). It drops every dispatch whose tracked
     program is 0. That is not the no-op the launcher comment claims (`play-pkg.sh:127`).
4. **One row is inert (✔).** `BC5_GUARD_LEARN_LOG` is read only inside `alias_learn()`, which is marked "not called"
   (P:43489-43512).
5. **The library words are not firmware loads.** `KYTY_BC5_LOAD_*` register host C++ HLE tables (P:86318-86324),
   ported from AnyPS5/KytyPS5. A title that does not import the library is unaffected. The other 19 tables of that
   batch have been on for every title since exp 0419 candidate G, on the maintainer's word built in, but run only
   when a game calls them. These six were held back only because of the stale 0413 claim.
6. **`play-pkg.sh` still sets 37 of the 38 rows itself** (`notes-keyed.md` C8). The table is a second copy; moving a
   row does not change the second title until the launcher line goes too. The launcher is the maintainer's: it is not
   edited here.

### The table

Classes:
- **(a)** restores console or hardware behaviour, generic: goes to every title;
- **(b)** a system-library port or fix: generic by the port rule, goes to every title;
- **(c)** a diagnosis or guard: should not be a default at all;
- **(d)** carries a value learned from one title;
- **(e)** truly title data.

"Evidence" is a recorded run of the first title (A) or the third title (T) with the word on. Every patch line is P:n unless
a file is named.

#### Direct path (18)

| # | Switch (row value) | What it does (on) | Finding, code | Class | Evidence A/T | Risk if on for the first title (from the code) |
|---|---|---|---|---|---|---|
| 1 | `BC5_DIRECT_LAZY_RELEASE` `30,eager` | cuts direct-memory chunks unused for 30 s out of their BOs and rebuilds the mappings, on the sync path, only when every ring is idle | F843 (exp 0401 e7, exp 0412); read P:41313, pass P:41341 | (a) generic host memory policy (no title data); forced by `kTitleForced` | none (A cannot get it: unset at start) | **memory mapping** on every title's sync path |
| 2 | `BC5_GUARD_SPLIT` `1` | lets the lazy release split BOs that carry aliases, and re-maps the aliases right after a cut | exp 0412 g412c; P:44350, P:41410 | (c) a helper of #1 that matters only with #15 on; forced | none | none alone (only with #1 and #15) |
| 3 | `BC5_GUARD_LEARN_LOG` `2` | **nothing**: read only in the uncalled `alias_learn` | F819/F820 (learned windows); P:40132, P:43489 | (c)/(d) a learned-windows remnant, inert | n/a | none |
| 4 | `BC5_DIRECT_MEC_INDIRECT` `1` | a compute-form DISPATCH_INDIRECT of an acb on the GFX ring is rebuilt to the GFX form and run instead of dropped | F91 (exp 0039); P:53965, P:54189, P:54238; `direct.cpp:1365-1379` | (a) runs a console packet class that is dropped today | none | submission, only for acbs that fall back to the GFX ring (way 2 puts acbs on compute rings, which have their own `ACB_MEC_INDIRECT` in kSoft) |
| 5 | `BC5_DIRECT_GPU_CHECK` `1` | the CP checks each indirect dispatch's group counts when it runs it (COND_WRITE/COND_EXEC) instead of the host's stale submit-time check | F106 (exp 0052); P:54000; `direct.cpp:1435-1445` | (a) replaces a host check that drops valid dispatches; its draw limits were sized on one title | none | **submission**: extra packets before every indirect dispatch, on every ring kind |
| 6 | `BC5_DIRECT_DMA_SYNC` `1` | a CP DMA wait before the first dispatch after an unsynced DMA_DATA, **GFX ring only** | F107 (exp 0050/0053); P:53881; `direct.cpp:1401` | (a) restores the console's ordering (F894: the third title's stall is the same race, and the shared filter strips the title's own CP_SYNC) | T: only in exp 0439's pending "fixes" run (env, `t3one.sh:19-22`), no result yet | submission and timing (an added wait). The ring-generic form is exp 0439's candidate D/D2/F |
| 7 | `BC5_DIRECT_REMEMBER_UNMAPPED` `1` | an IB that only touches pages a forced sync left unmapped <2 s ago skips a second full sync walk | F163 (exp 0103); P:53681 | (a) host speed fix | none (the code comment and exp 0103 disagree on whether A pays this cost) | timing of the mapping sync only |
| 8 | `KYTY_BC5_APR_PARALLEL` `8` | consecutive APR ReadFile commands run on 8 threads | F166 (exp 0112); `libAmpr.cpp` P:59928 | (a) host speed fix | **A: yes**, exp 0227 AU2/AU3 (27.0/26.9 s vs 25.3 s, no gain, no failure; F286) | load I/O timing and completion order (exp 0117: the first title's GPU work is sensitive to its load rhythm) |
| 9 | `BC5_DIRECT_DMA_SNAPSHOT` `4096` | each graphics-buffer DMA_DATA source of ≥4096 bytes is copied at submit into a shared ring, and the IB reads the copy | F172 (exp 0122); P:53903; `direct.cpp:1269` | (a) emulates the console's short submit-to-run gap for CPU staging | none | **submission and semantics**: wrong if a title writes the source after submit on purpose |
| 10 | `BC5_DIRECT_FLAT_APERTURE` `1` | rewrites the console's flat-aperture constants in a program's code before its first dispatch, by pattern | F249 (exp 0190); P:53541, P:54120 | (a) the console ABI | T: on in two runs that stopped at the earlier stall before any rewrite (0439 README:836); A: O arm prepared (`ab439bk.sh`), no result found | writes guest code memory where the pattern matches; one scan per program otherwise. **exp 0439's kit already moves it** |
| 11 | `BC5_DIRECT_AMM_PRT` `1` | a PRT mapping over the fixed 64 GiB AMM window `0x8000000000`, so writes to unbacked sparse pages are dropped instead of faulting | F257/F260 (exp 0199/0202, n=1); P:40166 | (c) fault suppression with an address constant, **unless the PS5 itself maps the AMM window as PRT** (TODO(verify), the maintainer's "does the PS5 do this?") | none | **memory mapping** of a 64 GiB range for the whole process |
| 12 | `BC5_DIRECT_SKIP_PGM` `0` | drops dispatches whose tracked program is 0 (the set {0}) | exp 0059 hook; P:54142 | (c) a test hook; the row is not a no-op | none | submission (drops), if program-0 dispatches occur (not established) |
| 13 | `BC5_DIRECT_CS_PREFIX` `1` | replays the GFX queue's tracked compute SH registers in front of a dcb that dispatches before setting its program | F321 (exps 0195/0254/0259); P:46597, P:48393 | (a) restores per-queue compute state on a shared ring (F251) | none (F315: the first title was clean without it) | **submission**: added packets in matching GFX buffers |
| 14 | `BC5_DIRECT_INDIRECT_DRAWS` `multi` | lets DRAW_INDIRECT 0x24 and the multi-draws 0x2c/0x38 through (the **unset default drops them for every title**); when set at all, also drops indirect draws after a given-up wait | F108/F112 (exps 0054/0057); P:53922, P:54080-54092 | (a) runs console packets; the default is the guard. The after-a-given-up-wait drop is (c) | A uses 0x25 only (exp 0054), which the default does not drop | submission: with the word set, the first title's 0x25 draws after a given-up wait would be dropped |
| 15 | `BC5_DIRECT_ALIASES` `1` | maps the learned file `~/bc5-work/direct-aliases-pkg.txt` a second time at `(byte<<40)+lo` | F110 (exp 0056); P:43458 | **(d)** a learned file: one real line (the second title's code heap under tag 0x80) and four dead lines (exp 0412 README:2838-2848) | none | memory mapping. It must not go to every title as is |
| 16 | `BC5_DIRECT_GPU_CHECK_PRODUCT` `1` | refuses GFX-ring dispatches with y or z > 1 and x > 2^16 (only with #5 on) | F414/F415 (exp 0341); `direct.cpp:593`, `:1441` | (c) a guard against F403's runaway grids, not a cause fix | none | submission, with #5 only |
| 17 | `BC5_DIRECT_SHADOW_LABELS` `1` | a self-synced label's wait reads a host slot in the job scratch instead of the title's label | F414/F415, F360 (exp 0341); `direct.cpp:588`, `:1353-1365` | (c) a guard against a stray store; **presence-only read (bug)** | none | **submission and wait semantics** in every GFX IB with self-synced labels |
| 18 | `BC5_DIRECT_HOST_INDIRECT` `learn:1100000000` | GFX-form dispatches whose base is 0 after the title zeroes it are resolved by the host against a window (learned from SET_BASEs, or `0x1100000000` until one is learned); else NOP-ed | F432/F433 (exps 0346/0350); `direct.cpp:600-606`, `:1288-1338` | **(d)** `0x1100000000` is the second title's `AssetHeap Large` (F820). The mechanism is generic. F432 records 0 rewrites | none | submission: can NOP or rewrite indirect dispatches |

#### System libraries (20)

None is in kFixes, kDefaults or kSoft under another name. Each acts only inside its library unless noted. All carry no
title data. The only the first title runs with them on are exp 0413 e1env/e3env (90-s starts, PASS, on a binary from before the
F816 guard). There is no third-title run with any of them on.

| # | Switch | What it does (on) | Origin | Class | Risk if on for the first title |
|---|---|---|---|---|---|
| 19 | `KYTY_BC5_SAVEDATA_MEMORY_FIXES` | SyncSaveDataMemory posts MEMORY_SYNC_END; event queue under a lock; `existed` = memory.dat's real size | exp 0405 R2 KS03/SS01/KS02/KS09/SS02 | (b) | low-medium: **the first title uses save-data memory**. The `existed` part ran on the first title in exp 0417 sm1 with no change |
| 20 | `KYTY_BC5_SAVEDATA_DELETE_BUSY` | Delete of a mounted save returns BUSY | R2 KS14/SS10 | (b) | low |
| 21 | `KYTY_BC5_SAVEDATA_ALIASES` | registers two missing Initialize NIDs | R1 #15 | (b) | very low (importers only) |
| 22 | `KYTY_BC5_HTTP2_FIXES` | Http2 async completion events, SSL context ids, a "" user agent for NULL | exp 0405 row 21, R2 KS01/KS04, R1 #18 | (b) | low (the first title imports Http; no network on the box) |
| 23 | `KYTY_BC5_PAD_OPEN_EXT` | registers scePadOpenExt | exp 0405 row 22 | (b) | very low (the first title opens with scePadOpen) |
| 24 | `KYTY_BC5_JSON2_FIXES` | assignment copies the source first (use-after-free) | R1 #1, R2 KS05 | (b) | low |
| 25 | `KYTY_BC5_ULT_FIXES` | the join race fixed; the queue grows instead of dropping | R1 #2, R2 SK07 | (b) | low-medium (growth is not console-verified) |
| 26 | `KYTY_BC5_USERSERVICE_VALUES` | error codes for bad arguments; login checks; AgeLevel 0xFFFFFFFF | R1 #3, R2 KL03 (console measurement, 13.60) | (a)/(b) | low; on every title's path |
| 27 | `KYTY_BC5_SYSTEMSERVICE_VALUES` | ParamGetInt refuses unknown ids; one 13.40 console's settings values; ParamGetString answers only id 6 | R1 #4 (a 13.40 sweep) | (a)/(b), with console (not title) data | **medium**: every title calls it; a title relying on 0 for an unknown id now gets an error |
| 28 | `KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000` | params 7 (parental level) and 1000 (enter button) return 0x80A10003 instead of 0 and 1 | the same 13.40 sweep | (a)/(b) | **the highest of the twenty**: a title that reads the enter button and does not handle an error. Not found whether the first title reads 7 or 1000 |
| 29 | `KYTY_BC5_AUDIOOUT_CHECKS` | error codes instead of an EXIT or a crash on invalid arguments | exp 0405 rows 16-17 | (b) | very low (valid calls are unchanged) |
| 30 | `KYTY_BC5_AUDIOIN_CHECKS` | silence written and argument errors in AudioIn | R2 KA06/KA07 | (b) | low |
| 31 | `KYTY_BC5_NGS2_RACK_FIX` | the rack destroy unlinks and frees; **every Ngs2SystemRender walks the racks under a new mutex** | exp 0405 row 18, KA03/KA08 | (b) | low-medium: on the audio render path of every Ngs2 title (whether the first title uses Ngs2: not found) |
| 32 | `KYTY_BC5_FW_PAD` | **scePadInit is swapped for every pad title** (it adds an init flag); 18 more pad NIDs with argument checks | exp 0405 (AnyPS5 rows, rewritten) | (b) | low-medium: a pad call before scePadInit now returns NOT_INITIALIZED |
| 33 | `KYTY_BC5_LOAD_ZLIB` | registers the ported libSceZlib table | exp 0405 decision 4, 0401 e6 | (b) | low (importers only) |
| 34 | `KYTY_BC5_LOAD_JPEG` | libSceJpegEnc (argument checks; the encode itself is held) | same | (b) | low |
| 35 | `KYTY_BC5_LOAD_IME` | the dead Ime v1 table, without the 7 NIDs of the live table | same | (b) | low |
| 36 | `KYTY_BC5_LOAD_NPCOMMON` | 28 NpCommon NIDs | same | (b) | low-medium (ported thread/callout behaviour) |
| 37 | `KYTY_BC5_LOAD_NPMANAGER` | 20 NpManager NIDs; the live table keeps its keys | same | (b) | low-medium |
| 38 | `KYTY_BC5_LOAD_NPTROPHY` | 23 NpTrophy NIDs (context, register, unlock...) | same | (b) | **medium**: trophy registration runs early at start |

#### Class totals

| Class | Rows |
|---|---|
| (a) generic, to every title | 1, 4, 5, 6, 7, 8, 9, 10, 13, 14 (draws allowed), 26, 27, 28 |
| (b) library port or fix, to every title | 19-38 (26-28 also (a): console-measured values) |
| (c) guard or diagnosis, not a default | 2, 3, 11 (pending the PS5 question), 12, 16, 17, the after-a-given-up-wait part of 14 |
| (d) learned value | 15 (`ALIASES` file), 18 (`HOST_INDIRECT` constant); 3 was the learned-windows log |
| (e) title data | **none** |

What replaces the (d) rows and the guards:
- **#15 ALIASES:** a generic rule built in the code, "every code heap is mapped a second time under the 0x80 tag",
  which is exp 0412's own proposal (README:2838-2848; not built). That is only right if the PS5 maps code under that
  tag too: TODO(verify) (F110). Until it is built, the row stays for the second title. Moving the file as it is would
  give every title the second title's addresses.
- **#18 HOST_INDIRECT:** `learn` alone (the window learned from the title's own SET_BASEs), with no fixed
  `0x1100000000`. Since F432 recorded 0 rewrites, the alternative is to delete the mechanism after a second-title run
  shows it still does nothing.
- **#11 AMM_PRT:** answer "does the PS5 map the AMM window as PRT?" first. If yes, it is (a) and goes to every title.
  If no, it is a guard: remove it once F257's cause is fixed.
- **#16, #17 (guards against F403/F360):** keep them for the second title only until their causes are removed, then
  delete them. They are not every-title defaults. #17's presence-only read should be fixed to `env_on` in any case.
- **#2, #3, #12:** delete the rows. #2 goes when #15 goes (without ALIASES, splitting is always allowed).

### Other behaviour keyed on a title id (outside the table)

From `notes-keyed.md`.

**In the emulator (patch):**
- `kTitleForced` (P:6255): see finding 2.
- `settingsOverlay.cpp` P:9588-9597 compares against `"TITLE1"`, the image name, to show the "measured on the first title"
  warning. The run-time id is TITLE1B (F863), so the warning probably shows on the first title too (not checked on the
  box). It should compare against TITLE1B, or the warning should go.
- The heap name "FileSystem" is always eager for every title (P:40464-40474, P:40541-40545). This is keyed on a heap
  name, not a title.
- Everything else keyed on an id is DATA:
  - the per-title input.cfg keys (`RenderScale`, `RayTracing`, `MangoHud`; `JobArenaFix` is read and ignored);
  - the `titles/<ID>/` store;
  - the games list;
  - the window caption;
  - the save paths.

**backend/:** no code keyed on a title id; only comments.

**Launchers (the maintainer's files, not edited):**
- `play-any.sh:50,118-124` routes TITLE2 to `play-pkg.sh` and every other title to `play-t1.sh`. This is the
  biggest per-title switch in the system: it decides the whole word set.
- `play-pkg.sh` sets, for the second title only, behaviour words that are not in the table:
  - `BC5_DIRECT_CP_COHER_START_DELAY=1` (its comment says "never A/B'd");
  - `BC5_DIRECT_GC_TF_RING=1`, `BC5_DIRECT_GC_HS_OFFCHIP=1`;
  - `BC5_DIRECT_CROSS_RING_WAITS=all`, `BC5_DIRECT_RING_DEPS=dcb`, `BC5_DIRECT_TWO_RING_WAIT_MS=4`;
  - the module pack without PlayGo;
  - `BC5_DIRECT_FLIP_DEFER` unset.
  These need the same audit next. Whether the patch still reads each word is not checked here.
- The shared `bc5-run.env.in` gives every other title the first title's heap lists and module-pack path, and
  `BC5_DIRECT_FLIP_DEFER=1`.
- `play-t1.sh:62` sets `KYTY_BC5_APR_READAHEAD`, which is dead (`kIgnored`).

### Proposed order of moves

Each group is one bake:
- each moved row goes to `kSoft` (`setenv(name, value, 0)`), so `NAME=0` still turns it off and a group can be undone
  for one run with no build;
- the TITLE2 row is removed in the same edit;
- each group is checked with the first title's lean A/B at 1920×1080 (performance from lean only) and a third-title run.

The groups run simplest and safest first:

| Group | Rows | Why here | What to watch |
|---|---|---|---|
| **G0 cleanup (no every-title behaviour)** | delete #3 `GUARD_LEARN_LOG` and #12 `SKIP_PGM=0`; fix #17's presence read to `env_on`; fix the table comment (finding 1); fix the `"TITLE1"` compare | inert or wrong rows | #12: first count program-0 dispatches on the second title (normal build, journal), since removing the row stops dropping them |
| **G1 libraries, lowest risk** | #20, #21, #22, #23, #24, #29, #30, #33, #34, #35 | importers only, error paths, or ports of missing NIDs | First-title start, menu, save; the third title's start |
| **G2 libraries, medium** | #19, #25, #26, #31, #32, #36, #37 | on paths first-title probably uses (save memory, pad init, UserService, Ngs2 render mutex) | The first title's save/load (exp 0422's save fix path), audio replug (Ngs2 and pad code change: the audio replug check applies), pad input |
| **G3 libraries, highest** | #27, #28, #38 | values every title reads at start (system params, trophies) | a normal-build call log of the first title and the third title for ParamGetInt 7/1000 and trophy registration before baking |
| **G4 host speed, timing only** | #8 `APR_PARALLEL`, #7 `REMEMBER_UNMAPPED`, #4 `MEC_INDIRECT` | no mapping or semantic change; #8 has the first title runs | First-title load times (exp 0117's rhythm hazard), lean flips |
| **G5 = exp 0439's bake** | #10 `FLAT_APERTURE` (with exp 0439's IB_CHAIN, IB_CHAIN_FLAT, AGC_EOP_IDENT), and #6 `DMA_SYNC` in its ring-generic form from exp 0439's candidates D/D2/F | already being done there: **reference `exp/0439-third-title` `k439/mkbk439.py:405-437`, not duplicated here** | exp 0439's own runs (Q40, Q41) |
| **G6 submission changes** | #5 `GPU_CHECK`, #13 `CS_PREFIX`, #14 `INDIRECT_DRAWS=multi` (without its after-a-given-up-wait drop, which should get its own word or go), #9 `DMA_SNAPSHOT` | they change what reaches the GPU on every ring | First-title lean A/B (cost), a third-title run past the stall; one kernel line stops the group (R55/R60) |
| **G7 memory** | #1 `LAZY_RELEASE` (and `kTitleForced` emptied so `NAME=0` works) | mapping changes on every title's sync path | First-title long play (memory), the third title's memory (exps 0440/0441) |
| **G8 replace, do not move** | #15 `ALIASES` → the code-heap tag rule; #2 goes with it; #18 `HOST_INDIRECT` → `learn` without the constant, or delete; #11 `AMM_PRT` → the PS5 question first; #16/#17 stay second-title guards until their causes go | (d) and (c) rows | each is its own small experiment with a second-title run |

Not in any group, because they are outside this table: the `play-pkg.sh` launcher-only behaviour words and the
`play-any.sh` routing. They are the next audit, and launcher changes need the maintainer's word.

## Verdict

- No row is title data (class (e) is empty).
- **30 of the 38 rows are generic** and can go to every title in groups G1-G7: 20 library ports or fixes and 10
  direct-path fixes or host mechanisms (#1, #4-#10, #13, #14).
- **3 rows are deleted** (#2 with #15, #3, #12).
- **2 rows carry learned values** (`ALIASES`, `HOST_INDIRECT`) and need a generic replacement.
- **3 rows are guards** (`AMM_PRT` pending the PS5 question, `GPU_CHECK_PRODUCT`, `SHADOW_LABELS`). They should stay
  out of every title's defaults and go when their causes are fixed.
- The old reason for keeping the library words per title (exp 0413) was a host bug, fixed since 2026-11-12.

Limits:
- Code reading only.
- The risk notes are from the code, not runs. Apart from exp 0413's two pre-guard starts and exp 0227's APR runs, no
  the first title or third-title run with any row on is on record.
- Whether the first title imports Ngs2, NpTrophy, Json2, Ult, or reads system params 7/1000, was not established. A normal-build
  call log would settle it.

## Step 2: one private test build with the generic rows on every title (top session, 2026-11-22, after D26)

Kit: `kit/`. Code, build and det tests only: no GPU run, no deployment, nothing shared written.

### The change (`kit/mk0442.py`, on patch `589ef163`'s files)

**`switch_defaults.hpp`** (`48ae1cd6` → `3e951438`):
- **G0:** the inert row `BC5_GUARD_LEARN_LOG` and the hook row `BC5_DIRECT_SKIP_PGM=0` are deleted. The table's stale
  comment is corrected: the 5-6 s end was F816, and `KYTY_BC5_SWITCH_DEFAULTS` skips nothing.
- **G1-G3, G4, G6, G7:** the 28 rows (the 20 library words; `MEC_INDIRECT`, `REMEMBER_UNMAPPED`, `APR_PARALLEL`;
  `GPU_CHECK`, `DMA_SNAPSHOT`, `CS_PREFIX`, `INDIRECT_DRAWS=multi`; `LAZY_RELEASE=30,eager`) are deleted from
  TITLE2's rows. They go, with the same values, into a **new table `kGeneric0442`**, applied for every title right
  after `kSoft` with `setenv(name, value, 0)`. So `NAME=0` in the environment turns each one off.
- `kTitleForced` is emptied. `LAZY_RELEASE` now has an off-word, and the first title can be given it or not.
  `BC5_GUARD_SPLIT` stays a TITLE2 row (G8, with ALIASES) as a plain row.
- **Left for TITLE2:**
  - `DMA_SYNC` and `FLAT_APERTURE` (G5, exp 0439);
  - `GUARD_SPLIT`, `AMM_PRT`, `ALIASES`, `GPU_CHECK_PRODUCT`, `SHADOW_LABELS`, `HOST_INDIRECT` (G8).

**The off-words that did not work, fixed first:**
- `bc5LleAgc.cpp` (`ed489aca` → `53106d30`): `BC5_DIRECT_INDIRECT_DRAWS` is read through the new
  `bc5/idraws0442.hpp` (`4254c562`). Unset, empty and `0` are off. Before, `0` let DRAW_INDIRECT through and turned on
  the drop after a given-up wait.
- backend `direct.cpp` (`1b8b55ec` → `63656591`): `BC5_DIRECT_SHADOW_LABELS` is read with `env_on` (G0). Before, it
  was presence only.
- Every other moved word already reads `0` as off. The readers checked:
  - `env_on`: `MEC_INDIRECT`, `REMEMBER_UNMAPPED`, `GPU_CHECK`;
  - an explicit `"0"` test: `CS_PREFIX`, `LAZY_RELEASE` (`Lzr0401::parse`), and the 20 library parsers and readers
    (P:78673, 78719, 78729, 69387, 75798, 67310, 81471, 84394, 81034, 81076, 36177 `Bc5AoParse`, 75867, 66278, 85938,
    67083, 70093, 70757, 71579, and libs.cpp's table loop P:86357);
  - numeric 0: `APR_PARALLEL` (<2 off), `DMA_SNAPSHOT`.

**`settingsOverlay.cpp`** (`0acb8d6b` → `b7757f72`): the "measured on the first title" warning compares against the first
title's run-time TITLE_ID TITLE1B (F863), not the image name TITLE1.

### Exp 0439's bake and this one, in either order

- Exp 0439's `mkbk439.py` appends to `kSoft`'s end and inserts `BC5_T3` rows after the `kTitleDefaults` header. This
  kit touches neither place: its rows are a table of their own, and it deletes the TITLE2 rows one by one by their
  exact text.
- Shown with exp 0439's own generator (`ca9bda02`'s `k439/mkbk439.py`):
  - 0442 first, then `mkbk439.py` on `mk0442.py`'s header;
  - 0439 first, then `MK0442_ON_0439=1 mk0442.py` on `mkbk439.py`'s header (the switch admits only a header marked
    `#define BC5_T3`; without it the kit refuses that header).
  Both orders give the same header byte for byte (`753715b7`).

### Det tests (`kit/test0442.cpp`, `kit/test0442.sh`; run on the box CPU, in the distrobox, 2026-11-22)

`test0442.cpp` runs `Apply()` the way the emulator does at start, with a fake game folder per title id, and prints the
38 words. It is built against the shared header and against the new one.

Result: **263 passed, 0 failed.** A mutant header with one moved row dropped (`FW_PAD`) fails 33, so the test sees
a lost row.

- **T1 (units):**
  - `indirect_draws_mode`: unset, empty and `0` are off; `1` is DRAW_INDIRECT only; `multi` is all;
  - `env_on`: unset, empty and `0` are off; `1` is on.
- **T2 (every title):** for the first title (TITLE1B), the third title (TITLE3) and no title at all:
  - each of the 28 moved words has its value with the new header and is unset with the old one;
  - the 8 left rows and the 2 deleted rows are unset.
- **T3 (off-words):** for the first title, `NAME=0` keeps each moved word at `0` and leaves the other 27 at their values.
  Turning the G6+G7 group off with its five off-words leaves the other 23 on.
- **T4 (the second title, word by word over the 38):**
  - with a clean environment, old against new, only `BC5_GUARD_LEARN_LOG=2` and `BC5_DIRECT_SKIP_PGM=0` → unset
    differ (the two G0 deletions);
  - with `play-pkg.sh`'s own words for the 38 (its values equal the table's), old and new are identical;
  - `BC5_DIRECT_LAZY_RELEASE=0` gives `30,eager` with the old header (forced) and `0` with the new one;
  - on the first title, `LAZY_RELEASE=7` is removed by the old header and kept by the new one.
- **T5:** with `KYTY_BC5_TITLE_DEFAULTS=0` on the second title, the 28 moved words stay (every title's now) and the 8
  left rows go.

### G8: what would replace each row (proposals, no code)

| Row | Proposal | Open question |
|---|---|---|
| `BC5_DIRECT_ALIASES` (with `GUARD_SPLIT`) | **Removed (tag nl442, the maintainer's order of 2026-11-13: nothing learned stays).** The file, its read, its mapping and `GUARD_SPLIT` go. No built-in rule in this step. | A general rule comes only with a sourced answer to F110's question, as its own change. |
| `BC5_DIRECT_HOST_INDIRECT` | **Removed whole (tag nl442).** Without learning and the constant, nothing useful is left (a window of 0 NOPs every candidate). | A dispatch it covered runs as the title wrote it; a fault there is F416's class: a bug with a record, fixed at its cause. |
| `BC5_DIRECT_AMM_PRT` | If the PS5 maps its AMM window as sparse (PRT, writes to unbacked pages dropped), it is console behaviour and goes to every title, with the window taken from the title's own AMM calls rather than the constant `0x8000000000`. If not, **delete** it after F257's cause is fixed. | "Does the PS5 do this?" (the maintainer's rule). |
| `BC5_DIRECT_GPU_CHECK_PRODUCT` | A guard against F403's runaway grids: **delete** when F403's cause is removed. Until then it stays a second-title row. | F403's cause (the BVH data hunt of exps 0430/0438). |
| `BC5_DIRECT_SHADOW_LABELS` | A guard against a stray store over a label (F360): **delete** when that store's cause is found. Its presence-only read is fixed in this build, so `=0` works now. | F360's cause. |

### The maintainer's launchers: what becomes redundant (nothing changed there)

All of `~/bc5-work/play-pkg.sh` `47426d8e`, the second title's launcher:

| Line(s) | Sets | After the move |
|---|---|---|
| 55 | `BC5_DIRECT_LAZY_RELEASE=${...:-30,eager}` | redundant (every title's default, same value) |
| 57-66 (the `for w in ...` loop) | the twenty library words `=1` | redundant |
| 75 | `BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1` (and `BC5_DIRECT_DMA_SYNC=1`) | the first two redundant; `DMA_SYNC` stays until exp 0439's G5 |
| 82 | `BC5_DIRECT_REMEMBER_UNMAPPED=1` | redundant |
| 85 | `KYTY_BC5_APR_PARALLEL=8` (and `BC5_MOUNT_DISK_CACHE`) | `APR_PARALLEL` redundant; the cache path stays |
| 88 | `BC5_DIRECT_DMA_SNAPSHOT=4096` | redundant |
| 124 | `BC5_DIRECT_CS_PREFIX=${...:-1}` | redundant |
| 138 | `BC5_DIRECT_INDIRECT_DRAWS=multi` (and `BC5_DIRECT_ALIASES=1`) | `INDIRECT_DRAWS` redundant; `ALIASES` stays (G8) |
| 50 | `BC5_GUARD_LEARN_LOG=${...:-2}` | dead already (read only in uncalled code); the row is deleted here too |
| 113 | `BC5_DIRECT_SKIP_PGM=${...:-0}` | **not** harmless: `0` drops dispatches whose program is 0. Proposed: remove the line |
| 56 | `BC5_GUARD_FORGET=${...:-10}` | dead (`kIgnored`) |
| 143 | `BC5_DIRECT_SOFT_WAIT_MS=8` | dead (`kIgnored`) |

The six launcher-only behaviour words are **all dead today**:

| Line | Word | What it did | Now |
|---|---|---|---|
| 54 | `BC5_DIRECT_CP_COHER_START_DELAY=1` | wrote CP_COHER_START_DELAY at start | replaced by exp 0418's start-state table, for every title (row `CP_COHER_START_DELAY` = 0x20, constant). `backend/include/bc5/start_state.hpp:16-17`: "gone and read by nothing" |
| 100 | `BC5_DIRECT_GC_TF_RING=1` | programmed the tessellation-factor ring (F207/F208) | the same table's `VGT_TF_RING` request row, every title; the word is read by nothing |
| 101 | `BC5_DIRECT_GC_HS_OFFCHIP=1` | the title's own VGT_HS_OFFCHIP_PARAM (exp 0399, the water) | the same table's `VGT_HS_OFFCHIP_PARAM` row, every title; the word is read by nothing |
| 141 | `BC5_DIRECT_CROSS_RING_WAITS=all` | one ring: compute buffers on the GFX ring (exp 0342) | no reader in the patch or the backend (way 2 and exp 0430's cross-queue fences replaced it) |
| 144 | `BC5_DIRECT_RING_DEPS=dcb` | GFX jobs after the compute rings' last jobs (exp 0323, F385) | no reader |
| 148 | `BC5_DIRECT_TWO_RING_WAIT_MS=4` | the two-ring wait's limit | no reader |

Other per-title differences there:
- **Behaviour:** line 79 unsets `BC5_DIRECT_FLIP_DEFER`, which the shared `bc5-run.env` sets to 1 for every title.
  So the second title is the only one that runs without flip deferral (exp 0171). This is a per-title behaviour; it
  needs its own check.
- **Title data:**
  - line 46: the system-module pack without PlayGo (exp 0298), a path; the host's PlayGo answer is in the patch for
    every title;
  - line 117: the `KYTY_BC5_RT_BUILD_PGM` list (13 program addresses, the RT menu switch's list);
  - the heap-name lists;
  - line 49: the empty learned-windows file.
- **Routing:** `play-any.sh` `fc7a1395` lines 50 and 118-124 send TITLE2 to `play-pkg.sh` and every other title to
  `play-t1.sh`.

### The private build (`kit/box0442.sh`, 2026-11-22 09:0x, box CPU, no lock line, `raw/box0442.out`)

The method is exp 0438's (`build0438.py` `3fe0aaca`): the shared build's own compile commands for private copies of the
changed units, and the shared link with those objects swapped in.

- **Units:** `src/main.cpp` (the only includer of `switch_defaults.hpp`), `src/libs/bc5LleAgc.cpp`,
  `src/graphics/presentation/settingsOverlay.cpp`, and the backend's `src/direct.cpp`.
- **Reference check:** the shared `direct.cpp` (`1b8b55ec`) compiled here gives the shared archive's member byte for
  byte (`58de1da8`).
- **Results:**

  | | md5 | errors | warnings | words against the shared build |
  |---|---|---|---|---|
  | private archive | **`4778e6bd`** | 0 | 0 | |
  | private normal | **`3079cdf9`** | 0 | 8, all on old lines | 638 → 637: +[] −[`BC5_GUARD_LEARN_LOG`] |
  | private lean | **`fa07ceb9`** | 0 | 10, all on old lines | 505 → 504: +[] −[`BC5_GUARD_LEARN_LOG`] |

  No warning is on an edited line.
- **The lost word:** the first try (`raw/box0442-try1.out`) stopped on the check "no word lost". The binary lost
  `BC5_GUARD_LEARN_LOG`: its only reader is in `alias_learn()`, which is never called, so with the table row gone the
  compiler drops the string (finding 4, now confirmed by the binary). The check was changed to allow exactly that
  word. The rebuild gave the same three md5s.
- All 28 moved words are present in both binaries, and both hold the overlay's `TITLE1B`.
- **The shared state** before and after: patch `589ef163`, normal `30546370`, lean `05fd749d`, archive `a548a249`,
  unchanged.
- Outputs: `~/bc5-work/exp0442/priv/{normal,lean}/kyty_emulator` and `~/bc5-work/exp0442/priv/backend/libbc5_backend.a`.
  Edits for review: `kit/0442-edits.diff` (`8f4755ea`).

### The run plan for a clean boot (`kit/run0442.sh`; prepared and dry-run, NOT started)

One step per invocation, each under its own named user unit (`systemd-run --user --unit=exp0442-<step>`, LESSONS
R73), started by the top session.

| Step | When | What |
|---|---|---|
| `s1` | first, on a clean boot | The first title 200 s on the private lean `fa07ceb9`, everything on (no word set); flips/s as a smoke figure from MangoHud's own frame log (from 30 s; Plasma not stopped, so not an A/B number) |
| `s2` | only if `s1` failed **without** a kernel line | the same with G6+G7 off by their five off-words |
| `s3` | only if `s2` failed without a kernel line | the same with the twenty library words off (G6+G7 on) |
| `ab` | only after `s1` passed | exp 0438's `ab438o.sh` (`d93139fd`) as it is: control = the shared lean `05fd749d`, O = the private lean `fa07ceb9`, a discarded warm-up W0 and five pairs at 1920x1080, 180 s each, MangoHud's log as the frame counter, then one private-normal run (`3079cdf9`, diagnosis only) |

The rules:
- **A kernel line ends the boot's plan** (R55/R60): no further step on that boot. So `s2` and `s3` narrow a failure to
  a group only when it was a crash, an exit or a non-start without a kernel line. A GPU fault needs a restart first;
  the narrowing then goes on, one step per clean boot.
- **Each run step** checks, before it starts:
  - the three pinned binaries;
  - that none of the plan's words is already set;
  - that no emulator runs;
  - the R60 gate with the fixed read (a failed or empty read refuses, rc 3; resets refuse, rc 4);
  - the R72 display check (`display438.inc` `5c6003f7`: EDID, the first mode 1920x1080, the active mode
    1920x1080@60, scale 1);
  - that there is no dead first-title mount.
- **During each run:**
  - one `chain_claim` lock line;
  - pad keys counted (reported only: a caught fault is data);
  - the binary that ran read from `/proc/<pid>/exe` (R66);
  - `ulimit -c 0`.
- The third title's run with this build is exp 0439's, later.

**Dry run** (2026-11-22 09:15, `raw/dry-s2s3.txt`):

- On the real kernel log, every step refuses correctly. This boot (`c133d630`) has 15 GPU reset or timeout lines from
  exp 0439's runs, so `s1`, `s2` and `ab` stop with "R60 ... refused" (rc 4).
- A wrong pin refuses (rc 1), and so does a plan word already set in the environment (rc 1).
- With the stand-in kernel logs (`DRY=1 STANDIN_DMESG=...`, refused without `DRY=1`):
  - a clean log passes to the display check and the plan line (display: card1-DP-1, EDID 128 bytes, 1920x1080@60.00,
    scale 1);
  - a log with resets gives rc 4;
  - an empty log or a failed read gives rc 3;
  - `s2` and `s3` print their word sets.
- `ab`'s own dry run is exp 0438's: `ab438o.sh` refused at its boot check on this boot, as it should.

### s1 on a clean boot (2026-11-22 09:31-09:35, boot c47f9290, the top session's slot; `raw/s1.out`)

The first title ran 200 s on the private lean `fa07ceb9` (the exe md5 was checked) with no switch word set, so the
every-title defaults were on. The R72 display check passed: EDID 128 bytes, the first mode 1920x1080, active
1920x1080@60, scale 1.

- **PASS.**
  - **0 kernel lines**: the runner's check, the laptop's kernel-log stream, and a `sudo dmesg` read after the run all
    agree;
  - 0 crash lines and 0 pad keys.
- **Flips:** 59.19/s from MangoHud's log from 30 s on (9,472 frames in 160 s, 6 frames over 50 ms). This is a smoke
  figure with Plasma up, not an A/B number.
- **The start lines** show all 20 library words on for the first title: SaveData ×3, Http2, Pad OpenExt, Json2, Ult,
  UserService, SystemService and its params 7/1000, AudioOut, AudioIn, the Ngs2 rack, the firmware pad, and the six
  ports.
- `s2` and `s3` were not needed. The lean A/B gets a later boot, and the third title's run is exp 0439's.

### The shared starter swap (2026-11-22 ~09:55, `start0413g.sh` 2389300e → 1d7f34c2)

Checked against `run0442.sh`, by `diff` of the box's `start0413g.sh.before-s413` and the new copy:
- the arguments and the PASS line are unchanged;
- the new refusals print `NOT STARTED … kernel lines UNREAD` (an unreadable or untimestamped log at the start) or
  `KERNEL LOG UNREAD at N s` (mid-run).

`run0442.sh` counts only `PASS: ran 200 s … kernel lines 0, crash lines 0` as a pass, so both new cases come out as
NOT A PASS. `ab438o.sh` matches `PASS: ran $SECS s … kernel lines 0, crash lines 0` the same way. Nothing differs for
the plan.

### G8 for the top session's decision: the rule that replaces each row, or "delete"

No code. Each row stays a TITLE2 row until its open question is answered.

**1. `BC5_DIRECT_ALIASES` (with `GUARD_SPLIT`) and 2. `BC5_DIRECT_HOST_INDIRECT`.** **Superseded 2026-11-22 by the decision below (tag nl442):** both are removed, with no replacement and no learning mode in any form. The earlier proposals here (a built-in alias rule; `learn` without the constant) are withdrawn. See "The learned artefacts removed" below.

**3. `BC5_DIRECT_AMM_PRT=1`: likely console behaviour, so to every title, with the window taken from the title.**
- **What it does today:** at device open, a PRT (sparse) mapping over `0x8000000000` + 64 GiB. Writes to pages the
  title never backed are dropped, and reads return 0.
- **The record:**
  - F257: the second title's TCP write faults there are its own render-target clears of sparse UI surfaces it never
    backs, and "the console drops such writes";
  - F260: one 19-minute session with PRT had no fault of any kind (n = 1);
  - the code's comment: the window is "the title's AMM window … as the guest log's AMM reservation shows", so the
    address comes from the reservation in the guest's own memory calls, not from a learned file.
- **The rule:** the host maps as PRT exactly the AMM window the title reserves (read from that reservation when it is
  made), for every title. That replaces the constant.
- **Open questions:**
  - (a) is the PS5's behaviour for unbacked AMM sparse pages "drop writes, read zero"? F257 states it without a cited
    source: TODO(verify), the maintainer's "does the PS5 do this?";
  - (b) is the AMM reservation at the same place for the first title and the third title? Their normal-build logs show it.
  If (a) is no, the row is a guard: delete it once F257's clears are understood.

**4. `BC5_DIRECT_GPU_CHECK_PRODUCT=1`: delete, after a check that its class is gone.**
- **What it does:** a CP staircase refuses a GFX-ring indirect dispatch with y or z > 1 and x > 2^16. It catches
  F403's runaway grids, such as 818×820×819. It is a guard: it hides the bad arguments and does not stop them being
  made.
- **The record:**
  - F848/F859 found and fixed one source of junk in the title's BVH data (a cross-queue wait passed as met at submit);
  - Q20 (2026-11-18) leaves open "whether the earlier F403-class records are all the F848 mechanism".
- **The rule:** none. Delete the row and the backend's staircase when the class is shown gone.
- **Open question:** with the current shared builds (exp 0430's fix in) and the guard off
  (`BC5_DIRECT_GPU_CHECK_PRODUCT=0`), does the second title's RT-on route still produce grids the guard would refuse?
  The backend can count them without refusing: a count-only mode, its own small change.

**5. `BC5_DIRECT_SHADOW_LABELS=1`: delete, after the same kind of check.**
- **What it does:** a label that an IB both writes and waits on gets a host slot in the job scratch, so a stray store
  over the title's label (F360: a float, 538.4, written over a label that held 1) does not hold the GFX ring's wait.
  It is a guard against a store whose source is unknown.
- **The record:**
  - its presence-only read is fixed in this build (`env_on`), so `=0` now turns it off for a test;
  - F360's store came with an SQC fault and a compute job of the 0x11d03a… family on another ring. That is the same
    shape as F848's cross-queue overwrite, but not shown to be it.
- **The rule:** none. Delete it when the store's source is found and removed.
- **Open question:** with exp 0430's fix in and the guard off, does a label held by a foreign value still occur? A
  count-only mode (compare the title's label to the host slot at completion and journal a mismatch) answers it without
  a hang.

**What the decisions need, in order:**
1. A normal-build run of the second title with three counts: HOST_INDIRECT's rewrites, GPU_CHECK_PRODUCT's would-be
   refusals, and SHADOW_LABELS' label mismatches. This is one build with three count-only modes, by the "fixes first"
   rule.
2. A look at the first title's and the third title's AMM reservation in their logs. No GPU needed if a normal log exists.
3. The two hardware questions, the tag bits (F110) and the sparse-page behaviour (F257), from public sources or the
   maintainer.

### The three count modes (the top session's decisions (2), (4), (5); code on the laptop, NOT built on the box)

Both guards keep guarding in their count modes; the count is a record of how often they act. A plain "do not refuse"
mode could let the very hang they guard against take the box down, and a count of 0 over a run is the same evidence
for deleting them.

| Switch value | What it does |
|---|---|
| `BC5_DIRECT_HOST_INDIRECT=count[:learn[:hex]]` or `count:<hex>` | Every GFX-form dispatch is resolved and counted as before, and **nothing in the IB changes** (`rewrite_verified` is not called). The close summary line is marked `COUNT ONLY`. The register the host carries is the same either way: a rewrite leaves it at 0, as the title did. Parsing moved into `host_indirect::parse_switch`. |
| `BC5_DIRECT_GPU_CHECK_PRODUCT=count[:x_limit[:yz_min]]` | The staircase as before, plus, inside the same `COND_EXEC` (now 18 dwords instead of 9), a second `COND_WRITE x > x_limit ? would = 1` on the flag area's 8th dword (`kWouldByte` 28). That dword is zeroed per job with the area and was unused (the argument copy uses dwords 4-6). `finish()` reads it before the slot is given back. Close line: "N of M completed checked jobs refused at least one dispatch". Parsing moved into `indirect_check::parse_product`. |
| `BC5_DIRECT_SHADOW_LABELS=count` | The shadow labels as before (waits still on the host slot). `apply()` hands back each slot's title label, and after each completed GFX job `finish()` reads the slot and the title's label (through `process_vm_readv`: an unmapped page is counted, not a crash). `shadow_labels::classify` sorts each pair: **equal**; **0** (most likely the title's CPU reset it after its wait); **a third value**, the candidate stray store (F360's float); **unreadable**. The first 20 third values get a line with the job, address and both values. |

`=0` turns each one off; for `SHADOW_LABELS` that works now because its presence-only read is fixed.

**Files** (branch only; the box's sources are untouched):
- `backend/src/direct.cpp`;
- `backend/src/host_indirect.cpp`, `backend/include/bc5/host_indirect.hpp`;
- `backend/src/indirect_check.cpp`, `backend/include/bc5/indirect_check.hpp`;
- `backend/src/shadow_labels.cpp`, `backend/include/bc5/shadow_labels.hpp`;
- `backend/tests/count0442_test.cpp` (added to the Catch2 suite in `backend/CMakeLists.txt`).

**Det tests on the laptop** (Visual Studio's clang++ 20, `-std=c++20`; the Catch2 suite itself needs the Linux
toolchain):
- `count0442_test.cpp` standalone (`-DBC5_STANDALONE`): **5 cases, 53 checks, 0 failed**.
  - The two parsers, every form.
  - The staircase without `count` is exp 0341's exactly (same size, `COND_EXEC` 9).
  - With `count` it is 9 dwords longer, the `COND_EXEC` covers 18, and the second `COND_WRITE` writes 1 at flag + 28.
    Every other dword is the plain staircase's (shifted by 9 after the insertion).
  - `classify` for 32- and 64-bit labels, F360's float included.
  - `apply()` returns the labels in slot order.
- Two mutants (the `COND_EXEC` count left at 9; `classify`'s 0 case removed) fail 1 and 2 checks: the test sees them.
- The three units' existing Catch2 tests (`indirect_check_test`, `shadow_labels_test`, `host_indirect_test`), run
  through a minimal stand-in for Catch2's macros (laptop only, not committed): 23 cases, 588 checks pass on both
  main's sources and the new ones. With `count0442` that makes 28 cases and 641 checks.
- **Not compiled:** `direct.cpp` (it needs libdrm and the Linux headers). Its first compile is the box's, on the top
  session's word. Only the async submission path (the emulator's) reads the counts.

### ALIASES (decision (1)): where a sourced answer could come from (no code)

The question (F110's TODO(verify)): what does the PS5 GPU do with a pointer whose bits 47:40 are 0x80?

Candidate sources, each still to be read and cited by path and commit:
- **Linux amdgpu, the GPU VA layout:** `drivers/gpu/drm/amd/amdgpu/amdgpu_gmc.h` (`AMDGPU_GMC_HOLE_START`,
  `AMDGPU_GMC_HOLE_END`, `amdgpu_gmc_sign_extend`). From memory, and so TODO(verify): the gfx9+ VA is 48 bits with a
  hole starting at `0x0000800000000000`, which is exactly `0x80 << 40`. Addresses from bit 47 up are the
  sign-extended high half. If that holds, the title's 0x80-tagged pointers are high-half addresses, not "tags". The
  question then becomes whether the PS5's GPU sign-extends them (into the upper half the console's own kernel may
  map code into), and what the BC-250's VM does with such an unextended address.
- **Mesa, the client side of the same layout:** `src/amd/common/ac_gpu_info.c` (the VA range the kernel reports) and
  radeonsi's or RADV's use of `address32_hi` and the high VA range.
- **The RDNA2 ISA reference (AMD, public):** the FLAT and global address sections. Is the 64-bit address truncated to
  48 bits, or must it be canonical?
- **RPCSX** (`~/src/rpcsx` `e8ae148`, the GPU-side reference since D18): how its GPU emulation turns a guest GPU
  address into a host one, masked or sign-extended, for the PS5 path.
- **Other public PS4/PS5 projects' GPU code** (Kyty, KytyPS5, shadPS4, under HANDOFF's "Related projects"): any mask
  or tag handling of shader pointers. Only open-source code, cited by file and commit.

What to look for: a statement or code that the console's GPU address space puts code at `0x80xx_xxxx_xxxx`, or that
bits 47:40 are ignored or sign-extended. Until one is cited, `ALIASES` stays a TITLE2 row.

### The learned artefacts removed (tag nl442; the top session's decision of 2026-11-22 on the maintainer's order of 2026-11-13: nothing learned stays, in any form)

Code on the laptop; the box build (`kit/box0442b.sh`) waits for the top session's word.

**Removed:**
- **Host unit `bc5LleAgc.cpp`** (`mk0442.py` stage 2; the unit is `0a7e05a1`):
  - **the aliases:** `alias_path` (`~/bc5-work/direct-aliases-pkg.txt`), `aliases_on`, `aliases_load`, `aliases_apply`
    and both of its calls, and the uncalled `alias_learn`;
  - `BC5_GUARD_SPLIT` (`guard0412_split`, `guard0412_after_cuts` and its call). The lazy release may now always split a
    BO (`splits = true`, as for every other title before);
  - `BC5_GUARD_LEARN_LOG` (`mr412::learn_log`);
  - the zero skip's learned-window guard (`t_force_learned`, `ZLearned`) and its seam `bc5_zsk0401_hint`;
  - the m11 learn refusal (`m11_learn_refused`, `bc5_m11_0401_learn_refused`; `BC5_DIRECT_LEARN_GUEST_ONLY`'s name);
  - the `BC5_DIRECT_LEARNED` comment block.
  The generator asserts that none of these names is left.
- **Header `switch_defaults.hpp`** (`3f9ee1d9`):
  - TITLE2's rows `GUARD_SPLIT`, `ALIASES` and `HOST_INDIRECT` are deleted;
  - **`kGone0442`**: `BC5_DIRECT_ALIASES`, `BC5_GUARD_SPLIT`, `BC5_GUARD_LEARN_LOG`, `BC5_DIRECT_HOST_INDIRECT`,
    `BC5_DIRECT_LEARNED`, `BC5_DIRECT_LEARN_GUEST_ONLY`. One still set in the environment gets the line
    `[bc5] exp 0442: <W>=<v> is set, but the word is gone (nothing learned is read): ignored`, and is unset at start.
- **Backend:**
  - `Device::map_alias`, `unmap_aliases`, the `Alias` list and `drop_aliases_of` (`direct.cpp`, `direct.hpp`);
  - **`BC5_DIRECT_HOST_INDIRECT` whole:** `backend/src/host_indirect.cpp`, `include/bc5/host_indirect.hpp`,
    `tests/host_indirect_test.cpp`, its `CMakeLists.txt` entries, and its fields, parse, submit pass and summary line
    in `direct.cpp`;
  - the HOST_INDIRECT count mode written earlier today goes with it.

**Left for the second title:** `DMA_SYNC` and `FLAT_APERTURE` (G5, exp 0439), and `AMM_PRT`, `GPU_CHECK_PRODUCT`,
`SHADOW_LABELS` (G8, their questions above).

**Risks, recorded and not hidden:**
- Without the alias, a fetch of a 0x80-tagged program address (F110) faults: a bug with a record, fixed at its cause.
  - Code removed with `map_alias` already sign-extended such addresses for this kernel ("the kernel's VA hole",
    `amdgpu_vm_ioctl`), which supports the lead in the ALIASES note.
- Without HOST_INDIRECT, a GFX-form dispatch after the title's zeroing reads the bare offset: F416's class (CPF
  permission fault, machine down on 2026-10-27). F432 counted 0 rewrites in 18 minutes.

**The sweep** (the list sent to the top session for the maintainer; P:n are lines of patch 0001 on main `589ef163`):
- **A, removed here:** ALIASES, GUARD_SPLIT, GUARD_LEARN_LOG with `alias_learn`, and HOST_INDIRECT.
- **B, dead learned remnants:**
  - 5-7 are removed here: the `BC5_DIRECT_LEARNED` comment, the zero skip's `ZLearned` and `bc5_zsk0401_hint`, and the
    m11 learn refusal.
  - **B8, the zero skip as a whole**, is left for its own step: exp 0379's zero list, written by a run and read in
    later ones; its option has been removed since exp 0419, and F818 calls it unsound.
- **C, named "learned" but a rule or record, no learned data:** `learned_apply()` (exp 0037's zero guards behind the
  eager heaps, with `BC5_GUARD_APPLY_MIN_MS`), `mr412_would_learn` (the GPU-fault record), and the `load_stat` names.
  Proposed: rename only, on the top session's word.
- **D:** `BC5_GUARD_MAP_RULE` and `BC5_GUARD_PRT_BG`, the rule switches built to replace the windows: not learned; a
  separate decision.
- **E, the repo's tools:**
  - `tools/scripts/bc5-install.sh:26`, `:170-171` create `direct-learned-none.txt`;
  - the repo copy of `tools/scripts/launchers/play-pkg.sh`: `:5`, `:63`, `:64`, `:70`, `:152`, `:157`.
- **F, the maintainer's `~/bc5-work/play-pkg.sh` `47426d8e`:** lines 49, 50, 56, 138, 143 (listed only; nothing
  changed).
- **G, files on the box, by name only (nothing read):**
  - `~/bc5-work/direct-aliases-pkg.txt`;
  - `direct-learned-pkg.txt` (F687);
  - `direct-learned.txt` (the old default name);
  - `direct-learned-none.txt`;
  - F820's three stale scripts `run-pkg.sh`, `play-pkg-exp0155.sh`, `lean-backup-play-pkg.sh`;
  - earlier moves are in `~/bc5-work/trash-20261113/`.
  The top session moves them to the trash after the bake.

**Det tests:**
- **Laptop** (VS clang++ 20):
  - the backend's `indirect_check_test` and `shadow_labels_test` through the Catch2 stand-in: 23 cases, 559 checks,
    0 failed;
  - `count0442_test` standalone: 43 checks, 0 failed (its HOST_INDIRECT case went with the word).
- **Box** (`test0442.sh`, updated; it needs Linux, so it runs with the box build on the top session's word). It checks:
  - T2: the 5 left rows are unset for other titles;
  - T4: the second title, word by word; a clean environment differs only by the five deleted rows (`GUARD_LEARN_LOG`,
    `SKIP_PGM`, `GUARD_SPLIT`, `ALIASES`, `HOST_INDIRECT`), and with `play-pkg.sh`'s own words only the four gone
    learned words, set → unset;
  - T6: each of kGone0442's six words, when set, is unset and reported on stderr; the old header kept it.
- **Not compiled:** `bc5LleAgc.cpp` and `direct.cpp` (Linux only): the box build is their first compile.

### B8: exp 0379's zero list removed whole (tag zl442, its own commit)

`mk0442.py` stage 4 removes the zero list (the option was gone since exp 0419; F818: unsound by design; the list one
run wrote was read by later runs). The host unit goes from 17,895 to 17,084 lines (unit md5 `3b28b024`).

**Removed:**
- the inlined `zero_skip.hpp`; its standard `#include`s are kept;
- the section "experiment 0379: the zero list" (the scan, the canary, `g_zskip`, `zskip_*`, the seams
  `bc5_zsk0401_*`);
- the zero-skip poll `zpoll412_submit` (zp412);
- `lzr_zero_skip`, `lzr_zero_name`, and every call into them;
- K1r's refusal for the zero skip or the pin cap (both gone since exp 0419);
- the backend's own copy, `backend/include/bc5/zero_skip.hpp`, with `backend/tests/zero_skip_test.cpp` (nothing else
  used them).

**Kept, now always false:**
- the lazy release library's own "zero" chunk class and `plan()` parameter;
- two slots of exp 0432's x432 reason counters, so the counters keep their meaning.

**History left uncompiled:** exp 0401's CPU harnesses that called the seams (`experiments/0401-mesa-preamble-switches/zsk0401.cpp`,
`m110401.cpp`) and exp 0412's `zpoll0412.cpp` stay in `experiments/` as the record; they are no longer built against the
current unit.

### C: renames with unchanged behaviour (tag rn442, `mk0442.py` stage 3)

**Identifiers:**
- `learned_apply` → `heap_guards_apply`: exp 0037's 2 MiB zero guards behind the eager heaps, a rule;
- `mr412_would_learn` → `mr412_fault_record`: the GPU-fault record;
- in `bc5/load_stat.hpp`: `kLearned`, `kLearnedApply`, `kLearnedChanged` → `kHeapGuards`, `kHeapGuardsApply`,
  `kHeapGuardsChanged`. The values are unchanged; all ten includers of the header recompile.

**Journal and stat texts that change** (no shared tool in `tools/` parses them; exps 0231-0412 scripts in
`experiments/` do, as history):

| Before | After |
|---|---|
| `learned apply: %.1f ms (...)` | `heap guards apply: %.1f ms (...)` |
| `learned_apply took %.1f ms on %s (layout gen ...)` | `heap_guards_apply took ...` |
| `guard: BC5_GUARD_APPLY_MIN_MS ...: learned_apply at most once per that ...` | `... heap_guards_apply at most once ...` |
| `would learn (exp 0412, tag mr412): t %.3f s: fault ...` | `fault record (exp 0412, tag mr412): t %.3f s: fault ...` |
| load-stat names `learned`, `learned_apply`, `learned_changed` | `heap_guards`, `heap_guards_apply`, `heap_guards_changed` |

Every other line keeps its text. The one-shot line `learned windows: removed from this build (exp 0412, tag nl412,
guards kept): ...` is unchanged: it states the removal.

### D: `BC5_GUARD_MAP_RULE` and `BC5_GUARD_PRT_BG` (listed for a separate decision; no change)

| Word | What the rule did (exp 0412 mr412, F819) | Today |
|---|---|---|
| `BC5_GUARD_MAP_RULE=1\|2` | R1: every 2 MiB chunk under a view of direct memory (2: of private memory too) imported when the view exists, instead of the learned windows | `mr412::rule()` returns 0 ("gone since exp 0419 candidate G; K1r replaced it"). So `rule_for()` is always false, and its one use, the eager-import branch of `direct_sync_one` (`v.eager \|\| mr412::rule_for(S.kind)`), is dead. Nothing reads the word. |
| `BC5_GUARD_PRT_BG=1` | R2: one PRT mapping under the guest's whole span `[kBgLo, kBgHi)` at device open (acts only with MAP_RULE) | `mr412::prt_bg()` returns false. `g_mr412_bg` is never set, so `in_bg()` and the background branches in `mr412_prt_open` and `scratch_fill` are dead. Nothing reads the word. |

Neither is learned data: they were the rules built to replace the windows. Both are already gone as options; what is
left is dead code (`rule`, `rule_for`, `prt_bg`, `in_bg`, `kBgLo`/`kBgHi`, `g_mr412_bg` and their branches), for a
cleanup on the top session's word. `CLAUDE.md`'s line that they are "compiled in, off, and must stay unset" can say
"gone, dead code left" until then.

### E: the repo's tools (done)

- `tools/scripts/bc5-install.sh` no longer creates `direct-learned-none.txt`.
- The repo copy of `tools/scripts/launchers/play-pkg.sh` loses:
  - the comment's "learned-fault file";
  - `BC5_DIRECT_LEARNED`, `BC5_GUARD_LEARN_LOG`, `BC5_GUARD_SPLIT` and `BC5_DIRECT_ALIASES`;
  - `BC5_DIRECT_HOST_INDIRECT`;
  - `BC5_GUARD_FORGET` and `BC5_DIRECT_SOFT_WAIT_MS`, which were dead (`kIgnored`, no reader);
  - it keeps `BC5_DIRECT_INDIRECT_DRAWS=multi` (it has a reader; redundant with the every-title default).
- The maintainer's live `~/bc5-work/play-pkg.sh` is his and unchanged.

### Bakes 1a-1d and runs 1-8: what reached the shared builds (2026-11-22)

**Deployed: bake 1c+1d, patch `d45618c6`, since 2026-11-22 19:49** (the maintainer's approval to deploy). Builds: normal
`28ab1389`, lean `b0f856ed`, archive `ed9f5dfe`. Undo: `bash ~/bc5-work/exp0442/bake442kit/undo0442.sh`, back to
`589ef163` / `30546370` / `05fd749d` / `a548a249`. The kit is `bake/` (pins in `bake/pins0442.inc`); the docs text is
in `bake/DOCS-1c1d.md`.
- **Bake 1** gave the 28 rows to every title, removed everything learned and removed the zero list. Its lean A/B was
  about −1 % flips/s on the first title, so it was not swapped.
- **Bakes 1a and 1b** kept DMA_SNAPSHOT (1a) or all five G6+G7 rows (1b) as TITLE2 rows. They gave −1.06 % and
  −1.21 %, below the control in 3 of 3 runs. Not swapped.
- **Run 5** used a null private build (the unchanged sources rebuilt). It sat as far below the shared lean as B did:
  C 58.51, B 57.63, G4 off 57.82, null 57.80 flips/s. The first run after a start was always the fastest control run.
- **Bake 1c** is bake 1 plus three D28 cost fixes, each on unless set to "0": `BC5_DIRECT_0442_GC_NOCOPY`,
  `BC5_DIRECT_0442_CS_SKIP` and `BC5_DIRECT_0442_SNAP_GROW` (an 8 MiB snapshot ring that doubles up to 64 MiB).
  Run 6 swapped it and built both sides with ninja. Lean C 58.01 against N 57.43 flips/s (−1.0 %); it failed and was
  undone. GTT was +8 MiB against the old lean (the ring stayed at 8 MiB, not 64).
- **Bake 1d** removed exp 0273's ray-tracing switch whole, on the maintainer's order of 18:05: the menu item,
  `KYTY_BC5_RT` and `KYTY_BC5_RT_BUILD_PGM`. An old `RayTracing.<ID>=` line is accepted, reported once and not
  written back. `kGone0442` gains the two words.
- **Run 7** checked the swapped 1c+1d's functions on boot aef3e9b1, and every check passed:
  - smoke: lean 58.39 and normal 57.95 flips/s;
  - the gone-words report appears once in normal and never in lean;
  - on a copy of the maintainer's input configuration, one ignore line and no error, with his files unchanged
    (md5 checked);
  - no "Ray tracing" string is left in the new binaries.
- **Run 8 (perf stat, user space, old shared lean against the new one):**
  - flips/s: C 57.57 and 57.49, N 57.28 and 57.60;
  - the title's render thread (DrawThread): 106.3-106.6 G against 110.0-110.7 G instructions in 100 s (+3.8 %),
    at the same IPC (1.41 against 1.43) and the same L1i miss rate;
  - BC5's own threads are unchanged.

  So the cost is extra work in the submit path, not code layout. `bake/D28-DRAWTHREAD-LIST.md` lists each row's
  expected work there; the GPU check's IB rebuild is the most likely cause. A `perf record` on DrawThread comes next.
  Raw data: `raw/perf8/`.
- **Procedure:**
  - `kit/stop0442.sh` stops a run and cleans up after it: a `bc5-mount` left in the distrobox's cgroup, a dead FUSE
    mount visible only inside the container, and this run's own lock line;
  - R55 now also forbids file reads during a measured run;
  - the RA24 display line is excluded by name.
- Main's copy of patch 0001 was regenerated to exactly `d45618c6` on the laptop: f266548, plus 589ef163 (re-diffed to
  589ef163), plus the 1d host files at their pinned md5s.
