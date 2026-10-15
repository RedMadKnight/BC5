// SPDX-License-Identifier: GPL-2.0-only
//! Decoded Kraken blocks kept on disk between mounts (experiment 0112). A title
//! reads the same ~2 GB at every start, and decoding it costs seconds the game
//! spends waiting. With a cache directory, a block decoded once is written to a
//! sparse data file at `index × block size`, and an entry in a map file records
//! its length and CRC-32. A later mount reads it back instead of decoding; an
//! entry whose CRC does not match is dropped and the block decoded again.
//!
//! Files: `<key>.data` (sparse, one slot per block) and `<key>.map` (8 bytes per
//! block, little-endian: CRC-32 in the high half, length in the low half, 0 =
//! absent). The key is derived from the stored image, so another package gets
//! its own files. Writing stops at a byte limit.

use std::fs::{File, OpenOptions};
use std::io;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

use sha2::{Digest, Sha256};

use crate::io::ReadAt;

/// Default limit for the data written, in MiB (`BC5_MOUNT_DISK_CACHE_MIB`).
pub const DEFAULT_LIMIT_MIB: u64 = 8192;

/// The cache files of one package image.
#[derive(Debug)]
pub struct DiskCache {
    data: File,
    map: File,
    entries: Vec<AtomicU64>,
    block_bytes: u64,
    limit: u64,
    written: AtomicU64,
}

fn crc32(bytes: &[u8]) -> u32 {
    let mut c = flate2::Crc::new();
    c.update(bytes);
    c.sum()
}

#[cfg(unix)]
fn read_exact_at(f: &File, buf: &mut [u8], offset: u64) -> io::Result<()> {
    std::os::unix::fs::FileExt::read_exact_at(f, buf, offset)
}

#[cfg(unix)]
fn write_all_at(f: &File, buf: &[u8], offset: u64) -> io::Result<()> {
    std::os::unix::fs::FileExt::write_all_at(f, buf, offset)
}

#[cfg(windows)]
fn read_exact_at(f: &File, mut buf: &mut [u8], mut offset: u64) -> io::Result<()> {
    while !buf.is_empty() {
        let n = std::os::windows::fs::FileExt::seek_read(f, buf, offset)?;
        if n == 0 {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }
        buf = &mut buf[n..];
        offset += n as u64;
    }
    Ok(())
}

#[cfg(windows)]
fn write_all_at(f: &File, mut buf: &[u8], mut offset: u64) -> io::Result<()> {
    while !buf.is_empty() {
        let n = std::os::windows::fs::FileExt::seek_write(f, buf, offset)?;
        if n == 0 {
            return Err(io::ErrorKind::WriteZero.into());
        }
        buf = &buf[n..];
        offset += n as u64;
    }
    Ok(())
}

/// A key naming the cache files of `image`: its length and the SHA-256 of its
/// first 64 KiB.
pub fn image_key<R: ReadAt>(image: &R) -> io::Result<String> {
    let head = image.read_vec_at(0, usize::try_from(image.len().min(64 << 10)).unwrap_or(0))?;
    let mut h = Sha256::new();
    h.update(image.len().to_le_bytes());
    h.update(&head);
    let digest = h.finalize();
    Ok(digest[..8].iter().fold(String::new(), |mut s, b| {
        use std::fmt::Write as _;
        let _ = write!(s, "{b:02x}");
        s
    }))
}

impl DiskCache {
    /// Opens (or creates) the cache files for `blocks` blocks of at most
    /// `block_bytes` each. Files from a different layout are started afresh.
    pub fn open(
        dir: &Path,
        key: &str,
        blocks: usize,
        block_bytes: u64,
        limit: u64,
    ) -> io::Result<Self> {
        std::fs::create_dir_all(dir)?;
        let open = |name: String| {
            OpenOptions::new()
                .read(true)
                .write(true)
                .create(true)
                .truncate(false)
                .open(dir.join(name))
        };
        let data = open(format!("{key}.data"))?;
        let map = open(format!("{key}.map"))?;
        let map_len = blocks as u64 * 8;
        let data_len = blocks as u64 * block_bytes;
        let mut raw = vec![0u8; usize::try_from(map_len).unwrap_or(0)];
        let fresh = map.metadata()?.len() != map_len || read_exact_at(&map, &mut raw, 0).is_err();
        if fresh {
            raw.fill(0);
            map.set_len(0)?;
            map.set_len(map_len)?;
            data.set_len(0)?;
        }
        if data.metadata()?.len() != data_len {
            data.set_len(data_len)?; // sparse: only written slots take space
        }
        let mut written = 0u64;
        let entries = raw
            .chunks_exact(8)
            .map(|c| {
                let e = u64::from_le_bytes(c.try_into().unwrap_or([0; 8]));
                if (e & 0xffff_ffff) > block_bytes {
                    return AtomicU64::new(0); // not a length this layout can have
                }
                written += e & 0xffff_ffff;
                AtomicU64::new(e)
            })
            .collect();
        Ok(Self {
            data,
            map,
            entries,
            block_bytes,
            limit,
            written: AtomicU64::new(written),
        })
    }

