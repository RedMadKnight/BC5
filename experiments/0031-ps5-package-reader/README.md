# 0031 — reading a PS5 package: layout, Kraken blocks and the inner tree

**Question.** Can `bc5-mount` read a PS5 package (`.pkg`, `\x7fFIH`) built from a game the
maintainer owns — find the inner image, map its blocks from `naps_pkg_layout.dat`, decode
the Kraken blocks with the vendored `oozextract`, and list and read the files — using
public documentation only (`docs/formats/ps5pkg.md`)?

**Setup.** One package of 101,814,213,551 bytes, built by the maintainer on 2026-10-08 with
a public packer from their own game (never committed, never named here). The whole file was
on the laptop; the box received only the byte ranges a reader touches (header, outer
superblock and tables, the 20 MB layout, the stored metadata tail, the first 40 data blocks:
54 MB in all), re-assembled into a sparse file of the original size
(`~/bc5-data/pkg-excerpt.sparse`), while the full copy ran in the background. Prototype:
`scratchpad/pkgproto-rs` (Rust, oozextract with the excess patch), then `bc5-mount` itself
(commit of this experiment) built in the `fedora` container. Reference readers consulted as
documentation: LibProsperoPKG, pkg-to-anyps5 (both GPL-3.0).

**Result.**

| Step | Outcome |
|---|---|
| Header, outer PFS | plaintext (seed `PPRPLAIN-NOAUTH!`), superblock at 0x179f330000, 5 inodes, `uroot/pfs_image.dat` 101,434,392,576 bytes stored / 196,633,821,184 logical, `uroot/naps_pkg_layout.dat` 20,663,568 bytes |
| Layout, LibProsperoPKG's record layout | garbage: 778,947 of 815,782 records read as run bases, the stored cursor ran to 7.7 TB |
| Layout, pkg-to-anyps5's record layout (table at 13,321,520, 8-byte aligned after `u2c`) | 750,239 blocks (616,999 Kraken, 133,240 stored) covering the mount exactly; stored cursor ends 54,599 bytes before the image's end (padding) |
| Kraken, oozextract 0.5.5 as published | every block rejected: "excess bytes not supported" |
| Kraken, with the excess framing added | the 5 metadata blocks decode (flags 0x23, 0x32, 0x22, 0x02); the inner superblock is at the expected place (mode 0x18, 303 inodes, `ndblock × 64 KiB` = mount); 288 files in 11 directories |
| First 40 data blocks | all decode: 3 stored, 4 × flags 0x02, 2 × 0x23, 3 × 0x32, 28 × 0x33 |
| File contents | `sce_sys/about/right.sprx` at logical 0 begins with the PS5 SELF magic `54 14 F5 EE`; `sce_sys/pfs-version.dat` reads `01.001.006`; `sce_sys/keystone` begins with `keystone`; the Kraken block of `sce_sys/lem_notification.dat` starts with its 8-byte seed and the excess flag byte |
| `bc5-mount` on the box (release build in the `fedora` container, the sparse excerpt) | `inspect` in 75 ms wall (the 20 MB layout parsed and 750,239 blocks walked); `ls -r` lists 298 entries; `cat` returns the right bytes for the three `sce_sys` files; a FUSE mount (`type fuse.pkg`) lists `sce_sys`, `md5sum` reads through it, `fusermount3 -u` unmounts; `bc5-mount.txt` |

Flag histogram over all Kraken blocks: 0x22 343,941; 0x33 199,170; 0x32 34,193; 0x23 27,299;
0x04 7,599; 0x06 1,423; 0x30 1,220; 0x20 1,090; 0x07 925; 0x02 79; 0x03 54; 0x00 6.

**Verdict.** Passed for what the excerpt allows: the format notes and the reader are right
for this producer, down to file contents, and the decoder needs exactly one addition
(the excess framing). Not yet shown: the whole image (the copy to the box takes hours; a
full `verify` and a play session through the mount are the follow-up), the 0x04-flag
blocks (none among the first 40), sparse regions (none in this package), and any other
producer's layout variant. The layout documented by LibProsperoPKG does not describe this
package; its own output may differ (its builder writes what its reader reads).
