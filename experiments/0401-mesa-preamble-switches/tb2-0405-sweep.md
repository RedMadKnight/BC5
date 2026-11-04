# Dead tables, batch 2: the sweep (exp 0405 decision 4, after series e6)

The maintainer's decision 4 of exp 0405 ("=> B => B": port first, then load, a switch per table) for the 26 tables that
batch 1 (series e6: tbc, tbn, tld) left. The top session's order (2026-11-04, after e6): the CPU-only library tables first,
then the hardware ones, then GnmDriver, RazorCpu, RageEngine and Ngs2 (Ngs2 never from `ngs2_pcm.h`). Laptop only.

## How it was counted

- **The tree.** The e6 input tree: e5's sources with e6's fifteen outputs on top (each md5 checked against `box0401.sh`'s
  E6_EDITS), assembled in the scratch directory.
- **The census.** exp 0405's own scripts, unchanged, on that tree: `r1-anyps5-inventory.py` (AnyPS5 4f41f4c37,
  GPL-2.0-only), `r1-anyps5-loaded.py`, `r1-anyps5-report.py`. 3,134 of our NIDs; 1,911 live; 1,223 only in tables
  `InitAll` never calls (the switch block of e6's libs.cpp is not seen by the parser, so batch 1's six count as dead here).
- **The sweep** (scratch `sweep.py`): for each dead NID, the table (the file of its `LIB_FUNC`), our body (a stub is only
  `PRINT_NAME()` and a `return` of a constant), and AnyPS5's body for the same NID in any module (logic, const, not
  implemented, absent).
- **Size.** exp 0405's rule: logic lines ÷ 150 plus constants ÷ 200, in days. It counts only the NIDs our table registers.
- **Live NIDs, same library** are tld0405-notes.md's: live records under the table's own library key. They mark the tables
  whose port must share state with a live implementation (as Ime and NpManager in batch 1).

## Sizes

| Group | Table | Our NIDs (our real bodies) | AnyPS5 logic / const / not impl. / absent | Logic lines | Size, days | Live NIDs, same library |
|---|---|---|---|---|---|---|
| library | NpTus | 142 (0) | 136 / 0 / 6 / 0 | 784 | 5.2 | 0 |
| library | NpParty | 26 (0) | 13 / 2 / 11 / 0 | 48 | 0.3 | 0 |
| library | NpPartner001 | 4 (0) | 3 / 0 / 1 / 0 | 17 | 0.1 | 0 |
| library | NpAuth | 5 (0) | 5 / 0 / 0 / 0 | 26 | 0.2 | 8 |
| library | NpSnsFacebookDialog | 1 (0) | 1 / 0 / 0 / 0 | 3 | 0.0 | 0 |
| library | Voice | 14 (0) | 13 / 1 / 0 / 0 | 138 | 0.9 | 16 |
| library | ScreenShot | 14 (0) | 3 / 4 / 7 / 0 | 13 | 0.1 | 0 |
| library | DiscMap | 5 (0) | 2 / 0 / 3 / 0 | 16 | 0.1 | 0 |
| library | ulobjmgr | 4 (0) | 2 / 0 / 2 / 0 | 6 | 0.0 | 0 |
| library | CompanionHttpd | 17 (0) | 8 / 3 / 6 / 0 | 65 | 0.4 | 0 |
| library | CompanionUtil | 5 (0) | 0 / 5 / 0 / 0 | 0 | 0.0 | 0 |
| library | InvitationDialog | 9 (6) | 7 / 0 / 2 / 0 | 68 | 0.5 | 0 |
| library | WebBrowserDialog | 12 (4) | 8 / 0 / 4 / 0 | 78 | 0.5 | 2 |
| library | SharePlay | 22 (0) | 2 / 0 / 19 / 1 | 18 | 0.1 | 2 |
| library | GameLiveStreaming | 45 (0) | 20 / 0 / 25 / 0 | 124 | 0.8 | 2 |
| library | Remoteplay | 39 (0) | 0 / 0 / 38 / 1 | 0 | 0.0 | 3 |
| library | VideoRecording | 1 (0) | 1 / 0 / 0 / 0 | 13 | 0.1 | 0 |
| library | **total** | 365 (10) | | 1417 | **9.5** | |
| hardware | Camera | 76 (0) | 44 / 10 / 22 / 0 | 190 | 1.3 | 0 |
| hardware | Usbd | 65 (0) | 61 / 0 / 0 / 4 | 524 | 3.5 | 0 |
| hardware | Hmd | 137 (0) | 11 / 6 / 120 / 0 | 53 | 0.4 | 0 |
| hardware | VrTracker | 39 (0) | 10 / 0 / 29 / 0 | 77 | 0.5 | 0 |
| hardware | Move | 11 (0) | 11 / 0 / 0 / 0 | 62 | 0.4 | 0 |
| hardware | **total** | 328 (0) | | 906 | **6.1** | |
| gpu/audio | GnmDriver | 251 (17) | 33 / 53 / 48 / 117 | 320 | 2.4 | 0 |
| gpu/audio | RazorCpu | 34 (0) | 9 / 23 / 2 / 0 | 64 | 0.5 | 1 |
| gpu/audio | RageEngine | 15 (15) | 0 / 0 / 0 / 15 | 0 | 0.0 | 0 |
| gpu/audio | Ngs2 | 40 (0) | 23 / 0 / 16 / 1 | 361 | 2.4 | 26 |
| gpu/audio | **total** | 340 (32) | | 745 | **5.3** | |

All 26: 1,033 NIDs, 3,068 logic lines, about 21 days by the rule.

## What the numbers say

- **Our bodies are stubs.** Of the 1,033 NIDs, 42 have a real body (InvitationDialog 6, WebBrowserDialog 4, GnmDriver 17,
  RageEngine 15). Every other one returns OK and writes nothing, so loading a table unported would answer every call with
  OK and leave its outputs unwritten.
- **Nothing to port for two.** AnyPS5 implements none of Remoteplay's 39 and has none of RageEngine's 15 (RageEngine is
  not a module there). For those, the port is our own code or nothing, and loading them changes only which stub answers.
- **Not implemented upstream either.** 361 NIDs are AnyPS5 stubs too (Hmd 120, VrTracker 29, SharePlay 19,
  GameLiveStreaming 25, Remoteplay 38, ...). These stay our stubs and are held, as batch 1 held NpTrophy's placeholders.
- **The biggest single item** is NpTus: 136 functions, 784 lines, about 5 days. They are many variants of the same few
  requests, so it may go faster than the rule says.
- **Split state.** NpAuth, Voice, WebBrowserDialog, SharePlay, GameLiveStreaming, Remoteplay and RazorCpu have live
  functions in the same library (Ngs2 has 26). Each port must share state with the live side, or show that none is shared.
- **Provenance.** AnyPS5's notes for these modules cite shadPS4, firmware runs (BunnyFl's 13.42 run) and module readings
  (accepted under decision 1), and in places Orbital's IDA type database (`libSceVoice`: SetMuteFlagAll, SetBitRate,
  UpdatePort). Rows that name an IDA database, a disassembly with addresses or SDK headers as their source stay out, as in
  batch 1. Each port agent checks its rows.
- **Usbd** follows AnyPS5's libusb transport: it needs host USB access and is the largest hardware item (exp 0405 #42).

## Files

| File | Note |
|---|---|
| scratch `e7/sweep.py` | the sweep |
| scratch `e7/sweep/sweep-tables.tsv`, `sweep-nids.tsv` | its output, one row per table and per NID |
| scratch `e7/census/` | the census of the e6 tree |
