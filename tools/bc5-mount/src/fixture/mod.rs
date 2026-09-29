// SPDX-License-Identifier: GPL-2.0-only
//! Synthetic `.ffpfsc` containers for tests (ADR 0003). A [`Spec`] describes a
//! directory tree with deterministic file contents; [`build`] turns it into a
//! container: exFAT image → PFSC stream → PFS v2. Nothing here ever touches a
//! real dump.

pub mod exfat_writer;
pub mod pfs_writer;
pub mod pfsc_writer;

use std::fs;
use std::io::{self, Cursor, Seek, Write};
use std::path::Path;

use sha2::{Digest, Sha256};

use crate::error::Result;

/// Fixed timestamp used for every generated inode (2024-01-01T00:00:00Z).
pub const FIXED_TIMESTAMP: i64 = 1_704_067_200;

/// Deterministic file contents that can be produced at any offset without
/// holding the whole file in memory.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Content {
    /// Literal bytes.
    Bytes(Vec<u8>),
    /// `len` zero bytes (compresses to almost nothing).
    Zeros(u64),
    /// `len` pseudo-random bytes from `seed` (incompressible).
    Pattern {
        /// Generator seed.
        seed: u64,
        /// Length in bytes.
        len: u64,
    },
    /// Zeros with `noise` pseudo-random bytes at the start of every `period`.
    SparseNoise {
        /// Generator seed.
        seed: u64,
        /// Total length.
        len: u64,
        /// Distance between noise bursts.
        period: u64,
        /// Length of each burst.
        noise: u64,
    },
}

fn splitmix64(x: u64) -> u64 {
    let mut z = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

fn pattern_byte(seed: u64, pos: u64) -> u8 {
    splitmix64(seed ^ (pos / 8).wrapping_mul(0x2545_F491_4F6C_DD1D)).to_le_bytes()
        [(pos % 8) as usize]
}

impl Content {
    /// Length in bytes.
    pub fn len(&self) -> u64 {
        match self {
            Content::Bytes(v) => v.len() as u64,
            Content::Zeros(len)
            | Content::Pattern { len, .. }
            | Content::SparseNoise { len, .. } => *len,
        }
    }

    /// True when the file is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Fills `buf` with the bytes at `offset`. Bytes past the end are zero.
    pub fn fill(&self, offset: u64, buf: &mut [u8]) {
        match self {
            Content::Bytes(v) => {
                buf.fill(0);
                let start = usize::try_from(offset).unwrap_or(usize::MAX).min(v.len());
                let n = buf.len().min(v.len() - start);
                buf[..n].copy_from_slice(&v[start..start + n]);
            }
            Content::Zeros(_) => buf.fill(0),
            Content::Pattern { seed, len } => {
                for (i, b) in buf.iter_mut().enumerate() {
                    let pos = offset + i as u64;
                    *b = if pos < *len {
                        pattern_byte(*seed, pos)
                    } else {
                        0
                    };
                }
            }
            Content::SparseNoise {
                seed,
                len,
                period,
                noise,
            } => {
                for (i, b) in buf.iter_mut().enumerate() {
                    let pos = offset + i as u64;
                    *b = if pos < *len && pos % period < *noise {
                        pattern_byte(*seed, pos)
                    } else {
                        0
                    };
                }
            }
        }
    }

    /// Streams the content into `out`.
    pub fn write_to(&self, out: &mut impl Write) -> io::Result<()> {
        let mut buf = vec![0u8; 1 << 20];
        let mut off = 0u64;
        while off < self.len() {
            let n = (self.len() - off).min(buf.len() as u64) as usize;
            self.fill(off, &mut buf[..n]);
            out.write_all(&buf[..n])?;
            off += n as u64;
        }
        Ok(())
    }

    /// SHA-256 of the content.
    pub fn sha256(&self) -> [u8; 32] {
        let mut h = Sha256::new();
        let mut buf = vec![0u8; 1 << 20];
        let mut off = 0u64;
        while off < self.len() {
            let n = (self.len() - off).min(buf.len() as u64) as usize;
            self.fill(off, &mut buf[..n]);
            h.update(&buf[..n]);
            off += n as u64;
        }
        h.finalize().into()
    }
}

/// A file in the tree.
#[derive(Debug, Clone)]
pub struct FileSpec {
    /// Name (no separators).
    pub name: String,
    /// Contents.
    pub content: Content,
}

/// A directory in the tree.
#[derive(Debug, Clone, Default)]
pub struct DirSpec {
    /// Name; empty for the root.
    pub name: String,
    /// Subdirectories.
    pub dirs: Vec<DirSpec>,
    /// Files.
    pub files: Vec<FileSpec>,
}

impl DirSpec {
    /// A directory with the given name.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            ..Default::default()
        }
    }
    /// Adds a file.
    #[must_use]
    pub fn file(mut self, name: impl Into<String>, content: Content) -> Self {
        self.files.push(FileSpec {
            name: name.into(),
            content,
        });
        self
    }
    /// Adds a subdirectory.
    #[must_use]
    pub fn dir(mut self, d: DirSpec) -> Self {
        self.dirs.push(d);
        self
    }
}

