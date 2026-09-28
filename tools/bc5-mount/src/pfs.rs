// SPDX-License-Identifier: GPL-2.0-only
//! PFS v2 image: superblock, D32 inodes, directory entries.
//! Layout: `docs/formats/ffpfsc.md` §2–§5. Only unsigned, unencrypted images
//! with 32-bit inodes are accepted, and every file must be one contiguous run
//! of blocks starting at `db[0]` (that is all `.ffpfsc` writers produce).

use crate::error::{bail_format, Error, Result};
use crate::io::{Le, ReadAt, Window};

const LAYER: &str = "pfs";

/// `magic` field value.
pub const MAGIC: u64 = 20_130_315;
/// `version` for the PS5 profile.
pub const VERSION_PS5: u64 = 2;
/// `mode` bit: signed image (rejected).
pub const MODE_SIGNED: u16 = 0x1;
/// `mode` bit: 64-bit inodes (rejected).
pub const MODE_64BIT_INODES: u16 = 0x2;
/// `mode` bit: encrypted (rejected).
pub const MODE_ENCRYPTED: u16 = 0x4;
/// `mode` bit: case-insensitive names.
pub const MODE_CASE_INSENSITIVE: u16 = 0x8;
/// Size of a D32 inode.
pub const INODE_SIZE: usize = 0xA8;
/// Bytes of the superblock that carry data (the rest of block 0 is zero).
pub const SUPERBLOCK_LEN: usize = 0x370;
/// Smallest block size accepted.
pub const MIN_BLOCK_SIZE: u32 = 0x1000;
/// Largest block size accepted (psdevwiki: 32 MiB).
pub const MAX_BLOCK_SIZE: u32 = 0x200_0000;

/// `mode` bit: directory.
pub const INODE_MODE_DIR: u16 = 0x4000;
/// `mode` bit: regular file.
pub const INODE_MODE_FILE: u16 = 0x8000;
/// Permission bits used by `.ffpfsc` writers (`r-xr-xr-x`).
pub const INODE_PERM_RX: u16 = 0x16D;
/// `flags` bit: file body is a PFSC stream.
pub const INODE_FLAG_COMPRESSED: u32 = 0x1;
/// `flags` bit: read-only.
pub const INODE_FLAG_READONLY: u32 = 0x10;
/// `flags` bit: internal (super-root, flat path table).
pub const INODE_FLAG_INTERNAL: u32 = 0x2_0000;
/// Number of direct block pointers in an inode.
pub const DIRECT_BLOCKS: usize = 12;
/// Number of indirect block pointers in an inode.
pub const INDIRECT_BLOCKS: usize = 5;

/// Dirent type: regular file.
pub const DIRENT_FILE: u32 = 2;
/// Dirent type: directory.
pub const DIRENT_DIR: u32 = 3;
/// Dirent type: `.`.
pub const DIRENT_DOT: u32 = 4;
/// Dirent type: `..`.
pub const DIRENT_DOTDOT: u32 = 5;

/// Largest directory we are willing to load into memory.
const MAX_DIR_BYTES: u64 = 64 << 20;

/// The PFS superblock (block 0).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Superblock {
    /// 2 for PS5 images.
    pub version: u64,
    /// Always [`MAGIC`].
    pub magic: u64,
    /// Mode bits; only [`MODE_CASE_INSENSITIVE`] may be set.
    pub mode: u16,
    /// Block size in bytes, a power of two.
    pub block_size: u32,
    /// Leading blocks before the inode table; always 1.
    pub nblock: u64,
    /// Number of inodes.
    pub ndinode: u64,
    /// Total block count; the file is exactly `ndblock * block_size` bytes.
    pub ndblock: u64,
    /// Number of inode-table blocks; always 1.
    pub ndinodeblock: u64,
}

