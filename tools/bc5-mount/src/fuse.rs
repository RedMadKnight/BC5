// SPDX-License-Identifier: GPL-2.0-only
//! FUSE glue (Linux only): exposes a [`FileTree`] (the exFAT tree of a
//! `.ffpfsc` container or the inner image of a PS5 package) as a read-only
//! file system. Inode numbers are entry indices plus one, so the root is 1 as
//! FUSE expects. Written against `fuser` 0.15.
//!
//! The session loop is single-threaded, but reads are answered from a pool of
//! worker threads: a game's loaders each wait on their own read, and serving
//! them one after another made the level load the file server's pace
//! (experiment 0032). Lookups and directory listings stay on the session
//! thread; they are cheap. A file read in order is also decoded ahead: the
//! pool fills the block cache with the next bytes while the game is still
//! busy with the last ones (experiment 0033).

use std::collections::HashMap;
use std::ffi::OsStr;
use std::num::NonZeroUsize;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, SystemTime};

use fuser::{
    FileAttr, FileType, Filesystem, KernelConfig, MountOption, ReplyAttr, ReplyData,
    ReplyDirectory, ReplyEntry, ReplyOpen, ReplyStatfs, Request,
};

use crate::reuse::{Reuse, AGE_LIMITS, DISTANCE_LIMITS_MIB};
use crate::stats::Span;
use crate::trace::ReadTrace;
use crate::tree::{fold_name, FileTree};
use crate::tuning::Tuning;

const ENOENT: i32 = 2;
const EIO: i32 = 5;
const ENOTDIR: i32 = 20;
const EISDIR: i32 = 21;
const EINVAL: i32 = 22;

/// Attribute/entry cache lifetime; the source never changes.
const TTL: Duration = Duration::from_secs(3600);
/// Worker threads answering reads, unless `BC5_MOUNT_THREADS` says otherwise:
/// the machine's parallelism, at most this many.
const MAX_WORKERS: usize = 8;
/// Bytes decoded ahead of a file read in order, unless `BC5_MOUNT_PREFETCH_KIB`
/// says otherwise (0 turns it off).
const PREFETCH: u64 = 2 << 20;
/// A read starting this close to where the last one of the same file ended
/// counts as reading in order (the kernel's own readahead skips a little).
const SEQUENTIAL_SLACK: u64 = 1 << 20;

type Job = Box<dyn FnOnce() + Send>;

/// A fixed pool of threads running jobs in arrival order.
struct Pool {
    tx: mpsc::Sender<Job>,
    threads: usize,
    /// Jobs queued or running.
    pending: Arc<AtomicUsize>,
}

impl Pool {
    fn new(threads: usize) -> Self {
        let (tx, rx) = mpsc::channel::<Job>();
        let rx = Arc::new(Mutex::new(rx));
        let pending = Arc::new(AtomicUsize::new(0));
        for i in 0..threads {
            let rx = Arc::clone(&rx);
            let pending = Arc::clone(&pending);
            std::thread::Builder::new()
                .name(format!("bc5-mount-io{i}"))
                .spawn(move || loop {
                    let job = rx
                        .lock()
                        .unwrap_or_else(std::sync::PoisonError::into_inner)
                        .recv();
                    match job {
                        Ok(job) => {
                            job();
                            pending.fetch_sub(1, Ordering::Relaxed);
                        }
                        Err(_) => break,
                    }
                })
                .expect("spawning a worker thread");
        }
        Self {
            tx,
            threads,
            pending,
        }
    }

    fn run(&self, job: Job) {
        let jobs = self.pending.fetch_add(1, Ordering::Relaxed) + 1;
        crate::stats::pending(jobs as u64);
        // A send fails only when every worker is gone, which the pool's owner
        // outlives; run the job here then.
        if let Err(e) = self.tx.send(job) {
            (e.0)();
            self.pending.fetch_sub(1, Ordering::Relaxed);
        }
    }

    /// True when every worker could take a job now.
    fn idle_enough(&self) -> bool {
        self.pending.load(Ordering::Relaxed) < self.threads
    }
}

