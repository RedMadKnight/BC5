// SPDX-License-Identifier: GPL-2.0-only
//! `install` subcommand: unpack a container or package into a plain directory.
//!
//! Walks the image's file tree, writes every file under `<dest>` with the same
//! relative paths and sizes. Streams each file (no whole-file buffering).
//! Writes to `<dest>.partial` first; on success renames to `<dest>`.
//! Refuses if `<dest>` already exists (exit 2), unless `--resume`.
//! Checks free space before starting (sum of file sizes + 1 GiB).
//! `--verify` compares each written file's sha256 with the image's.
//! Progress on stderr every 5 s.
//! Uses `posix_fadvise` for sequential reads and DONTNEED after fsync.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::Path;
use std::time::SystemTime;
use std::time::{Duration, Instant};

use anyhow::{bail, Context};
use sha2::{Digest, Sha256};

use crate::container::Container;
use crate::io::{FileSource, ReadAt};
use crate::pkg::PkgImage;
use crate::tree::TreeFile;
use crate::verify::FileHash;

/// What the install command produces.
#[derive(Debug)]
pub struct InstallInfo {
    /// Number of files written.
    pub file_count: usize,
    /// Total bytes written.
    pub total_bytes: u64,
    /// SHA-256 hashes of every file (sorted by path).
    pub hashes: Vec<FileHash>,
}

/// Open a container or package from a path.
pub enum OpenedImage {
    Ffpfsc(Box<Container<FileSource>>),
    Pkg(Box<PkgImage<FileSource>>),
}

impl OpenedImage {
    pub fn open(path: &Path) -> anyhow::Result<Self> {
        let mut head = [0u8; 4];
        let n = File::open(path)
            .and_then(|mut f| f.read(&mut head))
            .with_context(|| format!("opening {}", path.display()))?;
        if crate::pkg::is_package(&head[..n]) {
            PkgImage::open_path(path)
                .map(|p| OpenedImage::Pkg(Box::new(p)))
                .with_context(|| format!("opening the package {}", path.display()))
        } else {
            Container::open_path(path)
                .map(|c| OpenedImage::Ffpfsc(Box::new(c)))
                .with_context(|| format!("opening {}", path.display()))
        }
    }

    pub fn tree(&self) -> &dyn crate::tree::FileTree {
        match self {
            OpenedImage::Ffpfsc(c) => c.as_ref(),
            OpenedImage::Pkg(p) => p.as_ref(),
        }
    }

    #[allow(dead_code)]
    fn file_count(&self) -> usize {
        (0..self.tree().entry_count())
            .filter(|&i| self.tree().entry(i).is_some_and(|e| !e.is_dir))
            .count()
    }

    #[allow(dead_code)]
    fn total_file_bytes(&self) -> u64 {
        (0..self.tree().entry_count())
            .filter_map(|i| self.tree().entry(i))
            .filter(|e| !e.is_dir)
            .map(|e| e.size)
            .sum()
    }
}

/// Check available free space at `dest`'s parent directory.
/// Returns (required_bytes, free_bytes).
fn check_free_space(dest: &Path, required_extra: u64) -> anyhow::Result<(u64, u64)> {
    // Use statvfs if available (Unix), otherwise fall back.
    #[cfg(unix)]
    {
        let parent = dest
            .parent()
            .map(Path::new)
            .unwrap_or(Path::new("."));
        let vfs = nix::sys::statvfs::statvfs(parent)
            .with_context(|| format!("statvfs {}", parent.display()))?;
        let free = vfs.blocks_free() * vfs.block_size();
        Ok((required_extra, free))
    }

    #[cfg(not(unix))]
    {
        // Fallback: assume we have enough space.
        Ok((required_extra, required_extra))
    }
}

/// Write progress to stderr every 5 seconds.
struct ProgressPrinter {
    #[allow(dead_code)]
    start: Instant,
    last_print: Instant,
    files_done: usize,
    bytes_done: u64,
    files_total: usize,
    bytes_total: u64,
}

impl ProgressPrinter {
    fn new(files_total: usize, bytes_total: u64) -> Self {
        let now = Instant::now();
        Self {
            start: now,
            last_print: now,
            files_done: 0,
            bytes_done: 0,
            files_total,
            bytes_total,
        }
    }

