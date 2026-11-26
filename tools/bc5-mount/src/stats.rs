// SPDX-License-Identifier: GPL-2.0-only
//! Read and decode counters for tuning the mount (experiment 0112): bytes the
//! mount served, blocks it decoded, and blocks decoded more than once (evicted
//! from the block cache and needed again). Counting a repeat needs a set of
//! every block decoded, so that part is kept only while [`enable`] was called.

use std::collections::HashSet;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Mutex, PoisonError};

static ENABLED: AtomicBool = AtomicBool::new(false);
static SERVED_BYTES: AtomicU64 = AtomicU64::new(0);
static DECODED_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DECODED_BYTES: AtomicU64 = AtomicU64::new(0);
static REDECODED_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DISK_BLOCKS: AtomicU64 = AtomicU64::new(0);
static DISK_BYTES: AtomicU64 = AtomicU64::new(0);
static SEEN: Mutex<Option<HashSet<u64>>> = Mutex::new(None);

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
}

/// Counts one block read back from the on-disk cache.
pub fn from_disk(bytes: u64) {
    DISK_BLOCKS.fetch_add(1, Ordering::Relaxed);
    DISK_BYTES.fetch_add(bytes, Ordering::Relaxed);
}

/// Starts tracking repeated decodes as well.
pub fn enable() {
    *SEEN.lock().unwrap_or_else(PoisonError::into_inner) = Some(HashSet::new());
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
}
