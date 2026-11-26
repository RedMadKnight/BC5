# tbp0405: the NpAuth, NpPartner001, NpParty and NpSnsFacebookDialog tables, ported before they are loaded (series e7)

Port agent `tbp`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"), dead-table batch 2: four small Np tables. Revised the same
day on the top session's follow-ups: (1) held stubs are not registered when their table's switch is on; (2) NpAuth's five go
into libNet.cpp's live NpAuth table, next to its request state (one owner), registered only when `KYTY_BC5_LOAD_NPAUTH` is
on, and libNp.cpp's NpAuth namespace stays as its input (the loader row for npauth is dropped; tl2 is told); (3) the
libNp.cpp input is tbt's output.

Files: `mktbp0405.py` (the edit, two units), `tbp0405.cpp` (the CPU test), this note.

| Unit | Input (pinned in `PINS`, one dict) | Output |
|---|---|---|
| `src/libs/libNp.cpp` | `eb3bfe9d56f0fcdddf29199846f46fb5` (tbt's current output; 171,351 bytes, LF) | `a50bfab5a6c530e6ea4afa79e08c4f89` (184,774 bytes) |
| `src/libs/libNet.cpp` | `35773d6e769b85be74012a86c0f02e89` (the e7 input tree: e5's svc output; 138,701 bytes, LF) | `fdbbb28ec3b1529a898a775462d64804` (143,860 bytes) |

What is edited: in libNp.cpp, one line after `#include <optional>` and, inside `NpPartner`, `NpParty` and
`NpSnsFacebookDialog` only, a block after each `LIB_VERSION`, the ported stubs' parameter lists and one branch each, one
line at the top of each `LIB_DEFINE`, and `if (!switch) { ... }` around each held stub's `LIB_FUNC`. In libNet.cpp, inside
`namespace LibNpAuth` only, a block before `LIB_DEFINE(InitNet_1_NpAuth)` and an `if (switch)` group of five `LIB_FUNC`s
after its last line. libNp.cpp's NpAuth, NpCommon, NpManager, NpTrophy and NpTus and everything of libNet.cpp outside
LibNpAuth are byte-identical (asserted).

## Switches and journal lines

Default off, read once (a function-local static), env_flag.hpp's rule (on = set, non-empty and not `0`). Off is exactly
today's path: each ported stub runs `PRINT_NAME()`, then `if (switch) return port(...)`, then today's `return`.

| Switch | Printed by | stderr line, on (off: `[bc5] exp 0405: <item> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_NPPARTNER` | `Libs::NpPartner::InitNpPartner_1` | `[bc5] exp 0405: nppartner port on (items: init subscription)` |
| `KYTY_BC5_LOAD_NPPARTY` | `Libs::NpParty::InitNpParty_1` | `[bc5] exp 0405: npparty port on (items: init state members handler message)` |
| `KYTY_BC5_LOAD_NPSNSFACEBOOK` | `Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1` | `[bc5] exp 0405: npsnsfacebook port on (items: none, UpdateStatus already matches)` |
| `KYTY_BC5_LOAD_NPAUTH` | `Libs::LibNpAuth::InitNet_1_NpAuth` (libNet.cpp, the live table) | `[bc5] exp 0405: npauth port on (items: getters settimeout)` |

The npauth line comes from a live table that `InitNet_1` always loads, so it prints in every run, `off` included.

## Verdicts

| Table | NIDs | ported | already match | held (not registered when on) |
|---|---|---|---|---|
| NpAuth (now in libNet.cpp) | 5 | 5 | 0 | 0 |
| NpPartner001 | 4 | 3 | 0 | 1 |
| NpParty | 26 | 15 | 0 | 11 |
| NpSnsFacebookDialog | 1 | 0 | 1 | 0 |
| **total** | 36 | 23 | 1 | 12 |

Output lines: libNp.cpp include `:31`; NpPartner block `:1138-1189`, stubs `:1193, :1206, :1214`, `LIB_DEFINE` `:1221`,
held `:1224`; NpParty block `:1236-1329`, stubs `:1333-1495`, `LIB_DEFINE` `:1507`, held `:1510-1554`; NpSnsFacebookDialog
block `:1564-1583`, `LIB_DEFINE` `:1591`. libNet.cpp block `:2101-2186`, `LIB_DEFINE` `:2188`, the five `:2197-2203`.

### NpAuth (5 NIDs), ported into libNet.cpp's live table

- **GetAuthorizationCode** (`KxGkOrQJTqY`), **GetAuthorizationCodeA** (`qAUXQ9GdWp8`), **GetIdToken** (`uaB-LoJqHis`),
  **GetIdTokenA** (`CocbHVIKPE8`): AnyPS5 4f41f4c37 (GPL-2.0-only) `core/libs/prx/libSceNpAuth/Export.cpp:115-121, 162-168`
  forward to the V3 calls; here they forward to libNet.cpp's own `NpAuthGetAuthorizationCodeV3` / `NpAuthGetIdTokenV3`
  (unchanged), after AnyPS5's V3 null check (`:82, :99`: a null parameter or output gives 0x80550301 before the lookup,
  which the live V3 does not do). The plain GetAuthorizationCode passes no issuer (AnyPS5's three-argument form; shadPS4's
  has a fourth). So: unknown request 0x80550306, aborted 0x80550304, finished 0x80550301, synchronous 0x80550006, and
  asynchronous 0 with the result for PollAsync, all from the live state. The live V3 clears 136 / 4104 output bytes first,
  as today. Debt `libSceNpAuth.md:5` names shadPS4 f68923f `np_auth.cpp:189-199, 375-383` (the A forms differ from V3 only
  in a version flag). Its title call-site readings are not used.
- **SetTimeout** (`PM3IZCw-7m0`): AnyPS5 `:137-150`, the same checks as shadPS4 60c42b9 `np_auth.cpp:201-219`: a negative
  retry, all five 0, a resolve timeout under 1 s or another under 10 s (0 = no effect) give 0x80550301 first; then an
  unknown request 0x80550306 (looked up in the live table under its mutex); else 0. The values are not kept: nothing reads
  them (AnyPS5 keeps them for a transport that does not exist, debt `:11`).
- Nothing measured on a console (TODO(verify)). Not ported: AnyPS5's first-poll "running" answer (cb8b0caf7); that is the
  live PollAsync's behaviour, outside these five.

### NpPartner001 (4 NIDs)

- **Initialize** (`7CxI50-xlCk`), **Terminate** (`pMxXhNozUX8`), **HasEAAccessSubscription** (`+OnbUs1CV0M`,
  `(int user, bool* result)`): ported. AnyPS5 `libSceNpPartner001/Export.cpp:9-33` (a flag, no server, false written, 0).
  Where AnyPS5 throws, shadPS4 60c42b9 `np_partner.cpp:17-59`, `np_partner_error.h:8-9`: 0x819D0001 / 0x819D0002, PS4
  values; debt `libSceNpPartner001.md:10-11`: "whose PS5 value is unverified" (TODO(verify)). A second Initialize gives 0.
- **pQfYTZHznMc** (HasEAAccessSubscriptionAbortRequest): held, an AnyPS5 placeholder (debt `:5`: name, signature and
  behaviour unverified). Not registered when on; off, registered as today (0). shadPS4 `:27-34` has a body (0x819D0001
  before Initialize, else 0) if wanted later.

### NpParty (26 NIDs)

- **Ported (15):** CheckCallback, GetId, GetMemberInfo/A, GetMembers/A, GetMemberSessionInfo, GetMemberVoiceInfo,
  GetState, GetStateAsUserA, Initialize, RegisterHandler/A, SendBinaryMessage, Terminate. AnyPS5
  `libSceNpParty/Export.cpp:8-38, 50-76, 83-87, 94-99, 111-119, 126-128, 145-148`: a flag (ALREADY 0x80552502), NOT_INITIALIZED
  0x80552503 first, state 2 written, user -1 refused (INVALID 0x80552504), NOT_IN_PARTY 0x80552506 with nothing written,
  handlers accepted and never called. Values: shadPS4 60c42b9 `np_error.h:404-408`, `np_party.h:14-17`. Debt
  `libSceNpParty.md:5-6`: the NOT_INITIALIZED order and the -1 answer come from a firmware 13.42 run under an emulator (PR
  12948), accepted by decision 1. Debt `:7`: Initialize's check order is unknown (TODO(verify)).
- **Decision 3:** debt `:6` names a type database for six signatures (GetId, GetMembersA, GetMemberInfoA,
  GetMemberSessionInfo, GetMemberVoiceInfo, SendBinaryMessage); debt `:9` names fpPS4 for three. They are ported from behaviour
  only: our own parameter names, no type names, no layouts (opaque outputs, nothing written); the code cites AnyPS5's
  behaviour only.
- **Held (11):** Create, CreateA, GetStateAsUser, GetVoiceChatPriority, Join, Leave, RegisterPrivateHandler,
  SetVoiceChatPriority, ShowInvitationList, ShowInvitationListA, UnregisterPrivateHandler (AnyPS5 placeholders, debt `:8`;
  shadPS4 only `return ORBIS_OK`). Not registered when on; off, registered as today (0x80550005).

### NpSnsFacebookDialog (1 NID)

- **UpdateStatus** (`fjV7C8H0Y8k`): already matches (output `:1584-1587`). AnyPS5 `Export.cpp:23, 45-47` returns the
  status, which only Initialize/Open/Close/Terminate move; no table registers them, so it stays 0 = today's `return OK`.

## Split state and double registration

- **NpAuth: one owner.** The five now live in `LibNpAuth` with the request state (`g_np_auth_requests`, libNet.cpp
  `:1886-1888`) and use it directly: the getters through the live V3 calls, SetTimeout through `np_auth_find_request` under
  `g_np_auth_request_mutex`. The live eight are byte-identical in both states (asserted: the output up to the block equals
  the input).
- **No NID twice.** libNp.cpp's dead NpAuth table (unchanged) registers the same five NIDs under the same key
  (`NpAuth_v1`, as `GenerateName` strips `libSce`). So that table must never be loaded: with no npauth loader row, nothing
  loads it in any state. In libNet.cpp each of the five occurs once, inside the `if`. Off: 8 NIDs; on: 13.
- **NpPartner001, NpParty, NpSnsFacebookDialog:** no live functions in these libraries (grep of the tree), no NpManager or
  NpCommon state read (AnyPS5 ignores the user id or only refuses -1; no sign-in check). Nothing of batch 1 is needed.
- **Overlap:** the 31 NIDs of the three switched tables occur only in their own `LIB_FUNC`s in the whole output tree. The
  test dumps the database (`SymbolDatabase::DbgDump`) and finds every NID once in every switch state.
- tld's risk 3 (twice-called inits): the inits only read their switch, which is idempotent.

## Test: tbp0405.cpp

No subsystem is started. The three switched inits, then the live `InitNet_1_NpAuth`, run into one database and again into
a second, with stderr in `./tbp0405-stderr.txt` (4 lines, each once). The first database is dumped to `./tbp0405-dump/`
and read back. Each table's cases follow its own switch; the end line says on / off / mixed.

| Part | on | off |
|---|---|---|
| journal, registration (no NID twice; 32 records on, 39 off) | 2 | 2 |
| npauth | 31: five present + live eight; null checks (4); unknown, synchronous, finished request; A form with issuer 0; IdToken; asynchronous request then live poll (before: INVALID_ID; after: 0, signed out); aborted; SetTimeout x13 (each bad value, retry only, minimums, finished, unknown good/bad, deleted); deletes | 5: five absent, live eight present, live V3 and PollAsync give today's answers, deletes |
| nppartner | 10 (held absent, then the ported calls) | 6 (today's 0; held registered) |
| npparty | 33 (11 held absent, then the ported calls) | 12 (today's 0x80550005; 11 held registered) |
| npsnsfacebook | 1 | 1 |
| **total** | **77** (`tbp0405: on 77 of 77; end`) | **26** (`tbp0405: off 26 of 26; end`) |

## Verified on the laptop

- `mktbp0405.py <tree> <out>` (tree: `scratchpad/e7/tbp/in`, tbt's libNp.cpp and the e7 libNet.cpp) prints both md5s
  above, twice the same. It refuses its own output on either unit (markers) and a changed input (md5). Built-in checks:
  anchors once and in their namespace, each edit balanced, switch and switch-name counts, LIB_FUNC counts (libNp.cpp per
  table unchanged; LibNpAuth 8 to 13), each of the five once in libNet.cpp, the untouched namespaces and the rest of
  libNet.cpp byte-identical, undo gives each input back byte for byte, ASCII, LF.
- Syntax (VS clang++ 22, msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, the stand-ins of
  `scratchpad/lib0405chk/stub` and `e6/tbn/sched_standin.h`, fmt from Inori_GPCS4):
  - libNp.cpp in and out: clean, out also with `-Wshadow -Wconversion -Wsign-conversion`.
  - libNet.cpp: the input already fails twice on this compiler (`-Wmissing-field-initializers` at `:885, :962`, Http2,
    outside LibNpAuth); the output has the same two and nothing else; with `-Wno-missing-field-initializers -Wshadow` it is
    clean.
  - tbp0405.cpp: clean (with `-Wno-deprecated-declarations` for Windows' POSIX names).
- Stand-in run (`scratchpad/e7/tbp/standin/build.sh`): the real tbp0405.cpp, the real symbolDatabase.cpp, the output
  libNp.cpp (one TU with tbn's and tld's stand-ins), and the output libNet.cpp's `LibNpAuth` namespace copied verbatim.
  Results: all `=1` on 77 of 77; all `=0` off 26 of 26; unset off 26 of 26; npauth=yes, nppartner empty, npparty=1,
  npsnsfacebook=0: mixed 73 of 73.
- Negative control with both unedited inputs (`standin/neg`): all `=1` stops with `FAIL setup: KxGkOrQJTqY is not
  registered` after 4 FAIL cases (exit 2); unset gives off 25 of 26, only the journal case failing, so the off answers
  are today's.
- **Not checked:** the box's Linux compile and the real link with every emulator object; running tbp0405 on the box; the
  whole InitAll with tl2's libs.cpp (tl2's test).

## Risks

- NpAuth: titles that call the five now get AnyPS5's answers on the live requests instead of an unresolved import (the
  table was never loaded). An asynchronous getter now returns 0 and its poll reports "signed out". Out-of-range timeouts
  are refused.
- NpParty: Initialize now gives 0, then state 2 / NOT_IN_PARTY. NpPartner: HasEAAccessSubscription writes false. The error
  values are PS4 values (TODO(verify)).
- Held stubs unregistered when on: a title's call to them goes to the loader's stub path (exp 0327's stubbed-import line).
- If anything ever loads libNp.cpp's `NpAuth::InitNpAuth_1` together with the npauth switch on, the five are registered
  twice; nothing does today, and tl2's row is dropped.
- The test relies on DbgDump writing `./tbp0405-dump/db.txt` (a writable fresh directory), as tld's did.

## Sizes held and later work

- Held: NpPartner 1 placeholder (shadPS4 body 7 lines), NpParty 11 placeholders (no logic). Nothing of NpAuth is held now.
- AnyPS5 implements 7 more NIDs of these libraries that no table registers (`census/r1-anyps5-missing.tsv`): the Facebook
  dialog's Initialize, Open, GetStatus, GetResult, Close, Terminate (~40 lines) and NpAuth GetAuthorizedAppCode
  (`IDX0S5EsEh4`, throws on its valid path). Not in this brief.
- Found in batch 1's test: `tbn0405.cpp` checks a call's outputs in the same expression as the call (unspecified argument
  order). It passed on the box, so that compiler went left to right. This test makes each such call in its own statement.

## Files

| File | md5 |
|---|---|
| `mktbp0405.py` | `8bd78bad50771c009407ba9d0f30cd5a` |
| `tbp0405.cpp` | `1b11e272f783b323c418da83aba16dbc` |
| input / output `src/libs/libNp.cpp` | `eb3bfe9d56f0fcdddf29199846f46fb5` / `a50bfab5a6c530e6ea4afa79e08c4f89` |
| input / output `src/libs/libNet.cpp` | `35773d6e769b85be74012a86c0f02e89` / `fdbbb28ec3b1529a898a775462d64804` |
