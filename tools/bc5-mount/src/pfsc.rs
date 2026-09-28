// SPDX-License-Identifier: GPL-2.0-only
//! PFSC stream: 64 KiB logical blocks, each stored raw or as one zlib stream.
//! Layout: `docs/formats/ffpfsc.md` §6. [`PfscReader`] exposes the decoded
//! bytes as a [`ReadAt`] with a small block cache.

use std::collections::VecDeque;
use std::io::{self, Read};
use std::sync::Mutex;

use crate::error::{bail_format, Error, Result};
use crate::io::{Le, ReadAt};

const LAYER: &str = "pfsc";

/// `"PFSC"` little-endian.
pub const MAGIC: u32 = 0x4353_4650;
/// The version-like field at 0x08.
pub const VERSION_FIELD: u32 = 6;
/// Logical block size; the only value readers accept.
pub const BLOCK_SIZE: u32 = 0x10000;
/// Bytes of the fixed header.
pub const HEADER_LEN: usize = 0x30;
/// Where the offset table always starts.
pub const TABLE_OFFSET: u64 = 0x400;
/// Smallest possible data start (one logical block of header).
pub const INITIAL_DATA_OFFSET: u64 = 0x10000;
/// Sanity limit on block count (16 Mi blocks = 1 TiB logical).
pub const MAX_BLOCKS: u64 = 1 << 24;
/// Decoded blocks kept in memory.
const CACHE_BLOCKS: usize = 16;

/// The fixed PFSC header.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Header {
    /// Always [`BLOCK_SIZE`].
    pub block_size: u32,
    /// Always [`TABLE_OFFSET`].
    pub table_offset: u64,
    /// Offset of the first stored block, relative to the stream start.
    pub data_start: u64,
    /// Logical length, padded to a multiple of `block_size`.
    pub data_length: u64,
}

impl Header {
    /// Parses and validates the 0x30-byte header (without the offset table).
    pub fn parse(bytes: &[u8]) -> Result<Self> {
        let le = Le(bytes);
        let (Some(magic), Some(unk4), Some(unk8), Some(block_size)) =
            (le.u32(0x00), le.u32(0x04), le.u32(0x08), le.u32(0x0C))
        else {
            bail_format!(LAYER, "header shorter than {HEADER_LEN:#x} bytes");
        };
        let (Some(block_size2), Some(table_offset), Some(data_start), Some(data_length)) =
            (le.i64(0x10), le.i64(0x18), le.u64(0x20), le.i64(0x28))
        else {
            bail_format!(LAYER, "header shorter than {HEADER_LEN:#x} bytes");
        };
        if magic != MAGIC {
            bail_format!(LAYER, "bad magic {magic:#x}");
        }
        if unk4 != 0 || unk8 != VERSION_FIELD {
            bail_format!(
                LAYER,
                "unexpected header fields {unk4}/{unk8}, expected 0/{VERSION_FIELD}"
            );
        }
        if block_size != BLOCK_SIZE || block_size2 != i64::from(BLOCK_SIZE) {
            bail_format!(
                LAYER,
                "block size {block_size:#x}/{block_size2:#x}, expected {BLOCK_SIZE:#x}"
            );
        }
        if u64::try_from(table_offset) != Ok(TABLE_OFFSET) {
            bail_format!(
                LAYER,
                "offset table at {table_offset:#x}, expected {TABLE_OFFSET:#x}"
            );
        }
        if data_start < INITIAL_DATA_OFFSET || data_start % u64::from(BLOCK_SIZE) != 0 {
            bail_format!(
                LAYER,
                "data start {data_start:#x} is not a block multiple >= {INITIAL_DATA_OFFSET:#x}"
            );
        }
        let Ok(data_length) = u64::try_from(data_length) else {
            bail_format!(LAYER, "negative data length");
        };
        if data_length % u64::from(BLOCK_SIZE) != 0 {
            bail_format!(
                LAYER,
                "data length {data_length} is not a multiple of the block size"
            );
        }
        let blocks = data_length / u64::from(BLOCK_SIZE);
        if blocks > MAX_BLOCKS {
            bail_format!(LAYER, "{blocks} blocks exceeds the safety limit");
        }
        if header_size(blocks) > data_start {
            bail_format!(
                LAYER,
                "offset table for {blocks} blocks overlaps data at {data_start:#x}"
            );
        }
        Ok(Self {
            block_size,
            table_offset: TABLE_OFFSET,
            data_start,
            data_length,
        })
    }

    /// Number of logical blocks.
    pub fn block_count(&self) -> u64 {
        self.data_length / u64::from(self.block_size)
    }

