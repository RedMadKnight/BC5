# 0383 — Host fixes from the upstream review: NpCppWebApi self-aliasing and three libc NIDs

**Date.** 2026-10-30. **Branch.** `fix/port-np-libc`. **Box.** CPU only, no emulator run and no GPU; the rest ran on the laptop.
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
python test_runner_port.py
```

- The box runner was hardened after Codex's review `REVIEW-PORTS-01`, which found that an empty case listing passed with
  exit 0, that the shared hash was printed and not enforced, and that `ACCEPT_TREE_DIFF=1` allowed any source diff. It also
  required final lines and a warnings baseline. `BOX-PLAN.md` has the new rules, and `pins.env` the pins.

**Result (laptop).** Logs in `raw/`.

| check | before | after |
|---|---|---|
| `NpAliasTests`, 30 cases, one process each | 9/30, rc 1: ASan heap-use-after-free, memcpy-param-overlap | **30/30, rc 0** |
| exp 0328's `NpCppWebApiTests`, unchanged | rc 0 | rc 0 |
| mutants of the fix | | 7 of 7 caught |
| `LibcNidTests` on the real `SymbolDatabase` | 13 checks fail, rc 1 | **all pass, rc 0** |
| `check_nids.py`, independent of the C++ | rc 1, the 4 NIDs wrong | rc 0 |
| `test_runner_port.py`, the runner on synthetic cases | | 35 of 35 as expected, rc 0 (`raw/runner-tests.txt`) |

- Both vectors' use-after-free, a code reading in the review, is shown here by test with a forced move.
- On a tree built only from `f266548` + the final patch, the results are the same, with 0 compiler warnings.
- `exp 0372` count 5 and `pad_audio_route.hpp` are kept.
- Each commit reverts alone (tested in a throwaway clone), and the patch applies after either revert.
- `strcpy_s` stays unregistered: the host has no wrapper with its size and error contract, so an import of it is stubbed
  and logged. A real wrapper is a separate request.

**First box run (2026-10-30 14:44–14:45, Codex's GO, the maintainer's yes).** It stopped with rc 1 at the shared-tree step, before
any compile (`raw/box1-boxcheck.txt`). Passed first: the archive's hashes, the patch, the shared binary, both baseline units,
`git apply`, the `src` tree pin and exp 0372's pieces. The box's locale is pl_PL, so `diff -rq` printed "Pliki ... różnią się"
where the script compared with English. The output named the two approved files and nothing else, so the stop was the
runner's, not the tree's. Nothing shared changed, and the shared binary's md5 was the pin afterwards. The script and the
build step now run in the C locale, and a Polish stand-in `diff` reproduces the stop on the old script and passes on the new.

**Second box run (2026-10-30 19:00–19:01, commit `4968372`, Codex's GO, the maintainer's yes).** `boxcheck: PASS`, exit 0, in
54 s (`raw/run2-*`). The archive's full hashes matched before and after the transfer. Ubuntu clang 21.1.8, kernel 7.2.9.

| check | result |
|---|---|
| patched tree | `src` tree is the pin; exp 0372's 5 lines and header there; only the two approved files differ from the shared tree |
| compile | the two fixed units and their baselines, with the shared build's flags |
| link | a private `kyty_emulator`, md5 `269c5569b12b2301335fd5567e1bfd45`, never run |
| `NpCppWebApiTests` (exp 0328) | rc 0, final line seen |
| `LibcNidTests`, through `InitAll` → `InitLibC_1` → `InitLibcInternal_1` | rc 0, final line seen |
| `NpAliasTests` | 30/30 manifest cases, one process each, **without ASan** |
| shared binary | `58c4a627...` before and after; lock empty and no process of ours left afterwards |

Two things the PASS line does not say:

- **ASan did not run on Linux.** The box's clang has no `libclang_rt.asan*.a`, so `NpAliasTests` fell back to its tracker, as
  the plan allows. The use-after-free proof is the laptop's; the box adds the Linux build and the tracker's exact counts.
  No unfixed tree was run on Linux, so a before/after exists on the laptop only.
- **The runner's warnings gate did not work.** `-fcolor-diagnostics` in the shared flags put colour codes in the compiler's
  lines, its pattern matched none, and "new warnings 0 of 0" says nothing. The test programs hid this because synthetic
  output had no colour. `recount_warnings.py` recounted from the same log with the codes removed: baseline 4, fixed 4, new
  0 (`raw/run2-warnings-recount.txt`), and each of the four is an existing warning. The gate in `boxbuild_port.py` stays as it
  ran; it needs that fix before it is used again.

**Not shown.** The fixed paths in the emulator itself, since the private binary was not run. Nothing shows a title calling
these paths, and nothing here links to F443, F403 or Q21.

**Verdict.** Supported. The self-aliasing and the three NID registrations are fixed in patch 0001, with the acceptance tests
passing on the laptop (with ASan) and on Linux (compile, link, `InitAll`, tests, without ASan), and with no new warning by the
recount. Integration is not decided here: the plan for it goes to Codex separately, and merge, the shared patch, shared
builds and the launcher each stay separate decisions.
