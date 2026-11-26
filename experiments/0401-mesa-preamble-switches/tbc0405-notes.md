# tbc0405: Zlib, JpegEnc and Ime tables ported (exp 0405 decision 4, batch 1, series e6)

Tag `tbc`. Files: `mktbc0405.py` (the edit), `tbc0405.cpp` (the CPU test), this file.

**What it is.** Three of the 32 tables that are compiled but never loaded by `Libs::InitAll`. Under decision 4 they are
ported first. Tag `tld` (libs.cpp) then loads each one when its switch is on, before the live tables.

| Switch | Init | Items | Journal line (stderr, once, at registration or at the first call) |
|---|---|---|---|
| `KYTY_BC5_LOAD_ZLIB` | `Libs::LibZlib::InitZlib_1` | none | `[bc5] exp 0405: zlib port on (items: Initialize Finalize Inflate WaitForDone GetResult)` / `... zlib port off` |
| `KYTY_BC5_LOAD_JPEG` | `Libs::LibJpeg::InitJpeg_1` | none | `[bc5] exp 0405: jpeg port on (items: Create Delete QueryMemorySize Encode-checks; Encode itself held)` / `... off` |
| `KYTY_BC5_LOAD_IME` | `Libs::LibIme::InitIme_1` | `panel`, `test` | `[bc5] exp 0405: ime port on (items: panel test; the 7 NIDs of the live Ime table not registered)` / `... off` |

**How the switches read.** Unset, empty or `0` is off. Any other value is on. `KYTY_BC5_LOAD_IME` may name items (for
example `panel`); a value that names none of them turns every item on. With a switch off, every function returns
today's answer: OK, nothing written. tld does not call an init whose switch is off, so off also means not loaded.

**Inputs.** The e6 input tree (`scratchpad\e6\e5tree`). These three units are base-tree files, not among e4/e5's 22.

## Table sizes

| Table | NIDs | Shared with a live table (same key) | Ported | Held |
|---|---|---|---|---|
| Zlib (`libSceZlib`) | 5 | 0 | 5 | 0 |
| JpegEnc (`libSceJpegEnc`) | 4 | 0 | 4 (Encode: checks only) | the encode itself in Encode, ~120 lines |
| Ime (`libSceIme`) | 48 | 7: removed from this table | 2 (panel, test) | 39 |

**How the shared NIDs were found.** By grepping all 3,000+ `LIB_FUNC` NIDs of the tree (`*.cpp`, `*.h`, `*.inc`) for
each of the 57.
- Only `libs/ime.cpp`'s `InitPlatform_1_Ime` shares any: 7 of the Ime NIDs.
- `SymbolDatabase::GenerateName` (loader/symbolDatabase.cpp:16-22) drops "libSce". So `libSceIme` v1 / v1.1 is the same
  key as the live `Ime` v1 / v1.1.
- **Zlib.** tld's "1 NID-only lookup moved" for zlib comes from its stand-in, which plants one Zlib NID under another
  library on purpose (tld0405-notes.md:107). It is not a real collision: tld's own table (:206) shows 0 overlap for Zlib,
  and no other unit of the tree registers any of the 5 Zlib NIDs. Nothing is dropped from Zlib.

## The 7 shared Ime NIDs (coordinator's request; tld0405-notes.md "Risks" 1)

**The 7.** TmVP8LzcFcY sceImeClose, ziPDcIjO0Vk GetPanelSize, RPydv-Jr1bc Open, WmYDzdC4EHI ParamInit, WLxUN2WMim8
SetCaret, ieCNrVrzKd4 SetText, TXYHFRuL8UY SetTextGeometry.

**Why they collide.** tld loads the switched tables first. `Find` (exact key) returns the last registration, so it gets
ime.cpp's function. `FindByNid` returns the first, so it gets this table's stub. FindByNid is the loader's NID-only
fallback:
- `RuntimeLinker::Resolve`, runtimeLinker.cpp:2091-2111;
- `ResolveLoadedSymbolByNid`, :2181-2207;
- libKernel.cpp:188-195's symbol lookup.

