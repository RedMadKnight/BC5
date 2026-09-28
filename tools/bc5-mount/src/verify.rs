// SPDX-License-Identifier: GPL-2.0-only
//! Per-file SHA-256 over a mounted tree or a plain directory, for the
//! `verify` subcommand and the gate experiment.

use std::fs;
use std::io::{self, Read};
use std::path::Path;

use sha2::{Digest, Sha256};

use crate::error::Result;
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

/// Hashes every file in the volume, sorted by path. `progress` is called with
/// bytes hashed so far.
pub fn hash_volume<R: ReadAt>(
    vol: &ExfatVolume<R>,
    mut progress: impl FnMut(u64),
) -> Result<Vec<FileHash>> {
    let mut files: Vec<usize> = (0..vol.entries().len())
        .filter(|&i| !vol.entries()[i].is_dir)
        .collect();
    files.sort_by(|&a, &b| vol.entries()[a].path.cmp(&vol.entries()[b].path));
    let mut buf = vec![0u8; 1 << 20];
    let mut done = 0u64;
    let mut out = Vec::with_capacity(files.len());
    for idx in files {
        let entry = &vol.entries()[idx];
        let file = vol.file(idx)?;
        let mut h = Sha256::new();
        let mut off = 0u64;
        while off < entry.size {
            let n = file.read_at(off, &mut buf)?;
            if n == 0 {
                return Err(
                    io::Error::new(io::ErrorKind::UnexpectedEof, entry.path.clone()).into(),
                );
            }
            h.update(&buf[..n]);
            off += n as u64;
            done += n as u64;
            progress(done);
        }
        out.push(FileHash {
            path: entry.path.clone(),
            size: entry.size,
            sha256: h.finalize().into(),
        });
    }
    Ok(out)
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
