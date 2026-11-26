# lib0405: exp 0405 R1 #1-#4 (+ R2 KS05, SK07, KL03) in Json2, Ult, UserService, SystemService (series e5)

Port agent `lib`, 2026-11-04. Files: `mklib0405.py` (the edit), `lib0405.cpp` (the CPU test), this note. Inputs: the e5
input tree (`scratchpad/e5/e4tree`, KytyPlus f266548 + patch 0001 + e4's private units; none of the four units here was
changed by e4). Specs: exp 0405 `raw/r1-anyps5.md` §1 rows 1-4 and §2 items 1-4; `raw/r2-kyty-sharpemu.md` §5 items 21
(SK07), 22 (KS05), 30 (KL03).

## Switches and journal lines

All default off and read once (a function-local static); the line is printed when `Libs::InitAll` registers the library,
so every run shows it, on or off. Unset, empty or `0` is off; any other value turns all items on unless it names items
(comma list), as e4's `KYTY_BC5_AUDIO_FIXES`.

| Switch | Items | stderr line |
|---|---|---|
| `KYTY_BC5_JSON2_FIXES` | `value`, `string`, `array`, `object` | `[bc5] exp 0405: json2 on (items: value string array object)` / `... json2 off` |
| `KYTY_BC5_ULT_FIXES` | `join`, `queue` | `[bc5] exp 0405: ult on (items: join queue)` / `... ult off` |
| `KYTY_BC5_USERSERVICE_VALUES` | `age`, `login`, `name`, `zoom` | `[bc5] exp 0405: userservice on (items: age login name zoom)` / `... off` |
| `KYTY_BC5_SYSTEMSERVICE_VALUES` | `int`, `table`, `string` | `[bc5] exp 0405: systemservice on (items: int table string)` / `... off` |
| `KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000` | (one) | `[bc5] exp 0405: systemservice-params-7-1000 on (items: 7 1000)` / `... off` |

Catchers (only when on): `[bc5] exp 0405: ult queue 0x... holds N items, over its data pool's num_data M (kept; dropped
when off)` (first 8 pushes); `[bc5] exp 0405: system param <id> (int|string) -> 0x80A10003` (once per refused parameter).

## Item 1: R1 #1 + R2 KS05, Json2 assignment that copies its source first: PORTED

- Source: AnyPS5 4f41f4c37 (GPL-2.0-only) `core/libs/prx/libSceJson2/Export.cpp:1299-1320` (OwnsPayload, AssignPayload),
  `1370-1383` (AssignNode); commits fa8239009, 3e03f8df7 (descendant assignment), f8e4d8acb (collection self-setting),
  e237f1bfe (String setter aliases). KytyPS5 dfec14a (GPL-2.0) `src/libs/libJson2.cpp:626-636` (SetObject), `987-996`
  (Object::operator=), R2 KS05. Folded: R1 #1 and KS05 are the same bug; both sources are cited in the block.
- The bug, ours (`e4tree src/libs/libJson2.cpp`): `JsonValueCopy` (:242), `SetString` (:650), `ObjectAssign` (:911),
  `SetArrayCopy` (:1012), `SetObject` (:1033), `SetCString` (:1050) clear the destination, then read the source. A source
  inside the destination is freed first: `v = v["a"]`, `v.set(v.getString())`, `v.set(v.getString().c_str())`,
  `v.set(v.getArray())`, `v.set(v["a"].getObject())`, `obj = v["a"].getObject()` read freed memory; `obj = obj` empties
  `obj`; `v["a"] = v` gives `{"a":{"a":{},...}}`.
- Change (output `src/libs/libJson2.cpp`): helper block :243-443; `JsonValueCopy` :449 (`value`); `SetString` :859 and
  `SetCString` :1272 (`string`); `ObjectAssign` :1124 and `SetObject` :1252 (`object`); `SetArrayCopy` :1226 (`array`);
  `#include <cstdio>` :7; registration line :1525.
  - The rule: when the destination owns a payload (string, array, object), build the copy in a fresh value, clear the
    destination, move the copy in and re-point the moved members' `parent` at it, as today's copy does. A destination that
    owns nothing takes today's code (nothing a source could be in is freed). The copies inside go into fresh values, which
    take today's path, so there is no recursion.
  - Value set to its own String/Array/Object, and Object assigned to itself, stay as they are (no rebuild). That is our
    choice, matching today's `dst == src` rule for Value. AnyPS5's f8e4d8acb / e237f1bfe found from SDK reference-module
    runs that the console rebuilds a self-set collection and keeps a self-aliased String's storage. Those facts are
    reference-sourced and HELD (brief rule 1/SDK); the contents are the same either way.
  - Not taken: AnyPS5's allocator and reference-module details, e237f1bfe's "missing headers" part.
