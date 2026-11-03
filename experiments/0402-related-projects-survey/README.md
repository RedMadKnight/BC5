# 0402 — related projects survey, 2026-11-03: what to import, especially from AnyPS5

**Question.** What have the public related projects (AnyPS5 above all) solved since our last surveys, which of their
system libraries are missing, weaker or fixed relative to our host, and which of their GPU-side and memory changes touch
our open problems (GPU hangs with no page fault, sparse/PRT memory, memory pressure)? The output is a ranked import list
for the maintainer's decision; nothing is imported here.

The maintainer's words (2026-11-03): "zleć kolejne rozeznanie w pokrewnych projektach - co warto od nich zaimportować i
jakie problemy udało się rozwiązać - w szczególności zaimportować nowe lub brakujące u nas (lub poprawione) biblioteki z
anyps5".

## Setup

Read-only research on the laptop. There was no box access and no code import. No Sony material, dumps or keys were
fetched or used.

### Our side (the effective base)

- KytyPlus `f266548` with `backend/kytyplus-patches/0001-bc5-lle-agc.patch` from main `a8324c8b` applied with `git apply`.
  That patch already holds the 0327 imports, the 0328 NpCppWebApi port and the PORT-NP and PORT-LIBC fixes (F740, F741).
- "Registered in our host" means a `LIB_FUNC("<nid>", …)` anywhere in that patched `src/` tree, 3,036 NIDs in all.
- The second title's link-time stub list (197 NIDs) is `experiments/0327-missing-imports/raw/S1-stub-list-resolved.txt`.

### AnyPS5 (GPL-2.0-only, `LICENSE` and README)

- Read at `boykopovar/AnyPS5` `4f41f4c375f5abb487dbd184fbc150f31994d762` (2026-11-03, blobless clone).
- It has 17,035 commits since our first review at `7f596df`. Codex's review (`Documents/ChatGPT/BC5/audit/upstream-review/`,
  REPORT/ANYPS5/PORT-PLAN) covered it up to `7ba97f4` (2026-10-30). Only the delta after that, and anything Codex did not
  report, is new here.
- Exports were counted per library directory from `APS5_VABI` definitions. A definition whose short body calls
  `NotImplemented_nid_no_patch` counts as pending.
- `_nid_postfix` is stripped, `_nid_no_patch` is internal, and `APS5_EXPORT("<nid>", f)` gives the NID directly. This
  follows `core/libs/nid/include/nid/NidPatcherUtils.hpp` and `core/libs/prx/libc/include/general/ExportMacros.hpp`.
- Names were hashed to NIDs with the same calculator as exp 0327 (`nidcalc.pl`), self-checked on known pairs.
- Script: `inventory.py`. Output: `raw/anyps5-vs-host-by-library.tsv` and `raw/title-stubs-vs-hosts.txt`.

### Other projects

- Two read-only sub-agents read AnyPS5's GPU side and the other projects. They used the clones at the commits named
  below and GitHub's unauthenticated API (`gh` is not installed).
- KytyPlus `149c877`, KytyPS5 `dfec14a`, RPCSX master `e8ae148`, sharpemu `514d7660`, astraea, obliteration,
  OpenProspero/AGC, ps5-vulkan, shadPS4 PRs and branches, and a GitHub search for new PS5 projects since 2026-10-15.

### Lessons applied (`coordination/LESSONS.md`)

- R18: a host or stub fix is not evidence for F403, F443 or Q21.
- R21: similarity is not cause.
- R23: loading a program is not complete state.
- R32: check name → NID → `SymbolDatabase` → function type.
- R34: an export name or success code is not a native contract.

### Provenance exclusions

These are not used and not cited as facts:

- AnyPS5 debt notes that cite an SDK reference (already excluded in `docs/ports/anyps5-review.md` §1).
- Notes citing disassembly of firmware 13.42 modules: `docs/dev/debt/libSceAgcDriver.md` lines 52 and 73,
  `docs/dev/debt/libkernel.md` line 63.
- The initial context registers in `core/libs/prx/libSceAgc/Command/include/RegisterDefaultsData.hpp`, described there
  as "SDK context defaults".
- The KytyPlus fork `ayasns` (264 commits of firmware/PUP key-store work) was not read.
- `chaosyizer/KytyPS5` has no licence and was skipped. RustPS5 is AGPL: ideas only.

## Result

### 1. The one gap the second title still links against: ten NpCppWebApi exports

