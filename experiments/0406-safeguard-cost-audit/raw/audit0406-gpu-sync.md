# Audit 0406: GPU-direct-path safeguards (sync, waits, flushes, prefixes, copies, checks)

Laptop only, read-only. Repo `bc5-0401` @ 19f9d1df (branch exp/0401-mesa-preamble-switches). Sources: `docs/HANDOFF.md`
(F-rows), `backend/kytyplus-patches/0001-bc5-lle-agc.patch` (= main's bc5LleAgc.cpp; line numbers below are patch
lines, prefixed P:), `backend/src/direct.cpp`, the 0401 mk*.py edit scripts, exp 0352/0367 READMEs, and
`Documents/ChatGPT/BC5/coordination/switch-removal-2-20261102.md`. The current shortcut (`shortcut0401.sh cpacb`,
commit 24fccd38) runs series e8 (dc7fb4e0) with e6's words minus FL_CRUMBS, plus ZERO_SKIP and JOURNAL_QUIET.

## Three facts that change the picture

1. **Ten of the listed launcher switches no longer exist as switches.** Switch-removal pass 2 (F812, patch 728f2a77,
   shared 4d2b1b1d) folded RINGS, REOPEN, GDS_ALL, GDS_SHADOW, ASYNC, RING_ASYNC, MAX_IN_FLIGHT (constant 24, P:33750),
   PIECES_DRY, PIECES_FULL, RING_ORDER_WAITS and the default-on HOLD_TAIL. `git grep` finds no parser for any of them in
   backend/ or the patch. Setting or unsetting them in bc5-run.env does nothing. Bringing old behaviour back needs code.
2. **One ring (COMPUTE_RING=-1, F412/F416) makes the two-ring machinery dead code, so it costs nothing.**
   - `two_rings` needs `compute_ring_env() >= 0` (P:31587), so TWO_RING_WAIT_MS (P:31621) and the HOLD_TAIL hold path
     (P:31593-31615) never run. F312 already says the hold acts only with a compute ring.
   - `acb_ring()` returns kGfxRing when the ring is < 0 (P:30266-30267), so every pending label write is on ring -1, and
     `ring_will_satisfy`'s cross-ring test (P:31324) never fires. CROSS_RING_WAITS=all is a no-op.
   - RING_DEPS=dcb adds a GFX job's dependency on `last_seq_comp[k]` (direct.cpp:1579-1589), which stays 0 with no
     compute job, so n = 0 and nothing is added.
   - So none of these is a cost to remove. They matter only as traps if COMPUTE_RING ever changes.
