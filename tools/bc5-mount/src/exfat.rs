// SPDX-License-Identifier: GPL-2.0-only
//! Read-only exFAT: boot sector, FAT, directory tree, file data.
//! Layout: `docs/formats/ffpfsc.md` §7 and the Microsoft exFAT specification.
//! The whole directory tree is read at open time; file data is read on demand.

use std::collections::HashMap;
use std::io;
use std::sync::{Arc, Mutex};

use crate::error::{bail_format, Error, Result};
use crate::io::{Le, ReadAt};

const LAYER: &str = "exfat";

/// FAT values at or above this end a cluster chain.
pub const END_OF_CHAIN: u32 = 0xFFFF_FFF8;
/// First data cluster number.
pub const FIRST_CLUSTER: u32 = 2;
/// Directory entry: file.
pub const ENTRY_FILE: u8 = 0x85;
/// Directory entry: stream extension.
pub const ENTRY_STREAM: u8 = 0xC0;
/// Directory entry: file name.
pub const ENTRY_NAME: u8 = 0xC1;
/// Directory entry: allocation bitmap.
pub const ENTRY_BITMAP: u8 = 0x81;
/// Directory entry: up-case table.
pub const ENTRY_UPCASE: u8 = 0x82;
/// Directory entry: volume label.
pub const ENTRY_LABEL: u8 = 0x83;
/// `FileAttributes` bit: directory.
pub const ATTR_DIRECTORY: u16 = 0x10;
/// `FileAttributes` bit: archive.
pub const ATTR_ARCHIVE: u16 = 0x20;
/// Stream-extension flag: `NoFatChain` (contiguous).
pub const STREAM_NO_FAT_CHAIN: u8 = 0x02;
/// Stream-extension flag: allocation possible.
pub const STREAM_ALLOC_POSSIBLE: u8 = 0x01;

const MAX_ENTRIES: usize = 2_000_000;
const MAX_DEPTH: usize = 256;
const MAX_DIR_BYTES: u64 = 512 << 20;
const MAX_CLUSTERS: u32 = 1 << 28;

/// The fields of the main boot sector that a reader needs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BootSector {
    /// Volume length in sectors.
    pub volume_length: u64,
    /// FAT offset in sectors.
    pub fat_offset: u32,
    /// FAT length in sectors.
    pub fat_length: u32,
    /// Cluster heap offset in sectors.
    pub cluster_heap_offset: u32,
    /// Number of clusters in the heap.
    pub cluster_count: u32,
    /// First cluster of the root directory.
    pub root_cluster: u32,
    /// Volume serial number.
    pub serial: u32,
    /// File system revision (0x0100).
    pub revision: u16,
    /// log2(bytes per sector), 9..=12.
    pub sector_shift: u8,
    /// `log2(sectors per cluster)`.
    pub cluster_shift: u8,
    /// `NumberOfFats` (1, or 2 for `TexFAT`).
    pub num_fats: u8,
}

