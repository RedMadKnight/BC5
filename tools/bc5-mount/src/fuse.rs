// SPDX-License-Identifier: GPL-2.0-only
//! FUSE glue (Linux only): exposes a [`FileTree`] (the exFAT tree of a
//! `.ffpfsc` container or the inner image of a PS5 package) as a read-only
//! file system. Inode numbers are entry indices plus one, so the root is 1 as
//! FUSE expects. Written against `fuser` 0.15.

use std::collections::HashMap;
use std::ffi::OsStr;
use std::path::Path;
use std::time::{Duration, SystemTime};

use fuser::{
    FileAttr, FileType, Filesystem, KernelConfig, MountOption, ReplyAttr, ReplyData,
    ReplyDirectory, ReplyEntry, ReplyOpen, ReplyStatfs, Request,
};

use crate::tree::{fold_name, FileTree};

const ENOENT: i32 = 2;
const EIO: i32 = 5;
const ENOTDIR: i32 = 20;
const EISDIR: i32 = 21;
const EINVAL: i32 = 22;

/// Attribute/entry cache lifetime; the source never changes.
const TTL: Duration = Duration::from_secs(3600);

struct Bc5Fs<T> {
    tree: T,
    uid: u32,
    gid: u32,
    mounted_at: SystemTime,
    /// Per directory, folded child name -> entry index, built on the directory's first
    /// lookup. A linear scan folding every name cost ~8 ms per miss in a 12,000-entry
    /// directory, and a game stats missing files by the thousand while it loads
    /// (experiment 0029).
    names: HashMap<usize, HashMap<String, usize>>,
}

impl<T: FileTree> Bc5Fs<T> {
    fn idx(ino: u64) -> Option<usize> {
        usize::try_from(ino.checked_sub(1)?).ok()
    }

    fn attr(&self, idx: usize) -> Option<FileAttr> {
        let e = self.tree.entry(idx)?;
        let blksize = self.tree.block_size();
        Some(FileAttr {
            ino: idx as u64 + 1,
            size: e.size,
            blocks: e.size.div_ceil(512),
            atime: self.mounted_at,
            mtime: self.mounted_at,
            ctime: self.mounted_at,
            crtime: self.mounted_at,
            kind: if e.is_dir {
                FileType::Directory
            } else {
                FileType::RegularFile
            },
            perm: if e.is_dir { 0o555 } else { 0o444 },
            nlink: 1,
            uid: self.uid,
            gid: self.gid,
            rdev: 0,
            blksize,
            flags: 0,
        })
    }

    fn names_of(&mut self, parent: usize) -> &HashMap<String, usize> {
        let tree = &self.tree;
        self.names.entry(parent).or_insert_with(|| {
            tree.children(parent)
                .iter()
                .filter_map(|&c| tree.entry(c).map(|e| (fold_name(e.name), c)))
                .collect()
        })
    }

    fn negative(&self) -> FileAttr {
        FileAttr {
            ino: 0,
            size: 0,
            blocks: 0,
            atime: self.mounted_at,
            mtime: self.mounted_at,
            ctime: self.mounted_at,
            crtime: self.mounted_at,
            kind: FileType::RegularFile,
            perm: 0,
            nlink: 0,
            uid: self.uid,
            gid: self.gid,
            rdev: 0,
            blksize: 0,
            flags: 0,
        }
    }
}

