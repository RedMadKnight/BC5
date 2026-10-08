// SPDX-License-Identifier: GPL-2.0-only
//! An opened `.ffpfsc`: PFS image → payload inode → PFSC stream → exFAT volume.

use std::path::Path;
use std::sync::Arc;

use crate::error::{bail_format, Error, Result};
use crate::exfat::ExfatVolume;
use crate::io::{FileSource, ReadAt, Window};
use crate::pfs::{
    fpt_hash, Dirent, Inode, PfsImage, Superblock, DIRENT_DIR, DIRENT_DOT, DIRENT_DOTDOT,
    DIRENT_FILE,
};
use crate::pfsc::PfscReader;

const LAYER: &str = "container";

/// The decoded payload stream type.
pub type Payload<R> = PfscReader<Window<Arc<R>>>;

/// Title metadata from `sce_sys/param.json`, when present.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TitleInfo {
    /// `titleId`.
    pub title_id: Option<String>,
    /// First `titleName` found.
    pub title_name: Option<String>,
}

/// Everything `bc5-mount inspect` prints.
#[derive(Debug, Clone)]
pub struct ContainerInfo {
    /// PFS superblock.
    pub superblock: Superblock,
    /// Name of the inner file in `uroot`.
    pub inner_name: String,
    /// Byte offset of the PFSC stream in the container.
    pub payload_offset: u64,
    /// PFSC stream length on disk.
    pub stored_len: u64,
    /// Decoded exFAT image length.
    pub logical_len: u64,
    /// PFSC block count.
    pub pfsc_blocks: u64,
    /// Blocks stored compressed.
    pub compressed_blocks: u64,
    /// exFAT cluster size.
    pub cluster_size: u32,
    /// Files in the tree.
    pub file_count: usize,
    /// Directories in the tree (excluding the root).
    pub dir_count: usize,
    /// Sum of file sizes.
    pub total_file_bytes: u64,
    /// Title metadata, if `sce_sys/param.json` exists.
    pub title: Option<TitleInfo>,
}

/// An opened container.
#[derive(Debug)]
pub struct Container<R: ReadAt> {
    pfs: PfsImage<Arc<R>>,
    payload: Inode,
    inner_name: String,
    payload_offset: u64,
    exfat: ExfatVolume<Payload<R>>,
}

impl Container<FileSource> {
    /// Opens a container file.
    pub fn open_path(path: impl AsRef<Path>) -> Result<Self> {
        Self::open(FileSource::open(path)?)
    }
}

impl<R: ReadAt> Container<R> {
    /// Validates the PFS structure, locates the payload and opens the exFAT
    /// volume inside it.
    pub fn open(source: R) -> Result<Self> {
        let source = Arc::new(source);
        let pfs = PfsImage::open(Arc::clone(&source))?;
        if pfs.superblock().ndinode < 4 {
            bail_format!(
                LAYER,
                "expected at least 4 inodes, found {}",
                pfs.superblock().ndinode
            );
        }
        let super_root = pfs.inode(0)?;
        let fpt = pfs.inode(1)?;
        let uroot = pfs.inode(2)?;
        let payload = pfs.inode(3)?;

        let sr = pfs.read_dir(&super_root)?;
        require(&sr, 1, DIRENT_FILE, "flat_path_table")?;
        require(&sr, 2, DIRENT_DIR, "uroot")?;
        let ur = pfs.read_dir(&uroot)?;
        require(&ur, 2, DIRENT_DOT, ".")?;
        require(&ur, 2, DIRENT_DOTDOT, "..")?;
        let mut files = ur.iter().filter(|d| d.kind == DIRENT_FILE);
        let (Some(entry), None) = (files.next(), files.next()) else {
            bail_format!(LAYER, "uroot must contain exactly one file");
        };
        if entry.ino != 3 {
            bail_format!(
                LAYER,
                "uroot file {:?} is inode {}, expected 3",
                entry.name,
                entry.ino
            );
        }
        if !payload.is_file() || !payload.is_compressed() {
            bail_format!(
                LAYER,
                "payload inode is not a PFSC-compressed file (mode {:#x}, flags {:#x})",
                payload.mode,
                payload.flags
            );
        }
        let (fpt_off, fpt_len) = pfs.extent(&fpt)?;
        if fpt_len != 8 {
            bail_format!(LAYER, "flat_path_table is {fpt_len} bytes, expected 8");
        }
        let fpt_bytes = source.read_vec_at(fpt_off, 8)?;
        let hash = u32::from_le_bytes([fpt_bytes[0], fpt_bytes[1], fpt_bytes[2], fpt_bytes[3]]);
        let ino = u32::from_le_bytes([fpt_bytes[4], fpt_bytes[5], fpt_bytes[6], fpt_bytes[7]]);
        let want = fpt_hash(
            &format!("/{}", entry.name),
            pfs.superblock().is_case_insensitive(),
        );
        if hash != want || ino != 3 {
            bail_format!(
                LAYER,
                "flat_path_table ({hash:#x} -> {ino}) does not match {:?} ({want:#x} -> 3)",
                entry.name
            );
        }

        let (payload_offset, stored_len) = pfs.extent(&payload)?;
        let window = Window::new(Arc::clone(&source), payload_offset, stored_len)
            .map_err(|e| Error::format(LAYER, format!("payload window: {e}")))?;
        let pfsc = PfscReader::open(window, Some(payload.size_compressed))?;
        let exfat = ExfatVolume::open(pfsc)?;
        Ok(Self {
            pfs,
            inner_name: entry.name.clone(),
            payload,
            payload_offset,
            exfat,
        })
    }