impl BootSector {
    /// Parses and validates the 512-byte main boot sector.
    pub fn parse(bytes: &[u8]) -> Result<Self> {
        if bytes.len() < 512 {
            bail_format!(LAYER, "boot sector shorter than 512 bytes");
        }
        let le = Le(bytes);
        if &bytes[3..11] != b"EXFAT   " || le.u16(0x1FE) != Some(0xAA55) {
            bail_format!(LAYER, "not an exFAT boot sector");
        }
        let bs = Self {
            volume_length: le.u64(0x48).unwrap_or(0),
            fat_offset: le.u32(0x50).unwrap_or(0),
            fat_length: le.u32(0x54).unwrap_or(0),
            cluster_heap_offset: le.u32(0x58).unwrap_or(0),
            cluster_count: le.u32(0x5C).unwrap_or(0),
            root_cluster: le.u32(0x60).unwrap_or(0),
            serial: le.u32(0x64).unwrap_or(0),
            revision: le.u16(0x68).unwrap_or(0),
            sector_shift: le.u8(0x6C).unwrap_or(0),
            cluster_shift: le.u8(0x6D).unwrap_or(0),
            num_fats: le.u8(0x6E).unwrap_or(0),
        };
        if !(9..=12).contains(&bs.sector_shift) || bs.sector_shift + bs.cluster_shift > 25 {
            bail_format!(
                LAYER,
                "invalid sector/cluster shift {}/{}",
                bs.sector_shift,
                bs.cluster_shift
            );
        }
        if bs.num_fats != 1 && bs.num_fats != 2 {
            bail_format!(LAYER, "NumberOfFats is {}", bs.num_fats);
        }
        if bs.cluster_count == 0 || bs.cluster_count > MAX_CLUSTERS {
            bail_format!(LAYER, "cluster count {} is invalid", bs.cluster_count);
        }
        if bs.root_cluster < FIRST_CLUSTER || bs.root_cluster >= bs.cluster_count + FIRST_CLUSTER {
            bail_format!(LAYER, "root cluster {} outside the heap", bs.root_cluster);
        }
        let fat_bytes = u64::from(bs.fat_length) << bs.sector_shift;
        if fat_bytes < (u64::from(bs.cluster_count) + 2) * 4 {
            bail_format!(
                LAYER,
                "FAT of {fat_bytes} bytes cannot hold {} clusters",
                bs.cluster_count
            );
        }
        if bs.fat_offset < 24 || bs.cluster_heap_offset < bs.fat_offset {
            bail_format!(
                LAYER,
                "FAT/heap offsets {}/{} are inconsistent",
                bs.fat_offset,
                bs.cluster_heap_offset
            );
        }
        Ok(bs)
    }

    /// Bytes per sector.
    pub fn sector_size(&self) -> u32 {
        1 << self.sector_shift
    }
    /// Bytes per cluster.
    pub fn cluster_size(&self) -> u32 {
        1 << (self.sector_shift + self.cluster_shift)
    }
    /// Byte offset of the FAT.
    pub fn fat_byte_offset(&self) -> u64 {
        u64::from(self.fat_offset) << self.sector_shift
    }
    /// Byte offset of the cluster heap.
    pub fn heap_byte_offset(&self) -> u64 {
        u64::from(self.cluster_heap_offset) << self.sector_shift
    }
    /// Byte offset of cluster `n` (n ≥ 2).
    pub fn cluster_byte_offset(&self, n: u32) -> u64 {
        self.heap_byte_offset() + u64::from(n - FIRST_CLUSTER) * u64::from(self.cluster_size())
    }

    /// Encodes the main boot sector (512 bytes) without the boot-region
    /// checksum, which covers 11 sectors and is computed by [`boot_checksum`].
    pub fn encode(&self) -> [u8; 512] {
        let mut b = [0u8; 512];
        b[0] = 0xEB;
        b[1] = 0x76;
        b[2] = 0x90;
        b[3..11].copy_from_slice(b"EXFAT   ");
        b[0x48..0x50].copy_from_slice(&self.volume_length.to_le_bytes());
        b[0x50..0x54].copy_from_slice(&self.fat_offset.to_le_bytes());
        b[0x54..0x58].copy_from_slice(&self.fat_length.to_le_bytes());
        b[0x58..0x5C].copy_from_slice(&self.cluster_heap_offset.to_le_bytes());
        b[0x5C..0x60].copy_from_slice(&self.cluster_count.to_le_bytes());
        b[0x60..0x64].copy_from_slice(&self.root_cluster.to_le_bytes());
        b[0x64..0x68].copy_from_slice(&self.serial.to_le_bytes());
        b[0x68..0x6A].copy_from_slice(&self.revision.to_le_bytes());
        b[0x6C] = self.sector_shift;
        b[0x6D] = self.cluster_shift;
        b[0x6E] = self.num_fats;
        b[0x6F] = 0x80; // DriveSelect
        b[0x70] = 0xFF; // PercentInUse: not available
        b[0x1FE] = 0x55;
        b[0x1FF] = 0xAA;
        b
    }
}