/// Worker count from `BC5_MOUNT_THREADS` (1 answers reads one at a time, as
/// before), or the machine's parallelism capped at [`MAX_WORKERS`].
fn worker_count() -> usize {
    if let Some(n) = std::env::var("BC5_MOUNT_THREADS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .filter(|&n| n >= 1)
    {
        return n.min(64);
    }
    std::thread::available_parallelism()
        .map_or(1, NonZeroUsize::get)
        .clamp(1, MAX_WORKERS)
}

/// Decode-ahead length from `BC5_MOUNT_PREFETCH_KIB`, or [`PREFETCH`].
fn prefetch_len() -> u64 {
    std::env::var("BC5_MOUNT_PREFETCH_KIB")
        .ok()
        .and_then(|v| v.parse::<u64>().ok())
        .map_or(PREFETCH, |k| k.min(256 << 10) << 10)
}

/// Per file: where the last read ended and how far decode-ahead has gone.
#[derive(Debug, Default, Clone, Copy)]
struct Stream {
    last_end: u64,
    ahead_to: u64,
}

struct Bc5Fs<T> {
    tree: Arc<T>,
    pool: Pool,
    prefetch: u64,
    streams: HashMap<usize, Stream>,
    /// Exp 0381's switches.
    tuning: Tuning,
    /// What is read again, with `BC5_MOUNT_STATS`.
    reuse: Option<Arc<Mutex<Reuse>>>,
    /// Every request, with `BC5_MOUNT_READ_TRACE`.
    trace: Option<ReadTrace<std::fs::File>>,
    uid: u32,
    gid: u32,
    mounted_at: SystemTime,
    /// Per directory, folded child name -> entry index, built on the directory's first
    /// lookup. A linear scan folding every name cost ~8 ms per miss in a 12,000-entry
    /// directory, and a game stats missing files by the thousand while it loads
    /// (experiment 0029).
    names: HashMap<usize, HashMap<String, usize>>,
}

impl<T: FileTree + 'static> Bc5Fs<T> {
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

    /// Called for every read of file `idx` covering `[offset, end)`: when
    /// the file is being read in order, queue the decoding of the next
    /// `prefetch` bytes that are not queued yet. Skipped while the pool is
    /// busy, so decode-ahead never delays a read a game waits for.
    fn decode_ahead(&mut self, idx: usize, offset: u64, end: u64, file_size: u64) {
        if self.prefetch == 0 {
            return;
        }
        let s = self.streams.entry(idx).or_default();
        let in_order = offset >= s.last_end.saturating_sub(SEQUENTIAL_SLACK)
            && offset <= s.last_end + SEQUENTIAL_SLACK
            && s.last_end > 0;
        s.last_end = end;
        if !in_order {
            s.ahead_to = end;
            return;
        }
        let from = s.ahead_to.max(end);
        let to = (end + self.prefetch).min(file_size);
        if to <= from || !self.pool.idle_enough() {
            return;
        }
        s.ahead_to = to;
        let tree = Arc::clone(&self.tree);
        self.pool.run(Box::new(move || {
            // Blocks another reader is decoding are skipped, not waited for
            // (experiment 0116). Errors surface on the real read; here they
            // only end the run.
            let _ = tree.prefetch_file(idx, from, to - from);
        }));
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
    fn init(&mut self, req: &Request<'_>, config: &mut KernelConfig) -> Result<(), i32> {
        self.uid = req.uid();
        self.gid = req.gid();
        if let Some(n) = self.tuning.max_readahead {
            let got = config.set_max_readahead(n);
            eprintln!("bc5-mount: kernel readahead asked {} KiB: {got:?}", n >> 10);
        }
        if self.tuning.direct_io {
            eprintln!("bc5-mount: direct I/O, reads pass the page cache by");
        }
        // Reads from different threads are separate requests the kernel sends
        // without waiting for each other; the pool answers them in parallel.
        eprintln!(
            "bc5-mount: {} read worker{}, decode-ahead {} KiB",
            self.pool.threads,
            if self.pool.threads == 1 { "" } else { "s" },
            self.prefetch >> 10
        );
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

    fn forget(&mut self, _req: &Request<'_>, ino: u64, nlookup: u64) {
        if let Some(t) = &mut self.trace {
            t.forget(ino, nlookup);
        }
    }

    fn open(&mut self, req: &Request<'_>, ino: u64, _flags: i32, reply: ReplyOpen) {
        if let Some(t) = &mut self.trace {
            t.open(ino, req.pid());
        }
        match Self::idx(ino).and_then(|i| self.tree.entry(i)) {
            Some(e) if e.is_dir => reply.error(EISDIR),
            Some(_) if self.tuning.direct_io => reply.opened(0, fuser::consts::FOPEN_DIRECT_IO),
            Some(_) => reply.opened(0, fuser::consts::FOPEN_KEEP_CACHE),
            None => reply.error(ENOENT),
        }
    }

    fn read(
        &mut self,
        req: &Request<'_>,
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
        let file_size = e.size;
        let want = usize::try_from(e.size.saturating_sub(offset).min(u64::from(size))).unwrap_or(0);
        if let Some(t) = &mut self.trace {
            t.read(ino, offset, want as u64, req.pid());
        }
        if let Some(r) = &self.reuse {
            let now = self.mounted_at.elapsed().map_or(0.0, |d| d.as_secs_f64());
            r.lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .read(idx, offset, want as u64, now);
        }
        self.decode_ahead(idx, offset, offset + want as u64, file_size);
        let tree = Arc::clone(&self.tree);
        let queued = crate::stats::span_start();
        self.pool.run(Box::new(move || {
            crate::stats::span_end(Span::Queue, queued);
            let service = crate::stats::span_start();
            let mut buf = vec![0u8; want];
            match tree.read_file_at(idx, offset, &mut buf) {
                Ok(n) => {
                    crate::stats::served(n as u64);
                    reply.data(&buf[..n]);
                }
                Err(err) => {
                    eprintln!("bc5-mount: read {path}: {err}");
                    reply.error(EIO);
                }
            }
            crate::stats::span_end(Span::Service, service);
        }));
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
    let tree = Arc::new(tree);
    let reuse = report_stats(&tree);
    let fs = Bc5Fs {
        tree,
        pool: Pool::new(worker_count()),
        prefetch: prefetch_len(),
        streams: HashMap::new(),
        tuning: Tuning::from_env(),
        reuse,
        trace: ReadTrace::from_env(),
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

/// With `BC5_MOUNT_STATS=<seconds>`, prints the read and decode counters at that
/// interval on stderr, while they change (experiment 0112), and what is read
/// again (exp 0381): a `reread` and a `spans` line each time, the files with the
/// most repeats once a minute.
fn report_stats<T: FileTree + 'static>(tree: &Arc<T>) -> Option<Arc<Mutex<Reuse>>> {
    let every = std::env::var("BC5_MOUNT_STATS")
        .ok()
        .and_then(|v| v.trim().parse::<f64>().ok())
        .filter(|s| *s > 0.0)?;
    crate::stats::enable();
    let reuse = Arc::new(Mutex::new(Reuse::default()));
    let shared = Arc::clone(&reuse);
    let tree = Arc::clone(tree);
    let started = std::time::Instant::now();
    let _ = std::thread::Builder::new()
        .name("bc5-mount-stats".into())
        .spawn(move || {
            let mut last = crate::stats::Snapshot::default();
            let mut last_reuse = crate::reuse::Totals::default();
            let mut last_spans = crate::stats::spans();
            let mut last_files = 0.0;
            loop {
                std::thread::sleep(Duration::from_secs_f64(every));
                let s = crate::stats::snapshot();
                if s == last {
                    continue;
                }
                let mib = |b: u64| b >> 20;
                eprintln!(
                    "bc5-mount stats {:.1} s: served {} MiB (+{}), decoded {} blocks {} MiB (+{}), {} decoded again, from disk {} blocks {} MiB (+{})",
                    started.elapsed().as_secs_f64(),
                    mib(s.served_bytes),
                    mib(s.served_bytes - last.served_bytes),
                    s.decoded_blocks,
                    mib(s.decoded_bytes),
                    mib(s.decoded_bytes - last.decoded_bytes),
                    s.redecoded_blocks,
                    s.disk_blocks,
                    mib(s.disk_bytes),
                    mib(s.disk_bytes - last.disk_bytes)
                );
                let (r, top) = {
                    let u = shared
                        .lock()
                        .unwrap_or_else(std::sync::PoisonError::into_inner);
                    (u.totals(), u.top_files(12))
                };
                let t = started.elapsed().as_secs_f64();
                eprintln!(
                    "bc5-mount reread {t:.1} s: first {} MiB (+{}), again {} MiB (+{}), age s {:?} {:?} MiB, distance MiB {:?} {:?} MiB",
                    mib(r.first),
                    mib(r.first - last_reuse.first),
                    mib(r.again),
                    mib(r.again - last_reuse.again),
                    AGE_LIMITS,
                    r.by_age.map(mib),
                    DISTANCE_LIMITS_MIB,
                    r.by_distance.map(mib),
                );
                last_reuse = r;
                let now = crate::stats::spans();
                let mut line = format!(
                    "bc5-mount spans {t:.1} s: jobs peak {}, image {} MiB (+{}), written {} MiB (+{}), block uses {}, ahead {} used {}",
                    crate::stats::take_pending_peak(),
                    mib(s.image_bytes),
                    mib(s.image_bytes - last.image_bytes),
                    mib(s.put_bytes),
                    mib(s.put_bytes - last.put_bytes),
                    s.touches,
                    s.ahead_blocks,
                    s.ahead_used
                );
                for (((_, name), n), o) in crate::stats::SPANS.iter().zip(&now).zip(&last_spans) {
                    use std::fmt::Write as _;
                    let count = n.count - o.count;
                    let mean = (n.ns - o.ns).checked_div(count).unwrap_or(0);
                    let _ = write!(
                        line,
                        ", {name} {count} mean {} us peak {} us",
                        mean / 1000,
                        n.peak_ns / 1000
                    );
                }
                eprintln!("{line}");
                last_spans = now;
                if t - last_files >= 60.0 {
                    last_files = t;
                    for (idx, b) in top {
                        let path = tree.entry(idx).map_or("?", |e| e.path);
                        eprintln!(
                            "bc5-mount again {t:.0} s: {} MiB of {} MiB {path}",
                            mib(b.again),
                            mib(b.first + b.again)
                        );
                    }
                }
                last = s;
            }
        });
    Some(reuse)
}
