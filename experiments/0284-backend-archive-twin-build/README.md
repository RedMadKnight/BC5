# 0284 — The shared builds' backend archive is byte-identical to a fresh build of `backend/` on main

**Question.** Both shared builds link `~/bc5-work/backend-ubuntu/libbc5_backend.a`, built 2026-10-19 16:37, and `ninja -n` in that build directory wants 15 steps (Q19). F345 showed that the archive already holds F225's code (`Device::Impl::shared_disjoint_locked`, commit f7ba38f), the only backend commit later than the build. Does a fresh build of today's `backend/` give the same archive, so that a rebuild would change nothing?

**Setup.** Top session, 2026-10-24 23:10–23:11, under its own BOX-LOCK line, no emulator, `nice -n 19`.
- Source: the box's checkout `~/src/bc5` at 1853b14 (main's backend unchanged since f7ba38f).
- A twin build directory `~/bc5-work/exp0284/build`, configured like the shared one: Ninja, Release, `-O3 -DNDEBUG`, `clang++` (Ubuntu clang 21.1.8 in the `ubuntu` distrobox), `BC5_WITH_AMDGPU=ON`, `BC5_BUILD_TESTS=OFF`. Built with `cmake --build … --target bc5_backend -j4`.
- The shared build directory was not touched.
- Comparison: `cmp` of the two archives, then `ar x` of both and per member an md5 of `objdump -d --no-show-raw-insn` and of the `.rodata` dump (`raw/compare.txt`).

**Result.**
- The fresh archive is **byte-identical** to the shared builds' one: both 273,302 bytes, md5 `549892e8db26…`, `cmp` equal.
- All nine members (`version`, `pm4`, `dispatch_min`, `policy`, `state_stack`, `full_state`, `cu_tables`, `indirect_check`, `direct`) have identical code and read-only data.
- So ninja's 15 pending steps are file times from the 2026-10-23 re-checkout, not content.

**Verdict.** Q19 is answered: the shared builds' backend archive is exactly today's `backend/` on main. Any later backend change (exp 0052's check, a `policy.cpp` refusal, a breadcrumb probe in `indirect_check`) can be rebuilt into the shared archive as an ordinary integration step, without bringing in anything else. The twin build stays in `~/bc5-work/exp0284/` for reuse.
