# PROMPT.md — how to drive Claude Code on BC5

Copy the prompt for the situation you are in. Each prompt assumes Claude Code is started in the repository root, so `CLAUDE.md` is loaded automatically. Prompts are in English because the repo is; write follow-ups in whatever language you like.

**Where the project stands (2026-10-24).** Gates G1b, G2 and G3 are recorded as passed in `docs/PHASES.md`. Track B, the KytyPlus host with BC5's direct GPU path (patch `backend/kytyplus-patches/0001-bc5-lle-agc.patch`), plays ASTRO BOT and the second title on the BC-250. The work is now driven by play: the maintainer plays, reports what he sees, an experiment explains it, and a fix goes into the two shared builds once he agrees. Status and numbers: `README.md`. Findings F1–F333 and open questions: `docs/HANDOFF.md`.

## 1. The supervisor ("top") session

One session owns the BC-250 box, grants access to it and commits to `main`. Start it with:

```
You are the BC5 top session: the supervisor of the BC-250 box (ssh bc250). Read CLAUDE.md, README.md, the last 30 rows of docs/HANDOFF.md §2 and ~/bc5-work/BOX-QUEUE before doing anything.

Your rules:
- Box access: one GPU workload at a time. A session asks with "BOX REQUEST" (what, how long); you answer GO, add a line to ~/bc5-work/BOX-QUEUE, and the session writes one line to ~/bc5-work/BOX-LOCK while it runs and removes it after. A lock line that starts "MAINTAINER PLAYING" means nobody touches the box, not even reads. Every box command starts with a guard: stop if a kyty_emulator runs without a lock line of your own.
- Experiment numbers are claimed in both places at once: experiments/NNNN-name/ in the repo and ~/bc5-work/expNNNN on the box. F-numbers are handed out by you, in order.
- Watched GPU runs stream the kernel log to the laptop (ssh bc250 journalctl -k -f -n 0 -o short-precise | tee <file>); on a machine-down the box's own journal loses the last minutes.
- The second title's saves: check them before and after every run with
  cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16
  Runs take a fresh snapshot at their start and restore to it; never restore to an old fixed copy, it would roll back the maintainer's progress.
- Side sessions send "final"; you review their write-up, add or check the HANDOFF row, redact private data (serial numbers, IP addresses), commit with a conventional message and push. Side sessions do not push to main.
- Shared builds (normal ~/bc5-work/kytyplus-build, lean ~/bc5-work/kytyplus-build-lean) change only with the maintainer's yes; see section 4.
- Standing policy from the maintainer: if an experiment gives a speed-up with no regression, the change goes into use even when the root cause of the bug is not found.

Report to me in Polish, briefly, and act on your own between my messages.
```

## 2. A side session for one problem

```
Investigate <what the maintainer saw, where, when, which build>. You are a side session of the BC5 top session (<its session id>); it owns the box.

Start read-only and offline: docs/HANDOFF.md (search for the F-rows on this subject), the logs and journals under ~/bc5-work/play-review-* or ~/bc5-data/captures/play-<date>-<time>/ (copy what you need once, then work on the laptop). Ask the top session for an experiment number and claim it in both places.

For anything on the box beyond a small read, send the top session a BOX REQUEST with what it does and how long it takes, and wait for GO. Use a unique run tag, a lock line of your own, and a kernel stream that ends itself when your lock line is gone.

A fix is a diff in your experiment directory, against the shared tree's file md5s, syntax-checked or built privately (one or two units compiled with the shared build's flags and relinked into ~/bc5-work/expNNNN/kyty_emulator, the pattern of experiments 0252, 0267, 0272). Never write the shared tree or the shared builds.

When done, write experiments/NNNN-name/README.md (Question, Setup, Result, Verdict), add one HANDOFF row if the top session asks you to, and send "final" with the file list and a suggested commit message.
```

## 3. Playing

Phrases the maintainer uses with the top session, and what they do:

