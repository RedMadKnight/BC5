# Experiment 0419: options to remove in the swap AFTER the cleanup candidate (HARDEN)

From the unverified inventory (`switch-inventory.tsv`). These are on by default in the code already. The cleanup candidate keeps every one of them as an option, because they are what a bisect of that candidate needs. After the maintainer has played on it, each read site becomes a constant and the word leaves `switch_defaults.hpp`. Before that swap each row needs its read site checked, as the DELETE rows were.

| Switch | Read at (patch line) | State today | Tested, verdict (the inventory's words) |
|---|---|---|---|
| BC5_DIRECT_ACB_STATE_RESTORE | patch libs/bc5LleAgc.cpp:39996 | on in code (kFixes) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0381, F685: 3/3 faulted without, 3/3 clean with; audit row A2; kFixes since exp 0416 |
| BC5_DIRECT_COMPUTE_RING | patch libs/bc5LleAgc.cpp:38570 | code default GFX ring | exp 0339/0342, F412/F415: one ring costs no frame rate and takes the compute ring (the machine-down path) out of play; first RT-on play without a hang |
| BC5_DIRECT_IB_MAX_DW | backend/src/direct.cpp:560 | code default built-in | exp 0349, F426/F433: the IB cut is in both shared builds and passed the route with RT on |
| BC5_DIRECT_JOURNAL_QUIET | patch libs/bc5LleAgc.cpp:34287 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e7; audit row B16: journal 24 MB against 385 MB; in his shortcut since e8/e9 |
| BC5_DIRECT_PREFIX_ALL | patch libs/bc5LleAgc.cpp:39378 | on in code (hard-coded at the getenv site) | exp 0157/0160 (F204, F207, F208), F599 names it "the default"; I did not re-read a verdict line for the default itself |
| BC5_DIRECT_SOFT_WAIT_MS | patch libs/bc5LleAgc.cpp:44707 | code default 8; launcher: play-pkg.sh=8 | exp 0343, F433: soft-CP replay polls bounded at 8 ms |
| BC5_FAULT_RECORD | patch libs/bc5LleAgc.cpp:41981 | on in code (hard-coded at the getenv site) | exp 0412 (mkdef0412.py); CLAUDE.md: with candidate B a GPU fault ends the game with a diagnostic record and exit 86; the maintainer's rule of 2026-11-13 (fault = bug + record) |
| BC5_R3_COND_WRITE | patch libs/bc5LleAgc.cpp:33126 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (gpu0405-notes.md); audit row A9: CPU 72/68, tgpu clean, in his shortcut |
| BC5_R3_DMQ_END | patch kernel/memory.cpp:22551 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_EXEC_EINVAL | patch kernel/memory.cpp:22551 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_FLEX_HINT | patch kernel/memory.cpp:22551 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_MEMSEM_SIGNAL | patch libs/bc5LleAgc.cpp:33122 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (gpu0405-notes.md); audit row A9: CPU 72/68, tgpu clean, in his shortcut |
| BC5_R3_MPROTECT_GAPS | patch kernel/memory.cpp:22550 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_MUNMAP_HOLES | patch kernel/memory.cpp:22550 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_NULL_ARGS | patch kernel/memory.cpp:22550 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_QUERY_SIZE | patch kernel/memory.cpp:22551 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_RELEASE_HOLES | patch kernel/memory.cpp:22550 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (mem0405-notes.md); audit row A13: CPU 8/8, tmem clean, in his shortcut |
| BC5_R3_TS_100MHZ | patch libs/bc5LleAgc.cpp:33128 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (gpu0405-notes.md); audit row A9: CPU 72/68, tgpu clean, in his shortcut |
| BC5_R3_WAIT_IDLE | patch libs/bc5LleAgc.cpp:33127 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5 (gpu0405-notes.md); audit row A9: CPU 72/68, tgpu clean, in his shortcut |
| KYTY_BC5_AMM_SETBUFFER_GUARD | patch libs/libAmpr.cpp:52185 | on in code (hard-coded at the getenv site) | exp 0413, F816: 7 of 7 ASTRO BOT starts pass with it, 3 of 3 crash without |
| KYTY_BC5_AMPR_WAITS | patch libs/libAmpr.cpp:51132 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A6: CPU 317/63, swaits clean |
| KYTY_BC5_APR_POSIX | patch libs/libAmpr.cpp:51801 | on in code (kFixes) | exp 0415, F817: first key 7.3 s earlier, save load 4.2 s sooner, 10 runs against 8; kFixes (direct) since 2026-11-13 |
| KYTY_BC5_APR_READAHEAD | patch libs/libAmpr.cpp:51742 | code default 4; launcher: play-astro.sh=4 | exp 0203-0229, F266/F286/F287: on again with the worker fix; exp 0415: 12 no better |
| KYTY_BC5_APR_SYNC | patch libs/libAmpr.cpp:51722 | off everywhere | exp 0156, F203/F206 (the async answer is the fix); F295 names a race on the async side; no verdict found on dropping the old path |
| KYTY_BC5_AT9_VIBRATION | patch libs/ajm/atrac9_decoder.h:29863 | on in code (hard-coded at the getenv site) | exp 0243, F301: confirmed at the pad by the maintainer ("Haptyka dziala") |
| KYTY_BC5_AUDIO_FIXES | patch libs/libAudio2.cpp:54405 | on in code (kDefaults) [shortcuts: e10-menu=set,room, 0412-fast9=set,room] | exp 0401 e4; audit row A5: replug checks PASS with set,room; "=1" (with silence) silences the haptics port |
| KYTY_BC5_EQUEUE_FIXES | patch kernel/eventQueue.cpp:14268 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A8: CPU 21/18, teq clean, r5/r6 route clean |
| KYTY_BC5_EVENT_PENDING_CAP | patch kernel/eventQueue.cpp:14443 | on in code (kFixes) [shortcuts: 0412-fast9=64, 0412-astro-cap=64] | exp 0412 sections 10/11, F815: ASTRO BOT's 217.8 MiB/min leak -> 0.1 MiB/min; audit row C1 |
| KYTY_BC5_FS_FIXES | patch kernel/fileSystem.cpp:16240 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A14: CPU 23/19, tfs clean; note: his unexplained fall out of the world of 11-04 had the fs group on |
| KYTY_BC5_FW_AUDIO | patch libs/audio.cpp:30609 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e6; audit row A19: CPU 50/28, replug PASS, his physical replug OK |
| KYTY_BC5_FW_KERNEL | patch libs/libKernel.cpp:59564 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e6; audit row A20: CPU 8/3, t6jit clean |
| KYTY_BC5_FW_NET | patch libs/libNpCppWebApi.cpp:66097; patch libs/libRtc.cpp:68634; patch libs/libRudp.cpp:68818 (+2 more) | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e6; audit row A18: CPU 33/33, t6fwn clean |
| KYTY_BC5_JIT_SHM | patch libs/libKernel.cpp:59534 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e6; audit row A20: CPU 8/3, t6jit clean |
| KYTY_BC5_MMAP_SHIM_FIXES | patch libs/bc5LleAgc.cpp:46851 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A8: CPU 21/18, teq clean, r5/r6 route clean |
| KYTY_BC5_NO_PAD_AUDIO | patch libs/audio.cpp:30844; patch libs/audio.cpp:31370 | off everywhere | exp 0372, F502; F828: the pad route passes the replug checks on the shared build; no verdict found on dropping the option |
| KYTY_BC5_NP_SESSION_V2 | patch libs/libNpCppWebApi.cpp:67092 | on in code (hard-coded at the getenv site) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e, exp 0413; audit row A1: gate 10/10, 0 failures since 11-03; in the shared builds since 2026-11-12 |
| KYTY_BC5_PAD_PW_PROPS | patch libs/audio.cpp:30706 | on in code (hard-coded at the getenv site) | exp 0372, F503: dont-fallback is the essential key; "=0 is the A/B arm" |
| KYTY_BC5_PAD_RUMBLE_FALLBACK | patch libs/audio.cpp:30915 | on in code (hard-coded at the getenv site) | exp 0256-0270, F214/F326/F328; no verdict found on dropping the option |
| KYTY_BC5_PAD_SPEAKER | patch libs/audio.cpp:30829; patch libs/audio.cpp:30833; patch libs/audio.cpp:30839 | code default pad route | exp 0267/0268/0372 (F326, F330, F502); main-blocking is "the A/B arm of exp 0268's hold"; F828: the default passes the replug |
| KYTY_BC5_PAUSE_ON_BACKGROUND | patch graphics/presentation/window/window.cpp:13811 | off everywhere | exp 0176, F233: the window ignores the background event since; the old behaviour made ASTRO BOT's two "hangs" |
| KYTY_BC5_PHYSMAP_SORTED | patch kernel/memory.cpp:23435 | on in code (kFixes) [shortcuts: 0412-fast9=1] | exp 0412 section 18; audit row C3: 1,259,728 checks equal; scene +17 %, save +18 % |
| KYTY_BC5_POSIX_RET_FIXES | patch libs/libKernel.cpp:59886 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A14: CPU 23/19, tfs clean; note: his unexplained fall out of the world of 11-04 had the fs group on |
| KYTY_BC5_PTHREAD_FIXES | patch kernel/pthread.cpp:28676 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A3: CPU stress 10/10, start arm clean |
| KYTY_BC5_RANGES_FAST | patch kernel/memory.cpp:22950 | on in code (kFixes) [shortcuts: 0412-fast9=1] | exp 0412 section 15; audit row C2: 600,000 queries identical; scene load 15 -> 19.7 flips/s |
| KYTY_BC5_SAVEDATA_EVENT_CB | patch libs/libSaveData.cpp:70246 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A4: CPU 20/33/20, live saves unchanged in every arm |
| KYTY_BC5_SAVEDATA_FIXES | patch libs/libSaveData.cpp:70705 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A4: CPU 20/33/20, live saves unchanged in every arm |
| KYTY_BC5_SAVEDATA_SORT | patch libs/libSaveData.cpp:70600 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A4: CPU 20/33/20, live saves unchanged in every arm |
| KYTY_BC5_SEMA_FIXES | patch kernel/semaphore.cpp:29197 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A12: CPU 9/9, tthr clean |
| KYTY_BC5_SWITCH_DEFAULTS | not read (patch 36864 comment only) | on in code (hard-coded at the getenv site) | exp 0413/0416, F827: p0off shows the old behaviour is reachable |
| KYTY_BC5_THREAD_SYNC_FIXES | patch kernel/pthread.cpp:28497 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A12: CPU 9/9, tthr clean |
| KYTY_BC5_TLS_FIXES | patch loader/runtimeLinker.cpp:87646 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e5; audit row A11: 15-min route clean; exp 0413 a2astro: not the cause of ASTRO BOT's start crash |
| KYTY_BC5_VIDEOOUT_STATUS | patch graphics/presentation/videoOut.cpp:11934 | on in code (kDefaults) [shortcuts: e10-menu=1, 0412-fast9=1] | exp 0401 e4; audit row A7: CPU 27/27, svo clean |

52 rows.
