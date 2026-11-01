// SPDX-License-Identifier: GPL-2.0-only
//! Every request the kernel sends the mount, one line each (exp 0381). With
//! `BC5_MOUNT_READ_TRACE=<file>` the re-reads can be replayed offline, per page and
//! per caller, and a dropped inode shows as a `forget` line. Off by default.
//!
//! Lines, time in seconds since the mount:
//! `R <t> <ino> <offset> <len> <pid>`, `O <t> <ino> <pid>`, `F <t> <ino> <nlookup>`.

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;
use std::time::Instant;

/// Where writing stops: a run sends about a million requests.
const LIMIT: u64 = 256 << 20;
const BUFFER: usize = 1 << 20;

/// The trace of one mount.
#[derive(Debug)]
pub struct ReadTrace<W: Write> {
    out: BufWriter<W>,
    start: Instant,
    last_flush: f64,
    written: u64,
    limit: u64,
}

impl ReadTrace<File> {
    /// The trace named by `BC5_MOUNT_READ_TRACE`, if any.
    pub fn from_env() -> Option<Self> {
        let path = std::env::var_os("BC5_MOUNT_READ_TRACE").filter(|p| !p.is_empty())?;
        match Self::create(Path::new(&path)) {
            Ok(t) => Some(t),
            Err(e) => {
                eprintln!("bc5-mount: no read trace: {e}");
                None
            }
        }
    }

    fn create(path: &Path) -> io::Result<Self> {
        Ok(Self::new(File::create(path)?, LIMIT))
    }
}

impl<W: Write> ReadTrace<W> {
    fn new(out: W, limit: u64) -> Self {
        Self {
            out: BufWriter::with_capacity(BUFFER, out),
            start: Instant::now(),
            last_flush: 0.0,
            written: 0,
            limit,
        }
    }

    fn line(&mut self, text: std::fmt::Arguments<'_>, t: f64) {
        if self.written >= self.limit {
            return;
        }
        let text = text.to_string();
        // A trace is only a measurement: a failed write loses lines, not the read.
        let _ = self.out.write_all(text.as_bytes());
        self.written += text.len() as u64;
        if t - self.last_flush >= 1.0 {
            self.last_flush = t;
            let _ = self.out.flush();
        }
    }

    /// A read of `len` bytes at `offset`, asked by process `pid`.
    pub fn read(&mut self, ino: u64, offset: u64, len: u64, pid: u32) {
        let t = self.start.elapsed().as_secs_f64();
        self.line(format_args!("R {t:.4} {ino} {offset} {len} {pid}\n"), t);
    }

    /// An open by process `pid`.
    pub fn open(&mut self, ino: u64, pid: u32) {
        let t = self.start.elapsed().as_secs_f64();
        self.line(format_args!("O {t:.4} {ino} {pid}\n"), t);
    }

    /// The kernel dropped `nlookup` references to the inode.
    pub fn forget(&mut self, ino: u64, nlookup: u64) {
        let t = self.start.elapsed().as_secs_f64();
        self.line(format_args!("F {t:.4} {ino} {nlookup}\n"), t);
    }

    /// The writer, after the buffer went out.
    #[cfg(test)]
    fn finish(mut self) -> W
    where
        W: std::fmt::Debug,
    {
        self.out.flush().expect("flush");
        self.out.into_inner().expect("buffer")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn without_time(text: &str) -> Vec<String> {
        text.lines()
            .map(|l| {
                let mut f: Vec<&str> = l.split(' ').collect();
                f.remove(1);
                f.join(" ")
            })
            .collect()
    }

    #[test]
    fn each_kind_writes_one_line() {
        let mut t = ReadTrace::new(Vec::new(), 1 << 20);
        t.read(7, 4096, 131072, 42);
        t.open(7, 42);
        t.forget(7, 3);
        let text = String::from_utf8(t.finish()).expect("text");
        assert_eq!(
            without_time(&text),
            ["R 7 4096 131072 42", "O 7 42", "F 7 3"]
        );
    }

    #[test]
    fn writing_stops_at_the_limit() {
        let mut t = ReadTrace::new(Vec::new(), 10);
        t.read(1, 0, 1, 1);
        t.read(2, 0, 1, 1);
        let text = String::from_utf8(t.finish()).expect("text");
        assert_eq!(text.lines().count(), 1);
    }

    #[test]
    fn a_trace_goes_to_its_file() {
        let path = std::env::temp_dir().join(format!("bc5-trace-{}", std::process::id()));
        let mut t = ReadTrace::create(&path).expect("create");
        t.read(1, 0, 1, 1);
        drop(t);
        let text = std::fs::read_to_string(&path).expect("read");
        std::fs::remove_file(&path).expect("remove");
        assert!(text.starts_with("R "));
    }
}
