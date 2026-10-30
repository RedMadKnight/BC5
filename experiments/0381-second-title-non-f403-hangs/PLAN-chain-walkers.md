# Plan: INDIRECT_BUFFER CHAIN in the tracker and the other walkers

Status: a plan. Revision 2, after Codex rejected Step 1 of the first version. Nothing runs in the host, and no box step has
run. Allowed now: this plan, the scanner, and synthetic CPU tests. A runtime fix needs its own review and the maintainer's yes.
Separate from PORT-CHAIN (`fix/port-chain`, which fixes `acb_restore::final_value` only).

## The problem

`full_state::Tracker` treats an `INDIRECT_BUFFER` with the CHAIN bit (bit 20 of the size dword, AMD PAL c5e8000
`gfx9_plus_merged_f32_pfp_pm4_packets.h:2580`) as a call that returns, and goes on to apply packets the CP never runs. Codex
reproduced this through the real code (REVIEW-PORTS-01, `port-review-probe.cpp`): the target ends with 0x22, and the dead tail
gives tracked 0x33 and **an emitted prefix of 0x33** (F761).

**Not known:** whether any CHAIN occurs in the title's streams. No link to F443 or Q21 is shown, and this plan claims none.

## The risk, plainly

The tracker's values go out in the full prefix, the CS prefix (on in `play-pkg.sh` since exp 0195) and
`BC5_DIRECT_ACB_STATE_RESTORE`. A value the tracker has wrong is sent to the GPU as fact: F443's class of fault, from the
fix for F443.
- Test build 4c686b5b has this exposure; the CS prefix has had it in play since exp 0195.
- The restore widens it from buffers that dispatch before setting a program to **every dispatching buffer**.
- **Default-on for the restore in shared builds has to wait for the contract below.** An empty count (Step 0) does not close
  this: the dumps are incomplete, and Codex is right that absence from them is not a reason to go on.

## What changed from the first version, and why

The first version counted what it could not follow and kept the old values, and for a conditional CHAIN it followed the target
and kept the tail. Both are wrong. A count removes nothing: `emit_prefix` still sends stale values as certain. And a conditional
CHAIN with target 0x22 and tail 0x33 has two possible ends, but it would have given a certain 0x33, the same defect.

## The contract

**A register the tracker calls certain holds that value at every end of the stream. Anything else is uncertain, and is not
emitted as fact.** It needs one flag per register, not a copy of the state per way.

| Case | Rule |
|---|---|
| Unconditional CHAIN | follow the target; the tail is dead |
| A write under `COND_EXEC` | uncertain, unless it writes the certain value already there |
| A call under `COND_EXEC` | the target's writes count as conditional |
| A conditional CHAIN | the target is walked as conditional, and so is the rest of this buffer |
| Unreadable target, cycle, limit, unreadable table that may cover the register | **every** register uncertain (it could write anything), in O(1) by a generation count; the walk of that buffer goes on for a call and ends for a CHAIN |
| A later plain write | makes that one register certain again |
| `CLEAR_STATE` or a state push/pop under a condition | the context space uncertain |
| `SET_BASE`, `INDEX_BASE` and the other tracked packets | the same flag, per packet |
| A `COND_EXEC` whose count runs past the buffer | the rest uncertain, and the next buffer starts with a carried count |

Both ends writing the same value still reads as uncertain; that is a safe overestimate, and the price of keeping no second
copy.

**What this does not cover.** A table read from the CPU's view at submit can differ from what the CP reads (Codex's REVIEW-06).
That stays a stated limit, and a certain register means certain *in the host's view*.

## What happens to an uncertain register at emission

Two options, and I recommend the first for the restore and neither yet for the other prefixes.

1. **Leave it out.** The restore omits uncertain registers and journals them. An omitted register stays as the ring left it, the
   same as with the restore off for that register, so it is no worse than today. This keeps a dispatch working when one user-data
   register is in doubt.
2. **Refuse the whole prefix.** Clearer, but a single uncertain register would drop the program too.

The **CS and full prefixes run today and carry the title.** How often registers go uncertain there is unknown, and title streams
do use `COND_EXEC`, so a strict policy could remove registers the title needs. They therefore go through **shadow mode first**:
the tracker computes the flags, emission is unchanged, and the journal counts uncertain registers at each prefix, by name of
register. That number decides their policy, in its own review.

## The check that it is safe

`trackermodel0381.py` models the contract and tests it against the truth: every way through a stream, by brute force, with
something that cannot be followed allowed to leave any value.
- 13 named cases, among them Codex's: seeds, an unreadable target, both ways of a conditional CHAIN, and the effect on the safe
  prefix.
- 40,000 random streams: no register claimed certain is wrong at any end.
- The check can fail: the first plan's design and today's tracker are both caught as mutants.

It is a model of control flow in Python, not the C++ tracker, and it has no tables or packet layouts. The Catch2 tests below must
hold for the real code.

## Step 0: count (no code in the emulator)

`chainscan0381.py` (12 synthetic cases) reads dumped buffers and prints counts only: packets, IBs, CHAINs, those under a
`COND_EXEC`, CHAINs with a tail, other lengths of 0x3f, malformed. It answers how urgent this is. It does not decide safety.

