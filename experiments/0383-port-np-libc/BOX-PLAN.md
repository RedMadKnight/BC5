# 0383: the Linux check of PORT-NP and PORT-LIBC

The laptop cannot compile the full `libC.cpp`, link the host or run on Linux. This is the CPU-only plan for that. It needs
its own slot from the top session and Codex's decision on the current commit and archive; the B loop's GO does not cover
it. The runner was hardened after Codex's review `REVIEW-PORTS-01`, and `test_runner_port.py` tests it on the laptop.
The first run stopped early on the box's locale and compiled nothing (README, `raw/box1-boxcheck.txt`), so the check itself
has not been done. It kept `~/bc5-work/exp0383/tree` and `raw/`; the next run works in `~/bc5-work/exp0383/run2/`.

**What runs.** `boxcheck_port.sh`, from the unpacked archive, on the box, about 15 minutes at nice 19. No emulator, no
GPU, no root, no `drop_caches`. It writes only under `~/bc5-work/exp0383/run2/` and its own BOX-LOCK line, which it clears. It runs in the C locale.

**Pins.** `pins.env` holds them, and no variable overrides them: a new pin is a new commit and a new review.

| pin | value |
|---|---|
| patch 0001 md5 | `00a296dac4a5b3f73b66302afafba317` |
| patched `src` tree | `7fab373ac309cf05b0f666dd8152601756d2df3d` |
| shared normal binary, full md5 | `58c4a627d23b06e25c2868249124f9c5` (exp 0380's `raw/runs/BL-after.txt`) |
| baseline `libC.cpp` sha256 | `d6f9d62f645a7c93aadc1c31eddfb5999f382561c3d00521b7e0dc8b16229ff4` |
| baseline `libNpCppWebApi.cpp` sha256 | `134e042802335d774292b5ee8cbe8efd669c11a50096484d73c1ad0ca6e9b800` |

| step | what | stops if |
|---|---|---|
| guards | no emulator running, empty lock, the patch, the shared binary and both baseline units at their pins, `~/bc5-work/exp0383/run2/tree` absent | any fails |
| tree | `git archive f266548` of `~/src/KytyPlus`, then `git apply --check` and `git apply` of the branch's patch | the apply fails, or the `src` tree is not the pin |
| exp 0372 | `grep -c 'exp 0372'` is 5 and `src/bc5/pad_audio_route.hpp` is there | either is not |
| shared tree | `diff -rq` of `~/src/KytyPlus/src` against the patched tree, because the other objects come from there | its output is anything but the two approved files, both differing; the rest is printed |
| compile | the two fixed units, and the same two from the shared tree as the warnings' baseline, with the shared build's flags from `ninja -t compdb` | an error |
| warnings | the units' warnings without line numbers, counted against the baseline, in `raw/warnings.txt` | any warning is new |
| link | a private `kyty_emulator` from the shared objects and the two fixed units; never run | an error |
| tests | `NpCppWebApiTests` (exp 0328, unchanged) and `LibcNidTests` through `InitAll` → `InitLibC_1` → `InitLibcInternal_1`, each needing rc 0, its final line and no `FAILED`; `NpAliasTests`, with ASan if it links and the tracker alone if not (the result line says which) | see the pass rule |
| NP cases | the listing must be exactly the 30 unique names of `np-cases.manifest`; one process per name; each needs rc 0, its own `ok` line and the final line | a listing that differs runs no case and fails |
| shared binary after | full md5 against the pin | it changed |

Recorded: toolchain versions, `raw/build.out`, the tree diff, `raw/warnings.txt`, the private binary's md5, and the shared
binary's md5 before and after.

**Pass.** Exit 0 and the last line `boxcheck: PASS`. That needs the build step's rc 0, its last line
`== PASS: ... np_alias_tests 30/30 ...` with 0 new warnings, and the shared binary unchanged. Anything else is a failure:
rc 5 the shared binary changed, rc 6 the build step failed, rc 7 rc 0 without the final line, rc 1 a stop.

**Synthetic tests (laptop).** `python test_runner_port.py` needs no SSH, compiler or box, and its rc 0 means all 35 checks
came out as expected (`raw/runner-tests.txt`). Part A runs `boxbuild_port.py`'s real `main()` with a stand-in executor; part B
runs the real `boxcheck_port.sh` in a temporary HOME with stand-in tools, a `diff` that speaks Polish outside the C locale as
the box's does, its own pins and a stub build step. So the real
compile, link and test runs are exactly what they do not cover.

**If it fails.** Stop, keep `~/bc5-work/exp0383/run2/`, and report. No retry and no change to a pin. A failure of `LibcNidTests` at
`InitAll` with a crash or an EXIT before its final line may be a side effect of running `InitAll` outside the emulator, not a
wrong table; that would be reported with the log, and the test changed only by a new commit and a new review. A stop at the
shared tree or at the baseline pins would mean `~/src/KytyPlus` is not `f266548` + main's patch; it gets reported, not
accepted.

**Rollback.** `rm -r ~/bc5-work/exp0383` and the unpacked archive. Nothing shared is touched.

**After a pass.** Patch 0001 on this branch is ready for Codex's integration decision. Merge, the shared patch, shared
builds and the launcher each stay separate decisions, and each needs the backup, exp 0372 and rollback statement the plan
asks for.