/// Boot-region checksum over the first 11 sectors (skipping `VolumeFlags` and
/// `PercentInUse`), MSX §3.1.2.
pub fn boot_checksum(region: &[u8]) -> u32 {
    let mut sum: u32 = 0;
    for (i, &byte) in region.iter().enumerate() {
        if i == 106 || i == 107 || i == 112 {
            continue;
        }
        sum = sum.rotate_right(1).wrapping_add(u32::from(byte));
    }
    sum
}

/// Entry-set checksum (MSX §6.3.3), skipping the checksum field itself.
pub fn entry_set_checksum(entries: &[u8]) -> u16 {
    let mut sum: u16 = 0;
    for (i, &byte) in entries.iter().enumerate() {
        if i == 2 || i == 3 {
            continue;
        }
        sum = sum.rotate_right(1).wrapping_add(u16::from(byte));
    }
    sum
}

/// Name hash over the up-cased UTF-16 name (MSX §7.6.3).
pub fn name_hash(upcased: &[u16]) -> u16 {
    let mut sum: u16 = 0;
    for unit in upcased {
        for byte in unit.to_le_bytes() {
            sum = sum.rotate_right(1).wrapping_add(u16::from(byte));
        }
    }
    sum
}

/// Table checksum for the up-case table (MSX §7.2.4).
pub fn table_checksum(data: &[u8]) -> u32 {
    data.iter().fold(0u32, |sum, &b| {
        sum.rotate_right(1).wrapping_add(u32::from(b))
    })
}

/// Case folding used for lookups: Unicode simple upper-casing per char. The
/// volume's own up-case table is not consulted (see `docs/formats/ffpfsc.md` §9).
pub fn fold_name(name: &str) -> String {
    name.chars().flat_map(char::to_uppercase).collect()
}

/// One file or directory. Index 0 is the root directory.
#[derive(Debug, Clone)]
pub struct Entry {
    /// Index of the parent entry (0 for the root's children; the root points to itself).
    pub parent: usize,
    /// Name as stored.
    pub name: String,
    /// `/`-separated path without a leading slash; empty for the root.
    pub path: String,
    /// True for directories.
    pub is_dir: bool,
    /// Data length in bytes (for directories: their entry data).
    pub size: u64,
    /// First cluster, 0 when nothing is allocated.
    pub first_cluster: u32,
    /// `NoFatChain`: clusters are consecutive.
    pub contiguous: bool,
    /// Raw `FileAttributes`.
    pub attributes: u16,
}

/// A parsed exFAT volume over any [`ReadAt`] source.
#[derive(Debug)]
pub struct ExfatVolume<R> {
    source: R,
    boot: BootSector,
    fat: Vec<u32>,
    entries: Vec<Entry>,
    children: Vec<Vec<usize>>,
    by_path: HashMap<String, usize>,
    chains: Mutex<HashMap<usize, Arc<Vec<u32>>>>,
}

impl<R: ReadAt> ExfatVolume<R> {
    /// Parses the boot sector and FAT, then walks the whole directory tree.
    pub fn open(source: R) -> Result<Self> {
        let boot = BootSector::parse(
            &source
                .read_vec_at(0, 512)
                .map_err(|e| Error::format(LAYER, format!("cannot read the boot sector: {e}")))?,
        )?;
        let heap_end = boot.heap_byte_offset()
            + u64::from(boot.cluster_count) * u64::from(boot.cluster_size());
        if heap_end > source.len() {
            bail_format!(
                LAYER,
                "cluster heap ends at {heap_end} but the image is {} bytes",
                source.len()
            );
        }
        let fat_entries = boot.cluster_count as usize + 2;
        let raw = source
            .read_vec_at(boot.fat_byte_offset(), fat_entries * 4)
            .map_err(|e| Error::format(LAYER, format!("cannot read the FAT: {e}")))?;
        let fat: Vec<u32> = raw
            .chunks_exact(4)
            .map(|c| u32::from_le_bytes(c.try_into().expect("chunks_exact yields 4 bytes")))
            .collect();

        let root = Entry {
            parent: 0,
            name: String::new(),
            path: String::new(),
            is_dir: true,
            size: 0,
            first_cluster: boot.root_cluster,
            contiguous: false,
            attributes: ATTR_DIRECTORY,
        };
        let mut vol = Self {
            source,
            boot,
            fat,
            entries: vec![root],
            children: vec![Vec::new()],
            by_path: HashMap::new(),
            chains: Mutex::new(HashMap::new()),
        };
        let root_clusters = vol.clusters(vol.boot.root_cluster, None, false)?;
        vol.entries[0].size = root_clusters.len() as u64 * u64::from(vol.boot.cluster_size());
        let mut visited = vec![vol.boot.root_cluster];
        vol.read_directory(0, &mut visited, 0)?;
        Ok(vol)
    }