impl<T: FileTree + 'static> Filesystem for Bc5Fs<T> {
    fn init(&mut self, req: &Request<'_>, _config: &mut KernelConfig) -> Result<(), i32> {
        self.uid = req.uid();
        self.gid = req.gid();
        Ok(())
    }

    fn lookup(&mut self, _req: &Request<'_>, parent: u64, name: &OsStr, reply: ReplyEntry) {
        let Some(parent) = Self::idx(parent) else {
            return reply.error(ENOENT);
        };
        let Some(name) = name.to_str() else {
            return reply.error(ENOENT);
        };
        let want = fold_name(name);
        let found = self.names_of(parent).get(&want).copied();
        match found.and_then(|i| self.attr(i)) {
            Some(attr) => reply.entry(&TTL, &attr, 0),
            // A negative entry with a lifetime (nodeid 0): the source never changes, so
            // the kernel may answer the next stat of the same missing name itself.
            None => reply.entry(&TTL, &self.negative(), 0),
        }
    }

    fn getattr(&mut self, _req: &Request<'_>, ino: u64, _fh: Option<u64>, reply: ReplyAttr) {
        match Self::idx(ino).and_then(|i| self.attr(i)) {
            Some(attr) => reply.attr(&TTL, &attr),
            None => reply.error(ENOENT),
        }
    }

    fn open(&mut self, _req: &Request<'_>, ino: u64, _flags: i32, reply: ReplyOpen) {
        match Self::idx(ino).and_then(|i| self.tree.entry(i)) {
            Some(e) if e.is_dir => reply.error(EISDIR),
            Some(_) => reply.opened(0, fuser::consts::FOPEN_KEEP_CACHE),
            None => reply.error(ENOENT),
        }
    }

    fn read(
        &mut self,
        _req: &Request<'_>,
        ino: u64,
        _fh: u64,
        offset: i64,
        size: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyData,
    ) {
        let (Some(idx), Ok(offset)) = (Self::idx(ino), u64::try_from(offset)) else {
            return reply.error(EINVAL);
        };
        let Some(e) = self.tree.entry(idx) else {
            return reply.error(ENOENT);
        };
        if e.is_dir {
            return reply.error(EISDIR);
        }
        let path = e.path.to_owned();
        let want = usize::try_from(e.size.saturating_sub(offset).min(u64::from(size))).unwrap_or(0);
        let mut buf = vec![0u8; want];
        match self.tree.read_file_at(idx, offset, &mut buf) {
            Ok(n) => reply.data(&buf[..n]),
            Err(err) => {
                eprintln!("bc5-mount: read {path}: {err}");
                reply.error(EIO);
            }
        }
    }

    fn opendir(&mut self, _req: &Request<'_>, ino: u64, _flags: i32, reply: ReplyOpen) {
        match Self::idx(ino).and_then(|i| self.tree.entry(i)) {
            Some(e) if e.is_dir => reply.opened(0, 0),
            Some(_) => reply.error(ENOTDIR),
            None => reply.error(ENOENT),
        }
    }

    fn readdir(
        &mut self,
        _req: &Request<'_>,
        ino: u64,
        _fh: u64,
        offset: i64,
        mut reply: ReplyDirectory,
    ) {
        let Some(idx) = Self::idx(ino) else {
            return reply.error(ENOENT);
        };
        let Some(dir) = self.tree.entry(idx) else {
            return reply.error(ENOENT);
        };
        if !dir.is_dir {
            return reply.error(ENOTDIR);
        }
        let parent_ino = if idx == 0 { 1 } else { dir.parent as u64 + 1 };
        let mut items: Vec<(u64, FileType, String)> = vec![
            (ino, FileType::Directory, ".".into()),
            (parent_ino, FileType::Directory, "..".into()),
        ];
        for &c in self.tree.children(idx) {
            let Some(e) = self.tree.entry(c) else {
                continue;
            };
            let kind = if e.is_dir {
                FileType::Directory
            } else {
                FileType::RegularFile
            };
            items.push((c as u64 + 1, kind, e.name.to_owned()));
        }
        let start = usize::try_from(offset).unwrap_or(usize::MAX);
        for (i, (ino, kind, name)) in items.into_iter().enumerate().skip(start) {
            // FUSE readdir offsets are the index of the *next* entry.
            let next = i64::try_from(i + 1).unwrap_or(i64::MAX);
            if reply.add(ino, next, kind, name) {
                break;
            }
        }
        reply.ok();
    }

    fn statfs(&mut self, _req: &Request<'_>, _ino: u64, reply: ReplyStatfs) {
        let bsize = self.tree.block_size();
        reply.statfs(
            self.tree.block_count(),
            0,
            0,
            self.tree.entry_count() as u64,
            0,
            bsize,
            255,
            bsize,
        );
    }
}

/// Mounts `tree` read-only on `mountpoint` and blocks until unmounted.
/// `subtype` names the source format (`ffpfsc`, `pkg`) in `/proc/mounts`.
pub fn mount<T: FileTree + 'static>(
    tree: T,
    subtype: &str,
    mountpoint: &Path,
    allow_other: bool,
) -> std::io::Result<()> {
    let fs = Bc5Fs {
        tree,
        uid: 0,
        gid: 0,
        mounted_at: SystemTime::now(),
        names: HashMap::new(),
    };
    let mut options = vec![
        MountOption::RO,
        MountOption::FSName("bc5-mount".into()),
        MountOption::Subtype(subtype.into()),
        MountOption::DefaultPermissions,
        // No AutoUnmount: it needs `user_allow_other` in /etc/fuse.conf for
        // non-root users; callers unmount with `fusermount3 -u`.
    ];
    if allow_other {
        options.push(MountOption::AllowOther);
    }
    fuser::mount2(fs, mountpoint, &options)
}