    /// The decoded block `index`, if it was stored and its CRC matches.
    pub fn get(&self, index: usize) -> Option<Vec<u8>> {
        let slot = self.entries.get(index)?;
        let e = slot.load(Ordering::Acquire);
        let len = usize::try_from(e & 0xffff_ffff).ok()?;
        if len == 0 {
            return None;
        }
        let mut buf = vec![0u8; len];
        if read_exact_at(&self.data, &mut buf, index as u64 * self.block_bytes).is_err()
            || crc32(&buf) != (e >> 32) as u32
        {
            slot.store(0, Ordering::Release);
            return None;
        }
        Some(buf)
    }

    /// Stores decoded block `index` unless it is stored already or the limit is
    /// reached. Data first, then the map entry, so an entry never names
    /// unwritten data. Errors are ignored: the cache is only an optimisation.
    pub fn put(&self, index: usize, block: &[u8]) {
        let Some(slot) = self.entries.get(index) else {
            return;
        };
        let len = block.len() as u64;
        if slot.load(Ordering::Acquire) != 0
            || len == 0
            || len > self.block_bytes
            || self.written.load(Ordering::Relaxed) + len > self.limit
        {
            return;
        }
        if write_all_at(&self.data, block, index as u64 * self.block_bytes).is_err() {
            return;
        }
        let e = (u64::from(crc32(block)) << 32) | len;
        if write_all_at(&self.map, &e.to_le_bytes(), index as u64 * 8).is_ok() {
            slot.store(e, Ordering::Release);
            self.written.fetch_add(len, Ordering::Relaxed);
        }
    }

    /// Bytes of decoded data stored.
    pub fn stored_bytes(&self) -> u64 {
        self.written.load(Ordering::Relaxed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("bc5-diskcache-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn stores_and_reads_back_across_opens() {
        let dir = temp_dir("roundtrip");
        let c = DiskCache::open(&dir, "k", 4, 16, 1 << 20).unwrap();
        assert!(c.get(1).is_none());
        c.put(1, &[7u8; 16]);
        c.put(3, &[9u8; 5]); // a short last block
        assert_eq!(c.get(1).unwrap(), vec![7u8; 16]);
        drop(c);
        let c = DiskCache::open(&dir, "k", 4, 16, 1 << 20).unwrap();
        assert_eq!(c.get(1).unwrap(), vec![7u8; 16]);
        assert_eq!(c.get(3).unwrap(), vec![9u8; 5]);
        assert!(c.get(0).is_none());
        assert_eq!(c.stored_bytes(), 21);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_corrupted_block_is_dropped() {
        let dir = temp_dir("corrupt");
        let c = DiskCache::open(&dir, "k", 2, 16, 1 << 20).unwrap();
        c.put(0, &[1u8; 16]);
        drop(c);
        let f = OpenOptions::new()
            .write(true)
            .open(dir.join("k.data"))
            .unwrap();
        write_all_at(&f, &[2u8], 3).unwrap();
        drop(f);
        let c = DiskCache::open(&dir, "k", 2, 16, 1 << 20).unwrap();
        assert!(c.get(0).is_none(), "the CRC must reject the changed byte");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn writing_stops_at_the_limit_and_a_new_layout_starts_afresh() {
        let dir = temp_dir("limit");
        let c = DiskCache::open(&dir, "k", 4, 16, 20).unwrap();
        c.put(0, &[1u8; 16]);
        c.put(1, &[1u8; 16]); // would pass 20 bytes
        assert!(c.get(0).is_some() && c.get(1).is_none());
        drop(c);
        let c = DiskCache::open(&dir, "k", 8, 16, 20).unwrap(); // other block count
        assert!(c.get(0).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
