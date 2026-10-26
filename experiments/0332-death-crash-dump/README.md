# 0332 — the second title's crash when the character dies: what is in the handle list it walks?

*Number claimed by the cloud supervisor, 2026-10-26 (the maintainer chose "a i c", then "1": the build with the
extended crash dump).*

**Question.** When the maintainer's character died (2026-10-26 15:06, RT off), the title crashed. The site is a
null write at `eboot.bin+0x3ba1bdf`, in a loop that releases a list of 16-byte handle entries (F401). The element
comes from a bounds-checked lookup that yields null for an out-of-range index, and the first entry held garbage:
table 0xcae, element index 0x2064cd3 (~34 M). What is in that list, where does it live, and does the garbage look like
some other kind of data (floats, pointers, GPU output as in F360)? That tells us whose write to chase. And does every
death crash?

**Known before this experiment.**
- **The crash site** (F401). The code was read on the box from the fake-signed SELF's executable segment, as KytyPlus's
  `elf.cpp` maps it; per exp 0318's rule no code bytes or disassembly are kept here.
  - The loop takes the list through `[rbp-0x38]` and then `[[rbp-0x38]]`, and its count through `[rbp-0x2c]`.
  - Each entry gives a table number (16 bits), an element index (32 bits) and a byte that picks one of two table
    groups. The groups hang off the object in rbx (+0xa068 / +0xa070).
- **The existing crash dump** has the registers and 8 qwords behind each, the code around RIP, 16 stack slots and the
  stack trace (exps 0318, F383). It does not reach the list.
- **Not the cause:** the "recent stubbed import" lines are link-time stubs. No session called the ten NpCppWebApi stubs
  (F401's correction).

**Setup.**
- **`patch0332.py`** makes `patch_0332.diff` against the tree's `src/loader/runtimeLinker.cpp` (md5 f294dfc2): one
  block after the register dump in `KytyExceptionHandler`. It dumps:
  - the faulting function's stack frame, `rbp-0x80 … rbp+0x18`;
  - for every slot that points to readable memory above 4 GB, 8 qwords there;
  - when that memory's first qword points on, 32 qwords at it. That is the list at `[[rbp-0x38]]` (16 entries).

  Every read is checked with the file's `IsReadableRange`. It runs at crash time only, so it has no switch.
- **Checked offline:** the block compiles in a stand-in harness with g++ and clang (`-std=c++20 -Wall -Wextra
  -Wformat=2 -Werror`), and the file's brace and parenthesis balance is unchanged.
- **The private build:** `run0332.sh build` compiles that one unit with the shared flags (`build0332.py`, from a fresh
  ninja compdb). It links `~/bc5-work/exp0332/kyty_emulator` from the shared normal build's objects (4a146894) and exp
  0330's `bc5LleAgc.cpp.o`, so the test shortcut keeps the 0330 memory switches (the import table and zero scan at
  530/540 s, the journal DONTNEED).
- **The shortcut:** `run0332.sh shortcut` points the test shortcut's host wrapper at this binary (one `BC5_EMU=`
  line) and renames the shortcut "BC5 emulator (test 0332: crash przy śmierci)". It was tried on stand-ins first. The
  sampler beside each session stays.
- **The maintainer's part:** play with RT as in his `input.cfg` (off since 14:31) until the character dies.

**Readings.**
- Did it crash at the death, and at the same site?
- The frame, the list's address and its 16 entries: are they handles or something else?
- The list's address relative to the heaps that exp 0330's breakdown names (the import table's spans): which
  allocator owns it?

**Plan.** If the list lives in memory the GPU can write (an imported direct-memory heap), the next step is a write
trap on its page during play (exp 0313's method). If it lives in CPU-only memory, the next step is the host functions
the title calls on death.

**Built (2026-10-26 15:49).**
- `run0332.sh build` produced `~/bc5-work/exp0332/kyty_emulator`, **acb1cfd7**, in 16 s (`raw/build.out`, `raw/build-inputs.txt`).
  The patch output is 9eb84730, the same as on the laptop. The two warnings are the tree's own: `stringUtils.h`'s
  deprecation, and the handler's older `EXIT` lambda at line 885, which predates this block.
- `run0332.sh shortcut` pointed the test shortcut's wrapper at the new binary: `test0330p.sh` 7ce287ad → 04fbe2cf
  (`raw/test0330p-0332.diff`). It renamed the shortcut "BC5 emulator (test 0332: crash przy śmierci)"
  (`raw/shortcut.out`). The undo is in `~/bc5-work/exp0332/shortcut-before/`.

**Result.** Pending: the maintainer's play to the character's death.
