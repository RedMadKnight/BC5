// SPDX-License-Identifier: GPL-2.0-only
//! Record a title's startup reads of the image once, preload them at every
//! mount (ADR 0014, experiments 0227/0228).
//!
//! A title's start is thousands of small reads of the image issued one after
//! another, so it is bound by the drive's latency whenever the page cache does
//! not hold them. With `BC5_MOUNT_TRACE=<file>` every read a [`FileSource`]
//! makes during the first `BC5_MOUNT_TRACE_SECS` (default 120) seconds is
//! appended to `<file>` as `<ms since the first read> <offset> <length>`. With
//! `BC5_MOUNT_PRELOAD=<file>` (such a trace) the mount starts a background
//! thread that reads the traced ranges, merged into large chunks and ordered by
//! their first use, through its own handle on the image: the page cache then
//! answers the title's reads. The preload never serves data itself, so a stale
//! list costs I/O only.
//!
//! [`FileSource`]: crate::io::FileSource

use std::fs::{File, OpenOptions};
use std::io::{self, BufWriter, Write};
use std::path::Path;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use crate::io::{FileSource, ReadAt};

/// Ranges closer than this are read as one (an SSD reads a small gap faster
/// than it serves a second request).
pub const MERGE_GAP: u64 = 1 << 20;
/// Largest single preload read; longer merged ranges are split.
pub const MAX_CHUNK: u64 = 8 << 20;
/// Default trace window in seconds (`BC5_MOUNT_TRACE_SECS`).
pub const DEFAULT_TRACE_SECS: u64 = 120;

/// Appends read records to a writer during a time window.
#[derive(Debug)]
pub struct Tracer<W: Write> {
    start: Instant,
    window: Duration,
    state: Mutex<TraceState<W>>,
}

#[derive(Debug)]
struct TraceState<W: Write> {
    out: Option<W>,
    last_flush: Duration,
}

impl<W: Write> Tracer<W> {
    /// A tracer writing to `out` for `window` after its creation.
    pub fn new(out: W, window: Duration) -> Self {
        Self {
            start: Instant::now(),
            window,
            state: Mutex::new(TraceState {
                out: Some(out),
                last_flush: Duration::ZERO,
            }),
        }
    }

    /// Records a read of `len` bytes at `offset` now.
    pub fn record(&self, offset: u64, len: u64) {
        self.record_at(self.start.elapsed(), offset, len);
    }

    /// Records a read at `elapsed` since the tracer's start (tests pass their
    /// own time). Past the window the writer is flushed and dropped, so later
    /// reads cost one lock and nothing else.
    pub fn record_at(&self, elapsed: Duration, offset: u64, len: u64) {
        let mut guard = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let s = &mut *guard;
        if elapsed > self.window {
            if let Some(mut out) = s.out.take() {
                let _ = out.flush();
            }
            return;
        }
        let Some(out) = s.out.as_mut() else {
            return;
        };
        if writeln!(out, "{} {offset} {len}", elapsed.as_millis()).is_err() {
            s.out = None;
            return;
        }
        // A run may be killed before the window ends: flush about once a second.
        if elapsed.saturating_sub(s.last_flush) >= Duration::from_secs(1) {
            let _ = out.flush();
            s.last_flush = elapsed;
        }
    }

    /// Flushes what was written so far.
    pub fn flush(&self) {
        let mut s = self
            .state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(out) = s.out.as_mut() {
            let _ = out.flush();
        }
    }
}

/// The process-wide tracer from `BC5_MOUNT_TRACE` (`None` when unset or when
/// the file cannot be opened, which is reported on stderr once).
pub fn global_tracer() -> Option<&'static Tracer<BufWriter<File>>> {
    static TRACER: OnceLock<Option<Tracer<BufWriter<File>>>> = OnceLock::new();
    TRACER
        .get_or_init(|| {
            let path = std::env::var_os("BC5_MOUNT_TRACE").filter(|p| !p.is_empty())?;
            let secs = std::env::var("BC5_MOUNT_TRACE_SECS")
                .ok()
                .and_then(|v| v.trim().parse::<u64>().ok())
                .unwrap_or(DEFAULT_TRACE_SECS);
            match OpenOptions::new().create(true).append(true).open(&path) {
                Ok(f) => {
                    eprintln!(
                        "bc5-mount: tracing image reads to {} for {secs} s",
                        Path::new(&path).display()
                    );
                    Some(Tracer::new(BufWriter::new(f), Duration::from_secs(secs)))
                }
                Err(e) => {
                    eprintln!(
                        "bc5-mount: cannot open the trace file {}: {e}",
                        Path::new(&path).display()
                    );
                    None
                }
            }
        })
        .as_ref()
}

/// Records a read in the process-wide trace, if there is one.
pub fn trace(offset: u64, len: u64) {
    if let Some(t) = global_tracer() {
        t.record(offset, len);
    }
}

