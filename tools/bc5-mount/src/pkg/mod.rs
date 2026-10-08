// SPDX-License-Identifier: GPL-2.0-only
//! A PS5 package (`.pkg`, magic `\x7fFIH`): the finalized image whose outer
//! PFS holds the game's inner image and the layout that maps it
//! (`docs/formats/ps5pkg.md`). Only plaintext outer images are read; an
//! encrypted one is reported, never decrypted.
//!
//! * [`naps`] — `naps_pkg_layout.dat`: logical blocks → stored bytes.
//! * [`kraken`] — the Kraken blocks, through the vendored `oozextract`.
//! * [`inner`] — the logical inner image and its file tree.
//! * [`PkgImage`] — the package: header, outer PFS, the two inner files.

pub mod inner;
pub mod kraken;
pub mod naps;

use std::path::Path;
use std::sync::Arc;

use crate::error::{bail_format, Error, Result};
use crate::io::{FileSource, Le, ReadAt, Window};
use crate::pfs::{parse_dirents, DIRENT_DIR, DIRENT_FILE, MAGIC, MODE_ENCRYPTED, VERSION_PS5};
use crate::tree::{EntryRef, FileTree};
use inner::{BlockStats, InnerImage, InnerTree};
use naps::Layout;

const LAYER: &str = "pkg";
/// The finalized-image header magic.
pub const FIH_MAGIC: &[u8; 4] = b"\x7fFIH";
const CNT_MAGIC: &[u8; 4] = b"\x7fCNT";
/// The seed a plaintext outer image carries where an encrypted one has its key seed.
const PLAINTEXT_SEED: &[u8; 16] = b"PPRPLAIN-NOAUTH!";
/// Outer PFS inode size: the signed layout with a 32-byte digest per block pointer.
const OUTER_INODE_SIZE: usize = 0x2c8;
const OUTER_DB_OFFSET: usize = 0x64;
const OUTER_DB_STRIDE: usize = 36;
const OUTER_DIRECT_BLOCKS: usize = 12;
/// The name of the inner image inside `uroot`.
pub const INNER_IMAGE_NAME: &str = "pfs_image.dat";
/// The name of the layout file inside `uroot`.
pub const LAYOUT_NAME: &str = "naps_pkg_layout.dat";

/// True when `head` (the first bytes of a file) starts a package.
pub fn is_package(head: &[u8]) -> bool {
    head.starts_with(FIH_MAGIC)
}

/// The fields of the 0x100-byte finalized-image header that locate the rest.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FihHeader {
    /// Byte offset of the outer PFS image.
    pub pfs_offset: u64,
    /// Length of the outer PFS image.
    pub pfs_size: u64,
    /// Byte offset of the outer superblock (the image is data-first: the
    /// superblock sits after the file data, not at block 0).
    pub superblock_offset: u64,
    /// Byte offset of the embedded `\x7fCNT` container (title metadata).
    pub cnt_offset: u64,
    /// Header byte 5: `0x80` marks a retail image, `0` a debug one.
    pub signed_byte: u8,
}

impl FihHeader {
    /// Parses the header.
    pub fn parse(head: &[u8]) -> Result<Self> {
        if !is_package(head) {
            bail_format!(LAYER, "not a package: no \\x7fFIH magic");
        }
        let le = Le(head);
        let (Some(pfs_offset), Some(pfs_size), Some(superblock_offset), Some(cnt_offset)) =
            (le.u64(0x10), le.u64(0x18), le.u64(0x20), le.u64(0x58))
        else {
            bail_format!(LAYER, "header shorter than 0x60 bytes");
        };
        Ok(Self {
            pfs_offset,
            pfs_size,
            superblock_offset,
            cnt_offset,
            signed_byte: head.get(5).copied().unwrap_or(0),
        })
    }
}

/// An outer PFS inode (the fields the reader uses).
#[derive(Debug, Clone, Copy)]
struct OuterInode {
    mode: u16,
    size: u64,
    blocks: u32,
    db: [i32; OUTER_DIRECT_BLOCKS],
}

