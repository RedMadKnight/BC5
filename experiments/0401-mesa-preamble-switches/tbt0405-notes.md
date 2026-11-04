# tbt0405: the NpTus table of libNp.cpp, ported before it is loaded (series e7)

Port agent `tbt`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"): the tables that are compiled but never loaded by
`Libs::InitAll` are ported first, then loaded, each behind its own switch. This is batch 2's largest library table. Agent
`tl2` edits `libs.cpp` so the table loads when its switch is on; this agent edits only `src/libs/libNp.cpp`, and in it only
`namespace NpTus { ... } // namespace NpTus`. No include is added: the block uses `<cstdint>`, `<cstdio>`, `<cstdlib>`,
`<cstring>`, `<map>`, `<mutex>` and `<set>`, which the input already includes (tbn added them, input `:20-32`).

Files: `mktbt0405.py` (the edit), `tbt0405.cpp` (the CPU test), this note.

Input: `src/libs/libNp.cpp` of the e7 input tree, which is e6's output of `mktbn0405.py`: md5
`24e778261495abcd5a069396f14b28b4`, 108,689 bytes, LF, UTF-8 BOM. The script pins it in `PINS` at its top.

Output md5: `eb3bfe9d56f0fcdddf29199846f46fb5` (171,351 bytes, LF, BOM kept).

Chaining with `tbp` (NpAuth, NpPartner, NpParty, NpSnsFacebookDialog, includes after `#include <optional>`): every anchor
lies inside `namespace NpTus`, and the script asserts that everything before and after that namespace is byte-identical to
its input. A scratch check (`e7/tbt/chain/chain.py`) applied a stand-in for tbp's kind of edit (an include after
`<optional>`, lines in NpAuth and NpParty) before and after this edit: the NpTus namespace comes out the same either way,
and both orders give the same file. Only the md5 in `PINS` needs re-pinning.

## Switch and journal line

| Switch | Table (`LIB_DEFINE`) | stderr line (on / off) |
|---|---|---|
| `KYTY_BC5_LOAD_NPTUS` | `Libs::NpTus::InitNpTus_1` | `[bc5] exp 0405: nptus port on (items: context request abort poll wait slots variable data status friends users tss)` / `[bc5] exp 0405: nptus port off` |