**Fixed at the source.** `InitIme_1` no longer registers these 7 NIDs, and their 7 stubs are removed. Each removed piece
leaves a one-line comment: output libIme.cpp:154, 227, 239, 246, 253, 255, 257 (stubs) and :363-386 (registrations).
- This holds with every switch value. Today nothing calls `InitIme_1`, so with the switch off nothing changes.
- With the switch off, the table still answers as today: OK, nothing written. tld does not load it then.

**Tested.** tbc0405 cases 13-16, the same both ways:
- this table registers 41 NIDs and none of the 7;
- the 7 resolve to ime.cpp's own functions (`&Libs::Ime::ImeOpen` and the other six), by `Find` and by `FindByNid`, in
  a database loaded in tld's order;
- the 39 held NIDs resolve to this table.

**Negative control.** The same test linked with the unedited `libIme.cpp`, switch off, FAILs cases 13 and 15: it
registers all 48, and FindByNid finds 0 of 7 of ime.cpp's functions.

## Ime state (coordinator's request: split state)

- **"panel" shares ime.cpp's state.** It reads the panel that ime.cpp's `ImeOpen` opened, through `libs/ime.h`'s public
  `GetHostSnapshot` (no header edit). With no panel open it answers as AnyPS5 does: NOT_OPENED.
- **"test" has no state.**
- **The 39 held stubs read and change no state.** They return OK and write nothing, whatever ime.cpp has open. Examples:
  `sceImeKeyboardUpdate` on a keyboard that ime.cpp's `ImeKeyboardOpen` opened, `sceImeDisableController`, and the
  candidate calls.
- **No "no IME open" answer to port.** AnyPS5 throws (`NotImplemented_nid_no_patch`) for all of them except FilterText
  (held on provenance), and two are not in AnyPS5. This is listed under the risks.

## Items

Common source for every ported item: AnyPS5 (github.com/boykopovar/AnyPS5) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
GPL-2.0-only. It is ported in adapted form: our own names and structure, with a cited comment block in each unit. The
three units are headed GPL-2.0-or-later (from shadPS4). With AnyPS5's GPL-2.0-only code in them, each combined file is
GPL-2.0-only in effect. Each block says so.

### Z1-Z5 libSceZlib: ported (KYTY_BC5_LOAD_ZLIB)

**Source.**
- `core/libs/prx/libSceZlib/Export.cpp:16-112`.
- Its note `docs/dev/debt/libSceZlib.md:5`. It names a native run for these facts: "Native validation confirms" the
  64-bit initialization length, 2 KiB output granularity up to 64 KiB, the null-argument errors and the initialization
  precedence.
- The rest follows shadPS4 (PS4) and SharpProspero, per the same note; it is unverified on a PS5. That covers request
  order, repeated GetResult, NOT_FOUND, TIMED_OUT, the microsecond timeout and the results dropped by Finalize.

**What changed (output libZlib.cpp).**
- :13-24: includes.
- :31-193: the block, with the state `Bc5ZlibState` and `Bc5ZlibInitialize` / `Finalize` / `Inflate` / `WaitForDone` /
  `GetResult`.
- :195-234: the five wrappers. Each takes its real arguments now and branches on `Bc5ZlibOn()`.
- :239: the switch is read at registration.

**Behaviour with the switch on.**
- Initialize: ALREADY_INITIALIZED 0x81120033 when already initialized. INVALID_ARGUMENT 0x81120016 when exactly one of
  buffer and length is null or zero.
- Finalize: NOT_INITIALIZED 0x81120032 before Initialize. It drops every result and wakes the waiters.
- Inflate: NOT_INITIALIZED first. Then INVALID_ARGUMENT for a null source, destination or request id, a zero source
  length, or a destination length of 0, over 64 KiB, or not a multiple of 2 KiB.