/// One traced read.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Entry {
    /// Milliseconds after the first traced read.
    pub ms: u64,
    /// Byte offset in the image.
    pub offset: u64,
    /// Length in bytes.
    pub len: u64,
}

/// Parses a trace: `<ms> <offset> <length>` per line, decimal. Blank lines,
/// `#` comments and malformed lines are skipped.
pub fn parse_trace(text: &str) -> Vec<Entry> {
    text.lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }
            let mut f = line.split_whitespace().map(str::parse::<u64>);
            let (Some(Ok(ms)), Some(Ok(offset)), Some(Ok(len)), None) =
                (f.next(), f.next(), f.next(), f.next())
            else {
                return None;
            };
            (len > 0).then_some(Entry { ms, offset, len })
        })
        .collect()
}

/// A range to preload and the first time the title used it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Chunk {
    /// Byte offset in the image.
    pub offset: u64,
    /// Length in bytes.
    pub len: u64,
    /// Earliest use (ms) among the traced reads it covers.
    pub first_ms: u64,
}

/// Turns traced reads into preload chunks: ranges are clamped to `image_len`
/// (ranges past it are dropped), merged when they overlap or lie within `gap`
/// bytes of each other, split at `max_chunk` bytes, and ordered by first use
/// (then offset).
pub fn plan(entries: &[Entry], image_len: u64, gap: u64, max_chunk: u64) -> Vec<Chunk> {
    let max_chunk = max_chunk.max(1);
    let mut ranges: Vec<(u64, u64, u64)> = entries
        .iter()
        .filter(|e| e.offset < image_len)
        .map(|e| {
            let end = e.offset.saturating_add(e.len).min(image_len);
            (e.offset, end, e.ms)
        })
        .collect();
    ranges.sort_unstable_by_key(|&(start, _, _)| start);
    let mut merged: Vec<(u64, u64, u64)> = Vec::new();
    for (start, end, ms) in ranges {
        match merged.last_mut() {
            Some(last) if start <= last.1.saturating_add(gap) => {
                last.1 = last.1.max(end);
                last.2 = last.2.min(ms);
            }
            _ => merged.push((start, end, ms)),
        }
    }
    let mut chunks = Vec::new();
    for (start, end, ms) in merged {
        let mut off = start;
        while off < end {
            let len = (end - off).min(max_chunk);
            chunks.push(Chunk {
                offset: off,
                len,
                first_ms: ms,
            });
            off += len;
        }
    }
    chunks.sort_by_key(|c| (c.first_ms, c.offset));
    chunks
}

/// What a preload did.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Done {
    /// Chunks read.
    pub chunks: usize,
    /// Bytes read.
    pub bytes: u64,
}

/// Reads every chunk from `src` in order, discarding the data (it is the
/// page cache that is wanted). Stops at the first error.
pub fn preload<R: ReadAt + ?Sized>(src: &R, chunks: &[Chunk]) -> io::Result<Done> {
    let largest = chunks.iter().map(|c| c.len).max().unwrap_or(0);
    let mut buf = vec![0u8; usize::try_from(largest).unwrap_or(usize::MAX)];
    let mut done = Done::default();
    for c in chunks {
        let n = usize::try_from(c.len).unwrap_or(usize::MAX).min(buf.len());
        let mut got = 0usize;
        while got < n {
            let r = src.read_at(c.offset + got as u64, &mut buf[got..n])?;
            if r == 0 {
                break; // the image ends here
            }
            got += r;
        }
        done.chunks += 1;
        done.bytes += got as u64;
    }
    Ok(done)
}

