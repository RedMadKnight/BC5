// SPDX-License-Identifier: GPL-2.0-only
//! Read and decode counters for tuning the mount (experiment 0112): bytes the
//! mount served, blocks it decoded, and blocks decoded more than once (evicted
//! from the block cache and needed again). Counting a repeat needs a set of
//! every block decoded, so that part is kept only while [`enable`] was called.

use std::collections::HashSet;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Mutex, PoisonError};
use std::time::Instant;

static ENABLED: AtomicBool = AtomicBool::new(false);
static SERVED_BYTES: AtomicU64 = AtomicU64::new(0);
static DECODED_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DECODED_BYTES: AtomicU64 = AtomicU64::new(0);
static REDECODED_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DISK_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DISK_BYTES: AtomicU64 = AtomicU64::new(0);
static SEEN: Mutex<Option<HashSet<u64>>> = Mutex::new(None);
static IMAGE_BYTES: AtomicU64 = AtomicU64::new(0);
static PUT_BYTES: AtomicU64 = AtomicU64::new(0);
static TOUCHES: AtomicU64 = AtomicU64::new(0);
static AHEAD_BLOCKS: AtomicU64 = AtomicU64::new(0);
static AHEAD_USED: AtomicU64 = AtomicU64::new(0);
static AHEAD: Mutex<Option<HashSet<u64>>> = Mutex::new(None);
static PENDING_PEAK: AtomicU64 = AtomicU64::new(0);

/// A stretch of a read's life (exp 0381: where a read waits).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Span {
    /// In the pool's queue.
    Queue,
    /// On a worker, the whole read.
    Service,
    /// Reading a block from the on-disk cache.
    DiskRead,
    /// Reading a block's stored bytes from the image.
    ImageRead,
    /// Decoding a block.
    Decode,
}

/// The [`Span`]s in the order of [`spans`].
pub const SPANS: [(Span, &str); 5] = [
    (Span::Queue, "queue"),
    (Span::Service, "service"),
    (Span::DiskRead, "disk"),
    (Span::ImageRead, "image"),
    (Span::Decode, "decode"),
];

static SPAN_COUNT: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static SPAN_NS: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static SPAN_PEAK_NS: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];

/// One [`Span`]'s totals since the start, and its longest since the last call.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct SpanTotals {
    /// How many.
    pub count: u64,
    /// Their time, nanoseconds.
    pub ns: u64,
    /// The longest, nanoseconds.
    pub peak_ns: u64,
}

/// The start of a span, while the counters are on.
pub fn span_start() -> Option<Instant> {
    ENABLED.load(Ordering::Relaxed).then(Instant::now)
}

/// Ends a span begun by [`span_start`].
pub fn span_end(kind: Span, start: Option<Instant>) {
    if let Some(s) = start {
        let ns = u64::try_from(s.elapsed().as_nanos()).unwrap_or(u64::MAX);
        let i = kind as usize;
        SPAN_COUNT[i].fetch_add(1, Ordering::Relaxed);
        SPAN_NS[i].fetch_add(ns, Ordering::Relaxed);
        SPAN_PEAK_NS[i].fetch_max(ns, Ordering::Relaxed);
    }
}

/// The spans' totals; their peaks start afresh.
pub fn spans() -> [SpanTotals; 5] {
    std::array::from_fn(|i| SpanTotals {
        count: SPAN_COUNT[i].load(Ordering::Relaxed),
        ns: SPAN_NS[i].load(Ordering::Relaxed),
        peak_ns: SPAN_PEAK_NS[i].swap(0, Ordering::Relaxed),
    })
}

/// Records the jobs queued or running, keeping the peak.
pub fn pending(jobs: u64) {
    PENDING_PEAK.fetch_max(jobs, Ordering::Relaxed);
}

/// The peak of [`pending`] since the last call.
pub fn take_pending_peak() -> u64 {
    PENDING_PEAK.swap(0, Ordering::Relaxed)
}

/// Counts stored bytes read from the image.
pub fn image_read(bytes: u64) {
    IMAGE_BYTES.fetch_add(bytes, Ordering::Relaxed);
}

/// Counts decoded bytes written to the on-disk cache.
pub fn disk_put(bytes: u64) {
    PUT_BYTES.fetch_add(bytes, Ordering::Relaxed);
}

/// Counts a block made ready by decode-ahead, before a reader asked for it.
pub fn ahead(key: u64) {
    if ENABLED.load(Ordering::Relaxed) {
        AHEAD_BLOCKS.fetch_add(1, Ordering::Relaxed);
        if let Some(s) = AHEAD
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .as_mut()
        {
            s.insert(key);
        }
    }
}

/// Counts a reader's use of a block.
pub fn touched(key: u64) {
    if ENABLED.load(Ordering::Relaxed) {
        TOUCHES.fetch_add(1, Ordering::Relaxed);
        if let Some(s) = AHEAD
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .as_mut()
        {
            if s.remove(&key) {
                AHEAD_USED.fetch_add(1, Ordering::Relaxed);
            }
        }
    }
}