    /// Encodes the fixed header.
    pub fn encode(&self) -> [u8; HEADER_LEN] {
        let mut b = [0u8; HEADER_LEN];
        b[0x00..0x04].copy_from_slice(&MAGIC.to_le_bytes());
        b[0x08..0x0C].copy_from_slice(&VERSION_FIELD.to_le_bytes());
        b[0x0C..0x10].copy_from_slice(&self.block_size.to_le_bytes());
        b[0x10..0x18].copy_from_slice(&u64::from(self.block_size).to_le_bytes());
        b[0x18..0x20].copy_from_slice(&self.table_offset.to_le_bytes());
        b[0x20..0x28].copy_from_slice(&self.data_start.to_le_bytes());
        b[0x28..0x30].copy_from_slice(&self.data_length.to_le_bytes());
        b
    }
}

/// Header size (= data start) for `block_count` blocks: one logical block,
/// grown in whole blocks when the offset table does not fit in 0xFC00 bytes.
pub fn header_size(block_count: u64) -> u64 {
    let table = (block_count + 1) * 8;
    let initial = INITIAL_DATA_OFFSET - TABLE_OFFSET;
    let extra = table.saturating_sub(initial);
    INITIAL_DATA_OFFSET + extra.div_ceil(u64::from(BLOCK_SIZE)) * u64::from(BLOCK_SIZE)
}

#[derive(Debug, Default)]
struct Cache {
    // Most recently used at the back. Linear search is fine for 16 entries.
    blocks: VecDeque<(u64, Vec<u8>)>,
}

/// Decoded view of a PFSC stream.
#[derive(Debug)]
pub struct PfscReader<R> {
    source: R,
    header: Header,
    offsets: Vec<u64>,
    logical_len: u64,
    cache: Mutex<Cache>,
}

impl<R: ReadAt> PfscReader<R> {
    /// Opens a stream. `source` must span exactly the stored stream.
    /// `logical_len` is the true payload length (from the PFS inode); it must
    /// lie within the last block of `data_length`. `None` uses `data_length`.
    pub fn open(source: R, logical_len: Option<u64>) -> Result<Self> {
        let mut head = [0u8; HEADER_LEN];
        source
            .read_exact_at(0, &mut head)
            .map_err(|e| Error::format(LAYER, format!("cannot read the header: {e}")))?;
        let header = Header::parse(&head)?;
        let stored_len = source.len();
        if header.data_start > stored_len {
            bail_format!(
                LAYER,
                "data start {:#x} beyond stream length {stored_len}",
                header.data_start
            );
        }
        let blocks = header.block_count();
        let table_bytes = (blocks + 1) * 8;
        let table = source
            .read_vec_at(TABLE_OFFSET, table_bytes as usize)
            .map_err(|e| Error::format(LAYER, format!("cannot read the offset table: {e}")))?;
        let mut offsets = Vec::with_capacity(blocks as usize + 1);
        for (i, chunk) in table.chunks_exact(8).enumerate() {
            let off = u64::from_le_bytes(chunk.try_into().expect("chunks_exact yields 8 bytes"));
            if off < header.data_start || off > stored_len {
                bail_format!(LAYER, "offset[{i}] = {off:#x} outside the stored data");
            }
            if let Some(&prev) = offsets.last() {
                let stored = off.saturating_sub(prev);
                if off < prev || stored == 0 || stored > u64::from(BLOCK_SIZE) {
                    bail_format!(
                        LAYER,
                        "block {} has an invalid stored size ({prev:#x}..{off:#x})",
                        i - 1
                    );
                }
            } else if off != header.data_start {
                bail_format!(
                    LAYER,
                    "first block at {off:#x}, expected data start {:#x}",
                    header.data_start
                );
            }
            offsets.push(off);
        }
        let logical_len = match logical_len {
            None => header.data_length,
            Some(len) => {
                if len > header.data_length || header.data_length - len >= u64::from(BLOCK_SIZE) {
                    bail_format!(
                        LAYER,
                        "logical length {len} does not fit the padded length {}",
                        header.data_length
                    );
                }
                len
            }
        };
        Ok(Self {
            source,
            header,
            offsets,
            logical_len,
            cache: Mutex::new(Cache::default()),
        })
    }

    /// The parsed header.
    pub fn header(&self) -> &Header {
        &self.header
    }

    /// Number of logical blocks.
    pub fn block_count(&self) -> u64 {
        self.header.block_count()
    }

    /// Number of blocks stored compressed (stored size < block size).
    pub fn compressed_block_count(&self) -> u64 {
        self.offsets
            .windows(2)
            .filter(|w| w[1] - w[0] < u64::from(BLOCK_SIZE))
            .count() as u64
    }

