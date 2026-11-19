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
(the A/B), `smoke0436.sh` (ASTRO BOT).

## Setup

(to be filled from the box: kernel, Mesa, libdrm, binaries)

## Result

(pending)

## Verdict

(pending)
