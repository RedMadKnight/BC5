# PROMPT.md — how to drive Claude Code on BC5

Copy the prompt for the step you are on. Each prompt assumes Claude Code is started in the repository root, so `CLAUDE.md` is loaded automatically. Prompts are in English because the repo is; write follow-ups in whatever language you like.

## 0. First session — bootstrap the repository

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

## 1. Phase 0a — format research

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

## 2. Phase 0a — implementation

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

## 3. Phase 0b — RPCSX baseline (run on the BC-250, inside the fedora distrobox)

```
Phase 0b. First create experiments/0003-dev-box-inventory and record: uname -a, distro, glxinfo -B, vulkaninfo --summary (device name, driver, apiVersion), pkg-config --modversion libdrm_amdgpu, lspci -nn for the GPU and PSP (1022:143e), free -h, disk type and free space, and whether dmesg mentions the BC-250 PSP/CCP patches. Do not change any system setting.

Then build RPCSX from its main branch following .github/BUILDING.md in this container, in ~/src/rpcsx. Record the commit hash, the exact commands, build time and any patches needed to build. Do not fetch firmware or games; I will provide the system software myself afterwards. Stop and report when the build succeeds or when you hit something you cannot fix without a system change.
```

## 4. Phase 1 — AGC decoder

```
Phase 1. Start with Q2 in docs/HANDOFF.md: read the RPCSX GPU sources in ~/src/rpcsx and write docs/formats/agc.md section "RPCSX AGC handling" (where DCB/CCB are received, how PM4 is parsed, where PS4 GNM and PS5 AGC paths differ, file paths with commit hash). Then scaffold tools/bc5-agc: a PM4 type-0/2/3 packet decoder with register-name resolution from Mesa's src/amd/registers gfx10 JSON (vendor the JSON with its license), tests with hand-built streams, and a report mode listing unknown opcodes and register offsets with counts. Do not touch backend/ yet.
```

## 5. Any GPU phase — before submitting anything

```
Before any code path that submits to amdgpu: confirm the --submit flag is default off, that tests never set it, that the experiment README names the risk (machine reset), and ask me to confirm the machine is idle and my work is saved. Then proceed.
```

## Follow-up phrases that work well

- `Record this as experiment NNNN with the template, verdict included.`
- `Update docs/HANDOFF.md: move Qn to Findings with the source you used.`
- `Explain the trade-off in an ADR before implementing.`
- `Show me the diff and the test output before committing.`