- `Gram teraz (<build>, <title>, <pad>)`: the top session waits for any run to end, writes `MAINTAINER PLAYING | …` to BOX-LOCK and tells every side session to keep off the box, reads included.
- `Koniec` plus what he saw (hitches with the time and place, freezes, sound, textures, rumble): the top session releases the lock, checks the saves, routes each observation to the session that owns that subject and resumes the queue.
- A test on a private build: the top session starts it over ssh (`systemd-run --user … play-…sh`, with `BC5_EMU` pointing at the private binary and the traces on), the maintainer plays and reports, the owning session reads the log.

## 4. Putting a fix into the shared builds

```
Integrate experiment NNNN's diff into both shared builds (the maintainer agreed: "<his words>").

Wait until the box has been free for 60 s. Check the md5s of the tree's files against the diff's base and of the shared normal binary. Write your lock line. Back up the tree's files and both binaries into ~/bc5-work/expNNNN/integration/. Copy the patched files in without -p (ninja must see a new mtime), then build both:
  distrobox enter ubuntu -- nice -n 10 cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8
  distrobox enter ubuntu -- nice -n 10 cmake --build ~/bc5-work/kytyplus-build-lean --target kyty_emulator -j8
Record the new md5s, check the new strings are in both binaries, remove the lock.
Regenerate main's patch with: cd ~/src/KytyPlus && git add -N . && git diff f266548
Compare it per file with the old one (only the intended files may differ), commit it with a HANDOFF row and the README tables (on-by-default list, key switches), and push.
```

## 5. After a machine-down

```
The box went down at <time> during <run>. I power-cycled it.

Before anything else: list the boots (journalctl --list-boots; the crashed boot is often not -b -1), restore the second title's saves from the run's own snapshot and verify the checksum, set the crashed live copy aside instead of deleting it, and clear the dead lock line. Then collect: the laptop's kernel stream, the timeout probe's synced records under ~/bc5-data/captures/play-<date>-<time>/gc/, and any GPU coredump in ~/bc5-data/captures/devcoredump/ (saved by the maintainer's udev rule; it exists only if the driver got as far as recovery). Hand them to the session that owns the hang. No new run until the cause has been read.
```

## 6. Any code path that submits to the GPU

```
Before any code path that submits to amdgpu: confirm the --submit flag is default off, that tests never set it, that the experiment README names the risk (a GPU reset can take the whole machine down), and ask me to confirm the machine is idle and my work is saved. Then proceed.
```

## Follow-up phrases that work well

- `Record this as experiment NNNN with the template, verdict included.`
- `Update docs/HANDOFF.md: move Qn to Findings with the source you used.`
- `Explain the trade-off in an ADR before implementing.`
- `Show me the diff and the test output before committing.`
- `Review all sub-sessions, including the ones marked finished; is any of them waiting on something?`
- `Prepare it as a private build first; I will test it when you tell me.`
- `First the analysis, then integrate.`

<details>
<summary>The bootstrap prompts of phases 0a–1 (2026-09, kept for reference)</summary>

### 0. First session — bootstrap the repository

```
Read CLAUDE.md, README.md, docs/HANDOFF.md and docs/PHASES.md before doing anything.

Bootstrap this repository:
1. git init (main branch), add .gitignore for Rust, C++/CMake, FUSE mountpoints, *.ffpfsc, *.exfat, *.img, experiments/**/raw/ larger than 1 MB.
2. Add LICENSE (GPL-2.0 full text) and a short CONTRIBUTING.md that repeats the hard rules from CLAUDE.md in two paragraphs.
3. Create the Rust workspace under tools/ with an empty bc5-mount crate (bin + lib), clippy and fmt configured, one placeholder test.
4. Create backend/ with a CMake skeleton (C++20, warnings as errors, Catch2 via FetchContent, .clang-format) and one placeholder test. It must build without libdrm present (option BC5_WITH_AMDGPU default OFF).
5. Add docs/decisions/0001-project-scope.md and 0002-languages.md as ADRs summarising D1-D6 from HANDOFF.md.
6. Add experiments/README.md explaining the NNNN-name layout and the Question/Setup/Result/Verdict template, plus experiments/TEMPLATE.md.
7. Make one commit per step with conventional messages.

Do not write any format parser yet. At the end, list the commands you ran and anything you could not verify.
```

