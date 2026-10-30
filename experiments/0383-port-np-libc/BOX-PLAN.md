# 0383: the Linux check of PORT-NP and PORT-LIBC (not run)

The laptop cannot compile the full `libC.cpp`, link the host or run on Linux. This is the CPU-only plan for that. It needs
its own slot from the top session, a GO from the maintainer, and Codex's review: the B loop's GO does not cover it. It has not been run.

**What runs.** `boxcheck_port.sh`, from the unpacked archive, on the box, about 10 minutes at nice 19. No emulator, no
GPU, no root, no `drop_caches`. It writes only under `~/bc5-work/exp0383/` and its own BOX-LOCK line, which it clears.

| step | what | stops if |
|---|---|---|
| guards | no emulator running, empty lock, patch md5 pinned, shared normal binary `58c4a627`, `~/bc5-work/exp0383/tree` absent | any fails |
| tree | `git archive f266548` of `~/src/KytyPlus`, then `git apply --check` and `git apply` of the branch's patch | the apply fails, or the `src` tree hash is not the pinned one |
| exp 0372 | `grep -c 'exp 0372'` is 5 and `src/bc5/pad_audio_route.hpp` is there | either is not |
| shared tree | `diff -rq` of `~/src/KytyPlus/src` against the patched tree, because the other objects come from there | anything differs beyond the two fixed files, unless `ACCEPT_TREE_DIFF=1` |
| compile | `libC.cpp` and `libNpCppWebApi.cpp` with the shared build's own flags, from `ninja -t compdb` | an error |
| link | a private `kyty_emulator` from the shared objects and those two; never run | an error |
| tests | `NpCppWebApiTests` (exp 0328, unchanged); `LibcNidTests` through `InitAll` → `InitLibC_1` → `InitLibcInternal_1`; `NpAliasTests`, one process per case, with ASan if it links and the tracker alone if not | a non-zero rc is recorded |

`EXPECT_NORMAL` pins the last shared binary this session read. If the shared build has moved on, the guard stops, and the
top session decides whether to pass the new md5. Recorded: toolchain versions, `raw/build.out`, the tree diff, the private
binary's md5, and the shared binary's md5 after.

**Pass.** rc 0, the three test programs pass, `np_alias_tests: 30/30`, the shared binary unchanged, and no warning new
to the two units.

**If it fails.** Stop, keep `~/bc5-work/exp0383/`, and report. A failure of `LibcNidTests` at `InitAll` with a crash or an
EXIT before the first check may be a side effect of running `InitAll` outside the emulator, not a wrong table; that would be
reported with the log, and the test changed only with the top session's agreement.

**Rollback.** `rm -r ~/bc5-work/exp0383`. Nothing shared is touched.

**After a pass.** Patch 0001 on this branch is ready for Codex's integration decision. Merge, the shared patch, shared
builds and the launcher each stay separate decisions, and each needs the backup, exp 0372 and rollback statement the plan
asks for.
