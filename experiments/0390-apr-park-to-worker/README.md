# 0390 — A switch that routes parked AMM-only submissions to their worker (F295's race)

**Status: done, as a private candidate.** The build with the real headers and the smoke run on the box passed on
2026-11-01. Nothing is in shared, main or patch 0001. Integration waits for the next D19 rebuild.

**Question.** Exp 0236 (F295) found that in async APR mode the wait thread's pump races the per-queue workers and
readers, on a path the second title never takes. Does `patch_0236`, behind a switch that is off by default, remove the
race when the path is taken, and does it change nothing while off?

**Decision.** The maintainer in the exp 0236 session: "jeżeli nie ma kolizji a codex i main wyrażą zgodę to tak". The top
session (2026-11-01): yes, as a private candidate only. Into shared only with the next D19 rebuild, after a compile on
the box, a smoke run and Codex's round, with a switch that defaults to off. Top sends the Codex request and gives the
box signal after its queue (0388, 0389, mount-reread). The maintainer's own word, "Build i smoke 0390", covers those
two steps on this branch.

**Setup.** Laptop only: no box access, no GPU run. 2026-11-01.

- Source: `~/src/KytyPlus` was not read. `src/libs/libAmpr.cpp` was rebuilt from `refs/Coder787-source_KytyPlus` blob
  `073361d` plus the libAmpr section of patch 0001 on main (5b22f700). The result has blob `8fe2d40`, the one patch 0001
  names, md5 `93bdfe77…`.
- `patch_0390.diff`, `8fe2d40` → `886f7d2`, md5 `9a9b8f46…`. It differs from `patch_0236.diff` in these ways:
  - `KYTY_BC5_APR_PARK_TO_WORKER=1` selects the new route, and unset or 0 keeps today's. It is read with `std::getenv`,
    not `BC5_DIAG_ENV`, so it also works in the lean build. The other APR behaviour switches do the same.
  - `StartAprWorker(qi)` is factored out of the async branch, with the same behaviour.
  - The readers' comment on the 1-s limit stays, because it is still true while the switch is off.
