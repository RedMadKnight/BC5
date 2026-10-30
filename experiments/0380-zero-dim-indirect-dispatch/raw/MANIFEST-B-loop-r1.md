# B loop manifest: variant r1 (for Codex's decision; nothing here has run)

Requested variant: **r1**, the only one with a binary. r2 (`rec0380_before`, the 16 jobs before a timeout) is not built,
has no md5 and no smoke, and its test `rec0380_test.cpp` case 6 has not been compiled. Its timeout path would not run in
a healthy smoke. It is a different capture and would need its own manifest. Nothing below applies to it.

| Item | Value | Source or state |
|---|---|---|
| Binary | `~/bc5-work/exp0380r1/bin/kyty_emulator`, md5 44417414 (8 hex digits recorded) | README §25; RS1's start record |
| Binary's parts | shared objects 58c4a627, archive bb50b2e0; unit c46144c4 (exp 0379's e62113a5 + recorder); `runtimeLinker.cpp` 5f2bc982 (tree 96e03695 + crash frames) | RS1-extract.txt |
| Recorder | `rec0380.inc` b844fb51 + `mk-rec0380.py` 78d98c50 **at commit 6c0c84d** (F608). The files at HEAD are r2's and do not reproduce r1. Part A only | git; R1-rec0380_test-out.txt passed |
| Runner | `~/bc5-work/exp0380r1/s6n0380r1.sh`, repo copy md5 494ac253, pinned by the loop | the box copy is unread; the loop refuses another hash |
| Loop | `raw/loop0380b.sh` md5 c42425b9 | stand-in dry run passed; not on the box yet |
| Kernel stream | `raw/stream0380bl.sh` md5 3d9d7b3b, from the laptop | not run yet |
| Launcher | `play-pkg.sh` 55531ab6, derived private copy b0504f88; the runner checks the first and records the second | RS1 |
| Learned file | `direct-learned-pkg.txt` a7cc8581, 109 windows, private copy | RS1; recorded per try, not pinned |
| Switches | `BC5_CRASH_FRAMES=1 BC5_0380_REC=1`, hard-coded in the loop, and nothing else from exp 0380: no `NO_CLEAR`, no `ZERO_SKIP` (the skip's code is in the unit, off) | loop line 35; each try's start record shows the environment |
| Mode | RT on, one ring (the launcher's `BC5_DIRECT_COMPUTE_RING=-1`), the runner's environment check | runner |
| Saves | Live sum 377a8d456a9b4cb1 (read 2026-10-29, re-read before start; the loop refuses another). Route saves `exp0196/saves-before-152617`, private copy. The live saves are only compared | RS1 |
| Limits asked | 180 s a try, 7200 s budget, about 34 tries | for Codex to decide |
| Stops | first try not `pass` (any class, not only F403); stop file; live saves changed; under 20 GiB free; budget; lock taken by someone else; emulator left running | loop |

## Smoke

- **RS1 (2026-10-29 23:51) passed, but with other switches:** 300 s, plus `BC5_DIRECT_PIECES_NO_CLEAR=1`,
  `BC5_DIRECT_ZERO_SKIP` and `BC5_0380_REC_SELFTEST_S=150`. 30.9 flips/s, no crash or kernel line, the recorder's
  self-test wrote its file.
- **No smoke exists with the loop's exact switches.** Proposed first box step, tag `BS1`: one 180-s try with the loop's
  two switches plus `BC5_0380_REC_SELFTEST_S=150`, the one difference, because a healthy run does not otherwise run the
  recorder. Pass means verdict `pass`, a `rec0380:` self-test line and file, and flips/s near RS1's. Its hashes are read
  on the box and added here before the loop starts.
- A smoke covers neither the recorder's timeout trigger nor the crash frames. Those have unit tests only for this binary.

## What it can and cannot show

- It records part A at a timeout: the launched dims, the `SET_BASE` and `INDEX_BASE` dumps, the triple scan, 2–20 s late.
- It does not record which job ran before the B (F640's open point), and it cannot prove a fetch bug (REVIEW-06, REVIEW-07).

## Other limits

- The runner frees the lock after each try. The loop now takes it straight back and ends if someone else got it first.
- A watch reboot kills the loop without its exit trap, so the lock line stays until this session clears it after a health
  check. That also keeps the box closed until someone has looked.
- It needs an attended window of up to 2 h, the maintainer's own word in this chat, and no play on the box.
- Each try makes a save snapshot and a journal. The 20-GiB stop is the only bound on them.
