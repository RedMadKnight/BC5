# Exp 0439, bake 2: the third title's fixes for every title

Bake 2 sits on top of exp 0442's bake 1 (branch `exp/0442-title-defaults-audit` at 24ed91cc). It applies the fixes of
exp 0439 that are proven or justified, for every title. Each fix is on by default through `switch_defaults.hpp` kSoft,
and `NAME=0` in the environment turns one off. Nothing learned is in it, and no probe or capture.

## The fixes

The first-title risk column is my reading; the A/B is what settles it.

| fix (tag) | word | finding | evidence | risk for the first title |
|---|---|---|---|---|
| ib439: soft CP: a chained IB runs at the caller's depth and ends the caller's buffer. The GPU copy follows chains by the chain rule. | `BC5_DIRECT_IB_CHAIN` | README item 26 | the third title shows no screen without it | low to moderate: only buffers with chains change |
| fl439: a compute job's top-level chain laid out flat, so that the root-only backend passes see every segment | `BC5_DIRECT_IB_CHAIN_FLAT` | items 26-28 | needed for the title's screens | moderate: rewrites compute jobs that chain at the top level |
| ae439: end-of-pipe interrupts with the AGC idents | `BC5_DIRECT_AGC_EOP_IDENT` | F890 | the job-system stall is gone | the highest; see below |
| FLAT_APERTURE moved from TITLE2's row | `BC5_DIRECT_FLAT_APERTURE` | F249, F277 | the second title | low |
| DMA_SYNC (exp 0050) moved from TITLE2's row | `BC5_DIRECT_DMA_SYNC` | F104, F107 | the second title | low (the GFX ring only) |
| ds439 D: the same DMA wait on the compute rings | `BC5_DIRECT_DMA_SYNC_MEC` | ds439 | test_ds0439; title-free sync and sync7d | low: a few CP packets per buffer with a DMA_DATA |
| ds439 D2: the wait also before a label write and at a buffer's end | `BC5_DIRECT_DMA_SYNC_LABEL` | ds439 | test_ds0439; title-free gdssync | low |
| pc439: the system prefix also for dcbs that draw only in chained pieces | `BC5_DIRECT_PREFIX_CHAINS` | F901 | test_pc0439; the GPU read back the title's TF ring (11:28) | low: only dcbs with no top-level draw |
| cw439: the label-writer scan follows chains and calls | `BC5_DIRECT_CHAIN_WRITERS` | F899 | test_cw0439 | moderate: more waits are kept for the GPU in ring order |
| dm439: ATRAC9 DMC configs (sync 0x30) through vgmstream | `KYTY_BC5_AT9_DMC` | F892 | test_dm0439; the title's SIGFPE is gone | none: only 0x30 configs, which failed before |
| lw439: the host's completion bound as a word | `BC5_DIRECT_WAIT_MS` (100-60000, default 2000) | - | test_b2w0439 | none at 2000 |
| fw439: the umr watchdog's wait start per completion thread, the oldest wins | none | a watchdog bug | test_b2w0439; 11:28 | none: diagnosis path only |
| fp439: exp 0190's flat-aperture rewrite reaches every program however bound (SET_SH_REG, LOAD_SH_REG, LOAD_SH_REG_INDEX), at the top level and in every chained or called piece; the rewrite cache checks the program's identity and its rewritten sites | rides on `BC5_DIRECT_FLAT_APERTURE` (kSoft); `BC5_DIRECT_FLAT_APERTURE_PIECES=0` turns the new reach off | README item 50 (the ray-pass stall, F249's halt) | test_fp0439 (plants NOTABLE, NOCARRY, TOPONLY); test_fa0439 unchanged; runs fp2211 and fp2211b: both ray programs rewritten, no stall in 138 s | low: the rewrite is unchanged and only reaches more programs; cost is a packet-header walk per submit and an identity check per dispatch |

Two more are compiled in with no row (D26). They are words for the A/B, each on its own and both together, with GTT
and RssAnon next to the frame figures:

- `BC5_DIRECT_EAGER_GPU_WRITE=1` (mw439, the map rule): a direct view mapped with GPU write is imported whole.
  **Since 11-23 a kSoft row for every title** (the top session's rule; `=0` turns it off): on the console direct memory is
  physical and committed at allocation, so the GPU writes it from the map call on (README item 8); the lazy import is
  our shortcut. The first title function check before the bake, with its memory: item 12 found 10.4 GB of GPU-writable direct
  views there, all of which this pins; the second title is unchecked. The prot bit 0x20's meaning is TODO(verify).
- `BC5_DIRECT_DCC_PRESENT=2` (dc439 with F891's CB_SHADER_MASK 0xf): the DCC display surface is decompressed in place
  at its flip. **Since 11-23 a kSoft row for every title** (the top session's decision; `=0` turns it off). Why it can
  be universal: on the console the display engine scans a DCC flip surface out through its metadata; our present
  reads plain bytes, so the decompress at the flip is the same picture for any title, and it acts only when the
  registered display surface's colour block has DCC_ENABLE (a title that flips plain surfaces is untouched). The first title
  needs a function check with it on before the bake (does it flip DCC surfaces; the picture and the flip rate).

Out of the bake:

- Every probe and capture: pa, gp, lr, ia, ad, vg, un, rs, px, ms, gt, nf, cl, mi, lb and xq439.
- B, C, E, F and G.
- pw439, both modes. Mode 1 goes to exp 0444, with its det test test_pw0439.
- Anything learned.

## AGC end-of-pipe idents and the first title

The first title is an AGC title too, so the AGC idents are the console's behaviour for it as well. The A/B runs it with them on.

What the first title does with these interrupts today (the PS4 idents) is still to be read from its journal: which equeues it
registers, and with which idents. That is the first thing the A/B's journal is read for. If first-title regresses, the finding
to explain is which of its equeues listens for which ident.

## Files

The kit is in `k439/`, on this branch.

| file | what it does |
|---|---|
| `mkb2439.py` + `mkb2439_add.py` | the unit, videoOut.cpp and switch_defaults.hpp over bake 1's unit (`MKB2439_UNIT=3b28b024`) and header (`MKB2439_HDR=3f9ee1d9`), plus the tree's videoOut.cpp (6785425e) |
| `mkdm439b.py` | ajm.cpp (971b3d66) and atrac9_decoder.h (c2f248cb), from the shared tree, plus dm0439.hpp |
| `b2be439.py` + `b2-ib-be.diff` | bake 1's backend: direct.cpp 35fca52f, full_state.cpp 29f7dd6d, policy.cpp 107bb1b6 |
| `box439b2.sh` | the private build on the box, once bake 1 is the shared state |

To make the backend: copy bake 1's three files into a tree, run `patch -p1 < b2-ib-be.diff` (two hunks fail, on context
bake 1 removed), then `python b2be439.py <bake-1 backend> <tree>/backend`. The script places the two hunks itself.

The outputs of 2026-11-22 ~12:10 (laptop):

- new/: ajm.cpp 44e01c8b, atrac9_decoder.h 402d5d10, bc5LleAgc.cpp 37269d87 (with fp439 since 2026-11-22 ~17:50; 5406798d before, with exp 0438's r438h and kept438 since ~12:40; 119caba6 before that), fp0439.hpp 46f3eb75, cw0439.hpp 9f1436d3, dc0439.hpp c05cca6d,
  dm0439.hpp f2bf23e1, switch_defaults.hpp ba8077b4, videoOut.cpp 11f5e977
- be/: src/direct.cpp 662db3bf, src/full_state.cpp c49ae21f, src/policy.cpp ea26c088, include/bc5/ds0439.hpp c2b318af,
  include/bc5/ib_chain.hpp 11df8b8f (058b3267 before the comment's rename, 2026-11-22)

The header diff against bake 1: ten rows at kSoft's end (IB_CHAIN, IB_CHAIN_FLAT, AGC_EOP_IDENT, FLAT_APERTURE,
DMA_SYNC, DMA_SYNC_MEC, DMA_SYNC_LABEL, PREFIX_CHAINS, CHAIN_WRITERS, AT9_DMC). TITLE2's DMA_SYNC and FLAT_APERTURE
rows are gone. There is no BC5_T3.

## Det tests

On the laptop (VS clang++ x64):

- test_b2w0439: PASS. The plants LW and FW both FAIL.

On the box, with the kit's build, because they need the distrobox's g++, POSIX mmap or the backend's units:

| test | what it covers | plants |
|---|---|---|
| test_ds0439 / test_dsp0439 | D and D2 | NOWB, NOLABEL, NOEND |
| test_pc0439 | the prefix through chains | TOP |
| test_cw0439 | the writer scan | FIRST |
| test_fp0439 (with fa0439.hpp; also on the laptop, PASS) | the flat-aperture reach through pieces and tables | NOTABLE, NOCARRY, TOPONLY |
| test_fa0439 (laptop, PASS) | the rewrite itself, unchanged | BC5_FA439_PLANT_SKIP, BC5_FA439_PLANT_BREV |
| test_dm0439 | dmc_info | BC5_DM439_PLANT |
| a gate check of `KYTY_BC5_AT9_DMC=0` | the DMC off-word | to write |
| the backend's own ib_chain tests | the chain hunks | none |
| an ae439 off/on check | the end-of-pipe idents | to write |

## Before the build

- Check which units include atrac9_decoder.h. The class gains a member (m_dm439_tmp), so every unit that includes it must
  be rebuilt, not only ajm.cpp.
- Swap and undo scripts in exp 0442's pattern, and the lean word count before and after, come with the box build.
- Exp 0438's ride-alongs (the r438h sync-mode fix, the lean "kept" warning) still need their diff from exp 0444.

## The b439rs binaries

The b439rs binaries on the box (~/bc5-work/exp0439/k439/{normal,lean}) are not to be run. The top session stopped the
build at about 11:40. Its normal build had finished (5baf72f4) but the lean one had not. Rebuild before the next capture
run.
