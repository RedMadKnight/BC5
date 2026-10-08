// SPDX-License-Identifier: GPL-2.0-only
//! `naps_pkg_layout.dat`: the map from the inner image's logical bytes to the
//! stored (raw or Kraken-compressed) bytes of `pfs_image.dat`. The layout is
//! described in `docs/formats/ps5pkg.md` §4.
//!
//! Layout: a 16-byte packed header, one 8-byte digest per 64 KiB block of the
//! stored image, 8-byte shuffle patterns, 6-byte file-offset entries (`fidx`),
//! 10-byte `u2c` entries (the first `CblockInfo` record of every 256 KiB logical
//! block, eight per entry), then 9-byte `CblockInfo` records. Where the `u2c`
//! table starts differs between producers (right after `fidx`, or `fidx`
//! padded to 16 bytes); the `CblockInfo` table starts on an 8-byte boundary after
//! `u2c`. Both placements are tried and the one whose records map the whole
//! image is kept.

use crate::error::{bail_format, Error, Result};
use crate::io::Le;

const LAYER: &str = "naps";

/// Logical block size: one `CblockInfo` record covers up to this much of a file.
pub const UBLOCK_SIZE: u64 = 0x40000;
/// The header counts the stored image in these.
pub const OUTER_BLOCK_SIZE: u64 = 0x10000;
/// Size of the packed header.
pub const HEADER_SIZE: usize = 16;
const OUTER_STRIDE: usize = 8;
const SHUFFLE_STRIDE: usize = 8;
const FILE_OFFSET_STRIDE: usize = 6;
const U2C_STRIDE: usize = 10;
/// Size of one `CblockInfo` record.
pub const CBLOCK_STRIDE: usize = 9;
/// File-offset kind of the mount-size entry at the end and of sparse regions.
pub const KIND_MOUNT: u8 = 0x40;
/// Kraken flag of a record ([`Cblock::flags`]): the first 128 KiB chunk's
/// literals are deltas against the match source (otherwise plain bytes).
pub const FLAG_CHUNK0_SUB_LITERALS: u8 = 0x01;
/// The first chunk is an LZ chunk (otherwise a bare entropy-coded array).
pub const FLAG_CHUNK0_LZ: u8 = 0x02;
/// The second chunk's literals are deltas.
pub const FLAG_CHUNK1_SUB_LITERALS: u8 = 0x10;
/// The second chunk is an LZ chunk.
pub const FLAG_CHUNK1_LZ: u8 = 0x20;
/// The second chunk decodes on its own instead of continuing the first.
pub const FLAG_CHUNK1_RESTART: u8 = 0x40;

/// The packed header.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Counts {
    /// File-offset entries (stored minus one).
    pub num_files: u32,
    /// 2 = Kraken.
    pub compression_type: u8,
    /// Key table entries (stored minus one).
    pub num_keys: u32,
    /// Shuffle patterns.
    pub num_shuffle: u32,
    /// 256 KiB logical blocks of the mount.
    pub num_ublocks: u32,
    /// 64 KiB blocks of the stored image.
    pub num_outer_blocks: u32,
    /// `CblockInfo` records (stored minus two).
    pub num_cblock_info: u32,
}

impl Counts {
    /// `u2c` entries: one per eight logical blocks.
    pub fn num_u2c(&self) -> usize {
        ((self.num_ublocks + 8) >> 3) as usize
    }

    /// Parses the 16-byte header.
    pub fn parse(blob: &[u8]) -> Result<Self> {
        let le = Le(blob);
        let (Some(w0), Some(w1)) = (le.u64(0), le.u64(8)) else {
            bail_format!(LAYER, "header is truncated");
        };
        let counts = Counts {
            num_files: (w0 as u32 & 0xff_ffff) + 1,
            compression_type: ((w0 >> 24) & 3) as u8,
            num_keys: ((w0 >> 26) & 3) as u32 + 1,
            num_shuffle: ((w0 >> 28) & 0xf) as u32,
            num_ublocks: ((w0 >> 32) & 0xff_ffff) as u32,
            num_outer_blocks: (w1 & 0xff_ffff) as u32,
            num_cblock_info: ((w1 >> 24) & 0xff_ffff) as u32 + 2,
        };
        if counts.compression_type != 2 {
            return Err(Error::Unsupported(format!(
                "naps compression type {} (only 2, Kraken, is known)",
                counts.compression_type
            )));
        }
        Ok(counts)
    }

