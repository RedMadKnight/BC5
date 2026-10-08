// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount` command line: inspect, verify, ls, cat and (on Linux) mount a
//! `.ffpfsc` container or a PS5 package (`.pkg`), told apart by their magic.

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
}

fn main() -> anyhow::Result<()> {
    match run() {
        // `ls | head`: the reader closed the pipe; nothing went wrong.
        Err(e)
            if e.downcast_ref::<io::Error>()
                .is_some_and(|e| e.kind() == io::ErrorKind::BrokenPipe) =>
        {
            Ok(())
        }
        r => r,
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
