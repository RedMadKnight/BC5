// SPDX-License-Identifier: GPL-2.0-only
//! The inner image (`pfs_image.dat`): the game's PFS, stored as 256 KiB
//! logical blocks, each raw or Kraken-compressed, as the naps layout says.
//! [`InnerImage`] reads the logical bytes through a block cache; [`InnerTree`]
//! parses the metadata at the top of the logical image (superblock, inode
//! table, directories) into a [`FileTree`].

use std::collections::HashMap;
use std::io;
use std::sync::{Arc, Mutex};

use crate::error::{bail_format, Error, Result};
use crate::io::{Le, ReadAt};
use crate::pfs::{parse_dirents, DIRENT_DIR, DIRENT_FILE, MAGIC};
use crate::pkg::kraken;
use crate::pkg::naps::{Block, Layout};
use crate::tree::{fold_name, EntryRef, FileTree};

const LAYER: &str = "inner";
/// Decoded blocks kept: 64 × 256 KiB = 16 MiB.
const CACHE_BLOCKS: usize = 64;
/// Inner inode size (the compact layout: data address at 0x60).
const INODE_SIZE: usize = 0xa8;
/// The compact inode layout's mode bits (0x10), with case-insensitive names (0x08).
const MODE_COMPACT: u16 = 0x10;
const MAX_DIR_SIZE: u64 = 8 << 20;
/// The metadata after the last file: a few MiB in real images.
const MAX_META_TAIL: u64 = 1 << 30;

/// Counts of block kinds, for `inspect`.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct BlockStats {
    /// Blocks stored as they are.
    pub stored: usize,
    /// Kraken-compressed blocks.
    pub kraken: usize,
    /// Blocks with no stored bytes (zeros).
    pub sparse: usize,
}

#[derive(Debug)]
struct Cache {
    blocks: HashMap<usize, Arc<Vec<u8>>>,
    order: Vec<usize>,
}

/// The logical bytes of the inner image over the stored image.
#[derive(Debug)]
pub struct InnerImage<R> {
    image: R,
    blocks: Vec<Block>,
    mount: u64,
    stats: BlockStats,
    cache: Mutex<Cache>,
}

impl<R: ReadAt> InnerImage<R> {
    /// Resolves the layout against the stored image.
    pub fn open(image: R, layout: &Layout) -> Result<Self> {
        let mount = layout.mount_size();
        let blocks = layout.blocks()?;
        let mut stats = BlockStats::default();
        for b in &blocks {
            if b.comp == 0 {
                stats.sparse += 1;
            } else if b.kraken {
                stats.kraken += 1;
            } else {
                stats.stored += 1;
            }
            if b.on_disk
                .checked_add(u64::from(b.comp))
                .map_or(true, |end| end > image.len())
            {
                bail_format!(
                    LAYER,
                    "block at logical {:#x} is stored at {:#x}+{:#x}, past the {:#x}-byte image",
                    b.logical,
                    b.on_disk,
                    b.comp,
                    image.len()
                );
            }
        }
        Ok(Self {
            image,
            blocks,
            mount,
            stats,
            cache: Mutex::new(Cache {
                blocks: HashMap::new(),
                order: Vec::new(),
            }),
        })
    }

    /// Logical size.
    pub fn mount(&self) -> u64 {
        self.mount
    }

    /// Number of blocks.
    pub fn block_count(&self) -> usize {
        self.blocks.len()
    }

    /// Block kind counts.
    pub fn stats(&self) -> BlockStats {
        self.stats
    }

    /// The stored image.
    pub fn stored(&self) -> &R {
        &self.image
    }

    fn find_block(&self, logical: u64) -> Option<usize> {
        let i = self
            .blocks
            .partition_point(|b| b.logical + u64::from(b.uncomp) <= logical);
        self.blocks
            .get(i)
            .filter(|b| b.logical <= logical)
            .map(|_| i)
    }

    fn block(&self, index: usize) -> Result<Arc<Vec<u8>>> {
        if let Ok(c) = self.cache.lock() {
            if let Some(b) = c.blocks.get(&index) {
                return Ok(Arc::clone(b));
            }
        }
        let b = self.blocks[index];
        let mut out = vec![0u8; b.uncomp as usize];
        if b.comp != 0 {
            let payload = self.image.read_vec_at(b.on_disk, b.comp as usize)?;
            if b.kraken {
                kraken::decode_block(&payload, b.even_comp as usize, b.flags, &mut out).map_err(
                    |e| {
                        Error::format(
                            LAYER,
                            format!(
                                "block at logical {:#x} (stored at {:#x}, {} -> {} bytes, flags {:#x}, split {}): {e}",
                                b.logical, b.on_disk, b.comp, b.uncomp, b.flags, b.even_comp
                            ),
                        )
                    },
                )?;
            } else {
                out.copy_from_slice(&payload);
            }
        }
        let out = Arc::new(out);
        if let Ok(mut c) = self.cache.lock() {
            if c.blocks.len() >= CACHE_BLOCKS {
                let evict = c.order.remove(0);
                c.blocks.remove(&evict);
            }
            c.blocks.insert(index, Arc::clone(&out));
            c.order.push(index);
        }
        Ok(out)
    }
}

