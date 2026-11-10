// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount` command line: inspect, verify, ls, cat and (on Linux) mount a
//! `.ffpfsc` container or a PS5 package (`.pkg`), told apart by their magic.

use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context};
use clap::{Parser, Subcommand};

use bc5_mount::container::Container;
use bc5_mount::io::{FileSource, ReadAt};
use bc5_mount::pkg::{self, PkgImage};
use bc5_mount::tree::{FileTree, TreeFile};
use bc5_mount::verify::hash_volume;

#[derive(Parser, Debug)]
#[command(
    name = "bc5-mount",
    version,
    about = "Read-only access to .ffpfsc containers and PS5 packages"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Print the container's or package's structure and title metadata.
    Inspect {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
    },
    /// Print `sha256  size  path` for every file.
    Verify {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
    },
    /// List a directory inside the container or package.
    Ls {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
        /// Directory inside (default: root).
        path: Option<String>,
        /// Recurse into subdirectories.
        #[arg(short, long)]
        recursive: bool,
    },
    /// Write one file to stdout.
    Cat {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
        /// File inside.
        path: String,
    },
    /// Mount read-only with FUSE (Linux only).
    Mount {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
        /// Empty directory to mount on.
        mountpoint: PathBuf,
        /// Allow other users to access the mount (needs `user_allow_other` in fuse.conf).
        #[arg(long)]
        allow_other: bool,
    },
    /// Install (unpack) the container or package into a directory.
    Install {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
        /// Destination directory.
        dest: PathBuf,
        /// Resume: skip files whose size already matches.
        #[arg(long)]
        resume: bool,
        /// Verify: compare sha256 of every written file with the image.
        #[arg(long)]
        verify: bool,
    },
    /// Adopt an already-unpacked directory: verify sizes and optionally sha256, write .bc5-install.json.
    Adopt {
        /// Path to the .ffpfsc or .pkg file.
        container: PathBuf,
        /// Destination directory (must already exist).
        dest: PathBuf,
        /// Verify: compare sha256 of every file in the directory with the image.
        #[arg(long)]
        verify: bool,
    },
}

fn main() {
    if let Err(e) = run() {
        if e.downcast_ref::<std::io::Error>()
            .is_some_and(|e| e.kind() == std::io::ErrorKind::BrokenPipe)
        {
            std::process::exit(0);
        }
        if e.to_string().contains("destination") && e.to_string().contains("already exists") {
            eprintln!("bc5-mount: {} already exists (use --resume)", e.to_string().replace("destination ", "").replace(" (use --resume to skip matching files)", ""));
            std::process::exit(2);
        }
        eprintln!("bc5-mount: {e}");
        std::process::exit(1);
    }
}

fn run() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Inspect { container } => inspect(&container),
        Cmd::Verify { container } => verify(&container),
        Cmd::Ls {
            container,
            path,
            recursive,
        } => ls(&container, path.as_deref().unwrap_or(""), recursive),
        Cmd::Cat { container, path } => cat(&container, &path),
        Cmd::Mount {
            container,
            mountpoint,
            allow_other,
        } => mount(&container, &mountpoint, allow_other),
        Cmd::Install {
            container,
            dest,
            resume,
            verify,
        } => install(&container, &dest, resume, verify),
        Cmd::Adopt {
            container,
            dest,
            verify,
        } => adopt(&container, &dest, verify),
    }
}

/// Whichever of the two formats the file is.
enum Opened {
    Ffpfsc(Box<Container<FileSource>>),
    Pkg(Box<PkgImage<FileSource>>),
}

impl Opened {
    fn tree(&self) -> &dyn FileTree {
        match self {
            Opened::Ffpfsc(c) => c.as_ref(),
            Opened::Pkg(p) => p.as_ref(),
        }
    }
}

fn open(path: &PathBuf) -> anyhow::Result<Opened> {
    let mut head = [0u8; 4];
    let n = std::fs::File::open(path)
        .and_then(|mut f| f.read(&mut head))
        .with_context(|| format!("opening {}", path.display()))?;
    if pkg::is_package(&head[..n]) {
        PkgImage::open_path(path)
            .map(|p| Opened::Pkg(Box::new(p)))
            .with_context(|| format!("opening the package {}", path.display()))
    } else {
        Container::open_path(path)
            .map(|c| Opened::Ffpfsc(Box::new(c)))
            .with_context(|| format!("opening {}", path.display()))
    }
}

#[allow(clippy::cast_precision_loss)] // ratio display only
fn inspect(path: &PathBuf) -> anyhow::Result<()> {
    match open(path)? {
        Opened::Ffpfsc(c) => inspect_container(path, &c),
        Opened::Pkg(p) => {
            inspect_pkg(path, &p);
            Ok(())
        }
    }
}

