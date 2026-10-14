# 0080 — the second title's menu text: letters lost to asynchronous submission

**Question.** The second title's dialogs and its first menu show missing or garbled letters, and
parts of the menu are missing. The maintainer wants the menu and its background right before
anything else. What causes it?

**Setup.**
- Runs 324–332, 2026-10-14 09:45–10:41, with the maintainer present. Scripts are in this
  directory; all use `run-pkg.sh`, which now takes `BC5_RUN_ENV=<settings file>`.
- On the first start the title shows a screen-reader dialog. One cross turns it off and brings
  up the "Initial setup" menu. Nothing else was pressed, except in runs 325–326 (see below).
- Screenshots every 8–10 s, private.
- Runs 324–326 also took snapshots of the reflection traversal's instance-table window
  (`BC5_DIRECT_SNAP=118c5f0000:262144:4000`, F116).
- Raw:
  - `raw/runs-fps.txt`: frame rate at 95–125 s and the last frame per run;
  - `raw/run326-instance-table.txt`: the instance-table summary, `insttab.py`;
  - `pm4dec.py`: a small PM4 lister used on a dumped 84-dword buffer.

**Result.**

| run | indirect draws | heavy probe | submission | dialog text | menu |
|---|---|---|---|---|---|
| 323 (0079) | off | off | asynchronous | letters missing | — |
| 324 (window) | `multi` + aliases | on | asynchronous | complete | — (not opened) |
| 327 | `multi` + aliases | off | asynchronous | letters missing | items right, title "IN T AL SETUP", no description |
| 329 (window) | `multi` + aliases | off | asynchronous | letters missing, box cut | items garbled |
| 330 | `multi` + aliases | on | asynchronous | complete | left half only, letters missing |
| 331 | `multi` + aliases | on | asynchronous | complete | items right, title "IN T AL SETUP" |
| **332** | `multi` + aliases | off | **synchronous** | **complete** | **complete**: title, items, description, icon, button hints |

- Run 332 used the play settings without `BC5_DIRECT_ASYNC`, `BC5_DIRECT_RING_ASYNC`,
  `BC5_DIRECT_FLIP_DEFER` and `BC5_DIRECT_MAX_IN_FLIGHT=24` (`bc5-run.env.pkg-sync`).
- Frame rate in the menu: 23.3 fps synchronous, 24.6–25.3 fps asynchronous.
- What was ruled out on the way:
  - The filter drops nothing that draws. Its drop tally (run 328) has only thread-trace markers
    (`SQ_THREAD_TRACE_USERDATA_2/3`, policy), an unresolved SH register, the CPU-served waits,
    and one `RELEASE_MEM` per frame in an 84-dword buffer that writes a label outside guest
    memory.
  - The CP's checks of the indirect draws do not skip them: the arguments read at submission
    are 1 instance and 13–439 vertices.
  - The presentation filter is linear, with native scale. The windowed run was as bad.
- The heavy probe had seemed to help the dialog (3 of 3 runs with it, 0 of 3 without). It only
  slows the game thread.
- Runs 325–326: the script pressed cross three times, so "New Game" started.
  - Run 325: a GPU page fault at 0x11ec16b000; the host learned the region, and the ring reset
    recovered.
  - Run 326: at the same point (~91 s) the GPU hung without a fault, and the machine went down.
    The hang watcher wrote nothing (it did not trigger in run 325's 2 s timeout either).
  - Run 326's last instance-table snapshot, 3 s before the hang: records 173–191 of the table at
    +0x36100 had an all-NaN transform, object-tree address 0, root link 0x25 and flags 0. One
    snapshot earlier they held valid records (flags 0x1f000000). Every snapshot of runs 324–326
    before that was clean.

**Verdict.** Passed for its question:
- The missing letters and the broken menu are a race between the game's CPU and our
  asynchronous submission. With up to 24 jobs in flight and deferred flips, the title rewrites
  per-frame text data while the GPU has not yet drawn from it. Submitted synchronously, the
  menu is complete. The multi-draw packets are still needed for the text (F118).
- This also explains why the run-to-run results differed, and why slowing the game thread (the
  heavy probe) seemed to help.

Next:
- Find which of the four settings is the race, so that ASTRO BOT keeps its asynchronous path.
- Give the second title its own settings.
- The "New Game" hang (F113–F116) remains. The NaN/zero instance records just before it are the
  lead: a record with tree address 0 and flags 0 sends the traversal into memory it was never
  meant to walk.
