// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount` command line: inspect, verify, ls, cat and (on Linux) mount.

use std::io::{self, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context};
use clap::{Parser, Subcommand};

use bc5_mount::container::Container;
use bc5_mount::io::ReadAt;
use bc5_mount::verify::hash_volume;

#[derive(Parser, Debug)]
#[command(
    name = "bc5-mount",
    version,
    about = "Read-only access to .ffpfsc containers"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Print the container's structure and title metadata.
    Inspect {
        /// Path to the .ffpfsc file.
        container: PathBuf,
    },
    /// Print `sha256  size  path` for every file.
    Verify {
        /// Path to the .ffpfsc file.
        container: PathBuf,
    },
    /// List a directory inside the container.
    Ls {
        /// Path to the .ffpfsc file.
        container: PathBuf,
        /// Directory inside the container (default: root).
        path: Option<String>,
        /// Recurse into subdirectories.
        #[arg(short, long)]
        recursive: bool,
    },
    /// Write one file from the container to stdout.
    Cat {
        /// Path to the .ffpfsc file.
        container: PathBuf,
        /// File inside the container.
        path: String,
    },
    /// Mount the container read-only with FUSE (Linux only).
    Mount {
        /// Path to the .ffpfsc file.
        container: PathBuf,
        /// Empty directory to mount on.
        mountpoint: PathBuf,
        /// Allow other users to access the mount (needs `user_allow_other` in fuse.conf).
        #[arg(long)]
        allow_other: bool,
    },
}

fn main() -> anyhow::Result<()> {
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

fn open(path: &PathBuf) -> anyhow::Result<Container<bc5_mount::io::FileSource>> {
    Container::open_path(path).with_context(|| format!("opening {}", path.display()))
}

#[allow(clippy::cast_precision_loss)] // ratio display only
fn inspect(path: &PathBuf) -> anyhow::Result<()> {
    let c = open(path)?;
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

fn verify(path: &PathBuf) -> anyhow::Result<()> {
    let c = open(path)?;
    let hashes = hash_volume(c.exfat(), |_| {})?;
    let out = io::stdout();
    let mut out = out.lock();
    for h in &hashes {
        writeln!(out, "{}  {:>12}  {}", h.hex(), h.size, h.path)?;
    }
    Ok(())
}

fn ls(path: &PathBuf, dir: &str, recursive: bool) -> anyhow::Result<()> {
    let c = open(path)?;
    let vol = c.exfat();
    let idx = vol
        .find(dir)
        .with_context(|| format!("no such directory: {dir}"))?;
    let entry = vol.entry(idx).context("entry vanished")?;
    if !entry.is_dir {
        bail!("{dir} is a file");
    }
    let mut stack = vec![idx];
    while let Some(d) = stack.pop() {
        let mut kids: Vec<usize> = vol.children(d).to_vec();
        kids.sort_by(|&a, &b| vol.entries()[a].name.cmp(&vol.entries()[b].name));
        for k in kids {
            let e = &vol.entries()[k];
            println!(
                "{} {:>12}  {}",
                if e.is_dir { "d" } else { "-" },
                e.size,
                e.path
            );
            if recursive && e.is_dir {
                stack.push(k);
            }
        }
    }
    Ok(())
}

fn cat(path: &PathBuf, file: &str) -> anyhow::Result<()> {
    let c = open(path)?;
    let vol = c.exfat();
    let idx = vol
        .find(file)
        .with_context(|| format!("no such file: {file}"))?;
    let f = vol.file(idx)?;
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
    let c = open(path)?;
    bc5_mount::fuse::mount(c, mountpoint, allow_other)
        .with_context(|| format!("mounting on {}", mountpoint.display()))
}

#[cfg(not(all(feature = "fuse", target_os = "linux")))]
fn mount(_path: &PathBuf, _mountpoint: &Path, _allow_other: bool) -> anyhow::Result<()> {
    bail!("mount is only available on Linux builds with the `fuse` feature; use ls/cat/verify here")
}