- Harness: `extract0390.py` copies the real APR code verbatim out of the file (`CommandBufferState` and everything from
  `ReadHostFileToGuest`'s declaration through `ExecuteAprCommandBuffer`, `raw/build.txt`). `harness0390.cpp` compiles it
  on stubs, with no emulator headers, and counts how often each command ran.
  - Stubbed: guest memory, file reads, maps, events and submission results. A worker's file read sleeps 2 ms, a reader's
    0.3 ms.
  - Scenarios:
    - `none`: the second title's shape, the AMM-only wait met by the buffer's own earlier write (exp 0236).
    - `busy`: a read buffer, then an AMM-only buffer that stops at a wait, then 200 read buffers at the same priority.
      A later AMM-only buffer moves the counter, as the title does.
    - `alone`: an AMM-only buffer stops at a wait at a priority with no worker yet.
  - A run passes on exit code 0 with no sanitizer report: every write, event, map and submission result exactly once,
    in queue order.
- `build0390.bat`: Visual Studio 2026 clang-cl 22.1.3, MSVC STL, `/O1 /MD /fsanitize=address`. It is built twice, from
  the unpatched and the patched file. Earlier sessions noted no compiler on the laptop; it was only missing from `PATH`.
- `arms0390.sh`: 12 arms, 10 runs each. `stacks0390.py` shortens the sanitizer reports.

**Result.**

1. **No collision in the repo.** Patch 0001 names the same `libAmpr.cpp` blob, `8fe2d40`, on all 24 local branches and
   all 5 origin heads. `patch_0390.diff` applies to it. The box's tree is not checked.
2. **Compile.** Both versions of the real code compile with no errors. The only error on the way was my own stub
   (`KernelEqueue` is not a pointer). The build on the box with the real headers and GCC/libstdc++ is still to come.
3. **The harness** (`raw/harness-summary.txt`, per run `raw/harness-runs.txt`, 120 runs):

   | arm | build | scenario | switch | read-ahead | passed | sanitizer crash | wrong counts |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | control-off | patched | none | unset | 4 | 10/10 | 0 | 0 |
   | control-on | patched | none | 1 | 4 | 10/10 | 0 | 0 |
   | old-ra4 | unpatched | busy | | 4 | 0/10 | 9 | 1 |
   | old-ra0 | unpatched | busy | | 0 | 0/10 | 10 | 0 |
   | off-ra4 | patched | busy | unset | 4 | 0/10 | 10 | 0 |
   | off-ra0 | patched | busy | unset | 0 | 0/10 | 10 | 0 |
   | off0-ra0 | patched | busy | 0 | 0 | 0/10 | 10 | 0 |
   | on-ra4 | patched | busy | 1 | 4 | 10/10 | 0 | 0 |
   | on-ra0 | patched | busy | 1 | 0 | 10/10 | 0 | 0 |
   | alone-off | patched | alone | unset | 4 | 10/10 | 0 | 0 |
   | alone-on | patched | alone | 1 | 4 | 10/10 | 0 | 0 |
   | sync-on | patched | busy, `KYTY_BC5_APR_SYNC=1` | 1 | 4 | 10/10 | 0 | 0 |

   - **F295's race happens when the code runs, not only on paper.** All 50 `busy` runs on today's route failed. The ones
     that printed counts show submissions finished twice (up to 343 results for 202 submissions in the kept lines) and
     the parked buffer's commands repeated, with the wait thread started.
   - One of those runs lost a buffer outright, F295's lost submission: `old-ra4` run 6, 202 results but one write never
     ran. It is the one "wrong counts" entry in the table.
   - **With the switch on, all 20 `busy` runs were exact:** 202 results for 202 submissions, in order, with the wait
     thread not started.
   - **The test reaches the changed branch.** `busy` parks by construction: the counter is 0 at the submit. `alone-on` is
     the sharpest case, because only the parked branch can start `bc5-apr-q6` there, and it did. `alone-off` shows the
     pump alone is correct when no worker exists.
   - **Off means off.** `off0` (`=0`) fails as `off` does. `off-*` fails as `old-*` does, so the switch does not hide or
     alter today's route. The stubbed `BC5_DIAG_ENV` returns null as in the lean build, and the switch still works.
   - **Sync mode is untouched:** with the switch on, the wait thread still runs the parked buffers and no worker starts.
4. **The crash** (`raw/asan-stacks.txt`): in `AprWorkerThread` at its `front.ra_state` read, or in `AprReaderThread` at
   `b.ra_state`, both in the real code. The read is at address 0xe8 or 0x108 in the zero page. The first is `ra_state`'s
   offset in `ParkedAprBuffer` by its declaration (232). That fits the queue being corrupted by the worker's and the
   pump's pops, F295's "pops an empty deque", but I did not trace the deque's fields.

**Limits of this evidence.**

- The harness is real queue code on synthetic input and stubs. It says nothing about the title. `busy` is a shape the
  second title has not been seen to produce (exp 0236).
- Windows, the MSVC STL and clang are not the box's GCC and libstdc++. The crash site depends on the STL's deque; a
  different failure is to be expected on the box's library, not the same address.
- There is no ThreadSanitizer on this platform, so the data race on `next` is inferred, not reported by a tool.
- F295's "lost submission" was seen once, not reliably: run 6 of `old-ra4` ended with 202 results but one buffer's write
  never ran (`raw/harness-runs.txt`). A run that crashes before it counts cannot show this, so 1 is a lower bound.
- Timings are the stubs', so 50 of 50 says the race is reliable in this setup, not how soon it would strike in a game.

**The box kit, ready before any run.** Nothing here has touched the box. `mk0390run.py` derives the scripts from exp
0388's reviewed set (branch `exp/0388-job-arena-root`, 68ea1ffe), as 0388 derived its own from 0386.

- **Build, `gobuild0390.sh`, in a slot from the top session:** an atomic claim of BOX-LOCK by hard link (`box0390.sh`),
  nothing written before the lock is ours, then the send with its hashes compared. On the box `units0390.sha256` must
  match the shared tree's `libAmpr.cpp` (blob `8fe2d40`), `patch0390.py` patches a private copy, `patched0390.sha256` must
  match the result (blob `886f7d2`), and `build0390.py` compiles that one unit with the shared build's own command and
  links with the shared objects into `~/bc5-work/exp0390/kyty_emulator`. It stops if the shared binary changed. The lock
  is given back on a stop; a lost connection leaves it and says so, because the box may still be compiling.
- **Smoke, `series0390.sh`, one `go0390.sh` per run, 30 min in all:** the fight route of exps 0386/0388, the private
  binary, 180 s, the job-arena fix on as in shared use.
  - Saves, by the maintainer's rule of 2026-10-31: `run0390.sh` pins the named snapshot, each run resets a private copy
    from it and writes the copy's sum to `<tag>-savecopy.txt`, by `route_sum`'s recipe. Live saves are neither read nor
    compared: exp 0388's reads were removed here, and nothing about them can stop or fail a run.
  - Arm P (`P1`): no switch. Arm Q (`Q1`): `KYTY_BC5_APR_PARK_TO_WORKER=1`.
  - A run that does not reach the fight gets one replacement in the whole series. Any stop ends the series.
- **RT on is an entry condition, enforced three times:**
  - before the emulator starts, `prestart0390.sh` stops the launcher (exit 97) if `KYTY_BC5_RT` is set at all;
  - during the run, a `ray tracing off:` line at the live check at 150 s stops it;
  - afterwards, any such line in the run's own journal, or `KYTY_BC5_RT=0`, makes it INVALID.
- **Fail-closed:** the environment manifest proves the arm from the emulator's own environment. An arm P run with the
  switch set, or an arm Q run with it at 0, is INVALID (tested). Missing evidence is INVALID, never a zero count.

- **Tests on stand-ins, laptop only, no SSH** (`raw/test-*.txt`): the real scripts with ssh, scp, `/proc` and the kernel
  log replaced.
  - `test0390run.sh`: 110 of 111 in the full run. The one FAIL, "a thread list older than the run", was mine: I
    regenerated the scripts while the test ran, so bash read the new case and judged it with the old `check0390.py` it
    had copied at its start.
  - The groups that changed, rerun on the final scripts: `arms` 13 of 13, `rule` 5 of 5, `series` 7 of 7.
  - `test_box0390.sh` 14 of 14, `test_gobuild0390.sh` 7 of 7.
  - After the save change, targeted, on the final scripts (`raw/test-run-saves.txt`): `positive` 9 of 9, with the copy's
    sum equal to the snapshot's and no live-save read left, `series` 7 of 7, `rule` 5 of 5. The full suite was not rerun.
  - None of this is a run on the box: the build has not met the real headers and the scripts have not met the real box.
- **Codex's round:** done on `patch_0390.diff`/654ff6a2, on the maintainer's delegation: agreed as a private candidate,
  build and smoke under the top session's slot, with no blocking remark (`coordination/codex-to-claude.md`, 01:23 UTC).
  Shared, main and patch 0001 stay a separate integration.

**The rule, fixed before the runs** (`check0390.py rule`).

- `RULE PASS`: arm P and arm Q each have a run classed NO_CRASH, that is every d19gates gate met: no kernel line,
  devcoredump, TIMEOUT or crash, RT on, the fight reached.
- `RULE FAIL`: any run in the series is classed otherwise. KERNEL, INVALID or a crash at the known site stops the series
  at once.
- `RULE OPEN`: an arm has no run.
- **What PASS means: no regression seen in two runs, nothing more.** `AprParkToWorker()` is read only in the parked
  branch, and the second title does not reach that branch (exp 0236). So P and Q run the same code unless that branch fires,
  and a smoke cannot show the fix working; the harness is the only evidence of that.
- **What the runs do show about the branch:** each run lists the emulator's `bc5-apr-*` threads just before it stops, and
  `-check.txt` says `APR wait thread: absent`, `present` or `not read`. `absent` in arm P means the path did not fire.
  `present` does not change the class, but it would be the first sighting of the path in the title and is a finding
  in itself. `not read` is no evidence either way.

**Result on the box, 2026-11-01.** The record is `raw/box-P2-Q1.txt`, with `raw/series.txt`, `raw/rows.txt` and the
kernel streams. Kernel 7.2.9-ogc3.1, swappiness 150 and page-cluster 0 (the top session's temporary settings, read at
the end), RT on, `MangoHud.PPSA03671=on` from the maintainer's 07:31 `input.cfg`, the job-arena fix on in both arms.

- **Build:** rc 0, no errors, on the box's GCC with the real headers. The tree's `libAmpr.cpp` matched its pin, and so did
  the patched copy. Private binary `2db9b7d0…`; the shared binary stayed `78f25172…`.
- **Smoke:** `RULE PASS`, 2 of 2 NO_CRASH.

| Run | Arm | Stopped after | Fight reached | Flips | Kernel, TIMEOUT, devcoredump, crash | `bc5-apr-wait` |
|---|---|---|---|---|---|---|
| P2 | switch unset | 183 s | at 63 s | 5552 | 0 | absent |
| Q1 | switch `=1` | 180 s | at 64 s | 5380 | 0 | absent |

  Both streams hold only an IPv6 notice, no amdgpu line. Both private save copies summed to the snapshot's
  `9347496fbaf30f25`, and the private learned list came back unchanged. One run per arm gives no performance comparison.
- **The queue threads differ.** Q1 also had `bc5-apr-q0` and its four readers; P2 had only queues 1, 3 and 5. In the code
  a worker starts for an ordinary submission with reads, or, with the switch on, for a parked AMM-only one. Arm Q never
  starts the wait thread, so its `absent` says nothing about the path. An unpatched run of exp 0200 also had
  `bc5-apr-q0` (`experiments/0200-cutscene-character-lag/raw/L1-sample.txt`), so the thread alone does not show the
  path. Without a trace these runs cannot tell which start happened in Q1. In arm P the path did not fire up to the list.
- **Getting there:**
  - The app refused `gobuild0390.sh` as `[Remote Shell Writes]` at 06:15 and about 09:42, before it ran; nothing reached
    the box. It passed at 09:53, after a third GO.
  - Reading the wrapper first found that the claim's two-word label reached the box as two arguments, which would have
    spoiled the lock line's time. It is now quoted for the box's shell. `test_gobuild0390.sh` 7 of 7 cannot see this bug;
    a one-line check of the words the box's shell gets can.
  - The first P1 stopped under the lock before any launch, on `input.cfg differs` (`raw/series-first-stop.txt`). Its
    pin and the learned list's were re-read in the slot, and the box refuses a used tag, so arm P ran as P2.

**Still to do.**

- The maintainer's word covered the build and the smoke, on this branch. It does not cover a merge, a push, or any change
  to the shared builds or `~/src/KytyPlus`.
- At integration, with the next D19 rebuild: `backend/kytyplus-patches/README.md` gets the switch, and patch 0001 is
  regenerated. Then the default can be reconsidered.
- To learn whether the title ever parks a submission, a run needs AmmTrace or the APR journal on. Neither was in this
  smoke's scope.

**Verdict. The candidate builds on the box and showed no regression in one run of each arm; the fix itself rests on the
harness alone.** It stays private, with the switch off by default. The title's use of the parked path is still not
seen: not in arm P, and unknown in arm Q.