#[allow(clippy::cast_precision_loss)] // ratio display only
fn inspect_container(path: &Path, c: &Container<FileSource>) -> anyhow::Result<()> {
    let info = c.info()?;
    let sb = &info.superblock;
    println!("container:        {}", path.display());
    println!(
        "pfs version:      {}  mode {:#x}{}",
        sb.version,
        sb.mode,
        if sb.is_case_insensitive() {
            " (case-insensitive)"
        } else {
            ""
        }
    );
    println!(
        "pfs block size:   {:#x}  blocks {}  inodes {}",
        sb.block_size, sb.ndblock, sb.ndinode
    );
    println!("inner file:       {}", info.inner_name);
    println!("payload offset:   {:#x}", info.payload_offset);
    println!(
        "pfsc stored:      {} bytes in {} blocks ({} compressed)",
        info.stored_len, info.pfsc_blocks, info.compressed_blocks
    );
    println!(
        "exfat image:      {} bytes, cluster {:#x}",
        info.logical_len, info.cluster_size
    );
    let ratio = if info.logical_len == 0 {
        0.0
    } else {
        info.stored_len as f64 / info.logical_len as f64
    };
    println!("ratio:            {ratio:.3} stored/logical");
    println!(
        "files:            {}  in {} directories, {} bytes",
        info.file_count, info.dir_count, info.total_file_bytes
    );
    match info.title {
        Some(t) => {
            println!("title id:         {}", t.title_id.as_deref().unwrap_or("-"));
            println!(
                "title name:       {}",
                t.title_name.as_deref().unwrap_or("-")
            );
        }
        None => println!("title:            (no sce_sys/param.json)"),
    }
    Ok(())
}

#[allow(clippy::cast_precision_loss)] // ratio display only
fn inspect_pkg(path: &Path, p: &PkgImage<FileSource>) {
    let info = p.info();
    let h = &info.header;
    println!("package:          {}", path.display());
    println!(
        "image:            {}",
        if h.signed_byte == 0x80 {
            "retail"
        } else {
            "debug"
        }
    );
    println!(
        "content id:       {}",
        info.content_id.as_deref().unwrap_or("-")
    );
    println!(
        "title id:         {}{}",
        info.content_id
            .as_deref()
            .and_then(pkg::title_id_from_content_id)
            .unwrap_or("-"),
        if p.param_json_synthesised() {
            " (sce_sys/param.json synthesised from the content id)"
        } else {
            ""
        }
    );
    let from_cnt = p.container_files();
    println!(
        "cnt files:        {} shown under sce_sys{}",
        from_cnt.len(),
        if from_cnt.is_empty() {
            String::new()
        } else {
            format!(" ({})", from_cnt.join(", "))
        }
    );
    println!(
        "outer pfs:        at {:#x}, {} bytes, superblock at {:#x}, mode {:#x}, {} inodes",
        h.pfs_offset, h.pfs_size, h.superblock_offset, info.outer_mode, info.outer_inodes
    );
    println!(
        "inner image:      {} bytes stored, {} bytes logical, layout {} bytes",
        info.image_stored_len, info.image_logical_len, info.layout_len
    );
    println!(
        "blocks:           {} ({} kraken, {} stored, {} sparse)",
        info.blocks, info.stats.kraken, info.stats.stored, info.stats.sparse
    );
    let ratio = if info.image_logical_len == 0 {
        0.0
    } else {
        info.image_stored_len as f64 / info.image_logical_len as f64
    };
    println!("ratio:            {ratio:.3} stored/logical");
    let (bs, inodes, mode) = info.inner_superblock;
    println!(
        "inner pfs:        superblock at logical {:#x}, block size {bs:#x}, {inodes} inodes, mode {mode:#x}",
        info.inner_superblock_offset
    );
    println!(
        "files:            {}  in {} directories, {} bytes",
        info.file_count, info.dir_count, info.total_file_bytes
    );
}

fn verify(path: &PathBuf) -> anyhow::Result<()> {
    let opened = open(path)?;
    let hashes = hash_volume(opened.tree(), |_| {})?;
    let out = io::stdout();
    let mut out = out.lock();
    for h in &hashes {
        writeln!(out, "{}  {:>12}  {}", h.hex(), h.size, h.path)?;
    }
    Ok(())
}

fn ls(path: &PathBuf, dir: &str, recursive: bool) -> anyhow::Result<()> {
    let opened = open(path)?;
    let tree = opened.tree();
    let idx = tree
        .find(dir)
        .with_context(|| format!("no such directory: {dir}"))?;
    let entry = tree.entry(idx).context("entry vanished")?;
    if !entry.is_dir {
        bail!("{dir} is a file");
    }
    let out = io::stdout();
    let mut out = out.lock();
    let mut stack = vec![idx];
    while let Some(d) = stack.pop() {
        let mut kids: Vec<usize> = tree.children(d).to_vec();
        kids.sort_by(|&a, &b| {
            let na = tree.entry(a).map(|e| e.name.to_owned()).unwrap_or_default();
            let nb = tree.entry(b).map(|e| e.name.to_owned()).unwrap_or_default();
            na.cmp(&nb)
        });
        for k in kids {
            let Some(e) = tree.entry(k) else {
                continue;
            };
            writeln!(
                out,
                "{} {:>12}  {}",
                if e.is_dir { "d" } else { "-" },
                e.size,
                e.path
            )?;
            if recursive && e.is_dir {
                stack.push(k);
            }
        }
    }
    Ok(())
}

