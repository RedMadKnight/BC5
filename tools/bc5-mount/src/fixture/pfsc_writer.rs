// SPDX-License-Identifier: GPL-2.0-only
//! Streaming PFSC encoder: a [`Write`] sink that compresses 64 KiB blocks as
//! they arrive and writes the header and offset table at the end.

use std::io::{self, Seek, SeekFrom, Write};

use flate2::write::ZlibEncoder;
use flate2::Compression;

use crate::pfsc::{header_size, Header, BLOCK_SIZE, TABLE_OFFSET};

/// Keep a compressed block only if it saves at least this much (percent).
pub const MIN_GAIN_PERCENT: u64 = 5;

/// What [`PfscEncoder::finish`] reports.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PfscStats {
    /// Bytes written for the whole stream (header + data).
    pub stored_len: u64,
    /// Logical blocks.
    pub blocks: u64,
    /// Blocks stored compressed.
    pub compressed_blocks: u64,
    /// Padded logical length (`blocks * 64 KiB`).
    pub data_length: u64,
}

/// Encodes a logical stream of known length into `out`, starting at the
/// sink's current position.
#[derive(Debug)]
pub struct PfscEncoder<W: Write + Seek> {
    out: W,
    start: u64,
    data_start: u64,
    logical_len: u64,
    received: u64,
    pending: Vec<u8>,
    offsets: Vec<u64>,
    compressed_blocks: u64,
    finished: bool,
}

impl<W: Write + Seek> PfscEncoder<W> {
    /// Reserves the header and prepares to receive exactly `logical_len` bytes.
    pub fn new(mut out: W, logical_len: u64) -> io::Result<Self> {
        let blocks = logical_len.div_ceil(u64::from(BLOCK_SIZE));
        let data_start = header_size(blocks);
        let start = out.stream_position()?;
        write_zeros(&mut out, data_start)?;
        Ok(Self {
            out,
            start,
            data_start,
            logical_len,
            received: 0,
            pending: Vec::with_capacity(BLOCK_SIZE as usize),
            offsets: vec![data_start],
            compressed_blocks: 0,
            finished: false,
        })
    }

    fn flush_block(&mut self) -> io::Result<()> {
        self.pending.resize(BLOCK_SIZE as usize, 0);
        let mut z = ZlibEncoder::new(Vec::with_capacity(BLOCK_SIZE as usize), Compression::new(6));
        z.write_all(&self.pending)?;
        let compressed = z.finish()?;
        let gain = (u64::from(BLOCK_SIZE) - (compressed.len() as u64).min(u64::from(BLOCK_SIZE)))
            * 100
            / u64::from(BLOCK_SIZE);
        let keep = compressed.len() < BLOCK_SIZE as usize && gain >= MIN_GAIN_PERCENT;
        let chosen = if keep { &compressed } else { &self.pending };
        self.out.write_all(chosen)?;
        if keep {
            self.compressed_blocks += 1;
        }
        let last = *self.offsets.last().expect("offsets starts with data_start");
        self.offsets.push(last + chosen.len() as u64);
        self.pending.clear();
        Ok(())
    }

    /// Pads the last block, writes header and table, and returns the sink
    /// positioned at the end of the stream.
    pub fn finish(mut self) -> io::Result<(W, PfscStats)> {
        if self.received != self.logical_len {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!(
                    "PFSC encoder received {} bytes, expected {}",
                    self.received, self.logical_len
                ),
            ));
        }
        if !self.pending.is_empty() {
            self.flush_block()?;
        }
        self.finished = true;
        let blocks = self.offsets.len() as u64 - 1;
        let data_length = blocks * u64::from(BLOCK_SIZE);
        let end = *self.offsets.last().expect("non-empty");
        let header = Header {
            block_size: BLOCK_SIZE,
            table_offset: TABLE_OFFSET,
            data_start: self.data_start,
            data_length,
        };
        self.out.seek(SeekFrom::Start(self.start))?;
        self.out.write_all(&header.encode())?;
        self.out.seek(SeekFrom::Start(self.start + TABLE_OFFSET))?;
        let mut table = Vec::with_capacity(self.offsets.len() * 8);
        for off in &self.offsets {
            table.extend_from_slice(&off.to_le_bytes());
        }
        self.out.write_all(&table)?;
        self.out.seek(SeekFrom::Start(self.start + end))?;
        Ok((
            self.out,
            PfscStats {
                stored_len: end,
                blocks,
                compressed_blocks: self.compressed_blocks,
                data_length,
            },
        ))
    }
}