### 1. Phase 0a — format research

```
Phase 0a, step 1 (docs/PHASES.md). Goal: docs/formats/ffpfsc.md.

Study the public implementations named in docs/HANDOFF.md F8 (pearlxcore/PS5PKGTool managed PFS, PFSC and exFAT; the FFPFS CLI referenced by PS5-FFPFSC-PRO; thanhsondev/PSVIETHOA-FPKG-Builder release notes). Clone only public source repositories; never download any .ffpfsc, .pkg or game files.

Write docs/formats/ffpfsc.md describing, with a source citation (repo, file path, commit) for every field:
- the PFS v2 superblock, block size, inode and directory entry layouts, and how the single inner file is located;
- the PFSC framing (block table, compression algorithm, block size, how uncompressed blocks are marked);
- the exFAT image inside (only what we need for read-only traversal);
- a "what we do not know yet" section.

Then write docs/decisions/0003-ffpfsc-fixture-strategy.md: how we will build synthetic containers for tests (fpkg-cli if it is open source and runs on Linux; otherwise our own writer), and what the minimal fixture set is (empty dir, one small file, one file > 64 KiB spanning blocks, deep directory tree, 1 GB sparse case).

Stop after the docs; do not implement readers yet. Flag any license that would block porting code.
```

### 2. Phase 0a — implementation

```
Phase 0a, steps 2-5. Implement bc5-mount per docs/formats/ffpfsc.md and ADR 0003.

Order, one commit each with tests:
1. tests/fixtures: synthetic container generator (library + `cargo run --bin bc5-fixture`). Fixtures generated at test time, never committed.
2. pfs reader (superblock, inodes, dirents, block map) with unit + proptest tests.
3. pfsc reader with a block cache; round-trip tests against the generator.
4. exfat read-only reader (boot sector, FAT, directory entries, file streams).
5. fuser-based mount: `bc5-mount <container> <mountpoint>`, read-only, plus `bc5-mount inspect` and `bc5-mount verify` (SHA-256 per file).
6. experiments/0002-bc5-mount-gate: script that builds a fixture, mounts it, compares the tree and hashes with the source dir, measures sequential read throughput. Fill Question/Setup/Result/Verdict.

Constraints: cargo clippy -D warnings and cargo fmt --check clean; no unsafe outside the FUSE glue; every parser rejects malformed input with an error, never panics. Ask before adding any dependency other than fuser, anyhow, thiserror, proptest, sha2, clap, memmap2.
```

### 3. Phase 0b — RPCSX baseline (run on the BC-250, inside the fedora distrobox)

```
Phase 0b. First create experiments/0003-dev-box-inventory and record: uname -a, distro, glxinfo -B, vulkaninfo --summary (device name, driver, apiVersion), pkg-config --modversion libdrm_amdgpu, lspci -nn for the GPU and PSP (1022:143e), free -h, disk type and free space, and whether dmesg mentions the BC-250 PSP/CCP patches. Do not change any system setting.

Then build RPCSX from its main branch following .github/BUILDING.md in this container, in ~/src/rpcsx. Record the commit hash, the exact commands, build time and any patches needed to build. Do not fetch firmware or games; I will provide the system software myself afterwards. Stop and report when the build succeeds or when you hit something you cannot fix without a system change.
```

### 4. Phase 1 — AGC decoder

```
Phase 1. Start with Q2 in docs/HANDOFF.md: read the RPCSX GPU sources in ~/src/rpcsx and write docs/formats/agc.md section "RPCSX AGC handling" (where DCB/CCB are received, how PM4 is parsed, where PS4 GNM and PS5 AGC paths differ, file paths with commit hash). Then scaffold tools/bc5-agc: a PM4 type-0/2/3 packet decoder with register-name resolution from Mesa's src/amd/registers gfx10 JSON (vendor the JSON with its license), tests with hand-built streams, and a report mode listing unknown opcodes and register offsets with counts. Do not touch backend/ yet.
```

</details>
