// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-agc` command line: dump a capture packet by packet, or report opcode
//! and register statistics over many captures.

use std::fs;
use std::path::PathBuf;

use anyhow::{bail, Context};
use clap::{Parser, Subcommand};

use bc5_agc::decode::{events, format_event, Report};
use bc5_agc::pm4::{dwords_from_hex_text, dwords_from_le_bytes, parse};
use bc5_agc::regdb::RegDb;

#[derive(Parser, Debug)]
#[command(name = "bc5-agc", version, about = "PM4/AGC command-stream decoder")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Print every packet of one capture.
    Dump {
        /// Raw little-endian dwords, or hex text with --hex.
        file: PathBuf,
        /// Parse the file as whitespace-separated hex words.
        #[arg(long)]
        hex: bool,
        /// Stop after this many packets.
        #[arg(long)]
        limit: Option<usize>,
    },
    /// Count opcodes, register writes and unresolved offsets over captures.
    Report {
        /// Capture files.
        files: Vec<PathBuf>,
        /// Parse the files as hex text.
        #[arg(long)]
        hex: bool,
    },
    /// Show table sizes and look up a register or opcode.
    Tables {
        /// Register name, `mm:<hex offset>` or `op:<hex opcode>`.
        query: Option<String>,
    },
}

fn load(path: &PathBuf, hex: bool) -> anyhow::Result<Vec<u32>> {
    let bytes = fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    if hex {
        dwords_from_hex_text(&String::from_utf8_lossy(&bytes)).map_err(anyhow::Error::msg)
    } else {
        let (words, trailing) = dwords_from_le_bytes(&bytes);
        if trailing != 0 {
            eprintln!("{}: {trailing} trailing byte(s) ignored", path.display());
        }
        Ok(words)
    }
}

fn main() -> anyhow::Result<()> {
    match Cli::parse().cmd {
        Cmd::Dump { file, hex, limit } => {
            let words = load(&file, hex)?;
            let parsed = parse(&words);
            let ev = events(&parsed);
            for (i, e) in ev.iter().enumerate() {
                if limit.is_some_and(|l| i >= l) {
                    println!("… {} more", ev.len() - i);
                    break;
                }
                println!("{}", format_event(e));
            }
            if let Some(err) = parsed.error {
                bail!("stream stopped: {err}");
            }
        }
        Cmd::Report { files, hex } => {
            if files.is_empty() {
                bail!("no capture files given");
            }
            let mut report = Report::default();
            for f in &files {
                let words = load(f, hex)?;
                report.add(&f.display().to_string(), &parse(&words));
            }
            print!("{}", report.render());
        }
        Cmd::Tables { query } => {
            let db = RegDb::get();
            println!(
                "registers: {}  opcodes: {}",
                db.register_count(),
                db.opcode_count()
            );
            if let Some(q) = query {
                if let Some(op) = q.strip_prefix("op:") {
                    let op = u8::from_str_radix(op.trim_start_matches("0x"), 16)?;
                    println!("{op:#04x} = {}", db.opcode_name(op).unwrap_or("(unknown)"));
                } else if let Some(mm) = q.strip_prefix("mm:") {
                    let mm = u32::from_str_radix(mm.trim_start_matches("0x"), 16)?;
                    println!(
                        "mm {mm:#07x} = {}",
                        db.register_name(mm).unwrap_or("(unknown)")
                    );
                } else {
                    match db.register_offset(&q) {
                        Some(mm) => println!("{q} = mm {mm:#07x}"),
                        None => bail!("unknown register {q}"),
                    }
                }
            }
        }
    }
    Ok(())
}