impl<W: Write + Seek> Write for PfscEncoder<W> {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        if self.received + buf.len() as u64 > self.logical_len {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "PFSC encoder received more than the declared length",
            ));
        }
        let mut rest = buf;
        while !rest.is_empty() {
            let room = BLOCK_SIZE as usize - self.pending.len();
            let n = room.min(rest.len());
            self.pending.extend_from_slice(&rest[..n]);
            rest = &rest[n..];
            if self.pending.len() == BLOCK_SIZE as usize {
                self.flush_block()?;
            }
        }
        self.received += buf.len() as u64;
        Ok(buf.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        self.out.flush()
    }
}

use super::write_zeros;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::io::ReadAt;
    use crate::pfsc::PfscReader;
    use std::io::Cursor;

    fn encode(data: &[u8]) -> (Vec<u8>, PfscStats) {
        let mut enc = PfscEncoder::new(Cursor::new(Vec::new()), data.len() as u64).unwrap();
        enc.write_all(data).unwrap();
        let (cur, stats) = enc.finish().unwrap();
        let v = cur.into_inner();
        assert_eq!(v.len() as u64, stats.stored_len);
        (v, stats)
    }

    #[test]
    fn empty_stream() {
        let (v, stats) = encode(&[]);
        assert_eq!(stats.blocks, 0);
        assert_eq!(v.len(), 0x10000);
        let r = PfscReader::open(v, Some(0)).unwrap();
        assert_eq!(r.len(), 0);
    }

    #[test]
    fn raw_and_compressed_blocks_round_trip() {
        let mut data = vec![0u8; 3 * 0x10000 + 123];
        // Block 1 is incompressible noise; blocks 0, 2 and 3 are zeros.
        crate::fixture::Content::Pattern {
            seed: 11,
            len: 0x10000,
        }
        .fill(0, &mut data[0x10000..0x20000]);
        let (v, stats) = encode(&data);
        assert_eq!(stats.blocks, 4);
        assert_eq!(stats.compressed_blocks, 3);
        let r = PfscReader::open(v, Some(data.len() as u64)).unwrap();
        assert_eq!(r.len(), data.len() as u64);
        assert_eq!(r.read_vec_at(0, data.len()).unwrap(), data);
        assert_eq!(
            r.read_vec_at(0x0FFF0, 0x20).unwrap(),
            &data[0x0FFF0..0x10010]
        );
        let mut tail = [9u8; 10];
        assert_eq!(r.read_at(data.len() as u64 - 3, &mut tail).unwrap(), 3);
        assert_eq!(r.read_at(data.len() as u64, &mut tail).unwrap(), 0);
        assert!(PfscReader::open(r.header().encode().to_vec(), None).is_err());
    }

    #[test]
    fn length_mismatch_is_an_error() {
        let mut enc = PfscEncoder::new(Cursor::new(Vec::new()), 10).unwrap();
        enc.write_all(&[1; 5]).unwrap();
        assert!(enc.finish().is_err());
        let mut enc = PfscEncoder::new(Cursor::new(Vec::new()), 2).unwrap();
        assert!(enc.write_all(&[1; 5]).is_err());
    }

    #[test]
    fn corrupted_block_is_rejected_not_panicked() {
        let data = vec![7u8; 0x10000];
        let (mut v, _) = encode(&data);
        let r = PfscReader::open(v.clone(), None).unwrap();
        assert_eq!(r.read_vec_at(0, 16).unwrap(), vec![7u8; 16]);
        v[0x10005] ^= 0xFF; // inside the zlib stream
        let r = PfscReader::open(v, None).unwrap();
        assert!(r.read_vec_at(0, 16).is_err());
    }
}
