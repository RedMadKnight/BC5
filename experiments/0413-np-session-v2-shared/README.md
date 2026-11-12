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

Pending: the top session's GO for the box read and the slot.

## Verdict

Pending.