3. **The direct path's CPU does not set the frame rate.** F482: at the fight the render thread waits for title code.
   F483 (exp 0367): taking ~80 % of `emit_prefix` (~11-15 ms/s of render-thread CPU) off gave 33.8 against 33.6 flips/s,
   inside the noise. CPU-only removals should be expected to give ~0 fps. The GPU-side items carry the gain:
   - the CP check, 0.8 ms of GPU a frame (F439);
   - the full prefix, ~1,150 dwords per drawing dcb (45.0 → 43.9 fps in F204's menu run);
   - FL_SERIAL, ~3 % (e8), already off.

**=0 versus unset.** F767 (fab8660d, an ancestor of 029e0d6b, so in the shared archive) moved GPU_CHECK_PRODUCT,
HOST_INDIRECT, PIECES_NO_CLEAR, INDEX_BASE_DUP, NO_CARRY, BO_JOURNAL and ARGS_HISTOGRAM to `bc5::env_on`, so `=0` is off
for them. The coordinator's switch-history REPORT (10-30) predates F767 on those seven. Still presence-only, where `=0`
is ON: SHADOW_LABELS (direct.cpp:507), GPU_CHECK (P:34043), DMA_SYNC (P:33931), REMEMBER_UNMAPPED (P:33778) and
MEC_INDIRECT (P:34008). Value traps:
- COMPUTE_RING=0 is compute ring 0, the two-ring setup (`atoi`, P:30259), not "off";
- RING_DEPS=0 means `both` (P:30593-30598);
- CROSS_RING_WAITS=0 means `compute` (P:31283-31286);
- SOFT_WAIT_MS=0 is the old 2-s soft-CP deadline (P:33151), F415's 22-s hold;
- INDIRECT_DRAWS=0 still lets DRAW_INDIRECT through and drops only the multi-draw packets (P:33968-33971).
The 0401/0405 switches (CP_COHER_START_DELAY, ACB_*, TABLE_CATCHER, FL_*, R3_*) all use `env_on`, so `=0` is off.

## Ranked list (likely gain × low risk)

| # | Item | Kind | Guards against / origin | Evidence it is needed | Overlap | Cost | Verdict, restore value |
|---|---|---|---|---|---|---|---|
| 1 | `GPU_CHECK_PRODUCT=1` (staircase half of the CP check) | fix attempt, behaves as a filter | F403 runaway grids (exp 0341, F414) | F416: as built it refuses only (y or z > 1) with x > 2^16, so F403's 818×820×819 passes; F403 recurred with it on (F416 R2, F813, e8c2/e8c4). Has it ever refused a dispatch in play? Not found. F415's clean 46-min play had both guards on together, never separated. | none | 44 of the check's 88 dwords and one of its two PFP_SYNC_MEs (exp 0352 README:11-15). Estimate ~0.4 of F439's 0.8 ms GPU a frame, ~1-1.3 % flips. | **Drop candidate, medium-low confidence**: an A/B with RT on. A reading of what it refused needs a count; the 0341 journals have one. It is an F414/F415 RT guard, so not without that A/B. Off: `=0` or unset (env_on, F767). |
| 2 | `ACB_INHERIT=journal` | **pure catcher** | exp 0403's question: does an acb inherit another queue's program? | 0 `acb inherit` lines in r5, r6, rA, rB, rC, rp0 and rp1, and in the e2 play (cap0401-notes.md:47-60; README:95) | none | ring thread: `inherit_scan` plus a `full_state::Tracker::apply` of every acb part under `g_inh_mutex`, a map node per bound program, a census of every ring slice (mkunit0401.py:766-800). Not measured. Same order as `piece_check` per dcb (apply_level 10.4 % of render CPU, exp 0367); here on bc5-ring, which feeds the GPU (F174). | **Drop, high confidence**: unset or `=0` (P mkunit0401.py:712-716). |
| 3 | `TABLE_CATCHER=1` | **pure catcher** | F403 sub-class B: dims written after submit? (exp 0402 item 4) | Gave one reading: at e8's F403 timeouts, 24 of 256 slots changed by small float steps (hang1954-0401.md:816). The question is open. | none | Per job, FNV-hashes up to 256 slots of up to 64 KiB at submit (in `submit_now`'s walk, on the submitting thread) and again at completion on bc5-cq (mkunit0401.py:228-300). ~4,000 sampled journal lines a route; 578k changes counted in a 155-s play (README:95). Not measured. | **Keep only while F403-B is being chased; otherwise drop.** Medium confidence. Off: unset or `=0`. The quiet journal keeps its timeout lines (cap0401-notes.md:186). |
| 4 | `R3_REWIND_CATCH`, `R3_DROP_CATCH` | **pure catchers**, soft CP only | exp 0405 G4 and G8 | G8 counted only opcode 0x4a (112,152) and never 0x20 (README:327) | none | one table lookup per soft-CP packet, plus a 10-s summary (gpu0405-notes.md:151; cap0401-notes.md) | **Drop, high confidence; gain ~0.** `=0` or unset. |
| 5 | `R3_WAIT_IDLE` | behaviour (blocks wait-idle ioctl 0xc0048117 until `g_cq_items` = 0) | exp 0405 G12 | F144: the second title never calls submit-done or wait-idle | none | 0 for this title; a frame-time cost for one that calls it (gpu0405-notes.md:254-258) | Keep (port policy: not title-gated); zero cost here. |
| 6 | `R3_SUBMIT_EOP_EVENT`, `_COND_WRITE`, `_MEMSEM_SIGNAL`, `_TS_100MHZ` | behaviour, soft CP and host events only; nothing new is submitted (gpu0405-notes.md:7) | exp 0405 G6, G11, G2, G14 | ports; no repro | none | negligible: a soft-CP replay or event per such ioctl or packet | Keep. |
| 7 | Launcher no-ops on one ring: `TWO_RING_WAIT_MS=4`, `CROSS_RING_WAITS=all`, `RING_DEPS=dcb`, plus folded HOLD_TAIL | dead code | two-ring races (F132, F180/F181, F312) | moot (fact 2) | covered by COMPUTE_RING=-1 | 0 (the `bc5-hold` thread idles) | **No gain from removal.** Switch-removal-2 lists them as "his decision", so leave them. Note the traps if COMPUTE_RING ≥ 0. |
| 8 | `SOFT_WAIT_MS=8` | bound (a relaxation) | F415's 22-s soft-CP hold (exp 0343, F433) | yes, F415 | none | saves time | Keep. The line equals the code default (P:33151); `=0` would restore the 2-s deadline. |
| 9 | Full-state prefix (`PREFIX_ALL` default `draws`), default-on | fix | F204: foreign context state from desktop RADV jobs on the one GFX ring; 0/88 flagged against 9-27 | yes (F204, 6 runs) | It also carries the TF ring and `VGT_HS_OFFCHIP_PARAM` (tf_ring_prefix, P:31153-31224, the F785 lake fix), the 0401 Mesa registers, and the compute SH registers (F679's protection for drawing dcbs) | GPU: ~1,150 dwords per drawing dcb; 43.9 against 45.0 fps (F204, run 690). CPU: `emit_prefix` 27.5 % of direct-path CPU (F482) plus a tracker copy per dcb, 5.6-5.9 µs (exp 0367). | **Keep the stream. Take C1** (`experiments/0367-direct-path-cpu/full_state-0367.diff`): byte-identical, zero risk, CPU only, no fps (F483). Do not move to `sx` (run 689: 45.0 fps, 0/88): it drops the offchip write and the compute restore. A delta prefix is a design task, high risk. Old behaviour: `PREFIX_ALL=0`. |
| 10 | `CP_COHER_START_DELAY=1` (0401) | fix candidate, unproven | Mesa preamble register | No A/B. The play 1 slowdown was confounded (README:27-29). Every later arm had it on, so there is no off arm. | Inference, not shown: if desktop RADV jobs write 0x20 in their preamble (ac_cmdbuf.c:60), the register already holds 0x20 and the switch is a no-op | 3 dwords per prefix; GPU effect unknown (TODO(verify)) | **Unknown.** A/B needs a reboot between arms (it latches, F780). Off: `=0`/unset, then reboot. |
| 11 | `GPU_CHECK=1` (base half) | fix | F32/F106: stale or absurd indirect counts keep the CP busy, a full reset (machine-down) | yes (F106; exp 0052: 2.4-2.6 M dispatches a run run now instead of dropped) | the host check P:34036 only for unknown bases | about half of F439's 0.8 ms (~0.4 ms GPU a frame, one PFP_SYNC_ME a dispatch); the batched form batched 0.27 % only (F438) | **Keep, high.** Unset to disable (presence; `=0` stays on). |
| 12 | `SHADOW_LABELS=1` | fix (lesson R41: a functional RT guard) | F360 stray stores over the title's label (F414) | the F415 RT-on play with it on; not isolated | none | ~10.5 shadowed labels a job (F415): one extra label write and a redirected wait each; not measured separately (F414 R2 RT off 36.6 against 36.9/38.6, noise) | **Keep.** Unset to disable (presence). |
| 13 | `HOST_INDIRECT=learn:1100000000` | fix | F419: a GFX-form dispatch without a SET_BASE runs at an inferred base, box-killer class | yes (F419, F433) | none | in the filter (0.94 ms prepare, F439) | Keep. Off: `=0` (F767). |
| 14 | `DMA_SYNC=1` | fix (a wait) | F107: the refit reads a half-copied tree | yes (runs 233-238 against hangs) | F41's IB-end CP_SYNC covers only the IB end | one zero-byte DMA_DATA CP_SYNC before the first dispatch after an unsynced copy; small | Keep, high. Unset to disable (presence). |
| 15 | `DMA_SNAPSHOT=4096` | fix (a copy) | F146/F172: the title rewrites CPU staging before the GPU reads it | yes (runs 507-513) | none | "no measurable cost" with one ring (F172: 40.9-42.7 against 40.2-41.3 fps); dcbs only | Keep. Off: `=0`. |
| 16 | `CS_PREFIX=1` | fix | F251/F321: a dcb dispatches before it sets a program, from foreign state | weak (F321: acted 33 times in 140 s; prevention unshown) | ACB_STATE_RESTORE covers a superset: any dispatching, non-prefixed dcb (mkunit0401.py:111-118, README:46). The CS prefix wins when both apply. | ~60 dwords per such dcb, rare | **Merge candidate** (fold into the restore), medium confidence, ~0 gain. Off: `=0`. |
| 17 | `ACB_STATE_RESTORE=1` | fix | F679: on one ring a dcb inherits an acb's USER_DATA_0 and faults (F443) | yes, on a forced position: 3/3 faults off, 3/3 clean on (F685) | The drawing dcbs' full prefix already restores compute registers; this adds only the non-drawing ones. It exists because of COMPUTE_RING=-1. | ~60 dwords per dispatching non-prefixed dcb | Keep, high. `=0` off. |
| 18 | `COMPUTE_RING=-1` | fix (removes a path) | F332: a compute-ring hang whose reset never came, a machine-down | F412/F416: one ring costs nothing with RT off | makes items 7 moot; makes items 16-17 necessary | gives up overlap: F178 two rings 32-34 → 41-42 fps (start screen); F97 4.3 ms of compute could run beside graphics | **Keep**: the biggest potential gain, the highest risk. Old: `=0` (two rings, needs CROSS_RING_WAITS=all, the hold, etc.). |
| 19 | `FL_SERIAL`, `FL_VGT_FLUSH`, `FL_CRUMBS` | fix candidates and catcher, not set | the 19:54 draw class | e8: 0/18 draw-class hangs either way | none | F2 ~3 % (e8: 32.6 against 33.6 flips/s over 8 pairs) | Leave off. Already 0 cost. |

## Always-on paths (no switch), same kind

- **F41 IB-end CP DMA wait**: a zero-byte DMA_DATA + CP_SYNC on every IB (Mesa's practice; run 89 machine-down without
  it). Negligible. Keep.
- **`piece_check`** for every cc, hib and dcb: a `full_state` apply, plus a whole-tracker copy (`t_fs_before`) in the
  default prefix mode (exp 0367). apply_level is 10.4 % of direct-path CPU (F482). Needed for items 9 and 17. C2 (no
  copy) was proven equivalent and is worth ~6 µs a dcb. Not built.
- **`submit_now` walk** (21.5 % of direct-path CPU, exp 0367): the host indirect sanity check (NOP over 4M vertices or
  64K groups, P:34000-34036), LOAD_SH_REG_INDEX table reads, the mec, catcher and inherit hooks, the forced mapping sync
  (REMEMBER_UNMAPPED trims it, F-run 372; memory side, other agent). CPU only.
- **Dry prefixes at unsatisfied game-thread waits** (folded PIECES_DRY/PIECES_FULL, P:31605, 31698): with ring order
  almost no split happens (F133). Small.
- **Indirect draw limits** inside GPU_CHECK (2^20 vertices, 64 instances; P:33975-33977): part of item 11.
- **In-flight cap 24** (P:33750-33752, a 50-µs sleep poll): F99 measured 24 and 48 alike. Keep.
- **Soft-CP replay** of every job after its fence (bc5-cq0/1): host-side labels and events. Core mechanism, off the
  render thread.
- **ib_split** (exp 0349, F427/F431): cuts only buffers over 0xf0000 dwords. No steady cost.
- **Heavy journal lines** from these items: TABLE_CATCHER (sampled; counts in the hundreds of thousands), the R3 summary
  every 10 s, and the tf-ring line every 65,536 prefixes. JOURNAL_QUIET handles the per-submission timing lines.

## Bottom line

- **Safe, now:** unset ACB_INHERIT (pure catcher, 0 hits), R3_REWIND_CATCH and R3_DROP_CATCH (answered), and
  TABLE_CATCHER once F403-B is not being chased. All CPU only, so expect ~0 fps but less ring and completion thread work
  and less journal.
- **The only GPU-side gain within reach:** GPU_CHECK_PRODUCT. It never caught F403 (F416) and is about half of the CP
  check's 0.8 ms (~1-1.3 % flips). It needs an RT-on A/B because it was one of F415's two guards (R41 caution).
- **Free CPU:** fold C1 (F483) at the next backend rebuild.
- **Everything else** is either needed (F106, F107, F172, F204, F419, F679 lines) or already costs 0 on one ring.
