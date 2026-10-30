# PORT-NP: self-aliasing in NpCppWebApi's String and Vector helpers

**Question.** `Common::String::append` and the two `Vector::pushBack` helpers read their source after they free or move
the storage it may point into. Does a port of AnyPS5's fix close that in the real host source, without changing layout,
ownership or the exp 0328 tests?

**Scope.** Three helpers in `src/libs/libNpCppWebApi.cpp`, which exists only as a new file in patch 0001. The change is in
the patch, against a tree rebuilt from KytyPlus `f266548`. `experiments/0328-npcppwebapi-port/libNpCppWebApi.cpp` is the
old experiment's artefact and stays as it was. Plan: `PORT-PLAN.md` (Codex's upstream review, outside this repository).

**Base.** BC5 main `65f13dd`, backend tree `437a0d5a`, KytyPlus `f266548` + patch 0001 (md5 `9420cfa0`).

**Provenance and licence.**

- Source: AnyPS5 (boykopovar/AnyPS5) commit `daf4eb3518b0acefed3e2606c09bedef9b9a856b` (2026-10-29), merge of PR #9612 by
  Ondra97, file `core/libs/prx/libSceNpCppWebApi/Export.cpp`.
- Licence checked at that commit: `LICENSE` is GPL version 2, and `README.md` says "licensed under the GNU General
  Public License version 2 only". `Export.cpp` has no header of its own. That matches this tree's GPL-2.0-only.
- The three code changes are AnyPS5's, adapted to the tree's formatting. The unit's header names the commit.
- `NpAliasTests.cpp` is written here. It takes the test patterns from AnyPS5's tests at that commit and says so.

**The change** (patch 0001, `libNpCppWebApi.cpp`):

- `String::append`: when it grows, the text goes into the new buffer before the old one is freed, then it returns.
  Without growth, `memmove` replaces `memcpy`, because source and target can overlap.
- `VectorPushBackIntrusivePtr`: a copy of `*element` before `VectorGrow`; everything after it reads the copy.
- `VectorPushBackString`: the deep copy comes before `VectorGrow`, and a failed growth frees the copy.
- Structures, registrations and the ownership model are unchanged. The only other change in the unit is the provenance
  note in its header.

**Test.** `NpAliasTests.cpp` includes the real unit and sends its allocator calls to a tracker:

- every `realloc` moves the block, so the bug cannot hide behind a realloc in place;
- the n-th allocation can fail;
- leaks and bad frees are counted without depending on the sanitizer.

It has 30 cases, called through the title's mangled entry points:

| area | cases |
|---|---|
| `String::append` | the 40 + 39 reproducer; own buffer at offset 0 and at substrings, with and without growth; empty text, own terminator, exact fit, one byte past; repeated growth; every length to 130 at every offset; failed allocation |
| `Vector<IntrusivePtr>` | own element at each index with a forced move; all four `pushBack` instantiations; null element; 100 pushes; exact reference counts; one deleter call after the last owner; failed body, storage and growth; a sweep failing each allocation in turn |
| `Vector<String>` | the same, plus deep-copy independence, failed copy, failed growth, and no leak of the copy |
| layout | offsets of `IntrusivePtr` (0x18), `CommonString` (0x20) and `VectorBody` (0x50) |

**Result on the laptop (2026-10-30).**

Toolchain: clang 22.1.3 from Visual Studio 18 (x86_64-pc-windows-msvc, so `KYTY_SYSV_ABI` is the real SysV attribute),
`-std=c++20 -O1 -g -fsanitize=address -Wall -Wextra`, Python 3.14. The host's headers that need submodules come from
`laptop-shim/`. The real `common/abi.h` and `loader/symbolDatabase.*` are used.

```text
python run_np_laptop.py before <unit before> <host tree> <out>   rc 1
python run_np_laptop.py after  <unit after>  <host tree> <out>   rc 0
python mutate_np.py <fixed unit> <host tree> <out>               rc 0
```

| | before (patch 0001 at `65f13dd`) | after |
|---|---|---|
| `NpAliasTests`, one process per case | 9 of 30 pass | **30 of 30 pass** |
| ASan reports | heap-use-after-free, memcpy-param-overlap | none |
| exp 0328's `NpCppWebApiTests`, unchanged | passes (rc 0) | passes (rc 0) |

- The 21 failures before the fix are the bug itself, in `String::append` and in both vectors. `raw/np-before-summary.txt`
  lists each case and `raw/np-after-summary.txt` the result; `raw/np-before-string_repro_40_39.txt` is the ASan report.
- The vectors' failures confirm by test what the review had only read in the code.
- Two cases failed on the first run with the fix, because of my test's seed: 32 characters already take 64 bytes, so
  those appends did not grow. Seeding 31 characters fixed the test and left the unit alone.
- Seven mutants, each undoing one part of the fix in a copy, are all caught (`raw/np-mutants.txt`).

**Limits.**

- This is not the Linux host. The compile with the shared flags, the link and the Linux run are in `BOX-PLAN.md` and
  have not been done.
- No claim about the game: nothing shows the title makes an aliasing call, and nothing links this to F443, F403 or Q21.
- The tracker's `realloc` always moves. That is the test's purpose, and it says nothing about how often glibc would.

**Rollback.** `git revert` of this commit. It touches only patch 0001 and this directory's NP files. Shared builds,
the launcher and the shared patch are not changed by this branch.
