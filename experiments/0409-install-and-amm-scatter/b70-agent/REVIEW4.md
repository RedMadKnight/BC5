# Review round 4 (Claude, top session)

Good: the script is small (155 lines), the helpers live only in pool0401_impl.inc, all 8 test groups pass, there are
no warnings, and the rerun exits 1.

Still wrong (blocking):
1. **Wrong input.** The script requires md5 8cabcfd7, which is the OLD script's output, and edits the old scatter block.
   It must take the ORIGINAL file, e8/x-amm/src/libs/libAmpr.cpp (md5 0a1762f6), which has no scatter code at all.
   So:
   - EDIT 1 inserts HOOKS + markers + the .inc before `static bool AllocateAmmAutoDirectMemory` (match exactly once);
   - EDIT 2 changes the original EAGAIN return at the AllocateAmmAutoDirectMemory call site (match exactly once);
   - the switch reader Bc5AmmScatterMode() goes into the .inc or HOOKS.
   Find those two spots by reading the original file. Test: `python3 work/mkpool0401.py e8/x-amm/src/libs/libAmpr.cpp
   /tmp/out` must succeed.
2. **The .inc path.** It is read from out_dir. Read it from the script's own directory
   (`os.path.dirname(__file__)`).
3. **Modes at the call site.** `journal` (1) must only LOG and still return EAGAIN; `rescue` (2) scatters only on
   EAGAIN; `first` (3) scatters first. Today `mode >= 1` scatters in journal mode.
4. **Exactly-once checks.** Each edit must assert that its anchor appears exactly once in the input. Exit 1 otherwise.
5. **Hooks must exist.** Check that every function the HOOKS call (KernelSetVirtualRangeName, bc5_watch_surface,
   AmmTraceStamp, ...) exists in the original libAmpr.cpp or memory.cpp. Grep for each, and remove any hook nobody
   uses.
6. **Second run.** Detect it by the BEGIN marker (if it is present: "has the edit already", exit 1), not by md5.

Done when, from a clean /tmp/out:
- the run on the original succeeds;
- the marker byte-equality check passes on that output;
- the second run exits 1;
- the test passes;
- `g++ -std=c++20 -fsyntax-only` over the patched libAmpr.cpp is attempted with `-I ref/kytyplus/src -I ref/kytyplus/src/include`.
  Report the first errors if it does not compile; missing third-party headers are acceptable.
Commit.
