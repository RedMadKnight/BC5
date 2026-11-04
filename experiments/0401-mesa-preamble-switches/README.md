# 0401 — Two registers of Mesa's preamble on their own switches

**Status: two plays, both unplayable: both switches (slow from the start) and series c (memory thrash after 3 min); cause not separated. Series b adds the acb CS prefix, series c adds exp 0381's acb state restore, and series d puts series c on exp 0379's zero skip. All three are built. Series e adds exp 0402's NpCppWebApi V2, table catcher and param.json memory sizing, with the acb CS prefix off. Series e2 adds exp 0403's ACB_INHERIT. The shortcut "test 0401 CP+acb" runs series e2 with ACB_INHERIT=journal; it has not been played.** Written on 2026-11-02 on the top session's GO, on the maintainer's yes to a test build; the plays are the maintainer's.

**Question.** A static audit of Mesa's gfx10 start state against 1,347 captured buffers (notes `static-register-audit.md`) found five live registers that neither the title nor the host sets. The direct read needs root, so their values are unknown. Does writing Mesa's value change the hang classes or the frame rate? This experiment only builds the switches for two of the five.

**Setup.** One private normal binary, `~/bc5-work/exp0401/bin/kyty_emulator`: main 029e0d6b's `src/libs/bc5LleAgc.cpp` plus `mesa_preamble_prefix()` (`mkunit0401.py`), compiled with the shared build's own command and linked with the shared objects and archive (`build0401.py`). Shared binaries, archive, tree and launcher are pinned and only read. Private launcher `~/bc5-work/exp0401/play-pkg-0401.sh`: `play-pkg.sh` with its binary and two logs moved (`launcher0401.py`). Saves and settings stay the shared ones.

| Switch, default off | Register | Value | Packet | Source |
|---|---|---|---|---|
| `BC5_DIRECT_CP_COHER_START_DELAY=1` | CP_COHER_START_DELAY, uconfig 0x7b | 0x20 | `SET_UCONFIG_REG` `C0017900 0000007B 00000020` | Mesa 0866ae7 `src/amd/common/ac_cmdbuf.c:60`, `src/amd/registers/gfx10.json` |
| `BC5_DIRECT_SPI_REQ_CTRL_PS=1` | SPI_SHADER_REQ_CTRL_PS, SH 0x30 | 0x7 | `SET_SH_REG` `C0017600 00000030 00000007` | Mesa 0866ae7 `ac_cmdbuf.c:444-446`, `gfx10.json` |

Both go in `prefix_of()` right after `tf_ring_prefix()`, so every drawing job's prefix carries them, in the same packet form as the rings. Unset, empty and `0` are off (`bc5::env_on`). Each writes one journal line at the first prefix, on or off.

**Why the packet is allowed.** `CP_COHER_START_DELAY` sits in the uconfig range, and Mesa's `ac_pm4_set_reg` sends that range as plain `SET_UCONFIG_REG` from a user IB (`src/amd/common/ac_pm4.c:382-383`). It is not in Mesa's privileged list (`ac_pm4.c:34`, `is_privileged_reg`, which uses `COPY_DATA`). This is the same packet the prefix uses for `VGT_HS_OFFCHIP_PARAM` (F785), and `backend/src/dispatch_min.cpp:45` sends this very write. No `COPY_DATA` and no kernel path.

**How it will be read.** One binary takes all three switches by environment, since `BC5_DIRECT_ARGS_WB` is in the shared archive. They are not to run together: `ARGS_WB=all` and `CP_COHER_START_DELAY` may act on the same CP coherency path (for the second, an inference from its name, TODO(verify)), so a clean play would not say which helped; and `SPI_SHADER_REQ_CTRL_PS` changes PS wave scheduling, so it would blur the frame-rate cost of `ARGS_WB=all`. Both registers are global and keep their value until a reboot or a reset (the lesson of F780, R17), so an arm with a switch on must not be followed by an off control without a reboot. Order proposed: the read of the five registers first, since a register that already holds Mesa's value makes its switch a no-op; then `ARGS_WB=all` alone; then `CP_COHER_START_DELAY` alone; `SPI_SHADER_REQ_CTRL_PS` last, for frame rate only.

Journal, `gc/direct.log`, at the first prefix: `exp 0401: CP_COHER_START_DELAY ...` and `exp 0401: SPI_SHADER_REQ_CTRL_PS ...`, each `off` or its value. Log: `~/bc5-work/exp0401/play-last.log`.

**Result.** Built 2026-11-02 11:25, claim to release in slot 2026110211243533705, no emulator. Binary `174e768ec3a68c34be879ad57067819c` (shared objects of 4d2b1b1d, unit 9eec0a38, shared archive 75e30335). Launcher `c6b2d7fd`, 4 lines changed from `play-pkg.sh` 97835f88 (`raw/play-pkg-0401.diff`). The tree's unit equals main's patch 0001 unit (d18b4482). The real function, compiled with clang++ in the container, gave the right packets and lines for 7 of 7 settings (`raw/check0401.out`). 5 compile warnings, none in the new lines (3859-3870): deprecation and format and unused-variable warnings in older code. Shared binaries, archive, tree and launcher were unchanged at the end. `test0401.py` 15 of 15 on stand-ins, laptop. Not shown: that the prefix reaches the chip with these packets on a real run. No game ran.

**Play 1, both switches (2026-11-03 08:54–08:59, the maintainer, RT on).** Shortcut "BC5 emulator (test 0401)" (`shortcut0401.sh`, `BC5_DIRECT_ARGS_WB=0`). The journal `play-20261103-0854/gc/direct.log` shows both `exp 0401` lines on. The maintainer: "Straszne spowolnienie", then "Nie da się grać", from the start of play. The top session's numbers: t 170–256 at 19–30 flips/s; at t 256 a flip took 103 ms, of it GPU busy 3.2 ms, outside the direct path 75 ms, sync 15.9, hints 8.8. The launcher log is kept as `~/bc5-work/exp0401/play-last-20261103-0854-both.log`, since the next play overwrites `play-last.log`.

How it reads, as an inference, not shown: both registers act inside the GPU, where the play spent 3.2 ms of 103. `SPI_SHADER_REQ_CTRL_PS` 0x7 is `SOFT_GROUPING_EN` 1 with `NUMBER_OF_REQUESTS_PER_CU` 3 (field layout from `tools/bc5-agc/regdb/gfx10.json`), the value Mesa writes on every gfx10 context; what the fields do is not in any public AMD text read here (TODO(verify)). `CP_COHER_START_DELAY` holds a 6-bit `START_DELAY_COUNT`. Two confounds fit the time outside the direct path better. First, this build has no zero skip, unlike the morning's plays (exp 0379's bench: GTT 11,992 against 10,080 MiB, MemAvailable 480 against 2,490). Second, it was the first play after the 08:53 machine-down, so it ran with a cold page cache (F620). A slow play with the CP switch alone would not by itself point at the register; a reboot followed by the plain normal shortcut is the control. The registers latch, so after this play the box needs a reboot before any run with the switches off.

**Shortcut 2, `CP_COHER_START_DELAY` alone (2026-11-03 09:06).** On the top session's GO: "BC5 emulator (test 0401 CP)", `shortcut0401.sh cp`, md5 19651ddb4ca5e7a8baa93461124b46d1. Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0`. RT on in the shared settings. Replaced at 09:21 by series b's shortcut, unplayed.

