# 0436 — submit unlock

**Question.** Does taking the kernel submit (`DRM_IOCTL_AMDGPU_CS`, `amdgpu_cs_submit`) out of the device mutex, as
exp 0432's note 8 designed, raise the second title's frame rate on the BC-250, without breaking the order and
bookkeeping guarantees of exp 0430's hang fix (F859) and ud434's import pass (F862)?

## Background

Exp 0432 result 6: the device mutex (`g_dev_mutex` in the host, `Impl::mutex` in the backend) is held 17-18 ms of
every ~30 ms frame, and the two submitting threads (the game thread on the GFX ring, `bc5-ring` on the compute rings)
wait for each other: 7.6 ms a frame of waits in shared d432S7. Note 7: the game thread waits 3.0-3.4 ms a frame; the
kernel call is 0.13-0.15 ms of an acb's 0.36 ms hold and 0.23 ms of a dcb chain's 1.0-1.2 ms. Note 8's estimate: only the
part of the wait spent behind the other thread's kernel call goes, about 1.2-1.4 ms a frame for the game thread
(4-5 %). Note 9: with the chain hold on (the shared default) the game thread's own kernel calls are 2.0 ms a frame; this
change does not shorten them, it only lets the other thread prepare meanwhile.

## The candidate (one switch: `BC5_DIRECT_SUBMIT_UNLOCK`, tag su436)

Checked against patch `8986853b` (the shared builds since 2026-11-19 15:27) and main's backend (`direct.cpp`
`52f74d0e`, the shared archive `51db2c91`'s source).