    /// Encodes the header.
    pub fn encode(&self) -> [u8; HEADER_SIZE] {
        let w0: u64 = u64::from((self.num_files - 1) & 0xff_ffff)
            | (u64::from(self.compression_type & 3) << 24)
            | (u64::from((self.num_keys - 1) & 3) << 26)
            | (u64::from(self.num_shuffle & 0xf) << 28)
            | (u64::from(self.num_ublocks & 0xff_ffff) << 32);
        let w1: u64 = u64::from(self.num_outer_blocks & 0xff_ffff)
            | (u64::from((self.num_cblock_info - 2) & 0xff_ffff) << 24);
        let mut h = [0u8; HEADER_SIZE];
        h[..8].copy_from_slice(&w0.to_le_bytes());
        h[8..].copy_from_slice(&w1.to_le_bytes());
        h
    }
}

/// A file-offset (`fidx`) entry: where a file's data starts in the logical
/// image. Kind [`KIND_MOUNT`] marks the mount size (the last entry) and sparse
/// regions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FileOffset {
    /// Entry kind.
    pub kind: u8,
    /// Logical byte offset.
    pub offset: u64,
}

impl FileOffset {
    /// Decodes a 6-byte entry: 40-bit little-endian offset, kind byte.
    pub fn parse(rec: &[u8]) -> Result<Self> {
        if rec.len() < FILE_OFFSET_STRIDE {
            bail_format!(LAYER, "file-offset entry is truncated");
        }
        let mut offset = 0u64;
        for (i, &b) in rec[..5].iter().enumerate() {
            offset |= u64::from(b) << (8 * i);
        }
        Ok(Self {
            kind: rec[5],
            offset,
        })
    }

    /// Encodes the entry.
    pub fn encode(&self) -> [u8; FILE_OFFSET_STRIDE] {
        let mut v = [0u8; FILE_OFFSET_STRIDE];
        for (i, b) in v[..5].iter_mut().enumerate() {
            *b = (self.offset >> (8 * i)) as u8;
        }
        v[5] = self.kind;
        v
    }
}

/// One `CblockInfo` record. A data record describes one stored block; a run
/// base re-anchors the on-disk cursor for the records that follow it.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Cblock {
    /// Run base (bit 18) or data record.
    pub is_run_base: bool,
    /// Data record: the block's stored offset modulo 256 KiB; the next
    /// record's value marks where this block's stored bytes end. Run base:
    /// unused by the reader (the previous run's end).
    pub coffset_mod: u32,
    /// Data record: stored length of the first 128 KiB chunk minus one.
    pub clen_even_minus1: u32,
    /// Data record: bits 56–58, the first chunk's Kraken flags (bit 1 = LZ).
    pub kde_predictor: u8,
    /// Data record: bits 59–62, the second chunk's Kraken flags.
    pub shuffle_idx: u8,
    /// Run base: twice the index of the 256 KiB stored block the run starts in.
    pub coffset_start_256k: u32,
}

impl Cblock {
    /// Stored length of the first Kraken chunk of a block.
    pub fn even_comp(&self) -> u32 {
        self.clen_even_minus1 + 1
    }

    /// True when the first chunk is an LZ chunk (a stored block has neither).
    pub fn kraken(&self) -> bool {
        self.kde_predictor & 2 != 0
    }

    /// The block's Kraken flags (see the `FLAG_*` constants).
    pub fn flags(&self) -> u8 {
        (self.kde_predictor & 7) | ((self.shuffle_idx & 0xf) << 4)
    }

    /// Where a run starts in the stored image: the run base's 256 KiB block
    /// plus the byte offset carried by the first data record after it.
    pub fn run_on_disk(&self, first: &Cblock) -> u64 {
        u64::from(self.coffset_start_256k / 2) * UBLOCK_SIZE + u64::from(first.coffset_mod)
    }