**The box step, for a separate GO**, needing a slot, the lock and the maintainer's go. The script is piped over ssh, nothing is
installed, and nothing is written on the box:

```bash
ssh bc250 'pgrep "^kyty_emulator" >/dev/null && exit 3; [ -s ~/bc5-work/BOX-LOCK ] && exit 4; cd ~/bc5-data/captures && find . -type f -name "ib-*.bin" ! -name "*.tfring.bin" -mtime -14 -size -64M -print0 | sort -z | head -z -n 5000 | nice -n 19 ionice -c3 xargs -0 python3 - --max-files 5000 --max-bytes 2147483648' < chainscan0381.py
```

- **Pin:** the script's md5 is recorded in the report, with the commit.
- **Input limits:** `ib-*.bin` under `captures`, the last 14 days, at most 5,000 files, 2 GiB, 64 MiB each; `.tfring.bin` left out.
- **Output limits:** two lines of counts on stdout, no paths, addresses or dwords. Those two lines may go into git. Nothing raw does.
- **Reading the result:** the dumps are samples, mostly around hangs, and hold one buffer each. A CHAIN inside a nested target is
  not seen. So zero is evidence of rarity, not of absence, and it closes nothing. A fuller count needs a host counter: a separate
  request.

## Step 1: the walkers

| Walker | Today | Proposed | Weight |
|---|---|---|---|
| `Tracker::apply_level`, `full_state.cpp:214` | applies the tail, every COND_EXEC taken | the contract above | **runtime**: flags computed; emission changes only by the policy above |
| `walk_draws`, `full_state.cpp:357` | visits draws in the tail | stop at an unconditional CHAIN; under a condition keep visiting, with the flags in the tracker it passes on | runtime, per draw state |
| `acb_restore::runs` | emits all tracked | emits certain registers only | the restore, off by default |
| `Touched::scan_level`, `acb_restore.hpp` | over-reports | stop at an unconditional CHAIN | diagnostic |
| `policy.cpp:242` | scans the tail for refusals | no change now; extra refusals are conservative | report only |
| `direct.cpp:1134`, `:1506` | copies targets found in the tail | no change now | report only |
| `direct.cpp:1134/1506` high-half mask 0xff, others 0xffff | an inconsistency | separate finding, separate task | unrelated |
| Host walkers in patch 0001 (lines 31113, 32045, 33924, 34366, 35351) | **not reviewed line by line** | review; report; no change without a new yes | unknown |

A chain does not nest on the CP, so it should not count against the tracker's call depth of 4: it gets its own limit (256 links)
and a visited set, and hitting either one is "cannot be followed". A shared `ib_is_chain` goes in `pm4.hpp`.

## Tests, written first (Catch2, CPU only)

`[full_state][chain]`, on the real tracker, each also through `emit_prefix` and `acb_restore::runs`:
1. Codex's case: target 0x22, dead tail 0x33: certain 0x22, emitted 0x22.
2. A call: unchanged, the tail applies and is certain.
3. A chain of chains; a call holding a CHAIN returns, and the caller's tail applies.
4. **Seeds:** a seed, then an unreadable call: uncertain, not emitted; a later plain write brings back that register only.
5. **An unreadable CHAIN:** tail not applied, all uncertain, none emitted as fact.
6. **Both ways of a conditional CHAIN:** target 0x22 and tail 0x33: uncertain, not emitted. A silent target keeps the seed; the tail's
   writes are uncertain.
7. A conditional write of the certain value stays certain; of another value, not.
8. A CHAIN cycle, a call cycle, the 256 limit: end, uncertain, no hang.
9. Unreadable tables, flat and in pairs, against a seed.
10. Context registers, `SET_BASE` and `CLEAR_STATE` in a dead tail and under a condition; `adopt_stack` across a CHAIN.
11. A random property test: the model's generator in C++, the real tracker against brute-force ends.

`walk_draws`: no draw from a dead tail; draws in the target see the right state. `Touched`: a dead tail not marked.

**No-change proof:** with shadow mode only, the same emitted prefixes byte for byte as today on recorded streams.

## Gates and order

1. Now: this plan, the model, the scanner. Codex reviews.
2. Step 0 on the box, on its own GO.
3. Tests and tracker flags on `fix/chain-walkers`, in shadow mode, from main after PORT-CHAIN merges. Full Catch2, MSVC and clang,
   `direct-selftest` without `--submit`, and the no-change proof.
4. A test run with shadow mode, reading the uncertain counts. It needs a build and the maintainer's yes.
5. Emission policy per consumer, each with its own review. The restore's default-on question is answered here, not before.
6. Shared builds only on the maintainer's yes (D19).

Stop if it needs a change to submission, if the no-change proof differs, or if shadow mode finds so many uncertain registers that
the policy would remove what the title needs. Then the flag's precision needs a new design: a report, not a workaround.
Rollback: revert each commit; shadow mode has no effect on emission.

Findings: F762 onward. The lines are few, but this is the path every prefix takes, and that is where the weight is.