impl<R: ReadAt> ReadAt for InnerImage<R> {
    fn len(&self) -> u64 {
        self.mount
    }

    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        if offset >= self.mount {
            return Ok(0);
        }
        let total = buf
            .len()
            .min(usize::try_from(self.mount - offset).unwrap_or(usize::MAX));
        let mut done = 0usize;
        while done < total {
            let pos = offset + done as u64;
            let Some(index) = self.find_block(pos) else {
                return Err(io::Error::other(format!(
                    "no block covers logical {pos:#x}"
                )));
            };
            let b = self.blocks[index];
            let within = (pos - b.logical) as usize;
            let n = (b.uncomp as usize - within).min(total - done);
            let bytes = self.block(index).map_err(io::Error::other)?;
            buf[done..done + n].copy_from_slice(&bytes[within..within + n]);
            done += n;
        }
        Ok(total)
    }
}

#[derive(Debug, Clone)]
struct Entry {
    parent: usize,
    name: String,
    path: String,
    is_dir: bool,
    size: u64,
    logical: u64,
}

/// The file tree of an inner image.
#[derive(Debug)]
pub struct InnerTree<R> {
    image: InnerImage<R>,
    entries: Vec<Entry>,
    children: Vec<Vec<usize>>,
    by_path: HashMap<String, usize>,
    superblock_offset: u64,
    block_size: u32,
    inode_count: u64,
    mode: u16,
}

impl<R: ReadAt> InnerTree<R> {
    /// Finds the inner superblock in the metadata at the top of the logical
    /// image and walks its directories from the super-root, keeping what lies
    /// under `uroot` (the super-root's other children are internal tables).
    pub fn open(image: InnerImage<R>, layout: &Layout) -> Result<Self> {
        let mount = image.mount();
        let meta_base = layout.metadata_base();
        if mount - meta_base > MAX_META_TAIL {
            bail_format!(
                LAYER,
                "{:#x} bytes after the last file boundary at {meta_base:#x}; the metadata should be far smaller",
                mount - meta_base
            );
        }
        let tail = image.read_vec_at(meta_base, (mount - meta_base) as usize)?;
        let Some(sb_off) = find_superblock(&tail, mount) else {
            bail_format!(
                LAYER,
                "no inner superblock covering {mount:#x} bytes after logical {meta_base:#x}"
            );
        };
        let sb = Le(&tail[sb_off..]);
        let (Some(block_size), Some(inode_count), Some(mode)) =
            (sb.u32(0x20), sb.u64(0x30), sb.u16(0x1c))
        else {
            bail_format!(LAYER, "inner superblock is truncated");
        };
        if block_size == 0
            || !block_size.is_power_of_two()
            || inode_count == 0
            || inode_count > 1_000_000
        {
            bail_format!(
                LAYER,
                "inner superblock: block size {block_size:#x}, {inode_count} inodes"
            );
        }
        if mode & (MODE_COMPACT | 0x3) != MODE_COMPACT {
            return Err(Error::Unsupported(format!(
                "inner PFS mode {mode:#x} (only the compact {MODE_COMPACT:#x} layout is known)"
            )));
        }
        let per_block = block_size as usize / INODE_SIZE;
        let table = sb_off + block_size as usize;
        let mut inodes = Vec::with_capacity(inode_count as usize);
        for i in 0..inode_count as usize {
            let at = table + (i / per_block) * block_size as usize + (i % per_block) * INODE_SIZE;
            let Some(rec) = tail.get(at..at + INODE_SIZE) else {
                bail_format!(LAYER, "inner inode table is truncated");
            };
            let le = Le(rec);
            inodes.push((
                le.u16(0).unwrap_or(0),
                le.u64(8).unwrap_or(0),
                le.u64(0x60).unwrap_or(0),
            ));
        }
        let mut entries = vec![Entry {
            parent: 0,
            name: String::new(),
            path: String::new(),
            is_dir: true,
            size: 0,
            logical: 0,
        }];
        let mut children: Vec<Vec<usize>> = vec![Vec::new()];
        let mut seen = vec![false; inodes.len()];
        // (inode, entry index of the directory it fills, under uroot)
        let mut stack = vec![(0u32, 0usize, false)];
        while let Some((ino, dir_idx, under)) = stack.pop() {
            let Some(&(mode, size, logical)) = inodes.get(ino as usize) else {
                bail_format!(LAYER, "inner inode {ino} out of range");
            };
            if std::mem::replace(&mut seen[ino as usize], true) {
                continue;
            }
            if mode & 0xf000 != 0x4000 || size == 0 || size > MAX_DIR_SIZE {
                bail_format!(LAYER, "inner inode {ino} is not a readable directory");
            }
            let bytes = match logical
                .checked_sub(meta_base)
                .and_then(|s| tail.get(s as usize..(s + size) as usize))
            {
                Some(slice) => slice.to_vec(),
                None => image.read_vec_at(logical, size as usize)?,
            };
            for d in parse_dirents(&bytes)? {
                if d.name == "." || d.name == ".." {
                    continue;
                }
                if d.name.contains(['/', '\\', ':']) {
                    bail_format!(
                        LAYER,
                        "inner file name {:?} contains a path separator",
                        d.name
                    );
                }
                let Some(&(cmode, csize, clogical)) = inodes.get(d.ino as usize) else {
                    bail_format!(LAYER, "{}: inode {} out of range", d.name, d.ino);
                };
                let is_uroot = !under && dir_idx == 0 && d.name == "uroot";
                match d.kind {
                    DIRENT_DIR if is_uroot => stack.push((d.ino, 0, true)),
                    DIRENT_DIR if under => {
                        let path = join(&entries[dir_idx].path, &d.name);
                        entries.push(Entry {
                            parent: dir_idx,
                            name: d.name,
                            path,
                            is_dir: true,
                            size: 0,
                            logical: clogical,
                        });
                        children.push(Vec::new());
                        let idx = entries.len() - 1;
                        children[dir_idx].push(idx);
                        stack.push((d.ino, idx, true));
                    }
                    DIRENT_FILE if under => {
                        if cmode & 0xf000 == 0x4000
                            || clogical.checked_add(csize).map_or(true, |end| end > mount)
                        {
                            bail_format!(
                                LAYER,
                                "{}: {clogical:#x}+{csize:#x} is not a file inside the image",
                                d.name
                            );
                        }
                        let path = join(&entries[dir_idx].path, &d.name);
                        entries.push(Entry {
                            parent: dir_idx,
                            name: d.name,
                            path,
                            is_dir: false,
                            size: csize,
                            logical: clogical,
                        });
                        children.push(Vec::new());
                        let idx = entries.len() - 1;
                        children[dir_idx].push(idx);
                    }
                    _ => {}
                }
            }
        }
        let by_path = entries
            .iter()
            .enumerate()
            .map(|(i, e)| (fold_name(&e.path), i))
            .collect();
        Ok(Self {
            image,
            entries,
            children,
            by_path,
            superblock_offset: meta_base + sb_off as u64,
            block_size,
            inode_count,
            mode,
        })
    }