impl Superblock {
    /// Parses and validates the first 0x48 bytes of block 0.
    pub fn parse(bytes: &[u8]) -> Result<Self> {
        let le = Le(bytes);
        let (Some(version), Some(magic), Some(mode), Some(block_size)) =
            (le.u64(0x00), le.u64(0x08), le.u16(0x1C), le.u32(0x20))
        else {
            bail_format!(
                LAYER,
                "superblock shorter than 0x48 bytes ({})",
                bytes.len()
            );
        };
        let (Some(nblock), Some(ndinode), Some(ndblock), Some(ndinodeblock)) =
            (le.i64(0x28), le.i64(0x30), le.i64(0x38), le.i64(0x40))
        else {
            bail_format!(
                LAYER,
                "superblock shorter than 0x48 bytes ({})",
                bytes.len()
            );
        };
        if magic != MAGIC {
            bail_format!(LAYER, "bad magic {magic:#x}, expected {MAGIC:#x}");
        }
        if version != VERSION_PS5 {
            bail_format!(
                LAYER,
                "unsupported PFS version {version} (need {VERSION_PS5})"
            );
        }
        if mode & !MODE_CASE_INSENSITIVE != 0 {
            bail_format!(
                LAYER,
                "mode {mode:#x}: only unsigned, unencrypted, 32-bit-inode images are supported"
            );
        }
        if !(MIN_BLOCK_SIZE..=MAX_BLOCK_SIZE).contains(&block_size) || !block_size.is_power_of_two()
        {
            bail_format!(LAYER, "invalid block size {block_size:#x}");
        }
        if nblock != 1 {
            bail_format!(LAYER, "nblock is {nblock}, expected 1");
        }
        if ndinodeblock != 1 {
            bail_format!(LAYER, "ndinodeblock is {ndinodeblock}, expected 1");
        }
        let inodes_per_block = i64::from(block_size / INODE_SIZE as u32);
        if ndinode < 1 || ndinode > inodes_per_block {
            bail_format!(LAYER, "ndinode {ndinode} outside 1..={inodes_per_block}");
        }
        if ndblock < 3 {
            bail_format!(
                LAYER,
                "ndblock {ndblock} too small for a superblock and inode table"
            );
        }
        Ok(Self {
            version,
            magic,
            mode,
            block_size,
            nblock: 1,
            ndinode: ndinode.unsigned_abs(),
            ndblock: ndblock.unsigned_abs(),
            ndinodeblock: 1,
        })
    }

    /// True when the image was written with case-insensitive names.
    pub fn is_case_insensitive(&self) -> bool {
        self.mode & MODE_CASE_INSENSITIVE != 0
    }

    /// Byte offset of the inode table.
    pub fn inode_table_offset(&self) -> u64 {
        self.nblock * u64::from(self.block_size)
    }

    /// Encodes a full block 0 (`block_size` bytes), including the inode-block
    /// signature record at 0x50 and the marker at 0x368, as the public writers
    /// do. `timestamp` fills the four time fields of that record.
    pub fn encode(&self, timestamp: i64) -> Vec<u8> {
        let mut b = vec![0u8; self.block_size as usize];
        put_u64(&mut b, 0x00, self.version);
        put_u64(&mut b, 0x08, self.magic);
        b[0x1A] = 1;
        put_u16(&mut b, 0x1C, self.mode);
        put_u32(&mut b, 0x20, self.block_size);
        put_u64(&mut b, 0x28, self.nblock);
        put_u64(&mut b, 0x30, self.ndinode);
        put_u64(&mut b, 0x38, self.ndblock);
        put_u64(&mut b, 0x40, self.ndinodeblock);
        // Inode-block signature record (S64 inode layout) describing the inode table.
        let rec = 0x50;
        put_u16(&mut b, rec + 0x02, 1);
        put_u32(&mut b, rec + 0x04, INODE_FLAG_READONLY);
        let inode_bytes = self.ndinodeblock * u64::from(self.block_size);
        put_u64(&mut b, rec + 0x08, inode_bytes);
        put_u64(&mut b, rec + 0x10, inode_bytes);
        for i in 0..4 {
            put_i64(&mut b, rec + 0x18 + i * 8, timestamp);
        }
        put_u32(&mut b, rec + 0x60, self.ndinodeblock as u32);
        put_u64(&mut b, rec + 0x88, 1);
        put_u32(&mut b, 0x368, 1);
        b
    }
}