- The inflate itself runs at submission on the calling thread, over the zlib the tree already links (no new dependency).
  - The link: `ZLIB::ZLIBSTATIC` and `KYTY_HAS_ZLIB=1`, src/CMakeLists.txt:374-380. libPngEnc.cpp:22 includes
    `<zlib.h>` the same way.
  - The call: `inflateInit` (a zlib-wrapped stream), then `inflate(Z_FINISH)`.
  - The status: Z_STREAM_END gives 0. A full output with input left gives NO_SPACE 0x8112001C. Anything else gives FATAL
    0x811200FF.
  - The ids: from 1, and they keep counting across Finalize.
- WaitForDone: hands out the completed ids in submission order. A null timeout waits; a timeout is in microseconds and
  ends with TIMED_OUT 0x81120027.
- GetResult: INVALID_ARGUMENT for null outputs, NOT_FOUND 0x81120002 for an unknown id. It can be repeated.

**Adapted where AnyPS5 throws, each TODO(verify).**
- A non-null work memory is accepted and not used.
- A destination off a 2 KiB boundary is written as any other.
- A wait that Finalize ends returns NOT_INITIALIZED.

**Tests.** 39 cases with the switch on, 7 with it off (all calls return 0 and write nothing, as today).

### J1-J4 libSceJpegEnc: ported, except the encode itself (KYTY_BC5_LOAD_JPEG)

**Source.**
- AnyPS5 `core/libs/prx/libSceJpegEnc/Export.cpp:18-105` and `169-215`: the codes, the create and encode checks in
  AnyPS5's order, 0x800, the handle at the first 32-byte boundary pointing at itself.
- AnyPS5 `core/libs/SceTypes.hpp:2030-2049`: the two parameter layouts (0x8 and 0x30 bytes).
- The note `docs/dev/debt/libSceJpegEnc.md:5`. It names a native validator for the restart intervals 0, -1 and 1-65535.
- Cross-check: shadPS4 @ 60c42b9 (GPL-2.0-or-later), `src/core/libraries/jpeg/jpegenc.cpp:16-198` and `jpeg_error.h`.
  It has the same codes, sizes and checks, minus AnyPS5's zero-width and zero-height checks and its restart floor of -1.

**What changed (output libJpeg.cpp).**
- :15-17: includes.
- :24-229: the block.
- :231-266: the four wrappers. Each takes its real arguments and branches on `Bc5JpegOn()`.
- :269: the switch is read at registration.

**Held: the encode itself.** When Encode's checks pass it keeps today's answer: 0, with the JPEG buffer and the output
info not written. AnyPS5 returns the size and fills both. Two reasons:
- No JPEG encoder is compiled in this tree. `stb_image_write.h` is vendored (3rdparty/stb, on the include path,
  src/CMakeLists.txt:414) but instantiated nowhere; libPngEnc.cpp:6 notes the same.
- **Size of the hold.** About 60 lines to port AnyPS5's pixel packing and quality (Export.cpp:107-163, 190-209), plus
  about 60 to wrap `stbi_write_jpg_to_func`. stb cannot honour 4:2:2 or restart intervals, and it picks its own
  subsampling from the quality. MJPEG mode throws in AnyPS5. About 0.3 d.

**Tests.** 55 cases with the switch on: 33 encode-parameter cases, the handle checks, Create, Delete and Query, and that
a passing Encode writes nothing. 5 cases with it off.

### I1 sceImeGetPanelPositionAndForm (T6FYjZXG93o): ported (item `panel`)

**Source.** AnyPS5 `core/libs/prx/libSceIme/Export.cpp:499-512` (commit e21d8bd12) and its note
`docs/dev/debt/libSceIme.md:21`. The note: the output is the PositionAndForm that the dialog call fills; the console's
values for a panel moved by its own adjustment are unknown.

**Behaviour.**
- With no panel open: NOT_OPENED 0x80bc0002, checked before a null form.
- A null form with a panel open: INVALID_ADDRESS 0x80bc0031.
- Otherwise the form is cleared, then gets the type, the position and the alignments that ime.cpp's `ImeOpen` was given,
  and the panel size: 793x408, or 370x402 for Number, doubled over 2K.
