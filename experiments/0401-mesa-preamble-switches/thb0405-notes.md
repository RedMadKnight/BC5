# thb0405: batch 1's held stubs are not registered when their table's switch is on (series e7)

Agent `thb`, 2026-11-04. The top session's decision of 2026-11-04: a held stub is a function with no behaviour, ours or
upstream's. Either AnyPS5 does not implement it (a throwing placeholder, or no export at all), or batch 1 held it because
its only source is not usable. Such a stub is not registered while its table's switch is on. A title's import of it then
stays unresolved, as it was before the table was loaded. With the switch off, each init registers every `LIB_FUNC` as
today, in today's order. Batch 2 already follows this rule (`tbd0405-notes.md`, "held, not registered"; tbp's NpParty
and NpPartner in the same libNp.cpp).

This applies the rule to batch 1's six tables, **in series e7 only**. Series e6 stays as built and tested:
`mktbc0405.py`, `mktbn0405.py`, `tbc0405.cpp`, `tbn0405.cpp` and their notes are not edited.

Files: `mkthb0405.py` (the edit), `tbc0405e7.cpp` and `tbn0405e7.cpp` (e7's copies of the two CPU tests), this note.

## Units

| Unit | Input (e7's chain at this point) | Output | Edited |
|---|---|---|---|
| `src/libs/libIme.cpp` | `49fa46f1d8005245e7f0b266d8b29659` (tbc's output, the e7 input tree) | `b82113cc80bce4d544c75cec3047e145` | `InitIme_1` only |
| `src/libs/libNp.cpp` | `e60a2844e6b607f7bafc019db8e872c2` (e7's chain after tbt and tbp) | `8222b0bc10f137fe99349becb4609034` | `InitNpManager_1` and `InitNpTrophy_1` only |
| `src/libs/libZlib.cpp` | `c7e165b9b288d71f874d5d6c6dbd363c` | not edited | every function it registers has behaviour when on |
| `src/libs/libJpeg.cpp` | `c5fe947cc30001c49bd2b1f8af7a0e2c` | not edited | the same; Encode's held encode sits inside a ported function |

`mkthb0405.py` pins the two edited inputs in one dict (`PINNED`). Both are LF with a UTF-8 BOM, and both stay so.

## What changed

Each held `LIB_FUNC` line is wrapped. This is the form tbp uses in the same file:

```
	if (!Bc5NptOn()) { // BC5 experiment 0405 (thb): held, registered only when KYTY_BC5_LOAD_NPTROPHY is off
		LIB_FUNC("cqGkYAN-gRw", NpTrophy::sceNpTrophyCaptureScreenshot);
	}
```

- **Ime.** The condition is `Bc5ImeItems() == 0`: the switch is off, so no item is on.
- **The `LIB_FUNC` text** is unchanged in every wrapped line.
- **A comment of four lines** follows each edited init's switch read. It says what is left out when the switch is on, and
  why.
- **Nothing else changes.** The block comments and the journal lines (`[bc5] exp 0405: <table> port on|off ...`) stay as
  batch 1 wrote them. Exp 0327's line names each held import that a title calls.

Where the changes are in the outputs:
- `libIme.cpp:356-488` is `InitIme_1`, with the comment at :358-361.
- `libNp.cpp:1100-1143` is `InitNpManager_1`, with the comment at :1102-1105.
- `libNp.cpp:2602-2823` is `InitNpTrophy_1`, with the comment at :2604-2607.

**What a title sees with the switch on.** The NID has no record in any table. `ResolveLoadedSymbolByNid`, the loader's
NID-only fallback, finds none either. So the import is bound to the runtime linker's unresolved-import thunk (e7 input
tree `src/loader/runtimeLinker.cpp`, md5 aba94c24ad35a1c944ad3bd5843b13ef):
- :300-317: the link-time line `[bc5] stubbed import #...`;
- :320-382 (`ResolveImportStubWithId`): the first call is journaled as `[bc5] stubbed import called: ...`, and the thunk
  answers 0.

This is the answer every one of these imports got before e6 loaded the tables.

## Per table: held and not registered when on

Reasons are quoted from batch 1's notes (`tbc0405-notes.md` "Held Ime", `tbn0405-notes.md` NpManager/NpTrophy "HELD").

| Table | NIDs registered off (today) | held, not registered when on | registered when on |
|---|---|---|---|
| Zlib | 5 | 0 | 5 |
| JpegEnc | 4 | 0 | 4 |
| Ime | 41 | **39** | 2 (`T6FYjZXG93o` GetPanelPositionAndForm, `wVkehxutK-U` ForTestFunction) |
| NpCommon | 28 | 0 | 28 |
| NpManager | 27 | **4** | 21 (the 2 NIDs it shares with libNet.cpp were already left out when on, by tbn) |
| NpTrophy | 87 | **64** | 23 |
| **total** | 192 | **107** | 83 |

### Ime: 39 held (KYTY_BC5_LOAD_IME, any item on)

- **`evjOsE18yuI` sceImeFilterText: provenance.** AnyPS5's note libSceIme.md:22 says the behaviour "follows the
  disassembly of `libSceIme.sprx` from firmware 13.60", and it names helper addresses.
- **36 that AnyPS5 does not implement either** (`NotImplemented_nid_no_patch`):
  - `mN+ZoSN-8hQ` FinalizeImeModule, `uTW+63goeJs` InitializeImeModule;
  - `Lf3DeGWC6xg` CheckFilterText, `zHuMUGb-AQI` CheckRemoteEventParam, `OTb0Mg+1i1k` CheckUpdateTextInfo;
  - `Ho5NVQzpKHo` ConfigGet, `P5dPeiLwm-M` ConfigSet;
  - `tKLmVIUkpyM` ConfirmCandidate, `TQaogSaqkEk` SetCandidateIndex;
  - the 6 Dic calls: `NYDsL9a0oEo`, `l01GKoyiQrY`, `E2OcGgi-FPY`, `JAiMBkOTYKI`, `JoPdCUXOzMU`, `FuEl46uHDyo`;
  - `E+f1n8e8DAw` DisableController;
  - `oYkJlMK51SA` KeyboardOpenInternal, `3Hx2Uw9xnv8` KeyboardUpdate;
  - 18 of the 19 Vsh calls, all but VshDisableController: `oOwl47ouxoM`, `gtoTsGM9vEY`, `wTKF4mUlSew`, `42xMaQ+GLeQ`,
    `ZmmV6iukhyo`, `EQBusz6Uhp8`, `LBicRa-hj3A`, `-IAOwd2nO7g`, `qDagOjvJdNk`, `tNOlmxee-Nk`, `rASXozKkQ9g`,
    `idvMaIu5H+k`, `ga5GOgThbjo`, `RuSca8rS6yA`, `J7COZrgSFRA`, `WqAayyok5p0`, `O7Fdd+Oc-qQ`, `fwcPR7+7Rks`.
- **2 that are not in AnyPS5's libSceIme:** `16UI54cWRQk` OpenInternal, `rM-1hkuOhh0` VshDisableController.
- **Items.** `KYTY_BC5_LOAD_IME=panel` (or `test`) turns the table on, so all 39 are left out. The other item's function
  stays registered and answers as today, because it is a ported function, not a held stub. For example, with `panel`
  only, ForTestFunction answers 0.

### NpManager: 4 held (KYTY_BC5_LOAD_NPMANAGER)

- These four are AnyPS5's throwing placeholders (`PendingExports.cpp:733, 753, 757`, `AdditionalExports.cpp:804`):
  - `KswxLxk4c1Y` sceNpRegisterGamePresenceCallbackA;
  - `aJZyCcHxzu4` sceNpUnregisterGamePresenceCallbackA;
  - `0c7HbXRKUt4` sceNpRegisterStateCallbackForToolkit;
  - `YIvqqvJyjEc` sceNpUnregisterStateCallbackForToolkit.
- **Left as they are:**
  - `xViqJdDgKl0` sceNpUnregisterPlusEventCallback already answers as AnyPS5 does (0, Export.cpp:1056). It is not held,
    and it stays registered both ways.
  - `mjjTXh+NHWY` and `cRILAEvn+9M` are shared with libNet.cpp's live table. They are already registered only when off
    (tbn, batch 1's risk 1), and that is kept.

### NpTrophy: 64 held (KYTY_BC5_LOAD_NPTROPHY)

- **`iqYfxC12sak` ConfigHasGroupFeature: provenance.** Its only source is the disassembly, with no run: the fifth
  function of AnyPS5 debt `libSceNpTrophy.md:28`.
- **62 throwing placeholders with no prototype** (debt :13-19, :34-38):
  - `cqGkYAN-gRw` CaptureScreenshot;
  - ConfigGet* (8): `lhE4XS9OJXs`, `qJ3IvrOoXg0`, `zDjF2G+6tI0`, `7Kh86vJqtxw`, `ndLeNWExeZE`, `6EOfS5SDgoo`,
    `MW5ygoZqEBs`, `3tWKpNKn5+I`;
  - Int* (11): `u9plkqa2e0k`, `pE5yhroy9m0`, `edPIOFpEAvU`, `DSh3EXpqAQ4`, `sng98qULzPA`, `t3CQzag7-zs`, `jF-mCgGuvbQ`,
    `PeAyBjC5kp8`, `PEo09Dkqv0o`, `kF9zjnlAzIA`, `UXiyfabxFNQ`;
  - `d9jpdPz5f-8` ShowTrophyList;
  - System* (37): `JzJdh-JLtu0`, `z8RCP536GOM`, `Rd2FBOQE094`, `Q182x0rT75I`, `lGnm5Kg-zpA`, `20wAMbXP-u0`,
    `sKGFFY59ksY`, `JMSapEtDH9Q`, `dk27olS4CEE`, `cBzXEdzVzvs`, `NobVwD8qcQY`, `yXJlgXljItk`, `U0TOSinfuvw`,
    `-LC9hudmD+Y`, `q6eAMucXIEM`, `OcllHFFcQkI`, `tQ3tXfVZreU`, `g0dxBNTspC0`, `sJSDnJRJHhI`, `X47s4AamPGg`,
    `7WPj4KCF3D8`, `pzL+aAk0tQA`, `Ro4sI9xgYl4`, `7+OR1TU5QOA`, `aXhvf2OmbiE`, `Rkt0bVyaa4Y`, `nXr5Rho8Bqk`,
    `SsGLKTfWfm0`, `XqLLsvl48kA`, `-qjm2fFE64M`, `50BvYYzPTsY`, `yDJ-r-8f4S4`, `mWtsnHY8JZg`, `tAxnXpzDgFw`,
    `tV18n8OcheI`, `kV4DP0OTMNo`, `lZSZoN8BstI`;
  - the four `Func_*`: `FJZW2oHUHFk`, `n4AHGHb-pfY`, `+O9vU1CpGZA`, `+not13BEdVI`.
- **Absent from AnyPS5:** `eV1rtLr+eys` SystemGetTrophyTitleIds.
- **Two answers change when on.** Today's stubs of `50BvYYzPTsY` SystemNetSyncTitle and `yDJ-r-8f4S4`
  SystemNetSyncTitles answer 0x80550005 (this file's `NP_NOT_SIGNED_IN`). On, the thunk answers 0 for them, as it did
  before e6. The other 62 answered 0 and still get 0. Off, all 64 answer as today.

## Split state and overlap (rechecked)

- **No new registrations.** The edit only removes registrations, and only when on. No NID of these tables gains a
  registration, so no NID collides with a live table that did not before.
- **The shared NIDs stay out.** The 7 Ime NIDs (ime.cpp) and the 2 NpManager NIDs (libNet.cpp) that live tables share
  were already not registered when on (tbc, tbn).
- **Ime.** The 39 held stubs read and changed no state (tbc). With the switch on, a title's call to one now reaches the
  thunk: 0, journaled. That was the same answer before, without the journal line. ime.cpp's live state is not touched.
- **NpManager.** Both GamePresenceA calls and both Toolkit calls are held, so each pair is left out whole. No pair is
  split between this table and the live one. sceNpRegisterPlusEventCallback (live) and its Unregister partner
  (`xViqJdDgKl0`, here) keep no state, as tbn found.
- **NpTrophy and NpCommon** have no live NIDs in the same library.

## The tests: e7's copies

Both copies keep e6's printed name and end line, so e7's gate rows can build them under the names `tbc0405` and
`tbn0405`. They were changed only where the rule requires:
- **on:** a held NID is absent, by the exact key and by `FindByNid`, and it is not called;
- **off:** it is present and answers as today.

Every other case is e6's, with the same names, conditions and order.

**tbc0405e7.cpp** (from tbc0405.cpp, f829246ab0b3e0b9b91f8f40ecbd492b). The Ime cases:
- **Registration.** On: 2 NIDs (panel, test), none of the 39 held, none of the 7 shared. Off: e6's case (41).
- **The 39 held NIDs, by key.** On: absent by `Find`, both in the table alone and in tld's order. Off: e6's case ("resolve
  to this table").
- **The 39 held stubs.** On: absent by `FindByNid`, in both databases, and not called. Off: e6's case (0 each).
- **On** means any item of `KYTY_BC5_LOAD_IME`.
- **Counts:** on 108 (as e6), off 26 (as e6). Mixed runs: 76 with `ZLIB=` (empty), `JPEG=yes`, `IME=panel`; 26 with
  `IME=test` alone; 108 with ZLIB and JPEG on and IME unset.

**tbn0405e7.cpp** (from tbn0405.cpp, 3eeaf1fe800442bcf66b0fa0a0a34338, which has tbt's evaluation-order fix):
- **Lookups.** The four held functions e6 took at the top of its cases are no longer taken there: RegisterGamePresenceCallbackA,
  RegisterStateCallbackForToolkit, ConfigHasGroupFeature and ShowTrophyList.
- **NpManager on.** e6's two "held, today's 0" calls become two cases:
  - the 4 held NIDs are absent by `Find`;
  - they are absent by `FindByNid`.

  Each case checks the test's database and a second one loaded in libs.cpp's order (this table, then
  `InitNet_1_NpManager`).
- **NpTrophy on.** e6's ConfigHasGroupFeature and ShowTrophyList calls become two cases: the 64 are absent by `Find`, and
  absent by `FindByNid`.
- **Off, one new case per table.** The 4 or 64 are registered as today (`Find` and `FindByNid` give the same record), and
  each answers today's value: 0, or 0x80550005 for the two SystemNetSyncTitle calls.
- **Counts:** on 165 (npcommon 57, npmanager 51, nptrophy 57; as e6). Off 36 (12, 16, 8; e6's 34 plus the two held
  cases). Mixed switches are refused (exit 2), as in e6.

## Verified on the laptop

**The script** (scratch `e7\thb`, input root `in\` = the two pinned inputs):
- It prints `src/libs/libIme.cpp b82113cc80bce4d544c75cec3047e145` and `src/libs/libNp.cpp
  8222b0bc10f137fe99349becb4609034`. A second run gives the same bytes.
- It refuses its own output ("the unit has the edit already"). It refuses a changed libIme.cpp or libNp.cpp ("not the
  pinned input") and writes nothing.
- Built-in checks:
  - every anchor occurs once and lies inside its own init;
  - each held function is a stub that takes no arguments, has a body of `PRINT_NAME(); return OK|NP_NOT_SIGNED_IN;`,
    and has no switch use;
  - each held list is exactly its init's stubs with no behaviour, less the kept ones;
  - each init's `LIB_FUNC` order is unchanged;
  - libNp.cpp's six other inits, NpCommon's among them, are byte-identical;
  - braces, parentheses and brackets balance per edit and per unit;
  - the inserted text is ASCII; LF and the BOM are kept;
  - undoing the edits gives the input back byte for byte.
- **Independent check** (scratch `undo_check.py`): unwrapping the 39 + 68 blocks by pattern and dropping the 3 comments
  gives both inputs back. Balance is (0, 0, 0) in and out. `diff` shows changes only inside the three inits.

**Syntax.** VS clang++ 22 (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with the stand-in
`cmake_config.h` and POSIX headers (`scratchpad\lib0405chk\stub`), tbn's `sched_standin.h`, fmt from Inori_GPCS4,
magic_enum and the vendored zlib. Clean for both outputs, both inputs, `tbc0405e7.cpp` and `tbn0405e7.cpp` (the latter
also needs `-Wno-deprecated-declarations`, as e6's did, for Windows' POSIX names).

**Stand-in runs.** Windows clang++ 22, lld; each run in a fresh directory, and each left nothing behind.
- **tbc0405e7** (scratch `e7\thb\tbc`). It links the real test, the output libIme.cpp, the e7 libZlib.cpp and
  libJpeg.cpp, the real `libs/ime.cpp` and `loader/symbolDatabase.cpp`, the vendored zlib and fmt, and tbc's own
  stand-in (log, timer, thread id, File).

  | Run | Result |
  |---|---|
  | all `=1` | **on 108 of 108** |
  | all `=0` | off 26 of 26 |
  | unset, with or without the argument | off 26 of 26 |
  | `ZLIB=`, `JPEG=yes`, `IME=panel` | mixed 76 of 76 |
  | `IME=test` | mixed 26 of 26 |
  | ZLIB and JPEG on | mixed 108 of 108 |
  | a wrong argument | exit 2 |

- **tbn0405e7** (scratch `e7\thb\tbn`, the first laptop run of tbn0405's code itself). It links the real test, the
  output libNp.cpp, the real `symbolDatabase.cpp` and fmt, plus two stand-ins:
  - `standin.cpp`: tbn's pthread and clock stand-ins; a small mount table; network.cpp's request model, copied from the
    e7 input tree (np_create_request ... NpPollAsync); no-op subsystems, Config::Load and RuntimeLinker;
  - `livenpm.cpp`: libNet.cpp's live NpManager table (its 29 `LIB_FUNC` lines generated from the e7 chain's libNet.cpp,
    with dummy functions), so the keys and debug names are real.

  | Run | Result |
  |---|---|
  | all `=1` | **on 165 of 165** |
  | all `=0` | off 36 of 36 |
  | unset, with or without the argument | off 36 of 36 |
  | mixed (with or without the argument) | refused, exit 2, as in e6 |
  | a wrong argument | exit 2 |

  **The stand-in itself is checked:** e6's unchanged `tbn0405.cpp` against the unedited e7 libNp.cpp gives on 165 of
  165 and off 34 of 34.
- **tld0405** (e6's unchanged `tld0405.cpp`, 02ae1902c6ae557e9c9be06e4fb2fc95, with e7's units). Scratch `e7\thb\tld`,
  which is tl3's stand-in copied unchanged. It links:
  - e7's libs.cpp, tl3's final output 0728ab027534903ab50cbda93945b9dd;
  - this script's libIme.cpp and libNp.cpp;
  - the e7 libZlib.cpp and libJpeg.cpp;
  - the other switched tables' units from the e7 input tree.

  Results:

  | Run | Result |
  |---|---|
  | the six `=1` | **on 9 of 9** |
  | the six `=0` | off 9 of 9 |
  | unset | off 9 of 9 |
  | `IME=1`, `NPTROPHY=yes`, `ZLIB=` | mixed 9 of 9 |
  | a wrong argument | exit 2 |

  - **The "new" counts with the switches on:** zlib 5, jpeg 4, ime 2, npcommon 28, npmanager 21, nptrophy 23. They were
    41, 25 and 87 for the last three before this edit.
  - **Zlib's one NID-only lookup** is the planted NID of tld's stand-in (tld0405-notes.md:107).
  - **With the e7 input tree's libs.cpp** (903fa699db7c20b2b3f288ab572bce8d, tld's own output) in place of tl3's, all
    four runs give 9 of 9 again.

**Negative controls.**
- **The copies against the unedited e7 inputs.** The tests are the same; only libIme.cpp or libNp.cpp is the input.
  - tbc0405e7, on: `on 105 of 108 passed; FAIL`, exit 1. It FAILs case 95 (2 + 39 of the 39 held), case 98 (0 of 39
    absent) and case 108 (0 of 39 absent). Mixed `IME=panel` and `IME=test` FAIL the same three cases. Off passes 26 of
    26.
  - tbn0405e7, on: `on 161 of 165 passed; FAIL`, exit 1. It FAILs cases 107, 108 (0 of 4 absent), 164 and 165 (0 of 64
    absent). Off passes 36 of 36.
- **e6's tests against this script's outputs.**
  - Off, both pass e6's cases: tbc0405 26 of 26, tbn0405 34 of 34. So the off path is today's.
  - On, both stop at setup, with exit 2: `mN+ZoSN-8hQ (libSceIme) is not registered` and `KswxLxk4c1Y is not registered`.
    This is why e7's gate rows must build the e7 copies under the e6 names.

**Not checked:**
- the box's Linux compile and the real link;
- the real runtime linker binding a held import to its thunk (no title, and the thunk needs guest memory);
- the real live tables beyond the stand-ins (ime.cpp is real in the tbc run; libNet.cpp's NpManager is a key-for-key
  stand-in; network.cpp's request model is a copy);
- tld0405 with the batch-2 units of other agents' outputs, rather than the e7 input tree's (their switches stay unset
  in tld0405, so these tables are not loaded).

## Risks

1. **More `[bc5] stubbed import called` lines with a switch on.** A title that calls held Ime, NpManager or NpTrophy
   functions journals each one once. This is intended: it names what is still missing.
2. **Two NpTrophy answers move from 0x80550005 to 0 when on** (SystemNetSyncTitle, SystemNetSyncTitles). This is the
   pre-e6 answer. Both are system calls that a game is unlikely to import.
3. **The e6 tests do not fit the e7 units with the switches on** (exit 2 at setup, above). The gate rows must take
   `tbc0405e7.cpp` and `tbn0405e7.cpp` (named tbc0405 and tbn0405) whenever this script's outputs are in the build.
4. **tld0405's counts move, without a FAIL.** With the switches on, its per-table lines report fewer "new" keys: ime 2,
   npmanager 21, nptrophy 23.
5. **The journal lines of batch 1 are unchanged.** For example, ime's still says "the 7 NIDs of the live Ime table not
   registered" and does not count the 39. The edit was limited to the inits, and the comment in each init says it.

## Files

| File | md5 |
|---|---|
| `mkthb0405.py` | 403cb6e67d4bf1e1990849cb1441bdc3 |
| `tbc0405e7.cpp` | 5f9b0261e6bc9154cd112901a31e3c3f |
| `tbn0405e7.cpp` | 52ddceb057a357931afd4af0d5e15c93 |
| `thb0405-notes.md` | this file |
| in `src/libs/libIme.cpp` (tbc's output; e7 input tree) | 49fa46f1d8005245e7f0b266d8b29659 |
| in `src/libs/libNp.cpp` (e7 chain after tbt, tbp) | e60a2844e6b607f7bafc019db8e872c2 |
| out `src/libs/libIme.cpp` | b82113cc80bce4d544c75cec3047e145 |
| out `src/libs/libNp.cpp` | 8222b0bc10f137fe99349becb4609034 |
| not edited: `src/libs/libZlib.cpp`, `src/libs/libJpeg.cpp` | c7e165b9b288d71f874d5d6c6dbd363c, c5fe947cc30001c49bd2b1f8af7a0e2c |
| read only: `src/loader/runtimeLinker.cpp` (e7 input tree) | aba94c24ad35a1c944ad3bd5843b13ef |