/// A D32 inode.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Inode {
    /// POSIX bits plus [`INODE_MODE_DIR`] / [`INODE_MODE_FILE`].
    pub mode: u16,
    /// Link count.
    pub nlink: u16,
    /// [`INODE_FLAG_COMPRESSED`] and friends.
    pub flags: u32,
    /// Bytes occupied on disk (for a compressed file: the PFSC stream length).
    pub size: u64,
    /// For a compressed file: the decoded length. Otherwise equals `size`.
    pub size_compressed: u64,
    /// Timestamp in seconds (all four on-disk fields are written with this).
    pub time: i64,
    /// Number of data blocks.
    pub blocks: u32,
    /// Direct block pointers; `db[0]` is the first block.
    pub db: [i32; DIRECT_BLOCKS],
    /// Indirect block pointers; unused.
    pub ib: [i32; INDIRECT_BLOCKS],
}

impl Inode {
    /// Parses one 0xA8-byte inode. Range checks against the image happen in
    /// [`PfsImage::extent`].
    pub fn parse(bytes: &[u8]) -> Result<Self> {
        if bytes.len() < INODE_SIZE {
            bail_format!(LAYER, "inode record shorter than {INODE_SIZE:#x} bytes");
        }
        let le = Le(bytes);
        let size = le.i64(0x08).unwrap_or(-1);
        let size_compressed = le.i64(0x10).unwrap_or(-1);
        if size < 0 || size_compressed < 0 {
            bail_format!(LAYER, "inode has a negative size");
        }
        let mut db = [0i32; DIRECT_BLOCKS];
        for (i, slot) in db.iter_mut().enumerate() {
            *slot = le.i32(0x64 + i * 4).unwrap_or(-1);
        }
        let mut ib = [0i32; INDIRECT_BLOCKS];
        for (i, slot) in ib.iter_mut().enumerate() {
            *slot = le.i32(0x94 + i * 4).unwrap_or(-1);
        }
        Ok(Self {
            mode: le.u16(0x00).unwrap_or(0),
            nlink: le.u16(0x02).unwrap_or(0),
            flags: le.u32(0x04).unwrap_or(0),
            size: size.unsigned_abs(),
            size_compressed: size_compressed.unsigned_abs(),
            time: le.i64(0x18).unwrap_or(0),
            blocks: le.u32(0x60).unwrap_or(0),
            db,
            ib,
        })
    }

    /// Encodes the inode as 0xA8 bytes (all four time fields = `time`).
    pub fn encode(&self) -> [u8; INODE_SIZE] {
        let mut b = [0u8; INODE_SIZE];
        put_u16(&mut b, 0x00, self.mode);
        put_u16(&mut b, 0x02, self.nlink);
        put_u32(&mut b, 0x04, self.flags);
        put_u64(&mut b, 0x08, self.size);
        put_u64(&mut b, 0x10, self.size_compressed);
        for i in 0..4 {
            put_i64(&mut b, 0x18 + i * 8, self.time);
        }
        put_u32(&mut b, 0x60, self.blocks);
        for (i, v) in self.db.iter().enumerate() {
            put_i32(&mut b, 0x64 + i * 4, *v);
        }
        for (i, v) in self.ib.iter().enumerate() {
            put_i32(&mut b, 0x94 + i * 4, *v);
        }
        b
    }

    /// True for directories.
    pub fn is_dir(&self) -> bool {
        self.mode & INODE_MODE_DIR != 0
    }
    /// True for regular files.
    pub fn is_file(&self) -> bool {
        self.mode & INODE_MODE_FILE != 0
    }
    /// True when the body is a PFSC stream.
    pub fn is_compressed(&self) -> bool {
        self.flags & INODE_FLAG_COMPRESSED != 0
    }
}

/// One directory entry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Dirent {
    /// Inode number.
    pub ino: u32,
    /// [`DIRENT_FILE`], [`DIRENT_DIR`], [`DIRENT_DOT`] or [`DIRENT_DOTDOT`].
    pub kind: u32,
    /// ASCII name.
    pub name: String,
}

/// On-disk size of a dirent with an `name_len`-byte name.
pub fn dirent_size(name_len: usize) -> usize {
    (name_len + 17).div_ceil(8) * 8
}