/// A complete fixture description.
#[derive(Debug, Clone)]
pub struct Spec {
    /// Preset name (informational).
    pub name: String,
    /// The tree.
    pub root: DirSpec,
    /// exFAT cluster size (32 KiB or 64 KiB in real containers).
    pub cluster_size: u32,
    /// PFS block size (64 KiB in real containers).
    pub pfs_block_size: u32,
    /// Name of the inner exFAT file inside the PFS image.
    pub inner_name: String,
    /// Sets the PFS case-insensitive mode bit.
    pub case_insensitive: bool,
    /// Emit `NoFatChain` stream entries instead of FAT chains.
    pub no_fat_chain: bool,
}

impl Spec {
    /// A spec with the defaults real containers use.
    pub fn new(name: impl Into<String>, root: DirSpec) -> Self {
        Self {
            name: name.into(),
            root,
            cluster_size: 0x8000,
            pfs_block_size: 0x10000,
            inner_name: "BREW00001.exfat".into(),
            case_insensitive: true,
            no_fat_chain: false,
        }
    }

    /// Names of the built-in presets (ADR 0003).
    pub fn presets() -> &'static [&'static str] {
        &[
            "empty",
            "one-small",
            "spanning",
            "mixed-compress",
            "deep",
            "wide",
            "case",
            "contiguous",
            "noise-256m",
            "sparse-1g",
        ]
    }

    /// A built-in preset by name.
    pub fn preset(name: &str) -> Option<Spec> {
        let param = Content::Bytes(
            br#"{"titleId":"BREW00001","localizedParameters":{"defaultLanguage":"en-US","en-US":{"titleName":"BC5 fixture"}}}"#.to_vec(),
        );
        let spec = match name {
            "empty" => Spec::new(name, DirSpec::new("")),
            "one-small" => Spec::new(
                name,
                DirSpec::new("").file("a.txt", Content::Bytes(b"hello, bc5!\n".to_vec())),
            ),
            "spanning" => Spec::new(
                name,
                DirSpec::new("").file(
                    "big.bin",
                    Content::Pattern {
                        seed: 1,
                        len: 200 * 1024 + 1,
                    },
                ),
            ),
            "mixed-compress" => Spec::new(
                name,
                DirSpec::new("")
                    .file("zeros.bin", Content::Zeros(256 * 1024))
                    .file(
                        "noise.bin",
                        Content::Pattern {
                            seed: 2,
                            len: 256 * 1024,
                        },
                    )
                    .file("tail.bin", Content::Zeros(70_000)),
            ),
            "deep" => {
                let long_name = format!("{}.dat", "n".repeat(196));
                let mut dir =
                    DirSpec::new("level8").file(&long_name, Content::Pattern { seed: 8, len: 300 });
                for level in (1u64..8).rev() {
                    dir = DirSpec::new(format!("level{level}"))
                        .file(
                            format!("f{level}.bin"),
                            Content::Pattern {
                                seed: level,
                                len: level * 1000,
                            },
                        )
                        .dir(dir);
                }
                Spec::new(
                    name,
                    DirSpec::new("")
                        .dir(dir)
                        .file("root.txt", Content::Bytes(b"root\n".to_vec())),
                )
            }
            "wide" => {
                let mut root = DirSpec::new("wide");
                for i in 0..600 {
                    root = root.file(
                        format!("file-{i:04}.txt"),
                        Content::Pattern {
                            seed: 1000 + i,
                            len: 40 + i,
                        },
                    );
                }
                Spec::new(name, DirSpec::new("").dir(root))
            }
            "case" => Spec::new(
                name,
                DirSpec::new("")
                    .dir(DirSpec::new("sce_sys").file("param.json", param))
                    .file(
                        "eboot.bin",
                        Content::Pattern {
                            seed: 77,
                            len: 4096,
                        },
                    ),
            ),
            "contiguous" => {
                let mut s = Spec::new(
                    name,
                    DirSpec::new("")
                        .file("a.txt", Content::Bytes(b"contiguous\n".to_vec()))
                        .file(
                            "big.bin",
                            Content::Pattern {
                                seed: 3,
                                len: 150 * 1024,
                            },
                        )
                        .dir(DirSpec::new("d").file("empty.bin", Content::Zeros(0))),
                );
                s.no_fat_chain = true;
                s.cluster_size = 0x10000;
                s
            }
            // Worst case for throughput: every PFSC block is stored raw.
            "noise-256m" => {
                let mut s = Spec::new(
                    name,
                    DirSpec::new("").file(
                        "noise.bin",
                        Content::Pattern {
                            seed: 256,
                            len: 256 << 20,
                        },
                    ),
                );
                s.cluster_size = 0x10000;
                s
            }
            "sparse-1g" => {
                let mut s = Spec::new(
                    name,
                    DirSpec::new("").file(
                        "sparse.bin",
                        Content::SparseNoise {
                            seed: 9,
                            len: 1 << 30,
                            period: 64 << 20,
                            noise: 1024,
                        },
                    ),
                );
                s.cluster_size = 0x10000;
                s
            }
            _ => return None,
        };
        Some(spec)
    }

    /// Every file as `(path, content)`, depth-first in the writer's order.
    pub fn files(&self) -> Vec<(String, &Content)> {
        fn walk<'a>(d: &'a DirSpec, prefix: &str, out: &mut Vec<(String, &'a Content)>) {
            for f in &d.files {
                out.push((join(prefix, &f.name), &f.content));
            }
            for sub in &d.dirs {
                walk(sub, &join(prefix, &sub.name), out);
            }
        }
        let mut out = Vec::new();
        walk(&self.root, "", &mut out);
        out
    }

    /// Every directory path (excluding the root).
    pub fn dirs(&self) -> Vec<String> {
        fn walk(d: &DirSpec, prefix: &str, out: &mut Vec<String>) {
            for sub in &d.dirs {
                let p = join(prefix, &sub.name);
                out.push(p.clone());
                walk(sub, &p, out);
            }
        }
        let mut out = Vec::new();
        walk(&self.root, "", &mut out);
        out
    }

    /// Writes the tree as plain files under `dir`.
    pub fn materialize(&self, dir: &Path) -> io::Result<()> {
        fs::create_dir_all(dir)?;
        for d in self.dirs() {
            fs::create_dir_all(dir.join(d))?;
        }
        for (path, content) in self.files() {
            let mut f = fs::File::create(dir.join(path))?;
            content.write_to(&mut f)?;
        }
        Ok(())
    }

    /// `(path, size, sha256)` for every file, sorted by path.
    pub fn expected_hashes(&self) -> Vec<(String, u64, [u8; 32])> {
        let mut v: Vec<_> = self
            .files()
            .into_iter()
            .map(|(p, c)| (p, c.len(), c.sha256()))
            .collect();
        v.sort_by(|a, b| a.0.cmp(&b.0));
        v
    }
}

