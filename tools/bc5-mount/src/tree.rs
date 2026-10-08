// SPDX-License-Identifier: GPL-2.0-only
//! A read-only file tree, the view the CLI and the FUSE mount work on: the
//! exFAT volume of a `.ffpfsc` container or the inner image of a PS5 package.

use std::io;

use crate::io::ReadAt;
use crate::Result;

/// One file or directory of a tree. Index 0 is the root directory.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EntryRef<'a> {
    /// Index of the parent entry (the root points to itself).
    pub parent: usize,
    /// Name as stored.
    pub name: &'a str,
    /// `/`-separated path without a leading slash; empty for the root.
    pub path: &'a str,
    /// True for directories.
    pub is_dir: bool,
    /// Data length in bytes.
    pub size: u64,
}

/// A read-only tree of files. Names are matched case-insensitively (both
/// formats we read are case-insensitive file systems).
pub trait FileTree: Send + Sync {
    /// Number of entries; indices are `0..entry_count()`.
    fn entry_count(&self) -> usize;

    /// Entry by index.
    fn entry(&self, idx: usize) -> Option<EntryRef<'_>>;

    /// Indices of a directory's children.
    fn children(&self, idx: usize) -> &[usize];

    /// Finds an entry by path (`/` or `\` separated, case-insensitive).
    fn find(&self, path: &str) -> Option<usize> {
        find_by_walk(self, path)
    }

    /// Reads file data at `offset` into `buf`; returns bytes read (0 at EOF).
    fn read_file_at(&self, idx: usize, offset: u64, buf: &mut [u8]) -> Result<usize>;

    /// The allocation unit the tree reports to `statfs`.
    fn block_size(&self) -> u32;

    /// Total blocks of `block_size` bytes the tree reports to `statfs`.
    fn block_count(&self) -> u64;
}

/// Case folding for names: upper-cased, as exFAT's up-case table does for ASCII.
pub fn fold_name(name: &str) -> String {
    name.chars().flat_map(char::to_uppercase).collect()
}

/// Finds a path by walking the tree from the root one component at a time.
pub fn find_by_walk<T: FileTree + ?Sized>(tree: &T, path: &str) -> Option<usize> {
    let norm = path.replace('\\', "/");
    let mut idx = 0usize;
    for part in norm.split('/').filter(|p| !p.is_empty()) {
        let want = fold_name(part);
        idx = *tree
            .children(idx)
            .iter()
            .find(|&&c| tree.entry(c).is_some_and(|e| fold_name(e.name) == want))?;
    }
    Some(idx)
}

/// A [`ReadAt`] view of one file of a tree.
#[derive(Debug, Clone, Copy)]
pub struct TreeFile<'a, T: ?Sized> {
    tree: &'a T,
    idx: usize,
    len: u64,
}

impl<'a, T: FileTree + ?Sized> TreeFile<'a, T> {
    /// The file at `idx`; fails for a directory.
    pub fn new(tree: &'a T, idx: usize) -> Result<Self> {
        let e = tree
            .entry(idx)
            .ok_or_else(|| crate::Error::NotFound(format!("entry {idx}")))?;
        if e.is_dir {
            return Err(crate::Error::format(
                "tree",
                format!("{} is a directory", e.path),
            ));
        }
        Ok(Self {
            tree,
            idx,
            len: e.size,
        })
    }
}

impl<T: FileTree + ?Sized> ReadAt for TreeFile<'_, T> {
    fn len(&self) -> u64 {
        self.len
    }

    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        self.tree
            .read_file_at(self.idx, offset, buf)
            .map_err(io::Error::other)
    }
}
