# 0107 — what holds the second title's menu at 37 fps: its render thread waits for our device lock

**Question.** After the pacing fix (experiment 0105) the menu runs at 37 fps. The GPU is busy
12.7 ms a frame, and the frame profile counts 18 ms "outside the host" on the game thread.
Where does the render thread spend its time?

**Setup.**
- Unattended menu runs: the play shortcut's settings plus `BC5_DIRECT_REMEMBER_UNMAPPED=1` and
  `BC5_DIRECT_PACE_FIX=11d0288100:100/170`, a fresh save, one cross at 80 s;
  2026-10-15 00:39–00:49.
- A stack sampler attached gdb from 100 s on, 40 times, about every second. `pc-sampler-bt.sh`
  takes the first 6 frames of every thread (run 396); `pc-sampler-bt14.sh` the first 14 (runs 397,
  398).
- The python sampler of experiment 0037 printed no threads in run 395 and was replaced.
- Run 398 adds a host change (patch `0001-bc5-lle-agc.patch`). `Direct::init_once()`, which every
  /dev/gc ioctl calls, returns through an atomic flag once initialisation is done, instead of
  taking `g_dev_mutex` each time.
- A scan of all 341 private shader dumps for `s_memrealtime` / `s_memtime`.

**Result.**
1. **Render Thread, run 397** (19 samples): 7 wait on `g_dev_mutex`, 5 of them in `init_once`
   and 2 in `submit_one`. 4 are in our submission (CS ioctl, BO list, mapping copy). The other
   ~6 are in the title's code or elsewhere. The thread named `game-main` mostly waits on futexes.
   The Coherent threads idle.
2. **The lock holder is the ring thread.** `bc5-ring`, the soft CP's doorbell consumer, sends about
   74 small compute jobs a frame. Its samples show `submit_one` under the lock: CS ioctls, mapping
   copies, `direct_sync`. The completion threads `bc5-cq0/1` mostly wait.
3. **The `init_once` fast path changes nothing measurable** (run 398 against run 397, 90–99 s):

   | | run 397 | run 398 |
   |---|---|---|
   | fps | 37.7 | 37.8 |
   | frame, median | 25.0 ms | 25.5 ms |

   The waits move to `submit_one`'s lock (6 of the render thread's samples). The fast path stays
   (it cannot change behaviour).
4. **Our pre-submission passes are cheap.** `piece_check` takes about 105 ms per 3,900 graphics
   buffers, about 0.5 ms a frame; `pace_fix` is smaller.
5. **Only 0x11d0288100 reads the realtime clock.** No other dumped shader of the title uses
   `s_memrealtime` or `s_memtime`. Experiment 0105's fix covers the title's whole GPU-side pacing.

**Verdict.** Answered: the menu's limit is contention for the direct path's single device lock.
The title's render thread and our ring thread both submit under `g_dev_mutex`, and the ring
thread's ~74 jobs a frame keep it waiting. Shorter hold times for the ring thread's tiny jobs,
or priority for the game thread, are the next step. Delaying ring jobs changes cross-queue
timing (given-up waits, F121), so that is tested only with the maintainer present.