fn join(prefix: &str, name: &str) -> String {
    if prefix.is_empty() {
        name.to_string()
    } else {
        format!("{prefix}/{name}")
    }
}

/// Writes `n` zero bytes.
pub(crate) fn write_zeros(out: &mut impl Write, mut n: u64) -> io::Result<()> {
    static ZEROS: [u8; 1 << 16] = [0; 1 << 16];
    while n > 0 {
        let k = n.min(ZEROS.len() as u64) as usize;
        out.write_all(&ZEROS[..k])?;
        n -= k as u64;
    }
    Ok(())
}

/// What [`build`] produced.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BuildInfo {
    /// Container length in bytes.
    pub container_len: u64,
    /// Decoded exFAT image length.
    pub exfat_len: u64,
    /// PFSC stream length on disk.
    pub pfsc_stored_len: u64,
    /// Number of PFSC blocks.
    pub pfsc_blocks: u64,
    /// Blocks stored zlib-compressed.
    pub compressed_blocks: u64,
    /// exFAT cluster size.
    pub cluster_size: u32,
    /// Files in the tree.
    pub file_count: usize,
    /// Directories in the tree (excluding the root).
    pub dir_count: usize,
}

/// Builds the container into any seekable sink.
pub fn build<W: Write + Seek>(spec: &Spec, out: &mut W) -> Result<BuildInfo> {
    pfs_writer::write_container(spec, out)
}

/// Builds the container into a file (created or truncated).
pub fn build_to_path(spec: &Spec, path: &Path) -> Result<BuildInfo> {
    let mut f = io::BufWriter::new(fs::File::create(path)?);
    let info = build(spec, &mut f)?;
    f.flush()?;
    Ok(info)
}

/// Builds the container in memory.
pub fn build_in_memory(spec: &Spec) -> Result<(Vec<u8>, BuildInfo)> {
    let mut cur = Cursor::new(Vec::new());
    let info = build(spec, &mut cur)?;
    Ok((cur.into_inner(), info))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_is_deterministic_and_random_access() {
        let c = Content::Pattern { seed: 5, len: 1000 };
        let mut whole = vec![0u8; 1000];
        c.fill(0, &mut whole);
        let mut part = vec![0u8; 100];
        c.fill(450, &mut part);
        assert_eq!(&whole[450..550], &part[..]);
        assert_ne!(&whole[..100], &whole[100..200]);
        let mut past = [7u8; 4];
        c.fill(998, &mut past);
        assert_eq!(past[2..], [0, 0]);
        let s = Content::SparseNoise {
            seed: 1,
            len: 100,
            period: 40,
            noise: 3,
        };
        let mut b = vec![0u8; 100];
        s.fill(0, &mut b);
        assert!(b[3..40].iter().all(|&x| x == 0));
        assert!(b[40..43].iter().any(|&x| x != 0));
    }

    #[test]
    fn presets_resolve_and_list_files() {
        for name in Spec::presets() {
            let s = Spec::preset(name).unwrap();
            assert_eq!(s.name, *name);
        }
        assert!(Spec::preset("nope").is_none());
        let deep = Spec::preset("deep").unwrap();
        assert_eq!(deep.dirs().len(), 8);
        assert_eq!(deep.files().len(), 9);
        assert_eq!(Spec::preset("wide").unwrap().files().len(), 600);
    }
}
