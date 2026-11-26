# F929 and F930 for docs/HANDOFF.md (exp 0439, written 2026-11-24 23:2x on exp/0439-third-title)

The branch's `docs/HANDOFF.md` is the 11-21 copy, and merging main into the branch conflicts across exp 0439's own
files. So the rows and their section edits are here, to be placed on main after F928 by the top session.
Sources: `experiments/0439-third-title/README.md` sections "mp439 slot", "The maintainer's play-1124-1901 froze the
box", "vz439" through "vz439h-j".

## §2 Findings, two rows after F928

| F929 | **Locking the direct-memory imports (`BC5_0439_MLOCK_IMPORTS=1`) ends the reclaim thrash but not the freeze: the footprint stays and the failure turns into running out (exp 0439, 2026-11-24).** Under pressure applied from outside (P1: MemAvailable driven to ~1.55 GB for 90 s), the lock kept the title running with unevictable = mlocked 9.85-9.90 GB, pgscan_direct ~5,800 over the hold, PSI full under 1 % apart from seconds at 3-4 %, and 0 blocked tasks. Against that, N2 without the lock froze (pgscan_direct 0.4 M -> 8.3 M, PSI 8-9 %, 5-6 blocked). G1 (420 s scripted, the lock on) ran clean, VmLck 8.31 GB at 40 s, 0 lock failures. P0 (the same pressure without the lock) was not run. But the maintainer's play-1124-1901 (lock on, a title start plus a new game) froze the box anyway. The pinned direct memory grew 8.5 GB at 30 s -> 11.3 GB at 85 s, still rising ~40 MB/s, with BOs 476 -> 1517 and views 4.6k -> 39k. At the end: shmem = GTT 11.9 GB, unevictable 11.7 GB, MemAvailable 1.46 GB, then allocstall +161, 5 tasks blocked, and no amdgpu line. Reading: udmabuf already pins every imported page, so the lock makes nothing newly unreclaimable. It only moves the pages to the unevictable list, so scan thrash (N2) becomes file-page starvation (1901). The cause is the import: lazy and never released, it grows with the route (the save routes stay at 9.49 GB). The fix belongs there: release views the GPU no longer references, and measure the 2 MiB-chunk padding (view bytes against pinned bytes, not yet logged). README "mp439 slot", "The maintainer's play-1124-1901 froze the box". |
| F930 | **The third title's film and card noise (grain: full-strength colour on alternate rows) is a display-buffer race in BC5. The title waits for a display buffer's flip with a flip-label wait inside a chained piece, and BC5 served those waits only at the top level (exp 0439 vz439, 2026-11-24 21:26-23:14, 0 GPU kernel lines).** Measured: the decoder's NV12 bytes are smooth and unchanged until the slot is reused; the slots lie in an eager view, imported whole, with no K1R cover; the display registration and BC5's display answers are identical in noisy and clean starts. The noise follows the title's graphics mode, kept in its save memory. Performance (60-fps target) and an empty start are noisy; Quality and Ray Tracing (the maintainer's save) are clean, each mode set through the title's own menu with screenshots. Any stall ends it for the rest of the run: a 1-s SIGSTOP, a frame dump or a pass census. With the chained-piece flip-label wait served on the CPU like the top-level one (exp 0069's rule: wait while that buffer's flip is queued, at most 100 ms, then clear a label still set), the film is clean in all three modes and the empty start on one build: priv35 138e6779, PASS_CONTEXT_CONTROL on, ~1,025 waits served per run, none cleared still set. The change is universal (`mkvlon439.py`, vl439 (b) on unless `BC5_0439_FLIP_LABEL_PIECES=0`). Its lean cost and the other titles' check are owed (exp 0439 vz439k). A correction to fn439c: its "priv33 + his save noisy 4 of 4" arms never read the save (an arm-name pattern), so it is void. README "vz439" through "vz439h-j". |

## Header paragraph (current state), the sentences to add for 2026-11-24 night

The third title's film noise is understood and has a candidate fix (F930). BC5 dropped the title's flip-label waits
inside chained pieces; serving them like the top-level wait (private build priv35 138e6779, launcher candidate
`k439/t3-test-fl.sh`, not live) gives a clean film in every graphics mode. Its cost and the other titles' check are
being measured. The freeze of 11-24 19:01 is the import's growth, not the lock (F929). The release of unreferenced
imports is the next fix.

## §3 open questions

- Add: **Q (import growth):** what keeps every chunk under a view for the game's life on the new-game route (BOs
  476 -> 1517, views 4.6k -> 39k in 85 s)? Does the title unmap or reuse direct memory that BC5 keeps imported? (F929)
- Close, if listed: the third title's film noise (answered by F930).

## README.md (project)

- Known issues: the third title's opening film and cards may show coloured line noise in the Performance mode and
  on a first start. Cause known (F930); fixed in a private build, not yet in the shared builds.
- Known issues: the third title can exhaust memory on a long new-game route (F929); the fix is in progress.
