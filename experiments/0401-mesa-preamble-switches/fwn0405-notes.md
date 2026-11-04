# fwn0405: exp 0405 decision-1 items in Rtc, Rudp, Net, SystemService, NpCppWebApi, Pad/Mouse, UserService (series e6)

Port agent `fwn`, 2026-11-04. Files: `mkfwn0405.py` (the edit), `fwn0405.cpp` (the CPU test), this note.
Inputs: the e6 input tree (`scratchpad/e6/e5tree`): e5's sources.
- `libSystemService.cpp` and `libNpCppWebApi.cpp` are e5 units (md5 as in `E5-FILES.txt`).
- `libRtc.cpp`, `libRudp.cpp` and `network.cpp` are base-tree files (KytyPlus f266548 + patch 0001); their md5s were computed and pinned here.

Specs:
- exp 0405 `raw/r1-anyps5.md` §1 row 35;
- e5's `lib0405-notes.md` "Item 4";
- every `excluded-provenance` row of `raw/r1-verdicts/*.tsv` whose library is hosted in this group's files.

The rule applied is the maintainer's decision 1, as the e6 brief states it:
- **Port** when the upstream note names a firmware run (native or emulated) or a reading of a module's behaviour.
- **Hold** when it names SDK headers, decrypted firmware, a disassembly with addresses as the source, an IDA database,
  or a title's own libc.prx.

## Switch and journal lines

One switch for the group, `KYTY_BC5_FW_NET`. It is off by default and read once per unit (a function-local static).
- Unset, empty or `0` means off. Off is today's path: every edit only adds lines, and no line of today's code is changed
  or removed (checked by diff: `-0` lines in all five units).
- Any other value turns all items on, unless it names items as a comma list: `rtc`, `rudp`, `resolver`, `param400`,
  `npwebapi`.

| Unit | Item | Bit |
|---|---|---|
| `src/libs/libRtc.cpp` | `rtc` | 1 |
| `src/libs/libRudp.cpp` | `rudp` | 2 |
| `src/libs/network.cpp` | `resolver` | 4 |
| `src/libs/libSystemService.cpp` | `param400` | 8 |
| `src/libs/libNpCppWebApi.cpp` | `npwebapi` | 16 |

- **Journal line.** One line on stderr, printed by libRtc.cpp at its registration (`Libs::InitAll`), on or off:
  `[bc5] exp 0405: fw-net on (items: rtc rudp resolver param400 npwebapi)` or `[bc5] exp 0405: fw-net off`.
  The other four units parse the same variable with the same rule and stay silent.
- **Catchers** (only when on, at most 8 per unit): `[bc5] exp 0405: fw-net <what>`, each time an answer differs from
  today's. Examples:
  - `fw-net rtc: FormatRFC3339 past year 9999: the 16-bit year rule (0x80B50003 when off)`
  - `fw-net rudp: SetEventHandler before sceRudpInit -> 0x80770001, not stored (stored and 0 when off)`
  - `fw-net resolver: StartNtoa timeout under 1 s or a negative retry -> NET_ERROR_EINVAL (looked up when off)`
  - `fw-net param400: ParamGetInt(400) answers the language (0 when off)`
  - `fw-net npwebapi: finish of a never-started transaction -> 0x80553508 (0 when off)`

## Item 1a: R1 #35, Rtc far-year handling: PORTED (`rtc`)

**Source.**
- AnyPS5 4f41f4c37 (GPL-2.0-only), `core/libs/prx/libSceRtc/Export.cpp:578-599` (sceRtcFormatRFC3339).
- Commit 4dd4ec5ff (BunnyFl), "check the 16-bit year when formatting far ticks".

**Upstream notes naming the run** (`docs/dev/debt/libSceRtc.md`):
- :12, the 16-bit year: "From firmware 13.42's module run natively: the year rule with SDK versions 0x01000051,
  0x03000000 and 0x0A000000 ... not measured on a console".