    /// The boot sector.
    pub fn boot(&self) -> &BootSector {
        &self.boot
    }

    /// The underlying image.
    pub fn source(&self) -> &R {
        &self.source
    }

    /// All entries; index 0 is the root.
    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }

    /// Entry by index.
    pub fn entry(&self, idx: usize) -> Option<&Entry> {
        self.entries.get(idx)
    }

    /// Indices of a directory's children.
    pub fn children(&self, idx: usize) -> &[usize] {
        self.children.get(idx).map_or(&[], Vec::as_slice)
    }

    /// Finds an entry by path (`/` or `\` separated, case-insensitive).
    pub fn find(&self, path: &str) -> Option<usize> {
        let norm = path.replace('\\', "/");
        let norm = norm.trim_matches('/');
        if norm.is_empty() {
            return Some(0);
        }
        self.by_path.get(&fold_name(norm)).copied()
    }

    /// Reads file data at `offset` into `buf`; returns bytes read (0 at EOF).
    pub fn read_file_at(&self, idx: usize, offset: u64, buf: &mut [u8]) -> Result<usize> {
        let entry = self
            .entries
            .get(idx)
            .ok_or_else(|| Error::NotFound(format!("entry {idx}")))?;
        if offset >= entry.size {
            return Ok(0);
        }
        let avail = usize::try_from(entry.size - offset).unwrap_or(usize::MAX);
        let total = buf.len().min(avail);
        let cs = u64::from(self.boot.cluster_size());
        let chain = self.chain(idx)?;
        let mut done = 0usize;
        while done < total {
            let pos = offset + done as u64;
            let ci = (pos / cs) as usize;
            let within = pos % cs;
            let n = (total - done).min((cs - within) as usize);
            let Some(&cluster) = chain.get(ci) else {
                bail_format!(
                    LAYER,
                    "{}: cluster chain shorter than the data length",
                    entry.path
                );
            };
            let at = self.boot.cluster_byte_offset(cluster) + within;
            self.source.read_exact_at(at, &mut buf[done..done + n])?;
            done += n;
        }
        Ok(total)
    }

    /// A [`ReadAt`] view of one file.
    pub fn file(&self, idx: usize) -> Result<ExfatFile<'_, R>> {
        let entry = self
            .entries
            .get(idx)
            .ok_or_else(|| Error::NotFound(format!("entry {idx}")))?;
        if entry.is_dir {
            bail_format!(LAYER, "{} is a directory", entry.path);
        }
        Ok(ExfatFile {
            vol: self,
            idx,
            len: entry.size,
        })
    }

    fn chain(&self, idx: usize) -> Result<Arc<Vec<u32>>> {
        let mut chains = self
            .chains
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(c) = chains.get(&idx) {
            return Ok(Arc::clone(c));
        }
        let e = &self.entries[idx];
        let chain = Arc::new(self.clusters(e.first_cluster, Some(e.size), e.contiguous)?);
        chains.insert(idx, Arc::clone(&chain));
        Ok(chain)
    }

    /// Resolves the clusters of an allocation. With `len == Some`, exactly
    /// `ceil(len / cluster_size)` clusters are returned; with `None` the FAT
    /// chain is followed to its end.
    fn clusters(&self, first: u32, len: Option<u64>, contiguous: bool) -> Result<Vec<u32>> {
        let cs = u64::from(self.boot.cluster_size());
        let expected = len.map(|l| l.div_ceil(cs));
        if expected == Some(0) {
            return Ok(Vec::new());
        }
        let fat_len = self.fat.len() as u64;
        if u64::from(first) < u64::from(FIRST_CLUSTER) || u64::from(first) >= fat_len {
            bail_format!(LAYER, "first cluster {first} outside the heap");
        }
        if contiguous {
            let Some(n) = expected else {
                bail_format!(LAYER, "contiguous allocation without a length");
            };
            if u64::from(first) + n > fat_len {
                bail_format!(LAYER, "contiguous run {first}+{n} leaves the heap");
            }
            return Ok((first..first + n as u32).collect());
        }
        let mut out = Vec::with_capacity(expected.map_or(4, |n| n.min(1 << 20) as usize));
        let mut cluster = first;
        let mut steps: u64 = 0;
        while cluster < END_OF_CHAIN {
            if u64::from(cluster) < u64::from(FIRST_CLUSTER) || u64::from(cluster) >= fat_len {
                bail_format!(LAYER, "FAT chain from {first} points outside the heap");
            }
            out.push(cluster);
            steps += 1;
            if steps > fat_len {
                bail_format!(LAYER, "FAT chain from {first} is cyclic");
            }
            if expected == Some(steps) {
                break;
            }
            cluster = self.fat[cluster as usize];
        }
        if let Some(n) = expected {
            if steps != n {
                bail_format!(
                    LAYER,
                    "FAT chain from {first} has {steps} clusters, data needs {n}"
                );
            }
        }
        Ok(out)
    }

    fn read_directory(&mut self, dir: usize, visited: &mut Vec<u32>, depth: usize) -> Result<()> {
        if depth > MAX_DEPTH {
            bail_format!(LAYER, "directory nesting deeper than {MAX_DEPTH}");
        }
        let (first, size, contiguous, path) = {
            let e = &self.entries[dir];
            (e.first_cluster, e.size, e.contiguous, e.path.clone())
        };
        if size > MAX_DIR_BYTES {
            bail_format!(
                LAYER,
                "directory {path:?} of {size} bytes is unreasonably large"
            );
        }
        let chain = self.clusters(first, Some(size), contiguous)?;
        let cs = self.boot.cluster_size() as usize;
        let mut data = vec![0u8; size as usize];
        for (i, &cluster) in chain.iter().enumerate() {
            let start = i * cs;
            let end = (start + cs).min(data.len());
            self.source.read_exact_at(
                self.boot.cluster_byte_offset(cluster),
                &mut data[start..end],
            )?;
        }

        let mut off = 0usize;
        while off + 32 <= data.len() {
            let kind = data[off];
            if kind == 0 {
                break;
            }
            if kind != ENTRY_FILE {
                off += 32;
                continue;
            }
            let secondary = usize::from(data[off + 1]);
            let set_len = (secondary + 1) * 32;
            if secondary < 2 || off + set_len > data.len() {
                bail_format!(LAYER, "truncated file entry set in {path:?}");
            }
            let set = &data[off..off + set_len];
            let entry = parse_entry_set(set, &path)?;
            let idx = self.entries.len();
            if idx > MAX_ENTRIES {
                bail_format!(LAYER, "more than {MAX_ENTRIES} entries");
            }
            let key = fold_name(&entry.path);
            if self.by_path.insert(key, idx).is_some() {
                bail_format!(LAYER, "duplicate path {:?}", entry.path);
            }
            let is_dir = entry.is_dir;
            let child_first = entry.first_cluster;
            self.entries.push(Entry {
                parent: dir,
                ..entry
            });
            self.children.push(Vec::new());
            self.children[dir].push(idx);
            if is_dir && child_first >= FIRST_CLUSTER {
                if visited.contains(&child_first) {
                    bail_format!(LAYER, "directory cycle at cluster {child_first}");
                }
                visited.push(child_first);
                self.read_directory(idx, visited, depth + 1)?;
            }
            off += set_len;
        }
        Ok(())
    }
}

