# tbp0405: the NpAuth, NpPartner001, NpParty and NpSnsFacebookDialog tables of libNp.cpp, ported before they are loaded (series e7)

Port agent `tbp`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"), dead-table batch 2: four small Np tables of
`src/libs/libNp.cpp`. Agent `tl2` edits `libs.cpp` so a table loads (before the live tables) when its switch is on; this
agent edits only `libNp.cpp`, and in it only the namespaces `NpAuth`, `NpPartner`, `NpParty`, `NpSnsFacebookDialog`, plus
one include line right after `#include <optional>`. Agent `tbt` edits `namespace NpTus` of the same file in parallel; the
top session chains the two scripts and re-pins `PINS` (one dict at the top of `mktbp0405.py`).

Files: `mktbp0405.py` (the edit), `tbp0405.cpp` (the CPU test), this note.

Input: `src/libs/libNp.cpp` of the e7 input tree (e6's output of batch 1's tbn edit), md5 `24e778261495abcd5a069396f14b28b4`,
108,689 bytes, LF. Output md5 `93b864b77af305fe966aacdbbf8d8f17`, 124,396 bytes, LF.

## Switches and journal lines

Default off, read once (a function-local static), env_flag.hpp's rule (on = set, non-empty and not `0`). The line goes to
stderr when the table's `LIB_DEFINE` runs. Off is exactly today's path: each ported stub runs `PRINT_NAME()`, then
`if (switch) return port(...)`, then today's `return`; held stubs are not edited at all.

