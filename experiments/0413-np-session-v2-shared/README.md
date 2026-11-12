# 0413 — NpCppWebApi SessionManager V2 into both shared builds

## Question

The ten NpCppWebApi SessionManager V2 NIDs keep "coming back" as missing. Is that a regression, and can they go into
both shared builds for good?

The maintainer, 2026-11-12: "NpCppWebApi - to już było kilka razy dopisywane - znowu był regres i to usunąłeś?", then
"tak przenies i zbuduj - sprawdz przy okazji inne elementy które nigdy nie weszły, a które były testowane".

## History (why it looked like a regression)

| When | What | Where it went |
|---|---|---|
| exp 0328 | AnyPS5's NpCppWebApi port, 136 entry points | patch 0001, shared builds (F393, 77c1ce2c) |
| exp 0329 | the rest of the second title's missing imports, 197 → 10 | patch 0001, shared builds (F393) |
| exp 0402 | names the last ten: SessionManager V2, missed by 0328's port (F809) | analysis only, no code |
| exp 0401 series e | `mknp0401.py` adds the ten behind `KYTY_BC5_NP_SESSION_V2`, **default off** | private builds `exp0401e…` only |

Patch 0001 on main had 0 of the 10, so every build from it lacked them. Nothing was removed; they never reached the
shared builds, and even the private builds needed the variable set.

## Setup

- Base: KytyPlus f266548 (`refs/Coder787-source_KytyPlus`, `git -c core.autocrlf=false archive`) plus main's patch
  0001. `git diff f266548` reproduces main's patch byte for byte: 7e7c6899 with the index lines removed.
- `mknp0413.py` runs `mknp0401.py`'s edit unchanged on `src/libs/libNpCppWebApi.cpp` (exp 0328's unit, md5 7c40b784),
  then makes it **on by default**: the ten are registered unless `KYTY_BC5_NP_SESSION_V2=0`. One stderr line at
  registration:
  - `[bc5] NpCppWebApi SessionManager V2 on (10 exports registered)`
  - `[bc5] NpCppWebApi SessionManager V2 off (KYTY_BC5_NP_SESSION_V2=0, the loader's stubs)`
- Output unit md5 910acbb5. Candidate patch 0001 md5 2dbed49a (a43378ca without index lines). It differs from main's
  only in that file's hunk (+81 lines). Exp 0372's route is intact (5 lines, the header present).
- `int0413.sh`: the swap on the box, modelled on exp 0389's `int0388j.sh`:
  - an atomic BOX-LOCK claim;
  - pins checked first;
  - copies of both binaries and the unit;
  - the unit swapped in;
  - `ninja kyty_emulator` for normal and lean (the backend archive is not rebuilt and must not change);
  - checks that both binaries carry the "on" line and all ten NIDs and that the tree's diff equals the candidate;
  - a restore on any failure.

  Pins in `pins0413.env`, filled from the step-1 read.

## Result

The top session's GO: step 1 at 10:00, step 2 at 10:02. Each box step was guarded (no emulator, no foreign lock).

**Step 1 (reads, 10:01).**
- Shared normal 4d2b1b1d, lean 30d4be33 and archive 75e30335 are exp 0389's pins. The unit was 7c40b784.
- The tree's diff without index lines read 4d186f67, not the 7e7c6899 given in the request, so the step stopped and was
  reported.
- Cause: the laptop's value went through Git Bash's grep, which strips CRs, and the patch has 14,834 CR bytes (CRLF
  host sources).
- The full diff fetched from the box is byte-identical (`cmp`) to main's patch 0001, md5 728f2a77 on both sides.
- The top accepted this and set the pin to 4d186f67. Added to LESSONS R45.

**Step 2 (the swap, 10:03:10–10:03:32, `int0413.sh` from `~/bc5-work/exp0413/s/`).**
- The lock was claimed by hard link and released at the end.
- Ninja rebuilt the one unit and relinked: normal 10 s, lean 11 s.

| | before | after |
|---|---|---|
| normal `~/bc5-work/kytyplus-build/src/kyty_emulator` | 4d2b1b1d | **f6445dc6** |
| lean `~/bc5-work/kytyplus-build-lean/src/kyty_emulator` | 30d4be33 | **30ee854b** |
| archive `libbc5_backend.a` | 75e30335 | 75e30335 (not rebuilt) |
| `~/src/KytyPlus/src/libs/libNpCppWebApi.cpp` | 7c40b784 | 910acbb5 |
| tree diff vs f266548 | main's 0001 (728f2a77) | candidate (2dbed49a) |

The script's checks passed:
- both binaries changed and the archive did not;
- each binary holds the "on" line once and all ten NIDs;
- the tree's diff equals the candidate patch.

Three warnings in each build:
- `libNpCppWebApi.cpp:50` (`-Winvalid-noreturn`) and `:62` (an unused constant), both in exp 0328's code above the new
  block;
- `stringUtils.h:321` (deprecated `wstring_convert`).

None comes from the new lines. No emulator was started. `~/bc5-work/exp0412` was not touched.

**Rollback.** Copy back `~/bc5-work/exp0413/swap/kyty_emulator.before-0413` and `kyty_emulator-lean.before-0413` over
the two binaries, and `libNpCppWebApi.cpp.before-0413` over the unit. Then rebuild before the next change, since the
build directories' objects are the new ones. A rollback without touching files: `KYTY_BC5_NP_SESSION_V2=0`.

**Not verified here:** the ten functions at run time. Series e's `npgate0401` gate ran on private builds only. The
title's calls go through the maintainer's play.

## Verdict

The ten SessionManager V2 NIDs are in both shared builds and in patch 0001 on this branch (2dbed49a), on by default. They
no longer depend on a private build or a variable. A run-time check in play is still to come.

## Audit: other tested items never integrated

The maintainer also asked to check the other items that were tested but never integrated. `audit-unintegrated.md`
(read-only, laptop) lists 67 rows with file:line evidence. Nothing from exp 0390 on is in patch 0001; the last patch
commit on main is a8324c8b (exp 0389). 28 rows are recommended for integration default on, 20 default off, 19 left out
(failed, answered catchers, or no measured gain). Each integration needs the maintainer's yes (D19).