    /// The logical image.
    pub fn image(&self) -> &InnerImage<R> {
        &self.image
    }

    /// Logical offset of the inner superblock.
    pub fn superblock_offset(&self) -> u64 {
        self.superblock_offset
    }

    /// Inner superblock fields: block size, inode count, mode.
    pub fn superblock_fields(&self) -> (u32, u64, u16) {
        (self.block_size, self.inode_count, self.mode)
    }

    /// Logical offset of a file's data.
    pub fn logical_offset(&self, idx: usize) -> Option<u64> {
        self.entries.get(idx).map(|e| e.logical)
    }
}

fn join(dir: &str, name: &str) -> String {
    if dir.is_empty() {
        name.to_owned()
    } else {
        format!("{dir}/{name}")
    }
}

/// The superblock must cover exactly the mount size, so the outer image's
/// superblock can never be taken for the inner one.
fn find_superblock(buf: &[u8], mount: u64) -> Option<usize> {
    (0..=buf.len().saturating_sub(0x40))
        .step_by(0x10000)
        .find(|&off| {
            let le = Le(&buf[off..]);
            le.u64(0) == Some(2)
                && le.u64(8) == Some(MAGIC)
                && le.u64(0x30).is_some_and(|n| n > 0)
                && le
                    .u64(0x38)
                    .zip(le.u32(0x20))
                    .is_some_and(|(nd, bs)| nd.wrapping_mul(u64::from(bs)) == mount)
        })
}

impl<R: ReadAt> FileTree for InnerTree<R> {
    fn entry_count(&self) -> usize {
        self.entries.len()
    }

    fn entry(&self, idx: usize) -> Option<EntryRef<'_>> {
        self.entries.get(idx).map(|e| EntryRef {
            parent: e.parent,
            name: &e.name,
            path: &e.path,
            is_dir: e.is_dir,
            size: e.size,
        })
    }

    fn children(&self, idx: usize) -> &[usize] {
        self.children.get(idx).map_or(&[], Vec::as_slice)
    }

    fn find(&self, path: &str) -> Option<usize> {
        let norm = path.replace('\\', "/");
        self.by_path
            .get(&fold_name(norm.trim_matches('/')))
            .copied()
    }

    fn read_file_at(&self, idx: usize, offset: u64, buf: &mut [u8]) -> Result<usize> {
        let e = self
            .entries
            .get(idx)
            .ok_or_else(|| Error::NotFound(format!("entry {idx}")))?;
        if e.is_dir {
            bail_format!(LAYER, "{} is a directory", e.path);
        }
        if offset >= e.size {
            return Ok(0);
        }
        let n = buf
            .len()
            .min(usize::try_from(e.size - offset).unwrap_or(usize::MAX));
        self.image
            .read_exact_at(e.logical + offset, &mut buf[..n])?;
        Ok(n)
    }

    fn block_size(&self) -> u32 {
        self.block_size
    }

    fn block_count(&self) -> u64 {
        self.image.mount() / u64::from(self.block_size)
    }
}