fn parse_entry_set(set: &[u8], parent_path: &str) -> Result<Entry> {
    let primary = &set[..32];
    let stream = &set[32..64];
    if stream[0] != ENTRY_STREAM {
        bail_format!(
            LAYER,
            "file entry in {parent_path:?} has no stream extension"
        );
    }
    let secondary = usize::from(primary[1]);
    let name_len = usize::from(stream[3]);
    let name_entries = name_len.div_ceil(15);
    if name_len == 0 || name_entries > secondary - 1 {
        bail_format!(
            LAYER,
            "file entry in {parent_path:?} has an incomplete name"
        );
    }
    let mut units = Vec::with_capacity(name_len);
    for i in 0..name_entries {
        let e = &set[(2 + i) * 32..(3 + i) * 32];
        if e[0] != ENTRY_NAME {
            bail_format!(
                LAYER,
                "file entry in {parent_path:?}: missing file-name entry"
            );
        }
        for unit in e[2..32].chunks_exact(2) {
            if units.len() < name_len {
                units.push(u16::from_le_bytes([unit[0], unit[1]]));
            }
        }
    }
    let name = String::from_utf16(&units)
        .map_err(|_| Error::format(LAYER, format!("invalid UTF-16 name in {parent_path:?}")))?;
    if name.is_empty() || name == "." || name == ".." || name.contains(['/', '\\', '\0']) {
        bail_format!(LAYER, "unsafe file name {name:?} in {parent_path:?}");
    }
    let le = Le(stream);
    let attributes = Le(primary).u16(4).unwrap_or(0);
    let flags = stream[1];
    let first_cluster = le.u32(0x14).unwrap_or(0);
    let size = le.u64(0x18).unwrap_or(0);
    if size > i64::MAX as u64 {
        bail_format!(LAYER, "{name:?}: data length too large");
    }
    let path = if parent_path.is_empty() {
        name.clone()
    } else {
        format!("{parent_path}/{name}")
    };
    Ok(Entry {
        parent: 0,
        name,
        path,
        is_dir: attributes & ATTR_DIRECTORY != 0,
        size,
        first_cluster,
        contiguous: flags & STREAM_NO_FAT_CHAIN != 0,
        attributes,
    })
}

