# 0003 — Synthetic `.ffpfsc` fixtures for `bc5-mount`

**Status.** Accepted, 2026-09-28.

**Context.** Tests for the container readers need valid `.ffpfsc` files, and the repository must
never contain a real one (`CLAUDE.md`, hard rule 1). The public implementations we derived
`docs/formats/ffpfsc.md` from are all GPL-3.0 (PS5PKGTool, MkPFS, PS4 FFPFSC), which a GPL-2.0-only
project cannot port or vendor. `fpkg-cli` (the tool named in `PROMPT.md`) could not be identified
as an open-source, Linux-capable program; MkPFS is the open-source CLI that fills that role
(Python, `pip install mkpfs`, runs on Linux).

**Decision.**

1. **We write our own generator in Rust**, inside the `bc5-mount` crate: a `fixture` library module
   plus a `bc5-fixture` binary (`bc5-fixture build <spec> <out.ffpfsc>`, `bc5-fixture tree
   <spec> <dir>`). It produces, from an in-memory description of a directory tree, an exFAT image
   → a PFSC stream → a PFS v2 container, byte for byte according to `docs/formats/ffpfsc.md` §2–§7
   and with the writer conventions listed there (512-byte sectors, FAT at sector 128, 32/64 KiB
   clusters, Microsoft up-case table, `NoFatChain` on every entry, block 4 left empty). It is a test
   tool, not a packer: no compression tuning, no metadata, no attempt at console compatibility
   beyond what the readers check.
2. **Fixtures are deterministic**: fixed timestamps (2024-01-01), fixed volume serial, entries
   sorted by lower-cased name, file bytes from a seeded generator. The same spec yields the same
   SHA-256, so tests can assert on hashes of whole images, not only on decoded trees.
3. **Fixtures are generated at test time and never committed.** Large cases stream to disk; nothing
   holds more than a few MiB in memory.
4. **External oracles, never vendored.** The gate experiment (`experiments/*-bc5-mount-gate`)
   additionally runs `python -m mkpfs verify` / `unpack --deep` on our fixtures and, when the
   maintainer chooses, `bc5-mount verify` on their own real container. Both are separate processes;
   results go into the experiment log, not into the repository as data.
5. **Dependencies.** The generator needs a zlib *encoder* and the reader a zlib *decoder*. Proposed:
   `flate2` with its default pure-Rust `miniz_oxide` backend (MIT/Apache-2.0, no C, no network).
   This is outside the pre-approved list in `PROMPT.md` and is **pending maintainer approval**
   before implementation starts.

**Minimal fixture set** (each is a named spec in the generator; every reader test uses at least
one):

| Name | Content | What it exercises |
| --- | --- | --- |
| `empty` | no files, no directories | root directory only, zero-entry PFSC edge (one block of exFAT metadata) |
| `one-small` | `a.txt`, 13 bytes | single cluster, single PFSC block, compressible |
| `spanning` | `big.bin`, 200 KiB + 1 byte, seeded pseudo-random | file spanning clusters and four PFSC blocks; incompressible → raw blocks; odd tail |
| `mixed-compress` | `zeros.bin` (256 KiB of 0x00) next to `noise.bin` (256 KiB random) | raw and zlib blocks interleaved in one stream |
| `deep` | 8 nested directories, a file at every level, a 200-character name | directory recursion, multi-entry (0xC1) file names, path joining |
| `wide` | 600 files in one directory | directory data spanning more than one cluster |
| `case` | `sce_sys/param.json` with `titleId`, looked up as `SCE_SYS/PARAM.JSON` | case-insensitive lookup, `bc5-mount inspect` metadata |
| `sparse-1g` | one 1 GiB file of zeros with 1 KiB of noise every 64 MiB | 16 384 PFSC blocks, offset table larger than 0xFC00 bytes (header grows), 64-bit arithmetic, throughput measurement. `#[ignore]` in unit tests; run by the gate experiment |

**Consequences.** More code than porting would have cost, but no licence exposure and full control
over edge cases (we can also emit *malformed* variants for the "never panics" tests: truncated
files, non-monotonic PFSC offsets, dirent `entsize` not a multiple of 8, FAT cycles). Format
knowledge stays in one place (`docs/formats/ffpfsc.md`); the generator and the readers are both
checked against it, and against each other by round-trip tests.