    /// Decodes a 9-byte record.
    pub fn parse(raw: &[u8]) -> Result<Self> {
        if raw.len() < CBLOCK_STRIDE {
            bail_format!(LAYER, "CblockInfo record is truncated");
        }
        let lo = u64::from_le_bytes(raw[..8].try_into().expect("8 bytes"));
        let hi = u64::from(raw[8]);
        let coffset_mod = (lo & 0x3ffff) as u32;
        Ok(if (lo >> 18) & 1 == 0 {
            Cblock {
                is_run_base: false,
                coffset_mod,
                clen_even_minus1: ((lo >> 38) & 0x1ffff) as u32,
                kde_predictor: ((lo >> 56) & 7) as u8,
                shuffle_idx: ((lo >> 59) & 0xf) as u8,
                coffset_start_256k: 0,
            }
        } else {
            Cblock {
                is_run_base: true,
                coffset_mod,
                coffset_start_256k: (((lo >> 49) & 0x7fff) | ((hi & 0x1ff) << 15)) as u32,
                ..Cblock::default()
            }
        })
    }

    /// Encodes the record (the fields the reader uses; the rest zero).
    pub fn encode(&self) -> [u8; CBLOCK_STRIDE] {
        let mut lo = u64::from(self.coffset_mod & 0x3ffff);
        let mut hi = 0u8;
        if self.is_run_base {
            lo |= 1 << 18;
            lo |= u64::from(self.coffset_start_256k & 0x7fff) << 49;
            hi = ((self.coffset_start_256k >> 15) & 0x1ff) as u8;
        } else {
            lo |= u64::from(self.clen_even_minus1 & 0x1ffff) << 38;
            lo |= u64::from(self.kde_predictor & 7) << 56;
            lo |= u64::from(self.shuffle_idx & 0xf) << 59;
        }
        let mut v = [0u8; CBLOCK_STRIDE];
        v[..8].copy_from_slice(&lo.to_le_bytes());
        v[8] = hi;
        v
    }
}

/// One stored block of the inner image, in logical order.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Block {
    /// Logical byte offset.
    pub logical: u64,
    /// Offset in the stored image.
    pub on_disk: u64,
    /// Stored bytes; 0 for a sparse block that reads as zeros.
    pub comp: u32,
    /// Logical bytes.
    pub uncomp: u32,
    /// Kraken-compressed (otherwise stored as is).
    pub kraken: bool,
    /// Stored length of the first Kraken chunk.
    pub even_comp: u32,
    /// Kraken flags.
    pub flags: u8,
}

/// A `CblockInfo` table placement that passed the structural checks.
#[derive(Debug)]
pub struct Candidate {
    /// Byte offset of the table in the blob.
    pub start: usize,
    /// The records.
    pub cblocks: Vec<Cblock>,
}

/// A parsed layout.
#[derive(Debug)]
pub struct Layout {
    /// The header.
    pub counts: Counts,
    /// File-offset entries sorted by offset (stable, so entries sharing an
    /// offset keep their table order).
    pub file_offsets: Vec<FileOffset>,
    /// `CblockInfo` table placements that passed the structural checks.
    pub candidates: Vec<Candidate>,
}

impl Layout {
    /// Parses the whole blob.
    pub fn parse(blob: &[u8]) -> Result<Layout> {
        let counts = Counts::parse(blob)?;
        let pos = HEADER_SIZE
            + counts.num_outer_blocks as usize * OUTER_STRIDE
            + counts.num_shuffle as usize * SHUFFLE_STRIDE;
        let n_files = counts.num_files as usize;
        let fidx_end = pos + n_files * FILE_OFFSET_STRIDE;
        if fidx_end > blob.len() {
            bail_format!(
                LAYER,
                "file-offset table runs past the {}-byte layout",
                blob.len()
            );
        }
        let mut file_offsets = Vec::with_capacity(n_files);
        for i in 0..n_files {
            let at = pos + i * FILE_OFFSET_STRIDE;
            file_offsets.push(FileOffset::parse(&blob[at..at + FILE_OFFSET_STRIDE])?);
        }
        let u2c_len = counts.num_u2c() * U2C_STRIDE;
        let mut starts: Vec<usize> = [fidx_end.next_multiple_of(16), fidx_end]
            .iter()
            .map(|&u2c| (u2c + u2c_len).next_multiple_of(8))
            .collect();
        starts.dedup();
        let image_size = u64::from(counts.num_outer_blocks) * OUTER_BLOCK_SIZE;
        let mut problems = Vec::new();
        let mut candidates = Vec::new();
        for &start in &starts {
            match read_cblocks(blob, start, counts.num_cblock_info as usize, image_size) {
                Ok(cblocks) => candidates.push(Candidate { start, cblocks }),
                Err(err) => problems.push(format!("at {start:#x}: {err}")),
            }
        }
        if candidates.is_empty() {
            bail_format!(
                LAYER,
                "no valid CblockInfo table placement ({})",
                problems.join("; ")
            );
        }
        file_offsets.sort_by_key(|f| f.offset);
        Ok(Layout {
            counts,
            file_offsets,
            candidates,
        })
    }

