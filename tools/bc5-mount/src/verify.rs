// SPDX-License-Identifier: GPL-2.0-only
//! Per-file SHA-256 over a mounted tree or a plain directory, for the
//! `verify` subcommand and the gate experiment.

use std::fs;
use std::io::{self, Read};
use std::num::NonZeroUsize;
use std::path::Path;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Mutex;

use sha2::{Digest, Sha256};

use crate::error::{Error, Result};
use crate::exfat::ExfatVolume;
use crate::io::ReadAt;

/// One hashed file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileHash {
    /// `/`-separated path relative to the root.
    pub path: String,
    /// Size in bytes.
    pub size: u64,
    /// SHA-256 digest.
    pub sha256: [u8; 32],
}

impl FileHash {
    /// Lower-case hex digest.
    pub fn hex(&self) -> String {
        hex(&self.sha256)
    }
}

/// Lower-case hex encoding.
pub fn hex(bytes: &[u8]) -> String {
    use std::fmt::Write;
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        let _ = write!(s, "{b:02x}");
    }
    s
}

/// Hashes every file in the volume, sorted by path, using all available
/// cores (files are distributed over threads; each file is read
/// sequentially). `progress` is called with bytes hashed so far.
pub fn hash_volume<R: ReadAt>(
    vol: &ExfatVolume<R>,
    progress: impl FnMut(u64) + Send,
) -> Result<Vec<FileHash>> {
    let threads = std::thread::available_parallelism().map_or(1, NonZeroUsize::get);
    hash_volume_with(vol, threads, progress)
}

/// [`hash_volume`] with an explicit thread count.
pub fn hash_volume_with<R: ReadAt>(
    vol: &ExfatVolume<R>,
    threads: usize,
    progress: impl FnMut(u64) + Send,
) -> Result<Vec<FileHash>> {
    let mut files: Vec<usize> = (0..vol.entries().len())
        .filter(|&i| !vol.entries()[i].is_dir)
        .collect();
    files.sort_by(|&a, &b| vol.entries()[a].path.cmp(&vol.entries()[b].path));
    let threads = threads.clamp(1, files.len().max(1));

    let next = AtomicUsize::new(0);
    let done = AtomicU64::new(0);
    let progress = Mutex::new(progress);
    let results: Vec<Mutex<Option<FileHash>>> = files.iter().map(|_| Mutex::new(None)).collect();
    let first_error: Mutex<Option<Error>> = Mutex::new(None);

    std::thread::scope(|scope| {
        for _ in 0..threads {
            scope.spawn(|| {
                let mut buf = vec![0u8; 1 << 20];
                loop {
                    let i = next.fetch_add(1, Ordering::Relaxed);
                    if i >= files.len() {
                        break;
                    }
                    let hashed = hash_one(vol, files[i], &mut buf, |n| {
                        let total = done.fetch_add(n, Ordering::Relaxed) + n;
                        if let Ok(mut p) = progress.lock() {
                            p(total);
                        }
                    });
                    match hashed {
                        Ok(h) => {
                            if let Ok(mut slot) = results[i].lock() {
                                *slot = Some(h);
                            }
                        }
                        Err(e) => {
                            if let Ok(mut err) = first_error.lock() {
                                err.get_or_insert(e);
                            }
                            next.store(files.len(), Ordering::Relaxed);
                            break;
                        }
                    }
                }
            });
        }
    });

    if let Some(e) = first_error
        .into_inner()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
    {
        return Err(e);
    }
    results
        .into_iter()
        .map(|m| {
            m.into_inner()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .ok_or_else(|| io::Error::other("a file was not hashed").into())
        })
        .collect()
}

fn hash_one<R: ReadAt>(
    vol: &ExfatVolume<R>,
    idx: usize,
    buf: &mut [u8],
    mut progress: impl FnMut(u64),
) -> Result<FileHash> {
    let entry = &vol.entries()[idx];
    let file = vol.file(idx)?;
    let mut h = Sha256::new();
    let mut off = 0u64;
    while off < entry.size {
        let n = file.read_at(off, buf)?;
        if n == 0 {
            return Err(io::Error::new(io::ErrorKind::UnexpectedEof, entry.path.clone()).into());
        }
        h.update(&buf[..n]);
        off += n as u64;
        progress(n as u64);
    }
    Ok(FileHash {
        path: entry.path.clone(),
        size: entry.size,
        sha256: h.finalize().into(),
    })
}

/// Hashes every regular file under `root`, sorted by path.
pub fn hash_directory(root: &Path) -> io::Result<Vec<FileHash>> {
    let mut out = Vec::new();
    walk(root, "", &mut out)?;
    out.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(out)
}

fn walk(dir: &Path, prefix: &str, out: &mut Vec<FileHash>) -> io::Result<()> {
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().into_owned();
        let path = if prefix.is_empty() {
            name
        } else {
            format!("{prefix}/{name}")
        };
        let ft = entry.file_type()?;
        if ft.is_dir() {
            walk(&entry.path(), &path, out)?;
        } else if ft.is_file() {
            let mut f = fs::File::open(entry.path())?;
            let mut h = Sha256::new();
            let mut buf = vec![0u8; 1 << 20];
            let mut size = 0u64;
            loop {
                let n = f.read(&mut buf)?;
                if n == 0 {
                    break;
                }
                h.update(&buf[..n]);
                size += n as u64;
            }
            out.push(FileHash {
                path,
                size,
                sha256: h.finalize().into(),
            });
        }
    }
    Ok(())
}

/// Compares two hash lists; returns human-readable differences (empty = equal).
pub fn diff(expected: &[FileHash], actual: &[FileHash]) -> Vec<String> {
    let mut out = Vec::new();
    let mut e = expected.iter().peekable();
    let mut a = actual.iter().peekable();
    loop {
        match (e.peek(), a.peek()) {
            (None, None) => break,
            (Some(x), None) => {
                out.push(format!("missing: {}", x.path));
                e.next();
            }
            (None, Some(y)) => {
                out.push(format!("unexpected: {}", y.path));
                a.next();
            }
            (Some(x), Some(y)) => match x.path.cmp(&y.path) {
                std::cmp::Ordering::Less => {
                    out.push(format!("missing: {}", x.path));
                    e.next();
                }
                std::cmp::Ordering::Greater => {
                    out.push(format!("unexpected: {}", y.path));
                    a.next();
                }
                std::cmp::Ordering::Equal => {
                    if x.size != y.size || x.sha256 != y.sha256 {
                        out.push(format!(
                            "differs: {} ({} vs {} bytes)",
                            x.path, x.size, y.size
                        ));
                    }
                    e.next();
                    a.next();
                }
            },
        }
    }
    out
}
