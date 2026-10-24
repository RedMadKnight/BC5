# Upstream and related projects, second pass: what else BC5's host can take

*Written 2026-10-24; the two S-sized ports of section 6 landed the same day as hunks in patch 0001 (F335). Follows `anyps5-review.md` (2026-10-19) and `related-projects-review.md` (2026-10-21) and does not repeat what they settled.*

**Question asked:** do other projects hold libraries or fixes worth importing or adapting into the host?

**Short answer:** the richest source is not a new project but our own upstream. KytyPlus merged KytyPS5's main branch on 2026-10-15/16 and now carries 328 commits under `src/libs`, `src/kernel` and `src/loader` that the box's `f266548` lacks, among them fixes that touch our open findings (F88, F206, F295, F326, Q14). Our patch 0001 applies only to `f266548`; on upstream HEAD 55 of its 83 files fail. Section 2 ranks the library commits worth hand-porting now and section 5 sizes the rebase. Among other projects the one new source is SharpEmu (GPL-2.0-or-later, C#), a behaviour reference that settles two of our `TODO(verify)` disagreements by majority. AnyPS5 added 3,520 library commits in five days; the ones for our titles are listed in section 3. ATRAC9 configurations 6–7 are closed (Q17 → F300/F301) and no project knows more than we do about them.

## 1. Licence check of the sources read in this pass

| Source | Licence (GitHub API, 2026-10-24) | Sony material | Verdict for us |
|---|---|---|---|
| Coder787-source/KytyPlus `2c8e00d7` (HEAD 2026-10-23) | GPL-2.0 | none seen | **Our host.** Any commit may be ported or the patch rebased. |
| KytyPS5/KytyPS5 `8291cfe` (2026-10-24) | GPL-2.0 | none seen | Upstream of KytyPlus; commits after 2026-10-16 are not yet in KytyPlus. Portable. |
| boykopovar/AnyPS5 `origin/main` 2026-10-25 | GPL-2.0-only | none seen (`anyps5-review.md` §1); the SDK-reference citations in some debt notes stay excluded | Portable with attribution, as before. |
| **sharpemu/sharpemu `299c907c`** (2026-10-24, 6,449 stars, C#) | **GPL-2.0-or-later** (`LICENSE.txt`, `REUSE.toml`: the tree is GPL-2.0-or-later, fonts Apache-2.0, LibAtrac9 MIT); `CONTRIBUTING.md` forbids Sony code, firmware, keys and asks for clean-room work | `grep -rI` for Sony markers: none | **Compatible**; C#, so a port is a re-implementation of behaviour. This also settles the caveat of `related-projects-review.md` §9: pcsx5's files "ported from SharpEmu" derive from GPL-2.0-or-later code, but pcsx5 itself still carries no attribution for them, so the rule to copy nothing from those pcsx5 files stands. |
| shadps4-emu/shadPS4 | GPL-2.0-or-later | — | PS4; unchanged role (NID names, AJM/Ngs2/SaveData analogues). |
| red-prig/fpPS4 | LGPL-2.1 | — | PS4, Pascal; reference only. |
| mattias800/prosper | **no licence** | — | Ideas only (D10). |
| iStark/PS5PCEM, SvenGDK/SharpProspero, drakmor/ampr_emu, 02dnot/Jelly5, sainsaji/PS5-Audio-Passthrough-Research, OpenOrbis toolchain | GPL-3.0 | — | **Not portable into a GPL-2.0-only tree**; read for behaviour, cite as documentation. |
| WujekFoliarz/duaLib, AlexAltea/orbital, Thealexbarney/LibAtrac9 | MIT | — | Portable; already used as cited references (F78, F200). |
| RPCSX/rpcsx | GPL-2.0 (last push 2026-06-29) | — | GPU-side reference only (D18); nothing new. |

## 2. KytyPlus upstream since `f266548`: library commits to hand-port

KytyPlus `f266548` is 2026-09-28. Upstream merged KytyPS5 main in `c4855877`, `1cfe6aad`, `c7646066`, `7c85d286` (2026-10-15/16) and reconciled in `44c4c44f`. Of the 263 commits under `src/libs` since then, these touch our titles' paths. "Ours" is KytyPlus `f266548` + patch 0001 as of `origin/main` `d3be2f4`. None of the commits below is an ancestor of `f266548` (`git merge-base --is-ancestor`), and only `a107d1e`, `199d0a9`, `b10bd53`, `62643c3`, `7b9997b`, `c045f08`, `5dec523` have been ported by hand so far (F76, F89, HANDOFF mentions).

| Upstream commit (KytyPlus unless noted) | What it does | Our state | Verdict | Effort |
|---|---|---|---|---|
| **KytyPS5 `b46eeb7`** (2026-10-21, not yet in KytyPlus) "stop AudioOut2 contexts from stalling each other": `sceAudioOut2ContextPush` submits outside the state mutex (`libAudio2.cpp`, +118 lines with tests) | F326: with a DualShock 4 the second title's pad-speaker port becomes a second blocking output on the default sink, written by the same audio thread as the main port | **Skip (parity, 2026-10-24):** our `audioout2_queue_context_audio` on `f266548` already releases the port mutex before `AudioOutOutputs`; the stall came with upstream `c86c8b4d`, which we do not carry (F335) | — |
| `41beda43` (2026-10-12) "fix APR completion loss in 768-byte read batches": write-address record size chosen by value (8/12/16 bytes), the completion writes sized `0x20` (`libAmpr.cpp`, tests) | F88 (AMPR `WaitOnAddress` table), F295 (async APR races, lost submissions). Ours used a fixed 0x20 for every write-address record and measure | **Ported 2026-10-24** as hunks (F335); unbuilt | S |
| `5a880808` (2026-10-08) "honor shared counter waits and completion writes": 256 counters shared by AMM and APR, the first 128 writable, compare operators 4/5/default with the sign trick | F88; ours no-ops `WaitOnCounter`/`WriteCounter` | **Port with the box build**: a new command kind in our rewritten APR engine (F335) | M |
| `259a40ab` (2026-10-13) "honor sparse AMM unmaps and restore failed GPU ranges": an AMM unmap accepts holes and fully unmapped ranges; out-of-range → `EINVAL`; failed GPU ranges restored (`kernel/memory.cpp`, `libAmpr.cpp`) | F206: our pool is a coalescing free list with per-mapping bookkeeping; a map replacing part of an old one returns its pages. Ours routes `AmmUnmap` to `KernelMunmap`; the hole rule is the piece to check | **Compare at the rebase** (F335) | S |
| `34a3eb6b` (2026-09-28) "recycle automatic backing through physical ownership" (`kernel/memory.cpp` +250) | The upstream answer to the leak F206 fixed in `libAmpr.cpp`. Different layer (kernel memory vs the library); ours is verified on the box (run 637) | Skip now; revisit at the rebase | — |
| `b65dc122` (2026-10-08) "track pad port ownership and reject duplicate opens": `PAD_ERROR_ALREADY_OPENED`, one standard port for the configured user | ASTRO read pad handle 2 beside its own; we masked it with `KYTY_BC5_LOGIN_USERS` (patch `libUserService.cpp`) | **Skip for now**: upstream's one-port model replaces KytyPlus's local-multiplayer handles, which our tree keeps (F335) | S |
| `c885da0a` (2026-10-04) "recognize 'Wireless Controller' audio endpoint on Linux" (`dualSenseHaptics.cpp`) | F69: our `audio.cpp` opens the first SDL output named `DualSense` (`KYTY_BC5_PAD_AUDIO_DEVICE` to choose). A Bluetooth DualSense enumerates as "Wireless Controller" | **Ported 2026-10-24** (`Bc5FindPadAudioDevice()`, four-channel check, F335); unbuilt | S |
| `e1be2ead` (2026-10-02) "DualSense haptics and controller speaker sound over Bluetooth" (`dualSenseBluetooth.cpp`, new) | Ours is USB only (F69, F79) | Port when a BT controller is used; not before | M |
| `3ff6606f` (2026-10-15) "rumble for non-PS5 controllers from haptic audio" | Same problem as our F214/F328/F330, solved independently; theirs rumbles through SDL on the host-input path | Cross-check only | — |
| `c86c8b4d` (2026-10-08) "mix AudioOut2 objects and apply port gains" (`libAudio2.cpp` +317): object ports mixed into the main output, per-port gains, ambisonics W normalisation | F108: ours folds the 12-channel main port to 8; port gains and object ports are untouched. Whether either title opens an object port is not in our traces | Check the port types in `KYTY_BC5_AUDIO_TRACE`, then decide | M |
| `0471c999` (2026-09-28) "AudioOut2 user capability queries" (`sceAudioOut2UserGetSupportedAttributes`) | Absent at `f266548` (the earlier review wrongly counted it as ours; it measured KytyPlus HEAD) | **Port** if either title imports it (unresolved-NID log) | S |
| `8dc9b9d5` (2026-09-21, via the merge) "persist save allocations for search and mount capacity queries", `569ec04d` (2026-09-23) "fix save metadata and timestamps" (`libSaveData.cpp` +218, `saveDataMountSlots.h`) | Our port 4 (F217, F319, F324) keeps blocks in a sidecar per save. Upstream solved the same thing; two mechanisms would collide at a rebase | **Unify at the rebase**; until then keep ours (verified on the box) | S |
| `05f92b64` (2026-09-28) "fix SaveDataDialog lockups": `Open` sets RUNNING, `UpdateStatus` reports RUNNING once then FINISHED | F205 did the same with the progress-bar rule on top | Parity | — |
| `45f55413` (2026-10-03) "keep sign-in dialogs active until user dismissal" through `systemOverlay.cpp` | Ours end at the first poll. Needs KytyPlus's overlay UI, which patch 0001 does not carry | Skip | — |
| `72e4989b`, `fb7ff7ec` (2026-10-05/06) trophies: `libTrophy.cpp` split out of `libNet.cpp`, UDS events mapped from `uds00.ucp`/`trophy00.ucp`, unlock toast and viewer | At `f266548` the 50 NpTrophy2/UDS functions live in `libNet.cpp` (the ports session found this, F216). The earlier review's "we have `libTrophy.cpp`, 1325 lines" described KytyPlus HEAD, not the box | Correction noted; the engine is the same code. Skip the UI | — |
| `3c62359e` (2026-10-08) trigger-effect state (ASTRO's L2/R2 punches, Playroom's gacha) | Ported as F78 | Parity | — |
| `e7ac2420` (2026-10-16) "load packaged system modules through the native module lifecycle", `210d4dcd` "track shared module load references" (`runtimeLinker.cpp`, 28 commits since `f266548`) | Q14: phasing the system-module pack out of the launchers | **Read** before Q14's design | M |
| `67d7db68` "agc: new abi", `aa3b2cd5` async rewind imports, `fbea51c6` `sceAgcSetNop`, `3ae5a9b7` branch target patching, 47 commits on `agc.cpp` | The HLE `libSceAgc` that Q14 would replace the LLE pair with | Read with Q14 | — |
| `70a475ec` (2026-10-02) audio drift fix | F76 held it back; F211 measured our clock at 1.000 | Skip | — |
| `28766a91` (2026-10-15) ATRAC9 discrete multichannel (config byte `0x30`, N mono decoders); indices 6–7 still mapped to mono/dual-mono | We decode 6–7 with vgmstream (F300/F301, confirmed at the pad); `0x30` streams unseen in our titles | Skip unless a `0x30` config appears in `KYTY_BC5_AJM_TRACE` | — |
| KytyPS5 `2944d12` (10-21) `sceAudioOutGetSystemState`; `05694ab` NGS2 PCM streaming; `ba0e93d` JpegDec/Enc; `415387f` multiple controllers; `0caf4a6`/`6b6274f`/`18e6747` NGS2 custom racks | Not on either title's path | Skip | — |
| KytyPS5 `227f12e`, `bf5dd62` (10-23) remove the PS4-era constant engine, marker NOPs and `EVENT_WRITE_EOP/EOS`; decode `RELEASE_MEM` from the driver's native packet | Cross-check for our PM4 policy tables (`docs/formats/agc.md`): what KytyPS5 now considers never emitted by a PS5 title | Read | — |

Not in the list: 27 commits on `network.cpp`, 23 on `libNet.cpp`, 14 on `avPlayer.cpp`, the Json2 ABIs, fonts, IME, the launcher. Neither title's open gaps are there.

## 3. AnyPS5 since `7f596df` (five days, 3,520 library commits)

Only the commits in our titles' libraries, non-merge, from `git log 7f596df..origin/main -- core/libs/prx/<lib>`:

| Commit | Content | Relevance |
|---|---|---|
| `99bdd60a6`, `2a0f25239`, `f0e63df88`, `b03a8ea18`, `71932c0a5` (10-20/22) NpManager | pending state callbacks also delivered from `sceNpCheckCallbackForLib`; game-presence callbacks accepted while signed out; `sceNpGetAccountLanguageA`, `GetParentalControlInfoA`, `GetAccountDateOfBirthA` → `SIGNED_OUT` without writing; `sceNpCheckPremium` → not a Plus member; request ids validated | Extends our port 2 (F215). Add when the second title's Np trace shows the calls. S |
| `36bc22728` (10-20) `sceNpTrophy2GetRewardIcon` | zeroes `size`, returns `ICON_FILE_NOT_FOUND` "following KytyPS5" | Our port 3 returns a not-supported error; align to this code. S |
| `a42182ef4` (10-21) | `sceNpTrophy2GetTrophyInfo` for an id not in the title's data → `NP_TROPHY2_ERROR_INVALID_TROPHY_ID` `0x8055390A` (KytyPS5's code) | Check ours does the same (KytyPS5 lineage, likely yes). — |
| `22cfc4b0b` (10-21) SaveDataDialog | `GetResult` writes an empty `dir_name` when nothing was selected | S; harmless hardening. |
| `56dfc1327`, `4b8f05e3e` (10-20/23) SystemService | integer parameters and `ParamGetString` errors/padding "as measured on a PS5" | **Citable hardware facts** for `libSystemService.cpp` (our patch logs which parameters the title asks for, exp 0046). Compare the values the second title reads. S |
| `30785885f`, `0d6ba22d9`, `a97a04f0c`, `023139d12`, `5a7ef7610` (10-20/21) AudioOut | three info calls return what the firmware returns; low-latency (`Lo`) calls served by the standard ones; mastering `InitEx` flags; mastering init tracked | Only if a title imports the `Lo`/mastering calls. — |
| the "as measured on a PS5" series (10-18 to 10-23): kernel kevent timers and filters (`27e37024a`), socket options, `sceKernelGetModuleInfoFromAddr`, thread names, event flags, Rtc zone names, Http URI handling | console measurements on firmware 13.60 | Citable; not on our titles' path today. Kevent timer re-adds (`27e37024a`) relate to `related-projects-review.md` §2 (timer events). — |

AnyPS5 also added `sceAudioOutGetSystemState` (`b0b7198b7`) and `scePadGetControllerType` (`63a266655`); neither is in our unresolved-NID logs.

## 4. SharpEmu as a behaviour reference

`src/SharpEmu.Libs/` by C# lines: Gpu 46,702, Kernel 24,973, VideoOut 24,419, Agc 12,147, Audio 5,574, Np 3,767, Network 3,200, Ampr 2,895, Ngs2 2,409, Pad 2,177, SaveData 2,097. It is an emulator (its own GPU and kernel), so only the library layer is comparable.

What it settles for us, by majority against the other sources:

- **Signed-out Np error.** `NpManagerExports.cs` uses `NpErrorSignedOut = 0x80550006`, as AnyPS5 does; KytyPlus's `libNp.cpp` answers `0x80550005`. Two independent sources against one; our port 2 kept KytyPlus's value with a `TODO(verify)`. Switch to `0x80550006` unless the second title's trace shows it checks the code. Still unmeasured on a console.
- **Save-data block size.** `SaveDataExports.cs`: `SaveDataBlockSize = 65536`, `SaveDataBlocksMin = 48`, `SaveDataBlocksMax = 16384`, free blocks from the directory size; AnyPS5 rounds files to 32 KiB blocks. Our port 4 followed AnyPS5. The two disagree, so the sidecar's free-block figure is a `TODO(verify)`; the slot list does not depend on it (F319).
- **State callbacks** delivered through `sceNpCheckCallback` and `sceNpCheckCallbackForLib`; reachability and premium callbacks accepted and never invoked. Same model as AnyPS5 and our port 2.

Its `docs/` are tooling notes (tracing, debugger, patches); no console measurements were found in the tree.

## 5. The rebase question

Facts, measured on 2026-10-24 in the scratchpad clone:

| | |
|---|---|
| Patch 0001 on KytyPlus `f266548` | applies cleanly (both the pre-ports and the current patch; identical trees except the ported files) |
| Patch 0001 on KytyPlus HEAD `2c8e00d7` | 55 of 83 files fail (`git apply --check`) |
| Upstream commits since `f266548` in files our patch modifies | `agc.cpp` 47, `bufferCache.cpp` 45, `main.cpp` 44, `graphicsRun.cpp` 38, `kernel/memory.cpp` 31, `runtimeLinker.cpp` 28, `window.cpp` 25, `audio.cpp` 23, `controller.cpp` 20, `libAmpr.cpp` 16, `ajm.cpp` 8, `libSaveData.cpp` 6 |
| Files our patch modifies that upstream removed | `host_gpu/vma.h`, `renderer/cache/gpuResourceManager.cpp`, `renderer/pipeline/asyncPipelineCompiler.cpp`, `libs/libGraphicsDriver.cpp` |

A rebase is a multi-day piece with the box needed for the build and the regression runs, and the graphics side (where the direct path hooks in) is where upstream moved most. Recommendation: keep `f266548` as the base for now and hand-port the S-sized library commits of section 2 as patch hunks (F76's method), each verified on the box; open the rebase as its own ADR once the second title's gameplay work settles, pinning a KytyPlus commit after `44c4c44f` so the 263 library commits arrive at once.

## 6. Ranked short list

1. **KytyPS5 `b46eeb7`** — `sceAudioOut2ContextPush` outside the state mutex. Target: F326's second blocking output with a DualShock 4. `src/libs/libAudio2.cpp` + its test. Port; S.
2. **KytyPlus `41beda43` + `5a880808`** — APR write-address record sizes and the shared counter compare table. Target: F88/F295. Compare against our `libAmpr.cpp` first (the record-size rule `value <= 3 ? 8 : value < 2^34 ? 12 : 16` is the thing to diff); S.
3. **KytyPlus `259a40ab`** — AMM unmap with holes and failed-range restore. Target: F206's pool. Compare, port the hole rule; S.
4. **KytyPlus `b65dc122` + `c885da0a`** — pad port ownership and the "Wireless Controller" endpoint name. Targets: ASTRO's second pad handle, a Bluetooth DualSense. Port; S.
5. **Np/trophy alignments from the majority** — `0x80550006` for signed-out (SharpEmu + AnyPS5), `ICON_FILE_NOT_FOUND` from `GetRewardIcon` (AnyPS5 `36bc22728`), the extra signed-out answers (AnyPS5 `f0e63df88`) when the second title's Np trace names them. Re-implement; S.

Decision for the maintainer: the rebase (section 5), yes or later.

## Sources

- KytyPlus `Coder787-source/KytyPlus` at `2c8e00d7` (full clone, 2026-10-24): `git log f266548..origin/HEAD -- src/libs src/kernel src/loader`, `git show` of the commits named; `git apply --check` of patch 0001 at `f266548` and `2c8e00d7`.
- KytyPS5 `KytyPS5/KytyPS5` at `8291cfe` (blobless clone): `git log --since=2026-10-14 -- src/libs`.
- AnyPS5 `boykopovar/AnyPS5` `7f596df..origin/main` (2026-10-25): `git log --no-merges -- core/libs/prx/<library>`.
- SharpEmu `sharpemu/sharpemu` at `299c907c` (shallow clone): `LICENSE.txt`, `REUSE.toml`, `CONTRIBUTING.md`, `src/SharpEmu.Libs/Np/NpManagerExports.cs`, `src/SharpEmu.Libs/SaveData/SaveDataExports.cs`.
- GitHub API `repos/<owner>/<name>` for licences, 2026-10-24.
- This repo: `docs/HANDOFF.md` F69, F76, F78, F88, F108, F205, F206, F211, F214–F217, F295, F300, F301, F319, F324, F326, F328, F330, Q14, Q16, Q17; `docs/ports/anyps5-review.md`, `docs/ports/related-projects-review.md`; `backend/kytyplus-patches/0001-bc5-lle-agc.patch` at `d3be2f4`.