fn parse_outer_inode(rec: &[u8]) -> OuterInode {
    let le = Le(rec);
    let mut db = [-1i32; OUTER_DIRECT_BLOCKS];
    for (j, slot) in db.iter_mut().enumerate() {
        *slot = le
            .i32(OUTER_DB_OFFSET + j * OUTER_DB_STRIDE + 32)
            .unwrap_or(-1);
    }
    OuterInode {
        mode: le.u16(0).unwrap_or(0),
        size: le.u64(8).unwrap_or(0),
        blocks: le.u32(0x60).unwrap_or(0),
        db,
    }
}

/// The outer PFS: superblock fields and the inodes.
#[derive(Debug)]
struct OuterPfs {
    mode: u16,
    block_size: u32,
    inodes: Vec<OuterInode>,
}

impl OuterPfs {
    fn open<R: ReadAt>(source: &R, hdr: &FihHeader) -> Result<Self> {
        let sb = source.read_vec_at(hdr.superblock_offset, 0x400)?;
        let le = Le(&sb);
        let (
            Some(version),
            Some(magic),
            Some(mode),
            Some(block_size),
            Some(ndinode),
            Some(ndinodeblock),
        ) = (
            le.u64(0),
            le.u64(8),
            le.u16(0x1c),
            le.u32(0x20),
            le.u64(0x30),
            le.u64(0x40),
        )
        else {
            bail_format!(LAYER, "outer superblock is truncated");
        };
        if version != VERSION_PS5 || magic != MAGIC {
            bail_format!(
                LAYER,
                "outer superblock: version {version}, magic {magic:#x}"
            );
        }
        if block_size == 0 || !block_size.is_power_of_two() || block_size > 0x100_0000 {
            bail_format!(LAYER, "outer superblock: block size {block_size:#x}");
        }
        if ndinode == 0 || ndinode > 4096 || ndinodeblock == 0 || ndinodeblock > 64 {
            bail_format!(
                LAYER,
                "outer superblock: {ndinode} inodes in {ndinodeblock} blocks"
            );
        }
        if mode & MODE_ENCRYPTED != 0 && &sb[0x370..0x380] != PLAINTEXT_SEED {
            return Err(Error::Unsupported(
                "the outer image is encrypted (a retail or passcode-protected package); only plaintext images are read".into(),
            ));
        }
        // The inode table follows the superblock and its indirect-pointer
        // blocks, one per non-zero entry of the signature block's pointers.
        let mut indirect = 0u64;
        for k in 0..5 {
            if le.i64(0x50 + 0x248 + k * 40 + 32).is_some_and(|p| p > 0) {
                indirect += 1;
            }
        }
        let table_at = hdr.superblock_offset + u64::from(block_size) * (1 + indirect);
        let table = source.read_vec_at(table_at, block_size as usize * ndinodeblock as usize)?;
        let per_block = block_size as usize / OUTER_INODE_SIZE;
        let inodes = (0..ndinode as usize)
            .map(|i| {
                let at = (i / per_block) * block_size as usize + (i % per_block) * OUTER_INODE_SIZE;
                table
                    .get(at..at + OUTER_INODE_SIZE)
                    .map(parse_outer_inode)
                    .ok_or_else(|| Error::format(LAYER, "outer inode table is truncated"))
            })
            .collect::<Result<Vec<_>>>()?;
        if inodes[0].mode & 0xf000 != 0x4000 {
            bail_format!(
                LAYER,
                "outer inode 0 is not a directory (mode {:#x})",
                inodes[0].mode
            );
        }
        Ok(Self {
            mode,
            block_size,
            inodes,
        })
    }

