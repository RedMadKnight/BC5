# 0290 — DISPATCH_INDIRECT stays off the compute ring until the CP's argument check is verified on the MEC

**Question.** F332's machine-down (17:47, exp 0265) was a BVH-build chain on compute ring comp_1.2.0
that never ended; its queue reset failed and the kernel fell to MODE1. On the GFX ring every
`DISPATCH_INDIRECT` with a known base gets the CP's argument check (F106, `bc5/indirect_check.hpp`:
`WRITE_DATA`, three `COND_WRITE`, `PFP_SYNC_ME`, `COND_EXEC`), which skips a garbage triple; on a compute
ring the check's `COND_WRITE`/`COND_EXEC` are unverified and `PFP_SYNC_ME` is left out (ADR 0009, ladder
step 5 still TODO). The exp 0160 note of 2026-10-24 proposed a policy refusal: a buffer holding a
`DISPATCH_INDIRECT` keeps off the compute ring until the MEC check is verified, so the BVH build runs on the
GFX ring exactly as exp 0053's clean runs did. Does that hold on the S6N route, where the machine-downs of
the fault-less class came (F316, F332)? Q19 (exp 0284) settled that the shared archive equals a fresh build
of main's `backend/`, so the change can be built privately and compared.

**Setup.**
- The diff (`patch_0290.diff`, on main's `backend/`): `backend/src/policy.cpp` — a `constexpr bool
  kMecIndirectCheckVerified = false` and, in `refusal_in()`, `if (op == 0x16 && !kMecIndirectCheckVerified)
  return "indirect dispatch (MEC check unverified)";` after the PARTIAL_TG_EN check (so the MEC form, 4 dwords,
  is refused as the GFX form already was through `is_graphics_only`); `backend/include/bc5/policy.hpp` — the
  comment of `compute_ring_refusal`; `backend/tests/policy_test.cpp` — the MEC-form case now expects a refusal
  whose message names the MEC check. What it does in the host: `job_ring()` asks
  `bc5::policy::compute_ring_refusal` per buffer and keeps a refused buffer on the GFX ring (the journal's
  "compute buffers kept on the GFX ring" count, `compute ring 0: … jobs so far`); nothing else changes.
  With the second title's `BC5_DIRECT_COMPUTE_RING=0` the per-frame BVH build chains (0x909939400 …,
  F332) and every other acb with an indirect dispatch move to the GFX ring; acbs without one stay on the
  compute ring (ADR 0009's start-screen gain was measured on those).
- The build (`build0290.sh`, on the box, CPU only, under the BOX-LOCK): main's `backend/` copied from the box's
  checkout `~/src/bc5` into `~/bc5-work/exp0290/src/backend` (rsync, the checkout untouched), the three files
  copied over it; a private build directory `~/bc5-work/exp0290/build` configured as exp 0284's twin (Ninja,
  Release, `-O3 -DNDEBUG`, clang++, `BC5_WITH_AMDGPU=ON`, `BC5_BUILD_TESTS=OFF` — Catch2 is a network fetch);
  target `bc5_backend`; then the shared normal build's link command (`ninja -t compdb -x`) with
  `libbc5_backend.a` swapped for the private archive and the output in `~/bc5-work/exp0290/kyty_emulator`
  (`relink0290.py`, written by the script). The shared archive `~/bc5-work/backend-ubuntu/libbc5_backend.a`,
  the shared builds, `~/src/KytyPlus` and exp 0284's twin directory are only read; the inputs' checksums go to
  `raw/build-inputs.txt`. The unit test is not run on the box (tests off); it runs wherever `backend/` builds
  with tests (`ctest` in a tests-on configuration).
- The test (`s6n0290.sh`, exp 0265's chain with this binary and no extra environment; `stream0290.sh` on the
  laptop for the kernel log and the journal extracts): the second title, `play-pkg.sh` with its defaults, S6N's
  route from exp 0196's saves through `ab-restore.sh`, up to 6 × 600 s, each run with its own save restore, the
  chain stopping at the first run that is not a pass (a new kernel amdgpu line, a TIMEOUT, a crash, saves not
  back). Attended: the supervisor's GO, the maintainer reachable for a power-cycle; the live saves are snapshot
  at the chain's start and checked after every run. The comparison is exp 0265 S1 (F332: the machine-down at
  about 2 min of this route), exp 0275/0279 (F336/F339), and 0260's catch runs: the same route, hangs and
  machine-downs counted, plus what the journal says moved ("compute buffers kept on the GFX ring" per run) and
  the frame rate (fps counter) against those runs.
- Expected if the proposal is right: no compute-ring timeout of the BVH chain (the chain is on the GFX ring,
  where a garbage triple is skipped by the check, F106); if the chain still hangs there, the hang is a shader
  loop on its data (F234's family), and the breadcrumbs of exp 0277 name the dispatch. Expected cost: the acbs
  with indirect dispatches lose the compute ring; the start screen (no such acb) keeps ADR 0009's gain.

**Result.** Prepared 2026-10-25 offline (diff, scripts, the unit test.s expectation changed). **Built on the
box 01:05:27–01:05:37 on the supervisor.s GO** (`build0290.sh`, lock taken and released): source `~/src/bc5` at
1853b14 with 0 local changes under `backend/`; the private archive `~/bc5-work/exp0290/build/libbc5_backend.a`
is 270,566 bytes, md5 825ae1d1 (the shared one 549892e8, 273,302 bytes, unchanged before and after); the
emulator `~/bc5-work/exp0290/kyty_emulator` (md5 56270e18, 166,537,776 bytes) is the shared normal build.s
objects as of 2026-10-24 23:19 (binary 893f8ab4, exp 0276.s ports integrated at 23:20, unchanged before and
after) linked against the private archive; the refusal string is in the binary. Context for the runs: TCP.s
exp 0281 chain ran 6 × 600 s on S6N.s route with RT off (exp 0280.s ten-program list) clean, no fault or
timeout, while RT on took the machine down at 2 and 2.5 min on that route — so the S6N chain here, RT on with
the refusal, is the arm that asks whether keeping the BVH chains off the compute ring is enough on its own.
Not run yet: the chain.s GO comes after the water and memory sessions. runs.


**Result — the S6N chain (01:42–01:45, on the supervisor's GO, the maintainer's approval in this session):**
- Preconditions: live saves c0ee58b92c0cadc2, snapshot `exp0290/saves-before-0142`; binary 56270e18
  (checked by content from `/proc/<pid>/exe`); environment `BC5_DIRECT_COMPUTE_RING=0 CROSS_RING_WAITS=all
  CHAIN=2 CS_PREFIX=1 RING_ORDER_WAITS=1 TIMEOUT_PROBE=1`, RT on (the launcher's defaults, the compaction
  skipped by `BC5_DIRECT_SKIP_PGM` as always); `stream0290.sh` on the laptop (`raw/kernel-stream.txt`,
  `raw/journal-stream.txt`).
- **The refusal works as written:** the journal's counter at the end reads "compute ring 0: 65,537 jobs so
  far, **19,094 compute buffers kept on the GFX ring**" (0 at the start) — the acbs with a `DISPATCH_INDIRECT`
  (the BVH chains) ran on the GFX ring, the others on the compute ring.
- **S1 stopped at 117 s, and the box stayed up.** At 01:44:40.016 nine `[gfxhub] page fault` lines, client
  TCP (0x8), `ring:40`, status 0x00541051 — the write-permission class of F336/F339 — at 0xffc08c648000 …
  0xffc08c6e8000 (a 0x20000 stride, an address with 0xffc0 in bits 47:32: a garbage pointer), on the title's
  render thread; at 01:44:42.015 `gfx_0.0.0` timeout (signaled 6165132, emitted 6165134), **ring reset
  succeeded**, "device wedged, but no recovery needed"; no compute-ring timeout, no MODE1. The chain stopped
  the emulator at the first kernel line (so the host's 2-s probe did not fire: 0 TIMEOUT, 0 probe lines);
  saves restored and verified c0ee58b92c0cadc2; lock released 01:44:51. The journal's last lines before the
  stop (t 103–113 s) are the second tree family's build dispatches in graphics buffers (0x909973700/3d00,
  0x909974200, 0x909977100, 0x90997a500, the F339 family). Coredump: `~/bc5-data/captures/devcoredump/
  20261025-014442-devcd4.txt` (gfx_0.0.0, IB1 base 0x101600000000, 0x3f0 dwords left; the faulty page in its
  registers is this run's).
- **The coredump.s CP position** (`20261025-014442-devcd4.txt`, taken at the gfx timeout, read offline): `CP_IB1_BASE`
  0x101600000000 with `CP_IB1_CMD_BUFSZ` 0x2ef0 (12,016 dwords) and `CP_IB1_BUFSZ` 0x3f0 left — the CP was 11,008 dwords
  into a 12,016-dword IB of the host.s chain area; `CP_IB2_BUFSZ` 0; `CP_PFP_HEADER_DUMP` 0xc0065800 (the PFP.s last
  header an `ACQUIRE_MEM`); `CP_STALLED_STAT2` 0x00018000, `CP_CPF_STATUS` 0xb4000263 (TODO(verify): the bit names,
  not decoded here); `GRBM_STATUS` 0xa0403028. The gfx ring.s dump (Rptr 0x71a) ends with the `INDIRECT_BUFFER`s
  0x101200000000 … 0x101500000000 (the last 0xe98 dwords) and a `RELEASE_MEM`; the 0x1016 entry the register names
  lies past the dumped read pointer. **Which title buffer and which dispatch the ring stood in is not determinable from
  this run:** the chain.s segment-to-buffer map is not journaled, the run was killed at the first kernel line (0 probe
  lines, 0 TIMEOUT), and the coredump holds the ring, not the IB. Exp 0277.s breadcrumbs are the tool for that; the
  journal.s last submissions (t 103–113 s) and the F339 signature of the faults name the second tree family.s
  builders as the work in flight. The faults (the MEC ME1 header dump holds the compute ring.s last packets:
  `RELEASE_MEM`, `WRITE_DATA`, a 0xc0ea1000 `NOP`) are the title.s render thread.s, `ring:40`, i.e. the GFX side.
- Against the references on this route: exp 0265 S1 (RT on, no refusal) went down at about 2 min with the
  compute chain hung and the compute queue's reset failed (F332); exp 0281 (RT off, the ten-program list)
  ran 6 × 600 s clean; here (RT on, the refusal) the same ~2-min point produced the F336/F339 stray writes
  and a GFX-ring timeout that the kernel recovered from.


**Result — runs S2–S6 (02:34–02:48, the supervisor's "GO now", his rule: a GFX-ring hang the kernel recovers
from counts as a pass; the chain stops on a failed reset, MODE1, a crash or saves not back; `s6n0290.sh` gained
that rule, a run-number start (`[first]`) and the exemption of the host's 2-s fence timeout, which is part of a
recovered hang — S2 was first scored a fail on its two TIMEOUT lines and the chain restarted at S3):**

| run | start | stop | kernel | host probe | result |
|---|---|---|---|---|---|
| S1 | 01:42 | 117 s | 9 TCP write faults (0xffc08c648000+, stride 0x20000, 0x00541051), gfx timeout, reset OK, coredump devcd4 | killed before the fence timeout: none | box up (chain stopped by the old rule) |
| S2 | 02:34 | 123 s | 1 SQC (data) fault at 0xb20407c00000 (0x00701430), gfx timeout, reset OK, devcd5 | acb 3,240 + dcb 33,275 dwords dumped; the dcb: 57 fast-launch draws (ES 0x11d0134500), dispatches of 0x11d03a3400/0x11d03a2000/0x11d039f000 | recovered |
| S3 | 02:38 | 116 s | no fault; gfx timeout, reset OK | acb 4,361 (the BVH chain: 0x909936c00 ×63, 0x909939900 ×35, 0x909939700 ×35 — on the GFX ring now) + dcb 29,447 (28 fast-launch draws) | recovered, pass |
| S4 | 02:40 | 112 s | no fault; gfx timeout, reset OK, devcd6 | acb 4,361 (the chain) + dcb 29,685 (28 fast-launch draws) | recovered, pass |
| S5 | 02:43 | 112 s | no fault; gfx timeout, reset OK | acb 4,333 (the chain) + dcb 29,381 (28 fast-launch draws) | recovered, pass |
| S6 | 02:45 | 117 s | 2 TCP faults (0xb8c607000, 0x00541051), gfx timeout, reset OK | acb 4,603 (the chain) + dcb 3,020 (the one-draw buffer of F208) | recovered, pass |

Six runs, six GFX-ring hangs at 112–123 s (the route's ~2-minute point, where exp 0265 S1 went down),
six successful `gfx_0.0.0` ring resets, no compute-ring timeout, no failed reset, no MODE1, no crash, the live
saves verified c0ee58b92c0cadc2 after every run; lock released 02:48:23. What hung differs run to run: three
runs with no fault at all and the pair "BVH chain (now a GFX-ring job) + a graphics buffer of fast-launch draws"
— F208/F234's RT family —, two with the F336/F339 TCP write faults of the second tree family, one with an SQC
data fault; the common factor is RT on at that point of the route, which exp 0281 (RT off, 6 × 600 s clean)
removes. The private binary's cost in play was not measured (every run ended at ~2 min).

**What the probe dumps name, and what they cannot.** In S2–S6 the host.s 2-s fence timeout came before the
kernel.s reset, so the probe dumped the two timed-out jobs of each run (table above): in S3, S4 and S5 — the three
runs without any fault — the pair is the same, the per-frame BVH build chain (0x909939400 / 0x909936c00 /
0x909939700 / 0x909939900, ~4,300 dwords, a GFX-ring job because of the refusal) and a 29k-dword graphics buffer
with 28 fast-launch point draws of the ES 0x11d0134500 family (F208.s draw); in S6 the chain and F208.s one-draw
3,020-dword buffer; in S2 a 33k-dword graphics buffer of 57 fast-launch draws and 0x11d03a… dispatches plus a
3,240-dword acb. The dumps say which *jobs* did not finish, not which packet the CP stood in: the probe.s "ran"
marks are the filter.s (see 0273.s correction), the GFX ring was running host chain IBs whose segment-to-buffer map
is not journaled, and the two coredumps of this chain (devcd5 for S2, devcd6 for the faultless S4) give the CP.s
position inside such a chain IB (as S1.s devcd4 did) without naming the title.s packet. So the dispatch the ring
stood in stays unnamed here; the faultless S4 coredump is the one to decode once the chain.s segment map or exp
0277.s breadcrumbs are in a build. What the runs do say: with the refusal the hang of this route is a GFX-ring
hang of RT-on work — the chain or the fast-launch draws in three runs, the second family.s stray writes in two —
and it ends in a ring reset the kernel completes.

**Verdict.** Passed for its question. Keeping every `DISPATCH_INDIRECT` off the compute ring until the CP's
argument check is verified on the MEC turns this route's machine-down (F332: a compute-queue hang whose reset
failed, MODE1, VRAM lost) into a GFX-ring hang the kernel recovers from, six times out of six, with the BVH
chains running as GFX-ring jobs where the F106 check is verified. It does not remove the ~2-minute failure
itself — that is RT-on work (the traversals' loop, F234, and the second family's stray writes, F339), and RT
off (0280/0281) avoids it. Recommended for integration as a safety net in its own right for RT-on play: a
frozen picture and a 2-s ring reset instead of a downed machine; six lines of backend policy behind a flag
that flips once ADR 0009's step 5 verifies the MEC check; no effect with the compute ring off or on buffers
without indirect dispatches; the open cost is the 29 % of compute-ring jobs moved back to the GFX ring (an
fps A/B on the start screen and the route). The unit test's new expectation (`policy_test.cpp`) runs where
`backend/` builds with tests on. Raw: `~/bc5-work/exp0290/raw/` (S1–S6 start/end/dmesg/probe/journal
extracts, the chain outputs), the probe's dumps in `~/bc5-data/captures/play-20261025-0{142,234,238,240,243,245}/gc/`,
coredumps devcd4–6, and on the laptop the kernel and journal streams of each chain.
