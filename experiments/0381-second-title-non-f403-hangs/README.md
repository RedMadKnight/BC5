# 0381 — The second title's GPU hangs that are not F403: the 18:08 graphics stall and the 16:25 TCP fault

**Date.** 2026-10-29 (evening, the maintainer away). **Branch.** `exp/0381-non-f403-hangs`. **Box.** Reads only, on the
top session's GO (section 3); everything else on the laptop.

## Question

1. The 18:08:13 hang on the shared normal build (58c4a627, RT on; F588) is a graphics-pipe stall, not F403. Which
   state is it against the healthy baseline of exp 0378, and which draw or pass hangs?
2. The 16:25 start-up fault (exp 0380 start 1, test binary c3c8660b; F582/F586) — a TCP read fault at junk addresses,
   ring resets that succeed, the picture lost, program 0x909977100 — is it F443/Q22's garbage-pointer class, and does
   it tie to the BVH compaction (F207, F370) or to the garbage-pointer work (F92, F467)?
3. For each: the evidence, the hanging pass if the data allows, and the next test or fix candidate.

## Setup

- Read: HANDOFF F207, F403, F443, Q22, F467–F469 (exp 0364), F490–F495 (exp 0368), F519, F525, F534–F535, F553,
  F558, F582–F609 (exp 0380's branch at 6c0c84d), exp 0380 README §16–17 and its `raw/hang-1808/`, `raw/wbplay/`,
  the 0300 close-out (`docs/closed-branches/exp-0300-rt-dispatch-sync/`), the shared notes of the BVH compaction
  session (exp 0160's hand-over, the compaction output design note).
- `ana0381.py`: decodes the 18:08 devcoredump registers, F519's ASTRO BOT stop, the two 16:25 sampler values and
  F525's F403 sample with Linux v7.2 `gc_10_1_0_sh_mask.h` (blob 9b7d219e, ana0378.py's functions), compares 18:08
  field by field with exp 0378's 40 healthy forced samples and tests single-sample rules. Output `raw/ana.txt`.
- `reads0381.sh` (box, reads only): guard, lock, claim, then `walk0381.py` over the two private probe dumps
  (`ib-timeout-00127530-dcb-14945.bin`, `ib-timeout-00032979-dcb-14911.bin`): every draw and dispatch with the
  shader-stage, tessellation, streamout and user-data registers the IB itself sets (state from `LOAD_*_REG_INDEX`
  tables is invisible to it); the two devcoredumps' status registers; the probe and learned-region lines of the two
  journals. `filter0381.py` turns its output into the committed extracts; the dumps and journals stay private.

## 1. Laptop results

### 18:08 is a third stall state (F660)

Decoded (`raw/ana.txt`):

| | 18:08 | F403 (09:48) | F519 (ASTRO BOT 06:34) |
| --- | --- | --- | --- |
| `GRBM_STATUS` | 0xa2712028: GE, PA, SX, SPI busy; CB clean, DB **not** clean, SC/DB/CB idle, TA idle | 0xa0407028: TA, SPI busy; CB/DB clean | 0xe5f100ac: GE, SX, SPI, BCI, SC, DB, CB busy |
| `GRBM_STATUS2` | 0x50000008: no TCP, EA, EA_LINK, UTCL2 | 0x52000008: TCP busy | 0x50000008 |
| SE0 / SE1 | 0x0d000004 both: PA, SX, SPI | 0x0a000036: TA, TCP, GL1CC, SPI | 0x08000000 / 0xec400000 |
| `CP_STALLED_STAT2` | 0x218000: ME waits on a partial flush, EOPD needs SC EOP done | 0x18000: partial flush | 0x31000: ME parsing, RCIU not ready |
| `CP_BUSY_STAT` | 0x448400: EOP_DONE_BUSY, GFX_CONTEXT_BUSY | 0x400400 | 0x428100: ME parsing packets |

- Against the 40 healthy samples it is never close: the nearest differ by 18–20 status bits (F534's F403 sample
  differed from a healthy one by one bit). No healthy sample has GE busy with TA idle together with the partial-flush
  and EOP waits (0/40); 17 have the partial-flush wait, 3 of them with GE busy, 2 with GE busy and the EOP wait,
  and all three of those with TA, EA and `EA_LINK_BUSY` busy (10:51:35, :45, :50).
- The five sampler records over 1.2 s are identical (`GRBM_STATUS` 0xa2712028 in all; exp 0380 `raw/hang-1808/`).
  A draw grinding through a huge count would toggle SC/DB/TA; this is a standstill.
- So: waves resident (SPI busy) with **no memory traffic at all** (TA, TCP, GL1, EA, UTCL2 idle), the geometry
  front end (GE → PA, with SX's export path) holding work, the rasteriser and the back end empty, the CP past the
  IB waiting for the pipe to drain. The class is a geometry-front-end deadlock, distinct from F403 (compute waves
  busy in TA/TCP, GE idle) and from F519 (the back end busy, no partial-flush wait).

### Single-sample rules (F661)

| rule | healthy (40) | 18:08 | F519 | F403 |
| --- | --- | --- | --- | --- |
| F535: partial-flush wait, `EA_LINK_BUSY` clear | 0 | yes | no | yes |
| F589 compute: F535 + TA busy, GE idle, no EOPD wait | 0 | no | no | yes |
| graphics: F535 + GE busy, TA idle, EOPD wait | 0 | yes | no | no |
| graphics without the EA term | 0 | yes | no | no |

The early-warning design of F535 can therefore name two classes from one sample: `f403-early` (compute) and
`gfx-stall-early` (graphics). F519 is caught by neither (no partial-flush wait); it needs the stall clock alone.

### 16:25 is F443's pointer family, not the compaction (F662)

- The ten fault pages 0x8608c654000…0x8608c660000 (TCP, read, `PERMISSION_FAULTS` 0x3, status 0x00601031) have the
  low dwords 0x8c654000–0x8c660000. F443's junk pages were 0xe3808c5f2000…0xe3808c634000, low dwords
  0x8c5f2000–0x8c634000, which exp 0364 showed are one dispatch family's `COMPUTE_USER_DATA_3` offsets under the
  shared high dword 0x11 with that high dword replaced by garbage (F467). The 16:25 pages lie 0x20000–0x6e000 above
  them, under another garbage high dword (0x860 instead of 0xe380). Exp 0380 searched the maps for 0x8608c65c000,
  0x608c65c000 and 0x8c65c000 but not for 0x118c65c000, the address the family's layout predicts.
- The stuck dcb has the family's shape: a `LOAD_SH_REG_INDEX` from a 0x9098… table (0x909842dc0 here; F467:
  0x909841e50, 0x909842900, 0x9098426a0; F422: 0x909842440), then `SET_SH_REG` of `COMPUTE_USER_DATA_3…`
  (registers 0x243/0x247) between unbased GFX-form `DISPATCH_INDIRECT`s (exp 0380 `raw/wbplay/dcb-32979-head.txt`).
- Program 0x909977100 is the BVH adjacency build, one of the three consumers of the compaction 0x909974400's
  compacted list (exp 0160's reading, the compaction session's hand-over), and the compaction runs in the shared
  launchers (`BC5_DIRECT_SKIP_PGM=0`, exp 0378 `raw/B1-start.txt`). That is the only tie to F207: F207's fault is
  the geometry engine (GE2/WD) reading page 0 with the full-state prefix, a different client and mechanism.
- F443 happened on a build without `FORCE_START_AT_000` (the ledger build, 10-28), so the 16:25 test binary's
  FORCE_START is not needed to explain the class.
- Unlike F443, no real-address fault came first: the first printed fault is already a junk address (and the
  kernel's rate limit printed exactly ten). So the high dword was garbage from the start of the access, not
  after a first fault. Where the high dword comes from (the IB's user data, the `LOAD_SH_REG_INDEX` table, or a
  pointer the shader loads from the compacted data) is what the box read decides.

## 2. Hypotheses, ranked

18:08:
- **H1 (lead): a geometry-front-end deadlock in one of the dcb's last draws**, waves resident without memory
  traffic. Sub-cases: (a) tessellation: the dcb holds HS-stage draws (the probe's "HS user data" lines at dwords
  1046, 9233, 12139), the host owns the TF ring and the full-state prefix rewrites `VGT_TF_RING_SIZE` /
  `VGT_TF_MEMORY_BASE(_HI)` in front of every drawing dcb (F599), and exp 0160 tied the second title's GE faults to
  tessellation state; (b) an NGG or GDS ordered-count wait (the title appends to GDS, F207).
- H2: a runaway indirect draw with a garbage count, the graphics twin of F403 sub-class B. Against it: the
  standstill over 1.2 s and TA idle.
- H3: a memory wait (late data after the unpause, page-cache pressure F602). Against it: EA, UTCL2, TCP idle, no
  fault.
- Not F403: TA/TCP idle, GE busy, EOP pending (F588; the table above).

16:25:
- **H4 (lead): F443's dispatch family reading or building a pointer with a bad high dword**, the class of F92's
  junk upper bits. Sub-cases: (a) the bad high dword is in the IB's user data or in the `LOAD_SH_REG_INDEX` table
  (the host's tracking or a stale table); (b) the shader loads it from data that was not written yet at start-up
  (the compacted list or its header, written on another ring or later: the compaction design note's outcomes b/c).
- H5: the lazy-import class of F468 (an unimported view). Against it: no real-address fault preceded the junk.
- H6: the test binary's FORCE_START. Against it: F443 without it.

## 3. The box reads

Pending the top session's GO.

## Result

Pending.

## Verdict

Pending.
