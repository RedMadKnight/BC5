# 0383 — Host fixes from the upstream review: NpCppWebApi self-aliasing and three libc NIDs

**Date.** 2026-10-30. **Branch.** `fix/port-np-libc`. **Box.** None so far; everything here ran on the laptop.
Both fixes are default behaviour of the host library, so neither has a switch.

**Question.** Do the fixes from AnyPS5 `daf4eb3` and KytyPS5 `8c01d8e`, ported into patch 0001, correct the host's
self-aliasing in NpCppWebApi and its three wrong libc NID registrations, without changing layout, ownership or the exp
0328 tests, and without an alias for `strcpy_s`?

**Setup.**

- Base: main `65f13dd`, backend tree `437a0d5a`, KytyPlus `f266548` + patch 0001 (md5 `9420cfa0`). The scope, acceptance
  criteria and stop rules are Codex's upstream review plan, `PORT-PLAN.md`, kept outside this repository.
- Commits: `d3fe5b5` (NP), `167062a` (libc). The directory was then renamed from `port-np-libc`, so `raw/` logs and the two
  commits show the old name. The test sources have not changed since `167062a`.
- Patched tree: `f266548` + the final patch, with `src` tree `7fab373a` and patch md5 `00a296da`. Rebuild it with
  `git -c core.autocrlf=false archive`, or the laptop's global setting rewrites the line endings. Regenerating patch 0001
  from that base was first shown byte-identical to main's, so the patch delta holds only these two changes.
- Laptop toolchain: clang 22.1.3 of Visual Studio 18 (x86_64-pc-windows-msvc, so `KYTY_SYSV_ABI` is the real SysV
  attribute), `-std=c++20 -O1 -g -fsanitize=address -Wall -Wextra`, Python 3.14. Host headers that need submodules come
  from `laptop-shim/`; `common/abi.h` and `loader/symbolDatabase.*` are the real ones.
- Details: [`PORT-NP.md`](PORT-NP.md) and [`PORT-LIBC.md`](PORT-LIBC.md) hold the provenance, the licence check, the
  change, the tests and the commands for each fix. [`BOX-PLAN.md`](BOX-PLAN.md) is the Linux check.

```text
python run_np_laptop.py <label> <dir with libs/libNpCppWebApi.cpp> <host tree> <out>
python mutate_np.py <fixed unit> <host tree> <out>
python run_libc_laptop.py <label> <host tree> <out>
python check_nids.py <host tree>
```

**Result (laptop).** Logs in `raw/`.

| check | before | after |
|---|---|---|
| `NpAliasTests`, 30 cases, one process each | 9/30, rc 1: ASan heap-use-after-free, memcpy-param-overlap | **30/30, rc 0** |
| exp 0328's `NpCppWebApiTests`, unchanged | rc 0 | rc 0 |
| mutants of the fix | | 7 of 7 caught |
| `LibcNidTests` on the real `SymbolDatabase` | 13 checks fail, rc 1 | **all pass, rc 0** |
| `check_nids.py`, independent of the C++ | rc 1, the 4 NIDs wrong | rc 0 |

- Both vectors' use-after-free, a code reading in the review, is shown here by test with a forced move.
- On a tree built only from `f266548` + the final patch, the results are the same, with 0 compiler warnings.
- `exp 0372` count 5 and `pad_audio_route.hpp` are kept.
- Each commit reverts alone (tested in a throwaway clone), and the patch applies after either revert.
- `strcpy_s` stays unregistered: the host has no wrapper with its size and error contract, so an import of it is stubbed
  and logged. A real wrapper is a separate request.

**Not shown.** The Linux compile with the shared flags, the host link, the path through `InitAll` and `InitLibC_1`, and the
Linux run. Nothing shows a title calling these paths, and nothing here links to F443, F403 or Q21.

**Verdict.** Inconclusive until the Linux check in [`BOX-PLAN.md`](BOX-PLAN.md) has run: the laptop results pass, but the
acceptance needs that check. This section is to be finished then, and the directory is not frozen before it.