- Of the 197 NIDs that exp 0327's run stubbed at link time, our host now registers 187. The ten it does not are exactly
  the ten "unresolved" NpCppWebApi NIDs F809 found in the log of 10-31.
- AnyPS5 implements all ten. Its mangled names hash to them (`raw/title-stubs-vs-hosts.txt`). They are SessionManager V2:
  - `PlayerSessionsApi::createPlayerSessions` (`eVU3cXIJz0w`)
  - `joinPlayerSessionAsPlayer` (`BY1jyWLZrcA`)
  - `leavePlayerSession` (`JiY4sfHkV34`)
  - `getPlayerSessionInvitations` (`LbhH9NeB93I`)
  - `ParameterToJoinPlayerSessionAsPlayer::initialize` (`XuVY56j7GM0`)
  - five factories' `create`:
    - `RequestPlayerSessionFactory` (`fIzsqjyD5oY`)
    - `RequestCreatePlayerSessionPlayerFactory` (`sRn6qePT54Q`)
    - `RequestPlayerSessionMemberPlayerFactory` (`-0Vv7HKZaBM`)
    - `PostPlayerSessionsRequestBodyFactory` (`yl3T9brJay4`)
    - `PostPlayerSessionsSessionIdMemberPlayersRequestBodyFactory` (`xjVhrq2KPJA`)
- The four Api calls and the five factories return `SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN` (0x80552907).
  `initialize` calls the same `InitializeParameterWithBody` helper as the other parameters.
- Source: `core/libs/prx/libSceNpCppWebApi/Export.cpp` @ `4f41f4c37`.
- The names were already present at `27c88a8`, the commit 0328 ported from, and date back to `8cd400aa4`. F391's "absent
  from AnyPS5's table too" is therefore wrong for these ten. The port missed them.
- Our host answers them with the loader's return-0 stub. Under that stub, a factory `create` reports success without
  writing its out-pointer.
- Whether the title calls them is not shown. Exp 0327's 120-s run logged six `stubbed import called` lines, none of them
  these. The 10-31 lines are link-time stubs, not calls.

### 2. Per-library comparison (AnyPS5 `4f41f4c37` against our effective base)

"Impl." counts exports whose bodies are not the pending stub. "Not in ours" is how many of those our host does not
register at all. Full table: `raw/anyps5-vs-host-by-library.tsv` (406 directories, 38,075 exports, 10,707 implemented).
For the second title only the link-time list matters, and it is covered except for §1.