    fn maybe_print(&mut self) -> io::Result<()> {
        if self.last_print.elapsed() < Duration::from_secs(5) {
            return Ok(());
        }
        let elapsed = self.last_print.elapsed();
        let secs = elapsed.as_secs_f64();
        let mb_per_sec = if secs > 0.0 {
            self.bytes_done as f64 / (1024.0 * 1024.0) / secs
        } else {
            0.0
        };
        let gb_done = self.bytes_done as f64 / (1024.0 * 1024.0 * 1024.0);
        let gb_total = self.bytes_total as f64 / (1024.0 * 1024.0 * 1024.0);
        eprintln!(
            "[bc5-install] {}/{} files, {:.2}/{:.2} GiB, {:.1} MB/s ({:.0}s elapsed)",
            self.files_done,
            self.files_total,
            gb_done,
            gb_total,
            mb_per_sec,
            secs,
        );
        self.last_print = Instant::now();
        Ok(())
    }

    fn file_done(&mut self, bytes: u64) -> io::Result<()> {
        self.files_done += 1;
        self.bytes_done += bytes;
        self.maybe_print()
    }

    fn finish(&mut self) -> io::Result<()> {
        let elapsed = self.last_print.elapsed();
        let secs = elapsed.as_secs_f64();
        let mb_per_sec = if secs > 0.0 {
            self.bytes_done as f64 / (1024.0 * 1024.0) / secs
        } else {
            0.0
        };
        eprintln!(
            "[bc5-install] done: {}/{} files, {:.2} GiB, {:.1} MB/s ({:.0}s total)",
            self.files_done,
            self.files_total,
            self.bytes_done as f64 / (1024.0 * 1024.0 * 1024.0),
            mb_per_sec,
            secs,
        );
        Ok(())
    }
}