    /// Byte offset and length of an inode's data; the files we need are
    /// contiguous from their first block (the writers we know lay the image
    /// out that way; anything else is reported).
    fn extent(&self, hdr: &FihHeader, ino: usize) -> Result<(u64, u64)> {
        let Some(inode) = self.inodes.get(ino) else {
            bail_format!(LAYER, "outer inode {ino} out of range");
        };
        let Ok(first) = u64::try_from(inode.db[0]) else {
            bail_format!(
                LAYER,
                "outer inode {ino}: first block {} is negative",
                inode.db[0]
            );
        };
        let bs = u64::from(self.block_size);
        let direct = (inode.blocks as usize).min(OUTER_DIRECT_BLOCKS);
        let contiguous = inode.db[..direct]
            .iter()
            .enumerate()
            .all(|(j, &p)| u64::try_from(p).is_ok_and(|p| p == first + j as u64));
        if !contiguous {
            return Err(Error::Unsupported(format!(
                "outer inode {ino} is not stored contiguously; only contiguous files are supported"
            )));
        }
        if inode.size > u64::from(inode.blocks) * bs {
            bail_format!(
                LAYER,
                "outer inode {ino}: size {} exceeds {} blocks",
                inode.size,
                inode.blocks
            );
        }
        let off = first
            .checked_mul(bs)
            .and_then(|o| o.checked_add(hdr.pfs_offset));
        let Some(off) = off.filter(|&o| {
            o.checked_add(inode.size)
                .is_some_and(|e| e <= hdr.pfs_offset + hdr.pfs_size)
        }) else {
            bail_format!(LAYER, "outer inode {ino} lies outside the outer image");
        };
        Ok((off, inode.size))
    }

    fn read_dir<R: ReadAt>(
        &self,
        source: &R,
        hdr: &FihHeader,
        ino: usize,
    ) -> Result<Vec<crate::pfs::Dirent>> {
        let (off, len) = self.extent(hdr, ino)?;
        if len > 1 << 24 {
            bail_format!(LAYER, "outer directory inode {ino} is {len} bytes");
        }
        parse_dirents(&source.read_vec_at(off, len as usize)?)
    }
}

/// Everything `bc5-mount inspect` prints for a package.
#[derive(Debug, Clone)]
pub struct PkgInfo {
    /// The header.
    pub header: FihHeader,
    /// Content ID from the embedded container, when readable.
    pub content_id: Option<String>,
    /// Outer superblock mode.
    pub outer_mode: u16,
    /// Outer inode count.
    pub outer_inodes: usize,
    /// Stored length of the inner image.
    pub image_stored_len: u64,
    /// Logical length of the inner image.
    pub image_logical_len: u64,
    /// Length of the layout file.
    pub layout_len: u64,
    /// Blocks of the inner image.
    pub blocks: usize,
    /// Block kinds.
    pub stats: BlockStats,
    /// Logical offset of the inner superblock.
    pub inner_superblock_offset: u64,
    /// Inner superblock fields: block size, inode count, mode.
    pub inner_superblock: (u32, u64, u16),
    /// Files under `uroot`.
    pub file_count: usize,
    /// Directories under `uroot`.
    pub dir_count: usize,
    /// Sum of file sizes.
    pub total_file_bytes: u64,
}

/// An opened package.
#[derive(Debug)]
pub struct PkgImage<R: ReadAt> {
    source: Arc<R>,
    header: FihHeader,
    outer_mode: u16,
    outer_inodes: usize,
    layout_len: u64,
    tree: InnerTree<Window<Arc<R>>>,
}

impl PkgImage<FileSource> {
    /// Opens a package file.
    pub fn open_path(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let f = FileSource::open(path)
            .map_err(|e| Error::format(LAYER, format!("cannot open {}: {e}", path.display())))?;
        Self::open(f)
    }
}