**Series b: the acb CS prefix (2026-11-03, on the top session's GO, under the fixes-first rule).** A third switch, `BC5_DIRECT_ACB_CS_PREFIX=1`, default off. It is built into a second private binary in `~/bc5-work/exp0401b`, so the played 174e768e stays as it was.
- *Lead.* The 08:49 hang of that morning (exp 0379's zero-skip binary, notes `hangs-20261103-0849-0853.md`) stood in acb #432910. Its first four indirect dispatches launch 19612 × 1 × 1 before the acb sets any program. Its last dispatch sets 0x9098eb200 over the same arguments, so the head most likely expects the program the previous acb on its queue left (an inference). The stall sampler saw a dcb's program, 0x11d0287900, running those 19612 groups. Experiment 0195's CS prefix covers dcbs only.
- *What it does.* Every acb part the ring thread submits is applied to its guest queue's own tracker (`bc5::full_state`, keyed by `t_queue_idx`). A part that dispatches before it sets `COMPUTE_PGM_LO` (`cs_inherit_at`) gets that queue's tracked compute registers in front (`cs_prefix`: SH 0x204–0x3ff, the same runs as the dcb prefix), in the part's own chain segment. This covers the whole acb, a head that goes ahead of a wait, and a rest after one. Without the chain, the prefix goes as a job of its own just before. A queue with nothing tracked yet gets nothing. With the switch off nothing is tracked.
- *Journal.* `exp 0401: acb CS prefix on|off` at the first acb. Then `acb cs prefix (exp 0401): … queue Q acb part N dwords dispatches at A before it sets a program; the queue's program 0x…, D dwords in front (K such parts)` for the first 64 parts and every 1024th after.
- *Build.* 2026-11-03 09:18–09:19, claim to release in slot 2026110309184654684, no emulator. Binary `5b05ce9be5e4a4bf6352e270d28358d7` (shared objects of 4d2b1b1d, unit b1d96c71 = `mkunit0401.py --acb`, archive 75e30335). Launcher `01312b5b` (`raw/play-pkg-0401b.diff`). The same 5 warnings as the first build, none in the new lines. The function check gave 7 of 7 (`raw/check0401-b.out`). `test0401.py` 19 of 19 on stand-ins. The shared files and 174e768e were unchanged at the end. Not shown: that the prefix reaches the chip on a real run, or that it compiles to what the source says beyond the strings checked.
- *How a wrong program choice would show.* First in the journal: each prefixed part names the program put in front. For the 08:49 kind of acb the expected program is the 0x9098… family (0x9098eb200). A 0x11d0… program there, or 0 dwords, would mean the queue key or the tracking is wrong. On the GPU, a wrong program over thousands of groups gives what 08:49 gave: a dispatch that does not end (F403's CP state), or TCP/SQC faults at junk addresses (F443's family). A stale program address could also give an SQC instruction fetch fault, and a milder mismatch would show as wrong RT data in the reflections. The prefix also changes what a following dcb inherits in registers the acb does not set (F679's class).
- *Cost (estimates, not measured).* GPU: one `SET_SH_REG` run of the tracked compute registers, about 60 dwords (the dcb prefix's lines show 58), per acb part that inherits. How many such parts arrive per second is unknown; the journal counts them. CPU: with the switch on, the ring thread applies every acb part to its queue's tracker, as `piece_check` does for every dcb; acbs here are hundreds to a few thousand dwords. With the switch off, one static check per part.

**Shortcut 3, "BC5 emulator (test 0401 CP+acb)" (2026-11-03 09:21).** `shortcut0401.sh cpacb`, md5 300afa96869abd832a4703fbe02450bc. Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0`, launcher `exp0401b/play-pkg-0401.sh`, log `~/bc5-work/exp0401b/play-last.log`. It replaced the CP shortcut. The box had run since 08:53:34 when it was installed. `SPI_SHADER_REQ_CTRL_PS` still holds the 0x7 of play 1, and this shortcut does not write it, so a reboot must come before playing it. The 0401 confounds still hold for it (no zero skip, and a cold cache after the reboot). Moved to series c at 09:27, unplayed.

**Series c: series b plus exp 0381's acb state restore (2026-11-03, on the top session's GO, under the fixes-first rule).** A fourth switch, `BC5_DIRECT_ACB_STATE_RESTORE=1`, default off (`mkunit0401.py --acb-restore`, unit 29c88be3). It is built in `~/bc5-work/exp0401c`, so series b's 5b05ce9b stays in `exp0401b` as the rollback (`shortcut0401.sh cpacb-b`).
- *What it does.* This is exp 0381's restore (F679, F685: 3 of 3 starts clean with it, 3 of 3 faults without it). In front of a dcb that dispatches or calls an IB2 and gets no other prefix, it puts the graphics queue's tracked compute registers (SH 0x204–0x3ff without COMPUTE_VMID) through the CS prefix's path, in the dcb's own chain segment. `backend/include/bc5/acb_restore.hpp` is not on this build's include path, so its `wants()` and `runs()` are copied into the unit with the same behaviour. Two parts of exp 0381 are left out: its acb register census (`Touched`, journal only) and its `Stage::MapOnly` guard, a stage this unit lacks. `piece_check` keeps the graphics tracker current with the switch on.
- *Journal.* `exp 0401: acb state restore (exp 0381) on|off` once. Then `acb state restore (exp 0381): … dcb N dwords, R registers in D dwords (K such buffers)` for the first 16 dcbs and every 1024th after.
- *The two acb switches in one queue.* They do not overlap. The acb prefix acts on acb parts only and replays the guest compute queue's own tracker. The restore acts on dcbs only and replays the graphics tracker, which `piece_check` feeds from dcb, cc and hib buffers only. Neither tracker sees the other's buffers or prefixes, and a chain never holds acb and dcb segments together. On a dcb, the full draw prefix or exp 0195's CS prefix comes first, and both already carry the graphics tracker's compute registers. Left open: a register set through a table the tracker cannot read, and a dcb with neither a dispatch nor an IB2, which gets no restore.
- *Build.* 2026-11-03 09:26–09:27, claim to release in slot 2026110309262657606, no emulator. Binary `505b3ae35ac4510494e03e50fec6a43e` (shared objects of 4d2b1b1d, unit 29c88be3, archive 75e30335), launcher `d17996d3` (`raw/play-pkg-0401c.diff`), `raw/build-c.txt`, `raw/check0401-c.out` 7 of 7. The same 5 warnings as before, none in the new lines. `test0401.py` 20 of 20. The shared files, 174e768e and 5b05ce9b were unchanged at the end.

**Shortcut 3 on series c (2026-11-03 09:28).** `shortcut0401.sh cpacb`, md5 2fdf8e9f484a80f2d11fb3f6a69123d8, the same name "BC5 emulator (test 0401 CP+acb)". Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0`, launcher `exp0401c/play-pkg-0401.sh`, log `~/bc5-work/exp0401c/play-last.log`. Reboot before playing it, as above.

**Play 2, series c (2026-11-03 13:46, the maintainer, RT on).** Unplayable after 3 minutes. The top session's sampler showed the memory thrashing, with no GPU error in the kernel log. Available memory fell to ~250 MiB, swap rose from 0.7 to 2.9 GiB and GTT from 10.6 to 12.6 GiB. PSI memory "full" stalled about 40 % of the time, and the mount took 2.7M major faults. Every 0401 binary lacks exp 0379's zero skip, which exp 0388's memory-test build 902585e2 has.

**Series d: series c on the zero skip (2026-11-03 13:52, the top session's GO on the maintainer's "Tak, przebuduj").** The same three switches and edit (`mkunit0401.py --acb-restore`), applied to the unit of exp 0388's 902585e2 build instead of main's. That unit is main's d18b4482 plus `experiments/0388-job-arena-root/memory/z/patch-z-bc5LleAgc.diff` (`3a77e0acef307865d1cd524951060422`, git blob 321eed4 as the diff's index line says), and it includes `bc5/zero_skip.hpp` (`b29c66c4bc9d5bccb8aac233b3843414`, = `backend/include/bc5/zero_skip.hpp` on exp/0388-job-arena-root). `box0401.sh` (series d) reads both from `~/bc5-work/exp0388/z/src/src` under these pins and copies them into `exp0401d`. `build0401.py` puts the header's private directory first on the include path, as 0388's `build0389z.py` does. The edit adds the same lines to both units (unit 0f18cf30cb85843cdbe9d5df68909e3d). Every switch stays default-off on its own: the zero skip runs only when `BC5_DIRECT_ZERO_SKIP` names a list.
- *Build.* 2026-11-03 13:57–13:58, claim to release in slot 202611031357133761, no emulator. Binary `1545c4dee54528fc0480faf1b62df45e` (shared objects of 4d2b1b1d, unit 0f18cf30, archive 75e30335), launcher `7e4df66b96b3983b85733606895d2a01` (`raw/play-pkg-0401d.diff`, the same 4 lines), `raw/build-d.txt`, `raw/check0401-d.out` 7 of 7. The binary holds the zero skip's strings (`BC5_DIRECT_ZERO_SKIP`, `BC5_DIRECT_ZERO_SLICES`, `zero skip: list %s`) and `job-arena fix APPLIED`, as 902585e2 does. The same 5 warnings as series c, moved by the zero skip's lines, none in new code. `test0401.py` 22 of 22 on stand-ins (`python test0401.py <main unit> <work dir> <zero-skip unit>`). The shared files, 174e768e, 5b05ce9b, 505b3ae3, 902585e2 and its unit were unchanged at the end.

**Shortcut 3 on series d.** 2026-11-03 13:58, `shortcut0401.sh cpacb`, md5 0a1d81f619cc30596b979fb2fb7a7afd, the same name "BC5 emulator (test 0401 CP+acb)". Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_ZERO_SKIP=~/bc5-work/exp0388/m/zero-list-moving.txt`: the skip on as `play0389z.sh on` sets it, with the list pinned at 843f9fbc and `BC5_DIRECT_ZERO_SLICES` unset. RT on in the shared settings. Launcher `exp0401d/play-pkg-0401.sh`, log `~/bc5-work/exp0401d/play-last.log`. Rollback to series c's 505b3ae3 without the skip: `shortcut0401.sh cpacb-c`. The journal should show `zero skip: list …` and `… MiB in … runs skipped` per heap. If it says `not skipped`, the heap spans differ from the list's and the skip gives nothing (exp 0388's README). Reboot before playing, as the maintainer planned.

**Plays on series c and d (2026-11-03, the top session's numbers).** With the acb CS prefix on, three guest CPU crashes: one on 0401c and two on 0401d. The top then hand-edited the shortcut to series c with the prefix off (`desktop-before-e.bak`, md5 78296f80). That play ran 25 min, then hung the GFX ring at 16:32:33: GRBM 0xa2713028, and acb #1264478 dispatched program 0x11d0287900, the 08:49 class. Buffers: `~/bc5-data/captures/play-20261103-1607/gc`; devcoredump `20261103-163233-devcd1.txt`.

**Series e: three switches from exp 0402 (2026-11-03 16:4x, the top session's GO on the maintainer's "Buduj").** Items 1, 4 and 5 of exp 0402's Top 10, each behind its own switch, on series c's unit. Every 0401 switch is kept. The build adds three private units from the same tree, so it no longer touches `bc5LleAgc.cpp` alone.
- *1. NpCppWebApi SessionManager V2* (`KYTY_BC5_NP_SESSION_V2=1`, `mknp0401.py`, `libNpCppWebApi.cpp` 7c40b784 → 935fcc7e). It adds the ten exports exp 0328's port missed (F809), ported from AnyPS5 `core/libs/prx/libSceNpCppWebApi/Export.cpp` @ 4f41f4c37 (GPL-2.0-only; the note is in the unit).
  - Nine of them (the four `PlayerSessionsApi` requests and five factories) return 0x80552907 NOT_SIGNED_IN without writing their out-pointers.
  - `ParameterToJoinPlayerSessionAsPlayer::initialize` returns 0, as our port's other parameter `initialize`s do, and as AnyPS5 did at 27c88a8, where the port came from. AnyPS5 4f41f4c37's `InitializeParameterWithBody` belongs to a parameter-object model our port does not have. Here the same class's constructor and `terminate` are stubs, so that helper would read an uninitialised field. This departs from the GO's wording.
  - The ten are registered in `InitNpCppWebApi_1` only with the switch on. Off, the loader's stubs answer them, as before. One stderr line either way.
  - R32: `nid0401.py` (laptop) checks name → NID, 10 of 10. The gate `npgate0401.cpp` runs on the box after the link, linked with the emulator's own objects minus `main.cpp.o`. It runs `Libs::InitAll` into a real `SymbolDatabase`, resolves each NID by NID and by the title's import key to its function, and calls the ten. It runs with the switch on, 0 and unset. Notes: `np0401-notes.md`.
- *2. Submit-time table catcher* (`BC5_DIRECT_TABLE_CATCHER=1`, `mkunit0401.py --catcher`, unit 0d65c14d). F403 sub-class B: are the dims written after submit, or read too early? The idea is sharpemu 11506fc's; no code was taken from it.
  - *At submit:* `submit_now`'s walk hashes the arguments of each running DRAW_INDIRECT, DRAW_INDEX_INDIRECT, DISPATCH_INDIRECT (both forms) and multi-draw packet, at the SET_BASE 1 base it tracks, plus the LOAD_*_REG_INDEX (offset, value) tables.
  - *Later:* at the job's completion, and at a fence timeout before `timeout_probe`, it hashes them again and journals every change with the values then and now.
  - *Journal lines:* `exp 0401: table catcher on|off`, `table catcher (exp 0401): at completion|the timeout, submit #N kind op XX at Q: … changed since submit: was … now …`, a line per timeout, and a 64k-check summary.
  - *Not covered:* IB2 contents and the offset-and-size table format.
- *3. Direct/flexible sizing from param.json* (`KYTY_BC5_MEMORY_FROM_PARAM=1`, `mkmem0401.py`: `memory.cpp` f6154692 → 43713ef6, `systemContent.cpp` 7121c22c → 4e33b30a, `systemContent.h` 8890c158 → 2b2b21eb, first on the include path). This follows KytyPS5 09753bf (GPL-2.0).
  - Total = 12800 − 64 MiB cache − the page-table memory past 64 MiB each for CPU, GPU and AMM (param.json `kernel.cpuPageTableSize`, `kernel.gpuPageTableSize`, `amm.pagetableMemorySizeInMib`). `KYTY_GUEST_MEMORY_MB` (13824 in `bc5-run.env`) and the host cap are ignored.
  - Flexible stays param.json's 276 MiB (F194), and direct is the rest. If the title sets no table sizes, that is 12,460 MiB of direct memory against today's 13,548.
  - Left out: 0a14091's charge of module segments to flexible memory, and the `KernelGetPageTableStats` totals.
  - Journal: `[bc5] exp 0401: memory from param.json on|off: total …, flexible …, direct … (param.json: …)` on stderr at memory init.
  - Risk: a title that sizes its heaps from direct memory may fail an allocation, as ASTRO BOT did on AnyPS5's 12 GiB (reverted in 97f1d41a2). Less direct memory lowers pinned GTT only if the pinned heaps shrink with it. Notes: `mem0401-notes.md`.
- *Build.* 2026-11-03 16:49–17:0x, claim to release in slot 202611031649155497, no emulator. The first build stopped on `memory.cpp`'s same-directory include (`memoryAddressSpace.inc`, now copied beside the private unit under its pin 44586b1e). Binary `852d9b089558d4c845ba7005af888b96` (shared objects of 4d2b1b1d, archive 75e30335; units bc5LleAgc 0d65c14d, libNpCppWebApi 935fcc7e, memory 43713ef6, systemContent 4e33b30a + header 2b2b21eb), launcher `b9774734b4ae9411afb768197d3f59c8` (`raw/play-pkg-0401e.diff`), `raw/build-e.txt`, `raw/check0401-e.out` 7 of 7. R32 gate: `raw/npgate-e-on.out` 10 of 10 registered as their functions, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; `-off` and `-unset` 10 of 10 unregistered. 11 warnings over the four units, all in old code (deprecations, format, unused names; `libNpCppWebApi.cpp` lines 50 and 62). `test0401.py` 24 of 24 on stand-ins (`python test0401.py <main unit> <work dir> <zero-skip unit> <tree root>`). The shared files and every earlier 0401 binary were unchanged at the end.

**Shortcut 3 on series e.** 2026-11-03 17:0x, `shortcut0401.sh cpacb`, md5 ceb3220b3cff940b031b16e9da7c5340, the same name. Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=1`, launcher `exp0401e/play-pkg-0401.sh`, log `~/bc5-work/exp0401e/play-last.log`. None of these keys is in `bc5-run.env`, so the launcher does not override them. RT on. Before it, the top's hand edit (series c, prefix 0, md5 78296f80) was kept as `exp0401e/desktop-before-e.bak`; `shortcut0401.sh cpacb-c0` makes it again (the rollback to 505b3ae3).

**Series e2: series e plus exp 0403's ACB_INHERIT (2026-11-03 17:0x, the top session's addition under the fixes-first rule).** A seventh switch, `BC5_DIRECT_ACB_INHERIT=journal|wave|skip`, default off (`mkunit0401.py --inherit`, unit 73e8e4e0), from exp 0403's Verdict and "Proposed switch" (bd3744c5). Series e had stopped on its first build, so it was finished as it was; e2 is a separate build in `exp0401e2`, and e stays as the rollback (`shortcut0401.sh cpacb-e`).
- *State kept.* Per guest queue (`t_queue_idx`), the compute registers (`cs_prefix`, SH 0x204–0x3ff) and USER_DATA_0..3 at the queue's last wave32 and last wave64 dispatch. The wave mode is the initiator's CS_W32_EN, bit 15 (exp 0403 §2; TODO(verify) in the register database). The initiator is the last dword of each dispatch packet. At most two snapshots are taken per part. Tracking runs where exp 0401 tracks: after each head segment, and after each ring part.
- *`journal`.* No submission changes. Each part that dispatches before it sets a program gets a journal line (first 64, then every 1024th): `acb inherit (exp 0403): … queue Q head|rest part N dwords from offset F: K inheriting dispatches, the first at A, initiator 0x…, (W32|W64); the queue's last W32 program … ud0-3 …, last W64 … ud0-3 …; previous parts …; <action>, D dwords in front`.
- *Ring census.* Every non-IB type-3 packet on a guest ring slice is counted per queue: by opcode, and for SET_SH_REG by first register and count. The counts are journaled at the first slice and every 1024th, as `acb inherit census (exp 0403): queue Q after S ring slices, non-IB type-3 packets: op XX xN … sh 0xRRR+C xN`. A `sh 0x20c` entry there would mean the ring sets programs that our GPU never sees (exp 0403's difference 1).
- *`wave`.* A head (offset 0 in its title buffer) gets the slot with its dispatch's wave mode in front. This uses exp 0401's prefix path, in its own chain segment. With no such slot, it is skipped. A rest or segment is left as it is, since its head is replayed by `state_prefix`.
- *`skip`.* A head's inheriting dispatches (each dispatch before the part's first packet that may set COMPUTE_PGM_LO, by `cs_inherit_at`'s rule) are recorded by title address. `submit_now`'s filter drops them through `drop_offsets`, as `BC5_DIRECT_SKIP_PGM` drops, so the packet becomes a NOP of the same length. Each drop is journaled.
- *Exclusion.* With `BC5_DIRECT_ACB_CS_PREFIX` set too, ACB_INHERIT wins. The acb CS prefix stays off, and a line says so.
- *Build.* 2026-11-03 17:03–17:1x, claim to release in slot 2026110317031110672, no emulator. Binary `35ff82ebc8530e4bcc4ea66ccf43accf` (shared objects of 4d2b1b1d, archive 75e30335; units bc5LleAgc 73e8e4e0, libNpCppWebApi 935fcc7e, memory 43713ef6, systemContent 4e33b30a + header 2b2b21eb), launcher `fbac41eef200b36c440ddc1ef5322783` (`raw/play-pkg-0401e2.diff`), `raw/build-e2.txt`, `raw/check0401-e2.out` 7 of 7, R32 gate `raw/npgate-e2-{on,off,unset}.out` as in e. The 11 warnings are series e's, with their line numbers moved, and none falls in new code. `test0401.py` 25 of 25. The shared files and every earlier 0401 binary (852d9b08 included) were unchanged at the end.

**Review (Codex, 2026-11-03, after 14011b76): the W32 slot can hold an inherited program.** `acb_inherit_track` (`mkunit0401.py:413`) puts a dispatch's state into the W32 or W64 slot by its initiator bit alone. That includes a dispatch that set no program in its own part. Counter-example: part A sets program P and dispatches W64; part B sets only USER_DATA_0 and dispatches W32. The tracker still holds P, so B writes P into the W32 slot. The 08:49-type head is exactly such a part, so every inheriting W32 head fills the W32 slot with the program it inherited. Reading e2's journal: "last W32 program" means the state at the queue's last dispatch that asked for W32. It is not a confirmed wave32 program (inferred from the code, not observed). `wave` would replay such a slot, so it stays unset, as before. Proposed fix (series e3, not built): promote a slot only at a dispatch that comes after the part's first possible program write, by `cs_inherit_at`'s rule, and journal where each slot came from. A CPU case A→B on the box tests it.

**Shortcut 3 on series e2.** 2026-11-03 17:1x, `shortcut0401.sh cpacb`, md5 de0da78ec49da091b69ebb269a44448c, the same name. Env `BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=1`, launcher `exp0401e2/play-pkg-0401.sh`, log `~/bc5-work/exp0401e2/play-last.log`. RT on. `wave` and `skip` are built but not set. Rollbacks: `cpacb-e` (series e, 852d9b08) and `cpacb-c0` (505b3ae3, prefix off).

**Play on series e2 (2026-11-03 17:55:24–17:58:00, the maintainer, RT on; read-only analysis on the top session's GO).** The maintainer: "Gra była baaardzo bardzo płynna. Grało się świetnie ale krótko." It ended in the host's own fatal, "AMM virtual-memory unmap is unsupported: addr=0x0000008639a20000" (`exp0401e2/play-last.log:2377`), not a GPU hang.
- *Thread.* Load base 0x5602f5193000, from the job-arena hook line (log line 21, `bc5_job_arena_owner_help` +0x8ad950). `llvm-symbolizer` on `exp0401e2/bin` gives `AprWorkerThread` (libAmpr.cpp:2299) → `RunOrderedAprCommands` (:1960) → `ReadHostFileToGuest` (:2515, the `memcpy` into the guest) → libc → the signal handler → `KernelHandleReservedRangeAccessViolation` (memory.cpp:3718) → EXIT. This is F206's signature: the APR read worker copies a file into an AMM page with no mapping.
- *The memory switch, likely implicated (inference).* It gave total 12704 MiB, flexible 276, direct 12428. param.json sets cpu 64, gpu 64 and amm 96 MiB of tables, so the overhead is 32 MiB; 12736 assumed none. Automatic AMM maps take their pages from direct memory [0, `KernelGetDirectMemorySize()`) (`libAmpr.cpp:1642`), and F206 says the pool is the title's 3 GiB plus the host's direct memory. Exp 0288: the title reserves 12,162 MiB of the 13,824 offered. With 1,120 MiB less direct memory, the pool's headroom shrinks by that much. A refused automatic map returns EAGAIN, the rest of its map-only buffer is dropped, and the APR reads that follow hit reserved AMM pages, which is F206's chain. The refusal is traced only with `KYTY_BC5_AMM_TRACE` (stderr), which was off, so this log cannot show it. The AMM window is the title's own reservation, and the switch does not move it. At about 150 s the play had made 21,234 maps against 28,810 in the 16:07 play: consistent with refused maps, or with another route (R21). Check: one play with the switch on and `KYTY_BC5_AMM_TRACE=1`. The trace should show `amm trace: auto pool exhausted` before the fatal.
- *Smoothness, not from pinning.* Over the first 155 s: 28.8 flips/s and 38 seconds with a gap over 100 ms. The 16:07 play (505b3ae3, prefix 0) had 22.2 flips/s and 61 such seconds over the same span; series d had 17.8 and 75. Pinned memory at about 150 s was 11,588 MiB here against 11,710 at 16:07, so only about 120 MiB less, not 1.1 GiB. The fewer maps may have saved mapping work, possibly because maps were refused, which would also leave content unloaded; the route and the cache differ too. The journal cannot pin the cause.
- *The other switches.* No `acb inherit (exp 0403)` line, so no part inherited a program in 155 s. The ring census on queue 0 found no non-IB type-3 packets. The table catcher logged about 578k changes, mostly acb op 16 tables (the top session's count).

**Later plays on e2 (2026-11-03, the top session's numbers).**
- *18:14.* Memory switch on, with `KYTY_BC5_AMM_TRACE=1`. The AMM fatal came at t≈145 s, right after `amm trace: auto pool exhausted: map of 0x4000000 bytes refused, 9653 maps hold the pool, 0xd444000 free`. This confirms the inference above. The top session then set `KYTY_BC5_MEMORY_FROM_PARAM=0` in the shortcut by hand (backup `exp0401e2/desktop-mem1.bak`). `shortcut0401.sh cpacb` now writes it the same way.
- *18:04.* A freeze at t≈184 s. The GPU was idle with every submission done, while game-main and Render ran at 100 % in user space. There are no stacks.
- *18:16.* Memory switch off. The maintainer called it better. It ended at t≈681 s in a guest NULL read at eboot+0x3a05f35 (exit 65), after the frame rate collapsed in its last seconds. No memory sampler ran.
- The maintainer turned JobArenaFix off in the F2 menu. That is in the shared `input.cfg` and is his choice.

**Series e3: e2 with exp 0403's queue mode, plus a memory line (2026-11-03 18:3x–18:5x, the top session's GO; built, not installed).** The shortcut stays on e2 until the maintainer says otherwise.
- *First draft, set aside.* The first e3 fixed e2's W32/W64 slots (`--inherit2`): only a dispatch after its own part's program write filled a slot. It was built as binary 8b4efb9b (unit 989ca24b, its CPU test 12 of 12, `raw/build-e3w.txt`, `raw/inh0401-e3w.out`). The top session then replaced the design with exp 0403's addendum (a423f761), which withdraws the wave32 claim and the per-wave slots. The draft stays on the box as `exp0401e3w`, unused.
- *Second build, set aside.* The queue design below, with MISMATCH and dropping on fallback, was built as binary 57de16ee (unit d3869b92, its CPU test 13 of 13, `raw/build-e3q.txt`, `raw/inh0401-e3q.out`). Codex's second review and the top session's fallback decision followed, so it stays on the box as `exp0401e3q`, unused.
- *ACB_INHERIT, queue design* (`mkunit0401.py --inherit3`; e2's `--inherit` still gives 73e8e4e0). The modes are `off|journal|queue|skip`, and `wave` is gone.
  - *Tracking, in every mode.* Per guest queue: the live compute state, a `full_state::Tracker` applied over all of the queue's parts.
  - *Program provenance.* Per program address (COMPUTE_PGM_LO/HI): the wave modes the title used with it, counted only at dispatches after a certain program write in the same part. That is `inherit_scan`, by `cs_inherit_at`'s packets. An unreadable table or an IB2 that comes after the write voids it until the next certain write (Codex's second review, point 3). Each program also records the queue and part that last did so. `inherit_scan` also returns what each part leaves behind: a certain program, a voided one, or nothing that touches the program. That gives the queue a `known` flag.
  - *Ring.* Per physical ring: the guest queue of its last tracked part. This is exp 0403's difference 3.
  - *`journal`.* No submission changes. Each inheriting part's line gives: the part's address; its first inheriting dispatch and initiator; the queue's live program and USER_DATA_0..3; that program's provenance ("bound last by queue Q part P" or "never bound in a part of its own") and its own W32/W64 counts; `UNSEEN` when no dispatch of the title's own with that program in this wave mode has been seen (not observed: it is evidence of neither an illegal shader nor a wrong order, Codex's point 2); whether the physical ring's last tracked part came from the same queue; and the previous three parts with their first two dwords (a check that the driver's 2-dword IB is a NOP). The line also gives the running counts: prefixed, fallback ring (no program, voided, unseen), skip-mode heads, and dispatches dropped. The ring census stays.
  - *`queue`.* A head (offset 0) gets the queue's live state in front, through `cs_prefix` and exp 0401's prefix path, but on heads only. That needs a known state: a tracked program from a certain write that nothing has voided since, seen with the dispatch's wave mode. Otherwise nothing goes in front and the part keeps today's behaviour, the ring's state. The line then says `unknown, fallback ring` with its reason, and fallbacks are counted apart from prefixes. This is the top session's decision of 2026-11-03: queue mode never drops, so a clean play in it cannot come from silent drops.
  - *`skip`.* As in e2, and the only mode that drops.
  - *Rests and segments* are left alone in every mode.
  - *CPU test.* `inherit_scan` and the memory line's parsing are pure, and the same texts go to `inherit_scan.inc` and `memline_parse.inc`. `inh0401.cpp` runs them on the box over 25 cases. Scan cases: Codex's A→B (B's dispatch is not bound), the 08:49 head (4 unbound W32, then its own W64), an 18:16 wave64 head, ranges over and past 0x20c, readable and unreadable pair tables, the offset format, an IB2, and a part cut mid-packet, each with its end state. Point 3's cases: SET_PGM then an IB2 or an unreadable table, then a dispatch (not bound); SET_PGM, IB2, SET_PGM, dispatch (bound); a bound dispatch, an IB2, then an unbound one. Point 1's memory-line cases are listed below.
- *Memory line* (`--memline`, `BC5_DIRECT_MEM_LINE`, on unless 0). Every 10 s a background thread writes `memory (exp 0401): t … s: available … MiB, swap used … MiB, psi some … full … (avg10, %), full total … ms, gtt … of … MiB`. It reads `/proc/meminfo`, `/proc/pressure/memory` and amdgpu's `mem_info_gtt_used`/`_total`, once each, with no smaps walk. The min journal is flushed after each line, so the line before a crash survives. A value whose file, key or number cannot be read is printed as `unknown`, never 0, so a missing file cannot look like memory at its floor (Codex's point 1). The CPU test checks every file read; no meminfo; no MemAvailable key (a decoy `MemAvailableX:`); no SwapFree; no PSI `full` line; no PSI file; no GTT total; a GTT value that is not a number.
- *Build.* 2026-11-03 18:55–19:0x, claim to release in slot 20261103185545273314, no emulator. Binary `c059c71fa37c0f81db19310cb1197be4` (shared objects of 4d2b1b1d, archive 75e30335; units bc5LleAgc d3b7f9b0, libNpCppWebApi 935fcc7e, memory 43713ef6, systemContent 4e33b30a + header 2b2b21eb), launcher `2995f018116521816780f1aa73d58c38` (`raw/play-pkg-0401e3.diff`), `raw/build-e3.txt`, `raw/check0401-e3.out` 7 of 7, CPU test `raw/inh0401-e3.out` 25 of 25, R32 gate `raw/npgate-e3-{on,off,unset}.out` as in e. The same 11 warnings as e2, none in new code. `test0401.py` 26 of 26. Built only: `shortcut0401.sh cpacb-e3` would install it (ACB_INHERIT=journal, memory switch off), and the shortcut stays on e2. The shared files and every earlier 0401 binary were unchanged at the end.

**Series e4: e3 plus exp 0402's items 3, 9, 2, 7 and 10, where they were missing (2026-11-03 22:3x, the top session's GO on the maintainer's "buduj dodatkowo 3,9,2,7,10 o ile sami tego już nie poprawialiśmy"; built, not installed).** Each item was first compared with our effective code: the box tree, KytyPlus f266548 plus patch 0001. Each missing part is ported on its own script, unit and switch, default off. Four laptop agents did the comparisons and ports, one item each (7 and 10 together); their notes hold the evidence, file:line in our tree. The e4 launcher also keeps each run's log (the top session's line). The same line went into e2's launcher, f23acf27.
- *Item 3, rwlock/condvar (AnyPS5 4ed0f9f91, 372f0f6c6, 83b1015c4, 45a8b80a5, 16375634e): one ported, four not applicable* (`pth0401-notes.md`). Four of the commits are in AnyPS5's `_umtx_op` (SyncOnAddress.cpp, not Pthread), which this tree does not have.
  - Waiter-bit races (4ed0f9f91, 372f0f6c6, 83b1015c4): cannot happen here. One mutex per lock guards all of its state (pthread.cpp:2562-2593, 2744-2756), and there is no waiter bit.
  - An unlock that throws (4ed0f9f91 b): cannot happen. `NativeMutexUnlock` returns codes (1467-1495).
  - The relock spin (16375634e): cannot happen. Our relock does not spin (1373, 1958).
  - Missing: 45a8b80a5, `URWLOCK_PREFER_READER`. A thread that holds a read lock on any rwlock reads past waiting writers, as FreeBSD 11.4 libthr's `rdlock_count` does. Ours allowed it only for the same lock (2587-2593, 2680-2685), so two readers, each waiting behind the other lock's writer, could deadlock. Ported in adapted form, without AnyPS5's code, as `KYTY_BC5_PTHREAD_FIXES` (`mkpth0401.py`, pthread.cpp 11cef59e → 0363847b).
  - CPU stress test `pth0401.cpp`: 10 cases with real threads and a 50 s watchdog, switch on and off.
  - Note: none of the five explains the 18:04 freeze. A lost wake-up here sleeps in 10 ms polls; it does not spin at 100 % user CPU.
- *The maintainer's rule change (2026-11-03 23:0x), applied to every item below:* a port is judged for any title, not for our two. The only valid reasons to skip one are "we already match (file:line)" and "licence or provenance not acceptable". The first verdicts on items 7, 9 and 10 said "not applicable" for our titles. Those were reopened, and the missing parts were ported behind switches.
- *Item 9, SaveData (AnyPS5 0d0abe09c, bc6b4d76f; KytyPS5 4b0282e, dfec14a): three switches* (`sav0401-notes.md`, which records both verdicts).
  - Missing: dfec14a, mount result left alone on a refused mount. `*mount_result = {}` ran before every refusal (625). Ported as `KYTY_BC5_SAVEDATA_FIXES`.
  - Event callback (AnyPS5 0d0abe09c, bc6b4d76f). Our host exports neither `sceSaveDataRegisterEventCallback` (`hsKd5c21sQc`) nor `sceSaveDataUnregisterEventCallback` (`v-AK1AxQhS0`). A title that imports them gets the loader's return-0 stub: OK, and never a callback. The two fixes need the feature they fix, so the feature was ported with them: both NIDs, and the delivery thread started at the first successful registration of an initialization. Behind `KYTY_BC5_SAVEDATA_EVENT_CB`, and registered only with it on. The second title polls GetEventResult instead (F188, F189).
  - Sorted search (4b0282e). The order already matches (F217, libSaveData.cpp:559-582). Of the key definitions, the mtime key, from the files' write times, is ported as `KYTY_BC5_SAVEDATA_SORT`. Free blocks and the missing blocks record are kept: ours matches shadPS4 and AnyPS5.
  - One script, `mksav0401.py`: libSaveData.cpp d6e9c37f → 04f4c5bb.
  - CPU test `sav0401.cpp`, one program run once per switch: 20 checks (FIXES, SORT), 33 with EVENT_CB. It runs in a fresh directory under `exp0401e4` with `KYTY_BC5_SAVEDATA_DIR` unset, away from any save.
- *Item 2, AudioOut2 (AnyPS5 c34ab0258, 11f217b14, 42beeaa46, b87075aad, ccaac6602): three ported, two not needed* (`aud0401-notes.md`).
  - PCM taken at the set (c34ab0258): missing for the bed ports.
  - Silence for a buffer not set again (11f217b14): missing.
  - Blocking push returns once there is room (42beeaa46): missing on the timer path only. The device path already waits (audio.cpp:829-869).
  - Reopen of the default output (b87075aad): not applicable on the box, which uses SDL 2.33 with PipeWire.
  - Reopen of the controller card (ccaac6602): already covered by exp 0372's PadRouteStep (audio.cpp:908-945).
  - The three missing parts are ported as `KYTY_BC5_AUDIO_FIXES`: any value turns all three on, and a list such as `set,room` picks parts (`mkaud0401.py`, libAudio2.cpp fb44443e → 7a1914c8). audio.cpp and pad_audio_route.hpp are unchanged, and the `exp 0372` counts are the same.
  - CPU test `aud0401.cpp`: 25 checks, no sound device.
  - **Before the maintainer plays it: exp 0372's replug check.** The title's vibration port is an AudioOut2 port, so "set" and "silence" change what reaches the actuators. Software check: P1 and P2 of `s6n0372.sh`/`replug0372.sh` on the e4 binary. Then the physical replug and a DS4. A `silence` line that names type 0x6 means the haptics are cut; then use `set,room`.
- *Item 7, AMM PRT and the other AMM/AMPR commands (AnyPS5 4f41f4c3, `Apr.cpp`, PRT commits e3b5192cb, 79fc99774, 37881a5da): ported, 26 NIDs behind three switches* (`amm0401-notes.md`; the first verdict, `prtvo0401-notes.md`, said not applicable because our host registers no PRT command, libAmpr.cpp:3648-3741, and the second title imports none).
  - `KYTY_BC5_AMM_PRT_CMDS`: MapAsPrt, AllocatePaForPrt (with rollback), RemapIntoPrt, UnmapToPrt and their two measures. Zero pages are read-only on the CPU, after 37881a5da.
  - `KYTY_BC5_AMM_EXTRA_CMDS`: Remap, MultiMap, ModifyProtect, ModifyMtypeProtect, each with its `WithGpuMaskId` form, and their 8 measures.
  - `KYTY_BC5_AMPR_WAITS`: `sceAmprCommandBufferWaitOnAddress` and `…WaitOnCounter` with their measures, on real counters.
  - One script, `mkamm0401.py`: libAmpr.cpp a0e2ff6e → 0a1762f6, memory.cpp unchanged. The NIDs are registered only with their switch on.
  - Not ported: libkernel's `sceKernelWrite*Command` family. Our host has no executor for byte commands and no indirect-buffer submit for them, so it is a separate decision.
  - Note: with PRT or EXTRA on, every map goes into the page table, about 60 MB at 12 GiB.
  - CPU test `amm0401.cpp`, the three switches set together: 317 checks on, 63 off.
  - Still noted, not built: `scratch_fill` should leave the PRT window out (bc5LleAgc.cpp:2229-2324).
- *Item 10, VideoOutGetOutputStatus (sharpemu b1ec286 `VideoOutExports.cs:505-562`, AnyPS5): ported as `KYTY_BC5_VIDEOOUT_STATUS`* (`vo0401-notes.md`, which supersedes `prtvo0401-notes.md` for this item). The answer is resolution 2 (UHD) before registration. After registration it follows AnyPS5: the display setting, which is measured. sharpemu derives it from the buffer size, which is not measured. The other fields already match. One script, `mkvo0401.py`: videoOut.cpp f848f5c6 → 3fa490f7. CPU test `vo0401.cpp`: 27 checks. Exp 0291 (F354) had already run the UHD answer on the second title: the same buffers and the same rate.
- *Exp 0404's two switches (the top session's addition, 2026-11-03 23:4x).* `mkfl0401.py` turns e3's unit d3b7f9b0 into df12bb2d, plus `fl_scan.inc` for the CPU test (`fl0401-notes.md`).
  - `BC5_DIRECT_FL_CRUMBS=1` is a catcher. Every draw of a fast-launch dcb gets issued/done slots and a 64-entry ring in the GDS shadow at +0x8000. At a fence timeout the probe names the draw that did not finish, with the inputs the CP copied for it. The crumbs add end-of-pipe load, so a clean play with them on is weak evidence.
  - `BC5_DIRECT_FL_SKIP_ES=<list>` is a diagnostic. It takes `SPI_SHADER_PGM_LO_ES` values (0x11d00f85 is the program at 0x11d00f8500) and drops the draws that are certainly fast-launch with a listed ES.
  - CPU test `fl0401.cpp`: 74 cases.
- *Build.* 2026-11-04 00:53–00:5x, claim to release in one slot, no emulator. Binary `d6f11b10df3ba379922730502e576148` (shared objects of 4d2b1b1d, archive 75e30335). Units: bc5LleAgc df12bb2d, libNpCppWebApi 935fcc7e, memory 43713ef6, systemContent 4e33b30a + header 2b2b21eb, libSaveData 04f4c5bb, pthread 0363847b, libAudio2 7a1914c8, videoOut 3fa490f7, libAmpr 0a1762f6. Launcher `69e565be`, which keeps each run's log. Records: `raw/e4/` (build, the function check, every CPU test's output).
  - Every CPU test passed on the box, each with its switch 1, 0 and unset: fl0401 74/74, inh0401 25/25, sav0401 20/20, savcb 33/33, savsort 20/20, pth0401 10/10, aud0401 25/25, vo0401 27/27, amm0401 317/317 on and 63/63 off. npgate 10/10 on, off and unset; the function check 7 of 7.
  - 22 warnings, all in code that was already in the tree: the newly compiled units' own lines, such as libAmpr.cpp's format-extra-args and videoOut.cpp's `Bc5VideoOutEventName`. None is in new lines.
  - `test0401.py` 27 of 27 on stand-ins.
  - Built only. The shortcut stays on e2, and the maintainer said not to install e4 (2026-11-04 00:0x). e4a (`fe4ea308`, the first e4 without items 7 and 10 and the reopened item 9) stays on the box as `exp0401e4a`, unused.
- *Night tests of e4 (2026-11-04 00:57–02:14, unattended).* The maintainer approved them at 00:1x: "przetestuj też buildy z portami i przełącznikami z researchu". The top session gave the list.
  - *How.* Each arm ran under its own atomic lock line, one after another:
    - `run0401t.sh` (box, md5 1eee506a), driven by `night0401.sh` (laptop), from `raw/night-arms.txt`;
    - a private copy of input.cfg with RT on and JobArenaFix on;
    - a derived launcher with its own log, and a private working directory with a fresh snapshot of the live saves (`4b6b1ea5`, LC_ALL=C; the live saves were only compared, and they were unchanged after every arm);
    - exp 0401e3's freeze watcher and exp 0330's memory sampler;
    - the kernel log streamed to the laptop.
  - *The route.* Gated on the journal's frame profile lines: cross at the start screen, then down ×3 and cross for slot 4, then Continue and the load, then G (gameplay). A start check ends at the save-slot list.
  - *The shortcut's switches.* Every arm had them: `CP_COHER_START_DELAY=1`, `ACB_CS_PREFIX=0`, `ACB_INHERIT=journal`, `ACB_STATE_RESTORE=1`, `SPI_REQ_CTRL_PS=0`, `ARGS_WB=0`, `TABLE_CATCHER=1`, `NP_SESSION_V2=1`, `MEMORY_FROM_PARAM=0`.
  - *Results.* Text only, in `raw/night/` (`<tag>-summary.txt`, `-switch-lines.txt`, `-probe.txt`, `-memline.txt`, `-kernel-stream.txt`, …).

    | Arm | Binary, switches beyond the shortcut's | End | Flips/s | Seconds with a gap > 100 ms (longest) | Memory floor |
    |---|---|---|---|---|---|
    | s0 | e4, none | save-slot list at 93 s | 23.4 | 26 (610 ms) | 425 MiB |
    | spth | e4, `PTHREAD_FIXES` | list at 93 s | 23.8 | 20 (651) | 488 |
    | ssavfix | e4, `SAVEDATA_FIXES` | list at 93 s | 23.2 | 22 (600) | 565 |
    | ssavcb | e4, `SAVEDATA_EVENT_CB` | list at 93 s | 24.2 | 21 (615) | 540 |
    | ssavsort | e4, `SAVEDATA_SORT` | list at 93 s | 24.3 | 19 (614) | 517 |
    | saud | e4, `AUDIO_FIXES` | list at 93 s | 23.9 | 18 (698) | 435 |
    | svo | e4, `VIDEOOUT_STATUS` | list at 93 s | 24.5 | 21 (583) | 533 |
    | sprt | e4, `AMM_PRT_CMDS` | list at 94 s | 24.2 | 22 (696) | 530 |
    | sextra | e4, `AMM_EXTRA_CMDS` | list at 93 s | 24.4 | 25 (606) | 539 |
    | swaits | e4, `AMPR_WAITS` | list at 93 s | 24.4 | 19 (494) | 556 |
    | scrumbs | e4, `FL_CRUMBS` | list at 93 s | 22.9 | 17 (632) | 587 |
    | sskipes | e4, `FL_SKIP_ES=0x11d00cde,0x11d00f85,0x11d00f8d` | list at 93 s | 24.1 | 18 (426) | 545 |
    | sall | e4, all of the above (FL_SKIP_ES off) | list at 93 s | 22.8 | 23 (709) | 515 |
    | rA | e4, all on, FL_CRUMBS on | clean, G at 113 s, ended at G+900 | 51.2 | 29 (1126) | 487 |
    | rB | e2 (35ff82eb), the shortcut's own: the control | clean, G+900 | 53.4 | 27 (1096) | 523 |
    | rC | e4, all on plus FL_SKIP_ES (the three ES) | clean, G+900 | 51.9 | 32 (988) | 470 |

    Every arm had 0 crash lines, 0 kernel lines, 0 freeze dumps and 0 devcoredumps. Flips/s is over the whole run, menus and loads included.
  - *Each switch's own line* came up in the journal as set. In each single-switch arm only that switch read on (`raw/night/<tag>-switch-lines.txt`). For example:
    - `pthread fixes on (rwlock: … AnyPS5 45a8b80a5, libthr rdlock_count)`;
    - `audio fixes on: set silence room`;
    - `videoout status on: resolution 2 at the first sceVideoOutGetOutputStatus (port size 1280x720, …)`;
    - `KYTY_BC5_AMM_PRT_CMDS on`;
    - `fl crumbs on (…)`;
    - `fl skip es 0x11d00cde,0x11d00f85,0x11d00f8d (…)`.
  - *FL_CRUMBS.* No fence timed out in any route, so the catcher had nothing to name. In rA it crumbed 32,769 buffers and 1.41 M draws, none of them "maybe fast-launch".
  - *FL_SKIP_ES (rC).* 194,895 draws were dropped by their ES over 16,385 buffers, with no hang in 15 minutes. That is no evidence of anything while the hang itself did not come back in rA or rB.
  - *What this shows.*
    - Every e4 switch starts the title to its save-slot list, alone and all together.
    - e4 with everything on plays 15 minutes of the route as cleanly as the e2 control, within a few percent in frame rate.
    - None of the three routes met the 18:04 freeze or exp 0404's 22:54 hang, so nothing here says whether any switch cures them.
  - *Audio: exp 0372's software replug check for `KYTY_BC5_AUDIO_FIXES` (2026-11-04 02:14–02:33).*
    - *How it ran.*
      - `aud0401t.sh` runs one `run0401t.sh` route: 420 s of play, with exp 0391's traces and the owner word `BC5_0401T_OWNER=<tag>`.
      - Beside it runs `replug0401t.sh`, which is exp 0391's `replug0391.sh` changed by `mkrep0401t.py`: it finds the run by its lock line and the emulator by the owner word.
      - Then exp 0391's `check0391.py`, unchanged, classifies the run. `audn0401.sh` drives it from the laptop.
      - The DualSense was on USB (card 44, profile 1 "Direct").
    - *Arm aA, pulls: PASS.* Pulls of 5 s, 0.5 s and 30 s. Each time the pad port (type 10) closed and reopened on the DualSense, and no pad stream went to another sink (8 pad-stream reads). No `(pad) … device playing` line fell inside a pull.
    - *Arm aB, late: PASS.* The profile was off at the start and plugged at about 170 s, then pulled once for 5 s, with the same checks. It logged 70 rumble writes and no rumble failure.
    - Both arms were clean routes otherwise (50.1 flips/s, memory floor 484 and 597 MiB), and the profile was restored both times.
    - The physical replug and a DS4 are still the maintainer's.

**Series e5: e4 plus exp 0405's e4-now ports (2026-11-04 01:3x–02:42, the top session's GO on the maintainer's "przetestuj też buildy z portami i przełącznikami z researchu"; built, not installed).**
- *What went in.* The 0405 top-32 table, and further S items as time allowed: nine port groups, each its own script, CPU test and notes.
  - One agent did each group, from 0405's specs.
  - Every group works on the unit as e4 left it, or the tree's, and never on a header.
  - Default off; a switch value can be a comma list of items.
  - Held for the maintainer's decisions: SET_PREDICATION, the 32 dead tables, values from firmware modules or titles' libc, IDA-derived signatures, and `ngs2_pcm.h`'s values.

  | Script (tag) | Units (output md5) | Switches | Items |
  |---|---|---|---|
  | `mkeq0405.py` (eq) | eventQueue.cpp d8eaa6d2, bc5LleAgc.cpp 09770e46 | `KYTY_BC5_EQUEUE_FIXES`, `KYTY_BC5_MMAP_SHIM_FIXES` | KK02 level events once per wait, SK03 WaitEqueue(NULL), G1 kevent timeout, KK01 periodic timer (+DeleteTimerEvent), M2 mmap hint and prot 0 |
  | `mkgpu0405.py` (gpu, `--chain` after eq) | bc5LleAgc.cpp d1cfd9bb | `BC5_R3_MEMSEM_SIGNAL`, `_REWIND_CATCH`, `_DROP_CATCH`, `_SUBMIT_EOP_EVENT`, `_COND_WRITE`, `_WAIT_IDLE`, `_TS_100MHZ` | G2, G4 (catcher), G8 (catcher), G6, G11, G12 (narrower), G14. Soft CP and host side only; nothing new is submitted (G6's chain path is a soft-CP replay) |
  | `mktls0405.py` (tls) | runtimeLinker.cpp aba94c24 (jit.h read only) | `KYTY_BC5_TLS_FIXES` | KL01 stubs keep RFLAGS (lea), KL02 patch at the 0x64 byte with a REX.W call |
  | `mkthr0405.py` (thr) | pthread.cpp 81ee12c4, semaphore.cpp 3aa9c8b4 | `KYTY_BC5_THREAD_SYNC_FIXES`, `KYTY_BC5_SEMA_FIXES` | KK06 notify under the lock, KK03 static rwlock/cond, Signalto ESRCH/EPERM, x87 0x037f, KK07, semaphore attributes and signal counts |
  | `mkmem0405.py` (mem) | memory.cpp 95d9ca88 | `BC5_R3_MPROTECT_GAPS`, `_NULL_ARGS`, `_RELEASE_HOLES`, `_MUNMAP_HOLES`, `_FLEX_HINT`, `_DMQ_END`, `_EXEC_EINVAL`, `_QUERY_SIZE` | M1, M21, M3, M7, M6, M20, M26, M30 (M18 held) |
  | `mkfs0405.py` (fs) | fileSystem.cpp a7201a1a, libKernel.cpp b3532873 | `KYTY_BC5_FS_FIXES`, `KYTY_BC5_POSIX_RET_FIXES` | KK04 rename, SK04 open, st_blksize, ENAMETOOLONG, KK10, SK05; POSIX unlink/munmap/mprotect and 4 more return conventions |
  | `mksvc0405.py` (svc) | libSaveData.cpp 0e0c5d40, libNet.cpp 35773d6e, libPad.cpp 89a047a4 | `KYTY_BC5_SAVEDATA_MEMORY_FIXES`, `_DELETE_BUSY`, `_ALIASES`, `KYTY_BC5_HTTP2_FIXES`, `KYTY_BC5_PAD_OPEN_EXT` | KS03 sync event and queue lock, KS09 existed size, KS14, Initialize aliases, KS01 Http2 async events, SSL options, NULL agent, scePadOpenExt (KS17 held) |
  | `mklib0405.py` (lib) | libJson2.cpp 85144ef1, libUlt.cpp 191fe8b1, libUserService.cpp e3d34e98, libSystemService.cpp 4aa00c53 | `KYTY_BC5_JSON2_FIXES`, `_ULT_FIXES`, `_USERSERVICE_VALUES`, `_SYSTEMSERVICE_VALUES`, `_SYSTEMSERVICE_PARAMS_7_1000` | Json2 use-after-free (+KS05), Ult join (own lock design), Ult queue growth, UserService and SystemService values measured on 13.40/13.60 (param 400 held) |
  | `mkao0405.py` (ao) | audio.cpp 230f732d (`exp 0372` lines unchanged) | `KYTY_BC5_AUDIOOUT_CHECKS`, `KYTY_BC5_AUDIOIN_CHECKS`, `KYTY_BC5_NGS2_RACK_FIX` | KA01, KA02, KA03 rack destroy, KA06, KA07, KA08 (KA04/05 held: other files) |
- *Integration.* `box0401.sh` series e5 is e4 plus the `E5_EDITS` chain.
  - Each script runs on a staged root holding the unit as the rows before left it, with its md5 checked, and each output is pinned.
  - Files a script only reads go in as `+rel:md5`.
  - e5's unit replaces e4's, which is kept as `bc5LleAgc-e4.cpp`.
  - The unit list for `build0401.py` is rebuilt so that every unit appears once, with its last writer.
  - e4's tests run again over e5's objects.
  - `test0401.py` passes 28 of 28 on stand-ins; `t_series_e5` checks the chain, the unit list and the pins.
  - `go-build0401.sh` drives the build from the laptop: claim, kit and sha256, setup, build, fetch, release.
  - First attempt: the kit list carried CRs from Windows Python, so it stopped before the claim. Second attempt: Windows Python could not open a POSIX path after the claim. That claim was resumed with its own token (`GO0401_TOKEN`); nothing else was retried.
- *Build.* 2026-11-04 02:3x–02:42, claim 202611040234541205456 to release, no emulator.
  - Binary `ba14f22f8a6de8d4d920df331d050d87`, launcher `6eba5275`; `raw/e5/` holds the build record and every test's output.
  - Each of the nine e5 tests passed with its switches 1, 0 and unset:

    | Test | On | Off |
    |---|---|---|
    | eq0405 | 21/21 | 18/18 |
    | gpu0405 | 72/72 | 68/68 |
    | tls0405 | 19/19 | 19/19 |
    | thr0405 | 9/9 | 9/9 |
    | mem0405 | 8/8 | 8/8 |
    | fs0405 | 23/23 | 19/19 |
    | svc0405 | 21/21 | 21/21 |
    | lib0405 | 38/38 | 22/22 |
    | ao0405 | 30/30 | 20/20 |

  - tls0405 ran its 0x66 + REX.W call cases on the box's Zen 2, and the call behaved as a 64-bit call. That settles the agent's TODO(verify) for this CPU.
  - e4's tests over e5's objects still pass. The function check gives 7/7, inh0401 25/25 and fl0401 74/74.
  - 40 warnings, all in code that was already there: 29 from `common/stringUtils.h`, which more private units now include, and the rest at known old lines. None is in new code.
- *Night tests of e5 (2026-11-04 02:42–03:30, unattended, the same method as e4's).* `raw/night-arms-e5.txt` and `raw/night-arms-e5aud.txt`. The shortcut's switches were on in every arm.

  | Arm | e5 groups on | End | Flips/s | Seconds with a gap > 100 ms (longest) | Memory floor |
  |---|---|---|---|---|---|
  | t0 | none | save-slot list at 93 s | 23.6 | 23 (594 ms) | 546 MiB |
  | teq | eq | list at 93 s | 24.1 | 24 (723) | 562 |
  | tgpu | gpu | list at 93 s | 24.1 | 19 (682) | 575 |
  | ttls | tls | list at 94 s | 24.3 | 19 (636) | 534 |
  | tthr | thr | list at 93 s | 24.3 | 17 (633) | 590 |
  | tmem | mem | list at 93 s | 24.5 | 18 (717) | 506 |
  | tfs | fs | list at 93 s | 24.0 | 23 (638) | 533 |
  | tsvc | svc | list at 93 s | 24.6 | 22 (606) | 527 |
  | tlib | lib | list at 93 s | 24.1 | 20 (655) | 531 |
  | tao | ao | list at 93 s | 24.5 | 20 (628) | 471 |
  | tall | all nine, plus e4's all on (FL_CRUMBS on, FL_SKIP_ES off) | list at 93 s | 22.9 | 21 (588) | 481 |
  | r5 | the same as tall | clean, G at 113 s, ended at G+900 | 50.6 | 32 (964) | 518 |
  | a5 | ao, plus `KYTY_BC5_AUDIO_FIXES=1`: the replug check, pulls | **PASS**, 3/3, 0 pad streams on another sink | 49.2 | 31 (1008) | 558 |

  Every arm had 0 crash lines, 0 kernel lines, 0 freeze dumps and 0 devcoredumps, and the live saves were unchanged after each.
  - *The journal lines.* Each group's line read on, with its items, in its own arm (`raw/night/t<group>-switch-lines.txt`) and all of them in tall and r5. For example:
    - `equeue fixes on (items: kk02 sk03 g1 kk01)`;
    - `tls fixes on (items: kl01 kl02)`;
    - `thread sync on (items: kk06,kk03,signalto,x87,kk07)`;
    - `savedata memory fixes on (items: sync lock existed)`.
  - *The catchers' own lines* (kevent timeouts, mmap hints that were not free, Ult queue overflow, unknown system parameters) never showed in r5's switch-line record. That record is the play log's `exp 040x` lines, at most 40 of them. The gpu group's journal lines go to `direct.log` on the box and were not collected.
  - *The TLS patch* (`KYTY_BC5_TLS_FIXES`) rewrote every TLS load of the second title at load time, and the title ran its start and 15 minutes of play with it. The ASTRO BOT title was not run.
  - *What this shows.* Every e5 group starts the title alone, and all of them together with e4's switches play the route as cleanly as e4 and the e2 control did (50.6 flips/s against 51.2 and 53.4). It shows nothing about the freeze and the hang, which did not come back.
- *Haptics: a silence line on the vibration port.* In every arm with `KYTY_BC5_AUDIO_FIXES=1`, e4's and e5's alike, the journal has this line once (saud, sall, rA, rC, aA, aB, tall, r5, a5):

  `[bc5] exp 0401: AudioOut2 port 0x4 (type 0x6, format 0x00000200): silence at Advance, no buffer set since its last grain (the port's first)`

  - The line is printed only at the first grain that a port's silence rule takes. It cannot tell one silenced grain from all of them.
  - The pad port still played 94 calls a second at rate 1.000 through the pulls. That is frames delivered, not their content.
  - `aud0401-notes.md` says a type-0x6 silence line means the rule is cutting the haptics: report it and use `set,room`. So `KYTY_BC5_AUDIO_FIXES=set,room` is the setting for any play by the maintainer until he has felt the haptics with `=1`.
  - The replug check was run again with `set,room` on e5 (arm a5r, 03:30–03:40, `raw/night-arms-e5aud-setroom.txt`): **PASS**.
    - 3 of 3 pulls; 0 pad streams on another sink; 22 rumble writes, 0 failures.
    - Its journal reads `audio fixes on: set room` and has no silence line.
    - 49.8 flips/s, memory floor 543 MiB, a clean route otherwise.
  - Still the maintainer's: the physical replug, a DS4, and whether the haptics can be felt with `=1` against `set,room`.
- *State at 03:40.*
  - e4 and e5 are built and night-tested, with every arm clean, and nothing is installed: the shortcut stays on e2.
  - Neither night met the 18:04 freeze or the 22:54 hang, so neither tells whether a switch cures them.
  - The ports are behaviour fixes for any title; on the second title they run as cleanly as before.

**Series e6p: e5 plus exp 0405's G7, SET_PREDICATION, alone (2026-11-04 morning, the top session's GO on the maintainer's
answer 5 to exp 0405: "tak, z przełącznikiem - przetestuj w pierwszej kolejności sam"; built on his "Yes, build and test" in
this session; not installed).**
- *Where G7 lives.* In the backend's filter (`policy.cpp`), not in the host unit, so e6p builds a private backend archive:
  - the shared archive's source (`KYTY_BC5_BACKEND_SRC`, `~/bc5-work/d19/export/backend` on the box) is checked against
    main 029e0d6b's backend, file by file (`backend0405.md5`, 59 files, none more or less) and copied;
  - `mkpred0405.py` edits `policy.cpp` (8e22ce87), `policy.hpp` (89f098be) and `tests/policy_test.cpp` (7f81a28a);
  - the copy is built with the shared archive's build type and compiler, and the emulator links it in place of the shared
    archive (`build0401.py --archive`, as exp 0400's relink). FilterOptions and FilterStats keep their layout (the host's ABI).
- *The switch* `BC5_R3_PREDICATION`, read once:
  - unset: as before, silent;
  - `0`: as before, and every SET_PREDICATION the filter sees is counted and journaled (a census);
  - `1`: the gfx9 form (Mesa `ac_cmdbuf_cp.c:281-284`) passes to the GPU on the GFX ring;
  - `bool`: only CLEAR and the two memory booleans pass.
  A packet with other bits (outside 0x71100, AnyPS5 `Pm4.cpp:309`, KytyPS5 `CpOpSetPredication`), an operation above 4, a
  high address over 16 bits, or an unaligned or zero predicate address stays dropped; so does every SET_PREDICATION on a
  compute ring. The predicate is a memory operand, so an unmapped one is dropped and the host makes its page resident.
- *Build* (11:22, binary fa66e89f, private archive 244fb811, launcher 9e5ec5d3): all 125 of the backend's Catch2 cases pass
  (34,886 assertions), then G7's 4 cases (190 assertions), then the switch's reading for unset, empty, 0, 1 and bool. e5's
  and e4's tests pass as in e5. (`build.txt`'s summary line printed a stderr line instead of the pass line; the raw outputs
  in `raw/e6p/raw/bk-*.out` hold the pass lines; the summary is fixed in `box0401.sh`.)
- *First, a read of last night's r5* (e4 + e5 all on, 15-min route): exp 0405's drop catcher (G8) counted only opcode 0x4a,
  112,152 times, and never 0x20.
- *Arms* (`raw/night-arms-e6p*.txt`), each as the shortcut's switches with RT on and JobArenaFix on, kernel log streamed,
  freeze watcher, private wd; 0 crash, kernel, freeze and devcoredump lines in every arm (the kernel stream held only the
  IPv6 MLD lines that r5 had too), and the live saves unchanged:

  | Arm | Switch | Result |
  |---|---|---|
  | p0, start | `=0` (census) | list at 95 s; 22.8 flips/s; floor 485 MiB |
  | p1, start | `=1` | list at 95 s; 23.7 flips/s; floor 525 MiB |
  | rp0, 15-min route | `=0` | to G+900; 53.1 flips/s; longest gap 1338 ms; floor 445 MiB |
  | rp1, 15-min route | `=1` | to G+900; 53.3 flips/s; longest gap 1300 ms; floor 415 MiB |

- *What it shows.* The filter saw no SET_PREDICATION in any of the four arms: only the switch's own line is in the journal.
  The second title does not use predication on this route, so G7 changes nothing for it, and on and off ran the same. It is
  safe to keep behind its switch, default off; showing an effect needs a title that sends the packet (ASTRO BOT was not run).

**Series e6: e5 plus exp 0405's decisions 1, 3 and 4's batch 1 (2026-11-04, the top session's GO on the maintainer's answers;
built and tested on the box 14:18-15:20 on his "Yes, build e6").** His answers (Polish, relayed by the top): 1 "wdrażamy - to tylko Twoje
podejrzenie, traktujemy jako opis innej osoby i wdrażamy"; 2 titles' own code stays out; 3 "=> A, ale w taki sposób aby nie
można było powiązać naszego kodu z IDA"; 4 "=> B => B" (port first, then load, a switch per table); 5 is e6p above; 6 the
ngs2_pcm.h family stays out. Six laptop agents ported it, one group each (`*0405-notes.md` hold the evidence):

| Group | Switch | Units (input → output) | Test (on / off) |
|---|---|---|---|
| fwn: decision 1, net and system | `KYTY_BC5_FW_NET` (rtc, rudp, resolver, param400, npwebapi) | libRtc 719561dd, libRudp af8d0178, network 598cfe80, libSystemService (e5) 252a35f9, libNpCppWebApi (e) e613bc8f | 33 / 33 |
| fwa: decision 1, audio | `KYTY_BC5_FW_AUDIO` (audio3d, audio3dstrict, pcmloop, avplayer, ngs2) | audio.cpp (e5) 1f90e752, avPlayer 44203af3 | 50 / 28 |
| jit: decision 3, R3 M31 | `KYTY_BC5_JIT_SHM`; `KYTY_BC5_FW_KERNEL` (notify) | memory.cpp (e5) ee24c888, libKernel (e5) 0a0d4665 | 8 / 3 |
| tbc: decision 4, Zlib, JpegEnc, Ime | `KYTY_BC5_LOAD_ZLIB`, `_JPEG`, `_IME` | libZlib c7e165b9, libJpeg c5fe947c, libIme 49fa46f1 | 108 / 26 |
| tbn: decision 4, NpCommon, NpManager, NpTrophy | `KYTY_BC5_LOAD_NPCOMMON`, `_NPMANAGER`, `_NPTROPHY` | libNp 24e77826 | 165 / 34 |
| tld: decision 4, the loading | the six `KYTY_BC5_LOAD_*` | libs.cpp 903fa699 | 9 / 9 |
| pad: Pad b94b3fa32 and 3b404f65e, from behaviour only | `KYTY_BC5_FW_PAD` (infotype, argchecks, queries) | libPad (e5) b9940ebe | 71 / 4 |

- *Tables load first.* With a switch on, its table loads before every live table, so an import's exact key keeps the live
  function. The loader's NID-only fallback (`FindByNid`) takes the first record, though, so the 9 NIDs that live tables
  also register (7 Ime, 2 NpManager) are no longer registered by the switched tables (the top session's approval). The other
  26 dead tables have no such collision (`tld0405-notes.md` lists them all: 1,033 NIDs).
- *Held, with sizes* (in each group's notes): the Ngs2 renderer (3-5 days) and new Audio3d exports (about 1 day); Rudp's
  contexts (about 3.5 days), Mouse's absolute-position calls, Pad queries; the Jpeg encode itself (about 0.3 day); 39 Ime
  functions AnyPS5 leaves unimplemented too; 64 NpTrophy placeholders; `sceKernelJitGetSharedMemoryInfo`.
- *Held for the maintainer:* ImeFilterText and NpTrophy ConfigHasGroupFeature (disassembly with addresses), and three
  libkernel_sys rows ("read from disassembly and not measured on a console").
- *His answers on two of them (relayed by the top session):* `npwebapi` comes from a module a title ships, and "nie każda gra
  dostarcza własny, ale nie konieczna posiada - wdrażamy na wszelki wypadek w konfiguracji jeżeli nie ma, to korzystamy z
  naszych bibliotek": ported, and on in the all-on route (our library is the fallback for a title without its own). Pad
  b94b3fa32 and 3b404f65e: "tak, przepisać tak JIT", rewritten from behaviour only as a group of their own (tag `pad`).
- *Kit* (`box0401.sh` series e6): rows chained after e5's (E6_EDITS, E6_GATES, E6_STRS); the stand-in case `t_series_e6`
  passes. Arms are ready (`raw/night-arms-e6.txt`, `raw/night-arms-e6aud.txt`): the base start, one start per group, all on,
  a 15-min route with e4, e5 and e6 on, and exp 0372's software replug check for the audio group.
- *The build* (`raw/e6/`; binary 7252558e78d38b3bf589d8d773676a63, the shared builds unchanged).
  - Every CPU test passed on the box, both ways: the counts in the table above, and e5's tests as before (`raw/e6/build.txt`).
  - The first try (`raw/e6-try1/`; its box directory is kept as `exp0401e6-try1`) stopped at fwn0405's case 10 when off.
    - The test was wrong, not the code. AnyPS5's "distant" tick lies in year 134350, whose 16-bit year is 3278.
    - Today's code refuses it (past 9999); the test had expected the text both ways.
    - The case now expects VALUE when off (`fwn0405.cpp`, `fwn0405-notes.md`).
- *The arms* (`raw/night/t6*`, `r6-*`, `a6-*`; 14:37-15:20). `t6` is the e6 binary with every e4, e5 and e6 switch off; each
  group's start adds only its group. `t6all` and `r6` have e4's, e5's and e6's all on.

  | Arm | On | Result | Flips/s | Gaps over 100 ms (longest, ms) | Memory floor, MiB |
  |---|---|---|---|---|---|
  | t6 | none | list at 94 s | 22.8 | 25 (645) | 564 |
  | t6fwn | fwn | list at 94 s | 22.2 | 32 (627) | 534 |
  | t6pad | pad | list at 94 s | 21.0 | 22 (689) | 546 |
  | t6fwa | fwa | list at 107 s | 19.2 | 21 (499) | 590 |
  | t6jit | jit (both switches) | list at 95 s | 23.9 | 20 (661) | 495 |
  | t6tbl | the six loads | list at 94 s | 23.8 | 22 (842) | 510 |
  | t6all | e4, e5 and e6 all on | list at 93 s | 22.0 | 20 (595) | 503 |
  | r6 | the same as t6all | clean, G at 113 s, ended at G+900 | 51.1 | 32 (1234) | 668 |
  | a6 | a5's words plus fwa: the replug check, pulls | **PASS**, 3/3, 0 pad streams on another sink | 47.7 | 33 (1136) | 1276 |

  Every arm had 0 crash lines, 0 kernel lines, 0 freeze dumps and 0 devcoredumps, and the live saves were unchanged after each.
  - *The journal lines.* Each group's line read on, with its items, in its own arm and all of them in t6all and r6, e.g.:
    - `fw-net on (items: rtc rudp resolver param400 npwebapi)`;
    - `fw pad on (items: infotype argchecks queries)`;
    - `tables on (items: zlib,jpeg,ime,npcommon,npmanager,nptrophy)`;
    - `ime port on (items: panel test; the 7 NIDs of the live Ime table not registered)`.
  - *The 40-line record.* r6's `switch-lines.txt` lacks five of e4's and e5's lines (the AMM, AMPR, SessionManager V2 and
    audio fixes lines). The record keeps only the 40 most frequent lines, and e6 adds 13 more. The play log on the box has
    every one of them once (`r6-switch-lines-all.txt`, `t6all-switch-lines-all.txt` are the uncut lists).
  - *No e6 catcher line fired.* None of the items' "once" lines (an RTC refusal, a Rudp or resolver refusal, a pad check)
    is in r6's play log. So the second title's route never took a path whose answer e6 changes.
  - *a6 against a5.* The same pass: 3 of 3 pulls, 17 stream lines, 8 pad streams, 0 on another sink, 0 rumble writes, 39
    'pad route … dropped' lines (a5: 38). With `KYTY_BC5_AUDIO_FIXES=1`, as in a5, the haptics port's silence line is back.
  - *The start with fwa alone.* t6fwa reached the list at 107 s and a6 at 118 s (G at 142 s; a5: 97 s and 117 s), against
    93-95 s in every other arm, t6all and r6 included, which have fwa on too.
    - It was repeated at once (`raw/night-arms-e6fwa-rep.txt`): base, fwa, base, fwa, with the same words.
    - The list came at 93, 94, 93 and 93 s (23.2 and 23.0 flips/s with fwa; 22.6 and 23.0 without). All four were clean.
    - So the slow t6fwa start did not come back. a6's slower start is not explained; its route and its check passed.

**Verdict.** Not yet. Both switches together made the game too slow to play, and the confounds above leave the cause open.
