# PS5 package (`.pkg`, `\x7fFIH`) — what `bc5-mount` reads

Status: derived from public readers and verified against one package the maintainer built
from a game they own (experiment 0031). Nothing here comes from Sony material. Byte offsets
are what the code uses; everything marked *TODO(verify)* is an assumption that held for that
one package.

Sources (all read as documentation; no code was ported):

- SvenGDK/LibProsperoPKG @ main (GPL-3.0): `docs/ps5-pkg-format.md`, `PKG/ProsperoNapsLayout.cs`,
  `PFS/ProsperoPs5InnerImageReader.cs`, `PFS/Compression/Oodle/KrakenDecoder.cs`.
- awake-devel/pkg-to-anyps5 @ main (GPL-3.0): `src/naps.rs`, `src/inner.rs`, `src/kraken.rs`
  — the record bit layout below is theirs; it decoded every record of the test package where
  LibProsperoPKG's (fields shifted by one bit from bit 19 up, a different table alignment) did
  not. The same correction is described in 187rider/MacOS-Prospero-FPKG-GUI-Builder issues #2–#4.
- powzix/ooz (the C++ Kraken decoder) through its Rust port lvlvllvlvllvlvl/oozextract 0.5.5
  (MIT, vendored in `tools/third_party/oozextract`).

## 1. Layers

```
.pkg file
 ├─ 0x0000   \x7fFIH header (0x100 bytes used)
 ├─ pfs_offset (0x10000): outer PFS image, data-first
 │    ├─ block 0 …        uroot/pfs_image.dat   (the inner image, stored)
 │    ├─ …                uroot/naps_pkg_layout.dat
 │    └─ near the end     superblock, inode table, root dirents, flat path table, uroot dirents
 ├─ cnt_offset            \x7fCNT container: title metadata (param.json, icons, …)
 └─ trailing ZIP          install metadata (debug packages; stored entries)
```

The inner image is the game's `app0` as a PFS whose logical bytes are not stored as such:
`naps_pkg_layout.dat` maps every 256 KiB logical block to a run of stored bytes, raw or
Kraken-compressed. `bc5-mount` decodes blocks on demand behind a cache and exposes the inner
tree under `uroot` like it exposes an `.ffpfsc`'s exFAT tree.

## 2. `\x7fFIH` header