- Test: 10 alias cases (on: the fixed text). Also, both ways: `v["a"] = v` (on: a copy of v as it was; off: today's
  `{"a":{"a":{},"c":2},"c":2}`), `obj = obj` (on: unchanged; off: `{}`), own String keeps its storage (on), seven
  independent-source calls, `v = v` / `v.set(v)`, parse into an owning value, parent pointers after `v = w` and (on)
  `v = v["a"]`.
  - With an item off, its alias cases run once each in a fork()ed child, printed as info lines and not counted.
  - Freed memory during the Json2 cases is poisoned with 0xA5 and quarantined by the test's own `operator delete`, which
    acts as a canary in place of ASan.
- Risks: low. A guest that kept a pointer into the old payload (an iterator, a `getString()` reference) sees it freed after
  the call, as today. The extra copy happens only on assignment into a value that owns a payload. The `parent`/`rootparam`
  of the destination are still cleared by `JsonValueClear` as today (not changed here; a separate question).

## Item 2: R1 #2, Ult publication and join ownership: PORTED (item `join`)

- Source: AnyPS5 4f41f4c37 `core/libs/prx/libSceUlt/Export.cpp:125-185` (gCurrentUlthread, ulthreadRunner, joinUlthread),
  `881-916` (sceUltUlthreadCreate/Join); commit ffe469199. Provenance: the debt note `libSceUlt.md` says "host lifecycle
  guarantees, not console measurements"; the STATE answer to a losing joiner is AnyPS5's choice (TODO(verify)).
- Ours (`libUlt.cpp:237-292`): the handle is published before `PthreadCreate` stores the thread, and Join takes no claim,
  so a double join or a self-join calls `PthreadJoin` (glibc `pthread_join`) twice on one thread.
- Change (output `src/libs/libUlt.cpp`):
  - helper block :216-369; `UltUlthreadState` gains `bc5_create_mutex` and `bc5_joining` (:91-93, a struct inside the
    .cpp, not a header);
  - Create :398 and Join :435 branch to `Bc5UltUlthreadCreate` / `Bc5UltUlthreadJoin`;
  - includes :8-11; registration :881.
  - Design difference from AnyPS5: AnyPS5 holds its global `gMutex` across `scePthreadCreate`. Here the creator holds a
    per-ulthread mutex from publication until `PthreadCreate` returned. A join of that handle claims under `g_ult_mutex`,
    releases it, then waits on the per-ulthread mutex. Other Ult calls (mutexes, semaphores, queues, the new thread's own
    calls) never wait for a thread creation; lock order is create mutex, then `g_ult_mutex`, and a join never holds both.
  - A join in progress or a self-join (thread_local current ulthread, set by `Bc5UltUlthreadRun`) gets STATE without
    `PthreadJoin`. A failed `PthreadJoin` releases the claim. A failed `PthreadCreate` nulls the thread and unpublishes.
- Test:
  - Both ways: create/join/second join (STATE); unknown runtime (STATE); handle created twice (STATE); self-join (STATE;
    today via glibc EDEADLK).
  - `join` on only: two joiners (one gets 0 with status 42, the other STATE); 100 creates, each joined at once from
    another thread. Off they are not run: today's behaviour there is undefined.
- Risks: medium-low. A guest that joins an ulthread from two threads used to get two successes (or a crash); now the
  second gets STATE. `UltFinalize` clearing the map while ulthreads still run is unchanged (pre-existing).

## Item 5a: R2 SK07, Ult queue push past num_data: PORTED (item `queue`)

- Source: sharpemu 514d766 (GPL-2.0-or-later) `SharpEmu.Libs/Ult/UltExports.Sync.cs:518-560`. Ours `libUlt.cpp:441-451`
  drops the item and returns OK.
