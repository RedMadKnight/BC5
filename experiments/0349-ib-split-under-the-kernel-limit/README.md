# 0349 — a job's IB kept under the kernel's limit (the fix for F421)

Ordered by the top session on 2026-10-27 after experiment 0348: the real fix for the refused ~250,000-dword dcbs
(F421/F426) together with the carried-register commit of 0348 (F424), built privately, gated offline, run on the S6N
bench RT off and RT on, then offered as the desktop shortcut "BC5 emulator (test 0349)". Nothing shared is written
(D19). The title's dumps stay on the box and in the private folder; only counts, offsets and addresses are quoted.

**Question.** Does cutting an over-limit job into several IBs of one submit remove the refusal without changing any
packet decision, and does the title run on it unchanged (flips, no kernel line) RT off and RT on?

## Design note

**The two limits, with sources.**
- `amdgpu_cs` refuses an IB whose `ib_bytes / 4` exceeds `AMDGPU_GFX_SDMA_IB_PACKET_SIZE_MAX_DW` = 0xfffff for the
  GFX, compute and SDMA rings: `drivers/gpu/drm/amd/amdgpu/amdgpu_cs.c`, `amdgpu_cs_p2_ib`, torvalds/linux master
  62c457528529 (read 2026-10-27; the comment there: the emit_ib packet format's 20-bit size field). The refusal is
  -EINVAL before any BO is touched, which is why the four refusals of the day took 0.02 ms. Verified for the box: the OGC kernel tree at tag v7.2.9-ogc3 (github.com/OpenGamingCollective/linux, 97cfdbb4b314; the
  fc44 rpm 7.2.9-ogc3.1 is DXC-0/ogc-kernel-rpm's packaging of it) has the same check at line 400 of its `amdgpu_cs.c`, and the
  probe `raw/ib-probe.cpp` (NOP IBs on the GFX ring, `raw/ib-probe.out`, 20:26) ran 1,048,575 dwords and was refused -22
  before the GPU at 1,048,576, in an exactly sized BO and in one 1 MiB larger alike (262,143/262,144/262,145/300,000/524,288
  all ran). The limit is in dwords; the cut's default is 0xf0000 (983,040), a 6 % margin below it.
- One submit carries up to four IBs through libdrm: `/usr/include/libdrm/amdgpu.h` line 60 in the box's `ubuntu`
  distrobox, `AMDGPU_CS_MAX_IBS_PER_SUBMIT 4` (libdrm 2.4.134, F13). The ring itself takes more
  (`amdgpu_ring.c`, `amdgpu_ring_max_ibs`: 192 for GFX, 125 for compute, same commit), so libdrm is the binding
  limit: at most 4 × 0xfffff dwords per job.

**Why split and not chain.** The kernel runs the IBs of one job back to back from the ring, each through its own
INDIRECT_BUFFER at the IB1 level (`amdgpu_ib_schedule`, `gfx_v10_0_ring_emit_ib_gfx`), so the title's own nested
INDIRECT_BUFFERs inside the job stay IB2 exactly as today. RADV's chaining (Mesa 0866ae7,
`src/amd/vulkan/winsys/amdgpu/radv_amdgpu_cs.c` lines 293 and 435: the last packet of an IB replaced by an
INDIRECT_BUFFER with the chain bit) needs a trailing packet rewritten in every piece and a CP feature (`can_chain_ib2`
gates it for secondary buffers), i.e. inserted dwords and one more hardware fact to verify; the multi-IB submit needs
neither. Chaining stays the fallback if a job ever needs more than four pieces (none seen: the largest dcb of the day
was 264,505 title dwords).

**Where a cut may go.** `bc5/ib_split.hpp` (`backend/src/ib_split.cpp`, pure, no GPU): the executed IB is the image
`[0, padded)` in the job's scratch slot (prologue, the filtered main IB, epilogue, NOP padding to 8 dwords); a cut is a
packet boundary (type-3 and type-0 lengths from the header, every other type one dword) that is
- a multiple of 64 dwords from the image's start (256 bytes; the slot is page-aligned, so the IB's VA is 256-byte
  aligned, RADV's IB alignment), else of 8 dwords (the CP's 32-byte fetch chunk the host already pads to) when no
  64-aligned boundary lies in the window — counted as a fallback cut;