    /// The logical size of the inner image: the last mount-kind entry.
    pub fn mount_size(&self) -> u64 {
        self.file_offsets
            .iter()
            .rev()
            .find(|f| f.kind == KIND_MOUNT)
            .map_or(0, |f| f.offset)
    }

    /// The first file boundary after `cur`, or `mount` when there is none.
    pub fn next_boundary(&self, cur: u64, mount: u64) -> u64 {
        let i = self.file_offsets.partition_point(|f| f.offset <= cur);
        self.file_offsets
            .get(i)
            .map_or(mount, |f| f.offset.min(mount))
    }

    /// The first entry at or after `offset`, in table order among equal offsets.
    pub fn first_at_or_after(&self, offset: u64) -> Option<FileOffset> {
        let i = self.file_offsets.partition_point(|f| f.offset < offset);
        self.file_offsets.get(i).copied()
    }

    /// The logical offset where the inner metadata (superblock, inodes,
    /// directories) begins: the last file boundary below the mount size.
    pub fn metadata_base(&self) -> u64 {
        let mount = self.mount_size();
        self.file_offsets
            .iter()
            .map(|f| f.offset)
            .filter(|&o| o > 0 && o < mount)
            .max()
            .unwrap_or(0)
    }

    /// Resolves the records into blocks: the one placement whose records map
    /// the whole mount. Two placements that both do are refused.
    pub fn blocks(&self) -> Result<Vec<Block>> {
        let mount = self.mount_size();
        if mount == 0 {
            bail_format!(LAYER, "no mount-size entry in the file-offset table");
        }
        let mut walks = Vec::new();
        let mut problems = Vec::new();
        for c in &self.candidates {
            match walk_blocks(self, &c.cblocks, mount) {
                Ok(blocks) => walks.push(blocks),
                Err(err) => problems.push(format!("table at {:#x}: {err}", c.start)),
            }
        }
        if walks.len() > 1 {
            bail_format!(
                LAYER,
                "two CblockInfo placements both map the whole image; refusing to guess"
            );
        }
        walks
            .pop()
            .ok_or_else(|| Error::format(LAYER, problems.join("; ")))
    }
}

/// Reads the records and checks that every run base is followed by a data
/// record and lands inside the stored image.
fn read_cblocks(blob: &[u8], start: usize, count: usize, image_size: u64) -> Result<Vec<Cblock>> {
    let end = start + count * CBLOCK_STRIDE;
    let Some(table) = blob.get(start..end) else {
        bail_format!(
            LAYER,
            "{count} records end at {end:#x}, past the {:#x}-byte layout",
            blob.len()
        );
    };
    let records = table
        .chunks_exact(CBLOCK_STRIDE)
        .map(Cblock::parse)
        .collect::<Result<Vec<_>>>()?;
    for (i, rec) in records.iter().enumerate() {
        if !rec.is_run_base {
            continue;
        }
        match records.get(i + 1) {
            Some(next) if !next.is_run_base => {
                let at = rec.run_on_disk(next);
                if at >= image_size {
                    bail_format!(
                        LAYER,
                        "run base {i} points at {at:#x}, past the {image_size:#x}-byte image"
                    );
                }
            }
            _ => bail_format!(LAYER, "run base {i} is not followed by a data record"),
        }
    }
    Ok(records)
}

