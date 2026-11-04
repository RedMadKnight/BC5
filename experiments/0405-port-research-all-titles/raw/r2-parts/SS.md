# SS: sharpemu `514d766` non-kernel, non-GPU libraries vs OURS (KytyPlus f266548 + patch 0001)

Paths: S = sharpemu `src/SharpEmu.Libs/` at `514d766` (extracted copy `$R/sharp/src/SharpEmu.Libs`), O = OURS `src/`.
All sharpemu files carry `SPDX-License-Identifier: GPL-2.0-or-later`. shadPS4 (`refs/shadps4-emu_shadPS4` @ `60c42b9`,
GPL-2.0-or-later) is used only as a corroborating second source where named.

## 1. Method

Pass 1 (missing exports): took the 254 non-libc/libKernel/Agc/Ult rows of `s-only.tsv`, read every sharpemu body, and
re-checked each against OURS by grepping every quoted 11-character NID string in O (not only `ours-nids.tsv`). Two inventory
errors found: (a) 20 rows are false positives because `ours-nids.tsv` misses LIB_FUNC calls split over two lines
(all 19 libSceNpUniversalDataSystem property-object/array NIDs at O libs/libNet.cpp:3088-3138 and
NpEntitlementAccessGetAddcontEntitlementInfoList at O libs/libNet.cpp:1722-1723); (b) the 15 name-only rows (NpAuth x10,
Http2 x5, empty NID column) were resolved with the public NID hash (helper `parts/SS-scripts/nid.py`): 14 are registered in
OURS (O libs/libNet.cpp:1358-1383, 1972-1979, libs/libNp.cpp:62); only `sceNpAuthGetAuthorizedAppCode` (IDX0S5EsEh4) is
missing. Pass 2 (behaviour fixes): `git log` per directory for SaveData, Audio, Acm, Ngs2, Pad, Json, Rtc, Np, Network,
PlayGo, AvPlayer, Codec, Media, UserService, SystemService, AppContent, CommonDialog, Font, Png, Psml, Usbd, Remoteplay,
Share, Ampr, VideoOutExports.cs; read the reason-stating commits (4d56978, 4bb1af9, bc51cc2, 488b285, 4c8c67a, 9415395's
SaveData part, b307b2f, 341c2a0, b4b9501, 56bf00e, 16a2131, 3ebfc56, eb252af, 3c500d2, 2ced3af, de13735, ac8ffc3,
c60b57a, 9eef395, 5052fae, 2df6f5b, a8be1da, 7a108c6, 3585519, e13cb28, 26c5029, 4b8d455, d113a37, ef73fe4, 2cd6676,
660df73, 3172d7c, 8e1c625, 7b95016, acb0d4a, 22bbb4e) and opened the matching OURS function. Provenance scan: commit
`56bf00e` "[RTC] Port core rtc helpers from PS5 3.20 libs" (firmware-derived) and `Audio/AudioOut2Exports.cs` comments that
cite "the header" (:990, :1198) are flagged. Not done: AvPlayer/Media FFmpeg-bridge internals, Ime, Font text-string code
(11506fc Font part), Ngs2 line-by-line.

## 2. Table (ranked: fixes to functions we have, then missing functions with behaviour, then stubs, then skips)

