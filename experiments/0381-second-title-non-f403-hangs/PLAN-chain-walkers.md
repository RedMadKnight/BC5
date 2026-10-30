# Plan: INDIRECT_BUFFER CHAIN in the tracker and the other walkers

Status: a plan, nothing built, nothing run. It needs Codex's review and the maintainer's yes before any runtime change.
Separate from PORT-CHAIN (`fix/port-chain`, which fixes `acb_restore::final_value` only).

## The problem

`full_state::Tracker` treats an `INDIRECT_BUFFER` with the CHAIN bit (bit 20 of the size dword, AMD PAL c5e8000
`gfx9_plus_merged_f32_pfp_pm4_packets.h:2580`) as a call that returns, so it goes on to apply the packets after it, which the
CP never runs. Codex reproduced this through the real code (REVIEW-PORTS-01, `port-review-probe.cpp`): the target ends with
0x22, and the dead tail gives tracked 0x33 and **an emitted prefix of 0x33**. So this reaches what we send to the GPU, not only
logs (F761).

**What is not known:** whether any CHAIN occurs in the title's streams. Nobody has counted. No link to F443 or Q21 is shown, and
this plan claims none.

## The risk, plainly

The tracker's values go out in three places: the full prefix, the CS prefix (on in `play-pkg.sh` since exp 0195), and
`BC5_DIRECT_ACB_STATE_RESTORE`. If a title buffer holds a taken CHAIN with a tail that writes compute registers, the next
buffer's prefix can carry a wrong value. That is F443's class of fault, made by the fix for F443.

- The test build 4c686b5b has this exposure. The CS prefix has had it in play since exp 0195.
- The restore widens it from buffers that dispatch before setting a program to **every dispatching buffer**.
- **So the restore should not go default-on in the shared builds until Step 0 has counted CHAINs in real streams.** The test
  build can stay as it is: it is private, and its smoke saw no fault, but that smoke does not bear on this question.

## Step 0: count first (no code in the emulator)

A read-only scanner over the command buffers already on the box (`ib-*.bin`, `ib-timeout-*.bin` under
`~/bc5-data/captures`), offline, counting per file: `INDIRECT_BUFFER` packets, those with the CHAIN bit, those under a
`COND_EXEC`, and whether packets follow a CHAIN. Counts only; nothing from the dumps is committed. Limits: these dumps are
samples, mostly around hangs, and nested targets are reached only if the dump holds them. A count of zero there is
evidence, not proof. A fuller count needs one run with a counter in the host, which is a separate request.

- **CHAINs found:** the tracker fix is urgent, and the restore stays off everywhere it is not already on until the fix is in.
- **None found:** the fix stays small and worthwhile as a safety; it is no blocker for a shared-build decision, and that
  decision is the maintainer's, with the limit above stated.

## Step 1: the fix, walker by walker

A shared helper in `pm4.hpp`, `ib_is_chain(size_dword)`, one definition with the PAL citation.

| Walker | Today | Proposed | Weight |
|---|---|---|---|
| `Tracker::apply_level`, `full_state.cpp:214` | applies the tail | an unconditional CHAIN: follow the target, end this level. Unreadable target: end this level, count it | **runtime**, feeds every prefix |
| `walk_draws`, `full_state.cpp:357` | visits draws in the tail | the same; flush `from` first, as it does for a call | runtime, per draw state |
| `Tracker` under `COND_EXEC` | follows it as if taken (documented) | a conditional CHAIN: follow the target and keep walking, as today, and count it in a new stat. The tracker has one value per register, so it cannot join two ways | a known limit, made visible |
| `Touched::scan_level`, `acb_restore.hpp` | over-reports | stop at an unconditional CHAIN | diagnostic only |
| `policy.cpp:242` | scans the tail for refusals | stop at an unconditional CHAIN only if Step 0 finds any | changes ring routing; leave it otherwise |
| `direct.cpp:1134`, `:1506` | copies and patches targets found in the tail | no change now: an extra copy is harmless unless the tail is garbage | report only |
| `direct.cpp:1134/1506` high half mask 0xff, others 0xffff | an inconsistency | a separate finding, separate task | unrelated to CHAIN |
| Host walkers in patch 0001 (lines 31113, 32045, 33924, 34366, 35351) | **not reviewed line by line** | review in this task; report; no change without a new yes | unknown |

Limits: a chain does not nest on the CP, so it should not count against the tracker's call depth of 4. It gets its own limit
(256 links) and a visited set, and hitting either ends the level and counts it. The tracker has no Unknown, so what it could
not follow can only be counted (`stats`) and journaled, which already applies to unreadable tables.

## Tests (Catch2, CPU only, written first)

Tracker, `[full_state][chain]`:
1. Codex's case as a regression: target 0x22, dead tail 0x33: tracked 0x22, `emit_prefix` 0x22.
2. A call: unchanged, the tail applies.
3. A chain of chains; a call holding a CHAIN returns and the caller's tail applies.
4. An unreadable CHAIN: tail not applied, counted.
5. A CHAIN cycle and the 256 limit: ends, counted, no hang.
6. A conditional CHAIN: behaviour as today, counted.
7. A CHAIN with a context register, a `SET_BASE` and `CLEAR_STATE` in its tail: none applied. Also `adopt_stack` and the
   context stack across a CHAIN.

`walk_draws`, `[full_state][chain]`: no draw visited from a dead tail; draws in the target visited with the right state.

`Touched`: a dead tail not marked; a call's tail still marked.

**No-change proof:** the new tracker against the old on recorded streams with no CHAIN bit (Step 0's files, `piece-check`):
the same tracked registers and the same emitted prefix, byte for byte. This is what lets the change into a build without a
new GPU test of everything.

## Gates and order

1. Step 0's scanner: laptop first with a synthetic file, then one read-only run on the box (a slot and the maintainer's go).
2. Tests and fix on `fix/chain-walkers`, from main, in one commit after PORT-CHAIN merges, since both touch `acb_restore.hpp`.
3. Full Catch2 and subsets, MSVC and clang, `direct-selftest` without `--submit`, with `pcrun0381.sh`'s rules.
4. The no-change proof on the box.
5. Into shared builds only on the maintainer's yes (D19): the archive changes, so it needs a rebuild and a smoke.

Stop if it needs a change to submission or restore emission, or if the no-change proof differs on a stream with no CHAIN.
Rollback: revert the one commit.

Findings: F762 onward. Estimate: Step 0 is small. The fix is small in lines, but it is in the path every prefix takes, so its
weight is in the proof.