/// Builds the logical-to-stored block list from the records.
fn walk_blocks(layout: &Layout, recs: &[Cblock], mount: u64) -> Result<Vec<Block>> {
    let mut out = Vec::with_capacity(layout.counts.num_ublocks as usize + 16);
    let mut on_disk = 0u64;
    let mut logical = 0u64;
    let mut i = 0;
    while i < recs.len() {
        let rec = recs[i];
        if rec.is_run_base {
            match recs.get(i + 1) {
                Some(next) if !next.is_run_base => on_disk = rec.run_on_disk(next),
                _ => bail_format!(LAYER, "run base {i} is not followed by a data record"),
            }
            i += 1;
            continue;
        }
        append_sparse(layout, mount, &mut logical, &mut out)?;
        if logical >= mount || i + 1 >= recs.len() {
            break;
        }
        let file_end = layout.next_boundary(logical, mount);
        let uncomp = UBLOCK_SIZE.min(file_end.saturating_sub(logical)) as u32;
        if uncomp == 0 {
            break;
        }
        // The next record's offset within its 256 KiB block marks where this
        // block's stored bytes end, for stored and Kraken blocks alike.
        let mut diff = i64::from(recs[i + 1].coffset_mod) - i64::from(rec.coffset_mod);
        if diff <= 0 {
            diff += 0x40000;
        }
        let Ok(comp) = u32::try_from(diff) else {
            bail_format!(LAYER, "record {i}: stored length {diff} out of range");
        };
        out.push(Block {
            logical,
            on_disk,
            comp,
            uncomp,
            kraken: rec.kraken() || comp != uncomp,
            even_comp: rec.even_comp(),
            flags: rec.flags(),
        });
        on_disk += u64::from(comp);
        logical += u64::from(uncomp);
        if logical >= mount {
            break;
        }
        i += 1;
    }
    append_sparse(layout, mount, &mut logical, &mut out)?;
    if logical != mount {
        bail_format!(
            LAYER,
            "the records cover {logical:#x} bytes, but the mount size is {mount:#x}"
        );
    }
    Ok(out)
}

/// A mount-kind entry below the mount size opens a region with no records
/// that reads as zeros, up to the next boundary. Whether a producer writes one
/// entry per 256 KiB of such a region or one per region is not known
/// (`docs/formats/ps5pkg.md` §4); both read the same here.
fn append_sparse(
    layout: &Layout,
    mount: u64,
    logical: &mut u64,
    out: &mut Vec<Block>,
) -> Result<()> {
    while *logical < mount {
        match layout.first_at_or_after(*logical) {
            Some(entry) if entry.kind == KIND_MOUNT && entry.offset == *logical => {}
            _ => return Ok(()),
        }
        let end = layout.next_boundary(*logical, mount);
        if end <= *logical {
            bail_format!(LAYER, "empty sparse region at {:#x}", *logical);
        }
        while *logical < end {
            let len = UBLOCK_SIZE.min(end - *logical) as u32;
            out.push(Block {
                logical: *logical,
                on_disk: 0,
                comp: 0,
                uncomp: len,
                kraken: false,
                even_comp: 0,
                flags: 0,
            });
            *logical += u64::from(len);
        }
    }
    Ok(())
}