fn cat(path: &PathBuf, file: &str) -> anyhow::Result<()> {
    let opened = open(path)?;
    let tree = opened.tree();
    let idx = tree
        .find(file)
        .with_context(|| format!("no such file: {file}"))?;
    let f = TreeFile::new(tree, idx)?;
    let out = io::stdout();
    let mut out = out.lock();
    let mut buf = vec![0u8; 1 << 20];
    let mut off = 0u64;
    while off < f.len() {
        let n = f.read_at(off, &mut buf)?;
        if n == 0 {
            break;
        }
        out.write_all(&buf[..n])?;
        off += n as u64;
    }
    Ok(())
}

#[cfg(all(feature = "fuse", target_os = "linux"))]
fn mount(path: &PathBuf, mountpoint: &Path, allow_other: bool) -> anyhow::Result<()> {
    // ADR 0014: with BC5_MOUNT_PRELOAD set, the traced startup ranges are read
    // into the page cache in the background while the mount comes up.
    bc5_mount::preload::start_from_env(path);
    let r = match open(path)? {
        Opened::Ffpfsc(c) => bc5_mount::fuse::mount(*c, "ffpfsc", mountpoint, allow_other),
        Opened::Pkg(p) => bc5_mount::fuse::mount(*p, "pkg", mountpoint, allow_other),
    };
    r.with_context(|| format!("mounting on {}", mountpoint.display()))
}

#[cfg(not(all(feature = "fuse", target_os = "linux")))]
fn mount(_path: &PathBuf, _mountpoint: &Path, _allow_other: bool) -> anyhow::Result<()> {
    bail!("mount is only available on Linux builds with the `fuse` feature; use ls/cat/verify here")
}

fn install(
    path: &PathBuf,
    dest: &Path,
    resume: bool,
    verify: bool,
) -> anyhow::Result<()> {
    let info = bc5_mount::install::install(path, dest, resume, verify)
        .with_context(|| format!("installing {}", path.display()))?;
    println!(
        "installed {} files, {} bytes to {}",
        info.file_count,
        info.total_bytes,
        dest.display()
    );
    if verify {
        println!("verification passed");
        bc5_mount::install::write_install_json(dest, path, &info)
            .with_context(|| "writing .bc5-install.json")?;
    }
    Ok(())
}

/// Adopt an already-unpacked directory: verify sizes against the image, optionally sha256, write .bc5-install.json.
fn adopt(path: &PathBuf, dest: &Path, verify: bool) -> anyhow::Result<()> {
    if !dest.exists() {
        bail!("destination {} does not exist", dest.display());
    }
    let opened = bc5_mount::install::OpenedImage::open(path)?;
    let tree = opened.tree();

    // Collect files from the image.
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

    // Verify sizes first.
    let mut size_mismatches = Vec::new();
    for (_idx, rel_path, img_size) in &files {
        let file_path = dest.join(rel_path);
        match fs::metadata(&file_path) {
            Ok(meta) => {
                if meta.len() != *img_size {
                    size_mismatches.push(format!("{}: {} bytes on disk vs {} bytes in image", rel_path, meta.len(), img_size));
                }
            }
            Err(e) => {
                size_mismatches.push(format!("{}: {}", rel_path, e));
            }
        }
    }

    if !size_mismatches.is_empty() {
        bail!("size mismatches (use `install` to copy):\n  {}", size_mismatches.join("\n  "));
    }

    // Optionally verify sha256.
    if verify {
        let disk_hashes = bc5_mount::verify::hash_directory(dest)
            .with_context(|| "hashing directory")?;
        let image_hashes = bc5_mount::verify::hash_volume(tree, |_| {})
            .with_context(|| "hashing image")?;
        let diffs = bc5_mount::verify::diff(&image_hashes, &disk_hashes);
        if !diffs.is_empty() {
            bail!("verification failed: {}", diffs.join(", "));
        }
        println!("verification passed");
    }

    // Build InstallInfo from what we have.
    let file_count = files.len();
    let total_bytes: u64 = files.iter().map(|f| f.2).sum();
    let hashes = bc5_mount::verify::hash_directory(dest)
        .with_context(|| "hashing directory for json")?;

    let info = bc5_mount::install::InstallInfo {
        file_count,
        total_bytes,
        hashes,
    };

    bc5_mount::install::write_install_json(dest, path, &info)
        .with_context(|| "writing .bc5-install.json")?;

    println!("adopted {} files, {} bytes from {}", file_count, total_bytes, path.display());
    Ok(())
}