/// A snapshot of the counters.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct Snapshot {
    /// Bytes handed to readers.
    pub served_bytes: u64,
    /// Blocks decoded (cache misses).
    pub decoded_blocks: u64,
    /// Bytes those blocks decoded to.
    pub decoded_bytes: u64,
    /// Decodes of a block that had been decoded before.
    pub redecoded_blocks: u64,
    /// Blocks read back from the on-disk cache instead of decoded.
    pub disk_blocks: u64,
    /// Bytes of those blocks.
    pub disk_bytes: u64,
    /// Stored bytes read from the image.
    pub image_bytes: u64,
    /// Decoded bytes written to the on-disk cache.
    pub put_bytes: u64,
    /// Readers' uses of a block, cached or not.
    pub touches: u64,
    /// Blocks made ready by decode-ahead.
    pub ahead_blocks: u64,
    /// Those a reader then used.
    pub ahead_used: u64,
}

/// Counts one block read back from the on-disk cache.
pub fn from_disk(bytes: u64) {
    DISK_BLOCKS.fetch_add(1, Ordering::Relaxed);
    DISK_BYTES.fetch_add(bytes, Ordering::Relaxed);
}

/// Starts tracking repeated decodes as well.
pub fn enable() {
    *SEEN.lock().unwrap_or_else(PoisonError::into_inner) = Some(HashSet::new());
    *AHEAD.lock().unwrap_or_else(PoisonError::into_inner) = Some(HashSet::new());
    ENABLED.store(true, Ordering::Relaxed);
}

/// Counts bytes handed to a reader.
pub fn served(bytes: u64) {
    SERVED_BYTES.fetch_add(bytes, Ordering::Relaxed);
}

/// Counts one decoded block (`key` identifies it across the image).
pub fn decoded(key: u64, bytes: u64) {
    DECODED_BLOCKS.fetch_add(1, Ordering::Relaxed);
    DECODED_BYTES.fetch_add(bytes, Ordering::Relaxed);
    if ENABLED.load(Ordering::Relaxed) {
        let mut seen = SEEN.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some(s) = seen.as_mut() {
            if !s.insert(key) {
                REDECODED_BLOCKS.fetch_add(1, Ordering::Relaxed);
            }
        }
    }
}

/// The counters now.
pub fn snapshot() -> Snapshot {
    Snapshot {
        served_bytes: SERVED_BYTES.load(Ordering::Relaxed),
        decoded_blocks: DECODED_BLOCKS.load(Ordering::Relaxed),
        decoded_bytes: DECODED_BYTES.load(Ordering::Relaxed),
        redecoded_blocks: REDECODED_BLOCKS.load(Ordering::Relaxed),
        disk_blocks: DISK_BLOCKS.load(Ordering::Relaxed),
        disk_bytes: DISK_BYTES.load(Ordering::Relaxed),
        image_bytes: IMAGE_BYTES.load(Ordering::Relaxed),
        put_bytes: PUT_BYTES.load(Ordering::Relaxed),
        touches: TOUCHES.load(Ordering::Relaxed),
        ahead_blocks: AHEAD_BLOCKS.load(Ordering::Relaxed),
        ahead_used: AHEAD_USED.load(Ordering::Relaxed),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_repeats_only_once_enabled() {
        let before = snapshot();
        enable();
        decoded(u64::MAX - 1, 10);
        decoded(u64::MAX - 1, 10);
        decoded(u64::MAX - 2, 5);
        served(7);
        let after = snapshot();
        assert_eq!(after.decoded_blocks - before.decoded_blocks, 3);
        assert_eq!(after.decoded_bytes - before.decoded_bytes, 25);
        assert_eq!(after.redecoded_blocks - before.redecoded_blocks, 1);
        assert_eq!(after.served_bytes - before.served_bytes, 7);
    }

    #[test]
    fn decode_ahead_counts_what_a_reader_used() {
        enable();
        let before = snapshot();
        ahead(u64::MAX - 3);
        ahead(u64::MAX - 4);
        touched(u64::MAX - 3);
        touched(u64::MAX - 3); // a second use is not a second block
        let after = snapshot();
        assert_eq!(after.ahead_blocks - before.ahead_blocks, 2);
        assert_eq!(after.ahead_used - before.ahead_used, 1);
        assert!(after.touches - before.touches >= 2);
    }

    #[test]
    fn spans_add_up_and_their_peak_starts_afresh() {
        enable();
        let before = spans()[Span::Decode as usize];
        span_end(Span::Decode, span_start());
        let s = spans()[Span::Decode as usize];
        assert!(s.count > before.count);
        span_end(Span::Decode, None);
        assert_eq!(spans()[Span::Decode as usize].peak_ns, 0);
    }

    #[test]
    fn the_pending_peak_is_taken_once() {
        pending(5);
        pending(3);
        assert!(take_pending_peak() >= 5);
    }
}