| Switch | Table (`LIB_DEFINE`) | stderr line, on (off: `[bc5] exp 0405: <item> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_NPAUTH` | `Libs::NpAuth::InitNpAuth_1` | `[bc5] exp 0405: npauth port on (items: settimeout-arguments)` |
| `KYTY_BC5_LOAD_NPPARTNER` | `Libs::NpPartner::InitNpPartner_1` | `[bc5] exp 0405: nppartner port on (items: init subscription)` |
| `KYTY_BC5_LOAD_NPPARTY` | `Libs::NpParty::InitNpParty_1` | `[bc5] exp 0405: npparty port on (items: init state members handler message)` |
| `KYTY_BC5_LOAD_NPSNSFACEBOOK` | `Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1` | `[bc5] exp 0405: npsnsfacebook port on (items: none, UpdateStatus already matches)` |

## Verdicts

| Table | NIDs | ported | already match | held |
|---|---|---|---|---|
| NpAuth | 5 | 1 (SetTimeout's argument checks; its request lookup held) | 0 | 4 |
| NpPartner001 | 4 | 3 | 0 | 1 |
| NpParty | 26 | 15 | 0 | 11 |
| NpSnsFacebookDialog | 1 | 0 | 1 | 0 |
| **total** | 36 | 19 | 1 | 16 |

Output line numbers: include `:31`; NpAuth block `:50-102`, stub `:125-132`, `LIB_DEFINE` line `:136`; NpPartner block
`:1197-1248`, stubs `:1252, :1265, :1273`, `LIB_DEFINE` `:1281`; NpParty block `:1293-1385`, stubs `:1389-1551`,
`LIB_DEFINE` `:1564`; NpSnsFacebookDialog block `:1598-1617`, `LIB_DEFINE` `:1626`.

### NpAuth (5 NIDs, library also live in libNet.cpp)

- **sceNpAuthSetTimeout** (`PM3IZCw-7m0`): **ported in part.** AnyPS5 4f41f4c37 (GPL-2.0-only)
  `core/libs/prx/libSceNpAuth/Export.cpp:137-143`, identical to shadPS4 60c42b9 (GPL-2.0-or-later)
  `src/core/libraries/np/np_auth/np_auth.cpp:201-219`: before any lookup, a negative retry, all five values 0, a resolve
  timeout under 1 s or another timeout under 10 s (0 = no effect) give 0x80550301 (shadPS4 `np_error.h:58`). Valid values
  give today's 0. Held: the request lookup (AnyPS5 `:144-146`, 0x80550306 for an unknown id); the stored values have no
  reader on either side (AnyPS5 debt `libSceNpAuth.md:11`, "Stored settings currently have no transport"). Not measured on
  a console (TODO(verify)). Signature `(req, int32 retry, u32 x4)` from shadPS4/AnyPS5 (debt `:5` names shadPS4).
- **GetAuthorizationCode** (`KxGkOrQJTqY`), **GetAuthorizationCodeA** (`qAUXQ9GdWp8`), **GetIdToken** (`uaB-LoJqHis`),
  **GetIdTokenA** (`CocbHVIKPE8`): **held**, today's 0x80550005. AnyPS5 (`:115-121, :162-168`) forwards each to its V3 call
  (`:80-113`), which looks the request up, refuses an aborted or processed one, marks it processed and, for an
  asynchronous request, leaves "signed out" for Poll/Wait. That state is libNet.cpp's (see the split-state check); this
  file cannot read it. Answering without it is worse than today: a 0 on an asynchronous request would leave the live
  request "not started" forever (live `np_auth_wait_or_poll_async`, libNet.cpp:1996-1998). The debt's title call-site
  readings (static disassembly of three titles, debt `:5`) are not used anywhere here.

### NpPartner001 (4 NIDs, no live functions)

- **sceNpEAAccessInitialize** (`7CxI50-xlCk`), **sceNpEAAccessTerminate** (`pMxXhNozUX8`), **sceNpHasEAAccessSubscription**
  (`+OnbUs1CV0M`, `(int user, bool* result)`): **ported.** AnyPS5 `core/libs/prx/libSceNpPartner001/Export.cpp:9-33`: a flag,
  no server, "no subscription" (false written, 0). Where AnyPS5 throws (Terminate or HasEAAccessSubscription before
  Initialize, a null result), shadPS4 60c42b9 `np_partner.cpp:17-59`, `np_partner_error.h:8-9`: 0x819D0001 / 0x819D0002, PS4
  values; AnyPS5 debt `libSceNpPartner001.md:10-11`: "whose PS5 value is unverified" (TODO(verify)). A second Initialize
  gives 0 (shadPS4; AnyPS5 throws). The user id is ignored, as in both.
- **pQfYTZHznMc** (sceNpHasEAAccessSubscriptionAbortRequest): **held**, today's 0. AnyPS5 has a throwing placeholder (debt
  `:5`: "The name, signature and behavior are unverified"); brief rule for pending rows. Option for the top session:
  shadPS4 60c42b9 `np_partner.cpp:27-34` has a body (0x819D0001 before Initialize, else 0).

### NpParty (26 NIDs, no live functions)

- **Ported (15):** CheckCallback, GetId, GetMemberInfo, GetMemberInfoA, GetMembers, GetMembersA, GetMemberSessionInfo,
  GetMemberVoiceInfo, GetState, GetStateAsUserA, Initialize, RegisterHandler, RegisterHandlerA, SendBinaryMessage, Terminate.
  AnyPS5 `core/libs/prx/libSceNpParty/Export.cpp:8-38, 50-76, 83-87, 94-99, 111-119, 126-128, 145-148`: a flag (Initialize
  needs a parameter; ALREADY 0x80552502; Terminate clears), NOT_INITIALIZED 0x80552503 first in every other call, GetState
  writes the 16-bit state 2, GetStateAsUserA refuses user -1 (INVALID 0x80552504), the id/member/send calls give
  NOT_IN_PARTY 0x80552506 and write nothing (null output: INVALID), handlers accepted and never called. Values: shadPS4
  60c42b9 `np_error.h:404-408`, `np_party.h:14-17`. Debt `libSceNpParty.md:5-6`: the NOT_INITIALIZED order and the -1 answer
  follow "a firmware 13.42 run of the module under an emulator" (AnyPS5 PR 12948): decision 1, accepted. Debt `:7`: which
  check comes first in Initialize is unknown (TODO(verify)).
- **Decision 3 rows:** debt `:6` names a type database as the source of six signatures (GetId, GetMembersA,
  GetMemberInfoA, GetMemberSessionInfo, GetMemberVoiceInfo, SendBinaryMessage); debt `:9` names fpPS4 for three more.
  Ported from behaviour only, per the top session's correction: our own parameter names, no type names, no structure
  layouts (the outputs are opaque pointers, nothing is written); the code comment cites AnyPS5's behaviour only.
- **Held (11), today's 0x80550005:** Create, CreateA, GetStateAsUser, GetVoiceChatPriority, Join, Leave,
  RegisterPrivateHandler, SetVoiceChatPriority, ShowInvitationList, ShowInvitationListA, UnregisterPrivateHandler: AnyPS5
  placeholders (debt `:8`: no prototypes); shadPS4 60c42b9 has only `return ORBIS_OK` stubs for them.

### NpSnsFacebookDialog (1 NID)

- **sceNpSnsFacebookDialogUpdateStatus** (`fjV7C8H0Y8k`): **already matches**, `libNp.cpp:1335-1338` of the input (output
  `:1619-1622`). AnyPS5 `Export.cpp:23, 45-47` returns the dialog status, which starts at 0 ("none") and only Initialize,
  Open, Close and Terminate move; no table of the tree registers those, so the status cannot leave 0 = today's `return OK`.
  The switch only prints its line.

## Split-state check

- **NpAuth.** The live table is `libNet.cpp:1860-2112` (`LibNpAuth`, 8 NIDs, `InitNet_1_NpAuth` `:2101`, loaded by
  `InitNet_1` `:4332`). Its key `NpAuth_v1/NpAuth_v1.1` is the dead table's key too (`GenerateName` strips `libSce`). Its
  request state, `g_np_auth_requests` and the active count (`:1886-1888`), is `static` to libNet.cpp; no header exposes it.
  Per function: every one of the 5 takes a request id, which only the live CreateRequest/CreateAsyncRequest hands out, so
  the dependency always occurs. SetTimeout's argument checks precede the lookup and need no state: ported. Its lookup and the
  four getters need the state: held. The held answer (0x80550005) does not touch the live state: the test shows the live
  PollAsync still answers INVALID_ID ("not started") after a held getter, and the live DeleteRequest still works.
  Options for the top session (none taken here): (a) forward the four getters to the live V3 calls by NID through the
  loader's database (AnyPS5's own structure; a call into another file through the loader); (b) register the four getters
  in libNet.cpp's live `LibNpAuth` (an edit of libNet.cpp); (c) keep them held.
