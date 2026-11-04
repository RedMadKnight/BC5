# KS -- KytyPS5 @ dfec14a vs OURS: system-service libraries

## 1. Method

Read-only survey, 2026-11-03/04. For every shared file in scope I ran `diff --strip-trailing-cr -w $R/kps5/src/<f> OURS/<f>`
and read every KytyPS5-only hunk (libSaveData.cpp, saveDataMountSlots.h, libNet.cpp, network.cpp/.h, libJson2.cpp,
libPad.cpp, controller.cpp/.h, padData.h, ime*.cpp/.h, dialog.cpp/.h, libDialog.cpp, libWebBrowserDialog.cpp,
libPsml.cpp, libPlayGo.cpp, libRtc.cpp, libShare.cpp, libUsbd.cpp, libVideoOut.cpp). Where the files differ by name
(KytyPS5 libTrophy.cpp vs our libNet.cpp NpTrophy2/UDS namespaces; KytyPS5 libNpEntitlementAccess.cpp vs our libNet.cpp;
KytyPS5 libCes.cpp vs our libNet.cpp LibCes; KytyPS5 libNet.cpp NpCommerce/GameLiveStreaming/SharePlay vs our
libNpCommerceDialog.cpp/libGameLiveStreaming.cpp/libSharePlay.cpp; KytyPS5 libUsbd.cpp vs our shadPS4 libUsbd.cpp) I
joined the two NID inventories (`$R/kps5-nids.tsv`, `$R/ours-nids.tsv`, helper `KS-scripts/join.py`, `rjoin.py`) and
compared per NID. Namespaces were cut out with `KS-scripts/nsx.py` and diffed. Commits read in full: 22a9392, 52c80be,
4b0282e/dfec14a (stat only, in flight), 15452a5, a06e356, 22b3178, 3c77472 (in diff), f12fc20, 87e815b, a875d1b,
99044c7, 66e21a6 (stat), 39faa62, 02b17af/651ef73 (stat + libPsml.cpp), 3688412. Introducing commits were looked up
with `git log -S` over dfec14a; everything that resolves to the graft root 4644c52 is written "pre-4644c52 (history not
in clone)". Our host is Linux (OURS CMakeLists.txt:63 KYTY_PLATFORM_LINUX), which matters for the network rows: our
socket layer is Windows-only and answers ENOSYS on Linux (network.cpp:1857..2362), KytyPS5 has a POSIX backend.
Not compared per export: the Json2 implementations as a whole (two independent implementations; I read only the
KytyPS5-only hunks), and KytyPS5's TextEditEngine internals (imeCommon.cpp) against our inline IME editing.
Side note found while checking (not a KytyPS5 port): OURS registers stub `sceImeOpen`/`sceImeClose`/... in
libIme.cpp:268-291 (library "libSceIme") next to the real ones in ime.cpp (library "Ime"); which one a title binds
depends on the import's library name -- worth a check by whoever owns IME.

All KytyPS5 code is GPL-2.0 (same as ours). Provenance problem found once: KS70 (Hmd2/VrTracker2 SDK-style structs).

## 2. Table