/// Parses a directory's data until an all-zero entry or the end.
pub fn parse_dirents(data: &[u8]) -> Result<Vec<Dirent>> {
    let mut out = Vec::new();
    let mut off = 0usize;
    while off + 16 <= data.len() {
        let le = Le(&data[off..]);
        let (ino, kind, name_len, ent_size) = (
            le.u32(0).unwrap_or(0),
            le.u32(4).unwrap_or(0),
            le.i32(8).unwrap_or(-1),
            le.i32(12).unwrap_or(-1),
        );
        if ino == 0 && kind == 0 && name_len == 0 && ent_size == 0 {
            break;
        }
        let Ok(name_len) = usize::try_from(name_len) else {
            bail_format!(LAYER, "dirent at {off:#x} has a negative name length");
        };
        let Ok(ent_size) = usize::try_from(ent_size) else {
            bail_format!(LAYER, "dirent at {off:#x} has a negative entry size");
        };
        if ent_size < 16 || ent_size % 8 != 0 || name_len > ent_size - 16 {
            bail_format!(
                LAYER,
                "dirent at {off:#x} is malformed (size {ent_size}, name {name_len})"
            );
        }
        if ent_size > data.len() - off {
            bail_format!(LAYER, "dirent at {off:#x} runs past the directory data");
        }
        let raw = &data[off + 16..off + 16 + name_len];
        if !raw.is_ascii() || raw.contains(&0) {
            bail_format!(LAYER, "dirent at {off:#x} has a non-ASCII name");
        }
        out.push(Dirent {
            ino,
            kind,
            name: String::from_utf8_lossy(raw).into_owned(),
        });
        off += ent_size;
    }
    Ok(out)
}

/// Encodes one directory entry (8-byte aligned, zero padded).
pub fn encode_dirent(ino: u32, kind: u32, name: &str) -> Vec<u8> {
    debug_assert!(name.is_ascii());
    let size = dirent_size(name.len());
    let mut b = vec![0u8; size];
    put_u32(&mut b, 0, ino);
    put_u32(&mut b, 4, kind);
    put_u32(&mut b, 8, name.len() as u32);
    put_u32(&mut b, 12, size as u32);
    b[16..16 + name.len()].copy_from_slice(name.as_bytes());
    b
}

/// `flat_path_table` hash of a full path (with leading `/`): `hash = c + 31 * hash`
/// over ASCII-upper-cased characters when `case_insensitive`.
pub fn fpt_hash(path: &str, case_insensitive: bool) -> u32 {
    path.bytes().fold(0u32, |h, c| {
        let c = if case_insensitive {
            c.to_ascii_uppercase()
        } else {
            c
        };
        u32::from(c).wrapping_add(h.wrapping_mul(31))
    })
}

/// A parsed PFS image over any [`ReadAt`] source.
#[derive(Debug)]
pub struct PfsImage<R> {
    source: R,
    sb: Superblock,
}

impl<R: ReadAt> PfsImage<R> {
    /// Reads and validates the superblock; checks the file length.
    pub fn open(source: R) -> Result<Self> {
        let mut head = [0u8; 0x48];
        source
            .read_exact_at(0, &mut head)
            .map_err(|e| Error::format(LAYER, format!("cannot read the superblock: {e}")))?;
        let sb = Superblock::parse(&head)?;
        let expected = sb.ndblock.checked_mul(u64::from(sb.block_size));
        if expected != Some(source.len()) {
            bail_format!(
                LAYER,
                "file length {} does not equal ndblock {} x block size {:#x}",
                source.len(),
                sb.ndblock,
                sb.block_size
            );
        }
        Ok(Self { source, sb })
    }

    /// The superblock.
    pub fn superblock(&self) -> &Superblock {
        &self.sb
    }

    /// The underlying source.
    pub fn source(&self) -> &R {
        &self.source
    }

    /// Block size in bytes.
    pub fn block_size(&self) -> u64 {
        u64::from(self.sb.block_size)
    }

    /// Reads inode `n`.
    pub fn inode(&self, n: u64) -> Result<Inode> {
        if n >= self.sb.ndinode {
            bail_format!(LAYER, "inode {n} outside 0..{}", self.sb.ndinode);
        }
        let off = self.sb.inode_table_offset() + n * INODE_SIZE as u64;
        let mut buf = [0u8; INODE_SIZE];
        self.source
            .read_exact_at(off, &mut buf)
            .map_err(|e| Error::format(LAYER, format!("cannot read inode {n}: {e}")))?;
        Inode::parse(&buf)
    }