What the kernel call relied on that the two mutexes gave it, and what gives it now (note 8's table, as built):

| relied on | as built |
|---|---|
| the order of jobs on one ring: a job is prepared against the state the ring's previous job left (slot rotation of the ring's pool, the state-stack tracker, the host-indirect register `hi_reg` for the GFX ring) | a lock per ring in the host (`g_su436_ring_mu[5]`: GFX, compute 0-3), taken in `submit_now` **before** `g_dev_mutex` and held to the end of `submit_now`. The same ring's next job cannot be prepared before this one is in the kernel and recorded. Lock order: ring, `g_dev_mutex`, the backend's `flight_mu`, the backend's `mutex`. |
| the mappings a prepared job reads are still there when the kernel takes it (item D: the kernel orders a page-table clear only behind jobs it already has) | the backend's `flight_mu` (a `std::shared_mutex`): held shared by a split job from before its prepare to the end of its bookkeeping; taken exclusively, before `mutex`, by every removal (`unmap_userptr`, `unmap_shared`, `unmap_aliases`, `free_shared`, `~Device`). Adding mappings takes nothing new. A slot resize frees only the job's own slot, which no other job's IB uses; a BO list keeps its BOs referenced in the kernel. |
| the kept BO list's handle (`full_list`, replaced and destroyed by another job's prepare when the BO set changed) | a use count per kept list (`list_users`); a list replaced while a job is in its kernel call is destroyed by its last user. |
| the slot's records after the call (`slot_seq`, `last_seq*`, the DMA snapshot spans, `hi_reg`) | the backend's `mutex` taken again after the call; the job's slot and snapshot spans are kept in locals (`impl_->cur` and `snap_job` move on with another ring's job); `hi_reg` is written back only by a GFX job (a compute job never changes it, and must not write back a value read before a GFX job's call). |

What stays as it was, checked one by one:
- **ud434 / k1f412 pass, the syncs, F10's look, F2/F4's fence dependency**: all run before the backend's prepare, under
  `g_dev_mutex` (k1f412_pass and sync in `submit_now`; `ho430::at_wait` in `submit_split`, before `submit_now`; F4's
  `t_next_deps` is the calling thread's and is consumed in the prepare). Unchanged.
- **The label/fence bookkeeping** (`register_label_writes`, `ho430::job_submitted`, `chain_mark_executed`, `cq_push`,
  the EFAULT retry): after the call, with `g_dev_mutex` taken again and the ring lock still held, so per ring in the
  same order as the kernel calls.
- **F10/F16/F18's "writer in flight"**: a chain's `f10_flight` is cleared in `chain_submit` after `submit_now` returns,
  as before, so a waiter sees the writer in flight through the whole unlocked window; F16's phase stays 3.
- **Deadlocks**: a thread now waits for a ring lock exactly where it waited for `g_dev_mutex` before, and the ring's
  holder is the thread that held `g_dev_mutex` there before; the holder needs no host lock while in the kernel call
  (the backend's `mutex` only). `wait_jobs` (`Device::wait_idle`, fences) and `drain` (queue counts) do not wait for a
  job that is not queued yet, so a drain under `g_dev_mutex` never waits for a job blocked on the re-lock.
- **Off** (`BC5_DIRECT_SUBMIT_UNLOCK=0`): the old one-call `Device::submit` under both mutexes. The backend changes that
  run anyway (locals for the slot and spans, `hi_reg` written only by GFX jobs, `list_drop`, an uncontended exclusive
  `flight_mu` in the four removal calls) compute the same values as before when nothing runs outside the lock.

The test build has the switch **on unless `=0`** (unset = on), so the candidate's arm is its binary alone and no
launcher word can be lost on the way (LESSONS R66). A second cheap cost in the same path was looked for (note 9's
items 1 and 2) and not taken: with the chain hold on, the buffer-list create/destroy is 0.01 ms a frame (note 9, K1),
and the sync's fixed part is already items W/M's subject.

Files: `mkbe436.py` (the backend edit, applied to main's `direct.cpp`), `be/direct.cpp` (`eacf8d2a`),
`be/direct.hpp` (`9256f3b9`, written by hand: a `submit(..., before_call)` overload and a private `submit_impl`),
`mkhost436.py` (the host edit), `bc5LleAgc.cpp` (`57ce0f37`: patch `8986853b`'s unit `6f4bf71a` + `mkhost436.py`).
Box kit: `box0436.sh` (claim, build, release), `build0436.py` (exp 0433's `build0433.py`, unchanged), `chain0436.sh`
(the A/B), `smoke0436.sh` (the first title).

## Setup

- **Box.** BC-250, kernel 7.3.3-ogc1.1.fc45 (read 2026-11-20 00:35), boot `40a8312e` (up since 2026-11-18 15:39).
  Mesa and libdrm were not re-read here (F829's 26.2.6 / 2.4.134 last recorded). RT on: `RayTracing.TITLE2=on` in
  `~/bc5-work/menu/titles/TITLE2/input.cfg` (exp 0435's per-title file) and in the shared `input.cfg`.
- **The boot was not clean (R60 not met).** dmesg holds old amdgpu ring timeouts and resets from 11-19 ~14:06-14:14
  (dmesg 80821-81311 s; exp 0434's first-title faults, F862; all recovered, e.g. "Ring comp_1.1.1 reset succeeded"): 51
  lines by a broad grep, 50 by the runners' pattern. R60 asks for a reboot before the next GPU run; it was not possible
  from here: `sudo -n systemctl reboot` needs a password (sudoers holds only the read-only commands) and
  `systemctl reboot` was refused by polkit ("requires interactive authentication"). The top session's ruling (00:5x): run
  on this boot; both arms alternate on the same boot, so they see the same GPU state. The route runner's "no reset since
  boot" gate became a baseline gate in a private copy (`mkrun0436.py` → `run0430f-0436.sh` from exp 0430's `run0430f.sh`
  9d53dccc, which is not edited): the chain counts the lines at its start (50) and stops, and the runner refuses, if the
  count grows. A hang on this boot is data on a once-reset GPU, and that run is repeated after the maintainer's reboot
  before any conclusion.
- **Build** (step A, 2026-11-20 00:37, `box0436.sh`, CPU only, nice 19, the top session's GO). The shared archive
  `51db2c91` is exp 0433's copy of exp 0432's `6eac453e` with `policy.cpp.o` replaced; its `direct.cpp.o` comes from
  `~/bc5-work/exp0432/be-src` (main's `direct.cpp` `52f74d0e`, `direct.hpp` `24988c4e`) built in `exp0432/be-build`.
  The box's `~/src/bc5` is an old modified checkout (`d0c2668`) and was not used. Reference first: main's `direct.cpp`
  compiled with that build's own command gave the shared archive's member byte for byte (`1b9304e7`). Then the kit's
  `be/direct.cpp` into a copy of `51db2c91` (`ar r`): **archive `d6638808`**; the kit's `bc5LleAgc.cpp` with the shared
  normal and lean builds' own commands, linked with it: **normal `d55e4cbd`, lean `bbebc371`**. 0 errors; warnings 7
  (normal) and 8 (lean), every one on an old line of the unit or a KytyPlus header. The shared builds, archive and tree
  unit read the same md5s after the build. Log: `raw/build-20261120.txt`.
- **Runs** (step B, `chain0436.sh` under the user manager, `systemd-run --user`): arms S = shared normal `99f2a567`,
  C = candidate normal `d55e4cbd` (switch on by default in the test build), alternating S C S C S C. Both arms: way 2's
  five words, `BC5_DIRECT_TIMEOUT_PROBE=1`, the words file `exp0413/n/words0413nz.txt`, no fuse, no memory watchdog.
  - scene: exp 0432's `run0432f.sh` (`2d11fd6b`), his 09:46 scene (`~/bc5-data/saves/TITLE2-20261117-0946-play`,
    slot 4, no input after the load), G+300 s; tags `u436sS<k>` / `u436sC<k>`.
  - route: `run0430f-0436.sh`, slot 4 of exp 0425's named snapshot, his 14:50 fight record at G, then exp 0379's walk
    to G+1500 s, JobArenaFix off; tags `u436rS<k>` / `u436rC<k>`.
  - flips/s and the seconds with a gap over 50 / 100 ms from the runner's fps lines, from G+10 s.
  - per run: the running emulator's `/proc/<pid>/exe` and md5 (R66), the pad's key events (R51).
  - the laptop streams `journalctl -k -f` (`raw/kernel-stream-20261120.txt`).
- The first title smoke: `smoke0436.sh`, exp 0413's `start0413g.sh`, 200 s on the candidate's normal and lean builds.

## Result

### Result 1 (2026-11-20 00:40-00:59, boot 40a8312e, the once-reset boot): two clean runs, then a GPU hang on the SHARED build

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms |
|---|---|---|---|---|
| u436sS1 | shared 99f2a567 | NO_CRASH | 31.13 (294 s) | 229 / 75 |
| u436sC2 | candidate d55e4cbd | NO_CRASH | 34.40 (293 s) | 214 / 67 |
| u436sS3 | shared 99f2a567 | KERNEL: GPU hang at ~G+66 s, the box rebooted | - | - |

Both clean runs: exe verified from `/proc/<pid>/exe`, 0 pad keys; the su436 "ON" line in C's log only. These two runs
are on the once-reset boot and are not pooled with the runs on the clean boot (the top session's ruling). One pair is
no result.

**u436sS3's hang (the shared build, his 09:46 scene, no input):** started 00:55:47, G at 127 s; at 00:59:00 (~193 s)
the kernel: `ring gfx_0.0.0 timeout, signaled seq=21479881, emitted seq=21479883`, `Process kyty_emulator ... thread
bc5-ring`, `Ring gfx_0.0.0 reset failed`; bc5-gpu-watch crashed the kernel for a reboot (SysRq). No VM fault line this
time (0 in the laptop's stream and in pstore). The devcoredump's "page fault observed ... 0x314cb6000" is the device's
LAST fault, F862's first-title write fault of 11-19 at the same address, not this run's. CP at the timeout: IB1 at
0x101c00000000 (a job slot) with 0x2f0 of 0x4170 dwords left (~dword 16,000 of the executed copy), IB2 finished.
The host's own timeout probe (BC5_DIRECT_TIMEOUT_PROBE=1, the completion thread's 2 s fence bound) caught two jobs:
- **acb #165180, 7775 dwords:** its 5 waits, all WAIT_REG_MEM64 "== 0" on labels 0x12004b4bc8, 0x12004b4fc8,
  0x12004b53c8, 0x12004b57c8, 0x12004b5bc8, were each found met at submit and **DROPPED** (0 kept for the GPU); then 98
  indirect dispatches of program 0x909936c00 with **junk grids** (group counts ~1e9 per axis, float bit patterns; the
  largest 1.8e19 groups, at dword 3388).
- **dcb #165177, 15678 dwords** (the GFX ring, the kernel's timed-out ring): 26 waits, 25 kept for the GPU; one, a pfp
  WAIT_REG_MEM64 on 0x12004b4c38, NOT met at submit and DROPPED (the F262 given-up family); 48 dispatches, the largest
  grid 1792 groups.

**ho430 in u436sS3's journal** (read 01:5x, between chains): the last 60-s line, t 180.9 s (the hang ~188.7 s): F4
fences 15,514; F10 acb waits 64,392, with a chain writing the label 1,513, bound 1; F16 in-flight waits 1 (returned,
1.6 ms); F18 0; bounds that stood 0. No "THE BOUND STANDS" line before the hang. So at the dropped waits the host knew
no open, in-flight or registered pending writer of those labels: nothing for F10/F16/F18 or F4 to act on. Hypothesis
(NOT verified): the writer was not yet submitted by the title at all, the case exp 0430's F3 (XQ_ACQUIRE: a stale label
preset busy at the writer's submit) covered and F859 removed.

### Result 2 (2026-11-20 01:02-01:48, clean boot f813bbc0): the scene, 3 + 3

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms |
|---|---|---|---|---|
| u436sS4 | shared | NO_CRASH | 34.75 | 212 / 61 |
| u436sC5 | candidate | NO_CRASH | 34.14 | 219 / 72 |
| u436sS6 | shared | NO_CRASH | 34.34 | 204 / 56 |
| u436sC7 | candidate | NO_CRASH | 33.29 | 220 / 78 |
| u436sS8 | shared | NO_CRASH | 34.21 | 208 / 59 |
| u436sC9 | candidate | NO_CRASH | 35.46 | 215 / 70 |

Each run ~293 s from G+10; exe verified (`/proc/<pid>/exe` md5 = the arm's binary), 0 pad keys, 0 kernel lines; the
su436 ON line in every C log, none in S. Shared 34.21-34.75 (mean 34.43), candidate 33.29-35.46 (mean 34.30): the
ranges overlap, **no gain in the scene**. Seconds with a gap over 100 ms: shared 56-61, candidate 70-78, no overlap in
3 runs each (over 50 ms: 204-212 against 215-220). Small counts; not more than "the candidate is not better, and may
be a little worse on long gaps here".

### Result 3 (2026-11-20 01:54-04:39, clean boot f813bbc0): the scripted route, 3 + 3, the original exp 0430 runner

Runner `~/bc5-work/exp0430/run0430f.sh` unchanged (9d53dccc, its own "no reset since boot" gate; the boot had 0 lines),
slot 4 of exp 0425's snapshot, his 14:50 fight record at G, then exp 0379's walk to G+1500, `N_ARENA=off`, way 2's words
and the timeout probe in both arms, RT on.

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms |
|---|---|---|---|---|
| u436rS1 | shared | NO_CRASH | 40.52 | 225 / 6 |
| u436rC2 | candidate | NO_CRASH | 45.08 | 136 / 0 |
| u436rS3 | shared | NO_CRASH | 41.14 | 201 / 0 |
| u436rC4 | candidate | NO_CRASH | 44.47 | 112 / 2 |
| u436rS5 | shared | NO_CRASH | 40.69 | 217 / 2 |
| u436rC6 | candidate | NO_CRASH | 43.77 | 169 / 7 |

Each run ~1490 s from G+10; exe verified, 0 pad keys, 0 kernel lines in the streamed `journalctl -k`
(`raw/kernel-stream-20261120-b.txt`: no amdgpu line from 01:02 to 05:09). Shared 40.52-41.14 (mean 40.78), candidate
43.77-45.08 (mean 44.44): **no overlap, +9.0 % on the route**. Seconds with a gap over 50 ms: shared 201-225, candidate
112-169, no overlap; over 100 ms both small (0-7) and overlapping. The scene (Result 2) and the route disagree: the gain
is where the walk and the fight load the host (the route), not in the 09:46 scene, which stands still with no input and
may be GPU-bound; that reading is a guess, not measured.

### Result 4 (2026-11-20 05:09-05:17, clean boot f813bbc0): the first title smoke

`smoke0436.sh`: u436an (candidate normal d55e4cbd) and u436al (candidate lean bbebc371), 200 s each through exp 0413's
`start0413g.sh`: both PASS, kernel lines 0, crash lines 0, pad keys 0, exe verified; RssAnon at the end 234,752 /
232,860 kB.

Records of the clean boot's runs (scene, route, smoke; play logs left on the box, frame logs gzipped):
`raw/clean-f813bbc0/`.

### HANDOFF finding draft (F-next; the top session numbers it)

| F? | **The F852/F858 GPU hang class came back on the shared builds of patch 8986853b (exp 0430's F10+F4+F16+F18 built in,
F859): exp 0436's run u436sS3, shared normal 99f2a567, his 09:46 scene with no input, hung at ~G+66 s on 2026-11-20
00:59 (gfx_0.0.0 timeout submitted from bc5-ring, ring reset failed, gpu-watch reboot).** The host's timeout probe shows
the class's signature: an acb (#165180) whose five 64-bit "== 0" waits on 0x12004b4bc8 … 0x12004b5bc8 (the same label
row as H4's and h430J1's 0x12004b4fc8) were all decided met at submit and dropped, followed by 98 indirect dispatches of
0x909936c00 on junk grids up to 1.8e19 groups; beside it the GFX dcb #165177 with one given-up pfp wait (0x12004b4c38).
No VM fault this time (the dump's fault field is F862's of 11-19). The run was on a boot with old recovered resets
(exp 0434's first-title faults, 11-19 14:06-14:14; R60's reboot was not possible from a session), so it is to be repeated on a
clean boot before anything is concluded; F859's 0 in 6 scripted runs + the 57-min play was the route, not this scene.
The run's ho430 journal (t 180.9) shows F10 bound 1, F16 1 returned, 0 bounds that stood and no "THE BOUND STANDS"
line: the host knew no pending writer of the dropped labels. Hypothesis (not verified): the writer was not yet
submitted, the case exp 0430's F3 covered and F859 removed. On the clean boot f813bbc0 the same scene ran 3 more times
on the shared build (u436sS4/S6/S8) with no hang. |
experiments/0436-submit-unlock/README.md; records: `raw/hang-u436sS3/`, the devcoredump
`~/bc5-data/captures/devcoredump/20261120-005901-devcd10.txt` and the dumped acb
`~/bc5-data/captures/play-20261120-0055/gc/ib-timeout-00165180-acb-7775.bin` on the box (never committed) |

## Verdict

**The candidate (submit out of the device mutex, `BC5_DIRECT_SUBMIT_UNLOCK`) raises the scripted route by 9 %: 44.44
against 40.78 flips/s, 3 + 3 runs with no overlap (43.77-45.08 against 40.52-41.14), and cuts the seconds with a gap
over 50 ms from 201-225 to 112-169.** In his 09:46 scene it gives nothing (34.30 against 34.43, ranges overlap) and may
be slightly worse on gaps over 100 ms (70-78 against 56-61, small counts). All 12 measured runs on the clean boot
f813bbc0 and the first-title smoke of both test builds were clean: no GPU line, no crash, every binary verified.

- Stability: 0 hangs in 7 candidate runs of the second title (6 on the clean boot, C2 on the once-reset boot) and
  the 2 first-title smoke runs. The one
  hang of this experiment was on the SHARED build (u436sS3, the once-reset boot; the F852/F858 class, see the HANDOFF
  draft), so it says nothing against the candidate; 7 runs are not enough to say the candidate does not change the
  hang rate either.
- Once-reset boot: S1 31.13 / C2 34.40 flips/s (scene) are kept apart and not pooled.
- Disposition: a candidate for a shared build by decision (the switch can stay with `=0` off, or go in with no switch
  as the house style has it); not swapped here. Before that: the maintainer's play on it, and a longer scene look if the
  >100 ms gap count matters.
- Hashes: candidate normal `d55e4cbd`, lean `bbebc371`, private archive `d6638808`; shared normal `99f2a567`.

## Bake into the shared builds (2026-11-20 05:53-06:07, boot f813bbc0)

The maintainer's word through the top session: order to deploy at once, built in with no switch (his standing rule that switches go and
the code is built in). Kit `bake/` (on the box `~/bc5-work/exp0436/bake/`):

- `mkbake436.py`: the candidate's unit with `su436_on()`, its `getenv("BC5_DIRECT_SUBMIT_UNLOCK")` and its ON/off line
  removed; in async mode the unlocked kernel submit is the only path; sync mode (g_async off: each job waited for at
  submission) keeps the call under both locks. Normal keeps su436's count line ("tag su436"), lean compiles it out (the
  top session's yes, as ud434's journal line). `0002-bc5-0436-baked.patch` (3134afd1) is that unit against the shared
  tree's 6f4bf71a; `be/direct.cpp` eacf8d2a and `be/direct.hpp` 9256f3b9 are the tested candidate's backend unchanged
  (it never had a switch).
- `swap0436.sh` (c50a7684, exp 0433's int0433.sh form with exp 0434's dry run), `undo0436.sh` (31708598: back to patch
  8986853b, normal 99f2a567, lean 82720cca, archive 51db2c91, direct.cpp 52f74d0e, direct.hpp 24988c4e),
  `run-swap0436.sh` (d6d0ad33), `smoke0436s.sh` (7ef08f76: exp 0434's smoke with `/proc/<pid>/exe` md5 per run);
  `boxbake436.sh`: the private baked build before the swap.
- Private baked build (nice 19, own lock, pins before and after; the reference direct.o equal to the shared member):
  normal 0ce71405, lean 5b6e4ede, archive d6638808; strings: no SUBMIT_UNLOCK in either, "tag su436" in normal only.
- Dry run on copies of the tree, the backend source and the swap directory: all steps pass, PATCH_NEW bb04219b, the
  undo restored 8986853b / 52f74d0e / 24988c4e on the copies.
- The branch's backend (`backend/src/direct.cpp`, `backend/include/bc5/direct.hpp`) built as CI does in the box's
  ubuntu distrobox: Debug, amdgpu OFF and ON, 0 warnings, ctest 130/130 each (`raw/bake/exp0436/bake/ci/`).

**The swap (the top session's GO): patch 8986853b -> bb04219b (135 files, exp 0372 lines 5, the pad_audio_route header
in), archive 51db2c91 -> d6638808, normal 99f2a567 -> f345db74, lean 82720cca -> 6a735b81**; no (KYTY_)BC5_ word
gained or lost in either binary. `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on this branch is the box's new
`git diff f266548` (bb04219b). Undo: `bash ~/bc5-work/exp0436/bake/undo0436.sh`.

Smokes after the swap (one unit under the user manager, exe md5 read per run, 0 pad keys, 0 kernel lines, 0 crash
lines): s436sc the first title lean 200 s PASS; s436su the second title lean 300 s PASS (33 of 33 key lines); s436sn the first
title normal 200 s PASS, its log with su436's count line. Records: `raw/bake/`.

### HANDOFF row draft (the top session numbers it)

| F? | **The kernel submit (DRM_IOCTL_AMDGPU_CS) runs outside the host's device mutex and the backend's lock (exp 0432
note 8): +9 % flips/s on the second title's scripted route (44.44 against 40.78, 3 + 3, no overlap; seconds with a gap
over 50 ms 112-169 against 201-225), no change in the 09:46 scene (34.30 against 34.43).** Order kept by a lock per
ring taken before the device mutex; a backend flight lock keeps unmaps from running under a job in its kernel call;
F10/F16/F18 and ud434 unchanged. Built into the shared builds with no switch on 2026-11-20 (patch bb04219b, normal
f345db74, lean 6a735b81, archive d6638808); smokes 3/3 PASS. | experiments/0436-submit-unlock/README.md |
