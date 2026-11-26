// SPDX-License-Identifier: GPL-2.0-only
//! `uninstall` subcommand: remove one installed game and free its space (experiment 0420).
//!
//! It removes a directory only when every one of these holds, and refuses anything else:
//!
//! * the path names no `..` component and is not a symbolic link;
//! * it is a directory that resolves to a **direct child** of the games root (by default
//!   `~/bc5-data/games`), never the root itself and never a deeper path;
//! * it lies on the same file system as the root;
//! * it holds a `.bc5-install.json` written by `install` or `adopt` that names the image, a file
//!   count and a byte count.
//!
//! The tree is removed with `std::fs::remove_dir_all`, which does not follow symbolic links: a link
//! inside the install is removed as a link and its target stays. The source image named by the
//! record and the title's save data (which is not under the games root) are never read or touched.

use std::fmt;
use std::fs;
use std::path::{Component, Path, PathBuf};

/// The name of the record `install` and `adopt` write into an installed directory.
pub const RECORD: &str = ".bc5-install.json";

/// Why a directory is not removed. Every case is a refusal, not a failure of the removal.
#[derive(Debug, PartialEq, Eq)]
pub struct Refused(pub String);

impl fmt::Display for Refused {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "refused: {}", self.0)
    }
}

impl std::error::Error for Refused {}

/// What the record says, as far as `uninstall` and the menu need it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    /// The image the directory was installed from.
    pub image: String,
    /// Files written by the install.
    pub file_count: u64,
    /// Bytes written by the install.
    pub total_bytes: u64,
}

/// A directory that passed every check.
#[derive(Debug)]
pub struct Checked {
    /// The directory, resolved.
    pub dir: PathBuf,
    /// Its record.
    pub record: Record,
}

/// What a removal did.
#[derive(Debug)]
pub struct Removed {
    /// The directory that was removed.
    pub dir: PathBuf,
    /// Bytes of the files and links that were removed (not followed).
    pub bytes: u64,
    /// Entries removed (files, links and directories, the directory itself included).
    pub entries: u64,
    /// Whether the record's image is still at its path (a new install needs it).
    pub image_present: bool,
    /// The record.
    pub record: Record,
}

/// The default games root: `$HOME/bc5-data/games`.
pub fn default_root() -> Option<PathBuf> {
    std::env::var_os("HOME").map(|h| PathBuf::from(h).join("bc5-data").join("games"))
}

/// Reads a JSON string starting at `s[0] == '"'`; returns the text and the rest after the closing quote.
fn json_string(s: &str) -> Option<(String, &str)> {
    let mut out = String::new();
    let mut it = s.strip_prefix('"')?.char_indices();
    while let Some((i, c)) = it.next() {
        match c {
            '"' => return Some((out, &s[i + 2..])),
            '\\' => {
                let (_, e) = it.next()?;
                match e {
                    '"' => out.push('"'),
                    '\\' => out.push('\\'),
                    '/' => out.push('/'),
                    'n' => out.push('\n'),
                    't' => out.push('\t'),
                    'r' => out.push('\r'),
                    'b' => out.push('\u{8}'),
                    'f' => out.push('\u{c}'),
                    'u' => {
                        let mut v = 0u32;
                        for _ in 0..4 {
                            let (_, h) = it.next()?;
                            v = v * 16 + h.to_digit(16)?;
                        }
                        out.push(char::from_u32(v)?);
                    }
                    _ => return None,
                }
            }
            c if (c as u32) < 0x20 => return None,
            c => out.push(c),
        }
    }
    None
}

/// The value of a top-level key of the record: the text after `"key":`, white space skipped.
fn after_key<'a>(text: &'a str, key: &str) -> Option<&'a str> {
    let needle = format!("\"{key}\":");
    // The record's keys sit at the start of a line (two spaces in), so a file name inside the
    // `sha256` map that happens to read `"image":` cannot be taken for the key.
    for line in text.lines() {
        let t = line.trim_start();
        if line.len() - t.len() == 2 {
            if let Some(rest) = t.strip_prefix(&needle) {
                return Some(rest.trim_start());
            }
        }
    }
    None
}

fn number(rest: &str) -> Option<u64> {
    let end = rest
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(rest.len());
    rest[..end].parse().ok()
}

/// Parses a record's text. `None` when it is not one `install` or `adopt` wrote.
pub fn parse_record(text: &str) -> Option<Record> {
    if !text.trim_start().starts_with('{') || !text.trim_end().ends_with('}') {
        return None;
    }
    let (image, _) = json_string(after_key(text, "image")?)?;
    let file_count = number(after_key(text, "file_count")?)?;
    let total_bytes = number(after_key(text, "total_bytes")?)?;
    if image.is_empty() {
        return None;
    }
    Some(Record {
        image,
        file_count,
        total_bytes,
    })
}

