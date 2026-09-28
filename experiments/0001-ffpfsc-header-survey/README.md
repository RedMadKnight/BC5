# 0001 — ffpfsc header survey

**Question.** Does the `.ffpfsc` layout derived from public source code (PS5PKGTool, MkPFS; see
`docs/formats/ffpfsc.md`) match a container made from a real PS5 dump?

**Setup.** Windows 11, Git Bash, `od` from Git for Windows 2.55. Input: the maintainer's own dump
of one title (PPSA21567), a single `.ffpfsc` of 47 523 430 400 bytes, built 2026-06-30 (inode
timestamps) by a tool not recorded. The file stays outside the repository; only structural bytes
were read — superblock (0x0–0x400), inode table (0x10000–0x102A0), super-root dirents (0x20000),
flat_path_table (0x30000), uroot dirents (0x50000), PFSC header and the first six offset-table
entries (0x60000–0x60430). No file content from inside the exFAT image was read or decoded.

```sh
F='<container>.ffpfsc'
od -A x -t x1z -v -N 1024 "$F"
od -A x -t x1z -v -j $((0x10000)) -N $((4*0xA8)) "$F"
od -A x -t x1z -v -j $((0x20000)) -N 96 "$F"
od -A x -t x1z -v -j $((0x30000)) -N 16 "$F"
od -A x -t x1z -v -j $((0x50000)) -N 112 "$F"
od -A x -t x1z -v -j $((0x60000)) -N 0x30 "$F"
od -A x -t x8  -v -j $((0x60400)) -N 48 "$F"
```

Cross-checks done by hand: `ndblock × block_size` against the file length, `db[0] + blocks`
against `ndblock`, the PFSC `data_start` against the header-size formula, and the
`flat_path_table` hash against a re-implementation of the hash (bash loop, upper-cased path).

**Result.** Full dump in [`survey.log`](survey.log) (all-zero lines elided).

| Structure | Observed | Matches doc |
| --- | --- | --- |
| superblock | version 2; magic 0x01332A0B; byte 0x1A = 1; mode 0x0008; block_size 0x10000; nblock 1; ndinode 4; ndblock 725 150; ndinodeblock 1; 0x368 = 1; 0x50 record: nlink 1, flags 0x10, size 0x10000 ×2, timestamps ×4, blocks 1, pointer 1 at +0x88 | yes |
| file length | 725 150 × 65 536 = 47 523 430 400 = actual length | yes |
| inode 0 | mode 0x416D, nlink 1, flags 0x20010, size 0x10000 / 0x10000, blocks 1, db[0] 2, db[1..] 0 | yes |
| inode 1 | mode 0x816D, nlink 1, flags 0x20010, size 8 / 8, blocks 1, db[0] 3, db[1..] −1 | yes |
| inode 2 | mode 0x416D, nlink 3, flags 0x10, size 0x10000 / 0x10000, blocks 1, db[0] 5, rest −1 | yes |
| inode 3 | mode 0x816D, nlink 1, flags 0x11, size 47 522 995 988, size_compressed 163 940 663 296, blocks 725 144, db[0] 6, rest −1; 6 + 725 144 = 725 150 = ndblock | yes |
| super-root | (1, 2, 15, 0x20, "flat_path_table"), (2, 3, 5, 0x18, "uroot"), then zeros | yes |
| flat_path_table | 0xDFDA68EF → 3; recomputed hash of "/PPSA21564.EXFAT" = 0xDFDA68EF | yes |
| uroot | (2, 4, ".", 0x18), (2, 5, "..", 0x18), (3, 2, 15, 0x20, "PPSA21564.exfat") | yes |
| block 4 | not referenced by any inode (PS5PKGTool writer leaves it empty) | yes |
| PFSC header | "PFSC", 0, 6, 0x10000, 0x10000, 0x400, data_start 0x1320000, data_length 163 940 663 296 | yes |
| PFSC header size | 2 501 536 blocks → table 20 012 296 bytes → formula gives 0x1320000 | yes |
| offsets[0..6] | 0x1320000, 0x1320479, 0x13204CD, 0x1320521, 0x1320575, 0x13205C9 (monotonic; first block 1 145 bytes stored = compressed boot region, next ones 84 bytes = compressed zero sectors) | yes |
| stored / logical | 47.5 GB / 163.9 GB = 0.29 | — |

Two observations outside the doc: the inner file is named `PPSA21564.exfat` while the dump is of
PPSA21567 (the name is derived from `param.json` `titleId`, which can differ from the SKU the file is
labelled with; nothing reads it), and `size_compressed` is 163.9 GB while the stored stream is
47.5 GB — the exFAT image is mostly empty clusters, which is why the ratio is so favourable.

**Verdict.** Passed. Every field of `docs/formats/ffpfsc.md` §2–§6 that a reader depends on has
the documented value in a real container, and the container follows the PS5PKGTool/MkPFS block
layout exactly (including the unused block 4). One producer only; the "variation across producers"
question in §9 stays open. Phase 0a implementation can proceed on the documented layout, with
strict validation so that a different producer fails loudly.