- Change: output `libUlt.cpp:609-610` (the capacity check is skipped when on: the queue grows), `:624` catcher.
- Test: data pool num_data 2, data_size 8; push 1,2,3; TryPop x4. On: 1,2,3,AGAIN. Off: 1,2,AGAIN,AGAIN (today).
- Risks: unbounded growth if a title pushes without popping (the catcher shows it). Both sharpemu and AnyPS5 say the
  console blocks such a push; TODO(verify) a blocking push instead (AnyPS5's pool-based queue has one).

## Item 3: R1 #3 + R2 KL03, UserService values: PORTED (`age`, `login`, `name`, `zoom`)

- Provenance checked in the AnyPS5 debt note `docs/dev/debt/libSceUserService.md`:
  - :54 GetUserName 0x80960105 for an unknown user, PS5 13.60;
  - :57 GetAgeLevel 0xFFFFFFFF, and NOT_LOGGED_IN with or without an output, PS5 13.60;
  - :58 the six accessibility getters report 0,0,1,1,0,1 and NOT_LOGGED_IN with or without an output, PS5 13.60.
  - All three are console measurements. The title disassembly quoted in those notes only says how titles use the values;
    no value here rests on it.
- Code source: AnyPS5 `libSceUserService/Export.cpp:42-51, 159-161, 163-174, 238-252`; KytyPS5 dfec14a
  `src/libs/libUserService.cpp:113-132` (KL03, folded into `name`).
- Change (output `src/libs/libUserService.cpp`, CRLF kept):
  - block :31-122;
  - `name` :210: a null name gives 0x80960005; a user not in 1000-1003 gives 0x80960105 (measured; KytyPS5's
    NOT_LOGGED_IN not taken); a buffer too short for "Kyty-N" gives BUFFER_TOO_SHORT 0x8096000A with nothing written
    (KytyPS5's rule; TODO(verify): unmeasured; AnyPS5 also zeroes the buffer, unmeasured too). Today each of these EXITs or
    writes through null.
  - `login` :264, 283, 301, 320, 339, 358, 377: Vibration, TriggerEffect, AgeLevel, ChatTranscription, PressAndHoldDelay,
    ZoomEnabled, ZoomFollowFocus check the login before the null output.
  - `age` :311; `zoom` :387; registration :400.
- Not changed: "logged in" stays `IsLocalUser` (KL04 is a separate item); GetGamePresets order (its debt line rests on
  firmware 13.42 disassembly: held, and ours already checks null first); the user name stays ours.
- Test: 7 getters × (1000, 1003, (1000, null), (5, out) untouched, (-1, null)); GetUserName known users (16 and 7 bytes);
  `name` on: (5), (-1), (1000, 4), (1000, 6) untouched, (1000, null). With `name` off, the four aborting calls run in a
  child (info lines only; the brief says the off case is tested only where it does not abort).
- Risks: low. A title that read 9 as an age level now reads 0xFFFFFFFF ("no restriction"), as on a console.

## Item 4: R1 #4, SystemService parameters: PORTED, parameter 400's value HELD

- Provenance (`docs/dev/debt/libSceSystemService.md`):
  - :74 ParamGetInt answers only 1-5, 100-111, 200-213, 300, 400; others and null give 0x80A10003 without writing. This
    was measured on PS5 13.40 by ptrace inside a retail title, with a sweep of 0-2048: a console measurement.
  - :216 the values of 100-111/200-213/300, the same console on 2026-10-23: a console measurement, of one console's
    settings.
  - :69 ParamGetString answers only 6; under 65 bytes, null or another parameter gives 0x80A10003 without writing; the name
    is NUL-padded to the buffer. PS5 13.60, payload process: a console measurement.
  - HELD: that 400 answers the language (:70 rests on the 10.01/12.60 libSceSystemService modules read and a title's
    disassembly). 400 keeps today's answer, 0, until the maintainer decides.
- Code source: AnyPS5 `libSceSystemService/Export.cpp:40-49` (table), `549-578`.
- Change (output `src/libs/libSystemService.cpp`):
  - block :105-249; `int` refusal :257 (before today's switch, so a refused parameter writes nothing); `table` :283;
    `string` :301; `#include <cstdlib>` :15; registration :726-727.
  - The system name stays "Kyty" (AnyPS5 answers "PS5").
- Parameters 7 and 1000 (game parental level, enter button) are behind `KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000`, apart from
  `int`. On, they give 0x80A10003, as measured (:74). Off, today's 0 and 1 (cross).
- Test: ParamGetInt over 0-8, 99-112, 199-214, 299-301, 399-401, 999-1001, 2048, -1 (each: refused and untouched, or
  today's value or the table's), and (1, null). ParamGetString(6) with 64 and 65 bytes and null. On: unknown 0, 7, 1000
  are refused and the buffer is left alone. Off: today's EXIT, run in a child, info line only.
- Risks: medium. A title that reads 7 or 1000 and does not handle an error (own switch), or relies on 0 for an unknown
  parameter. The table values are one console's settings; their meaning is unknown (TODO(verify)).

## CPU test `lib0405.cpp`

- Build: `build0401.py ... src/libs/libJson2.cpp=<out>/src/libs/libJson2.cpp src/libs/libUlt.cpp=... src/libs/libUserService.cpp=... src/libs/libSystemService.cpp=... --gate lib0405.cpp <bin> --like src/libs/libJson2.cpp`.
- How it runs:
  - It registers all libraries (`Libs::InitAll`), calls the functions by NID, and starts Core/Threads/Config/Log/Timer/
    Memory/Pthread plus the RuntimeLinker, as sav0401.cpp does: ulthreads are real `PthreadCreate` guest threads.
  - Watchdog 150 s. A child that hangs is killed after 5 s.
  - It needs no game, GPU, window, sound device or network. It unsets `KYTY_BC5_INPUT_CONFIG`.
- Runs: all five switches `=1` -> `lib0405 on`; all `=0` or unset -> `lib0405 off`. Item lists -> `mixed`.
- Case count: on 38 (`lib0405: on 38 of 38; end`), off 22 (`lib0405: off 22 of 22; end`). The off info lines (10 Json2
  children, 4 GetUserName children, 1 ParamGetString child) are not counted.
- One assumption: the gate binary's own replacement of `operator delete(void*)` and `operator delete(void*, size_t)` takes
  over the units' deletes (the standard replaceable functions; no custom allocator in the tree).

## Laptop verification (2026-11-04)

- `python mklib0405.py <e4tree> <out>` applies, prints the four md5s below; a rerun gives the same md5s.
- With an output unit put back in the tree, it refuses ("the unit has the edit already").
- The script itself asserts:
  - each pinned input md5;
  - each anchor exactly once;
  - every edit keeps the brace, parenthesis and bracket balance;
  - each helper is used the expected number of times;
  - the inserted text is ASCII; CRLF stays CRLF (libUserService) and LF stays LF;
  - undoing every edit and removing the block gives the input back byte for byte.
- `lib0405.cpp`: balanced, ASCII, no NUL.
- **Syntax** (Visual Studio 18's clang++, x86_64-pc-windows-msvc, as mem0405/svc0405 did):
  - Command: `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` in the tree's Windows configuration. Stand-in
    `cmake_config.h` (KYTY_PLATFORM_WINDOWS); fmt from `refs/Inori_GPCS4` as `-isystem`; magic_enum from
    `refs/InoriRus_Kyty`.
  - Windows-only noise was switched off with `-D_CRT_SECURE_NO_WARNINGS -D_CRT_NONSTDC_NO_WARNINGS
    -D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS`. Without it, the unedited inputs fail too, in fmt and stringUtils.h.
  - Stand-ins, declarations only, kept in `scratchpad/lib0405chk/stub`: a `nlohmann/json.hpp` (not in any local clone),
    and `unistd.h`, `sys/wait.h`, `malloc.h` for the test's POSIX calls.
  - Result: the four inputs and the four outputs are clean. With `-Wshadow -Wconversion -Wsign-conversion` added, both
    inputs and outputs still have no warning.
  - `lib0405.cpp` is clean, also with those three flags.
  - A negative control (an unused variable put into a copy) is caught, so the check really runs.
- Not checked on the laptop: the Linux branches (none of the new code is platform-specific), GCC on the box, the link,
  and running the test (it needs fork and Linux guest threads). The box build is the first real compile and run.

## Not done / held

- Parameter 400 = language (firmware-module provenance): held.
- AnyPS5's reference-module Json2 facts (rebuild on self-set, String storage): held.
- GetGamePresets order (13.42 disassembly): held (ours already null-first).
- KL04 (UserService login set): not in this brief.
- A blocking Ult queue push instead of growth: TODO(verify) on a console.
- Json2's 128 missing exports and `s_null*` objects (R1 #27): later.

## Files

| File | md5 |
|---|---|
| input `src/libs/libJson2.cpp` | d38d30582b49f57f9ef3fea6d84584be |
| input `src/libs/libUlt.cpp` | 9198f40703960fe46e9ba066a6c58ac3 |
| input `src/libs/libUserService.cpp` (CRLF) | 4f90ba6b94167d9b857c8efa89f1cf47 |
| input `src/libs/libSystemService.cpp` | 6c2a2925078d2facd4abe9412408dd57 |
| output `src/libs/libJson2.cpp` | 85144ef10cbfe295d24ab7096710aa10 |
| output `src/libs/libUlt.cpp` | 191fe8b19bf663af73f48cfc85535a5d |
| output `src/libs/libUserService.cpp` | e3d34e9896ac5e6568f691f7c9699a06 |
| output `src/libs/libSystemService.cpp` | 4aa00c539657776620a49e222f3f8fa2 |
| `mklib0405.py` | 547c038fc81f64cc3ef05632c8757ecb |
| `lib0405.cpp` | c640adcefa0f53c9abc9e310f25f9bf7 |