impl<R: ReadAt> PkgImage<R> {
    /// Parses the header, the outer PFS, the layout and the inner metadata.
    pub fn open(source: R) -> Result<Self> {
        let source = Arc::new(source);
        let mut head = [0u8; 0x100];
        source
            .read_exact_at(0, &mut head)
            .map_err(|e| Error::format(LAYER, format!("cannot read the header: {e}")))?;
        let header = FihHeader::parse(&head)?;
        if header
            .pfs_offset
            .checked_add(header.pfs_size)
            .map_or(true, |end| end > source.len())
            || header.superblock_offset < header.pfs_offset
            || header.superblock_offset >= header.pfs_offset + header.pfs_size
        {
            bail_format!(
                LAYER,
                "header: outer image at {:#x}+{:#x} with its superblock at {:#x} does not fit the {}-byte file",
                header.pfs_offset,
                header.pfs_size,
                header.superblock_offset,
                source.len()
            );
        }
        let outer = OuterPfs::open(&*source, &header)?;
        let root = outer.read_dir(&*source, &header, 0)?;
        let Some(uroot) = root
            .iter()
            .find(|d| d.kind == DIRENT_DIR && d.name == "uroot")
        else {
            bail_format!(LAYER, "the outer root has no uroot directory");
        };
        let files = outer.read_dir(&*source, &header, uroot.ino as usize)?;
        let find = |name: &str| {
            files
                .iter()
                .find(|d| d.kind == DIRENT_FILE && d.name == name)
                .map(|d| d.ino as usize)
                .ok_or_else(|| Error::format(LAYER, format!("uroot has no {name}")))
        };
        let (image_off, image_len) = outer.extent(&header, find(INNER_IMAGE_NAME)?)?;
        let (layout_off, layout_len) = outer.extent(&header, find(LAYOUT_NAME)?)?;
        if layout_len > 1 << 30 {
            bail_format!(LAYER, "{LAYOUT_NAME} is {layout_len} bytes");
        }
        let layout = Layout::parse(&source.read_vec_at(layout_off, layout_len as usize)?)?;
        let image = Window::new(Arc::clone(&source), image_off, image_len)
            .map_err(|e| Error::format(LAYER, format!("inner image window: {e}")))?;
        let image = InnerImage::open(image, &layout)?;
        let tree = InnerTree::open(image, &layout)?;
        Ok(Self {
            source,
            header,
            outer_mode: outer.mode,
            outer_inodes: outer.inodes.len(),
            layout_len,
            tree,
        })
    }

    /// The header.
    pub fn header(&self) -> &FihHeader {
        &self.header
    }

    /// The file tree of the inner image.
    pub fn tree(&self) -> &InnerTree<Window<Arc<R>>> {
        &self.tree
    }

    /// The content ID from the embedded container, when it is there and readable.
    pub fn content_id(&self) -> Option<String> {
        let off = self.header.cnt_offset;
        if off == 0
            || off
                .checked_add(0x80)
                .map_or(true, |e| e > self.source.len())
        {
            return None;
        }
        let cnt = self.source.read_vec_at(off, 0x80).ok()?;
        if !cnt.starts_with(CNT_MAGIC) {
            return None;
        }
        let id = &cnt[0x40..0x40 + 36];
        if id
            .iter()
            .all(|&b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        {
            String::from_utf8(id.to_vec()).ok()
        } else {
            None
        }
    }

    /// Everything `inspect` prints.
    pub fn info(&self) -> PkgInfo {
        let image = self.tree.image();
        let mut file_count = 0;
        let mut dir_count = 0;
        let mut total_file_bytes = 0;
        for i in 1..self.tree.entry_count() {
            if let Some(e) = self.tree.entry(i) {
                if e.is_dir {
                    dir_count += 1;
                } else {
                    file_count += 1;
                    total_file_bytes += e.size;
                }
            }
        }
        PkgInfo {
            header: self.header,
            content_id: self.content_id(),
            outer_mode: self.outer_mode,
            outer_inodes: self.outer_inodes,
            image_stored_len: image.stored().len(),
            image_logical_len: image.mount(),
            layout_len: self.layout_len,
            blocks: image.block_count(),
            stats: image.stats(),
            inner_superblock_offset: self.tree.superblock_offset(),
            inner_superblock: self.tree.superblock_fields(),
            file_count,
            dir_count,
            total_file_bytes,
        }
    }
}

impl<R: ReadAt> FileTree for PkgImage<R> {
    fn entry_count(&self) -> usize {
        self.tree.entry_count()
    }

    fn entry(&self, idx: usize) -> Option<EntryRef<'_>> {
        self.tree.entry(idx)
    }

    fn children(&self, idx: usize) -> &[usize] {
        self.tree.children(idx)
    }

    fn find(&self, path: &str) -> Option<usize> {
        self.tree.find(path)
    }

    fn read_file_at(&self, idx: usize, offset: u64, buf: &mut [u8]) -> Result<usize> {
        self.tree.read_file_at(idx, offset, buf)
    }

    fn block_size(&self) -> u32 {
        self.tree.block_size()
    }

    fn block_count(&self) -> u64 {
        self.tree.block_count()
    }
}