- :14: native formatting confirms the zone limit of -1439 to 1439 minutes.
- :11: the 64-bit zone-shift overflow rule. This one is a PS4 10.71 / PS5 13.60 console measurement, already
  acceptable before decision 1.

**Ours.** `libRtc.cpp:348` (input = base):
- A tick past year 9999 returns INVALID_VALUE (0x80B50003, from RtcSetTick).
- A zone outside the limit is formatted.
- `UINT64_MAX` with an eastern zone wraps to year 1 and formats.

**Change** (output `src/libs/libRtc.cpp`):
- Block :326-471, with `Bc5RtcFormatRFC3339` and the group switch.
- Branch :480 (after today's null-text check).
- Includes :8, :12-13.
- Registration line :720.

**With `rtc` on:**
- A null tick means now, as today.
- A zone outside ±1439 gives INVALID_VALUE.
- A zone shift that overflows or underflows 64 bits gives INVALID_VALUE.
- The date is computed with RtcSetTick's own day arithmetic in 64 bits. Only the year is then cut to 16 bits.
- A 16-bit year of 0 or above 9999 gives INVALID_YEAR (0x80B50008). Otherwise the date is formatted with the wrapped
  year, in today's format.
- On every error the text is left unwritten.

**Not taken.**
- RFC2822 and RFC3339Precise: they are not registered here (R1 #24, Rtc's 25 missing exports).
- AnyPS5's PS4-title SDK gate `rangeChecked()`: a PS5 title always gets the checked rules (debt :11).

**Test.** 12 cases, each run both ways. AnyPS5's vectors (GuestRtc.cpp, 4dd4ec5ff) are used.

| Case | On | Off (today) |
|---|---|---|
| year 65536 | YEAR | VALUE |
| year 65537 +60 | `0001-01-01T01:00:00.00+01:00` | VALUE |
| year 75535 -60 | `9998-12-31T23:00:00.00-01:00` | VALUE |
| year 10000 | YEAR | VALUE |
| `UINT64_MAX` +1 | VALUE | `0001-01-01T00:00:59.99+00:01` |
| epoch zone 1440 | VALUE | `1970-01-02T00:00:00.00+24:00` |

These six give the same answer both ways:
- tick 0 with zone -1 gives VALUE;
- the last tick of 9999 gives `9999-12-31T23:59:59.99Z`;
- epoch +120;
- AnyPS5's distant tick at -821;
- a null text gives 0x80B50002;
- a null tick (now) gives a 23-character `2YYY-...Z`.

Error cases also check that the text was not written. The expected texts were computed on the laptop with a Python copy
of the same arithmetic, and they match AnyPS5's test.

**Risks.**
- Low. Only ticks past year 9999, zones beyond ±1439, and the eastern overflow change.
- TODO(verify): a console run (the source is a native run of the module, not a console).

## Item 1b: R1 #35, Rudp SetEventHandler checks: PORTED (`rudp`); bind/listen/accept HELD (missing exports)

**Source.**
- AnyPS5 4f41f4c37, `core/libs/prx/libSceRudp/Export.cpp:269-280`.
- Commit 11f42d025 (zaryabzip), "bind, listen and accept as a firmware 13.42 run shows".

**Upstream note.** `docs/dev/debt/libSceRudp.md:23`: "returns `0x80770001` before initialization and `0x80770022` for a
null handler, and `sceRudpEnd` clears the handler, as the 13.42 run under an emulator with imports stubbed shows; not
measured on a console". The run is BunnyFl's, AnyPS5 issue 13682.

**Ours.** `libRudp.cpp:44`: the handler is stored and 0 returned, always.

**Change** (output `src/libs/libRudp.cpp`):
- Block :48-119 (`Bc5RudpSetEventHandlerCheck`).
- Check :128, before the store.
- Includes :7, :10-12.
- On, before sceRudpInit the call returns 0x80770001 and a null handler 0x80770022. Neither error stores the handler.

**Held (missing exports, later).**
- sceRudpEnd (and its handler clear), CreateContext, Bind, Listen, Accept and Terminate are not registered here.
- They need a context model: R1 #39, Rudp's 31 missing exports, L, about 3.5 days.

**Test.** 3 cases:
- before Init: on 0x80770001, off 0;
- after Init, a null handler: on 0x80770022, off 0;
- after Init, a real handler: 0 both ways.

**Risks.**
- Low. A title that sets its handler before sceRudpInit now gets an error, as in the run. The handler then stays unset,
  but nothing in our Rudp calls it.

## Item 1c: R1 #35, Net resolver timeout under 1 s: PORTED (`resolver`)

**Source.**
- AnyPS5 4f41f4c37, `core/libs/prx/libSceNet/Export.cpp:2547-2552`.
- Commit ce093095f (zaryabzip), "refuse resolver timeouts below one second as firmware 13.42 does".

**Upstream note.** `docs/dev/debt/libSceNet.md:98`:
- A negative timeout or retry fails with EINVAL before anything else is checked, "as prosper's reading of the libSceNet
  module gives" (prosper 6c09a34a `hle_net.cpp:579-587`).
- "A timeout from 1 to 999999 also fails with `EINVAL` before the resolver is looked up, and 0 counts as 1000000, as
  @BunnyFl's 13.42 run of the module shows" (AnyPS5 PR 9727).

**Ours.** `network.cpp:1446`: the timeout and the retry count are ignored.

**Change** (output `src/libs/network.cpp`):
- Block :1446-1511 (`Bc5NetResolverArgsRefused`).
- Check :1526, before today's null and flag checks, so it also comes before the resolver lookup.
- On, a timeout below 0, a timeout from 1 to 999999, or a negative retry gives NET_ERROR_EINVAL (0x80410116). The net
  errno is set through libNet.cpp's NET_CALL, as today.
- The timeout is still not applied: one synchronous host lookup, as today.

**Test.** 10 cases with the literal `127.0.0.1` (no host lookup):

| Timeout / retry | On | Off |
|---|---|---|
| timeout 0 | OK | OK |
| timeout 1 | EINVAL | OK |
| timeout 999999 | EINVAL | OK |
| timeout 1000000 | OK | OK |
| timeout INT_MAX | OK | OK |
| timeout -1 | EINVAL | OK |
| retry -1 | EINVAL | OK |
| unknown resolver, timeout 1 | EINVAL | EBADF |
| unknown resolver, timeout 0 | EBADF | EBADF |
| flags 2 | EINVAL | EINVAL |

On an error the case also checks that the address is untouched and the errno is set.

**Risks.**
- Low-medium. A title that passes a sub-second timeout (for example 500 ms) loses name resolution when the item is on,
  as on the 13.42 module.

## Item 2: SystemService parameter 400 = the language: PORTED (`param400`, its own item)

**Source.**
- AnyPS5 4f41f4c37, `core/libs/prx/libSceSystemService/Export.cpp:549-566` (:555: 400 answers as parameter 1).
- `docs/dev/debt/libSceSystemService.md:70`: "in the PS5 10.01 and 12.60 `libSceSystemService` modules parameter 400
  reads the same registry value as parameter 1". This is a module reading, accepted under decision 1. It is the value
  e5 held (`lib0405-notes.md` Item 4).
- :74, a measurement: a 13.40 console answers 400.

**Ours.** The e6 input `libSystemService.cpp:278`: the default branch answers 0, with an "unsupported" log line.

**Change** (output `src/libs/libSystemService.cpp`):
- Block :252-319 (`Bc5SysParam400`), placed after e5's block.
- Branch :349, at the top of the default branch.
- Include :15.
- On, 400 answers what parameter 1 answers here: `HostInputSystemLanguage()`, else `--console-language`.
- It does not depend on e5's `KYTY_BC5_SYSTEMSERVICE_VALUES`, whose `int` item already lets 400 answer and whose `table`
  item does not touch it.

**Not modelled.** The modules' SDK-version mapping of parameter 1, and their 0x80A10003 when an unidentified import
returns 1. AnyPS5 models neither.

**Test.** 3 cases:
- parameter 1 is answered;
- 400: on, parameter 1's value; off, 0;
- 401: 0 both ways (e5's switches are unset by the test).

**Risks.** Low. A title that asks for 400 first (PPSA01325, per debt :70) now gets the configured language instead of 0
(Japanese).

## Item 3: the `excluded-provenance` rows of this group (r1-verdicts C.tsv, D1.tsv, D2.tsv)

Every row, with the TSV note quoted:

| Row (lib, sha) | TSV note | Verdict |
|---|---|---|
| NpCppWebApi 08fa66176 | "finish returns 0x80553508 per the bundled PPSA21564 module; ours returns 0 at :580 :717 :725 :749. Maintainer call on provenance." | **PORTED** (`npwebapi`): a module reading; no address or disassembly named (commit text and debt note checked) |
| NpCppWebApi f21a6b321 | "String used-size at +0x10, 0x80553503/0x80553504 from the bundled module; ours treats +0x10 as capacity and returns 0 for null text." | port-eligible (module reading); **held for time**: M (~0.5 d), changes String layout semantics used everywhere in the unit |
| NpCppWebApi c207cb884 | "Moves Vector<String> refcount to +0x38 per the bundled module; touches ours :359 :616 :704 :803 (we count at +0x30)." | port-eligible; **held for time**: M (~0.5 d), layout, risky |
| NpCppWebApi 705487269 | "0x80553502/03/0f/10/12 from the bundled module; ours returns 0 in our initialize/terminate (:446 :450 :608 :692 :300)." | port-eligible; **held for time**: S-M (~3 h), needs real arguments and per-object state |
| NpCppWebApi fcf9754a2 | "ParameterToDownloadData initialize/terminate codes from the bundled module; ours returns 0 (:191 :195)." | port-eligible; **held for time**: S-M (~2 h), same shape as 705487269 |
| Net 0a4d4e792 | "Read from libSceNet.sprx wrapper at 0x153f0; lFJb+BlPK1c also unregistered in ours." | **HELD, provenance** (a disassembly with an address); also a missing export |
| Net 81bc35886 | "Read from FUN_00006be0/FUN_000072d0 in libSceNet.sprx." | **HELD, provenance** (decompiler function addresses) |
| SystemService 126a40816 | "Codec activation calls follow fw 13.42 libSceSystemService read from disassembly (debt codec-activation entry). NIDs unregistered here anyway." | port-eligible (a module reading; no address named in the commit); **missing export, later** (S each once registered) |
| SystemService 5a161a06b | "Duplicate of 126a40816 (same patch): codec activation from fw 13.42 disassembly." | as 126a40816 |
| SystemService f87932d30 | "GetPSButtonEvent (gbUBqHCEgAI) follows fw 13.42 read from disassembly, not measured (debt query-payloads entry)." | port-eligible (module reading); **missing export, later** (S) |
| UserService 950918663 | "IsGuestUser/IsSharePlayClientUser/GetIsSpartacusEnabled from fw 13.42 disassembly plus native run (debt entry). NIDs unregistered here." | port-eligible (native run); **missing export, later** (S, three registrations) |
| UserService ed71528da | "GetNpAccountId null-before-user order from disassembly and native run with stubbed imports (#12165); NID 6dfDreosXGY unregistered here." | port-eligible; **missing export, later** (S) |
| UserService 9c55d9117 | "Null-presets-before-login order cites fw 13.42 disassembly; ours already checks null first (libs/libUserService.cpp:147)." | **already match**: e6 input `libUserService.cpp:243` checks `presets == nullptr` first |
| Pad b94b3fa32 | "BunnyFl 13.42 libScePad disassembly (issue 15087; docs/dev/debt/libScePad.md:60)" | **HELD, provenance**: the commit names "@BunnyFl's corrected reading of 0xe8a0" (a disassembly with an address); GetInfoByPortType is also not registered |
| Pad 3b404f65e | "BunnyFl 13.42 libScePad disassembly (commit message; docs/dev/debt/libScePad.md:60)" | **HELD, provenance**: the same reading (debt :60 cites the 13.42 `libScePad.sprx` disassembly by SHA-256, b94b3fa32 by address); its 13 exports are not registered here |
| Pad 2f9581050 | "firmware 13.42 checks from disassembly and native run (docs/dev/debt/libScePad.md:47); NIDs unregistered here (inventory)" | port-eligible (native run); **missing export, later**: S (5 queries, ~40 lines). It needs the pad init state and the open-handle state, which live in `controller.cpp`, outside this group, and no header edit is allowed |
| Mouse 26d7585cf (also listed under VideoOut) | "firmware 13.42 libSceMouse read and run natively (commit message; docs/dev/debt/libSceMouse.md:29)" | port-eligible (native run); **missing export, later**: M (~0.5 d; 4 exports, AnyPS5 mouse_impl +167 lines: screen sizes, curve, 40-byte record) |

**Item `npwebapi`, in detail.**
- Source: AnyPS5 4f41f4c37 `core/libs/prx/libSceNpCppWebApi/Export.cpp:11` (TransactionNotStarted) and its finish
  overrides; commit 08fa66176 (Alexandre Figueiredo).
- Ours: the five finish functions at e6 input `libNpCppWebApi.cpp:234, 580, 717, 725, 749` return 0.
- Output `src/libs/libNpCppWebApi.cpp`:
  - block :53-116;
  - branches :301, 650, 790, 801, 828;
  - include :30.
- On, they return 0x80553508. Every request here fails before it starts (NOT_SIGNED_IN), so every transaction is a
  never-started one.
- Not taken: abort and getId (not registered here), and the commit's constructor changes.
- Test: 5 cases. On 0x80553508, off 0.
- Risk: low. Titles call finish after a failed start, and the module answers the same.
- Note for the top session: the module is the one bundled with a title (PPSA21564). Decision 2 names only titles'
  libc.prx, so this row is ported. If decision 2 is meant to cover any module a title bundles, leave `npwebapi` off;
  it is its own item.

**Totals for this group.**

| Verdict | Count | Rows |
|---|---|---|
| Ported | 1 | 08fa66176 |
| Already match | 1 | 9c55d9117 |
| Held for provenance | 4 | b94b3fa32, 3b404f65e, 0a4d4e792, 81bc35886 |
| Port-eligible, held for time | 4 | NpCppWebApi f21a6b321, c207cb884, 705487269, fcf9754a2 |
| Port-eligible, missing export (later) | 7 | 126a40816, 5a161a06b (duplicate), f87932d30, 950918663, ed71528da, 2f9581050, 26d7585cf |

## CPU test `fwn0405.cpp`

**Build.**
```
build0401.py ... src/libs/libRtc.cpp=<out>/src/libs/libRtc.cpp src/libs/libRudp.cpp=<out>/... src/libs/network.cpp=<out>/... src/libs/libSystemService.cpp=<out>/... src/libs/libNpCppWebApi.cpp=<out>/... --gate fwn0405.cpp <bin> --like src/libs/libRtc.cpp
```
- The `--like` unit is `src/libs/libRtc.cpp`.
- If e5's private `libSystemService.cpp`/`libNpCppWebApi.cpp` are in the same build, this script's outputs replace
  them; the outputs contain e5's edits.

**How it runs.**
- It starts Core, Threads, Config, Log, Timer, Memory and Pthread, as lib0405.cpp does, plus the Network subsystem
  (deps core, log, pthread, as in emulator.cpp).
- It runs `Libs::InitAll` into its own SymbolDatabase and calls the functions by NID.
- It unsets `KYTY_BC5_INPUT_CONFIG` and e5's two SystemService switches.
- It needs no game, GPU, window, sound device or network. No fork, no guest thread.
- Watchdog: 60 s.

**Runs.**
- `KYTY_BC5_FW_NET=1` prints `fwn0405: on 33 of 33; end`.
- `=0` or unset prints `fwn0405: off 33 of 33; end`.
- An item list prints `mixed`; each case then follows its own item.

**Cases.** 33 both ways: rtc 12, rudp 3, resolver 10, param400 3, npwebapi 5. No off case aborts, so none needs a child.

## Laptop verification (2026-11-04)

**The script.**
- `python -I mkfwn0405.py <e6 tree> <out>` applies to the e6 input tree and prints the five md5s below.
- A second run gives the same md5s.
- With an output unit put back in a copy of the tree, it refuses ("the unit has the edit already") and writes nothing.
- The script itself asserts:
  - each pinned input md5;
  - each anchor exactly once;
  - the blocks' prerequisites before them, and their users after;
  - brace, parenthesis and bracket balance per block, per edit and per unit;
  - the expected count of each helper name;
  - that the inserted text is ASCII and LF stays LF;
  - that undoing every edit and removing the blocks gives the input back byte for byte.
- `diff` input/output: only added lines in all five units (+154, +82, +70, +73, +81; -0).

**Syntax.** Visual Studio 18 clang++ (x86_64-pc-windows-msvc), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with
e5's stand-ins (lib0405chk/stub: `cmake_config.h`, POSIX `unistd.h`) and fmt from `refs/Inori_GPCS4` (`-isystem`).
`scratchpad/fwnchk/chk.sh` is the command.
- Clean: the five inputs and the five outputs, and `fwn0405.cpp`.
  - `libNpCppWebApi.cpp` input and output both fail only with the already-present
    `-Wunused-const-variable` (`VectorReferenceCountOffset`, input :62). They are clean without that warning.
- With `-Wshadow -Wconversion -Wsign-conversion` added:
  - inputs and outputs have the same counts (libRtc 2, network 32, the others 0);
  - `fwn0405.cpp` is clean.
- A negative control (an unused variable in a copy of the test) is caught.
- `fwn0405.cpp`: ASCII, LF, no NUL, balanced.

**Not checked on the laptop.**
- The Linux branches. The new code is not platform-specific; network.cpp's resolver change sits above its `_WIN32`
  split.
- GCC on the box (`-Wformat-truncation` on the zone buffer: the zone is bounded to ±1439 before the `snprintf`, as in
  today's code), the link, and running the test.

## Files

| File | md5 |
|---|---|
| input `src/libs/libRtc.cpp` (base) | e1689ac69353d76f206bd7bb7736d3b8 |
| input `src/libs/libRudp.cpp` (base) | 9fbe2847b2aa61564c9eea80ceb4617a |
| input `src/libs/network.cpp` (base) | 98d501f4e09322ab8727dd65ff0ea45c |
| input `src/libs/libSystemService.cpp` (e5) | 4aa00c539657776620a49e222f3f8fa2 |
| input `src/libs/libNpCppWebApi.cpp` (e5) | 935fcc7e4ab1108f3d2d8b33eaf65bf6 |
| output `src/libs/libRtc.cpp` | 719561dd7cc51c965c9ae97a07df01fb |
| output `src/libs/libRudp.cpp` | af8d0178fa63f7e5a2f5bf2d72d9690c |
| output `src/libs/network.cpp` | 598cfe806da831d5a07a5f506d13a03c |
| output `src/libs/libSystemService.cpp` | 252a35f9f9b482e9c9fb74b2c0740a2f |
| output `src/libs/libNpCppWebApi.cpp` | e613bc8fcc3f58fe5b5ff3be47a9cc46 |
| unchanged in this group (e5) `libNet.cpp`, `libUserService.cpp`, `libPad.cpp` | 35773d6e…, e3d34e98…, 89a047a4… |
| `mkfwn0405.py` | f0d1ce0a52a5b836f5c87e62bee3180e |
| `fwn0405.cpp` | 8048213b9de7c4eac2f56f5a3a4db9c2 |