| Library | AnyPS5 exports / impl. | Impl., not in ours | Ours (KytyPlus + patch) | Mark | Note |
|---|---|---|---|---|---|
| NpCppWebApi | 1363 / 1074 | 953 | 138 (0328 port + F740) | **ours weaker** | Ten of the title's imports missing (§1); the rest are other titles' APIs. |
| libkernel | 771 / 726 | 335 | ~390 here + Posix fallback (F408) | **theirs fixed** | The missing ones are BSD socket/`dl*`/uid calls the title does not link. After `7ba97f4`: rwlock wake races (`4ed0f9f91`, `372f0f6c6`, `83b1015c4`), `URWLOCK_PREFER_READER` with `RW_RDLOCK` "as the console does" (`45a8b80a5`), condvar relock spin (`16375634e`). Unknown whether our pthread code shares the design (item 3). |
| libc / LibcInternal | 1633 / 1619; 989 / 87 | 1565; 82 | the title ships its own `libc.prx`; LibcInternal as patched (F741) | moot / parity | No LibcInternal NID in the title's stub list. |
| Ampr / APR / AMM | 150 / 147 | 56 | 106 + F206 pool | ours fine for the title; **theirs further on PRT** | Missing: the AMM PRT commands (`MapAsPrt`, `RemapIntoPrt`, `UnmapToPrt`, `AllocatePaForPrt`), `MultiMap`/`Remap`/`ModifyProtect` and their measure functions, `WaitOnAddress`/`WaitOnCounter`. None are in the title's stub list. Their PRT semantics: item 7. |
| AudioOut / AudioOut2 | 192 / 69 | 34 | `libAudio2.cpp` + F247 grain model, exp 0372 | **theirs fixed** (compare) | Missing: `Lo*`, `Ex*`/`Sys*`, `GetSystemState` (not linked by the title). After `7ba97f4`: PCM taken at the set on advance (`c34ab0258`), silence for a regiven buffer not set again (`11f217b14`), blocking push returns once there is room (`42beeaa46`), reopen of the default output and the controller card after the host stops them (`b87075aad`, `ccaac6602`). Item 2. |
| Pad | 214 / 53 | 31 | DualSense USB/BT, haptics, F214 rumble | **ours better** on the pad | Missing: queries (`GetControllerType`, `IsDS4Connected`, …) the title does not link. |
| SaveData | 120 / 54 | 26 | 23 funcs + F205, F217, F319 | parity for the title | Missing: event callback, `Umount`/`Mount2` v1 forms, SaveDataMemory. Event delivery fixes after `7ba97f4` (`0d0abe09c`, `bc6b4d76f`). KytyPS5 `dfec14a` mount result on failure. Item 9. |
| NpManager | 553 / 77 | 27 | F215 signed-out model | parity for the title | Missing: IdMapper and the `Int*` family. |
| NpTrophy2 / UDS | 61 / 18; 93 / 41 | 0; 26 | `libTrophy.cpp` + F216 | parity / not linked | UDS event-property builders are missing; not linked. |
| AgcDriver / Agc | 146 / 95; 240 / 234 | 70; 110 | **LLE from the module pack** (Q14) | **missing in ours** (D18 debt) | The title's command stream comes from the pack's `libSceAgc`/`libSceAgcDriver`. AnyPS5's are the candidate source for Q14(2). Item 8. |
| PlayGo / Psml | 24 / 23; 0 / 0 (`libScePsml_debug` 31 / 22) | 5; — | HLE tables exist (18 / 19) but the pack's `.sprx` win (Q14) | **missing in ours** (D18 debt) | Missing PlayGo: `GetRequiredDisc`, `RequestNextChunk`, `RequestOptionalChunk`, `SetInstallSpeed2`, `SetLanguageMask`. Item 8. |
| AJM | 52 / 38 | 7 | Opus via libopus, ATRAC9 6–7 via vgmstream (F300) | **ours better** | AnyPS5 still rejects ATRAC9 configurations 6–7. |
| VideoOut | 266 / 58 | 21 | direct path, deferred flip | different architecture | Missing: v1 `RegisterBuffers`, cursor, colour; not linked. |
| UserService, SystemService, Rtc, Ult, Fios2, Json2 | 617 / 27; 618 / 146; 52 / 51; 96 / 83; 168 / 106; 223 / 219 | 10; 134; 25; 60; 106; 130 | KytyPlus tables (+ 423 Json2 patch lines) | not linked by the title | Backlog by real imports only (Codex REPORT step 4). |
| Ngs2, Fiber, NpAuth, Audiodec, AvPlayer, dialogs | — | 0–8 | present | parity | The Ngs2 "missing" names are host-internal job functions. |

### 3. GPU side and memory: what AnyPS5 and the others do about our open problems

Judgements: (a) portable to a host that submits real PM4, (b) a semantic fact, (c) specific to Vulkan translation.

**F403: garbage dispatch dims, or an acb dispatching before its own program.**

- AnyPS5 reads indirect dims raw when the packet executes, with no clamp. It only refuses a zero dispatch base or an
  overflowing address (`libSceAgcDriver/Execution/src/Pm4.cpp:831-863`).
- It defers that read until the queue's pending labels and lease work are finished
  (`Execution/src/Driver/Dispatch/IndirectDispatch.cpp:71-112`). The CPU enforces an ordering the hardware does not. (b)
- The thread-dimension initiator bit (0x20) makes the dims thread counts. `b5e25f1b6` computes the groups in 64 bits so
  0xffffffff threads no longer wrap to 0 (`Execution/include/Driver/Driver.hpp:54-56`). (b)
- Compute state persists per queue number across submissions and is never reset implicitly
  (`Execution/src/Driver/Packets/PacketExecution.cpp:215-222`).
  - The only reset is a NOP marker 0x10 / subcode 9 that their own `sceAgcAcbResetQueue` emits
    (`libSceAgc/Acb/src/Control.cpp:54-63`, `Pm4.cpp:1071`). The encoding is their guess, not a measurement.
  - A dispatch on a queue that never wrote `COMPUTE_PGM` is refused (`Execution/src/Driver/Dispatch.cpp:83`,
    `Driver/Diagnostics.cpp:136-140`).
  - Unwritten user data reads 0 (debt note 88, unmeasured).
  - So AnyPS5 has no compute-state reset prefix and no console data on what the system does at an acb boundary. (b)