/// A file inside an [`ExfatVolume`] as a [`ReadAt`].
#[derive(Debug)]
pub struct ExfatFile<'a, R> {
    vol: &'a ExfatVolume<R>,
    idx: usize,
    len: u64,
}

impl<R: ReadAt> ReadAt for ExfatFile<'_, R> {
    fn len(&self) -> u64 {
        self.len
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        self.vol
            .read_file_at(self.idx, offset, buf)
            .map_err(|e| io::Error::other(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn checksums_match_known_vectors() {
        // Rotating checksum of an all-zero buffer is zero; of a single 1 is 1.
        assert_eq!(boot_checksum(&[0u8; 11 * 512]), 0);
        // rotr16(0) + 1 = 1, then rotr16(1) + 0 = 0x8000; bytes 2 and 3 are skipped.
        assert_eq!(entry_set_checksum(&[1u8, 0, 0, 0]), 0x8000);
        assert_eq!(name_hash(&[]), 0);
        assert_eq!(table_checksum(&[]), 0);
        assert_eq!(fold_name("Sce_Sys/param.json"), "SCE_SYS/PARAM.JSON");
    }

    #[test]
    fn boot_sector_round_trip() {
        let bs = BootSector {
            volume_length: 4096,
            fat_offset: 128,
            fat_length: 64,
            cluster_heap_offset: 256,
            cluster_count: 60,
            root_cluster: 4,
            serial: 0x4D6B_5046,
            revision: 0x0100,
            sector_shift: 9,
            cluster_shift: 6,
            num_fats: 1,
        };
        assert_eq!(BootSector::parse(&bs.encode()).unwrap(), bs);
        let mut b = bs.encode();
        b[0x60] = 1; // root cluster below 2
        assert!(BootSector::parse(&b).is_err());
        let mut b = bs.encode();
        b[3] = b'F';
        assert!(BootSector::parse(&b).is_err());
    }

    proptest! {
        #[test]
        fn boot_sector_parse_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..600)) {
            let _ = BootSector::parse(&bytes);
        }

        #[test]
        fn open_never_panics_on_garbage(bytes in proptest::collection::vec(any::<u8>(), 0..2048)) {
            let _ = ExfatVolume::open(bytes);
        }
    }
}
