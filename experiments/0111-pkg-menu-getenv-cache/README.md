# 0111 — caching the host's BC5_* settings per call site: slightly slower, reverted

**Question.** A stack sample of the ring thread in run 405 (experiment 0110) caught `getenv`
inside `submit_one`. The submission path calls `std::getenv` about eight times for every buffer,
and two of the calls sit inside its packet loop. Each call walks about a hundred environment
variables, some of them under `g_dev_mutex`. Does reading each setting once help the menu?

**Setup.**
- `envcache_host.py` (applied to the host source, then reverted) adds a macro
  `BC5_ENV(name)`: a lambda with a function-local static, so each call site reads its variable
  once.
- It replaces 16 `std::getenv("BC5_…")` calls on 15 lines: `direct_sync_one`, `sync_mappings`,
  `submit_split`, `piece_check` and `submit_one`.
- Nothing sets `BC5_*` variables while the title runs. The guest's `setenv` reaches the host
  environment, but the title never uses these names.
- Unattended menu runs as in run 403 (experiment 0109), 2026-10-15:

| run | time | binary |
|---|---|---|
| 407 | 02:32 | with the cache |
| 408 | 02:35 | with the cache, repeated for the noise |
| 409 | 02:37 | the 0109 binary rebuilt from `bc5LleAgc.cpp.before-0111` |

**Result.**

| run | binary | menu fps, 90–120 s | median frame | intro fps, 28–40 s |
|---|---|---|---|---|
| 403 (0109) | 0109 | 49.1 | 19.4 ms | 52.1 |
| 407 | cache | 46.2 | 20.8 ms | 44.9 |
| 408 | cache | 46.1 | 20.7 ms | 44.0 |
| 409 | 0109 | 48.7 | 19.7 ms | 43.5 |

- No failed jobs and no GPU faults.
- Temperatures at the end were normal: GPU 54 °C, CPU 66 °C, and the governor logged no
  throttling.

**Verdict.** Failed: with the cache the menu is about 2.5 fps slower, twice in a row, while the
unchanged binary repeats its 49 fps. The reason is not known; the function-local statics add a
guard check per call, which cannot plausibly cost that much. The intro numbers vary more between
runs than the menu's and decide nothing. Reverted: the host source again matches the committed
patch of experiment 0109 (`git diff` compared byte for byte), and the binary is rebuilt from it.
Lesson: changes on this path are measured against a fresh baseline run, not the number from
earlier in the night.