- Accepted acb queue range: 0x20–0x58. Debt note 42 cites a console measurement (firmware 13.40, label-only buffers;
  0x1F faulted). Sources: `Submit/src/Acb.cpp:13-27`, `051b3e017`, `683b3497d`. (b)
- sharpemu `11506fc` (GPL-2.0-or-later) captures the DCB and every `SET_*_REG_INDIRECT` table at submit and uses those
  copies unless the GPU wrote them, because titles rewrite them soon after submit
  (`src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs`, CaptureSubmittedTables). This is the only public lead on how dims
  could become garbage after submit. (a) as a catcher.
- KytyPS5 `1b70938`: `AgcAcbMemSemaphore` emits a PM4 `MEM_SEMAPHORE` (signal op 6, wait op 7).
  `src/libs/agc.cpp` and `pm4Handlers.cpp`. Relevant only once the host owns `libSceAgc` (Q14).

**The draw that never ends (GRBM 0xa2712028, `VGT_SHADER_STAGES_EN` 0x482030).**

- Nothing in any project on hangs, `GRBM_STATUS` or draw termination.
- AnyPS5's queue defaults: `indexBase` 0, `INDEX_BUFFER_SIZE` unset, `NUM_INSTANCES` 1, indirect bases 0
  (`Execution/include/QueueState.hpp:220-303`). `3d831f4d1` lets an indexed indirect draw on a queue that never set
  `INDEX_BUFFER_SIZE` read unclamped (`Pm4.cpp:900-923`), from a title that never emits it.
- Their notes 292 and 54 say the console's initial values are unmeasured. (b), weak.
- `GS_FAST_LAUNCH` handling is RADV-style mesh emulation. (c)

**Sparse/PRT.**

- AnyPS5 maps unbacked AMM PRT pages to zero pages that the GPU can only read. `AllocatePaForPrt` backs only the
  unbacked runs and restores the zero pages on failure.
- Sources: `core/libs/prx/libkernel/Apr/src/Apr.cpp:417-480` (`e3b5192cb`, `79fc99774`);
  `libkernel/DirectMemory/DirectMemory.cpp:1284-1293`; on Windows a single read-only zero section, `37881a5da`
  (after `7ba97f4`).
- Its stated semantics (debt note 61): reads return 0 and GPU writes fault. Ours (F161, F257) drops writes.
- Provenance: inferred from names and cross-checked against other emulators; "not confirmed on a title". (b), weak.
  There is no support for "writes dropped" either way.

**Memory pressure.**

- AnyPS5 `ad9a0c8ef` set direct memory to 12 GiB (0x300000000). Its commit message cites a measurement: the value
  `sceKernelGetDirectMemorySize` returned inside a retail title on a PS5 running firmware 13.40.
- `97f1d41a2` (2026-10-28) reverted it to 13,824 MiB because ASTRO BOT ran out at 12,228 of 12,288 MB.
- Ours: `TotalSize()` 12,800 MiB minus flexible (`src/kernel/memory.cpp:761-811`, KytyPlus comment "~12.5 GiB").
- KytyPS5 `09753bf` and `0a14091` derive the budget from `param.json`: 12.5 GiB minus a 64 MiB cache, minus
  `kernel.flexibleMemorySize` (default 448 MiB, module segments charged to it) and the page-table sizes. Direct memory
  gets the rest.
- Neither project has guest-memory eviction. AnyPS5's direct memory is one sparse memfd imported in 64 MiB udmabuf
  chunks, never punched, so the process keeps its high-water mark (debt note 195). That is close to our eager import (F353).

### 4. The other projects