Ranked: correctness fixes to functions we have first, then missing functions with behaviour, then later items, then
registration-only, then skips. "K" = KytyPS5 repo `src/` at dfec14a; "O" = OURS `src/`.

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KS01 | Http2 SendRequestAsync/ReadDataAsync never trigger the caller's kqueue user event | K libs/libNet.cpp:837-845,1259-1264,1266-1288,1436-1473; a06e356 2026-11-01 "net: signal the event queue when Http2 async calls complete" | GPL-2.0 | differs: O libs/libNet.cpp:1132-1152,1300-1336 (kqueue_option ignored) | S | L: only adds an event | e4-now | hang: a title that waits on its equeue for Http2 completion blocks forever |
| KS02 | SaveData event queue pushed/popped without g_mount_mutex (Commit, Backup, GetEventResult) | K libs/libSaveData.cpp:1027-1028,1275-1276,1191; pre-4644c52 (history not in clone) | GPL-2.0 | differs: O libs/libSaveData.cpp:940,1123,1090-1095 (no lock; Umount2 896 does lock) | S | L | e4-now | data race on std::deque (save thread vs poll thread) -> crash |
| KS03 | SaveDataSyncSaveDataMemory: validate, flush, queue MEMORY_SYNC_END (type 3) event unless option==1, MEMORY_NOT_READY before setup | K libs/libSaveData.cpp:197-202 (struct),267,1151-1182; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:1061-1067 (log + OK), 244-246 (no type 3) | S | L-M: event appears where none did | e4-now | hang: titles that wait for the sync-end event via GetEventResult poll NOT_FOUND forever |
| KS04 | HttpCreateTemplate with NULL user agent | K libs/network.cpp:469; 87e815b 2026-10-23 "net: accept a NULL user agent in sceHttpCreateTemplate (Cyberpunk 2077)" | GPL-2.0 | differs: O libs/network.cpp:584 `std::string(user_agent)` | S | L | e4-now | crash (std::string from nullptr) |
| KS05 | Json2 JsonValueSetObject / JsonObjectAssign destroy the target before copying a source that may be the target or its descendant | K libs/libJson2.cpp:626-636,987-996; pre-4644c52 | GPL-2.0 | differs: O libs/libJson2.cpp:1033-1048 (Clear then copy), 911-917 (Dtor then CopyCtor) | S | L | e4-now | use-after-free on self/descendant assignment |
| KS06 | sceNetResolverDestroy (kJlYH5uMAWI) frees the resolver slot | K libs/libNet.cpp:127-129, libs/network.cpp:311-319,1445-1456; pre-4644c52 | GPL-2.0 | missing (O network.cpp:423-447 has no destroy; RESOLVERS_MAX 32 at :369) | S | L | e4-now | after 32 create/destroy cycles sceNetResolverCreate fails ENOSPACE (stub destroy frees nothing) |
| KS07 | sce_net_errno holds positive errno (result - NET_ERROR_EPERM + 1), not the 0x8041xxxx code | K libs/libNet.cpp:52-57 (FinishNetCall), 85-87; pre-4644c52 (22b3178 only adds a caller) | GPL-2.0 | differs: O libs/libNet.cpp:20-27 (NET_CALL stores result), 71-79 (FinishSocketCall stores net_error) | S | M: anything reading errno changes value | e4-now | titles test sce_net_errno == EWOULDBLOCK/EINPROGRESS; ours never matches |
| KS08 | PlayGoGetChunkId(list==NULL) returns the total chunk count; list!=NULL && entries==0 -> BAD_SIZE | K libs/libPlayGo.cpp:209-245 (224-234); pre-4644c52 | GPL-2.0 | differs: O libs/libPlayGo.cpp:236-266 (254-255: BAD_POINTER; NULL+0 -> count 0) | S | M: PlayGo flow of titles | e4-now | wrong result: a count query answers 0 chunks |
| KS09 | SetupSaveDataMemory2 existed_memory_size = size of the stored memory file, 0 when none | K libs/libSaveData.cpp:457-483,811-825; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:763-766 (reports g_save_data_memory.size(), >= 0x10000 always) | S | M: first title's memory-save init path | e4-now | wrong result: a fresh install looks like an existing save |
| KS10 | Pad: a stick/axis event that changes no button merges into the newest unread sample | K libs/controller.cpp:522-546; 39faa62 2026-10-27 "controller: merge stick and sensor events into the newest unread pad sample" | GPL-2.0 | differs: O libs/controller.cpp:859-875 (every Axis event, :963, pushes a sample; ring 64 at :104) | S | M: fewer samples from scePadRead | e4-now | input loss: a burst of axis events between two reads pushes unread button changes out of the 64-entry ring (motion/touch already merged in ours, :111-127) |
| KS11 | Psml Initialize answers NOT_TRINITY_MODE (0x8a810012) on a base PS5; Psml_mfsr2 Initialize answers NOT_AVAILABLE (0x8a8a0012), its 8 other exports NOT_INITIALIZED; Psml aliases fccGInHrj8A/94iBp3KvIuI | K libs/libPsml.cpp:40,120-130,494-503,505-603,614-624,641,645; NOT_TRINITY_MODE 651ef73 2026-10-29 "graphics: add experimental Pro mode and linear PSSR"; mfsr2 02b17af 2026-11-02 "libs: implement Psml_mfsr2 and the 1100 Psml exports" | GPL-2.0 | differs: O libs/libPsml.cpp:113-121 (OK always) while O libs/libKernel.cpp:1408-1417 says base PS5; mfsr2 missing | S | M: a title that used the PSSR path stops | e4-now | consistency: ours tells titles PSSR/MFSR2 exist on a base console, then dispatches nothing. Console behaviour per KytyPS5 only (unverified) |
| KS12 | NpGetAccountAge / NpGetAccountLanguage2 complete their request (signed out) instead of answering synchronously | K libs/network.cpp:4164-4177,4369-4407; 15452a5 2026-10-29 "np: separate PSN emulation from host networking" | GPL-2.0 | differs: O libs/network.cpp:4560-4575 (no request lookup), O libs/libNet.cpp:1430-1444 | S | L | e4-now | async request: ours returns SIGNED_OUT from the call and NpPollAsync then answers INVALID_ID (request never completed) |
| KS13 | SaveDataGetParam types 1-5 (title/subtitle/detail/user_param/mtime) and NOT_MOUNTED; SaveDataSetParam types 1-4 and NOT_MOUNTED, PARAMETER for null buf | K libs/libSaveData.cpp:126-139,1064-1118,1282-1333; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:1021-1027 (zero fill), 1129-1167 (type!=0 no-op; LOGF derefs p before null check :1139-1145) | S | L | e4-now | wrong result + null deref crash |
| KS14 | SaveDataDelete of a mounted save -> BUSY; honours del->title_id | K libs/libSaveData.cpp:1034-1062; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:946-983 (removes even when mounted, own title only) | S | M | e4-now | data loss: deletes files under an open mount |
| KS15 | SaveDataTransferringMount: mounts the given title's dir read-only, NOT_FOUND when absent, PARAMETER for null title_id | K libs/libSaveData.cpp:934-970; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:850-883 (own title, creates dir, created=1) | S | M: slot key must then include title (O saveDataMountSlots.h:17-29 keys by dir name) | e4-now | wrong result: a PS4-transfer probe always "finds" an empty save |
| KS16 | SaveDataGetMountInfo: PARAMETER for null, NOT_MOUNTED for an unknown mount point | K libs/libSaveData.cpp:1335-1358; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:1169-1193 (EXIT_NOT_IMPLEMENTED on null, OK+MAX when unmounted) | S | L | e4-now | abort on null; wrong result |
| KS17 | SaveData input checks: dir/title names must be one path component of [A-Za-z0-9_-.@] (PARAMETER), user_id<0 -> INVALID_LOGIN_USER, Mount3 create blocks 48..16384, Mount3 nulls -> PARAMETER, Search: NUL-terminated dir_name, dir_names_num w/o buffer | K libs/libSaveData.cpp:286-297,581-597,693-702,742-744,938-945,1037-1043; pre-4644c52 (22a9392 adds callers) | GPL-2.0 | differs: O libs/libSaveData.cpp:612-614 (EXIT on null), 497-520, 854, 949 (no name checks) | S | M: a title using another character in a dir name would now get PARAMETER (charset is KytyPS5's choice, not verified on a console) | e4-now | path traversal ("../") out of _SaveData; abort on null |
| KS18 | sceSaveDataConvert (2mfSRGdshtk) synchronous checks: PARAMETER (names, memory dirs, blocks 48..16384), INVALID_LOGIN_USER, NOT_FOUND, BUSY, EXISTS, NO_NEED_CONVERT (0x809F001E), BLOCKS_FEWER_THAN_SRC (0x809F0020) | K libs/libSaveData.cpp:234-242,1210-1258, errno.h:661-662; 22a9392 2026-10-25 "savedata: implement sceSaveDataConvert's synchronous checks" (test tests/SaveDataMemoryTests.cpp TestConvert) | GPL-2.0 | differs: O libs/libSaveData.cpp:1218-1234 (always NOT_FOUND) | S | M: the second title calls it before Mount3 (exp 0145); KytyPS5 ends in EXIT for a real conversion -- keep our NOT_FOUND there | e4-now | wrong result for existing saves (NO_NEED_CONVERT) |
| KS19 | UsbdHandleEventsTimeout sleeps 16 ms | K libs/libUsbd.cpp:13,27-34; pre-4644c52 | GPL-2.0 | differs: O libs/libUsbd.cpp:673-680 (returns at once) | S | L | e4-now | a guest USB event thread spins a core |
| KS20 | Stubs that answer OK and write nothing: GameLiveStreamingGetCurrentStatus2 (zeroed, user_id -1), GetSocialFeedbackMessagesCount (type 1..3, count 0), SharePlay init state + GetCurrentConnectionInfoA (zeroed, user ids -1), NpGetUserIdByAccountId (INVALID_ARGUMENT / SIGNED_OUT) | K libs/libNet.cpp:2783-2830 (GLS), 2850-2905 (SharePlay), libs/network.cpp:4332-4350; GLS/SharePlay pre-4644c52; UserIdByAccountId f12fc20 2026-10-31 "Stub missing SystemService / NpManager / NpWebApi2 imports (Palworld, PPSA23126)" | GPL-2.0 | differs: O libs/libGameLiveStreaming.cpp:223,268; O libs/libSharePlay.cpp:30; O libs/libNet.cpp:4162-4176; O libs/libNp.cpp:347 | S | L | e4-now | guest reads uninitialised memory (a garbage count or user id) |
| KS21 | NpCommerceDialog result carries param->user_data (result layout int32,bool,void*,reserved[32]); PARAM_INVALID for size!=128 / mode>5 / reserved!=0 | K libs/libNet.cpp:1563-1585,1609-1645; pre-4644c52 | GPL-2.0 | differs: O libs/libNpCommerceDialog.cpp:36-40 (no user_data field), 58-76, 109-126 | S | L | e4-now | title gets user_data NULL back |
| KS22 | NetCtlGetInfo: null info -> INVALID_ADDR, code outside 1..21 -> INVALID_CODE before NOT_CONNECTED | K libs/network.cpp:3947-3962; pre-4644c52 | GPL-2.0 | differs: O libs/network.cpp:4074-4084 (EXIT_NOT_IMPLEMENTED on null) | S | L | e4-now | abort on null |
| KS23 | NpAuthGetAuthorizationCodeV3/GetIdTokenV3 check req_id, param, size (INVALID_SIZE 0x80550302), client_id/secret/scope | K libs/libNet.cpp:1737-1755,1921-1980; 15452a5 2026-10-29 | GPL-2.0 | differs: O libs/libNet.cpp:1908-1969 (no checks) | S | L | e4-now | error codes for bad params |
| KS24 | SaveDataDialogUpdateStatus answers RUNNING once before FINISHED ("Some games require a RUNNING update before FINISHED") | K libs/dialog.cpp:441,450,464-477; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:388-401 (message modes finish at first poll; progress bar kept running -- keep that) | S | M: second title's save dialogs (F205 history) | e4-now | titles that need to see RUNNING |
| KS25 | Pad port state: NOT_INITIALIZED before scePadInit, ALREADY_OPENED on a second open, GetHandle NO_HANDLE when not open, Close releases | K libs/controller.cpp:1155-1212,1230-1281; pre-4644c52 | GPL-2.0 | differs: O libs/controller.cpp:1199-1262 (stateless), O libs/libPad.cpp:278 | S | M: titles that open twice now get an error | e4-now | API contract |
| KS26 | select/sceNetSelect: open file and device descriptors are ready at once | K libs/network.cpp:2603-2620,2648-2654,2688-2694, kernel/fileSystem.cpp IsOpenDescriptor; a875d1b 2026-10-22 "net: report open file and device descriptors ready in select (Cyberpunk 2077 Galaxy RNG seeding)" | GPL-2.0 | differs: O libs/network.cpp:2361-2364 (Linux: ENOSYS for everything), caller O libs/libKernel.cpp:2099-2103 | S | L | e4-now | OpenSSL RAND_poll selects /dev/urandom first; ours fails |
| KS27 | sceNetConnect/Send/Sendto/Recv/Recvfrom/Getsockopt exports | K libs/libNet.cpp:99-101,191-224,246,268-273; pre-4644c52 | GPL-2.0 | missing exports; O network.cpp:1895,2062,2129,2133,2182,2186 exist (ENOSYS on Linux) | S | M: titles that "connected" via the stub now see an error | e4-now | today sceNetConnect returns 0 (stub) = connected, sceNetRecv 0 = peer closed |
| KS28 | sceNetResolverStartNtoaMultipleRecords (RCCY01Xd+58): literal IPv4 -> 1 record; NetResolverInfo 384 bytes | K libs/network.h:40-56, libs/network.cpp:1464-1531, libs/libNet.cpp:139-144,253; 22b3178 2026-11-01 "net: implement sceNetResolverStartNtoaMultipleRecords" | GPL-2.0 | missing | S | L | e4-now | port the literal path and our Linux answer (ENOTIMPLEMENTED as O network.cpp:1503-1505); DNS goes with KS38 |
| KS29 | Json2 Value::clear (FIjXN2TkuTs): free contents, keep parent/rootparam | K libs/libJson2.cpp:1063-1075,1154; pre-4644c52 | GPL-2.0 | missing (O libs/libJson2.cpp:224-240 JsonValueClear exists) | S | L | e4-now | stub leaves the old value in place |
| KS30 | NpEntitlementAccess GetEntitlementKey (5LiMEPuW0DQ: PARAMETER / NO_ENTITLEMENT), GetGameTrialsFlag (y7JD1gfwyfA: 0), GenerateTransactionId (IQtb-TaIjSM: "6b797479"+24 hex), NOT_INITIALIZED before Initialize | K libs/libNpEntitlementAccess.cpp:24-28,118,181-193,207-232,475-492; pre-4644c52 (99044c7 adds only Pft) | GPL-2.0 | missing; O libs/libNet.cpp:1576-1588 Initialize keeps no state | S | L | e4-now | stub answers "has a key" (0) and leaves the key buffer uninitialised |
| KS31 | Http: SetRedirectCallback, SetCookieRecvCallback, SetRequestStatusCallback, SetInflateGZIPEnabled (any valid id), SetChunkedTransferEnabled (request id, 0/1), HttpsLoadCert/UnloadCert (ctx id), HttpsGetSslError, HttpGetLastErrno (write 0) | K libs/network.cpp:415-419,3064-3200; libs/libNet.cpp:754-762; pre-4644c52 | GPL-2.0 | missing (O helpers network.cpp:260-263) | S | L | e4-now | INVALID_ID / INVALID_VALUE paths and zeroed out-params |
| KS32 | NpWebApi2: contexts tracked; GetMemoryPoolStats (Xweb+naPZ8Y) writes {pool rounded to 16 KiB,0,0}; Terminate INVALID_LIB_CONTEXT_ID / LIB_CONTEXT_NOT_FOUND | K libs/libNet.cpp:2084-2108,2122-2155,2435-2445; pre-4644c52 | GPL-2.0 | missing; O libs/libNet.cpp:3451-3460,3792-3798 | S | L | e4-now | stats struct otherwise garbage |
| KS33 | scePadIsRemoteController (fCWdlnmB1Ks): handle check, *is_remote=false | K libs/controller.cpp:1348-1360; pre-4644c52 | GPL-2.0 | missing | S | L | e4-now | bool left uninitialised |
| KS34 | sceConvertKeycodeGetImeKeyboardType (mUuUOWI-C+0): INVALID_ADDRESS / INVALID_USER_ID, *type=0 | K libs/libConvertKeycode.cpp:1-37; pre-4644c52 | GPL-2.0 | missing | S | L | e4-now | out-param unwritten |
| KS35 | sceVideoOutAddBufferAttributeOption (MBlv8YWoyOk): attribute->option |= option | K graphics/presentation/videoOut.cpp:1335-1340, libs/libVideoOut.cpp:19; pre-4644c52 | GPL-2.0 | missing; O graphics/presentation/videoOut.cpp:96-109 has `option` at the same offset | S | L-M: option bits now reach buffer registration (GPU-side consumer, not submitted here) | e4-now | option bits silently dropped |
| KS36 | VideoOutVrrStatus gWT7X8H0bYs: GetOutputStatus + zero 8-byte VRR range at +0x30 | K libs/libVideoOutVrrStatus.cpp:43-62; pre-4644c52 | GPL-2.0 | missing (O libs/libVideoOut.cpp:53-60 registers only kP2L8t3j-aM) | S | L | e4-now | status buffer unwritten; layout from KytyPS5's observation of a title |
| KS37 | NetCtl host info on Linux: getifaddrs + /proc/net/route default route, netmask, ip | K libs/network.cpp:3757-3811; pre-4644c52 | GPL-2.0 | differs: O libs/network.cpp:3920 (non-Windows: connected=true, no addresses) | S | L: only with --network-online | e4-now | empty IP strings on Linux |
| KS38 | POSIX socket backend (socket/bind/connect/listen/accept/send/recv, Linux errno->guest errno, MSG flag and sockopt-name conversion, sockaddr conversion, select, epoll, P2P virtual ports, getaddrinfo resolver on Linux) | K libs/network.cpp:844-2720; pre-4644c52 | GPL-2.0 | differs: O libs/network.cpp:1043-2367 (Windows only; ENOSYS on Linux) | L | H: titles reach real network | later | the whole host-networking layer on our platform |
| KS39 | Trophy system: NpTrophy2 contexts/registration with real package data (sce_sys/trophy2), unlock persistence, platinum, UDS `_UnlockTrophy` and stat rules, unlock notification overlay; NpTrophy2/UDS error codes | K libs/libTrophy.cpp:1-1334, common/trophies.cpp/.h (447 lines), graphics/presentation/systemOverlay; pre-4644c52 | GPL-2.0 | differs: O libs/libNet.cpp:1984-2420 (fixed 1-trophy "Kyty" answers), 2422-3144 (UDS no-ops) | L | M: overlay is GPU/UI | later | trophies list/unlock correct for any title |
| KS40 | SaveData memory model per slot (0..3) and user: options SET_PARAM/DOUBLE_BUFFER, 32 MiB total, LIMITATION_OVER, BUSY, MEMORY_NOT_READY, init_param, param stored/returned, range checks (no grow on read) | K libs/libSaveData.cpp:270-280,338-347,442-483,771-932; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:248,693-848 (one global vector for all slots/users, grows on read) | M | M: first title's memory save file layout | later | correctness for multi-slot titles |
| KS41 | Guest users' saves under [users]/<id>; per-user memory dir | K libs/libSaveData.cpp:313-336; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:629-630 (one dir per title) | M | M: needs a user model (Config::IsGuestUserId) | later | local multiplayer saves |
| KS42 | PSN emulation option (signed-in simulation: NpGetState, NpId "Kyty", account id, reachability, NpAuth SERVICE_DOWN) | K libs/network.cpp:4086-4100 and callers; 15452a5 2026-10-29 | GPL-2.0 | differs: O always signed out (network.cpp:4261-4275, libNet.cpp:1410-1444) | M | M: titles go online paths | later | optional mode |
| KS43 | NpEntitlementAccess request/poll family: RequestServiceEntitlementInfoList, RequestUnifiedEntitlementInfo, RequestConsumeUnifiedEntitlement, Poll* (3 k-only), param validation, kind checks | K libs/libNpEntitlementAccess.cpp:111-171,234-422; pre-4644c52 | GPL-2.0 | differs/missing: O libs/libNet.cpp:1651-1714 (only the unified list) | M | L | later | completes the offline entitlement API |
| KS44 | Ces CP932 (Shift-JIS) to UTF-8: ProfileInitSJis1997Cp932, MbcsUcsContextInit, MbcsStrGetUtf8Len, MbcsStrToUtf8Str | K libs/libCes.cpp:160-385; pre-4644c52 | GPL-2.0 | differs: O libs/libNet.cpp:3305-3318 (CesStub returns 0 = NULL profile), 2 NIDs missing | M | L: needs iconv CP932 on Linux (SDL_iconv) | later | Japanese text conversion |
| KS45 | Psml PSSR dispatch packets and Psml_mfsr2 real implementation (contexts, requirements, dispatch) | K libs/libPsml.cpp:120-653; 02b17af 2026-11-02, 651ef73 2026-10-29 | GPL-2.0 | differs: O libs/libPsml.cpp (bookkeeping only) | L | H: GPU | later | GPU agent's scope; only with a Pro mode |
| KS46 | Psml NID meaning differs: GHna9-DvnUk K GetMipmapBias vs O PsmlGetProgress; GJY0MvuTcs8 K ValidateContext vs O PsmlRequestCapture | K libs/libPsml.cpp:336-353,646-649 | GPL-2.0 | differs: O libs/libPsml.cpp:345-346 | S | L | later | verify which is right before Pro mode work |
| KS47 | Error and Signin dialogs as a host overlay (SystemDialog snapshot, visibility callback, HostClose) | K libs/dialog.cpp:17-91,303-369,748-825, dialog.h:70-92; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:234-293,697-771 (finish at first poll, no UI) | L | M: UI/GPU | later | user-visible error dialogs |
| KS48 | DualSense audio haptics and speaker over USB and Bluetooth (pad speaker/vibration ports, async BT HID sender) | K libs/dualSenseHaptics.cpp (436), dualSenseBluetooth.cpp (467); pre-4644c52 | GPL-2.0 | differs: O libs/dualsense.cpp:439 ("BT framing ... not wired through"), audio.cpp pad ports | L | H: audio, needs the replug check | later | BT haptics |
| KS49 | PSVR2 controllers: PadVrControllerReadState (iA-DdobUen8), PadVrControllerSetTriggerEffects (v8P+9PRqg10), OpenXR input | K libs/padVr.cpp:1-158, libs/libPad.cpp:192-193; pre-4644c52 | GPL-2.0 | missing | L | M | later | VR titles; depends on KS70 parts we will not take |
| KS50 | sceVideoOutSetFlipMaster (WkYtyOg30do) | K graphics/presentation/videoOut.cpp:794-830,1330-1333; pre-4644c52 | GPL-2.0 | missing | M | M: presenter | later | multi-port flip sync |
| KS51 | NpEntitlementAccess add-on list from installed add-ons (--addcont), package_type/download_status from the entry | K libs/libNpEntitlementAccess.cpp:155-171,424-473, loader/additionalContent.*; 66e21a6 2026-10-24 "addcont: add user add-ons with --addcont and a launcher list" | GPL-2.0 | differs: O libs/libNet.cpp:1570-1640 (fixed GTA V list only) | M | L | later | DLC; needs KytyPS5 loader/additionalContent (not in this scope) |
| KS52 | sceHttpCreateRequest2 (rGNm+FjIXKk) | K libs/network.cpp:3504-3521 | GPL-2.0 | missing | S | M: KytyPS5 passes the path where a URL is expected; needs host+path join | later | |
| KS53 | PlayGoOpen NOT_SUPPORT_PLAYGO when no chunk table; playgo_hack 1000 chunks | K libs/libPlayGo.cpp:27,57,100-103,124-126; pre-4644c52 | GPL-2.0 | differs: O libs/libPlayGo.cpp:75-83 (assumes 1 chunk, deliberate) | S | M | later | |
| KS54 | Login/Signin dialog: selected user from Config, Signin reserved/user_id checks (INVALID_USER_ID 0x81350007) | K libs/dialog.cpp:147-192,285,323-341; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:51,77-122,250-262 (user 1000) | S | L | later | needs a user model |
| KS55 | Controller host features: gyro emulation from the right stick, keyboard player cycling, device timestamps for motion | K libs/controller.cpp:656-830,1083-1134; pre-4644c52 | GPL-2.0 | differs: O libs/controller.cpp (own model) | M | M | later | UX |
| KS56 | scePadGetExtControllerInformation (hGbf2QTBmqc): handle check, no write | K libs/libPad.cpp:137-146,180 | GPL-2.0 | missing | S | L | later | error code only |
| KS57 | NpEntitlementAccessPft eDXKe9FndlE: *state=2 | K libs/libNpEntitlementAccess.cpp:524-541; 99044c7 2026-10-25 "libs: provide NpEntitlementAccessPft state query used by FC27 (#1897)" | GPL-2.0 | missing | S | M: meaning unknown ("for the FC27 investigation") | later | weak evidence |
| KS58 | DirNameSearch of another title_id searches that title; only dirs with param metadata listed | K libs/libSaveData.cpp:615-637 | GPL-2.0 | differs: O libs/libSaveData.cpp:538-556 (other title -> no match, AnyPS5) | S | L | later | |
| KS59 | IME text editing refactored into imeCommon (TextEditEngine shared by Ime and ImeDialog) | K libs/imeCommon.cpp/.h (418 lines); pre-4644c52 | GPL-2.0 | differs: O libs/ime.cpp:175-312, imeDialog.cpp:158-455 (inline); validation lines identical (O ime.cpp:352-735 vs K 235-615) | S | L | later | verify only; no behaviour difference found in the hunks read |
| KS60 | GetEventResult stops logging empty polls | K libs/libSaveData.cpp:1184-1188; 52c80be 2026-10-25 "savedata: stop logging empty sceSaveDataGetEventResult polls" | GPL-2.0 | differs: O libs/libSaveData.cpp:1071-1084 | S | L | later | log only |
| KS61 | M3wFXbYQtAA named NpUnregisterStateCallback (K) vs NpUnregisterStateCallbackA (O) | K libs/libNet.cpp:1676 | GPL-2.0 | differs: O libs/libNet.cpp:1458 | S | L | later | one name is wrong; not verified |
| KS62 | Net: NetResolverAbort AzqoBha7js4 | K libs/libNet.cpp:131-133, network.cpp:1458-1462 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS63 | Http2: Http2SetResolveRetry Gcjh+CisAZM | K libs/libNet.cpp:1185-1187,1511; 3c77472 2026-11-02 "libs: stub sceHttp2SetResolveRetry" | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS64 | NpWebApi2: PushEventUnregisterCallback hOnIlcGrO6g | K libs/libNet.cpp:2419-2427,2466; f12fc20 2026-10-31 | GPL-2.0 | missing (DeleteFilter KJdPcOGmK58 already O libNet.cpp:3805) | S | L | later | equivalent to loader return-0 stub; registration only |
| KS65 | CommonDialog: CommonDialogIsUsed BQ3tey0JmQM (false) | K libs/dialog.cpp:102-106, libDialog.cpp:17 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS66 | DeviceService: 84fDxStrG44, 9ddRUOV8Q5A, UNMEa+5lrUA | K libs/libDeviceService.cpp:13-44; 45f5323 2026-10-23 "hle: implement sceDeviceServiceGetEventState (My First Gran Turismo)" | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS67 | BluetoothHid: tul3-GzejQc, 4FUZ+c52d2k, 4Ypfo9RIwfM | K libs/libBluetoothHid.cpp:13-40 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS68 | VideoOutVrrStatus: LibwuIonIBw, -q-vbO859Tw | K libs/libVideoOutVrrStatus.cpp:20-41 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS69 | Pad: PadOpenExt WFIiSfXGUq8 (returns OK) | K libs/libPad.cpp:126-135,170 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KS70 | Hmd2 (15 NIDs) and VrTracker2 (4 NIDs) | K libs/libHmd2.cpp:42-135, libs/hmd2.h:33-60, libs/libVrTracker2.cpp:34-122 | GPL-2.0 | missing | L | H | skip: provenance (Sce-prefixed structs with SDK-style field names -- sizeOfThis, reserved00/01, motionSensorDataValidFlags, lastValidVisionTimestamp, playAreaUpdateCounter -- not derivable from NIDs; origin not stated) | |
| KS71 | MsgDialog finishes at Open | K libs/dialog.cpp:646 | GPL-2.0 | O libs/dialog.cpp:580-594 (RUNNING until first poll; progress bar until close) | - | - | skip: already match (ours supersedes, dialog.cpp:580-594) | |
| KS72 | RTC local time = UTC | K libs/libRtc.cpp:290-304 | GPL-2.0 | O libs/libRtc.cpp:285-318 (host zone, DST) | - | - | skip: already match (ours supersedes, libRtc.cpp:285-318) | |
| KS73 | WebBrowserDialogGetStatus returns NONE | K libs/libWebBrowserDialog.cpp:13-17 | GPL-2.0 | O libs/libWebBrowserDialog.cpp:237 (state machine) | - | - | skip: already match (libWebBrowserDialog.cpp:237) | |
| KS74 | Mount3 unknown mode -> EXIT | K libs/libSaveData.cpp:728-730 | GPL-2.0 | O libs/libSaveData.cpp:643-647 (PARAMETER, releases slot) | - | - | skip: already match (ours supersedes, libSaveData.cpp:643-647) | |
| KS75 | Ssl, NetCtl and LibNetCtl tables, NpGameIntent, GameUpdate, Share (libNet + libShare.cpp), Random, Remoteplay, WebBrowserDialog (libNet), NpTrophy2 icon getters | K libs/libNet.cpp namespaces; libShare.cpp | GPL-2.0 | O identical (nsx diff 0 KytyPS5-only lines; libShare.cpp onlyK=0) | - | - | skip: already match (libNet.cpp:223-236,1389-1408,3326-3411,3827-4032,4038-4131; libShare.cpp) | |
| KS76 | SaveData mount result kept on failed mount | K dfec14a 2026-11-02 "Fix save mount result on failed mounts (#2079)" | GPL-2.0 | O libs/libSaveData.cpp:625 | S | - | in e4 / done | |
| KS77 | SaveData search sorted by the requested key | K 4b0282e 2026-10-27 "savedata: sort directory searches by the requested key" | GPL-2.0 | O libs/libSaveData.cpp:559-582 | S | - | in e4 / done | |

## 3. Port specs for e4-now rows

All return codes are KytyPS5's constants; insertion points are in OURS. CPU tests need no game and no GPU: a small host
test binary linking the lib file (KytyPS5 has matching tests: tests/SaveDataMemoryTests.cpp, NetResolverTests.cpp,
HttpUriParseTests.cpp, KernelFileSystemTests.cpp, ControllerSettingsTests.cpp, PsmlTests.cpp).

**KS01 Http2 async event.** Http2 lib: Http2SendRequestAsync (A+NVAFu4eCg), Http2ReadDataAsync (bGN-6zbo7ms).
Signature `int(int req_id, const void* post_data|void* data, size_t size, const Http2TriggerUserEventArgs* kq, void* option)`;
struct {KernelEqueue eq; int uniq_id; uint8_t pad[4]; void* udata; void* reserved;} static_assert 32. After the
request state is set, `if (kq) LibKernel::EventQueue::KernelTriggerUserEvent(kq->eq, kq->uniq_id, kq->udata)`;
ReadDataAsync also sets async_event=1 on the error path (K:1453-1472). Port K libs/libNet.cpp:837-845,1259-1264,
1266-1288,1436-1473 into O libs/libNet.cpp:1132-1152,1300-1336 (O eventQueue.h:72 has KernelTriggerUserEvent).
Test: create equeue, AddUserEvent(id 7), call SendRequestAsync with {eq,7,udata} -> KernelWaitEqueue returns id 7 with udata.

**KS02 SaveData event lock.** Wrap the queue_save_data_event calls in SaveDataCommit (O :940) and SaveDataBackup (O :1123)
and the empty-check/pop in SaveDataGetEventResult (O :1090-1095) in `Common::LockGuard lock(g_mount_mutex)` (K:1027,1275,1191).
Test: two threads, one Backup in a loop, one GetEventResult in a loop, under TSan/ASan; no report.

**KS03 SyncSaveDataMemory.** NID wiT9jeC7xPw. `int(const SaveDataMemorySync* p)` with {int32 user_id; uint32 slot_id;
uint32 option; uint8 reserved[28]}. PARAMETER if p null, slot_id>=4 or option>1; INVALID_LOGIN_USER if user_id<0;
MEMORY_NOT_READY if Setup was never called (add a flag set in O SetupSaveDataMemory2 :757); flush
(save_data_memory_store, O :714-739); if option==1 return the flush status; else queue event type 3
(MEMORY_SYNC_END) with title_id = get_title_id(), dir_name "sce_sdmemory"+(slot?slot:""), error_code = status, under
g_mount_mutex; return OK. Source K libs/libSaveData.cpp:197-202,267,309-311,1151-1182. Insert at O :244-246 (constant),
:1061-1067. Test: Setup slot 0, Sync option 0 -> GetEventResult gives type 3, error 0; Sync option 1 -> no event;
Sync without Setup -> MEMORY_NOT_READY.

**KS04 HttpCreateTemplate.** `tn.user_agent = user_agent != nullptr ? user_agent : "";` at O libs/network.cpp:584
(K network.cpp:469). Test (K tests/HttpUriParseTests.cpp TestTemplateWithoutUserAgent): Initialize, NetPoolCreate,
SslInit, HttpInit, HttpCreateTemplate(http, nullptr, 2, 1) > 0.

**KS05 Json2 aliasing.** JsonValueSetObject (dFCphqnd+a4): build the copy of `value` first (parent = self), then
JsonValueClear(self), then attach (K:626-636). JsonObjectAssign (urOpESTBZmo): copy src into a new map, destroy self's
map, attach (K:987-996). Insert at O libs/libJson2.cpp:1033-1048 and :911-917. Test: object o with child "a" (object);
SetObject(o, o.a.object) and ObjectAssign(x, x) under ASan -> no use-after-free, contents preserved.

**KS06 NetResolverDestroy.** NID kJlYH5uMAWI, Net lib. `int(int rid)`: if Network::ResolverDestroy(rid) false ->
NET_ERROR_EBADF, else OK; sets net errno on error (with KS07). Add `bool ResolverDestroy(int)` to O network.cpp:243
and implement after :447 as K network.cpp:311-319; Net:: wrapper as K :1445-1456; LibNet wrapper and LIB_FUNC in
O libs/libNet.cpp:189-219. Test: 33 x (Create, Destroy) all succeed; Destroy twice -> EBADF.

**KS07 net errno.** Replace O NET_CALL (libNet.cpp:20-27) and FinishSocketCall (:71-79) with K FinishNetCall
(libNet.cpp:52-57): on result<0 store `result - NET_ERROR_EPERM + 1` in g_net_errno; return the result unchanged.
Test: NetResolverStartNtoa with null hostname returns NET_ERROR_EINVAL and *GetNetErrorAddr() == 22.

**KS08 PlayGoGetChunkId.** NID per O libPlayGo.cpp LIB_DEFINE :478. After handle and out_entries checks: if
list!=NULL && entries==0 -> PLAYGO_ERROR_BAD_SIZE; ensure_chunks_loaded(); if list==NULL -> *out_entries =
g_chunks_num, OK. Source K libs/libPlayGo.cpp:224-234; insert O :254-257. Test: open, GetChunkId(h, NULL, 0, &n) ->
n == chunk count (1 with our fallback); GetChunkId(h, buf, 0, &n) -> BAD_SIZE.

**KS09 existed_memory_size.** Record the size of memory.dat read by save_data_memory_load (O :693-716; 0 when the
file is missing) and report that at O :765 instead of g_save_data_memory.size() (K :457-483,823). Test: empty
KYTY_BC5_SAVEDATA_DIR -> Setup reports 0; after Set + new process state reload -> reports the file size.

**KS10 Pad sample merge.** In GameController::AddState(index, state) (O controller.cpp:859): if s.states_num != 0 and
the newest sample `(first+num-1)%64` is unread (`!s.obtained[newest]`) and its `buttons` equal the new state's buttons,
overwrite that sample (and last_state) and return (K controller.cpp:524-535; our touch is outside the samples, so
compare buttons only). Test: feed 100 Axis events with no button change between two ReadStates -> one sample; press
a button, 100 axis events, release -> the press is still read.

**KS11 Psml base mode.** Psml lib: PsmlInitialize (3WVD91e12ZQ, O libPsml.cpp:113-121) returns 0x8a810012
(NOT_TRINITY_MODE) when KernelIsTrinityMode is 0 (O libKernel.cpp:1408 returns 0), leaving g_initialized false
(K libPsml.cpp:40,120-130). Register aliases fccGInHrj8A -> PsmlContextInitialize and 94iBp3KvIuI -> PsmlDispatch in
O LIB_DEFINE(InitPsml_1) :329 (both then answer NOT_INITIALIZED). New `LIB_VERSION("Psml_mfsr2",1,"Psml",1,1)` block:
Initialize o+NM86gEwFE -> 0x8a8a0012 (NOT_AVAILABLE); 1ic5q-kdOsc, gMduXCLYrNg, 0GAw7SmkwII, 5z2gBlqxJ+0, m9JLPc3wOQw,
Kyy1baXgaVU, ZLL31lzzxr4, lrJwpLjKXRc -> 0x8a8a0001 (NOT_INITIALIZED) (K :358-372,494-603,614-624). No packet writing.
Test: PsmlInitialize == 0x8a810012; mfsr2 Initialize == 0x8a8a0012; mfsr2 GetDispatchPackets == 0x8a8a0001.

**KS12 Np request completion.** NpGetAccountAge (+4DegjBqV1g, O network.cpp:4560): after arg checks, lock
g_np_request_mutex, find the request (REQUEST_NOT_FOUND), *age=0, `return np_complete_signed_out_locked(request)`.
NpGetAccountLanguage2 (3Tcz5bNCfZQ, O libNet.cpp:1430): same through a new exported helper in network.cpp (the request
table is static there); do NOT memset KytyPS5's 48-byte NpLanguageCode -- ours documents 16 bytes (O libNet.cpp:1421-1426),
write nothing when signed out. Source K network.cpp:4164-4177,4369-4407. Test: CreateAsyncRequest, GetAccountAge -> 0,
PollAsync -> OK with result SIGNED_OUT; sync request -> SIGNED_OUT.

**KS13 Get/SetParam.** GetParam (XgvSuIdnMlw, O :985): PARAMETER if param_type>5 or mount_point not NUL-terminated;
NOT_MOUNTED if g_mount_slots.Find fails; load our .param sidecar (save_data_load_param); type 0 whole struct
(size >= sizeof), 4 user_param (4 bytes), 5 mtime (8 bytes), 1..3 text field copied up to buf-1 bytes plus NUL;
*got_size = bytes written (K :126-139,1064-1118). SetParam (85zul--eGXs, O :1129): PARAMETER for null mount/buf,
type>4, size checks; NOT_MOUNTED; type 0 store whole struct; type 4 user_param; 1..3 replace that text field
(truncate to field-1, zero fill) then store (K :1282-1333); move the LOGF after the null check. Test: mount, SetParam
type 1 "abc", GetParam type 1 -> "abc", type 0 -> title "abc"; GetParam on "/savedata9" -> NOT_MOUNTED; SetParam(NULL buf) -> PARAMETER.

**KS14 Delete busy.** In SaveDataDelete (S1GkePI17zQ, O :946): use del->title_id when non-null (validated, KS17);
if the dir is mounted (g_mount_slots.FindAvailable(dir_name)==BUSY, under g_mount_mutex) return SAVE_DATA_ERROR_BUSY
(K :1051-1056). Test: Mount3 "a", Delete "a" -> BUSY and files still there; Umount2, Delete -> OK.

**KS15 TransferringMount.** WAzWTZm1H+I/RjMlsR8EXrw (O :850): PARAMETER if title_id null; mount
`_SaveData/<title_id>/<dir>`; NOT_FOUND when absent (no create); created flag 0 (K :934-970). Slot key: include the
title (e.g. key "<title>/<dir>") so another title's "data" does not collide with ours. Test: TransferringMount of a
missing dir -> NOT_FOUND and no directory created; existing -> OK, mount_result.mount_status 0.

**KS16 GetMountInfo.** 65VH0Qaaz6s (O :1169): PARAMETER for null mount_point/info or non-terminated point;
NOT_MOUNTED when Find fails; else our sidecar blocks/free (K :1335-1358). Test: GetMountInfo("/savedata3") unmounted -> NOT_MOUNTED.

**KS17 SaveData input checks.** Add valid_path_component (K :286-297) and apply: Mount3 (O :612-614 -> PARAMETER instead
of EXIT; name check; user_id<0 -> INVALID_LOGIN_USER; on create, blocks outside 48..16384 -> PARAMETER, K :742-744 --
note our 0 means "unspecified" at O :672, keep 0 allowed or decide), TransferringMount, Delete (title and dir),
DirNameSearch (K :586-597: title_id name, NUL-terminated dir_name, dir_names_num w/o buffer, user_id), Setup/Get/Set
memory user_id. Test: Mount3 dir "../x" -> PARAMETER; Mount3(NULL) -> PARAMETER (no abort); user_id -1 -> INVALID_LOGIN_USER.

**KS18 SaveDataConvert.** NID 2mfSRGdshtk (O :1218, both LIB_DEFINEs). Struct {int32 user_id; int32 pad; const DirName*
src; const DirName* dst; uint64 dst_blocks; uint8 reserved[24]} -- our comment (:1214-1217) reads blocks at +0x18, same.
Order (K :1210-1258): PARAMETER (null, src invalid or "sce_sdmemory*", dst invalid, blocks outside 48..16384);
INVALID_LOGIN_USER; NOT_FOUND if src dir missing; BUSY if mounted; EXISTS if dst exists; if our .blocks sidecar exists:
equal -> 0x809F001E NO_NEED_CONVERT, smaller -> 0x809F0020 BLOCKS_FEWER_THAN_SRC; otherwise keep our current NOT_FOUND
(KytyPS5 EXITs here). Add the two constants to O errno.h next to SAVE_DATA_ERROR_PARAMSFO_TRANSFER_TITLE_ID_NOT_FOUND.
Test: K tests/SaveDataMemoryTests.cpp TestConvert sequence, last step expecting NOT_FOUND instead of abort.

**KS19 Usbd poll sleep.** sceUsbdHandleEventsTimeout (+wU6CGuZcWk, O libUsbd.cpp:673): `Common::Thread::SleepMicro(16000)`
then OK (K libUsbd.cpp:27-34). Test: 10 calls take >= 150 ms.

**KS20 Stub out-params.** GameLiveStreaming lK8dLBNp9OE `int(Status2* s)`: null -> 0x80A00002 INVALID_PARAM;
memset 72 bytes, user_id=-1. yeQKjHETi40 `int(int type, uint32_t* count)`: type 1..3 and count non-null else same
error; *count=0 (K libNet.cpp:2783-2830; replace O libGameLiveStreaming.cpp:223,268). SharePlay: add init flag to
O libNet.cpp:4162-4176 (ALREADY_INITIALIZED 0x810E0003, NOT_INITIALIZED 0x810E0004, heap!=NULL && size<6 KiB ->
INVALID_ARGS 0x810E0001); +MCXJlWdi+s `int(ConnectionInfoA*)` 72 bytes zeroed, host/visitor user id -1 (K :2850-2905;
replace O libSharePlay.cpp:30). NpGetUserIdByAccountId VgYczPGB5ss `int(uint64 account, int* user)`: account 0 or
user NULL -> 0x80550003; else 0x80550006 SIGNED_OUT (no PSN emulation) (K network.cpp:4332-4350; replace O libNp.cpp:347).
Test: call each with a 0xCC-filled buffer; check the written fields and codes.

**KS21 NpCommerceDialog.** Result struct {int32 result; bool authorized; void* user_data (+8); uint8 reserved[32]} 48
bytes; Open copies param->user_data (+88 of the 128-byte param) when param->size==128; size!=128, mode>5 or
reserved!=0 -> 0x80B8000A PARAM_INVALID (result.result too); GetResult copies the stored result (K libNet.cpp:1563-1645).
Keep our RUNNING-until-UpdateStatus state machine (O :58-86). Test: Open with user_data 0x1234 -> GetResult user_data
0x1234, result 1 (cancelled).

**KS22 NetCtlGetInfo.** At O network.cpp:4077 replace EXIT with `if (!info) return NET_CTL_ERROR_INVALID_ADDR; if (code<1||code>21) return NET_CTL_ERROR_INVALID_CODE;`
before the memset (K network.cpp:3950-3955). Test: GetInfo(1, NULL) -> 0x80412107; GetInfo(99, &i) -> 0x80412106.

**KS23 NpAuth V3.** Structs {size_t size; int user_id; pad; const void* client_id; const char* scope} (32) and
{...; const void* client_secret; const char* scope} (40). req_id<=0, param or out NULL -> 0x80550301; size<sizeof ->
0x80550302; client_id/scope (and secret) NULL -> 0x80550301; then the existing signed-out completion (K libNet.cpp:
1737-1755,1921-1980; O libNet.cpp:1908-1969). Test: param.size=8 -> 0x80550302.

**KS24 SaveDataDialog RUNNING poll.** In O dialog.cpp:388-401: for non-progress-bar modes, the first UpdateStatus after
Open returns RUNNING, the next FINISHED (flag reset in Open/Close/Terminate as K :441,450,464-477,531,542,557).
Test: Open(mode 1), UpdateStatus -> 2, UpdateStatus -> 3; mode 5 stays 2 until Close.

**KS25 Pad port state.** Per player slot: Uninitialized -> PadInit -> Closed; PadOpen: Uninitialized ->
NOT_INITIALIZED (0x80920005), invalid args -> INVALID_ARG, Open -> ALREADY_OPENED (0x80920004), else Open + handle;
PadGetHandle: NOT_INITIALIZED / NO_HANDLE (0x80920008) unless open; handle checks answer NOT_INITIALIZED before init;
PadClose releases (K controller.cpp:1155-1212,1230-1281). Insert O controller.cpp:1199-1262, libPad.cpp:278. Keep our
user->slot mapping and the remote-control port. Test: Open before Init -> 0x80920005; Init, Open, Open -> 0x80920004;
Close, GetHandle -> 0x80920008.

**KS26 select files.** Add `bool IsOpenDescriptor(int)` to O kernel/fileSystem (GetFile(d) && opened; K a875d1b
fileSystem.cpp:413-416). In O Net::Select (network.cpp:2241) before the platform branch: for each fd in 0..nfds with a
read/write bit that is not a socket and is an open descriptor, remember it as ready; on Linux, if every requested fd is
such a file, zero the sets, set those bits and return the count; if a socket is also requested keep ENOSYS (until KS38).
Bad fd -> EBADF (K test). Test (K tests/KernelFileSystemTests.cpp TestRandomDevices): open /dev/urandom, select with read+write
bits, NULL timeout -> 2 and both bits set; after close -> -1/EBADF.

**KS27 Net socket exports.** NIDs OXXX4mUk3uk Connect, xphrZusl78E Getsockopt, beRjXBn-z+o Send, gvD1greCu0A Sendto,
9wO9XrMsNhc Recv, 304ooNZxWDY Recvfrom. Wrappers as K libNet.cpp:99-101,191-224 over our Net::Connect/Getsockopt/
Sendto/Recv/Recvfrom (O network.cpp:1895,2062,2133,2182,2186): clamp len to INT_MAX, FinishSocketCall (KS07). Check
whether our ConvertMessageFlags (O :1190) accepts the 0x20000 KytyPS5 ORs into Sendto before keeping it. LIB_FUNC in
O libNet.cpp:189-219. Test (Linux): NetSocket fails ENOSYS today, so call NetConnect(200, addr, 16) -> the
net error for EBADF (not 0) and sce_net_errno == 9; NetRecv likewise. On Windows: loopback connect/send/recv round trip.

**KS28 MultipleRecords.** NID RCCY01Xd+58, `int(int rid, const char* host, NetResolverInfo* info, int timeout, int retry, int flags)`;
NetResolverAddr {uint32 addr; uint32 reserved[3]; int af; int reserved[3]} 32, NetResolverInfo {addrs[10]; int records;
int dns4records; int reserved[14]} 384. host/info NULL or flags & ~0x10000 -> EINVAL; bad rid -> EBADF; *info={};
literal IPv4 (flag clear) -> addrs[0], af 2, records=dns4records=1, OK; else our platform path (Windows getaddrinfo loop
filling up to 10 records, EAI_NODATA -> ENORECORD; Linux NET_ERROR_RESOLVER_ENOTIMPLEMENTED as StartNtoa). Source K
network.h:40-56, network.cpp:1464-1531; insert O network.h / network.cpp near :1446, LIB_FUNC O libNet.cpp:198.
Test (K tests/NetResolverTests.cpp): "192.168.1.2" -> 1 record, addr 0x0201a8c0.

**KS29 JsonValueClearMethod.** NID FIjXN2TkuTs, `void(void* self)`: save parent/rootparam, JsonValueClear, restore
(K libJson2.cpp:1063-1075). Insert next to O JsonValueDtor :596, LIB_FUNC in O :1301 block. Test: object value with
parent p -> after clear type null, parent p.

**KS30 NpEntitlementAccess key/flag/txn.** Add `g_initialized` set by NpEntitlementAccessInitialize (O libNet.cpp:1576).
5LiMEPuW0DQ `int(uint32 label, const Label* el, Key* key)`: el/key NULL -> 0x817D0002, else 0x817D0007 (K :475-492).
y7JD1gfwyfA `int(uint32* flag)`: not init -> 0x817D0001, NULL -> 0x817D0002, *flag=0 (K :207-218). IQtb-TaIjSM
`int(TransactionId* t)` (72 bytes): not init / NULL as above; memset, snprintf "6b797479%024llx" of a counter from 1
(K :219-232). LIB_FUNC in O :1716. Test: before Initialize -> 0x817D0001; after: key -> 0x817D0007; txn -> "6b797479000...001".

**KS31 Http k-only group.** Add Network::HttpValidBase(id) = HttpValid||HttpValidTemplate||HttpValidConnection||
HttpValidRequest (O network.cpp:260-263; K network.cpp:415-419). Exports (K network.cpp:3064-3200, LIB_FUNC K
libNet.cpp:754-762): h9wmFZX4i-4, Kh6bS2HQKbo, vO4B-42ef-k (int(id, cb, arg)) and i9mhafzkEi8 (int(id, en)) -> base
check; PDxS48xGQLs (int(req, en)): en not 0/1 -> HTTP_ERROR_INVALID_VALUE, non-request -> INVALID_ID; DK+GoXCNT04 /
zXqcE0fizz0 -> ctx check; JBN6N-EY+3M (int(req, int32* err, uint32* detail)) and 0onIrKx9NIE (int(req, int* err)): NULL ->
INVALID_VALUE, write 0s, then request check. Insert in O network.cpp Http namespace + LIB_DEFINE O libNet.cpp:617.
Test: each with id 12345 -> INVALID_ID; HttpGetLastErrno on a real request -> 0 and *err==0.

**KS32 NpWebApi2 stats.** Map ctx->rounded pool size in NpWebApi2Initialize (O :3451; pool > SIZE_MAX-0x3fff ->
INVALID_ARGUMENT); Xweb+naPZ8Y `int(int ctx, Stats* s)` {size_t pool, max_inuse, cur_inuse; int32 reserved}: NULL ->
INVALID_ARGUMENT, ctx<=0 -> 0x80553403, unknown -> 0x80553404, else {pool,0,0,0}; Terminate (O :3792) same errors and
erases (K libNet.cpp:2084-2108,2122-2155,2435-2445). Test: Initialize(1, 1) -> stats.pool 0x4000; Terminate twice -> 0x80553404.

**KS33 PadIsRemoteController.** fCWdlnmB1Ks `int(int handle, bool* r)`: our handle check (as PadReadState O
controller.cpp:1359), NULL -> PAD_ERROR_INVALID_ARG, *r=false (K controller.cpp:1348-1360). LIB_FUNC O libPad.cpp:301.
Test: valid handle -> false/OK; handle 99 -> 0x80920003.

**KS34 ConvertKeycode.** New `LIB_VERSION("ConvertKeycode",1,"ConvertKeycode",1,0)` + mUuUOWI-C+0 `int(int32 user, uint32* type)`:
NULL -> 0x80bc0031, user<0 -> 0x80bc0010, *type=0 (K libConvertKeycode.cpp:1-37). Can live in O libs/libPad.cpp
(keyboard) with its own LIB_DEFINE called from the module's init. Test: three cases.

**KS35 AddBufferAttributeOption.** MBlv8YWoyOk `void(VideoOutBufferAttribute2* a, uint64 option)`: a NULL -> return
(do not EXIT), else a->option |= option (K videoOut.cpp:1335-1340). Insert near O videoOut.cpp SetBufferAttribute2,
LIB_FUNC O libVideoOut.cpp:12 block. Test: SetBufferAttribute2 then Add(0x4) -> option has bit 2.

**KS36 VrrStatus status.** gWT7X8H0bYs `int(int handle, void* status)`: NULL -> VIDEO_OUT_ERROR_INVALID_ADDRESS;
r = VideoOutGetOutputStatus(handle, status) (O videoOut.cpp:1837); on OK zero 8 bytes at +0x30 (K
libVideoOutVrrStatus.cpp:43-62). LIB_FUNC in O libVideoOut.cpp:57-60. Test needs a VideoOut driver instance for
GetOutputStatus; with the sharpemu b1ec286 change in flight (status before registration) a CPU test can open a port
without presenting. Bad handle -> GetOutputStatus's error.

**KS37 NetCtl Linux info.** Replace the non-Windows branch of O QueryHostNetworkInfo (network.cpp:3919-3921) with K
network.cpp:3757-3811: first IFF_UP|IFF_RUNNING non-loopback AF_INET ifaddr, then /proc/net/route default route (lowest
metric, RTF_UP and not RTF_REJECT) picks interface + gateway; fill ip_address, netmask, default_route; connected = ip
non-empty. Keep our --network-online gate. Test (Linux): with the flag, GetInfo(14 IP) returns the host IP (compare with getifaddrs).

## 4. Totals

- e4-now: 37 (KS01-KS37), each S.
- later: 32 (KS38-KS69), of which 8 are registration-only rows (KS62-KS69, 15 NIDs).
  Size: 18 S (KS46, KS52-54, KS56-61, and the 8 registration rows) + 8 M (KS40-44, KS50, KS51, KS55) + 6 L (KS38,
  KS39, KS45, KS47, KS48, KS49). Rough: 18 S ~ 2 days + 8 M ~ 8 days + 6 L ~ 5-6 weeks (KS38 POSIX sockets and KS39
  trophies are the big ones; KS45/KS47/KS48 touch GPU, UI or audio) ~ 7-8 weeks in all.
- skip: provenance: 1 (KS70, Hmd2 + VrTracker2, 19 NIDs).
- skip: already match: 5 (KS71-KS75).
- in e4 / done: 2 (KS76 dfec14a, KS77 4b0282e).
