// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-fixture`: build synthetic `.ffpfsc` containers and their source trees.

use std::path::PathBuf;

use anyhow::Context;
use clap::{Parser, Subcommand};

use bc5_mount::fixture::{build_to_path, Spec};

#[derive(Parser, Debug)]
#[command(
    name = "bc5-fixture",
    version,
    about = "Synthetic .ffpfsc fixtures for bc5-mount tests"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// List the built-in presets.
    List,
    /// Build a preset into a container file.
    Build {
        /// Preset name (see `list`).
        preset: String,
        /// Output .ffpfsc path (overwritten).
        out: PathBuf,
    },
    /// Write a preset's source tree as plain files.
    Tree {
        /// Preset name.
        preset: String,
        /// Output directory (created).
        dir: PathBuf,
    },
    /// Print the expected `sha256  size  path` lines for a preset.
    Hashes {
        /// Preset name.
        preset: String,
    },
}

fn spec(name: &str) -> anyhow::Result<Spec> {
    Spec::preset(name).with_context(|| format!("unknown preset {name:?}; see `bc5-fixture list`"))
}

fn main() -> anyhow::Result<()> {
    match Cli::parse().cmd {
        Cmd::List => {
            for p in Spec::presets() {
                let s = Spec::preset(p).context("preset table is inconsistent")?;
                let bytes: u64 = s.files().iter().map(|(_, c)| c.len()).sum();
                println!(
                    "{p:<16} {:>4} files {:>4} dirs {bytes:>12} bytes",
                    s.files().len(),
                    s.dirs().len()
                );
            }
        }
        Cmd::Build { preset, out } => {
            let info = build_to_path(&spec(&preset)?, &out)
                .with_context(|| format!("building {}", out.display()))?;
            println!(
                "{}: {} bytes container, {} bytes exfat, {} pfsc blocks ({} compressed), {} files, {} dirs",
                out.display(),
                info.container_len,
                info.exfat_len,
                info.pfsc_blocks,
                info.compressed_blocks,
                info.file_count,
                info.dir_count
            );
        }
        Cmd::Tree { preset, dir } => {
            spec(&preset)?
                .materialize(&dir)
                .with_context(|| format!("writing {}", dir.display()))?;
        }
        Cmd::Hashes { preset } => {
            for (path, size, sha) in spec(&preset)?.expected_hashes() {
                println!("{}  {size:>12}  {path}", bc5_mount::verify::hex(&sha));
            }
        }
    }
    Ok(())
}