- It reads ime.cpp's state through `GetHostSnapshot`. The form is `libs/imeDialog.h:104`'s `PositionAndForm` (0x1c), so
  no new layout is added.

**What changed (output libIme.cpp).** :106-126 (the function), :219-225 (the wrapper).

**Tests.** 7 cases: no panel, a null form, a Default panel at (100.5, 200.25) with alignments 1 and 2, a Number panel
over 2K at (3000, 2000) giving 740x804, and after Close. Off: 0, nothing written.

### I2 sceImeForTestFunction (wVkehxutK-U): ported, decision 1 (item `test`)

**Value.** 0x80bc00ff, the IME's internal error code. shadPS4's `ime_error.h:51` has the same code.

**Source.** AnyPS5 Export.cpp:760-762, commit db2575839: "return what the firmware returns from 29 more calls it does not
implement". Its note libSceIme.md:25 says it "returns a constant error without consuming arguments in the supplied
module".

**Provenance call for the maintainer.** The note names a reading of a firmware module, not a run, and no disassembly
addresses. It is taken under decision 1, which covers prosper-style module readings. Turn the `test` item off to drop
it.

**What changed (output libIme.cpp).** :211-217.

**Tests.** 1 case: the value twice. Off: 0.

### Held Ime (39 NIDs; today's stubs: OK, nothing written)

- **sceImeFilterText (evjOsE18yuI): held on provenance.** AnyPS5's note libSceIme.md:22 says the behaviour "follows the
  disassembly of `libSceIme.sprx` from firmware 13.60". It also names helper addresses (0x4850, 0x48f0).
- **36 calls AnyPS5 does not implement either.** They throw there (`NotImplemented_nid_no_patch`), so there is no
  behaviour to port:
  - FinalizeImeModule, InitializeImeModule;
  - CheckFilterText, CheckRemoteEventParam, CheckUpdateTextInfo;
  - ConfigGet, ConfigSet;
  - ConfirmCandidate, SetCandidateIndex;
  - Dic* (6);
  - DisableController;
  - KeyboardOpenInternal, KeyboardUpdate;
  - Vsh* (18).
- **sceImeOpenInternal (16UI54cWRQk) and sceImeVshDisableController (rM-1hkuOhh0).** These names are not in AnyPS5's
  libSceIme.
- **Test.** 1 case: all 39 return 0, both ways.

### Exp 0405 r1-verdicts rows for these libraries

- **libSceZlib, libSceJpegEnc.** No rows.
- **libSceIme: 17 rows.**
  - 16 are `internal` or `test-doc-build`. These are AnyPS5's host features (preedit and paste host input, the PSN
    notice, `ANYPS5_PSN_DIALOGS`) and tests. They are not console behaviour of this table, and their functions are live
    in ime.cpp, outside this group. Not ported.
  - c71dac4bc ("declare 2 callable exports", NbbzN9GRg+c and aChMGUoc7QI) is held. Neither NID is in this table, and
    AnyPS5 only throws for them (no behaviour). Its note: the parameter lists, return types and behaviour are unverified,
    from an export inventory "cross-checked against the same module in PS5 firmware 13.60".
- **Used and not in the TSVs.** e21d8bd12 (I1) and db2575839 (I2), above.

## Checks on the laptop

