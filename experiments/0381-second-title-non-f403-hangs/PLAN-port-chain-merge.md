# PORT-CHAIN: integration and rollback

A plan for the merge decision (Codex's, then the top session's). Nothing is merged. Checked on 2026-10-30 against main e0d33d2.

## Which commit

`fix/port-chain` has two commits on main 65f13dd:

| Commit | Backend tree | What | clang on Linux | MSVC laptop |
|---|---|---|---|---|
| e00f084 | 89121f6b | the fix, its tests, F760 and F761 | **passed**, `raw/port-chain-linux/` | passed, Debug and Release |
| ce46317 | 909f6832 | one test section and one comment (+8/-1), no logic | **not run** | passed, Debug |

**Recommendation: merge ce46317 (the tip), after one clang re-run of ce46317.** The change since the pass is small, but the
acceptance names clang, and the test is the one Codex asked for. The run is `pcrun0381.sh ce46317`, about 3 minutes, CPU only;
it needs a slot and the maintainer's go, and it records `selftest-1.log`, `selftest-2.log` and the archive md5.
If the re-run should wait, merge e00f084 and bring ce46317 in after its own run. Do not merge ce46317 and call it the tree that
passed.

## Conflict points

`git merge-tree` of origin/main e0d33d2 and ce46317 is clean (result tree 8763b43d). Main moved 7 commits since 65f13dd, with
its backend tree unchanged at 437a0d5a, and neither `acb_restore.hpp` nor its test changed there. Files touched:
`backend/include/bc5/acb_restore.hpp`, `backend/tests/acb_restore_test.cpp`, `docs/HANDOFF.md`.

Run the same check again at merge time: the likely conflict is `docs/HANDOFF.md`, if a later branch adds rows after F704.

## HANDOFF numbering

F760 and F761 go in after the last row (F704 on main today). The range F760-F769 is this task's. F762 onward is reserved for
the walkers plan (`PLAN-chain-walkers.md`). F761 says what the tracker *would* do; Codex's dynamic reproduction, which reaches
`emit_prefix`, is recorded there and in the plan, and should go in as F762 with that plan's decision. No renumbering needed.

## What changes, and what does not

- **Patch 0001: unchanged.** Neither it nor anything in `backend/src` includes `acb_restore.hpp` at this commit
  (`git grep acb_restore e00f084 -- backend/src backend/kytyplus-patches backend/experiments`: no hits).
- **`libbc5_backend.a` and the shared builds: unchanged**, for the same reason. No rebuild, and no D19 step. Only the test
  binary changes.
- **`play-pkg.sh`, shortcuts, switches: unchanged.**
- **Private test build 4c686b5b:** it holds its own older copy of the header, so it keeps the old `final_value`. That only
  affects a journal line under `BC5_DIRECT_DISPATCH_JOURNAL`. A later rebuild takes the new one by itself.
- **The restore's integration (patch0381 diffs)**, if it comes later, picks up this header. The API is the same, so those diffs
  do not change.
- **Not fixed by this merge:** F761, the tracker's CHAIN gap. No claim on F443 or Q21.

## The merge

The top session runs this, in the integration checkout:

```bash
git fetch origin
git merge --no-ff origin/fix/port-chain -m "merge: fix/port-chain (PORT-CHAIN, F760-F761)"
git diff --stat HEAD^1 HEAD
```

Expect exactly the three files above. Then, on the merged tree, the full Catch2 and subsets through a runner that enforces rc
and no-tests, on clang. `direct-selftest` without `--submit` only if the merged backend tree differs from the tree already run.

## Rollback

```bash
git revert -m 1 <merge commit>
```

This removes the fix, its tests and F760-F761 together; nothing else depends on them. No box step, rebuild or shared-file
change. If only ce46317 is wanted out: `git revert ce46317`. Leftovers to clear afterwards: `~/bc5-work/exp0381/pc` (private) and
the branch and worktree `bc5-port-chain`.