- **NpPartner001, NpParty, NpSnsFacebookDialog.** No live function in these libraries (no other file of the tree mentions
  them or their NIDs). None of the ported bodies reads NpManager or NpCommon state: AnyPS5 ignores the user id in
  HasEAAccessSubscription (`Export.cpp:28`) and only refuses -1 in GetStateAsUserA (no user lookup), and neither looks at
  sign-in. So nothing of batch 1's tbn port in this file is needed.
- **Overlap.** Each of the 36 NIDs occurs once in the whole output tree (its `LIB_FUNC` in libNp.cpp); the edit adds no
  registration; the test checks that none of NpAuth's 5 is in a database holding only the live NpAuth table. Risk 3 of tld
  (twice-called inits): the inits only read the switch, which is idempotent.

## Test: tbp0405.cpp

No subsystem is started (PRINT_NAME is off by default; `Log::Bc5SetLogging(false)` keeps the live table's LOGF quiet). The
four inits run into one database and again into a second, with stderr in `./tbp0405-stderr.txt`; then the live
`InitNet_1_NpAuth` into the first. Each table's cases follow its own switch; the end line says on / off / mixed.

| Table | on cases | off cases |
|---|---|---|
| journal (one line per table, read once) | 1 | 1 |
| npauth | 19: SetTimeout x11 (each bad value, retry only, the exact minimums, live async request, unknown request with bad and good values), 5 held getters (outputs untouched), live poll INVALID_ID, live delete, no live overlap | 11: SetTimeout x3 (today's 0), the same 8 |
| nppartner | 10: before init, init twice, null, subscription false, held 0, terminate twice, after terminate | 6 (today's 0, nothing written) |
| npparty | 43: 6 before init, Initialize null/ok/again, state, as-user -1/ok/null, id and the six member/send calls, nulls, handlers, 11 held, terminate twice, state after | 11 (today's 0x80550005, nothing written) |
| npsnsfacebook | 1 | 1 |
| **total** | **74** (`tbp0405: on 74 of 74; end`) | **30** (`tbp0405: off 30 of 30; end`) |

## Verified on the laptop

- `mktbp0405.py <e7 input tree> <out>` prints `src/libs/libNp.cpp 93b864b77af305fe966aacdbbf8d8f17`, twice the same; it
  refuses its own output (marker) and a changed input (md5). Built-in checks: anchors once and inside their namespace (the
  include line before `namespace Libs`), each edit balanced, switch and switch-name counts, LIB_FUNC counts unchanged,
  NpCommon/NpManager/NpTrophy/NpTus byte-identical, undo gives the input back byte for byte, ASCII, LF. `diff` shows only
  insertions plus the 19 ported stubs' parameter lists. The edit also applies after a stand-in of tbt's chained edit (an
  include after `<set>`, a block in NpTus; pin bypassed for that check only).
- Syntax (VS clang++ 22, msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, stand-ins of
  `scratchpad/lib0405chk/stub`, `e6/tbn/sched_standin.h`, fmt from Inori_GPCS4): input and output libNp.cpp clean, also with
  `-Wshadow -Wconversion -Wsign-conversion` (0 warnings); tbp0405.cpp clean (needs `-Wno-deprecated-declarations` for
  Windows' POSIX names), also with `-Wformat=2`.
- Stand-in run (`scratchpad/e7/tbp/standin/build.sh`): the real tbp0405.cpp, the real symbolDatabase.cpp, the output
  libNp.cpp (one TU with tbn's and tld's stand-ins) and libNet.cpp's `LibNpAuth` namespace copied verbatim (awk) from the
  input libNet.cpp (md5 35773d6e769b85be74012a86c0f02e89): all `=1` on 74 of 74; all `=0` off 30 of 30; unset off 30 of
  30; npauth=yes, nppartner empty, npparty=1, npsnsfacebook=0: mixed 70 of 70; a mismatched argument: exit 2. Negative
  control with the unedited input libNp.cpp: on 28 of 74 (FAIL, exit 1); off 29 of 30, only the journal case failing, so the
  off answers are today's.
- Found while running: a first draft checked a call's outputs in the same expression as the call; argument order is
  unspecified (MSVC-ABI clang evaluates right to left), so the check ran first. Each such call is now its own statement.
  `tbn0405.cpp` has the same pattern (e.g. its GetTrophyUnlockState and info cases); it passed on the box, so the box's
  compiler evaluated those left to right, but nothing guarantees it.
- **Not checked:** the box's Linux compile and the real link with every emulator object; running tbp0405 on the box.

## Risks

- NpParty: Initialize used to give 0x80550005; it now gives 0, and the title then sees state 2 / NOT_IN_PARTY. That is
  AnyPS5's model; how a given title reacts is unknown.
- NpPartner: HasEAAccessSubscription now writes false (today it wrote nothing and the title read its own buffer). The
  error values are PS4 values (TODO(verify)).
- NpAuth: SetTimeout now refuses out-of-range values that today got 0 (shadPS4 and AnyPS5 agree; console unverified). The
  held getters keep this file's 0x80550005; libNet.cpp and AnyPS5 use 0x80550006 for signed out (the file's own
  TODO(verify) at input `:41`).
- The ported stubs declare real parameters now; the off path ignores them.

## Sizes held and later work

- Held here: NpAuth 4 getters (AnyPS5 3-line wrappers, 12 lines, over about 33 lines of V3 logic) plus SetTimeout's 3-line
  lookup; NpPartner 1 placeholder (shadPS4 body 7 lines); NpParty 11 placeholders (0 logic lines). By exp 0405's rule
  about 0.1 day of logic held, all of it NpAuth's.
- AnyPS5 implements 7 more NIDs of these libraries that no table registers (`census/r1-anyps5-missing.tsv`):
  NpSnsFacebookDialog Initialize, Open, GetStatus, GetResult, Close, Terminate (~40 lines; once registered, UpdateStatus
  needs the shared status) and NpAuth GetAuthorizedAppCode (`IDX0S5EsEh4`, throws on its valid path). Not part of this brief.

## Files

| File | md5 |
|---|---|
| `mktbp0405.py` | `deff11ac1b67cb5c0aa5bfd418b123d6` |
| `tbp0405.cpp` | `f5afb5fb8ada235ec1418134267287f5` |
| input `src/libs/libNp.cpp` (e7 input tree) | `24e778261495abcd5a069396f14b28b4` |
| output `src/libs/libNp.cpp` | `93b864b77af305fe966aacdbbf8d8f17` |