/// Reads the record of an installed directory.
pub fn read_record(dir: &Path) -> Result<Record, Refused> {
    let p = dir.join(RECORD);
    let meta = fs::symlink_metadata(&p)
        .map_err(|_| Refused(format!("{} holds no {RECORD}", dir.display())))?;
    if !meta.is_file() {
        return Err(Refused(format!("{} is not a plain file", p.display())));
    }
    let text =
        fs::read_to_string(&p).map_err(|e| Refused(format!("cannot read {}: {e}", p.display())))?;
    parse_record(&text).ok_or_else(|| Refused(format!("{} is not an install record", p.display())))
}

#[cfg(unix)]
fn same_device(a: &fs::Metadata, b: &fs::Metadata) -> bool {
    use std::os::unix::fs::MetadataExt;
    a.dev() == b.dev()
}

#[cfg(not(unix))]
fn same_device(_a: &fs::Metadata, _b: &fs::Metadata) -> bool {
    true
}

/// Every check of the module's header, without removing anything.
pub fn check(dir: &Path, root: &Path) -> Result<Checked, Refused> {
    if dir.components().any(|c| matches!(c, Component::ParentDir)) {
        return Err(Refused(format!("{} names a `..` component", dir.display())));
    }
    let meta = fs::symlink_metadata(dir).map_err(|e| Refused(format!("{}: {e}", dir.display())))?;
    if meta.file_type().is_symlink() {
        return Err(Refused(format!("{} is a symbolic link", dir.display())));
    }
    if !meta.is_dir() {
        return Err(Refused(format!("{} is not a directory", dir.display())));
    }
    let root_real = fs::canonicalize(root)
        .map_err(|e| Refused(format!("the games root {}: {e}", root.display())))?;
    let dir_real = fs::canonicalize(dir).map_err(|e| Refused(format!("{}: {e}", dir.display())))?;
    if dir_real == root_real {
        return Err(Refused(format!(
            "{} is the games root itself",
            dir.display()
        )));
    }
    if dir_real.parent() != Some(root_real.as_path()) {
        return Err(Refused(format!(
            "{} is not a directory directly under the games root {}",
            dir.display(),
            root_real.display()
        )));
    }
    let root_meta = fs::metadata(&root_real)
        .map_err(|e| Refused(format!("the games root {}: {e}", root_real.display())))?;
    if !same_device(&meta, &root_meta) {
        return Err(Refused(format!(
            "{} is on another file system than the games root",
            dir.display()
        )));
    }
    let record = read_record(&dir_real)?;
    Ok(Checked {
        dir: dir_real,
        record,
    })
}

/// Bytes and entries of a tree, links counted as links (not followed).
fn measure(dir: &Path) -> std::io::Result<(u64, u64)> {
    let mut bytes = 0u64;
    let mut entries = 1u64;
    for e in fs::read_dir(dir)? {
        let e = e?;
        let m = fs::symlink_metadata(e.path())?;
        if m.is_dir() {
            let (b, n) = measure(&e.path())?;
            bytes += b;
            entries += n;
        } else {
            bytes += m.len();
            entries += 1;
        }
    }
    Ok((bytes, entries))
}

/// Gives the owner write permission on every directory of the tree that lacks it, links not
/// followed, so that `remove_dir_all` can unlink their entries. A tree copied from a read-only
/// mount keeps the image's modes (directories 0555): the maintainer's adopted install of
/// 2026-11-09 had them, and its uninstall stopped at the first one with EACCES (2026-11-15).
/// Files need no change: unlinking depends on the directory's mode only.
#[cfg(unix)]
fn make_dirs_writable(dir: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    let m = fs::symlink_metadata(dir)?;
    if !m.is_dir() {
        return Ok(());
    }
    let mode = m.permissions().mode();
    if mode & 0o300 != 0o300 {
        fs::set_permissions(dir, fs::Permissions::from_mode(mode | 0o700))?;
    }
    for e in fs::read_dir(dir)? {
        let e = e?;
        if e.file_type()?.is_dir() {
            make_dirs_writable(&e.path())?;
        }
    }
    Ok(())
}

/// Checks `dir`, then removes it unless `dry_run`.
pub fn uninstall(dir: &Path, root: &Path, dry_run: bool) -> anyhow::Result<Removed> {
    let checked = check(dir, root)?;
    let (bytes, entries) = measure(&checked.dir)?;
    let image_present = Path::new(&checked.record.image).is_file();
    if !dry_run {
        #[cfg(unix)]
        make_dirs_writable(&checked.dir)?;
        fs::remove_dir_all(&checked.dir)?;
    }
    Ok(Removed {
        dir: checked.dir,
        bytes,
        entries,
        image_present,
        record: checked.record,
    })
}