| Project (licence) | Read | New since our last survey |
|---|---|---|
| KytyPlus (GPL-2.0) | `2c8e00d7..149c877`, 24 commits | Nothing in `src/libs`, `src/kernel` or `src/loader`; Vulkan present/cache work only. Forks: crystalse and JonJon1992 have 0 commits ahead; ayasns is excluded (keys/firmware). |
| KytyPS5 (GPL-2.0) | `8291cfe..dfec14a`, 182 commits, 46 in libs/kernel/loader | Memory budget from `param.json` (`09753bf`, `0a14091`); `MEM_SEMAPHORE` (`1b70938`); AudioOut2 port count and exact-grain drain (`2efd314`, `7ff8aff`, `64a554d`); Opus partial packets and resampler (`c528324`, already in Codex's review); SaveData sort and mount failure (`4b0282e`, `dfec14a`); guest TSC at 1.6 GHz by instruction patching (`2f885e2`, ideas only). |
| shadPS4 (GPL-2.0) | PRs and branches | No PS5 work since 2026-10-01. The CHAIN fix `1b9d1591` is already ported (PORT-CHAIN). |
| RPCSX (GPL-2.0) | master | Still `e8ae148`; PRs #121 and #122 were closed unmerged. |
| sharpemu (GPL-2.0-or-later SPDX) | `299c907c..514d7660` | Submit-time table capture (`11506fc`); acquire-mem as a global barrier (`8ddf660`); `sceVideoOutGetOutputStatus` reports UHD before buffers are registered (`b1ec286`). |
| astraea (GPL-3.0), obliteration (Apache-2.0), OpenProspero/AGC (GPL-3.0), ps5-vulkan (GPL-3.0) | GitHub API | Nothing relevant since 10-21. |
| New projects | GitHub search | lumen-emu (an Android wrapper) and TxCsOffc/KyTx (ARM64/Metal, created 11-02): nothing for gfx1013. |

## Verdict

AnyPS5 has no library the second title needs that we lack, except the ten NpCppWebApi exports of §1. Everything else on
the title's link-time list is registered in our host.

No project has solved any of our open GPU problems. AnyPS5 runs on Vulkan, reads indirect dims raw, and keeps compute
state per queue without a reset. Nobody has a hang or `GRBM_STATUS` analysis, and nobody has console values for queue
state at a buffer boundary. Their GPU work yields facts and one catcher idea, not fixes.

Under the "fixes and catchers first" rule, items 1, 4 and 5 can go into one private test build, each behind its own
switch. Items 2 and 3 are comparisons first and become code only where our implementation shows the same defect.

### Top 10, ranked by expected value over cost

| # | Import | Exact source (licence) | Touches | Effort / risk |
|---|---|---|---|---|
| 1 | **The ten SessionManager V2 NpCppWebApi exports**: nine return 0x80552907 NOT_SIGNED_IN; `initialize` uses the existing parameter helper. | AnyPS5 `core/libs/prx/libSceNpCppWebApi/Export.cpp` @ `4f41f4c37` (present since `8cd400aa4`) (GPL-2.0-only) | The last link-time stubs of the title (F809). A return-0 factory leaves its out-pointer unwritten: a possible guest CPU crash path, not shown to be called (R18). | S / low. Gate (R32): resolve each NID through the real `SymbolDatabase` after `InitAll`, check the signatures, run the 0328 tests. |
| 2 | **AudioOut2 fixes after `7ba97f4`**: PCM taken at the set on advance, silence for a regiven buffer, blocking push returns when there is room, reopen output/controller card after the host stops it. | AnyPS5 `libSceAudioOut` `c34ab0258`, `11f217b14`, `42beeaa46`, `b87075aad`, `ccaac6602` (GPL-2.0-only) | F247/F326 pacing; the DualSense replug (exp 0372) | S–M / M. Compare with our grain model first; any change gets the exp 0372 replug check. |
| 3 | **rwlock / condvar race fixes**: compare against our pthread code; port the predicate-atomic waiter cleanup and the console's `URWLOCK_PREFER_READER` rule where ours differs. | AnyPS5 `core/libs/prx/libkernel/Pthread` `4ed0f9f91`, `372f0f6c6`, `83b1015c4`, `45a8b80a5`, `16375634e` (GPL-2.0-only) | Title rwlocks via Posix fallback (F408) and the 0327 timed rwlocks; CPU-side stalls or crashes (hypothesis) | M / M. CPU stress tests first; no claim without a reproducer. |
| 4 | **Submit-time table catcher**: hash each submitted buffer's indirect-args slots and `SET_*_REG_INDIRECT` tables at submit, compare at completion and at a hang. | idea from sharpemu `src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs` @ `11506fc` (GPL-2.0-or-later) | F403 sub-class B: garbage dims written after submit vs read too early | S / low, as a switch, default off. A catcher, not a fix. |
| 5 | **Direct/flexible sizing from `param.json`**: flexible from `kernel.flexibleMemorySize` (default 448 MiB, module segments charged), page-table overhead subtracted, direct = rest. | KytyPS5 `src/kernel/memory.cpp`, `src/loader/systemContent.cpp` @ `09753bf`, `0a14091` (GPL-2.0); measured 12 GiB from AnyPS5 `ad9a0c8ef` as a reference only (reverted `97f1d41a2`) | The 11.3 GiB pinned GTT on the 16 GB box | S–M / M: a title may size its heaps from this value; AnyPS5's revert shows a too-small pool fails loads. One switch, a startup log of the reported sizes, then a play. |
| 6 | **acb-boundary facts for the F403 analysis**: per-queue compute state persists; their reset marker NOP 0x10/9; queue range 0x20–0x58 (measured); thread-dimension dims; never-written `COMPUTE_PGM` refused. Journal whether the title's acbs carry a reset-marker NOP before F403-class dispatches. | AnyPS5 `Execution/src/Driver/Packets/PacketExecution.cpp:215-222`, `Pm4.cpp:1071`, `Submit/src/Acb.cpp:13-27`, `Execution/include/Driver/Driver.hpp:54-56` @ `4f41f4c37` (GPL-2.0-only) | F403 (acb before its own program), today's acb-prefix crashes (R23) | S / low (analysis, then a journal line). The NOP encoding is their guess, so it is a lead only. |
| 7 | **PRT zero-page model**: GPU reads of unbacked AMM PRT pages return 0, `AllocatePaForPrt` backs only unbacked runs, rollback on failure. Compare with our AMM-as-PRT window; decide the write side (ours drops, theirs faults) by test. | AnyPS5 `core/libs/prx/libkernel/Apr/src/Apr.cpp:417-480`, `DirectMemory/DirectMemory.cpp:1284-1293` @ `4f41f4c37`; `e3b5192cb`, `79fc99774`, `37881a5da` (GPL-2.0-only) | F161/F257 sparse UI layer; Q22 stray writes | M / M. Weak provenance on both sides. The AMM PRT command exports are not linked by the title. |
| 8 | **Q14 / D18: replace the module pack's PlayGo, then Agc**: our HLE PlayGo with AnyPS5's five extra exports and chunk-list fixes; then an HLE `libSceAgc` adapter. | AnyPS5 `core/libs/prx/libScePlayGo` (`6ea971ead`, `a8a5caa2a`), `core/libs/prx/libSceAgc` (234 of 240 implemented) @ `4f41f4c37` (GPL-2.0-only); KytyPS5 `1b70938` `MEM_SEMAPHORE` | D18 debt (game-dump modules still loaded); no current symptom | PlayGo S–M / M; Agc L / H. Packet-by-packet comparison against the LLE stream is the gate (Codex REPORT, R34). |
| 9 | **SaveData lifecycle**: event-callback delivery thread and atomic registration; mount result untouched on a failed mount; sorted search. | AnyPS5 `libSceSaveData.native` `0d0abe09c`, `bc6b4d76f`; KytyPS5 `src/libs/libSaveData.cpp` @ `dfec14a`, `4b0282e` (GPL-2.0) | Save slots only if the title registers a callback (not on its stub list) | S / low. Only on evidence of use. |
| 10 | **`sceVideoOutGetOutputStatus` before buffer registration reports the UHD mode.** | sharpemu `src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` @ `b1ec286` (GPL-2.0-or-later) | Start-up resolution choice | S / low. Check what our host answers before registration. |

### Not recommended

- KytyPlus upstream since `2c8e00d7`: Vulkan only.
- AnyPS5's TF ring default (`State/src/Configuration.cpp:12-15`): a third-party claim, and moot for the second title (F248).
- AnyPS5's register defaults: possibly SDK-derived; excluded.
- AnyPS5 budgets and eviction: Vulkan staging only.
- KytyPS5 guest TSC patching: ideas only. It changes guest code.
- AnyPS5 `8b626e307`, the x87 control word 0x037f at thread start: Linux already starts threads with 0x037f, so a no-op
  for us (TODO(verify) on the box).
- AMPR occupancy and NetStatistics: still pending or synthetic, as Codex found.

## Files

- `inventory.py`: the NID-level inventory (Python 3, no dependencies). It takes the AnyPS5 tree, the patched KytyPlus
  tree, the stub list and an output path.
- `raw/anyps5-vs-host-by-library.tsv`: per-library exports, implemented, registered in our host, implemented but not in
  our host.
- `raw/title-stubs-vs-hosts.txt`: the second title's 197 link-time stub NIDs against both hosts.
