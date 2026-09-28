# `.ffpfsc` — container layout

Read-only view of the format `bc5-mount` has to understand. Derived from public source code; every
field cites where it was read from. One real container (the maintainer's own dump) was checked
against this description in `experiments/0001-ffpfsc-header-survey/`.

Sources, abbreviated in the tables below:

| Tag | Source | Licence |
| --- | --- | --- |
| **PKT** | [pearlxcore/PS5PKGTool](https://github.com/pearlxcore/PS5PKGTool) @ `0072cb4` (2026-09-22), `PS5PKGTool.Ffpfsc/*.cs` | GPL-3.0 |
| **MK** | [PSBrew/MkPFS](https://github.com/PSBrew/MkPFS) @ `78eda0a` (2026-09-03), `mkpfs/consts.py`, `mkpfs/pfs.py` | GPL-3.0 |
| **WIKI** | psdevwiki, [PS4/PFS](https://www.psdevwiki.com/ps4/PFS) — sections Header, Inodes, Dirents, flat_path_table | CC BY-SA |
| **MSX** | Microsoft, *exFAT file system specification* (published under the Open Specification Promise) | — |
| **E1** | `experiments/0001-ffpfsc-header-survey/` — values observed in a real container | — |

**Licence note.** PKT and MK are GPL-3.0; this repository is GPL-2.0-only. Nothing from them is
ported. This document records the on-disk layout (facts), and `bc5-mount` is written from it. The
"FFPFS CLI" mentioned in `HANDOFF.md` F8 is *PS4 FFPFSC* (`PS4pkg_to_ffpfsc`, GPL-3.0-or-later,
Python); it is a PS4 packaging pipeline built on MkPFS and adds nothing to the PS5 layout.
`PSBrew/ps5-exfat-builder` (credited by PKT) no longer exists on GitHub.

## 1. Layering

```
.ffpfsc file
└── PFS v2 image, unsigned, unencrypted, 32-bit inodes, one block size for everything
    ├── block 0      superblock
    ├── block 1      inode table: exactly 4 inodes of 0xA8 bytes
    ├── inode 0      super-root directory  → dirents: flat_path_table (ino 1), uroot (ino 2)
    ├── inode 1      flat_path_table       → 8 bytes: hash("/<inner name>") → 3
    ├── inode 2      uroot directory       → dirents: ".", "..", <inner name> (ino 3)
    └── inode 3      <inner name>, flag COMPRESSED → the file body is a PFSC stream
        └── PFSC: 64 KiB logical blocks, each stored raw or as one zlib stream
            └── decoded bytes = exFAT volume image (the game's app0 tree)
```

The inner payload can also be a UFS2 image (FFPKG) or another PFS image (PKT
`FfpfscVolume.cs:47-71` detects the kind by signature, not by name). Only exFAT is in scope for
phase 0a; the other two are rejected with a clear error.

Everything is little-endian. `q` = i64, `Q` = u64, `i` = i32, `I` = u32, `H` = u16, `B` = u8.

## 2. PFS v2 superblock (block 0)

Block 0 is `block_size` bytes long; only the first 0x370 are meaningful.

| Offset | Type | Field | Value in `.ffpfsc` | Source |
| --- | --- | --- | --- | --- |
| 0x00 | q | `version` | 2 (PS5); 1 is the PS4 profile | PKT `FfpfscImage.cs:16,192,201`; MK `consts.py:7-9`; WIKI |
| 0x08 | q | `magic` | 20130315 = 0x01332A0B | PKT `FfpfscImage.cs:15`; MK `consts.py:6`; WIKI |
| 0x10 | q | — | 0 | MK `pfs.py:3099` |
| 0x18 | B×4 | — | 0, 0, 1, 0 (byte 0x1A is always 1; meaning unknown) | PKT `FfpfscImage.cs:443`; MK `pfs.py:3100` |
| 0x1C | H | `mode` | bit 0 signed, bit 1 64-bit inodes, bit 2 encrypted, bit 3 case-insensitive. `.ffpfsc`: 0x0008 (or 0). Readers reject any other bit. | PKT `FfpfscImage.cs:17,194,202`; MK `consts.py:10-13`; WIKI |
| 0x1E | H | — | 0 | MK `pfs.py:3102` |
| 0x20 | I | `block_size` | power of two. PKT accepts 4 KiB–1 MiB; WIKI says up to 32 MiB. Observed: 0x10000 | PKT `FfpfscImage.cs:195,204`; E1 |
| 0x24 | I | — | 0 | MK `pfs.py:3104` |
| 0x28 | q | `nblock` ("leading blocks") | 1 — the superblock occupies one block | PKT `FfpfscImage.cs:196,206`; MK `pfs.py:3084,3105` |
| 0x30 | q | `ndinode` | inode count; 4 in `.ffpfsc` | PKT `FfpfscImage.cs:197,206`; MK `pfs.py:3106` |
| 0x38 | q | `ndblock` | total block count; **file length must equal `ndblock × block_size`** | PKT `FfpfscImage.cs:198,208-211`; E1 |
| 0x40 | q | `ndinodeblock` | number of inode-table blocks; 1 in `.ffpfsc` | PKT `FfpfscImage.cs:199,208`; MK `pfs.py:3108` |
| 0x50 | 0x310 bytes | inode-block signature record | an S64-layout inode describing the inode table: nlink 1, flags 0x10, size = `ndinodeblock × block_size` (twice), four timestamps, `blocks` at +0x60, first pointer at +0x88 = 1. Readers ignore it. | PKT `FfpfscImage.cs:452-461`; MK `pfs.py:558-605` |
| 0x368 | I | — | 1 for unsigned images (signed/encrypted images set 0x36C = 1 and a 16-byte seed at 0x370 instead) | PKT `FfpfscImage.cs:462`; MK `pfs.py:3111-3115` |

Reader requirements (PKT `FfpfscImage.cs:201-211`): `version == 2`, `magic`, `mode & ~8 == 0`,
`nblock == 1`, `4 <= ndinode <= block_size / 0xA8`, `ndinodeblock == 1`, `ndblock > 0`, and the file
length check above.

## 3. Inode (D32 layout, 0xA8 bytes)

The inode table starts at byte `nblock × block_size` (= block 1); inode *n* is at `+ n × 0xA8`.
Inodes never straddle a block (WIKI).

| Offset | Type | Field | Notes | Source |
| --- | --- | --- | --- | --- |
| 0x00 | H | `mode` | POSIX permission bits (0x1FF) \| 0x4000 directory \| 0x8000 regular file. `.ffpfsc` uses permissions 0x16D (`r-xr-xr-x`). | PKT `FfpfscImage.cs:19-21`; MK `consts.py:15-34` |
| 0x02 | H | `nlink` | 1 for files, 3 for `uroot` | PKT `FfpfscImage.cs:113-123`; E1 |
| 0x04 | I | `flags` | 0x1 COMPRESSED (body is PFSC), 0x10 READONLY, 0x20000 INTERNAL (super-root and flat_path_table) | PKT `FfpfscImage.cs:22-24`; MK `consts.py:36-38` |
| 0x08 | q | `size` | bytes occupied on disk. For the payload inode: **length of the PFSC stream** | PKT `FfpfscImage.cs:238,252` |
| 0x10 | q | `size_compressed` | for a COMPRESSED file this is the **decompressed (logical) length**, despite the name; equals `size` for other inodes | PKT `FfpfscImage.cs:149,253`; MK `pfs.py:706` |
| 0x18 | q×4 | `time[4]` | seconds; all four equal in generated images | PKT `FfpfscImage.cs:481-482`; MK `pfs.py:707` |
| 0x38 | I×4 | `time_nsec[4]` | 0 | MK `pfs.py:708` |
| 0x48 | I | `uid` | 0 | MK `pfs.py:709` |
| 0x4C | I | `gid` | 0 | MK `pfs.py:709` |
| 0x50 | Q | `unk1` | 0 | MK `pfs.py:709` |
| 0x58 | Q | `unk2` | 0 | MK `pfs.py:709` |
| 0x60 | I | `blocks` | number of data blocks | PKT `FfpfscImage.cs:483,496` |
| 0x64 | i×12 | `db[12]` | direct block pointers. `.ffpfsc`: `db[0]` = first block, the file is **one contiguous run** of `blocks` blocks; unused slots are −1 (the super-root inode uses 0) | PKT `FfpfscImage.cs:484-486,497`; MK `consts.py:48`, `pfs.py:722` |
| 0x94 | i×5 | `ib[5]` | indirect pointers; unused (−1) | MK `consts.py:49`, `pfs.py:723` |

PKT reads only `db[0]` and treats `blocks` as consecutive (`FfpfscImage.cs:237,500-505`). A
general PFS may scatter a file across `db[1..11]` and indirect blocks; `bc5-mount` rejects such
inodes rather than guessing (see §9).

Validation per inode (PKT `FfpfscImage.cs:500-506`): `size >= 0`, `size_compressed >= 0`,
`blocks > 0`, `0 < db[0] < ndblock`, `db[0] + blocks <= ndblock`, `size <= blocks × block_size`.

## 4. Directory entries

A directory's data is a sequence of 8-byte-aligned entries, terminated by an all-zero entry or the
end of the data (PKT `FfpfscImage.cs:508-531`; MK `pfs.py:631-670`; WIKI).

| Offset | Type | Field | Notes |
| --- | --- | --- | --- |
| 0x00 | I | `ino` | inode number |
| 0x04 | i | `type` | 2 file, 3 directory, 4 `.`, 5 `..` (MK `consts.py:40-43`) |
| 0x08 | i | `namelen` | bytes of name |
| 0x0C | i | `entsize` | `align8(namelen + 17)`; `>= 16`, multiple of 8, `namelen <= entsize − 16` |
| 0x10 | B×namelen | `name` | ASCII, no terminator required (the +17 leaves room for one) |

Expected contents of an `.ffpfsc` (PKT `FfpfscImage.cs:97-103,221-228`):

- super-root (inode 0): `(1, file, "flat_path_table")`, `(2, dir, "uroot")`
- uroot (inode 2): `(2, ".", 4)`, `(2, "..", 5)`, `(3, file, <inner name>)` — exactly one file entry

The inner name is `<TITLEID>.exfat` by convention (PKT `FfpfscImage.cs:581-612` derives it from
`sce_sys/param.json` `titleId`), but nothing depends on it.

## 5. `flat_path_table` (inode 1)

An array of `(I hash, I value)` pairs sorted by hash (MK `pfs.py:2451-2524`; WIKI).
`hash = (fold(c) + 31 × hash) mod 2^32` over the **full path with a leading `/`**, where `fold` is
ASCII upper-casing when the image is case-insensitive. `value` = inode number, `| 0x20000000` for
directories, or `0x80000000 | offset` into a collision blob (MK only; never occurs with one entry).

In `.ffpfsc` the table is exactly 8 bytes: `hash("/" + inner name) → 3` (PKT
`FfpfscImage.cs:232-235,553-570`). E1 confirmed the hash on a real container.

## 6. PFSC stream (body of inode 3)

All offsets are relative to the start of the stream (= `db[0] × block_size` in the container).

| Offset | Type | Field | Value | Source |
| --- | --- | --- | --- | --- |
| 0x00 | I | `magic` | `"PFSC"` = 0x43534650 | PKT `PfscCodec.cs:12`; MK `consts.py:62` |
| 0x04 | i | `unk4` | 0 | PKT `PfscCodec.cs:112,121`; MK `consts.py:63` |
| 0x08 | i | `unk8` | 6 (version-like) | PKT `PfscCodec.cs:13,121`; MK `consts.py:64` |
| 0x0C | i | `block_sz` | 0x10000; readers reject anything else | PKT `PfscCodec.cs:14,122`; MK `consts.py:65` |
| 0x10 | q | `block_sz2` | must equal `block_sz` | PKT `PfscCodec.cs:115,122`; MK `pfs.py:2279` |
| 0x18 | q | `block_offsets` | offset of the offset table: always 0x400 | PKT `PfscCodec.cs:16`; MK `consts.py:68`, `pfs.py:2287` |
| 0x20 | Q | `data_start` | first data byte; `>= 0x10000`, multiple of `block_sz`; equals `offsets[0]` | PKT `PfscCodec.cs:17,128,152`; MK `consts.py:69` |
| 0x28 | q | `data_length` | logical (decoded) length, **padded** to a multiple of `block_sz` | PKT `PfscCodec.cs:118,130` |
| 0x400 | Q×(n+1) | `offsets[]` | `n = data_length / block_sz`; monotonic non-decreasing; all in `[data_start, stream length]` | PKT `PfscCodec.cs:136-153` |

Header size is `0x10000 + ceil(max(0, 8(n+1) − 0xFC00) / 0x10000) × 0x10000`
(PKT `PfscCodec.cs:252-258`; MK `pfs.py:990-1007`); E1 matched this formula.

Block *i* is stored in `[offsets[i], offsets[i+1])`:

- stored size `== block_sz` → raw bytes;
- `0 < stored size < block_sz` → one zlib stream (RFC 1950, `ZLibStream` in PKT, `zlib`/`isal` in
  MK) that must inflate to exactly `block_sz` bytes with no trailing input;
- stored size `0` or `> block_sz` → invalid (PKT `PfscCodec.cs:195-221`).

The last logical block is zero-padded on encode (PKT `PfscCodec.cs:58`). The true payload length is
the inode's `size_compressed`, which must satisfy `data_length − block_sz < size_compressed <=
data_length` (PKT `FfpfscImage.cs:239-241`). Per-block compression is a writer choice (PKT keeps a
compressed block only if it saves ≥ 5 %, `PfscModels.cs:6`; MK defaults to 0 %) and is invisible to
readers. Compression level cannot be recovered and does not matter.

## 7. exFAT (read-only subset)

The decoded PFSC stream is a plain exFAT volume. What a read-only traversal needs, per MSX and as
implemented in PKT `ExfatVolume.cs`:

**Main boot sector** (sector 0, 512 bytes; MSX §3.1; PKT `ExfatVolume.cs:51-72`)

| Offset | Type | Field | Notes |
| --- | --- | --- | --- |
| 0x03 | B×8 | `FileSystemName` | `"EXFAT   "` |
| 0x48 | Q | `VolumeLength` | in sectors |
| 0x50 | I | `FatOffset` | sectors from volume start |
| 0x54 | I | `FatLength` | sectors; must cover `(ClusterCount + 2) × 4` bytes |
| 0x58 | I | `ClusterHeapOffset` | sectors |
| 0x5C | I | `ClusterCount` | |
| 0x60 | I | `FirstClusterOfRootDirectory` | `>= 2` |
| 0x64 | I | `VolumeSerialNumber` | informational |
| 0x68 | H | `FileSystemRevision` | 0x0100 |
| 0x6C | B | `BytesPerSectorShift` | 9–12 |
| 0x6D | B | `SectorsPerClusterShift` | `<= 25 − BytesPerSectorShift` |
| 0x6E | B | `NumberOfFats` | 1 |
| 0x1FE | H | `BootSignature` | 0xAA55 |

Sector 11 of each boot region holds the boot checksum (MSX §3.1.2); PKT ignores it on read.

**FAT** (MSX §4.1): one u32 per cluster starting at `FatOffset × sector_size`; entries 0 and 1 are
reserved (0xFFFFFFF8, 0xFFFFFFFF); a value `>= 0xFFFFFFF8` ends a chain (PKT
`ExfatVolume.cs:32,208-216`). Cluster *n* (n ≥ 2) lives at
`ClusterHeapOffset × sector_size + (n − 2) × cluster_size` (PKT `ExfatVolume.cs:278`).

**Directory entries** (32 bytes each; MSX §6, §7; PKT `ExfatVolume.cs:147-190`):

| Type byte | Entry | Fields used |
| --- | --- | --- |
| 0x00 | end of directory | stop |
| 0x81 / 0x82 / 0x83 | allocation bitmap / up-case table / volume label | skipped on read |
| 0x85 | File (MSX §7.4) | +0x01 `SecondaryCount` (≥ 2), +0x02 set checksum, +0x04 `FileAttributes` (0x10 = directory) |
| 0xC0 | Stream Extension (MSX §7.6) | +0x01 flags: bit 1 (0x02) `NoFatChain` = contiguous; +0x03 `NameLength` (UTF-16 units); +0x04 `NameHash`; +0x08 `ValidDataLength`; +0x14 `FirstCluster`; +0x18 `DataLength` |
| 0xC1 | File Name (MSX §7.7) | +0x02 15 UTF-16LE units; `ceil(NameLength / 15)` entries follow the stream extension |

A file's clusters: if `NoFatChain`, they are `FirstCluster .. FirstCluster + ceil(DataLength /
cluster_size) − 1` with no FAT lookup; otherwise follow the FAT, stopping after the expected count
and rejecting cycles (PKT `ExfatVolume.cs:193-220`). A directory's data length comes from its own
stream extension; the root directory's from walking the FAT. Names are compared case-insensitively
(PKT uses ordinal ignore-case; MSX mandates the up-case table — see §9).

Writer conventions seen in PKT `ExfatImage.cs` and useful for our fixture generator, not
requirements for reading: 512-byte sectors, FAT at sector 128, main + backup boot region of 12
sectors each, cluster size 32 KiB or 64 KiB, the Microsoft reference up-case table (5 836 bytes,
`ExfatUpcaseTable.cs`), `NoFatChain` set on every allocated entry while the FAT is still filled
with the chains, fixed timestamps, serial `"MkPF"`.

## 8. Observed on a real container (E1)

Maintainer's own dump, 47 523 430 400 bytes, built 2026-06-30 by an unidentified tool:

| Item | Value |
| --- | --- |
| superblock | version 2, magic ok, byte 0x1A = 1, mode 0x0008, block 64 KiB, nblock 1, ndinode 4, ndblock 725 150 (× 64 KiB = file length exactly), ndinodeblock 1, 0x368 = 1 |
| inodes | 0: dir 0x416D, flags 0x20010, block 2 · 1: file, flags 0x20010, size 8, block 3 · 2: dir, nlink 3, flags 0x10, block 5 · 3: file, flags 0x11, size 47 522 995 988, size_compressed 163 940 663 296, blocks 725 144, db[0] = 6 |
| dirents | super-root: `flat_path_table` (1), `uroot` (2) · uroot: `.`, `..`, `PPSA21564.exfat` (3) |
| flat_path_table | `0xDFDA68EF → 3`, equal to `hash("/PPSA21564.EXFAT")` recomputed |
| PFSC | magic, 0, 6, 0x10000, 0x10000, 0x400, data_start 0x1320000 (= formula for 2 501 536 blocks), data_length 163 940 663 296 |
| offsets | 0x1320000, +0x479, +0x54, +0x54, … (boot region compresses ~1000:1) |
| ratio | stored / logical = 0.29 |

Block 4 is unused (zero) between `flat_path_table` and `uroot`, exactly as the PKT writer lays it
out (`FfpfscImage.cs:105-111`) — the tool that made this container follows the same layout.

## 9. What we do not know yet

- **Meaning of superblock byte 0x1A, the 0x50 record and 0x368.** Writers set them, the readers we
  have read ignore them. Whether the console-side mounters (ShadowMountPlus etc.) check them is
  unknown; our fixture writer sets them exactly as PKT/MK do.
- **Variation across producers.** One real container seen, one producer (unknown; layout identical
  to PKT/MK). Whether console-side compressors (PS5 Game Compressor) ever emit more than 4 inodes,
  a non-contiguous payload (`db[1..]`, `ib`), a different `unk8`, or a data start not on a block
  boundary is unverified. `bc5-mount` rejects those with an error naming the field, so a new
  producer shows up as a clear failure, not silent corruption.
- **Inner payload kinds other than exFAT** (UFS2/FFPKG, nested PFS): out of scope until a dump
  needs them.
- **exFAT details deliberately skipped for reading:** boot checksum, allocation bitmap, up-case
  table (we fold ASCII only; non-ASCII names would need the table for correct case-insensitive
  lookup), TexFAT, timestamps, general secondary entries, `ValidDataLength < DataLength` (we read
  `DataLength` and expose it; PKT does the same).
- **`ampr_emu.index`**: PKT adds this virtual root file when `fakelib/libSceAmpr.sprx` exists in the
  dump (`ExfatImage.cs:276-290`). It is a runtime aid for the console, not part of the format.
- **PS4 profile** (`version == 1`, `.ffpfs`): out of scope.