**The script.**
- It applies to the e6 input tree and prints the three output md5s (below). It refuses its own output ("the unit has
  the edit already").
- In each unit it asserts:
  - the pinned md5;
  - every anchor once;
  - balanced braces, parentheses and brackets, per edit and per unit;
  - ASCII inserts;
  - LF kept, and the BOM kept;
  - the helper-use counts;
  - that undoing its edits gives the input back byte for byte.
- **Changes besides the inserted blocks** (from `diff`):
  - 10 wrapper signature lines, which now take the real arguments;
  - the 7 Ime stubs (4 lines each) and their 7 `LIB_FUNC` lines, each replaced by a comment line;
  - one `LIB_DEFINE` line per unit, which gains the switch read after it.

**Syntax.** Visual Studio's clang++ 22 (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with the
stand-in `cmake_config.h` and POSIX stubs (`scratchpad\lib0405chk\stub`), fmt from Inori_GPCS4, and the vendored zlib
headers. Clean for the three outputs, the three inputs and tbc0405.cpp.

**Stand-in run** (scratchpad `e6\tbc\run`).
- **What it links.** The real output units, the real `libs/ime.cpp` and `loader/symbolDatabase.cpp`, the vendored zlib
  (`refs\Coder787-source_KytyPlus\3rdparty\zlib`, the tree's own) and fmt. A stand-in `standin.cpp` supplies the log,
  timer and thread symbols that `PRINT_NAME` references (never reached) and `Common::File` (DbgDump; never reached).
- **Runs.** Each was a fresh directory, and each left nothing behind but its own output.
  - All `=1` with `on`: **108 of 108**, exit 0.
  - All `=0` with `off`: **26 of 26**.
  - All unset: **26 of 26**, off.
  - `ZLIB=` (empty), `JPEG=yes`, `IME=panel`: mixed, 76 of 76.
  - Earlier build: `IME=test` with the others unset, mixed 26 of 26. A wrong argument exits 2.
- **Negative control.** The same test with the three unedited input units:
  - switches on: 20 of 108 passed, 88 FAILs, exit 1;
  - switches off: 24 of 26, with cases 13 and 15 failing (the 7 shared NIDs, as described above).

**Not checked.** The box's Linux compile (gcc or clang) and the real link and run.

## Risks

- **A wait with nothing pending.** Zlib `WaitForDone` without a timeout blocks the guest thread until a completion or
  Finalize, as in AnyPS5. Requests finish at submission, so a title only blocks if it waits without having submitted.
- **Results are kept until Finalize** (about 40 B per request). A title that never finalizes grows this map.
- **The inflate holds the service lock** while it decodes, at most 64 KiB of output per call.
- **The Jpeg handle check reads 8 bytes at the handle address.** A garbage 32-byte-aligned pointer faults, as in AnyPS5
  and shadPS4.
- **A passing Jpeg Encode returns 0 and writes nothing** (held), the same as today.
- **The held Ime stubs answer OK beside an open IME** (split state, above). Examples: KeyboardUpdate delivers no events
  for a keyboard that ime.cpp opened, and the Vsh and Dic calls report success.
- **ForTestFunction's value rests on a module reading** (decision 1). It sits behind its own item.
- **libIme.cpp now includes `libs/ime.h` and `libs/imeDialog.h`.** Both are public headers, unchanged.
- **TODO(verify):** the three Zlib adaptations listed under Z1-Z5.

## Files

| File | md5 |
|---|---|
| mktbc0405.py | 635a920eabd9835dae364742378177cb |
| tbc0405.cpp | f829246ab0b3e0b9b91f8f40ecbd492b |
| tbc0405-notes.md | this file |
| in `src/libs/libZlib.cpp` (base tree, LF, BOM) | f5d3aafebca0d202082365ee609f15b6 |
| in `src/libs/libJpeg.cpp` (base tree, LF, BOM) | a85a83b8d541f5e10c14d739ff56457f |
| in `src/libs/libIme.cpp` (base tree, LF, BOM) | a572240f789088264b6e13850978b739 |
| out `src/libs/libZlib.cpp` | c7e165b9b288d71f874d5d6c6dbd363c |
| out `src/libs/libJpeg.cpp` | c5fe947cc30001c49bd2b1f8af7a0e2c |
| out `src/libs/libIme.cpp` | 49fa46f1d8005245e7f0b266d8b29659 |
| read only: `src/libs/ime.cpp`, `ime.h`, `imeDialog.h` (base tree) | 96579f36120bccadf4bdd83c837b932e, 8a99876bffd164135f52577184f1ee11, 812b7ea1bdf2b37f36c190eb4338bf2c |