/// Writes a layout blob for the fixture generator: `u2c` right after `fidx`,
/// the `CblockInfo` table on the next 8-byte boundary, everything else zero.
pub fn encode_layout(
    counts: &Counts,
    file_offsets: &[FileOffset],
    u2c_first_record: &[u32],
    cblocks: &[Cblock],
) -> Vec<u8> {
    let mut v = Vec::new();
    v.extend_from_slice(&counts.encode());
    v.resize(v.len() + counts.num_outer_blocks as usize * OUTER_STRIDE, 0);
    v.resize(v.len() + counts.num_shuffle as usize * SHUFFLE_STRIDE, 0);
    for f in file_offsets {
        v.extend_from_slice(&f.encode());
    }
    for chunk in u2c_first_record.chunks(8) {
        let base = chunk[0];
        v.extend_from_slice(&base.to_le_bytes()[..3]);
        for k in 1..8 {
            v.push(chunk.get(k).map_or(0, |&r| (r - base) as u8));
        }
    }
    v.resize(v.len().next_multiple_of(8), 0);
    for c in cblocks {
        v.extend_from_slice(&c.encode());
    }
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn header_round_trips() {
        let c = Counts {
            num_files: 64,
            compression_type: 2,
            num_keys: 1,
            num_shuffle: 0,
            num_ublocks: 40808,
            num_outer_blocks: 68506,
            num_cblock_info: 43581,
        };
        assert_eq!(Counts::parse(&c.encode()).unwrap(), c);
    }

    #[test]
    fn data_record_round_trips() {
        let rec = Cblock {
            is_run_base: false,
            coffset_mod: 0x2e07d,
            clen_even_minus1: 75656,
            kde_predictor: 2,
            shuffle_idx: 2,
            coffset_start_256k: 0,
        };
        let back = Cblock::parse(&rec.encode()).unwrap();
        assert_eq!(back, rec);
        assert_eq!(back.even_comp(), 75657);
        assert_eq!(back.flags(), 0x22);
        assert!(back.kraken());
    }

    #[test]
    fn run_base_round_trips() {
        let rec = Cblock {
            is_run_base: true,
            coffset_mod: 0x30000,
            coffset_start_256k: 772_164,
            ..Cblock::default()
        };
        let back = Cblock::parse(&rec.encode()).unwrap();
        assert_eq!(back, rec);
        let first = Cblock {
            coffset_mod: 768,
            ..Cblock::default()
        };
        assert_eq!(back.run_on_disk(&first), 386_082 * UBLOCK_SIZE + 768);
    }

    #[test]
    fn blocks_follow_file_boundaries_and_run_bases() {
        let data = |coffset_mod| Cblock {
            coffset_mod,
            ..Cblock::default()
        };
        let run = Cblock {
            is_run_base: true,
            coffset_mod: 0x10000,
            coffset_start_256k: 6,
            ..Cblock::default()
        };
        let layout = Layout {
            counts: Counts {
                num_files: 3,
                compression_type: 2,
                num_keys: 1,
                num_shuffle: 0,
                num_ublocks: 2,
                num_outer_blocks: 0,
                num_cblock_info: 5,
            },
            file_offsets: vec![
                FileOffset { kind: 0, offset: 0 },
                FileOffset {
                    kind: 0,
                    offset: 0x50000,
                },
                FileOffset {
                    kind: KIND_MOUNT,
                    offset: 0x60000,
                },
            ],
            candidates: vec![Candidate {
                start: 0,
                cblocks: vec![data(0), data(0), run, data(0x100), data(0x10100)],
            }],
        };
        let blocks = layout.blocks().unwrap();
        let summary: Vec<_> = blocks
            .iter()
            .map(|b| (b.logical, b.on_disk, b.comp, b.uncomp, b.kraken))
            .collect();
        assert_eq!(
            summary,
            vec![
                (0, 0, 0x40000, 0x40000, false),
                (0x40000, 0x40000, 0x10000, 0x10000, false),
                (0x50000, 3 * 0x40000 + 0x100, 0x10000, 0x10000, false),
            ]
        );
    }

    #[test]
    fn encoded_layout_parses_back() {
        let counts = Counts {
            num_files: 2,
            compression_type: 2,
            num_keys: 1,
            num_shuffle: 0,
            num_ublocks: 1,
            num_outer_blocks: 1,
            num_cblock_info: 3,
        };
        let fidx = [
            FileOffset { kind: 0, offset: 0 },
            FileOffset {
                kind: KIND_MOUNT,
                offset: 0x10000,
            },
        ];
        let recs = [
            Cblock {
                is_run_base: true,
                ..Cblock::default()
            },
            Cblock {
                coffset_mod: 0,
                clen_even_minus1: 0xffff,
                ..Cblock::default()
            },
            Cblock {
                coffset_mod: 0x10000,
                ..Cblock::default()
            },
        ];
        let blob = encode_layout(&counts, &fidx, &[1], &recs);
        let layout = Layout::parse(&blob).unwrap();
        assert_eq!(layout.mount_size(), 0x10000);
        let blocks = layout.blocks().unwrap();
        assert_eq!(blocks.len(), 1);
        assert_eq!(
            (blocks[0].on_disk, blocks[0].comp, blocks[0].uncomp),
            (0, 0x10000, 0x10000)
        );
        assert!(!blocks[0].kraken);
    }
}