- outside every COND_EXEC range: a COND_EXEC (op 0x22, 5 dwords, gfx10 form) skips the next `count` dwords
  (`dword 4 & 0x3fff`, as `indirect_check` reads it); a cut strictly inside `(packet start, packet end + count)` would
  let the skip run into the next IB or leave a half range behind, so those boundaries are refused. The backend's own
  check staircases are COND_WRITE/COND_EXEC pairs and fall under the same rule.
Greedy: from each piece start the largest allowed boundary within `max_dw` dwords; the last piece ends at `padded`.
No dword is inserted, moved or rewritten, so every decision of the passes before it (filter, host_indirect, tracker,
cu_tables, shadow labels, indirect_check) is unchanged by construction; the flag, shadow-slot and timestamp
addresses are absolute VAs in the same slot and stay valid. A job that cannot be cut (a COND_EXEC range longer than
the limit, or more than four pieces) is refused by the host with rc -EINVAL and one stderr line — as the kernel would
have refused it, but journaled with the final size.

**The submit.** `Device::submit` cuts only when `padded > ib_max_dw` (default 0xfffff; `BC5_DIRECT_IB_MAX_DW`
lowers it, so the bench can exercise the cut on ordinary jobs) and fills up to four `amdgpu_cs_ib_info` entries at
`slot VA + off × 4`; `number_of_ibs` is the piece count. Journal: the first eight cut jobs and every 500th with their
pieces, COND_EXEC ranges and fallback cuts; any refusal with the final size, the title's size and the IB count
(0348's line). The carried register of 0346 is committed only after `amdgpu_cs_submit` returned 0 (0348, F424).

**Gates.** (1) Catch2 `[ib_split]`: one piece within the limit; aligned cuts on a plain stream; the 8-dword fallback
when no 64-aligned boundary exists; a cut never inside a COND_EXEC range; a range longer than the limit fails; more
pieces than allowed fails; the two constants. (2) The offline harness `raw/harness0349.cpp` (0346's harness plus
`--split <max> [--pieces <n>]`) over every private dump of the day: without `--split` its output must equal 0346's
harness output line for line; with `--split 16384 --pieces 64` the cut set must satisfy the rules above on every dump
(real streams with COND_EXEC ranges); with `--split 0xfffff` every dump is one piece. The refused 250,000-dword dcbs
themselves are not dumped (only timeouts are), so the real-size case is covered by the bench with
`BC5_DIRECT_IB_MAX_DW=65536` and by the Catch2 limits. (3) The box: build, Catch2, S6N RT off 600 s, S6N RT on
600 s, both with the cut forced at 65,536 dwords (every dcb above it cut), gpu-watch active, the kernel stream on the
laptop; then the shortcut with the default limit.

**Setup.** Box: kernel 7.2.9-ogc3.1, shared normal build ddfb9456, shared archive 44ba4435, play-pkg.sh 5b469087,
input.cfg 30dd586e (RT on), exp 0343's patched host unit e7cc2f60 and its `build0343.py`; this branch's `backend/`
copied to `~/bc5-work/exp0349/backend`; `build0349.sh` (private archive + Catch2 + 0343's unit compiled + the shared
link command with both swapped), `s6n0349.sh <saves-sum> <tag> 600 off|on` (from 0343's, switches
`BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8 BC5_DIRECT_IB_MAX_DW=65536`, a 0349 result
block), `mktest0349.pl` + `shortcut0349.sh`. Laptop: `raw/build-harness0349.cmd` (MSVC) and the private dumps.

**Result.**

- **Build** (box, 19:56–19:57): private archive from this branch (822c800's backend), Catch2 71 cases / 32,541
  assertions passed (7 `[ib_split]` cases, 129 assertions), exp 0343's unit compiled, relinked: `kyty_emulator`
  d82f17b0 (`raw/build0349.out` on the box; 5 warnings, 4 pre-existing + 0343's format one). Strings: the 0349 switch
  and split lines, the refusal line, 0346's switch, 0343's soft-cp line all present.
- **Offline gate** (`raw/harness-gate.txt`): over the 14 private dumps of the day the new harness's output equals 0346's
  line for line (0 differing lines per play); with `--split 16384 --pieces 64` and with `--split 0xfffff` the outputs
  equal the no-split output once the `split:` lines are removed (0 differing lines). At 16,384: 5 of 14 dumps cut, 55
  pieces, 9,153 COND_EXEC ranges honoured, 0 fallback cuts, no failure; at the kernel limit every dump is one piece
  (the largest final IB 359,208 dwords, 14:23's dcb).
- **R1 (S6N, RT off, 600 s, `BC5_DIRECT_IB_MAX_DW=65536`), 20:01:11 → MACHINE-DOWN at 20:03** (box back 20:03:28;
  `raw/R1-kernel-stream.txt`; devcd `~/bc5-data/captures/devcoredump/20261027-200258-devcd1.txt`; journal
  `~/bc5-data/captures/play-20261027-2001/gc/direct.log`; dumps `ib-timeout-00081929-dcb-108366.bin`,
  `ib-timeout-00081930-acb-4.bin`, copied to the private folder). Live saves cef7b7b07c758ecd before (the maintainer's
  plays changed them from dc9d4f25fc2d41ca); the run died with the box, so the after-comparison did not run.
  - **F427 — the multi-IB submit works on the hardware.** Three jobs over the forced limit were cut and ran: split #1
    95,072 dwords (from the title's 50,285) into 2 IBs [0 +65216] [65216 +29856] with 1,041 COND_EXEC ranges; #2 66,768
    (46,527) into 2; #3 202,264 (83,163) into 4 IBs [0 +64768] [64768 +65344] [130112 +64960] [195072 +7192] with 2,714
    ranges; 0 fallback cuts. The crashing job #81929 (108,366 → 183,816 dwords) was cut into 3 IBs [0 +65216]
    [65216 +65280] [130496 +53320]; the devcd lists exactly those three IBs (IB #0 0x100900000000 65,216 dw, IB #1
    0x10090003fb00 65,280 dw, IB #2 0x10090007f700 53,320 dw) and `CP_IB1_CMD_BUFSZ` 0xfec0 = 65,216: the CP ran the
    pieces as IB1s back to back.
  - **F428 — the refusal that preceded the crash was this experiment's own, an artifact of the forced limit.** At
    t 102.011 s the S6N route's big dcb #81925, 204,940 title dwords, grew to **238,192** dwords (×1.16) and the greedy
    cut failed ("no aligned packet boundary outside the 789 COND_EXEC ranges at 157632": after three pieces of ≤65,536
    the rest, 80,560 dwords, did not fit the fourth; the message names the wrong reason — the piece count — to fix);
    the host refused it with rc -22 in 0.00 ms. At the real limit it is one IB. Note the growth: ×1.16 here, ×2.44
    (13:27) and ×3.36 (14:23) for dispatch-heavy dcbs — a 264,505-dword dcb reaches the kernel's 0xfffff only at ×4, so
    **F421's attribution of the day's four kernel refusals to the size limit is unproven**; the 0348 refusal line (the
    final size on any kernel refusal) is in this build and will settle it on the next refusal at the default limit.
  - **F429 — F416 corrected: hang 1 of 12:37 is this class.** 0342's R2 had its 206,438-dword dcb #76002 refused at
    t 99.698 s and the hang at ~106 s; today's R1 refused the same route's big dcb at t 102.011 s and faulted at
    t 102.1 s. The S6N route reaches that frame at ~100 s on every run: the "route to a frame over the limit" the
    order asked for is S6N itself, with the big dcb at ~100 s (205,000–207,000 title dwords, RT off or on).
  - **F430 — the fault, and F424 did not prevent it.** The next dcb #81929 carries a chain of 3,529 GFX-form
    `DISPATCH_INDIRECT` from dword 80 to 48,278 before its first `SET_BASE` (48315, compute type 0x118c9b6f00), offsets
    0x11fb80 … 0xd23c6b80; the dump ends with the zero pair (108245/108249) like every small dcb. The fault page
    0xccc55000 (CPF read, permission) is the dispatch at title dword 34517, offset 0xccc55f80 under a hardware base of
    0; `CP_IB1_BUFSZ` 0x63a0 puts the PFP 39,712 dwords into piece 0, inside the chain. The devcd's piece 0 holds
    3,529 × (PFP_SYNC_ME, DISPATCH_INDIRECT) and no inserted `SET_BASE`: the host left the chain, i.e. its carried
    register was non-zero while the hardware's was 0, although the refused dcb was not committed (F424) and the gfx
    jobs between were none (#81921–#81928 are compute-ring acbs, q0). No `SET_BASE` of the dump lies inside a
    COND_EXEC range (5 ranges). `TODO(verify)`: where the host's non-zero value came from (the previous dcb #81920,
    34,497 dwords, is not dumped; the play log holds no 0346 rewrite or drop line for the whole run), or whether the
    CP's register is reset by something the host does not model (an acb on the compute ring, the IB1 boundary).
  - Also: the offline harness over #81929 with nothing carried → 3,529 "never set" left, 312,851 dwords; with
    `--zeroed` → 3,529 rewrites to pages 0x110011f000 … 0x11d23c6000, 0 dropped, 644,577 dwords (507,979 inserted: the
    check's 88 dwords per dispatch would push a 265,000-dword dcb of this density past 0xfffff — the size hypothesis
    is not excluded either); with `--split 65536` the greedy cut fails at 195,072 as on the box.
- **The kernel's limit, measured (F431).** `raw/ib-probe.cpp` (NOP IBs of 0xffff1000, one IB per submit, the GFX ring,
  a fresh process; `raw/ib-probe.out`, 20:26): 200,000 / 262,143 / 262,144 / 262,145 / 300,000 / 524,288 / 1,048,575
  dwords ran (fence signaled); 1,048,576 refused with rc -22 before the GPU; the same in a BO 1 MiB larger than the
  IB. The limit is exactly 0xfffff dwords, as in the OGC kernel's source (v7.2.9-ogc3, `amdgpu_cs.c` line 400). The
  refused dcbs of the day reach it because RT on makes the passes grow a dcb ×5–6 (R2 below: 146,852 → 772,040;
  226,239 → 969,320; the CP check's 88 dwords per indirect dispatch on the BVH build lists that RT off drops), so
  the maintainer's 252,101–264,505-dword dcbs land above 1,048,575: F421 stands, the growth was the missing factor
  (the first R1's ×1.16 was an RT-off frame, 7,270 of its dispatches dropped as "build list").
- **Rebuild** (20:35–20:36): `kyty_emulator` fadeebd9 (archive from d9d301b's backend, 0343's unit), Catch2 71 cases
  / 32,545 assertions passed (7 `[ib_split]`, 133). The cut's default is 0xf0000 = 983,040 dwords; the greedy fit
  retries with a lowered limit before refusing and names the reason; the harness gate was rerun: 0 differing lines on
  every dump against the previous build and with/without the cut (`raw/harness-gate-65536-1423.txt`: the 359,208-dword
  final IB of 14:23's dcb now refused at 65,536 as "more pieces would be needed", correctly).
- **R1b (S6N, RT off, 600 s, the cut forced at 120,000), 20:40:53 → pass:** no kernel line, no TIMEOUT, no crash line,
  live saves unchanged, 26.2 flips/s over the last 100 s (36.1–36.3 in 0346's R1v3b and 0343's R1: a drop, cause
  not analysed — the lost big frame below is the suspect). Split #1: 205,304 dwords (from 84,443) into 2 IBs
  [0 +119488] [119488 +85816], 2,754 COND_EXEC ranges. The route's big frame at 102 s grew to **589,792** dwords this
  time (from 202,755; the first R1's was 238,192 from 204,940 — the frame's content varies), more than four pieces
  of 120,000 hold, so the host refused it ("more pieces would be needed", 8,797 COND_EXEC ranges) — and the title
  went on: a lost frame is not always the chain fault of F430.
- **R2 (S6N, RT on, 600 s, the cut forced at 400,000 so the big frame cuts and still fits four pieces), 20:53:31
  → pass:** 36.2 flips/s over 596 s (0346's R2v3b: 36.5), no kernel line, no TIMEOUT, no crash line, live saves
  unchanged; 4 jobs cut into 9 IBs, 0 refused, 0 fallback cuts: 772,040 dwords (from 146,852) into [0 +400000]
  [400000 +372040] with 14,216 COND_EXEC ranges; 402,400 (141,525) into 2; 969,320 (226,239) into
  [0 +399808] [399808 +399680] [799488 +169832] with 16,888 ranges; 778,088 (129,516) into 2. The title ran through
  all of them (`raw/R2-kernel-stream.txt`).

- **R3 (S6N, RT on, 600 s, the cut at its default 983,040), 21:04:58 → pass:** 36.5 flips/s over 596 s, no kernel
  line, no TIMEOUT, no crash line, no refusal, live saves unchanged; no job of this run needed a cut (the route's
  biggest RT-on frame reached 969,320 dwords in R2, 14,000 under the default), so the default-limit build behaves as
  0346's R2v3b did (`raw/R3-kernel-stream.txt`).
- **The shortcut** (21:16): `~/Pulpit/BC5 emulator (test 0349).desktop`, Exec `distrobox enter ubuntu -- env
  BC5_EMU=~/bc5-work/exp0349/kyty_emulator ~/bc5-work/exp0349/play-pkg-0349t.sh`; the launcher (md5 370343d4, from
  play-pkg.sh 5b469087 by `mktest0349.pl`) logs each start to `~/bc5-work/exp0349/play/play-<ts>.log` and exports
  `BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8`; the cut runs at its default. RT on comes from
  the shared input.cfg. The 0343+0346 and 0346 shortcuts stay. Nothing shared was written. The box scripts are in
  `raw/` (`build0349.sh`, `mk-s6n0349.pl`, `mktest0349.pl`, `shortcut0349.sh`).

**Verdict.** Passed. The kernel's IB limit is 0xfffff dwords (probe and source, F431); RT on grows the title's big
dcbs ×5–6 past it, which is the day's four refusals (F421 confirmed) and, through the lost frame, the three
machine-downs and 12:37's hang 1 (F429). The cut keeps every job under the limit with no packet decision changed
(gate), runs on the hardware (R1b, R2: 4 jobs as 9 IBs, R3) at 0346's flip rate RT on, and the test shortcut is up.
Open: R1b's 26.2 flips/s RT off after its refused frame (the forced 120,000 was below that frame's 589,792); the F430
mystery (the host's register non-zero where the hardware's was 0 after a lost frame); the lost-frame safety net stays
a later, offline-gated step. The first R1's machine-down (F428) was caused by the forced 65,536 limit, not by the cut.

**The maintainer's RT-on play (2026-10-28 07:24–07:42; "gram", then "Działa świetnie").** Top session; streams from the laptop in `raw/maintainer-test/` (kernel, GPU journal, play log, samples once a minute). Shortcut "BC5 emulator (test 0349)", binary fadeebd9, RT on and Polish from the shared `input.cfg`, gpu-watch f54e6e5c active, live saves cef7b7b07c758ecd before.
- One start, 07:24:46 → exit 0 at 07:42:45: 42,103 flips over 1,073 s = **39.2 flips/s** (per-second median 39.9, 10th percentile 28.5), no crash line, no TIMEOUT, no kernel line from amdgpu (`sudo dmesg` after the play holds only the boot lines of 20:03), no refusal.
- **Split #1**: a job of **1,442,872 dwords from the title's 244,565** (×5.9) was cut into 2 IBs [0 +982,848] [982,848 +460,024] with 27,234 COND_EXEC ranges, 0 fallback cuts. Without the cut the kernel would have refused it, as it did the four big dcbs of 2026-10-27 (F421).
- 0346: 32.8 M dispatches left with the register non-zero, 0 rewritten, 0 dropped; 0343: no soft-cp or slow-post line. 76 `cpu-wait … GIVEN UP after ~16 ms` lines, as in earlier plays.
- Memory: MemAvailable 565–860 MB through the game, swap up to 911 MB, GTT up to 12,253 MB; GPU edge 59–76 °C, CPU Tctl 71–78 °C.
- The maintainer: "Działa świetnie. Byłem przy wodzie przy innym miejscu. Piękne odbicia i brak patchu. Woda czysta" — reflections fine and the water clean at another lake spot (one observation; F418's bench spot not visited).
- Live saves after: 3f8412c4884ddf14 (the game saved during the play).