    /// Validates an inode's block range and returns `(byte offset, bytes on
    /// disk)` of its single contiguous extent.
    pub fn extent(&self, inode: &Inode) -> Result<(u64, u64)> {
        let bs = self.block_size();
        let first = inode.db[0];
        let Ok(first) = u64::try_from(first) else {
            bail_format!(LAYER, "inode first block {first} is negative");
        };
        let blocks = u64::from(inode.blocks);
        if blocks == 0 || first == 0 || first >= self.sb.ndblock || blocks > self.sb.ndblock - first
        {
            bail_format!(
                LAYER,
                "inode extent [{first}, {first}+{blocks}) outside 1..{}",
                self.sb.ndblock
            );
        }
        if inode.size > blocks * bs {
            bail_format!(LAYER, "inode size {} exceeds {blocks} blocks", inode.size);
        }
        // The writers we know emit one extent and mark the rest -1 (or 0 for
        // the super-root). Anything else is a layout we have not seen.
        let contiguous = inode.db.iter().enumerate().skip(1).all(|(i, &p)| {
            p == -1 || p == 0 || u64::try_from(p).is_ok_and(|p| p == first + i as u64)
        }) && inode.ib.iter().all(|&p| p == -1 || p == 0);
        if !contiguous {
            return Err(Error::Unsupported(
                "inode uses scattered or indirect blocks; only contiguous files are supported"
                    .into(),
            ));
        }
        Ok((first * bs, inode.size))
    }

    /// A window onto the bytes of a file inode.
    pub fn file_window(&self, inode: &Inode) -> Result<Window<&R>> {
        let (off, len) = self.extent(inode)?;
        Window::new(&self.source, off, len)
            .map_err(|e| Error::format(LAYER, format!("file window: {e}")))
    }

    /// Reads and parses a directory inode's entries.
    pub fn read_dir(&self, inode: &Inode) -> Result<Vec<Dirent>> {
        if !inode.is_dir() {
            bail_format!(LAYER, "inode mode {:#x} is not a directory", inode.mode);
        }
        let (off, len) = self.extent(inode)?;
        if len > MAX_DIR_BYTES {
            bail_format!(LAYER, "directory of {len} bytes is unreasonably large");
        }
        let data = self.source.read_vec_at(off, len as usize)?;
        parse_dirents(&data)
    }
}