    /// Bytes the stream occupies on disk.
    pub fn stored_len(&self) -> u64 {
        self.source.len()
    }

    /// Decodes block `idx` from the source (no cache).
    fn decode_block(&self, idx: u64) -> Result<Vec<u8>> {
        let (Some(&start), Some(&end)) = (
            self.offsets.get(idx as usize),
            self.offsets.get(idx as usize + 1),
        ) else {
            bail_format!(LAYER, "block {idx} outside 0..{}", self.block_count());
        };
        let stored = self.source.read_vec_at(start, (end - start) as usize)?;
        if stored.len() == BLOCK_SIZE as usize {
            return Ok(stored);
        }
        let mut out = vec![0u8; BLOCK_SIZE as usize];
        let mut z = flate2::read::ZlibDecoder::new(stored.as_slice());
        z.read_exact(&mut out).map_err(|e| {
            Error::format(
                LAYER,
                format!("block {idx} does not inflate to a full block: {e}"),
            )
        })?;
        let mut extra = [0u8; 1];
        match z.read(&mut extra) {
            Ok(0) => Ok(out),
            Ok(_) => Err(Error::format(
                LAYER,
                format!("block {idx} inflates to more than one block"),
            )),
            Err(e) => Err(Error::format(LAYER, format!("block {idx}: {e}"))),
        }
    }

    /// Copies `buf.len()` bytes from logical block `idx` at `within`. The
    /// cache lock is held only for lookup and insertion, so several threads can
    /// inflate different blocks at the same time.
    fn copy_from_block(&self, idx: u64, within: usize, buf: &mut [u8]) -> Result<()> {
        {
            let mut cache = self
                .cache
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            if let Some(pos) = cache.blocks.iter().position(|(i, _)| *i == idx) {
                let entry = cache.blocks.remove(pos).expect("position came from iter");
                buf.copy_from_slice(&entry.1[within..within + buf.len()]);
                cache.blocks.push_back(entry);
                return Ok(());
            }
        }
        let block = self.decode_block(idx)?;
        buf.copy_from_slice(&block[within..within + buf.len()]);
        let mut cache = self
            .cache
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if !cache.blocks.iter().any(|(i, _)| *i == idx) {
            cache.blocks.push_back((idx, block));
            if cache.blocks.len() > CACHE_BLOCKS {
                cache.blocks.pop_front();
            }
        }
        Ok(())
    }
}

impl<R: ReadAt> ReadAt for PfscReader<R> {
    fn len(&self) -> u64 {
        self.logical_len
    }

    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        if offset >= self.logical_len {
            return Ok(0);
        }
        let avail = usize::try_from(self.logical_len - offset).unwrap_or(usize::MAX);
        let total = buf.len().min(avail);
        let bs = u64::from(BLOCK_SIZE);
        let mut done = 0usize;
        while done < total {
            let pos = offset + done as u64;
            let idx = pos / bs;
            let within = (pos % bs) as usize;
            let n = (total - done).min(BLOCK_SIZE as usize - within);
            self.copy_from_block(idx, within, &mut buf[done..done + n])
                .map_err(|e| io::Error::other(e.to_string()))?;
            done += n;
        }
        Ok(total)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn header_sizes_follow_the_formula() {
        assert_eq!(header_size(0), 0x10000);
        assert_eq!(header_size(1), 0x10000);
        assert_eq!(header_size(0xFC00 / 8 - 1), 0x10000);
        assert_eq!(header_size(0xFC00 / 8), 0x20000);
        assert_eq!(header_size(2_501_536), 0x132_0000); // experiment 0001
    }

    #[test]
    fn header_round_trip_and_validation() {
        let h = Header {
            block_size: BLOCK_SIZE,
            table_offset: TABLE_OFFSET,
            data_start: 0x10000,
            data_length: 0x30000,
        };
        assert_eq!(Header::parse(&h.encode()).unwrap(), h);
        let mut b = h.encode();
        b[0x0E] = 0; // block size 0x10000 -> 0
        assert!(Header::parse(&b).is_err());
        let mut b = h.encode();
        b[0x28] = 1; // unaligned length
        assert!(Header::parse(&b).is_err());
        assert!(Header::parse(&b[..0x20]).is_err());
    }

    proptest! {
        #[test]
        fn header_parse_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..0x40)) {
            let _ = Header::parse(&bytes);
        }

        #[test]
        fn open_never_panics_on_garbage(bytes in proptest::collection::vec(any::<u8>(), 0..0x500)) {
            let _ = PfscReader::open(bytes, None);
        }
    }
}