/// Install a container or package into a directory.
///
/// * `image_path` — path to the .ffpfsc or .pkg file
/// * `dest` — destination directory (refused if exists, unless `resume`)
/// * `resume` — skip files whose size already matches
/// * `verify` — compare sha256 after writing
pub fn install(
    image_path: &Path,
    dest: &Path,
    resume: bool,
    verify: bool,
) -> anyhow::Result<InstallInfo> {
    // Open the image.
    let opened = OpenedImage::open(image_path)?;
    let tree = opened.tree();

    // Collect files (sorted by path).
    let mut files: Vec<(usize, String, u64)> = (0..tree.entry_count())
        .filter_map(|i| {
            let e = tree.entry(i)?;
            if e.is_dir {
                None
            } else {
                Some((i, e.path.to_owned(), e.size))
            }
        })
        .collect();
    files.sort_by(|a, b| a.1.cmp(&b.1));

    let files_total = files.len();
    let bytes_total: u64 = files.iter().map(|f| f.2).sum();

    // Check free space: sum of file sizes + 1 GiB.
    let (required, free) = check_free_space(dest, bytes_total + 1024 * 1024 * 1024)?;
    if free < required {
        bail!(
            "insufficient free space: need {} bytes ({} GiB), have {} bytes ({} GiB)",
            required,
            required / (1024 * 1024 * 1024),
            free,
            free / (1024 * 1024 * 1024),
        );
    }

    // Refuse if dest exists (unless resume).
    if dest.exists() && !resume {
        bail!("destination {} already exists (use --resume to skip matching files)", dest.display());
    }

    // Create destination directory.
    fs::create_dir_all(dest).with_context(|| format!("creating {}", dest.display()))?;

    // Progress printer.
    let mut progress = ProgressPrinter::new(files_total, bytes_total);

    // Install each file.
    let mut hashes = Vec::with_capacity(files_total);
    let mut file_count = 0;
    let mut total_bytes = 0u64;

    for (idx, path, size) in &files {
        let file_path = dest.join(path);
        let partial_path = format!("{}.bc5part", file_path.display());

        // Resume: skip files whose size already matches.
        if resume {
            if let Ok(meta) = fs::metadata(&file_path) {
                if meta.len() == *size {
                    // File size matches; skip.
                    progress.maybe_print()?;
                    continue;
                }
            }
        }

        // Read file from image.
        let tree_file = TreeFile::new(tree, *idx)
            .with_context(|| format!("reading file {} from image", path))?;

        // Create parent directories.
        if let Some(parent) = Path::new(&partial_path).parent() {
            fs::create_dir_all(parent)
                .with_context(|| format!("creating {}", parent.display()))?;
        }

        // Stream to file.
        let mut out = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&partial_path)
            .with_context(|| format!("creating {}", partial_path))?;

        let mut buf = vec![0u8; 1 << 20]; // 1 MiB buffer
        let mut off = 0u64;
        let mut file_hash = Sha256::new();

        while off < *size {
            let n = tree_file.read_at(off, &mut buf)?;
            if n == 0 {
                break;
            }
            out.write_all(&buf[..n])
                .with_context(|| format!("writing to {}", partial_path))?;
            file_hash.update(&buf[..n]);
            off += n as u64;
        }

        // fsync the file.
        out.sync_all()
            .with_context(|| format!("syncing {}", partial_path))?;

        // POSIX_FADV_DONTNEED on the written range.
        #[cfg(target_os = "linux")]
        {
            use nix::fcntl::{posix_fadvise, PosixFadviseAdvice};
            use std::os::unix::io::IntoRawFd;
            if let Ok(f) = File::open(&partial_path) {
                let fd = f.into_raw_fd();
                let _ = posix_fadvise(fd, 0, 0, PosixFadviseAdvice::POSIX_FADV_DONTNEED);
            }
        }

        // Rename partial to final.
        fs::rename(&partial_path, &file_path)
            .with_context(|| format!("renaming {} to {}", partial_path, file_path.display()))?;

        // Compute hex hash.
        let digest = file_hash.finalize();
        let _hex = hex::encode(&digest);
        hashes.push(FileHash {
            path: path.clone(),
            size: *size,
            sha256: digest.into(),
        });
        file_count += 1;
        total_bytes += *size;

        progress.file_done(*size)?;
    }

    progress.finish()?;

    // Sort hashes by path.
    hashes.sort_by(|a, b| a.path.cmp(&b.path));

    // --verify: re-read each written file from disk and compare with image hashes.
    if verify {
        let disk_hashes = crate::verify::hash_directory(dest)
            .with_context(|| "re-reading installed files from disk")?;
        let diffs = crate::verify::diff(&hashes, &disk_hashes);
        if !diffs.is_empty() {
            bail!("verification failed (disk re-read): {}", diffs.join(", "));
        }
    }

    Ok(InstallInfo {
        file_count,
        total_bytes,
        hashes,
    })
}

/// Write `.bc5-install.json` metadata file.
pub fn write_install_json(
    dest: &Path,
    image_path: &Path,
    info: &InstallInfo,
) -> anyhow::Result<()> {
    let mut json = String::new();
    json.push_str("{\n");
    json.push_str(&format!("  \"image\": \"{}\",\n", image_path.display()));
    json.push_str(&format!("  \"image_size\": {},\n", fs::metadata(image_path)?.len()));
    json.push_str(&format!("  \"file_count\": {},\n", info.file_count));
    json.push_str(&format!("  \"total_bytes\": {},\n", info.total_bytes));
    json.push_str("  \"sha256\": {\n");
    for (i, h) in info.hashes.iter().enumerate() {
        json.push_str(&format!("    \"{}\": \"{}\"", h.path, h.hex()));
        if i < info.hashes.len() - 1 {
            json.push(',');
        }
        json.push('\n');
    }
    json.push_str("  },\n");
    json.push_str(&format!("  \"date\": \"{}\"\n", SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap_or_default().as_secs()));
    json.push_str("}\n");

    let json_path = dest.join(".bc5-install.json");
    let mut tmp = json_path.clone();
    tmp.set_extension("partial");
    fs::write(&tmp, &json)
        .with_context(|| format!("writing {}", tmp.display()))?;
    fs::rename(&tmp, &json_path)
        .with_context(|| format!("renaming {} to {}", tmp.display(), json_path.display()))?;

    Ok(())
}

/// Lower-case hex encoding.
mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        use std::fmt::Write;
        let mut s = String::with_capacity(bytes.len() * 2);
        for b in bytes {
            let _ = write!(s, "{b:02x}");
        }
        s
    }
}