/// With `BC5_MOUNT_PRELOAD=<trace file>` set, starts a background thread that
/// preloads the traced ranges of the image at `image` and reports on stderr.
/// Returns at once; does nothing without the variable. Errors are reported,
/// never fatal: the mount works the same without a preload.
pub fn start_from_env(image: &Path) {
    let Some(list) = std::env::var_os("BC5_MOUNT_PRELOAD").filter(|p| !p.is_empty()) else {
        return;
    };
    let image = image.to_path_buf();
    let spawned = std::thread::Builder::new()
        .name("bc5-mount-preload".into())
        .spawn(move || {
            let t0 = Instant::now();
            let text = match std::fs::read_to_string(&list) {
                Ok(t) => t,
                Err(e) => {
                    eprintln!(
                        "bc5-mount: preload list {}: {e}",
                        Path::new(&list).display()
                    );
                    return;
                }
            };
            // Its own handle, untraced: the preload's reads are not the title's.
            let src = match FileSource::open_untraced(&image) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("bc5-mount: preload cannot open {}: {e}", image.display());
                    return;
                }
            };
            let chunks = plan(&parse_trace(&text), src.len(), MERGE_GAP, MAX_CHUNK);
            let planned: u64 = chunks.iter().map(|c| c.len).sum();
            eprintln!(
                "bc5-mount: preloading {} chunks, {} MiB, from {}",
                chunks.len(),
                planned >> 20,
                Path::new(&list).display()
            );
            match preload(&src, &chunks) {
                Ok(d) => eprintln!(
                    "bc5-mount: preload done: {} chunks, {} MiB in {:.1} s",
                    d.chunks,
                    d.bytes >> 20,
                    t0.elapsed().as_secs_f64()
                ),
                Err(e) => eprintln!(
                    "bc5-mount: preload stopped after {:.1} s: {e}",
                    t0.elapsed().as_secs_f64()
                ),
            }
        });
    if let Err(e) = spawned {
        eprintln!("bc5-mount: cannot start the preload thread: {e}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};

    fn e(ms: u64, offset: u64, len: u64) -> Entry {
        Entry { ms, offset, len }
    }

    #[test]
    fn parse_skips_blank_comment_and_malformed_lines() {
        let t = "# header\n\n10 4096 512\nbad line\n20 x 5\n30 8192 0\n40 1 2 3\n 50  100  7 \n";
        assert_eq!(parse_trace(t), vec![e(10, 4096, 512), e(50, 100, 7)]);
    }

    #[test]
    fn plan_merges_overlaps_and_small_gaps() {
        let p = plan(
            &[e(5, 0, 100), e(3, 50, 100), e(9, 160, 10)],
            1 << 20,
            16,
            1 << 20,
        );
        assert_eq!(
            p,
            vec![Chunk {
                offset: 0,
                len: 170,
                first_ms: 3
            }]
        );
    }

    #[test]
    fn plan_keeps_far_ranges_apart_and_orders_by_first_use() {
        let p = plan(&[e(7, 0, 10), e(2, 1000, 10)], 1 << 20, 16, 1 << 20);
        assert_eq!(
            p,
            vec![
                Chunk {
                    offset: 1000,
                    len: 10,
                    first_ms: 2
                },
                Chunk {
                    offset: 0,
                    len: 10,
                    first_ms: 7
                },
            ]
        );
    }

    #[test]
    fn plan_splits_long_ranges() {
        let p = plan(&[e(0, 0, 25)], 1000, 0, 10);
        let lens: Vec<u64> = p.iter().map(|c| c.len).collect();
        assert_eq!(lens, vec![10, 10, 5]);
        assert_eq!(
            p.iter().map(|c| c.offset).collect::<Vec<_>>(),
            vec![0, 10, 20]
        );
    }

    #[test]
    fn plan_clamps_to_the_image_and_drops_ranges_past_it() {
        let p = plan(&[e(0, 90, 50), e(1, 200, 5)], 100, 0, 1000);
        assert_eq!(
            p,
            vec![Chunk {
                offset: 90,
                len: 10,
                first_ms: 0
            }]
        );
    }

    struct Counting {
        data: Vec<u8>,
        reads: AtomicUsize,
        bytes: AtomicU64,
    }

    impl ReadAt for Counting {
        fn len(&self) -> u64 {
            self.data.len() as u64
        }
        fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
            // Short reads, to exercise the loop.
            let m = buf.len().min(7);
            let n = self.data.as_slice().read_at(offset, &mut buf[..m])?;
            self.reads.fetch_add(1, Ordering::Relaxed);
            self.bytes.fetch_add(n as u64, Ordering::Relaxed);
            Ok(n)
        }
    }

    #[test]
    fn preload_reads_every_chunk_completely() {
        let src = Counting {
            data: (0..=255u8).cycle().take(1000).collect(),
            reads: AtomicUsize::new(0),
            bytes: AtomicU64::new(0),
        };
        let chunks = plan(&[e(0, 0, 30), e(1, 500, 40), e(2, 990, 50)], 1000, 0, 16);
        let d = preload(&src, &chunks).unwrap();
        assert_eq!(d.bytes, 30 + 40 + 10);
        assert_eq!(d.chunks, chunks.len());
        assert_eq!(src.bytes.load(Ordering::Relaxed), 80);
    }

    #[test]
    fn tracer_writes_inside_the_window_only() {
        let t = Tracer::new(Vec::new(), Duration::from_secs(2));
        t.record_at(Duration::from_millis(5), 4096, 16384);
        t.record_at(Duration::from_millis(1500), 0, 512);
        t.record_at(Duration::from_millis(2500), 8192, 1); // past the window: closes it
        t.record_at(Duration::from_millis(100), 1, 1); // closed: ignored
        let out = t.state.into_inner().unwrap().out;
        assert!(out.is_none(), "the writer is dropped once the window ends");
    }

    #[test]
    fn tracer_lines_parse_back() {
        let t = Tracer::new(Vec::new(), Duration::from_secs(60));
        t.record_at(Duration::from_millis(5), 4096, 16384);
        t.record_at(Duration::from_millis(1500), 0, 512);
        let out = t.state.into_inner().unwrap().out.unwrap();
        let text = String::from_utf8(out).unwrap();
        assert_eq!(parse_trace(&text), vec![e(5, 4096, 16384), e(1500, 0, 512)]);
    }
}