- The switch defaults to off and is read once (a function-local static in `Bc5NtuOn`, output `:2463`). Unset, empty or `0`
  is off; any other value is on (env_flag.hpp's rule). There is no item list.
- `InitNpTus_1` (output `:4047`) reads it as its first line, so the line is printed whenever `libs.cpp` loads the table.
- Off is exactly today's path. Each of the 136 edited stubs runs `PRINT_NAME()`, then `if (Bc5NtuOn()) return <port>;`,
  then today's `return NP_NOT_SIGNED_IN;` (0x80550005, input `:44`). The stubs now declare real parameters, which the off
  path ignores. The 6 held stubs and all 142 registration lines are unchanged (the script asserts both).

## Size

| Table | NIDs | ported | already match | held | live elsewhere |
|---|---|---|---|---|---|
| NpTus | 142 | 136 | 0 | 6 | 0 |

## Source and provenance

**AnyPS5** (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
`core/libs/prx/libSceNpTus/Export.cpp`:
- `:10-34`: the error codes and limits (32 title contexts, 256 requests, 64 slots, 101 users, 100 friends, TSS slots 0-15,
  TSS small storage up to 64 KiB).
- `:36-137`: the request record, the slot-list, friends-option and empty-name checks, the offline start/wait, and the
  title-context table that TUS and TSS share.
- `:141-183`, `:222-230`, `:247-249`, `:1055-1057`: contexts, requests, abort, poll, wait.
- `:185-1089`: the 63 `*Async` calls and the 63 blocking forms.

The port is in our own form (names `Bc5Ntu*`, one helper per family of checks; output block `:2435-2926`). The
behaviour, the order of the checks and every constant are AnyPS5's.

**Debt note** `docs/dev/debt/libSceNpTus.md` (read in full):
- The signatures, checks, check order and community error codes follow shadPS4, and fpPS4 for the context and request
  calls. Nothing is measured on a console.
- Every request finishes with `SCE_NP_ERROR_SIGNED_OUT`. No output (variables, data, statuses, hits, content length) is
  ever written, and output sizes are not checked.
- An abort stays set: every later operation on the request finishes ABORTED.
- Until a request has started, poll answers 1 and wait answers INVALID_ARGUMENT.
- `sceNpTusCreateNpTitleCtxA` does not check sign-in (shadPS4 returns the `sceNpGetNpId` error instead).

**shadPS4** (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9, checked for the signatures and constants:
- `src/core/libraries/np/np_tus/np_tus.cpp:122-168` (the context calls, including both A forms `(serviceLabel, userId)`)
  and `:4871` (TSS data-status size check).
- `np_tus.h:48-82` (TSS data status = 0x18 bytes; TSS option = 0x20; friends option = 0x18).
- `np_error.h:15,105-125` (the error codes).
- `np_types.h:29-33` (online id = 20 bytes; the virtual-user arrays use this stride).

**Exp 0405 R1 rows** (`raw\r1-verdicts\D1.tsv:133-152`): all "shared missing", except header and test rows. One row needs a
note: `dbc28c0a9` ("Source unclear: subject says measured, debt :16 says not measured on a console").
- That commit added `sceNpTssGetDataAsync`'s data-status size check (0x18 or INVALID_ALIGNMENT, a null status taken).
- 0x18 is shadPS4's `sizeof(OrbisNpTssDataStatus)`, checked at `np_tus.cpp:4871`, so the source is a public project and no
  disallowed source is named. Ported, with `TODO(verify)` on "measured".

**Decision 3, corrected (top session, 2026-11-04):** a row whose types come from an IDA database is ported, rewritten from
behaviour.
- The only such mention here is the debt note's "Orbital's for the `A` form" (the signature of `sceNpTssCreateNpTitleCtxA`).
- The same `(service label, user id)` signature is in shadPS4 60c42b9 `np_tus.cpp:164-168`, and the behaviour is AnyPS5's
  `:228-230` (forward to `sceNpTusCreateNpTitleCtxA`).
- Ported with our own names. Nothing ties it to Orbital or IDA.

**Not taken** (`TODO(verify)`): the debt note reports an emulator run of firmware 13.42's module (AnyPS5 PR 10675) that
differs from these checks.
- It covers the A and ForCrossSave friends calls, `sceNpTusGetDataForCrossSaveVUser` and `sceNpTusDeleteMultiSlotDataVUser`.
- The differences: array sizes checked against the entry size (0x80550714); an option-size mismatch answered 0x80550704;
  start rank 0 accepted; the array zeroed for SDK 5.50+; data-status sizes 0x1F0/0x210 only; null or empty virtual users
  and `arrayLen` -1 accepted in delete, 0 refused.
- AnyPS5's code does not apply them, and the note gives no entry sizes and no rule for what follows an accepted
  null/empty user. Applying them would mean inventing that behaviour, so they are left for a decision.
- They are firmware-run values, which decision 1 accepts. If the top session wants them, they belong behind their own item
  switch.

## Per function

All ported rows: AnyPS5 4f41f4c37 `Export.cpp` at the line given; verdict **ported**; switch `KYTY_BC5_LOAD_NPTUS`.
- An `*Async` form answers its check's error, or else starts the request: `Bc5NtuStart`, `:2632`, which gives INVALID_ID
  for an unknown request and finishes the request at once with SIGNED_OUT, or ABORTED after an abort.
- A blocking form runs the same check, then returns the request's result: `Bc5NtuBlock`, `:2648`.
- Output lines are of the edited `src/libs/libNp.cpp`.

| Function(s) | NID(s) (blocking / Async) | AnyPS5 (blocking / Async) | our check (block) | output (blocking / Async) |
|---|---|---|---|---|
| `sceNpTssCreateNpTitleCtx` | sRVb2Cf0GHg | :222 | `Bc5NtuNewContextNpId` (:2538) | :2928 |
| `sceNpTusCreateNpTitleCtx` | BIkMmUfNKWM | :1055 | `Bc5NtuNewContextNpId` | :2968 |
| `sceNpTssCreateNpTitleCtxA` | lBtrk+7lk14 | :228 | `Bc5NtuNewContext` (:2527) | :3280 |
| `sceNpTusCreateNpTitleCtxA` | 1n-dGukBgnY | :141 | `Bc5NtuNewContext` | :3407 |
| `sceNpTusCreateRequest` | 3bh2aBvvmvM | :147 | `Bc5NtuNewRequest` (:2565) | :3415 |
| `sceNpTusDeleteNpTitleCtx` | H3uq7x0sZOI | :156 | `Bc5NtuDeleteContext` (:2548) | :3492 |
| `sceNpTusDeleteRequest` | CcIH40dYS88 | :163 | `Bc5NtuDeleteRequest` (:2581) | :3500 |
| `sceNpTusAbortRequest` | 2eq1bMwgZYo | :168 | `Bc5NtuAbort` (:2587) | :3330 |
| `sceNpTusPollAsync` | t7b6dmpQNiI | :176 | `Bc5NtuPoll` (:2598) | :3892 |
| `sceNpTusWaitAsync` | hYPJFWzFPjA | :247 | `Bc5NtuWait` (:2614) | :4038 |
| `sceNpTusGetMultiSlotVariable` + `Async` | F+eQlfcka98 / bcPB2rnhQqo | :1067 / :255 | `Bc5NtuSlotValues` (:2695) | :3104 / :3112 |
| `sceNpTusGetMultiSlotVariableA` + `Async` | GDXlRTxgd+M / 2BnPSY1Oxd8 | :251 / :185 | `Bc5NtuSlotValues` | :3700 / :3708 |
| `sceNpTusGetMultiSlotVariableForCrossSave` + `Async` | m9XZnxw9AmE / DFlBYT+Lm2I | :291 / :283 | `Bc5NtuSlotValues` | :3732 / :3740 |
| `sceNpTusGetMultiSlotVariableVUser` + `Async` | uFxVYJEkcmc / qp-rTrq1klk | :1071 / :263 | `Bc5NtuSlotValuesUser` (:2703), slots needed | :3120 / :3128 |
| `sceNpTusGetMultiSlotVariableAVUser` + `Async` | AsziNQ9X2uk / y-DJK+d+leg | :279 / :271 | `Bc5NtuSlotValuesUser` | :3716 / :3724 |
| `sceNpTusGetMultiSlotVariableForCrossSaveVUser` + `Async` | wTuuw4-6HI8 / DPcu0qWsd7Q | :303 / :295 | `Bc5NtuSlotValuesUser` | :3748 / :3756 |
| `sceNpTusSetMultiSlotVariable` + `Async` | c6aYoa47YgI / 5J9GGMludxY | :1083 / :311 | `Bc5NtuSlotValues` | :3232 / :3240 |
| `sceNpTusSetMultiSlotVariableA` + `Async` | cf-WMA0jYCc / ypMObSwfcns | :307 / :193 | `Bc5NtuSlotValues` | :3932 / :3940 |
| `sceNpTusSetMultiSlotVariableVUser` + `Async` | 1Cz0hTJFyh4 / CJAxTxQdwHM | :1087 / :318 | `Bc5NtuSlotValuesUser` | :3948 / :3956 |
| `sceNpTusDeleteMultiSlotVariable` + `Async` | mYhbiRtkE1Y / 0nDVqcYECoM | :335 / :329 | `Bc5NtuSlotDelete` (:2717) | :2992 / :3000 |
| `sceNpTusDeleteMultiSlotVariableA` + `Async` | pwnE9Oa1uF8 / NQIw7tzo0Ow | :325 / :200 | `Bc5NtuSlotList` (:2673) | :3460 / :3468 |
| `sceNpTusDeleteMultiSlotVariableVUser` + `Async` | o02Mtf8G6V0 / WCzd3cxhubo | :346 / :339 | `Bc5NtuSlotDelete` | :3476 / :3484 |
| `sceNpTusDeleteMultiSlotData` + `Async` | 0DT5bP6YzBo / OCozl1ZtxRY | :927 / :520 | `Bc5NtuSlotDelete` | :2976 / :2984 |
| `sceNpTusDeleteMultiSlotDataA` + `Async` | iXzUOM9sXU0 / 6-+Yqc-NppQ | :931 / :511 | `Bc5NtuSlotList` | :3428 / :3436 |
| `sceNpTusDeleteMultiSlotDataVUser` + `Async` | xutwCvsydkk / zDeH4tr+0cQ | :357 / :350 | `Bc5NtuSlotDelete` | :3444 / :3452 |
| `sceNpTusAddAndGetVariable` + `Async` | cRVmNrJDbG8 / Q2UmHdK04c8 | :903 / :465 | `Bc5NtuAddNpId` (:2743) | :2936 / :2944 |
| `sceNpTusAddAndGetVariableA` + `Async` | wPFah4-5Xec / 2dB427dT3Iw | :907 / :206 | `Bc5NtuAddAccount` (:2729) | :3338 / :3346 |
| `sceNpTusAddAndGetVariableForCrossSave` + `Async` | EPeq43CQKxY / mXZi1D2xwZE | :915 / :477 | `Bc5NtuAddCrossSave` (:2736) | :3370 / :3378 |
| `sceNpTusAddAndGetVariableVUser` + `Async` | ukr6FBSrkJw / lliK9T6ylJg | :923 / :499 | `Bc5NtuAddUser` (:2754), option first | :2952 / :2960 |
| `sceNpTusAddAndGetVariableAVUser` + `Async` | Nt1runsPVJc / GjlEgLCh4DY | :911 / :454 | `Bc5NtuAddUser` | :3354 / :3362 |
| `sceNpTusAddAndGetVariableForCrossSaveVUser` + `Async` | 4VLlu7EIjzk / 6Lu9geO5TiA | :919 / :488 | `Bc5NtuAddUser` | :3386 / :3394 |
| `sceNpTusGetData` + `Async` | XOzszO4ONWU / uHtKS5V1T5k | :1059 / :548 | `Bc5NtuDataGet` (:2769) | :3008 / :3016 |
| `sceNpTusGetDataA` + `Async` | yWEHUFkY1qI / xzG8mG9YlKY | :935 / :528 | `Bc5NtuDataGet` | :3508 / :3516 |
| `sceNpTusGetDataForCrossSave` + `Async` | 1TE3OvH61qo / CFPx3eyaT34 | :943 / :558 | `Bc5NtuDataGet`, cross-save order | :3540 / :3548 |
| `sceNpTusGetDataVUser` + `Async` | GQHCksS7aLs / 5R6kI-8f+Hk | :1063 / :567 | `Bc5NtuDataGet` | :3024 / :3032 |
| `sceNpTusGetDataAVUser` + `Async` | iaH+Sxlw32k / uoFvgzwawAY | :939 / :538 | `Bc5NtuDataGet` | :3524 / :3532 |
| `sceNpTusGetDataForCrossSaveVUser` + `Async` | -LxFGYCJwww / B7rBR0CoYLI | :380 / :371 | `Bc5NtuDataGet`, cross-save order | :3556 / :3564 |
| `sceNpTusGetFriendsDataStatus` + `Async` | DXigwIBTjWE / LUwvy0MOSqw | :947 / :577 | `Bc5NtuFriends` (:2785), option refused | :3040 / :3048 |
| `sceNpTusGetFriendsVariable` + `Async` | cy+pAALkHp8 / YFYWOwYI6DY | :951 / :587 | `Bc5NtuFriends`, option refused | :3056 / :3064 |
| `sceNpTusGetFriendsDataStatusA` + `Async` | yixh7HDKWfk / OheijxY5RYE | :416 / :408 | `Bc5NtuFriends`, option read | :3572 / :3580 |
| `sceNpTusGetFriendsDataStatusForCrossSave` + `Async` | TDoqRD+CE+M / 68B6XDgSANk | :428 / :420 | `Bc5NtuFriends`, option read | :3588 / :3596 |
| `sceNpTusGetFriendsVariableA` + `Async` | C8TY-UnQoXg / wrImtTqUSGM | :392 / :384 | `Bc5NtuFriends`, option read | :3604 / :3612 |
| `sceNpTusGetFriendsVariableForCrossSave` + `Async` | mD6s8HtMdpk / FabW3QpY3gQ | :404 / :396 | `Bc5NtuFriends`, option read | :3620 / :3628 |
| `sceNpTusGetMultiSlotDataStatus` + `Async` | pgcNwFHoOL4 / Qyek420uZmM | :955 / :617 | `Bc5NtuSlotStatusNpId` (:2832) | :3072 / :3080 |
| `sceNpTusGetMultiSlotDataStatusVUser` + `Async` | NGCeFUl5ckM / bHWFSg6jvXc | :975 / :646 | `Bc5NtuSlotStatusNpId` | :3088 / :3096 |
| `sceNpTusGetMultiSlotDataStatusA` + `Async` | 833Y2TnyonE / 7uLPqiNvNLc | :959 / :597 | `Bc5NtuSlotStatus` (:2813) | :3636 / :3644 |
| `sceNpTusGetMultiSlotDataStatusForCrossSave` + `Async` | DgpRToHWN40 / LQ6CoHcp+ug | :967 / :626 | `Bc5NtuSlotStatus` | :3668 / :3676 |
| `sceNpTusGetMultiSlotDataStatusAVUser` + `Async` | azmjx3jBAZA / 668Ij9MYKEU | :963 / :607 | `Bc5NtuSlotStatus` | :3652 / :3660 |
| `sceNpTusGetMultiSlotDataStatusForCrossSaveVUser` + `Async` | KBfBmtxCdmI / 4UF2uu2eDCo | :971 / :636 | `Bc5NtuSlotStatus` | :3684 / :3692 |
| `sceNpTusGetMultiUserDataStatus` + `Async` | NvHjFkx2rnU / 0zkr0T+NYvI | :979 / :675 | `Bc5NtuUsers` (:2852), count needed | :3136 / :3144 |
| `sceNpTusGetMultiUserDataStatusVUser` + `Async` | xwJIlK0bHgA / I5dlIKkHNkQ | :999 / :702 | `Bc5NtuUsers`, count needed, names | :3152 / :3160 |
| `sceNpTusGetMultiUserDataStatusA` + `Async` | lxNDPDnWfMc / kt+k6jegYZ8 | :983 / :656 | `Bc5NtuUsers` | :3764 / :3772 |
| `sceNpTusGetMultiUserDataStatusForCrossSave` + `Async` | cVeBif6zdZ4 / lq0Anwhj0wY | :991 / :683 | `Bc5NtuUsers` | :3796 / :3804 |
| `sceNpTusGetMultiUserDataStatusAVUser` + `Async` | fJU2TZId210 / WBh3zfrjS38 | :987 / :664 | `Bc5NtuUsers`, names | :3780 / :3788 |
| `sceNpTusGetMultiUserDataStatusForCrossSaveVUser` + `Async` | w-c7U0MW2KY / H6sQJ99usfE | :995 / :691 | `Bc5NtuUsers`, names | :3812 / :3820 |
| `sceNpTusGetMultiUserVariable` + `Async` | 6G9+4eIb+cY / YRje5yEXS0U | :1003 / :732 | `Bc5NtuUsers`, count needed | :3168 / :3176 |
| `sceNpTusGetMultiUserVariableVUser` + `Async` | zB0vaHTzA6g / xZXQuNSTC6o | :1019 / :763 | `Bc5NtuUsers`, count needed, names | :3184 / :3192 |
| `sceNpTusGetMultiUserVariableA` + `Async` | Gjixv5hqRVY / eGunerNP9n0 | :1007 / :713 | `Bc5NtuUsers` | :3828 / :3836 |
| `sceNpTusGetMultiUserVariableForCrossSave` + `Async` | Q5uQeScvTPE / oZ8DMeTU-50 | :748 / :740 | `Bc5NtuUsers` | :3860 / :3868 |
| `sceNpTusGetMultiUserVariableAVUser` + `Async` | fVvocpq4mG4 / V8ZA3hHrAbw | :1011 / :721 | `Bc5NtuUsers`, names | :3844 / :3852 |
| `sceNpTusGetMultiUserVariableForCrossSaveVUser` + `Async` | Djuj2+1VNL0 / 82RP7itI-zI | :1015 / :752 | `Bc5NtuUsers`, names | :3876 / :3884 |
| `sceNpTusSetData` + `Async` | 4NrufkNCkiE / G68xdfQuiyU | :1075 / :798 | `Bc5NtuDataSet` (:2874) | :3200 / :3208 |
| `sceNpTusSetDataA` + `Async` | VzxN3tOouj8 / 4u58d6g6uwU | :1023 / :774 | `Bc5NtuDataSet` | :3900 / :3908 |
| `sceNpTusSetDataVUser` + `Async` | +RhzSuuXwxo / E4BCVfx-YfM | :1079 / :810 | `Bc5NtuDataSet` | :3216 / :3224 |
| `sceNpTusSetDataAVUser` + `Async` | kbWqOt3QjKU / Fmx4tapJGzo | :1027 / :786 | `Bc5NtuDataSet` | :3916 / :3924 |
| `sceNpTusTryAndSetVariable` + `Async` | ukC55HsotJ4 / xQfR51i4kck | :1031 / :848 | `Bc5NtuTrySet` (:2890), bad op INVALID_ARGUMENT | :3248 / :3256 |
| `sceNpTusTryAndSetVariableVUser` + `Async` | ZbitD262GhY / trZ6QGW6jHs | :1051 / :886 | `Bc5NtuTrySet`, bad op INVALID_ARGUMENT | :3264 / :3272 |
| `sceNpTusTryAndSetVariableA` + `Async` | 0up4MP1wNtc / bGTjTkHPHTE | :1035 / :822 | `Bc5NtuTrySet`, bad op INVALID_TYPE | :3974 / :3982 |
| `sceNpTusTryAndSetVariableForCrossSave` + `Async` | MGvSJEHwyL8 / JKGYZ2F1yT8 | :1043 / :860 | `Bc5NtuTrySet`, bad op INVALID_TYPE | :4006 / :4014 |
| `sceNpTusTryAndSetVariableAVUser` + `Async` | oGIcxlUabSA / uf77muc5Bog | :1039 / :835 | `Bc5NtuTrySet`, bad op INVALID_TYPE | :3990 / :3998 |
| `sceNpTusTryAndSetVariableForCrossSaveVUser` + `Async` | fcCwKpi4CbU / CjVIpztpTNc | :1047 / :873 | `Bc5NtuTrySet`, bad op INVALID_TYPE | :4022 / :4030 |
| `sceNpTssGetData` + `Async` | -SUR+UoLS6c / DS2yu3Sjj1o | :442 / :432 | `Bc5NtuTssData` (:2905) | :3288 / :3296 |
| `sceNpTssGetSmallStorage` + `Async` | lL+Z3zCKNTs / f2Pe4LGS2II | :899 / :446 | `Bc5NtuTssSmall` (:2923) | :3304 / :3312 |

Already match: none. Every NpTus stub answers 0x80550005 today, which AnyPS5 answers for none of them.

**HELD** (6, today's 0x80550005 kept). AnyPS5 does not implement them: each is a `NotImplemented_nid_no_patch` placeholder
that returns 0, sweep kind "pending", and the debt note says "unknown signature".
- `sceNpTusSetThreadParam`: 6GKDdRCFx8c, AnyPS5 `:217`, output `:3964`.
- `sceNpTusCreateTitleCtx`: hhy8+oecGac, AnyPS5 `:232`, output `:3423`.
- `sceNpTusSetTimeout`: KMlHj+tgfdQ, AnyPS5 `:237`, output `:3969`.
- `sceNpTusChangeModeForOtherSaveDataOwners`: wjNhItL2wzg, AnyPS5 `:242`, output `:3402`.
- `sceNpTssGetStorage`: IVSbAEOxJ6I, AnyPS5 `:361`, output `:3320`.
- `sceNpTssGetStorageAsync`: k5NZIzggbuk, AnyPS5 `:366`, output `:3325`.

Their size is 0 logic lines; there is no behaviour to port. AnyPS5's own answer is 0 plus a log line. Taking that 0 would
invent a success with no known signature, so it is not taken.

## Split state and dependencies

- **No live NpTus functions.**
  - tld's scratch `e6\tld\tables.json`: `Libs::NpTus::InitNpTus_1`, 142 records, `same_key` 0, `nid_any` 0.
  - My scan (`e7/tbt/overlap.py`, every quoted NID in every `.cpp/.h/.inc/.hpp` of the e7 tree outside the NpTus
    namespace): 0 of the 142 NIDs occur anywhere else.
  - Nothing outside the namespace changes and the 142 registration lines are byte-identical, so no NID is added that a live
    table registers.
- **No NpManager/NpCommon state is used**, and none is needed:
  - TUS has its own title contexts (one table with TSS) and its own request ids, which are separate from
    `sceNpCreateRequest`'s (network.cpp).
  - It reads no sign-in state: AnyPS5's contexts never ask. The NpId forms only check the pointer, and the user (A) forms
    check nothing.
  - shadPS4 asks `sceNpGetNpId` in `sceNpTusCreateNpTitleCtxA`. Ours is live, `network.cpp:4568-4582`, and answers
    0x80550006 with a zeroed NpId, so the shadPS4 model would refuse every A-form context. The AnyPS5 model followed here
    makes it.
  - The signed-out answer is 0x80550006, the same code network.cpp's live NpManager and tbn's NpManager port use. The
    file-level `NP_NOT_SIGNED_IN` (0x80550005) stays only on the off path; its TODO(verify) at input `:41-43` still stands.

## Test (`tbt0405.cpp`)

The test registers `InitNpTus_1` into its own `SymbolDatabase` and takes every function with the exact key a title's import
uses (`libSceNpTus` v1, module 1.1). Functions are looked up by name through the test's own 142-row NID table, which was
generated from the sweep and checked equal to the output's `LIB_FUNC` lines. It needs no subsystem. Watchdog 60 s.

- **On: 77 cases.**
  - Registration (1): 142 NIDs by the exact key and by `FindByNid`; the symbol dump has exactly 142 records.
  - Core (12):
    - The NpId context checks and their order, for TSS and TUS; the user forms take any label and user.
    - 32 contexts across TUS and TSS, then TOO_MANY_OBJECTS; delete, delete again, make another.
    - Requests on unknown or deleted contexts.
    - A new request: poll 1, wait INVALID_ARGUMENT, nothing written.
    - Unknown ids for delete, abort, poll and wait.
    - Delete twice.
    - A started request: poll and wait give SIGNED_OUT, null results are taken, the blocking form answers SIGNED_OUT, and
      the content length is not written.
    - Abort before a start: poll stays 1, and the start finishes ABORTED in the async and blocking forms.
    - Abort after a start: poll keeps SIGNED_OUT, and the next start is ABORTED.
    - 256 requests across contexts, then TOO_MANY_OBJECTS; deleting a context drops its requests.
  - Pairs (63, one case per `*Async`/blocking pair, 799 checks in all).
    - Each check covers the async form's answer and request state (poll and wait), the blocking form, and both forms on an
      unknown request; then one abort run.
    - Checks per family:
      - The slot families: null array or slot ids, no slot or count -1, an option, 64 and 65 slots, a negative id, and the
        pairs that show the order.
      - User forms: null user, empty name, empty name with the other errors.
      - Add: the five check orders.
      - Get data: option first, or option and slot first in the cross-save forms.
      - Friends: 100/101, the sort limits, an option refused or read (size 0x10, start rank 0 or 1, no rank).
      - Users: 101/102, the empty third name with 3 and 2 users, entries not read in the non-name forms.
      - Set data: send = total and send > total.
      - Try-set: operations 0/6/7, INVALID_TYPE vs INVALID_ARGUMENT.
      - TSS data: slots 15/16/-1, null status with any size, status size 0x10, option sizes 0x20/0x18 and their order.
      - TSS small storage: 64 KiB and 64 KiB + 1, an option.
    - Every output buffer is checked untouched.
  - Held (1): the 6 held stubs answer 0x80550005.
  - Ends `tbt0405: on 77 of 77; end`.
- **Off: 75 cases.**
  - Registration (1).
  - The 10 core calls (10), each 0x80550005 with poll's and wait's result untouched.
  - 63 pairs (63), each form 0x80550005 with nothing written.
  - Held (1).
  - Ends `tbt0405: off 75 of 75; end`. Unset gives the same.
- **Off expectations from today's code:** every NpTus stub in the input is exactly `PRINT_NAME(); return NP_NOT_SIGNED_IN;`.
  That is 142 of 142, checked by the script and by a grep of input `:2431-3145`, and `NP_NOT_SIGNED_IN` is 0x80550005
  (input `:44`). The off path adds only the false branch.
- An argument that disagrees with the switch exits 2. There is a single switch, so "mixed" cannot occur.

## Risks

- **Titles see different answers on.** A title that today gets 0x80550005 from every TUS call now gets:
  - real context and request ids;
  - argument errors in the 0x805507xx range for bad calls;
  - 0x80550006 (signed out) from each request: from the blocking call, and from poll/wait after an `*Async` call.
  A title that treated 0x80550005 as "skip online features" but handles 0x80550006 differently could take another path.
  Both mean signed out. TODO(verify) on the box with a title that uses TUS.
- **No output is written.** A title that reads its variable array after a failed request reads its own memory. AnyPS5 and
  shadPS4 offline behave the same.
- **Abort stays set** (AnyPS5): every later start of that request finishes ABORTED. In shadPS4 an abort ends only the
  running operation.
- **Ids never repeat.** Context and request ids are counters, as in AnyPS5; a title that creates more than 2^31 would wrap.
- **Thread safety.** One mutex guards the table. Guest arrays and options are read outside it, as AnyPS5 does.
- **Not applied:** the 13.42 emulator-run differences (Source, "Not taken"). **TODO(verify):** `dbc28c0a9`'s "measured".

## Verified on the laptop

- `mktbt0405.py <e7 input tree> <out>` prints `src/libs/libNp.cpp eb3bfe9d56f0fcdddf29199846f46fb5`.
  - It refuses its own output ("the unit has the edit already"), an input with another md5 ("not the pinned input"), and a
    CR in the unit.
- The built-in checks pass:
  - every anchor occurs once, inside `namespace NpTus`;
  - each edit keeps the balance of braces, parentheses and brackets;
  - the `Bc5NtuOn()` uses number 138 and the switch-name count is right;
  - before and after the namespace the file is byte-identical;
  - the held stubs and the 142 registration lines are unchanged;
  - undoing the edits gives the input back byte for byte;
  - the inserted text is ASCII and the file stays LF.
- Chaining with another agent's edits: see the top of this note (`e7/tbt/chain/chain.py`).
- **Syntax:** Visual Studio's clang++ (clang 22, MSVC target) with `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`.
  - Setup: the stand-in `cmake_config.h` and POSIX headers of `scratchpad/lib0405chk/stub`, fmt from Inori_GPCS4, magic_enum
    from InoriRus_Kyty, and tbn's `sched_param` stand-in (`-include e6/tbn/sched_standin.h`; MSVC has no `<sched.h>`).
  - The input, the output and `tbt0405.cpp` are clean. Script: `e7/tbt/chk.sh`.
- **Stand-in run** (`e7/tbt/standin/build.sh`, not a deliverable):
  - The build links the real `tbt0405.cpp`, the real output `libNp.cpp` (both with `-Wall -Wextra -Werror`), the real
    `loader/symbolDatabase.cpp` of the e7 tree and fmt.
  - `standin.cpp` supplies logging/timer/file and abort-if-called stand-ins for the kernel and network.cpp calls that tbn's
    tables reference. The test never reaches them.
  - Results: `KYTY_BC5_LOAD_NPTUS=1`: `tbt0405: on 77 of 77; end`, exit 0. `=0` and unset: `tbt0405: off 75 of 75; end`,
    exit 0. The journal lines printed are as above.
- **Negative run** (`e7/tbt/neg`): the same test against a copy of the output with three checks deliberately changed:
  1. TOO_MANY_SLOTID instead of TOO_MANY_NPID in the NpId/VUser data-status forms;
  2. the output checked first in the cross-save add form;
  3. TSS slot 16 accepted.

  It fails exactly the four pairs those touch and exits 1:
  - case 29 `sceNpTusGetMultiSlotDataStatus` (65 slots: 0x80550718, want 0x80550719);
  - case 30 `...DataStatusVUser` (the same);
  - case 37 `sceNpTusAddAndGetVariableForCrossSave` (out null with an option: 0x8055070c, want 0x80550704);
  - case 75 `sceNpTssGetData` (slot 16: accepted, want 0x80550704).

  The run ends `tbt0405: on 73 of 77 passed; FAIL`. Run with the switch unset and the argument `on`, the test exits 2.
- **Not checked:** the box's Linux compile and link (gcc/clang, the real build0401 gate with every emulator object), and
  running `tbt0405.cpp` on Linux. The box build is the first real run.

## Files

| File | md5 |
|---|---|
| `mktbt0405.py` | `cf1a78e216896adf1d5a0c679d457785` |
| `tbt0405.cpp` | `d322561d983bfcf9b976f50aea257a97` |
| input `src/libs/libNp.cpp` (e6's output, e7 input tree) | `24e778261495abcd5a069396f14b28b4` |
| output `src/libs/libNp.cpp` | `eb3bfe9d56f0fcdddf29199846f46fb5` |

## Case counts

On: 77 cases (registration 1, core 12, pairs 63 with 799 checks, held 1), ending `tbt0405: on 77 of 77; end`.
Off (`=0` or unset): 75 cases (1, 10, 63, 1), ending `tbt0405: off 75 of 75; end`.