| Offset | Size | Field |
|---|---|---|
| 0x00 | 4 | magic `7F 46 49 48` |
| 0x05 | 1 | image type: `0x80` retail (encrypted outer image), `0x00` debug |
| 0x10 | 8 | outer PFS offset (0x10000 in the package seen) |
| 0x18 | 8 | outer PFS size |
| 0x20 | 8 | outer superblock offset (absolute) |
| 0x28 | 8 | outer superblock size (0x10000) |
| 0x30 | 32 | digest |
| 0x58 | 8 | `\x7fCNT` offset (absolute); the content ID is 36 ASCII bytes at +0x40 of it |
| 0x68 | 8 | `0x0000800000000000` in the package seen; flags, meaning not needed here |
| 0xa0 | 8 | offset of `naps_pkg_layout.dat` within the outer image (*TODO(verify)*: equal to its inode's first block; the reader walks the directory instead) |
| 0xa8 | 8 | length of `naps_pkg_layout.dat` (*TODO(verify)*, same) |

All little-endian. Fields the reader does not use are omitted.

## 3. Outer PFS

PFS v2 (version 2, magic 20130315) with 64 KiB blocks, **data-first**: block 0 of the image
is the first data block, the superblock is at the block the header names, the inode table
follows it (after any indirect-pointer blocks of the superblock's own signature inode, counted
from the non-zero pointers at superblock+0x50+0x248+k·40+32, k = 0..4), then the directory
blocks.

The superblock's mode is 0xd in the package seen (signed, encrypted, case-insensitive),
yet the image is plaintext: the 16-byte seed at superblock+0x370 reads `PPSPLAIN-NOAUTH!`.
A real seed means an encrypted image, which `bc5-mount` refuses (the key is derived from
the package passcode or console material; not implemented, not planned).

Inodes are the signed 32-bit layout, 0x2c8 bytes each: mode at 0, size at 8, `csize` at 0x10
(for `pfs_image.dat` the logical size of the inner image), block count at 0x60, then twelve
direct block pointers of 36 bytes (32-byte digest, then the signed 32-bit block number at
+32) from 0x64 and five indirect ones after them. `pfs_image.dat` starts at block 0 and is
stored contiguously (*TODO(verify)*: checked for the twelve direct pointers; the reader
assumes the indirect ones continue the run). Directory entries are the same 8-byte-aligned
records as in `docs/formats/ffpfsc.md` §5. The root holds `uroot`; `uroot` holds
`pfs_image.dat` and `naps_pkg_layout.dat`.

## 4. `naps_pkg_layout.dat`

Sections in order, no gaps except where noted:

| Section | Entry | Count |
|---|---|---|
| header | 16 bytes | 1 |
| outer block digests | 8 bytes | `num_outer_blocks` (zero in the package seen) |
| shuffle patterns | 8 bytes | `num_shuffle` |
| file offsets (`fidx`) | 6 bytes | `num_files` |
| `u2c` | 10 bytes | `(num_ublocks + 8) >> 3`; starts right after `fidx` or after `fidx` padded to 16 bytes, producers differ |
| `CblockInfo` | 9 bytes | `num_cblock_info`; starts on the next 8-byte boundary after `u2c` |

Header, two little-endian 64-bit words: word 0 bits 0–23 `num_files − 1`, 24–25 compression
type (2 = Kraken), 26–27 `num_keys − 1`, 28–31 `num_shuffle`, 32–55 `num_ublocks` (256 KiB
logical blocks of the mount); word 1 bits 0–23 `num_outer_blocks` (64 KiB blocks of the stored
image), 24–47 `num_cblock_info − 2`.

File offset: 40-bit little-endian logical offset, then a kind byte: 0 for a file's first
byte, `0x40` for the mount size (the last entry) and for a sparse region (no records; it
reads as zeros up to the next boundary; *TODO(verify)*: one entry per region or per 256 KiB,
none seen), other kinds (`0x0b` seen once, with an offset past the mount) are ignored.
The logical layout is: file data from 0 in file order, then the metadata (inner superblock,
inode table, directories) at the last boundary below the mount size.

`u2c`: a 24-bit record index, then seven byte deltas: the first `CblockInfo` record of each
of eight consecutive logical blocks. The reader does not need it (it walks the records).

`CblockInfo` record, 72 bits little-endian plus byte 8, bit 18 selects the kind:

| Kind | Bits | Field |
|---|---|---|
| both | 0–17 | `coffset_mod`: stored offset modulo 256 KiB (data record); the previous run's end (run base) |
| both | 18 | 1 = run base |
| data | 38–54 | stored length of the first 128 KiB chunk minus one |
| data | 56–58 | first chunk's Kraken flags: bit 0 sub-literals, bit 1 LZ (otherwise a bare entropy array) |
| data | 59–62 | second chunk's flags: bit 0 sub-literals, bit 1 LZ, bit 2 restart |
| run base | 49–63 + byte 8 bits 0–8 | twice the index of the 256 KiB stored block the run starts in |

Walking the records in order gives the blocks in logical order: a data record covers
`min(256 KiB, next file boundary − logical)` logical bytes; its stored length is the next
record's `coffset_mod` minus its own, modulo 256 KiB (for stored and Kraken blocks alike); a
run base re-anchors the stored cursor at `(start_256k / 2) · 256 KiB + coffset_mod of the
next record`. A block is Kraken when its first chunk has the LZ bit or when its stored
length differs from its logical length. Data records' bits 19–37 (twice the logical offset
modulo 256 KiB in LibProsperoPKG's reading) and bit 55 (always set in the package seen)
are not used.

Test package: 291 file offsets, 750,099 logical blocks, 815,782 records, 750,239 blocks
(616,999 Kraken, 133,240 stored, 0 sparse) covering the 196,633,821,184-byte mount exactly;
stored image 101,434,392,576 bytes.

## 5. Kraken blocks

A block is one 128 KiB chunk, or two for blocks over 128 KiB, with **no** Oodle block or
quantum headers. The naps record says what they would say: the first chunk's stored length,
and per chunk whether it is an LZ chunk and whether its literals are deltas. The reader
synthesises the headers (`tools/bc5-mount/src/pkg/kraken.rs`): block header `8C 06`
(Kraken, decoder restart), a 3-byte big-endian quantum header with the total stored length
minus one, then per chunk either a 3-byte big-endian chunk header `0x800000 | mode << 19 |
length` (mode 0 = delta literals, 1 = plain) followed by its bytes, or the bare entropy-coded
bytes. With the restart flag the second chunk is decoded as a block of its own (no
references into the first).

An LZ chunk begins with 8 raw bytes when it starts a block, then a flag byte: if its top
two bits are `10`, the low six bits (plus the next byte × 32 when they exceed 31) give the
size of a substream at the end of the chunk that holds the long length values; the entropy
streams end before it, the number of long lengths is the number of 255 bytes in the packed
length stream, and the values are read from both ends of that substream. Every Kraken block
of the test package uses this "excess" framing; ooz and oozextract 0.5.5 reject it, so the
vendored copy adds it (`tools/third_party/oozextract/README-bc5.md`).

Flags seen (first chunk | second chunk << 4): 0x22 and 0x33 for most two-chunk blocks,
0x32, 0x23, 0x02, 0x03 and a few 0x04/0x06/0x07 (bit 2 of a chunk's flags, meaning unknown,
*TODO(verify)*; such blocks decode when the LZ bit decides).

## 6. Inner PFS

The metadata at the top of the logical image is a PFS v2 superblock (mode 0x18: the compact
inode layout, case-insensitive names; block size 0x10000; `ndblock × block size` equals the
mount size, which is how the superblock is told from the outer one), an inode table of
0xa8-byte inodes (mode at 0, size at 8, the data's logical byte offset at 0x60, `db[2]` at
0x6c the parent inode) one block after it, then one block per directory. Directory entries
are the `.ffpfsc` dirent records. The super-root (inode 0) holds `uroot` and internal
tables (`flat_path_table`, `apr_flat_path_table`, `afid_to_ino_table`); the game's files are
under `uroot`.

Test package: 303 inodes, 288 files in 11 directories, 196,628,482,707 bytes; `sce_sys/`
holds `keystone`, `pfs-version.dat`, `about/right.sprx` and the usual rest; `param.json`
and the icons live in the `\x7fCNT` container, not in the inner image.

## 7. What `bc5-mount` does and does not do

Reads: header, plaintext outer PFS, the layout, the inner tree; decodes blocks on demand
with a 64-block (16 MiB) cache; FUSE-mounts the inner tree. `inspect` prints the content ID
from the `\x7fCNT` when readable.

Does not: decrypt an encrypted outer image, read the `\x7fCNT` metadata beyond the content ID,
verify digests, write packages (the fixture writer produces synthetic ones for tests, with
stored, entropy-only and sparse blocks only, since there is no Kraken encoder here).