| ID | What | Source (S path @514d766:lines; introducing commit) | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| SS01 | sceSaveDataSyncSaveDataMemory (wiT9jeC7xPw) must queue a SAVE_DATA_MEMORY_SYNC event (type 3) that sceSaveDataGetEventResult returns | SaveData/SaveDataExports.cs:1571-1609 (added in 9415395 2026-07-18; comment: guest blocks a worker on GetEventResult until SYNC_END, "what wedged Dead Cells at FLIP 0"); shadPS4 savedata.cpp:1637-1665 + save_backup.h:26 agree (type 3) | GPL-2.0+ | differs: O libs/libSaveData.cpp:1061-1067 (returns OK, no event) | S | L: one more event in the queue; queue has no lock (libSaveData.cpp:250,263-281) - add one | e4-now | hang fix: any title that waits for the sync-end event polls forever today |
| SS02 | sceSaveDataSetupSaveDataMemory2 (oQySEUfgXRA): result.existedMemorySize = size that existed before this call (0 on first setup) | SaveData/SaveDataExports.cs:1495-1551 (488b285 2026-07-16 "Implement save data memory2 exports"); shadPS4 savedata.cpp:1580-1603 (existed_size 0 = just created) | GPL-2.0+ | differs: O libs/libSaveData.cpp:757-767 reports the vector size after resize (>= 0x10000, = memory_size on a fresh title) | S | L: titles that took the "memory existed" path on first run now take their init path | e4-now | wrong result: fresh titles are told a save existed and read zeros as their save |
| SS03 | sceNetResolverDestroy (kJlYH5uMAWI) + sceNetResolverGetError (J5i3hiLJMPk) | Network/NetExports.cs:1245-1282 (02222c7 2026-06-28) | GPL-2.0+ | missing; O libs/network.cpp:369-375,423-446 has 32 resolver slots and no way to free one | S | L | e4-now | resource leak: the 33rd sceNetResolverCreate returns NET_ERROR_RESOLVER_ENOSPACE (network.cpp:1438-1441) for a title that creates/destroys per lookup |
| SS04 | sceSaveDataTransferringMount (WAzWTZm1H+I, RjMlsR8EXrw): read-only mount of the named title's save; NOT_FOUND when absent; never creates | SaveData/SaveDataExports.cs:920-963 + MountSaveData 825-918 (4c8c67a 2026-07-21); shadPS4 savedata.cpp:1685-1703 (RDONLY mount with mount->titleId) | GPL-2.0+ | differs: O libs/libSaveData.cpp:850-883 uses our own title id, creates the dir and reports mount_status 1 | S | M: a title that today proceeds on the false success sees NOT_FOUND (console behaviour); grep box logs for TransferringMount first | e4-now | wrong result: "PS4 save found" for every probe; empty dir left behind |
| SS05 | sceUsbdHandleEventsTimeout (+wU6CGuZcWk): validate {s64 sec, s64 usec} and sleep that long | Usbd/UsbdExports.cs:64-102 (acb0d4a 2026-09-22; stated: keep guest USB event threads paced instead of a hot loop) | GPL-2.0+ | differs: O libs/libUsbd.cpp:673-682 returns at once | S | L | e4-now | CPU: a USB event thread spins on the 4-core-ish box; sceUsbdHandleEvents (O :643-650) has the same shape (not changed by sharp) |
| SS06 | Notice-screen skip flag kept: Set stores (arg != 0), Get returns it | SystemService/SystemServiceExports.cs:62-107 (eb252af 2026-07-23: titles use it as a preference store and expect a later get to see the set value) | GPL-2.0+ | differs: O libs/libSystemService.cpp:234-256 (Get always false, Set ignores its argument) | S | L | e4-now | wrong result for any title that reads back its own setting |
| SS07 | Ngs2 renders audio: sampler voices (PCM/VAG/ATRAC9), streaming read-ahead, voice routing through matrices, panning | Ngs2/*.cs (2cd6676 2026-10-20, 2409 lines in 9 files) | GPL-2.0+ | differs: O libs/audio.cpp:2999-3022 Ngs2SystemRender memsets the buffers and only steps voice states | L | M: audio path, mixing levels; DualSense replug check (exp 0372) before ship | later | every Ngs2 title is silent today |
| SS08 | sceAcm_ConvReverb_SharedInput zeroes its output channel buffers (convolution itself not done) | Acm/AcmExports.cs @514d766 ConvReverbSharedInput (d113a37 2026-10-15; stated: stale output must not be played) | GPL-2.0+ | differs: O libs/audio.cpp:1724-1736 (advances batch only) | S | M: out-descriptor layout {u32 samples, u32 channels, .., u64 buffers@+0x10} is sharp's reading, unverified, and writes guest memory; replug check | later | stale/garbage reverb output becomes silence |
| SS09 | sceSaveDataSaveIcon/LoadIcon persist the icon with the slot; LoadIcon NOT_FOUND when none | SaveData/SaveDataExports.cs:431-505 | GPL-2.0+ | differs: O libs/libSaveData.cpp:1195-1206 (SaveIcon no-op), 1030-1045 (LoadIcon data_size 0, OK) | M | L: choose sidecar location (OURS keeps sidecars next to the dir, :320-343) | later | data loss: icon never kept; slot lists show none |
| SS10 | sceSaveDataDelete of a mounted save -> BUSY (shadPS4 savedata.cpp:741-746); missing save -> sharp NOT_FOUND (SaveDataExports.cs:343-348) vs shadPS4 OK (:748-756) | as cited | GPL-2.0+ | differs: O libs/libSaveData.cpp:946-983 deletes a mounted save, OK for missing | S | M: sources disagree on the missing case | later | data integrity (deleting the dir under a live mount) |
| SS11 | Get/SetSaveDataMemory2 and Sync before Setup -> MEMORY_NOT_READY 0x809F0012 | SaveData/SaveDataExports.cs:1576-1699 (488b285); shadPS4 :1652-1655 | GPL-2.0+ | differs: O libs/libSaveData.cpp:771-848 auto-loads and succeeds | S | M: a title relying on our lenient path would now see an error | later | console-accurate error |
| SS12 | MsgDialog state guards return SCE_COMMON_DIALOG errors (NOT_INITIALIZED 0x80B80003, NOT_FINISHED 0x80B80005, BUSY 0x80B80007, NOT_RUNNING 0x80B8000B, ARG_NULL 0x80B8000D) | CommonDialog/MsgDialogExports.cs (de13735 2026-07-15) | GPL-2.0+ | differs: O libs/dialog.cpp:~549-640 returns OK in those states | S | M: stricter errors | later | correctness of error paths |
| SS13 | Videodec2: picture-info size prefix and adjacent fields kept, EOF handled, teardown joins workers | Codec/Videodec2Decoder.cs, Videodec2Exports.cs (3172d7c 2026-10-15) | GPL-2.0+ | not compared in detail: O libs/libVideoDec2.cpp:460-507 + videoDec2Decoder.h | M | M | later | movie decode robustness; unverified whether OURS has the defects |
| SS14 | Trophy unlock from UDS events (stat rules from sce_sys/uds, _UnlockTrophy, platinum, persisted unlocks) | Np/* (5052fae 2026-10-13; message: rules follow KytyPS5's NpTrophy2/UDS code) | GPL-2.0+ | differs: O libs/libNet.cpp:2543-2555 PostEvent does not unlock | L | L | later | feature; likely duplicated by the KytyPS5 agent's rows |
| SS15 | sceAjmModuleUnregister/sceAjmFinalize validate the context and drop registrations | Audio/AjmExports.cs (4b8d455 2026-08-09) | GPL-2.0+ | differs: O libs/ajm.cpp:779-783, 813-817 no-ops | S | L; replug check | later | error-path accuracy |
| SS16 | sceFontGetHorizontalLayout/VerticalLayout take the layout pointer from rdx when rsi is 0 | Font/FontExports.cs (8e1c625 2026-10-01; stated: Astro Bot assert in FontSystem.cpp) | GPL-2.0+ | differs: O libs/libFont.cpp:1408-1413 returns -1 (O already scales metrics, :1416-1429) | S | M: rdx may be garbage when a caller passes 0 on purpose | later | avoids a title assert |
| SS17 | sceAudioPropagationSystemQueryMemory: report 1 MiB CPU, 0 GPU; null out -> 0x8A700003 | Audio/AudioPropagationExports.cs:20-52 (ddaf7ff) | GPL-2.0+ | differs: O libs/libAudio.cpp:36-48 reports 0 CPU bytes (descriptor already untouched, as sharp's fix wants) | S | L; replug check | later | a title allocating 0 bytes may assert |
| SS18 | scePlayGoGetLocus writes NOT_DOWNLOADED into the bad entry before returning BAD_CHUNK_ID | PlayGo/PlayGoExports.cs (16a2131 2026-07-16) | GPL-2.0+ | differs: O libs/libPlayGo.cpp:188-194 leaves it unwritten | S | L | e4-now | small: defined output on the error path |
| SS19 | AudioOut2 producer usleep shortened while the device runs short | Audio/AudioOut2Exports.cs (ef73fe4 2026-10-14) | GPL-2.0+ | differs by design: O libs/libAudio2.cpp:599-665 paces on the device queue | M | H: pacing; replug check | later | anti-crackle idea only |
| SS20 | PlayGo installed chunk set derived from pak files on disk | PlayGo/PlayGoExports.cs (3ebfc56 2026-07-19) | GPL-2.0+ | differs: O libs/libPlayGo.cpp:73-88 (all chunks of the table local) | M | L | later | partial installs only |
| SS21 | AvPlayer: file URIs resolved inside app0, case-insensitive fallback, traversal rejected | AvPlayer/AvPlayerExports.cs (22bbb4e 2026-07-17) | GPL-2.0+ | partly: O libs/avPlayer.cpp:646-690 handles file:// and relative paths; case-insensitive fallback not verified | S | L | later | Linux host is case-sensitive |
| SS22 | scePadOpenExt (WFIiSfXGUq8): as scePadOpen, also accepts port type 1 | Pad/PadExports.cs:91-96 + PadOpenCore 132-180 (373100a 2026-07-14) | GPL-2.0+ | missing (stub returns handle 0, which every O pad call rejects: controller.cpp:489-492) | S | L | e4-now | no input at all for a title that opens its pad this way |
| SS23 | sceNetRecv (9wO9XrMsNhc), sceNetRecvfrom (304ooNZxWDY) | Network/NetExports.cs:253-355 (d0dd3fe 2026-09-30) | GPL-2.0+ | missing in libSceNet; implementation exists: O libs/network.cpp:2182-2230 | S | L | e4-now | sockets usable through libSceNet; pair with KytyPS5 NetConnect/Send/Sendto (k-only) |
| SS24 | sceNetCtlRegisterCallbackV6 (1NE9OWdBIww) -> same as RegisterCallback | Network/NetCtlExports.cs:149-154 (373100a) | GPL-2.0+ | missing; O libs/network.cpp:4013-4033 | S | L | e4-now | stub leaves *cid unwritten (garbage id later unregistered) |
| SS25 | Json aliases: Array C2/D2, String C2/D2, iterator D2, iterator operator->, Value::getValue(size_t), Value::clear | Json/JsonExports.cs:489-494,531-548,667-686,777-782,807-812; JsonValueExports.cs:189-198 (b307b2f 2026-10-12, df53ff5, 864cbb0) | GPL-2.0+ | missing; targets exist: O libs/libJson2.cpp:1100-1121, 799-826, 1208-1224, 740-748, 224-240 | S | L | e4-now | an unregistered C2 constructor returns 0 without setting impl: later use dereferences garbage |
| SS26 | Json Array::iterator default ctor (C1/C2), copy ctor (C1/C2), operator=, operator++(int), advance(size_t) | Json/JsonExports.cs:731-764, 827-850 + helpers 852-910 (b307b2f) | GPL-2.0+ | missing; O iterator model libs/libJson2.cpp:1129-1224 | S | L | e4-now | range-for and std-style loops over sce::Json::Array |
| SS27 | sceAppContentGetAddcontInfoList (xnd8BJzAxmk): writes *hitNum | AppContent/AppContentExports.cs:48-68 (4d73f46); shadPS4 app_content.cpp:269-295 | GPL-2.0+ | missing | S | L | e4-now | stub leaves hitNum uninitialised: title iterates a garbage count |
| SS28 | sceNpCommerceDialogOpen2 (IXmfUaze9So) -> same state machine as Open | Np/NpCommerceExports.cs:41-46 (37694df 2026-09-19) | GPL-2.0+ | missing; O libs/libNpCommerceDialog.cpp:58-77 ignores the param, so a direct alias fits | S | L | e4-now | stub leaves the dialog INITIALIZED: a title polling for FINISHED waits forever |
| SS29 | sceSaveDataUmount (BMR4F-Uek3E) = Umount2(0, mp); sceSaveDataGetProgress (ANmSWUiyyGQ) writes 1.0f | SaveData/SaveDataExports.cs:263-265, 535-549 (9415395); shadPS4 savedata.cpp:1705-1708, 1096-1108 | GPL-2.0+ | missing; O libs/libSaveData.cpp:885-910 | S | L | e4-now | stub Umount never frees the slot: 17th mount -> MOUNT_FULL |
| SS30 | sceSystemServiceGetMainAppTitleId (4veE0XiIugA): TITLE_ID into a 16-byte field | SystemService/SystemServiceExports.cs:109-133 (b4b9501 2026-07-16) | GPL-2.0+ | missing | S | L | e4-now | out-param |
| SS31 | sceNpEntitlementAccessGetGameTrialsFlag (y7JD1gfwyfA): *flag=0; GetEntitlementKey (5LiMEPuW0DQ): zero 16-byte key, NO_ENTITLEMENT unless owned | Np/NpEntitlementAccessExports.cs:98-116, 223-252 (1811cef, e17fb6f) | GPL-2.0+ | missing; O constants and owned list libs/libNet.cpp:1547-1548, 1570-1574 | S | L | e4-now | out-params and error codes |
| SS32 | sceNpAuthGetAuthorizedAppCode (IDX0S5EsEh4): same signed-out completion as GetAuthorizationCodeV3 | Np/NpAuthExports.cs:154-158 + 180-217 (37694df) | GPL-2.0+ | missing; O libs/libNet.cpp:1908-1940 pattern | S | L | e4-now | error code instead of 0 (title thinks it got a code) |
| SS33 | sceNpSessionSignalingCreateContext2 (aBuX0PX-T7I) returns a positive id; RequestPrepare (r8mVMwlafF8) returns SIGNED_OUT 0x80550006 | Np/NpSessionSignalingExports.cs:24-41 (e17fb6f, d0dd3fe) | GPL-2.0+ | missing (O libs/libNet.cpp:1534-1539 has Init/Term/Deactivate/Destroy) | S | L | e4-now | context id 0 may be read as failure |
| SS34 | sceAudioOut2LoContextGetQueueLevel (Q8DZkKQ-SYc) -> ContextGetQueueLevel | Audio/AudioOut2Exports.cs:615-621 (e13cb28 2026-07-23) | GPL-2.0+ | missing; O libs/libAudio2.cpp:673-712 | S | L; audio path: replug check; file elsewhere quotes "the header" (:990,:1198), these lines do not | e4-now | stub writes no level: Wwise-style renderers see garbage |
| SS35 | sceAjmBatchJobRunBufferRa (ElslOCpOIns), RunSplitBufferRa (7jdAXK+2fMo): same nine args plus a return address | Audio/AjmExports.cs:572-590 (2b6bd5a 2026-07-28) | GPL-2.0+ | missing; O libs/ajm.cpp:1186-1232 | S | L; replug check | e4-now | decode jobs silently dropped today |
| SS36 | sceAmprCommandBufferWaitOnAddress (V7GQTEeUfhw), sceAmprMeasureCommandSizeWaitOnAddress (jIlc4p5dSD0): non-_04_00 forms (compare <= 3 instead of <= 6) | Ampr/AmprExports.cs:613-642, 835-869, 1748-1769 (8feea60 2026-09-25) | GPL-2.0+ | missing; _04_00 forms exist: O libs/libAmpr.cpp:3050-3066, 2743-2748, 3668, 3688 | S | L | e4-now | stub measure 0 -> undersized APR command buffers |
| SS37 | scePlayGoSetLanguageMask (LosLlHOpNqQ) stores the mask; GetLanguageMask returns it | PlayGo/PlayGoExports.cs:680-702 (01ebab9 2026-06-23) | GPL-2.0+ | missing; O libs/libPlayGo.cpp:381-395 returns a constant | S | L | e4-now | round-trip of a title setting |
| SS38 | sceRtcGetCurrentAdNetworkTick (LN3Zcb72Q0c), DebugNetworkTick (Ot1DE3gif84), RawNetworkTick (HWxHOdbM-Pg) -> current tick | shadPS4 rtc.cpp:390-507 (primary; sharp RtcExports.cs:163-242 is from flagged 56bf00e) | GPL-2.0+ | missing; O libs/libRtc.cpp:107-126 | S | L | e4-now | out-param tick |
| SS39 | sceAvPlayerSetAvailableBW (+7xJ+lFxmkQ) -> SetAvailableBandwidth | AvPlayer/AvPlayerExports.cs:884-900 (both NIDs on one method) | GPL-2.0+ | missing; O libs/avPlayer.cpp:1994-2005 | S | L | e4-now | param validation/state kept |
| SS40 | sceFontGetKerning (sDuhHGNhHvE): four zero floats at arg4; null -> invalid argument | Font/FontExports.cs:409-434 (b4584f8 2026-09-22) | GPL-2.0+ | missing | S | L | e4-now | out-param; stbtt kerning could follow later |
| SS41 | scePadIsRemoteController (fCWdlnmB1Ks): *out (1 byte) = 0; INVALID_HANDLE / 0x80920001 | Pad/PadExports.cs:816-839 (e17fb6f 2026-09-27) | GPL-2.0+ | missing | S | L | e4-now | out-param |
| SS42 | Rtc calendar exports: CompareTick, GetDosTime, SetDosTime, TickAddMonths, TickAddYears | clean-room from the public FAT date/time format and calendar rules; sharp's code is provenance-flagged (SS64); shadPS4 rtc.cpp:55-67,578-596,913-930,1070-1180 has defects (CompareTick returns 1/0, GetDosTime ORs into an uncleared out, TickAddMonths converts the destination tick) | own | missing | S | L | later | out-params; not "well sourced" from either repo |
| SS43 | SaveData memory v1: sceSaveDataSetupSaveDataMemory (v7AAAMo0Lz4), Get (7Bt5pBC-Aco), Set (h3YURzXGSVQ) | sharp aliases them to v2 (SaveDataExports.cs:617-624) - wrong: shadPS4 savedata.h:129-172 gives (userId, size, param*) and (userId, buf, size, offset) | GPL-2.0+ | missing | M | M | later | port v1 on the shadPS4 signatures over our memory store, not sharp's alias |
| SS44 | sceSaveDataMount (32HQAQdwM2o), Mount2 (0z45PIH+SNI), Mount5 (xz0YMi6BfNk) | sharp routes all to the Mount3 layout (SaveDataExports.cs:254-261); shadPS4 OrbisSaveDataMount2 (savedata.cpp:206-213) has no systemBlocks, so mountMode is at +0x18 not +0x20 | GPL-2.0+ | missing | M | M: layout errors corrupt mount mode | later | Mount5 layout unknown |
| SS45 | sceSaveDataGetSaveDataCount, GetMountedSaveDataCount, GetAllSize, IsMounted, Delete5 | SaveData/SaveDataExports.cs:267-283, 325-358, 508-533, 566-615 | GPL-2.0+ | missing | S | M: out-param positions are sharp-only (shadPS4 declares them without params); sharp Delete reads dirName at +0x08, OURS/shadPS4 at +0x10 (libSaveData.cpp:212-220) | later | unverified ABI |
| SS46 | scePadGetExtControllerInformation (hGbf2QTBmqc) | Pad/PadExports.cs:296-325 | GPL-2.0+ | missing | S | M: layout sharp-only | later | out-param |
| SS47 | sceNetGetMemoryPoolStats, sceSslGetMemoryPoolStats, sceHttp2GetMemoryPoolStats | Network/NetExports.cs:1093-1110, SslExports.cs:58-79, Http2Exports.cs:147-169 | GPL-2.0+ | missing | S | L | later | out-params |
| SS48 | Http2 CreateCookieBox (positive id), SetCookieBox, SetMinSslVersion; Http sceHttpsLoadCert; Ssl sceSslClose; Rudp PollCreate (positive id)/PollWait | Network/Http2Exports.cs:227-330, HttpExports.cs:161-175, SslExports.cs:82-90, RudpExports.cs:24-100 | GPL-2.0+ | missing | M | L | later | ids/err codes |
| SS49 | libSceVideodec v1: CreateDecoder writes a handle; Decode/Flush OK without picture; Delete | Codec/CodecExports.cs:86-118 | GPL-2.0+ | missing | S | L | later | handle out-param |
| SS50 | TextToSpeech2Open -> NOT_IMPLEMENTED; DeviceServiceQueryDeviceInfo_ -> NOT_FOUND; Hmd2Initialize -> NOT_FOUND | Stubs/GameServiceStubs.cs:157-163, 240-260 | GPL-2.0+ | missing (KytyPS5 has libDeviceService/libHmd2 - other agent) | S | L | later | error returns (OrbisGen2Result values not checked) |
| SS51 | sceAudioInGetSilentState | Audio/AudioInExports.cs:10-17 returns 0x80260101 only because sharp cannot open AudioIn | GPL-2.0+ | missing; OURS opens AudioIn ports (libs/audio.cpp:1542-1580) so needs its own answer | S | L; replug check | later | own implementation needed |
| SS52 | sceVideoOutSetBufferAttribute (i6-sR91Wt-4), sceVideoOutRegisterBuffers (w3BY+tAEiQY) (PS4 v1 forms) | VideoOut/VideoOutExports.cs:1319-1340, 1444-1500 | GPL-2.0+ | missing; v2 forms exist (O libs/libVideoOut.cpp:17-18) | M | M: presenter buffer registration | later | GPU-adjacent, not CPU-testable |
| SS53 | scePsmlMfsrGetDispatchMfsrPacket1000/1100 (s2psNHUIdjk, 94iBp3KvIuI) clear the packet buffer | Psml/PsmlExports.cs:284-322 (96fde57) | GPL-2.0+ | missing; the 900 variant (RUNLFro+qok) is registered as Psml::PsmlDispatch (O libs/libPsml.cpp:344), so 1000/1100 could alias it | S | M: GPU packet | later | GPU-adjacent, needs a GPU check |
| SS54 | libfmod uPLTdl3psGk (FMOD System::setOutput) override poking fmod object offsets 0x08/0x116D0/0x116D4 | Audio/FmodCompatExports.cs:14-45 | GPL-2.0+ | missing | S | H: patches a title-bundled library's internals; one fmod build | later | hack |
| SS55 | Font text-string state (sceFontText*, 11506fc Font part) | Font/FontExports.Text.cs (11506fc 2026-10-31) | GPL-2.0+ | not compared (NIDs registered in OURS) | M | L | later | unverified |
| SS56 | libSceAudioPropagation stubs (33): ZQXE-xS6MTE WXMhENV2NcA i687TNRF+hw d84otraxt2s wkseM3LWPuc -wsUTr31yeg PBcrVpEqUVY eEeKqFeNI3o G+QLTfyLMYk aKJZx7wCma8 3aEY9tPXGKc hhz9pITnC8k SoKPzY1-3SU tKSmk2JsMAA 5vzOS2pHMFc MNmGapXrYRs i-0aUex3zCE JZIkSbmt2BE tL2AEPejVQE 2BSFmuKtRss 0r2+9UTg1BA BbOT4vBwAjs gCmQm6dvMxw GrA9ke1QT+E x5VPqg5iyAk ile38Gl-p5M cMl3u+7QBBM 3B9IabLByyM B2KI2AachWE VlBT16890mA XKCN4gpeYsM S0JwP2AFTTE b-dYXrjSNZU | Audio/AudioPropagationExports.cs:55-166 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS57 | libSceAcm stubs (5): WeZOIm8+8WI Mk1xvQXIdkk A5NXCXK5Gfc S3BPrjCfZ90 uqDIauipRbo | Acm/AcmExports.cs:106-143 (4b8d455) | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS58 | libSceSaveData stubs (8): hsKd5c21sQc v-AK1AxQhS0 ZkZhskCPXFw l1NmDeDpNGU Wz-4JZfeO9g dQ2GohUHXzk eBSSNIG6hMk 52pL2GKkdjA | SaveData/SaveDataExports.cs:216-248, 551-561 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only (Initialize/2 only create the root dir) |
| SS59 | libSceRtc stubs (2): LlodCMDbk3o sceRtcInit, 8SljQx6pDP8 sceRtcEnd | shadPS4 rtc.cpp:103-105, 686-688 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS60 | libSceVoiceQoS stubs (3): Trpt2QBZHCI FuXenJLkk-c +0lOiPZjnBI | Voice/VoiceQoSExports.cs:20-50 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS61 | libSceBluetoothHid stubs (3): tul3-GzejQc 4FUZ+c52d2k 4Ypfo9RIwfM (0 by default; env experiments) | Pad/BluetoothHidExports.cs:37-75 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS62 | libSceSystemService stubs (2): x1UB9bwDSOw DisableMusicPlayer, 9kPCz7Or+1Y ReenableMusicPlayer | SystemService/SystemServiceExports.cs:48-60 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS63 | single-NID stubs: cTGkc6-TBlI sceNetTerm, BQ3tey0JmQM sceCommonDialogIsUsed, FzQS6DREDfk sceSharePlayProhibitController (INVALID_ARGUMENT only for arg > 1), UOjiprYwVNw sceTextToSpeech2Initialize, 84fDxStrG44 / 9ddRUOV8Q5A DeviceService Initialize/GetEventState, PZSoY8j0Pko scePadGetFeatureReport, yN7Jhuv8g24 sceAvPlayerVprintf, DxGyV8dtOR8 sceAudioOut2ContextBedWrite, i1393UBWu1U Json setGlobalSpecialFloatHandler (error only for null this) | files as in s-only.tsv | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| SS64 | sharp Rtc helpers from 56bf00e (CompareTick, Get/SetDosTime, TickAddMonths/Years, network ticks, Init/End) | Rtc/RtcExports.cs (56bf00e 2026-07-13 "[RTC] Port core rtc helpers from PS5 3.20 libs") | GPL-2.0+ | - | - | - | skip: provenance (commit says ported from PS5 3.20 firmware libs) | use SS38/SS42/SS59 instead |
| SS65 | sceAudioOut2UserGetSupportedAttributes (iE8trxPKnAg) masks 0x1F/0x3FFF | Audio/AudioOut2Exports.cs:1183-1215 | GPL-2.0+ | missing | - | - | skip: provenance (comment :1196-1198 derives the masks from attribute ids that "exist in the header") | - |
| SS66 | SaveDataDialog open param: mode at +0x34, userData at +0x70 | 4d56978 2026-10-10 | - | O libs/dialog.cpp:323-338 | - | - | skip: already match (dialog.cpp:323-338) | - |
| SS67 | Per-slot block count in mount info and search | 4d56978 | - | O libs/libSaveData.cpp:345-390, 670-675, 1169-1193 | - | - | skip: already match (libSaveData.cpp:345-390) | residual: no 48-block floor; a slot without a record reports the max |
| SS68 | SetParam keeps the slot's other metadata | 4d56978 | - | O .param/.blocks sidecars are separate files, libSaveData.cpp:1149-1161, 410-428 | - | - | skip: already match (libSaveData.cpp:1149-1161) | - |
| SS69 | NP reachability: signed out / UNAVAILABLE | 4d56978, 9eef395 | - | O libs/network.cpp:4678-4699, 4786-4799 | - | - | skip: already match (network.cpp:4678-4699) | - |
| SS70 | sceRtcConvertLocalTimeToUtc on non-UTC hosts | 341c2a0 | - | O libs/libRtc.cpp:172-182 (offset arithmetic) | - | - | skip: already match (libRtc.cpp:172-182) | - |
| SS71 | sceNetHtonl/Htons/Ntohl/Ntohs return the converted value | a8be1da | - | O libs/libNet.cpp:172-186 | - | - | skip: already match (libNet.cpp:172-186) | - |
| SS72 | sceNetInetPton | 7a108c6 | - | O libs/network.cpp:1508-1528 | - | - | skip: already match (network.cpp:1508-1528) | bad family: OURS EAFNOSUPPORT (BSD-like), sharp 0 |
| SS73 | Notice skip flag written as one byte | 3c500d2 | - | O libs/libSystemService.cpp:234-244 (bool*) | - | - | skip: already match (libSystemService.cpp:234-244) | - |
| SS74 | New touch id per touchpad contact | c60b57a | - | O libs/controller.cpp:1040-1044 | - | - | skip: already match (controller.cpp:1040-1044) | - |
| SS75 | Pad handle 0 accepted before first open (b4b9501), rejected after (ac8ffc3) | sharp HEAD dropped both: PadSessionRegistry.cs:97-103 (9e19412) only knows opened handles | - | O libs/controller.cpp:489-492 rejects 0 | - | - | skip: already match (controller.cpp:489-492) | - |
| SS76 | scePlayGoGetLocus BAD_CHUNK_ID for unknown ids (enumeration terminator) | b4b9501 | - | O libs/libPlayGo.cpp:188-194 | - | - | skip: already match (libPlayGo.cpp:188-194) | see SS18 |
| SS77 | AudioOut2 queue level written as u32, available queues reported | e13cb28 | - | O libs/libAudio2.cpp:673-712 | - | - | skip: already match (libAudio2.cpp:673-712) | - |
| SS78 | Float PCM endpoint conversion | 3585519 | - | O keeps float as float, libs/audio.cpp:558-570 | - | - | skip: already match (audio.cpp:558-570) | - |
| SS79 | AudioOut2 MasteringInit / Set3DLatency succeed | 4b8d455 | - | O libs/libAudio2.cpp:1016-1052 | - | - | skip: already match (libAudio2.cpp:1048-1052) | - |
| SS80 | sceAudioOutOutputs | 26c5029 | - | O libs/libAudio.cpp:125 | - | - | skip: already match (libAudio.cpp:125) | - |
| SS81 | Ajm Opus decode, Gen5 codec type 24 accepted | 660df73, d3600c9 | - | O libs/ajm.cpp:134, 415-416, 603 | - | - | skip: already match (ajm.cpp:415-416) | - |
| SS82 | sceAppContentDownloadDataGetAvailableSpaceKb | 2ced3af | - | O libs/libAppContent.cpp:131-163 | - | - | skip: already match (libAppContent.cpp:131-163) | - |
| SS83 | MsgDialog RUNNING state, buttonId 1, ProgressBar exports | de13735 | - | O libs/dialog.cpp:~581-650, libDialog.cpp:126-128 | - | - | skip: already match (dialog.cpp:581-596) | error guards differ: SS12 |
| SS84 | RemotePlay initialised + disconnected | 7b95016 | - | O libs/libNet.cpp:4088-4105 | - | - | skip: already match (libNet.cpp:4088-4100) | - |
| SS85 | UDS property object/array (19) + GetAddcontEntitlementInfoList | s-only rows | - | registered, two-line LIB_FUNC: O libs/libNet.cpp:3088-3138, 1722-1723 | - | - | skip: already match (libNet.cpp:3088-3138) | inventory parser miss |
| SS86 | NpAuth (9) and Http2 (5) name-only s-only rows | s-only rows | - | O libs/libNet.cpp:1972-1979, libNp.cpp:62, libNet.cpp:1358-1383 | - | - | skip: already match (libNet.cpp:1972-1979) | inventory had no NID |
| SS87 | VideoOutGetOutputStatus before buffer registration | b1ec286 | - | - | - | - | in e4 / done | brief |

## 3. Port specs for e4-now rows

Common: insert next to the named LIB_DEFINE; S paths are `src/SharpEmu.Libs/...` @514d766. Audio-path rows (SS34, SS35)
need the DualSense replug check (exp 0372 s6n0372.sh + replug0372.sh, then physical replug and a DS4) before shipping.

**SS01 sceSaveDataSyncSaveDataMemory** (wiT9jeC7xPw, libSceSaveData). `int (const SaveDataMemorySync* p)` where p =
{int32 userId; uint32 slotId; uint32 option; reserved[28]} (shadPS4 savedata.cpp:199-204). Behaviour: p null ->
SAVE_DATA_ERROR_PARAMETER; flush memory (OURS already writes through on Set, so nothing to do); queue
`queue_save_data_event(3 /*SAVE_DATA_MEMORY_SYNC*/, p->userId, title_id(our TITLE_ID), dir "sce_sdmemory")`; return OK.
Add a mutex around g_save_data_events (push in queue_save_data_event, pop in GetEventResult). Source:
S SaveData/SaveDataExports.cs:1571-1609; shadPS4 savedata.cpp:1637-1665. Ours: replace libs/libSaveData.cpp:1061-1067,
add `constexpr uint32_t SAVE_DATA_EVENT_TYPE_MEMORY_SYNC_END = 3;` near :244. Test: CPU unit test calls Setup2, Set2,
Sync, then GetEventResult -> OK with type 3, user id echoed; second GetEventResult -> NOT_FOUND.

**SS02 sceSaveDataSetupSaveDataMemory2** (oQySEUfgXRA). `int (const SaveDataMemorySetup2*, SaveDataMemorySetupResult*)`.
Behaviour: existed = bytes in memory.dat before this call (0 when the file is absent; if already set up in this
process, the size set up then); then grow the store to max(existed, memory_size); write result->existed_memory_size =
existed (before growing). Remove the 0x10000 pre-size of g_save_data_memory (libSaveData.cpp:248) or track a separate
`g_save_data_memory_existed`. Source: S SaveDataExports.cs:1495-1551 (result written before mutating, :1530-1545);
shadPS4 savedata.cpp:1580-1603. Ours: libs/libSaveData.cpp:693-718 (load), 741-769. Test: temp KYTY_BC5_SAVEDATA_DIR,
no file -> existed 0; Set2 then a fresh process-state (reset globals) -> existed = file size.

**SS03 sceNetResolverDestroy / sceNetResolverGetError** (kJlYH5uMAWI, J5i3hiLJMPk, libSceNet). `int Destroy(int rid)`:
valid id -> free the slot (m_resolvers[rid].used=false, name cleared), OK; else NET_ERROR_EBADF (sharp 0x80410109).
`int GetError(int rid, int* status)`: status null -> NET_ERROR_EINVAL (0x80410116); bad id -> EBADF; else *status =
resolver's last error (OURS keeps none: write 0), OK. Set the net errno as NET_CALL does. Source:
S Network/NetExports.cs:1245-1282. Ours: add Network::ResolverDestroy next to libs/network.cpp:423-446, wrappers in
libs/libNet.cpp near :114-121, LIB_FUNC in LIB_DEFINE(InitNet_1_Net) libs/libNet.cpp:189-224. Test: 40 x
(Create, Destroy) all succeed; 33 Creates without Destroy -> 33rd ENOSPACE; GetError(valid) writes 0.

**SS04 sceSaveDataTransferringMount** (WAzWTZm1H+I, RjMlsR8EXrw). Behaviour: title_id null or dir null -> PARAMETER;
path = _SaveData/<mount->title_id>/<dir>; if absent -> SAVE_DATA_ERROR_NOT_FOUND (no directory created); else mount it
read-only in a free slot (BUSY/MOUNT_FULL as Mount3), mount_status 0. Source: S SaveDataExports.cs:920-963 with
MountSaveData 825-918 (mode READ_ONLY); shadPS4 savedata.cpp:1685-1703. Ours: libs/libSaveData.cpp:850-883. Test: no dir
-> NOT_FOUND and no dir created; pre-created dir under another title id -> OK, /savedataN mounted.

**SS05 sceUsbdHandleEventsTimeout** (+wU6CGuZcWk, libSceUsbd). `int (const struct {int64 sec; int64 usec;}* tv)`. null,
sec < 0, usec outside [0, 1e6) or overflow -> 0x80240002 (SCE_USBD_ERROR_INVALID_PARAM per sharp); else sleep
sec*1e6+usec microseconds, return OK. Source: S Usbd/UsbdExports.cs:64-102. Ours: libs/libUsbd.cpp:673-682 (LIB_FUNC
:1161). Test: {0, 5000} returns OK after >= 5 ms; {0, 1000000} -> error.

**SS06 notice-screen skip flag** (Q3utJvma4Mo set, 3RQ5aQfnstU get, libSceSystemService). `int Set(int flag)` stores
flag != 0 (atomic); `int Get(bool* v)` writes it (one byte), PARAMETER on null. Source: S
SystemService/SystemServiceExports.cs:62-107 (eb252af). Ours: libs/libSystemService.cpp:234-256. Test: Get -> 0; Set(1);
Get -> 1; Set(0); Get -> 0.

**SS18 scePlayGoGetLocus bad entry** (uWIYLFkkwqk). Before returning PLAYGO_ERROR_BAD_CHUNK_ID for entry i, write
out_loci[i] = PLAYGO_LOCUS_NOT_DOWNLOADED. Source: S PlayGo/PlayGoExports.cs (16a2131 hunk at former :424-430). Ours:
libs/libPlayGo.cpp:188-194. Test: ids {0, 9999} -> BAD_CHUNK_ID, loci = {LOCAL_FAST, NOT_DOWNLOADED}.

**SS22 scePadOpenExt** (WFIiSfXGUq8, libScePad). `int (int user_id, int type, int index, const void* param)`. As PadOpen
(controller.cpp:1220-1243) but the personal-port check accepts type 0, 1 or 2; same handle numbering; same 0x80920001
for bad args. Source: S Pad/PadExports.cs:91-96, 132-180 (typeAccepted :149-151). Ours: add next to
libs/controller.cpp:1205-1243, LIB_FUNC in libs/libPad.cpp:301-326. Test: (1000,1,0) -> 1, (1000,0,0) -> 1, (1000,3,0)
-> 0x80920001, (0xff,16,0) -> 1.

**SS23 sceNetRecv / sceNetRecvfrom** (9wO9XrMsNhc, 304ooNZxWDY). `int64 Recv(int s, void* buf, uint64 len, int flags)`,
`int64 Recvfrom(int s, void* buf, uint64 len, int flags, void* addr, uint32_t* addrlen)`. Wrap Net::Recv/Recvfrom
(network.cpp:2182-2230) with an int64 variant of FinishSocketCall (libNet.cpp:70-78: negative -> map posix errno to
NET_ERROR, store in net errno, return it). Source: S Network/NetExports.cs:253-355 (flags 0x2 PEEK, 0x80 DONTWAIT
semantics). Ours: libs/libNet.cpp:80-104 + LIB_DEFINE :189-224. Test: two UDP sockets on 127.0.0.1 via NetSocket/NetBind;
host sendto; NetRecvfrom returns the bytes and the sender address; NetRecv on an empty non-blocking socket -> EAGAIN code.

**SS24 sceNetCtlRegisterCallbackV6** (1NE9OWdBIww, libSceNetCtl). `int (NetCtlCallback func, void* arg, int* cid)` ->
NetCtl::NetCtlRegisterCallback (network.cpp:4013-4033). Source: S Network/NetCtlExports.cs:149-154. Ours:
libs/libNet.cpp:1395-1406. Test: register -> cid written, OK; NULL func -> NET_CTL_ERROR_INVALID_ADDR.

**SS25 Json aliases** (libSceJson2). LIB_FUNC: t6AHhkWu4mY -> JsonArrayCtor; MIyMPw7YTGM -> JsonArrayDtor; eG9E9M6XvTM
-> JsonStringCtor; Ui7YFnSTCBw -> JsonStringDtor; 9niNrXsF3Bc -> JsonArrayIterDtor; iAIYn4oAWvI -> JsonArrayIterDeref;
0YqYAoO-+Uo -> JsonValueIndexUInt; FIjXN2TkuTs -> new `JsonValue* KYTY_SYSV_ABI JsonValueClearExport(JsonValue* self)`
that saves parent/rootparam, calls JsonValueClear (libJson2.cpp:224-240, which nulls them), restores them, returns
self. Source: S Json/JsonExports.cs:489-494, 531-548, 667-686, 777-782, 807-812; JsonValueExports.cs:189-198. Ours:
LIB_DEFINE(InitNet_1_Json2) libs/libJson2.cpp:1301-1391. Test: C2-construct an Array and String in a host buffer, push
values, D2-destroy (no leak under ASan); getValue(1) on [1,2,3] -> value 2; clear() on an object member -> type null,
parent kept.

**SS26 Json iterator ops**. JsonIterHandle {void* impl} (libJson2.cpp:1129-1136). TAPTWYaYf8Q/JSg1MSo7NKE `iterator()`:
self->impl = nullptr, return self. IaIvX3kgyb0/Hdc3DSIsG2I `iterator(const iterator& o)`: impl = o.impl ? new
JsonArrayIter{o.vec, o.index} registered via JsonIterRegister : nullptr. T3WReElX4BY `operator=(o)`: release own impl
(JsonIterRelease + delete), then copy as above, return self. GEylwSsiGG8 `operator++(int)`: rdi = hidden result,
rsi = this: result gets a copy at the old position, this advances (as JsonArrayIterNext); return result.
43MESLndGvQ `advance(size_t n)`: index = min(index + n, size). Source: S Json/JsonExports.cs:731-764, 827-850 and
helpers to :910 (b307b2f). Ours: after libs/libJson2.cpp:1224. Test: parse [1,2,3]; begin/end; copy begin, post-inc
the copy, deref old/new -> 1/2; advance(5) == end; destroy all copies (registry has no leaks/double frees).

**SS27 sceAppContentGetAddcontInfoList** (xnd8BJzAxmk). `int (uint32 serviceLabel, void* list, uint32 listNum,
uint32* hitNum)`. list null or listNum 0: hitNum null -> APP_CONTENT_ERROR_PARAMETER, else *hitNum = 0; otherwise
*hitNum = 0 if non-null; OK. Source: S AppContent/AppContentExports.cs:48-68; shadPS4 app_content.cpp:269-295. Ours:
LIB_DEFINE(InitAppContent_1) libs/libAppContent.cpp:258-265. Test: hitNum preset 0xFFFFFFFF -> 0; all-null -> PARAMETER.

**SS28 sceNpCommerceDialogOpen2** (IXmfUaze9So). LIB_FUNC to NpCommerceDialogOpen (libNpCommerceDialog.cpp:58-77).
Source: S Np/NpCommerceExports.cs:41-46. Ours: libs/libNpCommerceDialog.cpp:139-145. Test: Initialize, Open2 -> OK,
UpdateStatus -> FINISHED, GetResult -> OK.

**SS29 sceSaveDataUmount / sceSaveDataGetProgress** (BMR4F-Uek3E, ANmSWUiyyGQ). `int Umount(const SaveDataMountPoint*)`
-> SaveDataUmount2(0, mp). `int GetProgress(float* p)`: null -> PARAMETER; *p = 1.0f (all OURS operations finish in
the call); OK. Source: S SaveDataExports.cs:263-265, 535-549; shadPS4 savedata.cpp:1705-1708, 1096-1108. Ours:
libs/libSaveData.cpp:885-910, LIB_DEFINE :1290-1316. Test: Mount3 then Umount -> slot free (17 mount/umount cycles OK).

**SS30 sceSystemServiceGetMainAppTitleId** (4veE0XiIugA). `int (char* out /*16 bytes*/)`: null ->
SYSTEM_SERVICE_ERROR_PARAMETER; copy TITLE_ID (Loader::SystemContentParamSfoGetString as libSaveData.cpp:254-261),
at most 15 chars + NUL; OK. Source: S SystemService/SystemServiceExports.cs:109-133. Ours: LIB_DEFINE(InitSystemService_1)
libs/libSystemService.cpp:570-584. Test: with a param.sfo stub TITLE_ID "PPSA01234" -> "PPSA01234\0".

**SS31 sceNpEntitlementAccessGetGameTrialsFlag / GetEntitlementKey** (y7JD1gfwyfA, 5LiMEPuW0DQ).
`int GetGameTrialsFlag(uint32* f)`: null -> 0x817D0002; *f = 0. `int GetEntitlementKey(uint32 service, const
NpUnifiedEntitlementLabel* label, uint8 key[16])`: label or key null -> 0x817D0002; zero key; OK when label is in
NP_ENTITLEMENT_ACCESS_ADDON_LIST (libNet.cpp:1570-1574), else 0x817D0007. Source: S Np/NpEntitlementAccessExports.cs:
98-116, 223-252. Ours: libs/libNet.cpp:1716-1724. Test: listed label -> OK + zero key; other label -> 0x817D0007.

**SS32 sceNpAuthGetAuthorizedAppCode** (IDX0S5EsEh4). `int (int reqId, const void* param, void* out)`: unknown request
-> NP_AUTH_ERROR_REQUEST_NOT_FOUND; aborted -> ABORTED; else np_auth_complete_signed_out(request) (SIGNED_OUT for sync, 0 +
result for async), no out writes (layout unknown). Source: S Np/NpAuthExports.cs:154-158, 180-217. Ours: copy of
NpAuthGetAuthorizationCodeV3 libs/libNet.cpp:1908-1940; LIB_DEFINE :1971-1980. Test: CreateRequest, call -> 0x80550006.

**SS33 sceNpSessionSignalingCreateContext2 / RequestPrepare** (aBuX0PX-T7I, r8mVMwlafF8). CreateContext2 returns an
incrementing id starting at 1 (args ignored); RequestPrepare returns NP_ERROR_SIGNED_OUT 0x80550006. Source: S
Np/NpSessionSignalingExports.cs:24-41. Ours: libs/libNet.cpp:1534-1539. Test: two calls -> 1, 2; RequestPrepare -> error.

**SS34 sceAudioOut2LoContextGetQueueLevel** (Q8DZkKQ-SYc). LIB_FUNC to AudioOut2ContextGetQueueLevel
(libAudio2.cpp:673-712). Source: S Audio/AudioOut2Exports.cs:615-621. Ours: LIB_DEFINE(InitAudio_1_AudioOut2)
libs/libAudio.cpp:139-168. Test: unknown context -> level 0, available 4. Replug check before ship.

**SS35 sceAjmBatchJobRunBufferRa / RunSplitBufferRa** (ElslOCpOIns, 7jdAXK+2fMo). LIB_FUNC to AjmBatchJobRun /
AjmBatchJobRunSplit (ajm.cpp:1186-1232); the 10th (stack) return-address argument is ignored by the SysV callee.
Source: S Audio/AjmExports.cs:572-590. Ours: libs/libAudio.cpp:552-553 block. Test: same batch built through RunBufferRa
and Run gives identical batch buffers. Replug check before ship.

**SS36 Ampr non-_04_00 wait-on-address** (V7GQTEeUfhw, jIlc4p5dSD0). LIB_FUNC V7GQTEeUfhw -> CommandBufferWaitOnAddress
(libAmpr.cpp:3050-3066), jIlc4p5dSD0 -> MeasureCommandSizeFixed32 (:2743-2748, 0x20 covers the largest record);
optional: reject compare > 3 for the new form (sharp :1748-1757). Source: S Ampr/AmprExports.cs:613-642, 835-869.
Ours: LIB_DEFINE(InitAmpr_1_Ampr) libs/libAmpr.cpp:3648-3744. Test: measure -> 0x20; append into a host command buffer
and run the CPU executor: blocks until *addr matches.

**SS37 scePlayGoSetLanguageMask** (LosLlHOpNqQ). `int (int handle, uint64 mask)`: validate_handle; store; OK.
GetLanguageMask (libPlayGo.cpp:381-395) returns the stored mask (default PLAYGO_LANGUAGE_MASK_ALL). Source: S
PlayGo/PlayGoExports.cs:680-702. Ours: libs/libPlayGo.cpp:478-496. Test: bad handle -> BAD_HANDLE; set 0x5, get 0x5.

**SS38 Rtc network ticks** (LN3Zcb72Q0c, Ot1DE3gif84, HWxHOdbM-Pg). LIB_FUNC each to RtcGetCurrentNetworkTick
(libRtc.cpp:122-126). Source: shadPS4 rtc.cpp:390-507. Ours: LIB_DEFINE(InitRtc_1_Rtc) libs/libRtc.cpp:566-596. Test:
each tick within 1 s of GetCurrentTick.

**SS39 sceAvPlayerSetAvailableBW** (+7xJ+lFxmkQ). LIB_FUNC to AvPlayerSetAvailableBandwidth (avPlayer.cpp:1994-2005).
Source: S AvPlayer/AvPlayerExports.cs:884-900. Ours: LIB_DEFINE(InitAudio_1_AvPlayer) libs/libAudio.cpp:588-610. Test:
null handle -> AVPLAYER_ERROR_INVALID_PARAMS; min > max -> same.

**SS40 sceFontGetKerning** (sDuhHGNhHvE). `int (FontHandle font, uint32 pre, uint32 code, float kerning[4])`: kerning
null -> error (sharp INVALID_ARGUMENT; OURS font errors use -1 style, keep OURS convention); write 4 x 0.0f; OK. Source:
S Font/FontExports.cs:409-434. Ours: LIB_DEFINE(InitFont_1) libs/libFont.cpp:2218-. Test: zeros written.

**SS41 scePadIsRemoteController** (fCWdlnmB1Ks). `int (int handle, uint8* out)`: ControllerIndexFromHandle < 0 ->
PAD_ERROR_INVALID_HANDLE (controller.cpp:37); out null -> 0x80920001; *out = 0; OK. Source: S Pad/PadExports.cs:816-839.
Ours: next to controller.cpp:1321-1353, LIB_FUNC libs/libPad.cpp:301-326. Test: handle 1 -> 0 written; handle 0 ->
INVALID_HANDLE.

## 4. Totals

87 rows: e4-now 27 (SS01-06, SS18, SS22-41); later 36 (SS07-17, SS19-21, SS42-63); skip: provenance 2 (SS64-65);
skip: already match 21 (SS66-86); in e4 / done 1 (SS87).
e4-now size: 27 S, about 2-3 days with CPU unit tests.
later size: 25 S + 9 M + 2 L, about 1.5 + 4.5 + 6 = 12 days (Ngs2 mixer SS07 and trophy unlocks SS14 dominate; SS14 may
already be covered by the KytyPS5 agent).
