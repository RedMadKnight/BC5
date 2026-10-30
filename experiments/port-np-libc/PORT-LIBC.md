# PORT-LIBC: three wrong NID registrations in `libC.cpp`

**Question.** The `LibcInternal` table of `src/libs/libC.cpp` has `strcmp` and `strncmp` swapped, and registers the
two-argument `strcpy` under `strcpy_s`'s NID. Does correcting the table give the right functions from the real
`SymbolDatabase`, with no `strcpy_s` alias left?

**Base.** PORT-NP's commit on `fix/port-np-libc`. `src/libs/libC.cpp` is a file patch 0001 changes, so the fix is in the
patch, in a hunk of its own.

**Provenance and licence.** KytyPS5 (KytyPS5/KytyPS5) commit `8c01d8e849f6f80bae585a838b1f1d6f317c6396` (2026-10-24,
author nmzik). At that commit `LICENSE` is GPL version 2 and `README.md` says `GPL-2.0-only`; the original Kyty's MIT
notice is kept in `LICENSES/Kyty-MIT.txt`. The change is three NID strings, facts of the public hash, and
`check_nids.py` recomputes them. A comment in the table names the commit.

**The change** (`InitLibcInternal_1`):

| NID | name by the public hash | before | after |
|---|---|---|---|
| `Ovb2dSJOAuE` | `strcmp` | `LibcInternal::strncmp` | `LibcInternal::strcmp` |
| `aesyjrHVWy4` | `strncmp` | `LibcInternal::strcmp` | `LibcInternal::strncmp` |
| `kiZSXIWd9vg` | `strcpy` | not registered | `LibcInternal::strcpy` |
| `5Xa2ACNECdo` | `strcpy_s` | `LibcInternal::strcpy` | **not registered** |

**`strcpy_s` needs a decision if it is ever imported.** The host has no `strcpy_s` wrapper, and none was added. With the
alias gone the NID is unresolved, so the linker stubs and logs an import of it (`RegisterStubbedImport`). Before, such an
import reached a two-argument wrapper with the size in `src`'s place. A real wrapper is a separate change with a size
and error contract.

**Export version.** The three registrations stay in the table they were in (`LibcInternal` v1, module 1.1), the table
KytyPS5's commit corrects in place. shadPS4 registers `strcpy_s` in `libSceLibcInternal` v1
(`src/core/libraries/libc_internal/libc_internal_str.cpp`, `60c42b9`). The four NIDs appear nowhere else in `src/libs`.

**Test.** `LibcNidTests.cpp` runs on the real `SymbolDatabase`. Each NID is looked up as the linker does, by `Find`
with the import's library and module and by `FindByNid`, which must agree, and is called through a SysV pointer of its
real type:

- the wrapper's address and record name;
- `strcmp` and `strncmp` on strings differing past `n`, the sign of the result, equality, and the boundary at `n`;
- `strcpy` returns `dest`, copies the terminator and leaves the guard bytes;
- `strcpy_s` is not found by any of the lookups;
- two neighbours, `strlen` and `strncpy`, are unchanged.

`check_nids.py` is the independent check: it recomputes names from the public hash, parses `src/libs`, and requires
each of the four NIDs in one place only.

**Result on the laptop (2026-10-30).**

Toolchain: as in `PORT-NP.md`. libC.cpp as a whole needs submodules the laptop lacks, so `run_libc_laptop.py` cuts the
real `namespace LibcInternal` (wrappers and table, byte for byte) out of the tree and starts from `InitLibcInternal_1`.
The path through `InitAll` and `InitLibC_1` is in `BOX-PLAN.md`.

```text
python run_libc_laptop.py before <tree before> <out>   rc 1, 13 checks fail
python run_libc_laptop.py after  <host tree>   <out>   rc 0, all checks pass
python check_nids.py <tree before>                     rc 1, the four NIDs wrong
python check_nids.py <host tree>                       rc 0
```

- Before, the failures are the three bindings, `strncmp` ignoring its limit, `strcpy` unresolved and `strcpy_s`
  resolving (`raw/libc-before.txt`). After, all pass (`raw/libc-after.txt`).
- `check_nids.py` also lists two table entries not under their wrapper's own name, both meant: `zlfEH8FmyUA` is
  `_Stoul` on the `strtoul` wrapper, and `al3JzFI9MQ0` is the wrapper `LibcHeapErrorReportForGame`, whose name is the
  host's own. Neither is in scope (`raw/nids-after.txt`).

**Limits.**

- Not yet the real `InitAll` path, the full `libC.cpp` compile or the Linux link: `BOX-PLAN.md`.
- `nid-check.py`, the review's script, asserts the old table, so `check_nids.py` replaces it for the new one.
- No claim that a title calls any of these: an import-resolution trace would be its own evidence. Nothing links this to
  F443, F403 or Q21. A title that imports `strcpy` from this table now gets the wrapper in place of a stub, and one that
  imports `strcpy_s` gets a stub in place of the wrong wrapper. Whether either title does is not known.

**Rollback.** `git revert` of this commit, which leaves PORT-NP in place.