    /// The exFAT volume.
    pub fn exfat(&self) -> &ExfatVolume<Payload<R>> {
        &self.exfat
    }

    /// The PFS image.
    pub fn pfs(&self) -> &PfsImage<Arc<R>> {
        &self.pfs
    }

    /// Name of the inner file.
    pub fn inner_name(&self) -> &str {
        &self.inner_name
    }

    /// Reads `sce_sys/param.json` and extracts the title fields, if present.
    pub fn title_info(&self) -> Result<Option<TitleInfo>> {
        let Some(idx) = self.exfat.find("sce_sys/param.json") else {
            return Ok(None);
        };
        let entry = self
            .exfat
            .entry(idx)
            .ok_or_else(|| Error::NotFound("param.json".into()))?;
        if entry.is_dir || entry.size > 4 << 20 {
            return Ok(None);
        }
        let file = self.exfat.file(idx)?;
        let bytes = file.read_vec_at(0, entry.size as usize)?;
        let text = String::from_utf8_lossy(&bytes);
        Ok(Some(TitleInfo {
            title_id: json_string_after(&text, "\"titleId\""),
            title_name: json_string_after(&text, "\"titleName\""),
        }))
    }

    /// Collects the numbers `inspect` prints.
    pub fn info(&self) -> Result<ContainerInfo> {
        let entries = self.exfat.entries();
        let vol = self.exfat.pfsc_source();
        Ok(ContainerInfo {
            superblock: self.pfs.superblock().clone(),
            inner_name: self.inner_name.clone(),
            payload_offset: self.payload_offset,
            stored_len: self.payload.size,
            logical_len: self.payload.size_compressed,
            pfsc_blocks: vol.block_count(),
            compressed_blocks: vol.compressed_block_count(),
            cluster_size: self.exfat.boot().cluster_size(),
            file_count: entries.iter().filter(|e| !e.is_dir).count(),
            dir_count: entries.iter().skip(1).filter(|e| e.is_dir).count(),
            total_file_bytes: entries.iter().filter(|e| !e.is_dir).map(|e| e.size).sum(),
            title: self.title_info()?,
        })
    }
}

impl<R: ReadAt> ExfatVolume<Payload<R>> {
    /// The PFSC reader underneath this volume.
    pub fn pfsc_source(&self) -> &Payload<R> {
        self.source()
    }
}

fn require(entries: &[Dirent], ino: u32, kind: u32, name: &str) -> Result<()> {
    if entries
        .iter()
        .any(|d| d.ino == ino && d.kind == kind && d.name == name)
    {
        Ok(())
    } else {
        Err(Error::format(
            LAYER,
            format!("directory entry {name:?} (inode {ino}, type {kind}) is missing"),
        ))
    }
}

/// Finds `key` in `text` and returns the next JSON string value after it.
/// Good enough for `param.json`; not a JSON parser.
fn json_string_after(text: &str, key: &str) -> Option<String> {
    let at = text.find(key)? + key.len();
    let rest = text[at..].trim_start().strip_prefix(':')?.trim_start();
    let rest = rest.strip_prefix('"')?;
    let mut out = String::new();
    let mut chars = rest.chars();
    while let Some(c) = chars.next() {
        match c {
            '"' => return Some(out),
            '\\' => match chars.next()? {
                'n' => out.push('\n'),
                't' => out.push('\t'),
                'u' => {
                    let hex: String = chars.by_ref().take(4).collect();
                    let code = u32::from_str_radix(&hex, 16).ok()?;
                    out.push(char::from_u32(code).unwrap_or('\u{FFFD}'));
                }
                other => out.push(other),
            },
            _ => out.push(c),
        }
    }
    None
}

impl<R: ReadAt> crate::tree::FileTree for Container<R> {
    fn entry_count(&self) -> usize {
        self.exfat().entry_count()
    }

    fn entry(&self, idx: usize) -> Option<crate::tree::EntryRef<'_>> {
        crate::tree::FileTree::entry(self.exfat(), idx)
    }

    fn children(&self, idx: usize) -> &[usize] {
        crate::tree::FileTree::children(self.exfat(), idx)
    }

    fn find(&self, path: &str) -> Option<usize> {
        crate::tree::FileTree::find(self.exfat(), path)
    }

    fn read_file_at(&self, idx: usize, offset: u64, buf: &mut [u8]) -> Result<usize> {
        crate::tree::FileTree::read_file_at(self.exfat(), idx, offset, buf)
    }

    fn block_size(&self) -> u32 {
        crate::tree::FileTree::block_size(self.exfat())
    }

    fn block_count(&self) -> u64 {
        crate::tree::FileTree::block_count(self.exfat())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_extraction_handles_escapes_and_absence() {
        let t = r#"{"titleId": "PPSA00001", "x": {"titleName":"A \"quoted\" é name"}}"#;
        assert_eq!(
            json_string_after(t, "\"titleId\"").as_deref(),
            Some("PPSA00001")
        );
        assert_eq!(
            json_string_after(t, "\"titleName\"").as_deref(),
            Some("A \"quoted\" é name")
        );
        assert_eq!(json_string_after(t, "\"missing\""), None);
        assert_eq!(json_string_after("\"titleId\": 5", "\"titleId\""), None);
    }
}