fn put_u16(b: &mut [u8], off: usize, v: u16) {
    b[off..off + 2].copy_from_slice(&v.to_le_bytes());
}
fn put_u32(b: &mut [u8], off: usize, v: u32) {
    b[off..off + 4].copy_from_slice(&v.to_le_bytes());
}
fn put_i32(b: &mut [u8], off: usize, v: i32) {
    b[off..off + 4].copy_from_slice(&v.to_le_bytes());
}
fn put_u64(b: &mut [u8], off: usize, v: u64) {
    b[off..off + 8].copy_from_slice(&v.to_le_bytes());
}
fn put_i64(b: &mut [u8], off: usize, v: i64) {
    b[off..off + 8].copy_from_slice(&v.to_le_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn sample_sb() -> Superblock {
        Superblock {
            version: 2,
            magic: MAGIC,
            mode: MODE_CASE_INSENSITIVE,
            block_size: 0x10000,
            nblock: 1,
            ndinode: 4,
            ndblock: 7,
            ndinodeblock: 1,
        }
    }

    #[test]
    fn superblock_round_trip_and_markers() {
        let sb = sample_sb();
        let bytes = sb.encode(1_700_000_000);
        assert_eq!(bytes.len(), 0x10000);
        assert_eq!(bytes[0x1A], 1);
        assert_eq!(&bytes[0x368..0x36C], &[1, 0, 0, 0]);
        assert_eq!(Superblock::parse(&bytes).unwrap(), sb);
    }

    #[test]
    fn superblock_rejects_bad_fields() {
        let sb = sample_sb();
        let mut b = sb.encode(0);
        b[0x1C] = 0x9; // signed
        assert!(Superblock::parse(&b).is_err());
        let mut b = sb.encode(0);
        b[0x20] = 0x01; // block size not a power of two (0x10001)
        assert!(Superblock::parse(&b).is_err());
        let mut b = sb.encode(0);
        b[0x00] = 1; // PS4 profile
        assert!(Superblock::parse(&b).is_err());
        assert!(Superblock::parse(&b[..0x40]).is_err());
    }

    #[test]
    fn inode_round_trip() {
        let ino = Inode {
            mode: INODE_MODE_FILE | INODE_PERM_RX,
            nlink: 1,
            flags: INODE_FLAG_COMPRESSED | INODE_FLAG_READONLY,
            size: 123_456,
            size_compressed: 999_999,
            time: 42,
            blocks: 2,
            db: [6, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            ib: [-1; 5],
        };
        assert_eq!(Inode::parse(&ino.encode()).unwrap(), ino);
        assert!(Inode::parse(&[0u8; 10]).is_err());
    }

    #[test]
    fn dirents_round_trip_and_reject_garbage() {
        let mut data = encode_dirent(1, DIRENT_FILE, "flat_path_table");
        data.extend(encode_dirent(2, DIRENT_DIR, "uroot"));
        data.extend([0u8; 32]);
        let d = parse_dirents(&data).unwrap();
        assert_eq!(d.len(), 2);
        assert_eq!(d[0].name, "flat_path_table");
        assert_eq!(d[0].kind, DIRENT_FILE);
        assert_eq!(d[1].ino, 2);
        assert_eq!(dirent_size(15), 0x20);
        assert_eq!(dirent_size(5), 0x18);

        let mut bad = encode_dirent(3, DIRENT_FILE, "x");
        bad[12] = 0x0C; // entsize not a multiple of 8
        assert!(parse_dirents(&bad).is_err());
        let mut bad = encode_dirent(3, DIRENT_FILE, "x");
        bad[8] = 200; // name longer than the entry
        assert!(parse_dirents(&bad).is_err());
    }

    #[test]
    fn fpt_hash_matches_experiment_0001() {
        assert_eq!(fpt_hash("/PPSA21564.exfat", true), 0xDFDA_68EF);
        assert_ne!(fpt_hash("/PPSA21564.exfat", false), 0xDFDA_68EF);
    }

    #[test]
    fn image_checks_length_and_extents() {
        let sb = sample_sb();
        let mut img = sb.encode(0);
        img.resize(7 * 0x10000, 0);
        let payload = Inode {
            mode: INODE_MODE_FILE | INODE_PERM_RX,
            nlink: 1,
            flags: INODE_FLAG_READONLY,
            size: 100,
            size_compressed: 100,
            time: 0,
            blocks: 1,
            db: [6, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            ib: [-1; 5],
        };
        img[0x10000 + 3 * INODE_SIZE..0x10000 + 4 * INODE_SIZE].copy_from_slice(&payload.encode());
        let pfs = PfsImage::open(img.clone()).unwrap();
        assert_eq!(
            pfs.extent(&pfs.inode(3).unwrap()).unwrap(),
            (6 * 0x10000, 100)
        );
        assert!(pfs.inode(4).is_err());

        let mut scattered = payload.clone();
        scattered.db[1] = 9;
        assert!(matches!(pfs.extent(&scattered), Err(Error::Unsupported(_))));
        let mut out_of_range = payload;
        out_of_range.db[0] = 7;
        assert!(pfs.extent(&out_of_range).is_err());

        img.push(0);
        assert!(PfsImage::open(img).is_err());
    }

    proptest! {
        #[test]
        fn superblock_parse_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..0x80)) {
            let _ = Superblock::parse(&bytes);
        }

        #[test]
        fn inode_parse_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..0xB0)) {
            let _ = Inode::parse(&bytes);
        }

        #[test]
        fn dirents_parse_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..256)) {
            let _ = parse_dirents(&bytes);
        }

        #[test]
        fn inode_encode_parse_is_identity(
            mode in any::<u16>(), nlink in any::<u16>(), flags in any::<u32>(),
            size in 0..i64::MAX, size_compressed in 0..i64::MAX, time in any::<i64>(),
            blocks in any::<u32>(), db in any::<[i32; 12]>(), ib in any::<[i32; 5]>(),
        ) {
            let ino = Inode { mode, nlink, flags, size: size.unsigned_abs(), size_compressed: size_compressed.unsigned_abs(), time, blocks, db, ib };
            prop_assert_eq!(Inode::parse(&ino.encode()).unwrap(), ino);
        }
    }
}
