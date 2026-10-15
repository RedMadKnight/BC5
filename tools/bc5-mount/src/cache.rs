// SPDX-License-Identifier: GPL-2.0-only
//! A decoded-block cache shared by reader threads: blocks are spread over
//! shards by index, each with its own lock and least-recently-used order, so
//! threads reading different blocks do not wait for each other (experiment
//! 0033). Values are reference-counted, so a reader copies out of a block
//! without holding any lock.
//!
//! [`DecodeCache`] adds one decode per block (experiment 0116): a missing
//! block gets an in-flight slot of its own, and only readers of that same
//! block wait on it. No lock is held while a block decodes, so a reader of
//! another block never waits for an unrelated decode (the striped locks of
//! experiments 0112 and 0114 did that), and [`DecodeCache::prefetch`] skips a
//! block someone else is decoding instead of waiting for it.

use std::collections::{HashMap, VecDeque};
use std::io;
use std::sync::{Arc, Condvar, Mutex, PoisonError};

use crate::{Error, Result};

/// Number of shards; a power of two.
const SHARDS: usize = 16;

/// One shard: blocks in least-recently-used order, most recent at the back.
type Shard = Mutex<VecDeque<(u64, Arc<Vec<u8>>)>>;

/// A sharded LRU cache of decoded blocks keyed by block index.
#[derive(Debug)]
pub struct BlockCache {
    shards: Vec<Shard>,
    per_shard: usize,
}

impl BlockCache {
    /// A cache of about `blocks` entries (at least one per shard).
    pub fn new(blocks: usize) -> Self {
        Self {
            shards: (0..SHARDS).map(|_| Mutex::new(VecDeque::new())).collect(),
            per_shard: blocks.div_ceil(SHARDS).max(1),
        }
    }

    fn shard(&self, idx: u64) -> &Shard {
        &self.shards[(idx as usize) & (SHARDS - 1)]
    }

    /// The block, if cached; marks it most recently used.
    pub fn get(&self, idx: u64) -> Option<Arc<Vec<u8>>> {
        let mut s = self
            .shard(idx)
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        let pos = s.iter().position(|(i, _)| *i == idx)?;
        let entry = s.remove(pos)?;
        let value = Arc::clone(&entry.1);
        s.push_back(entry);
        Some(value)
    }

    /// True when the block is cached (does not change the order).
    pub fn contains(&self, idx: u64) -> bool {
        self.shard(idx)
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .iter()
            .any(|(i, _)| *i == idx)
    }

    /// Inserts a block (a block already present is kept) and evicts the
    /// shard's least recently used one when full.
    pub fn insert(&self, idx: u64, block: Arc<Vec<u8>>) {
        let mut s = self
            .shard(idx)
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        if s.iter().any(|(i, _)| *i == idx) {
            return;
        }
        s.push_back((idx, block));
        if s.len() > self.per_shard {
            s.pop_front();
        }
    }
}

/// Cache size in blocks of `block_bytes`: `BC5_MOUNT_CACHE_MIB` MiB when set
/// to a positive number (experiment 0112), else `default_mib` MiB.
pub fn cache_blocks(default_mib: usize, block_bytes: usize) -> usize {
    let mib = std::env::var("BC5_MOUNT_CACHE_MIB")
        .ok()
        .and_then(|v| v.trim().parse::<usize>().ok())
        .filter(|&mib| mib > 0)
        .unwrap_or(default_mib);
    ((mib << 20) / block_bytes.max(1)).max(1)
}

/// What a finished decode leaves for the readers that waited on it.
type Outcome = std::result::Result<Arc<Vec<u8>>, String>;

/// One block being decoded: its readers wait here, and on nothing else.
#[derive(Debug, Default)]
struct Slot {
    outcome: Mutex<Option<Outcome>>,
    ready: Condvar,
}

impl Slot {
    fn wait(&self) -> Outcome {
        let mut o = self.outcome.lock().unwrap_or_else(PoisonError::into_inner);
        loop {
            if let Some(done) = o.as_ref() {
                return done.clone();
            }
            o = self.ready.wait(o).unwrap_or_else(PoisonError::into_inner);
        }
    }
}

/// Blocks being decoded, by index.
type InFlight = Mutex<HashMap<u64, Arc<Slot>>>;

enum Claim {
    /// Decoded meanwhile.
    Cached(Arc<Vec<u8>>),
    /// Another reader is decoding it.
    Wait(Arc<Slot>),
    /// This reader decodes it.
    Mine(Arc<Slot>),
}

/// A [`BlockCache`] that decodes each missing block once, however many
/// readers ask for it at the same time.
#[derive(Debug)]
pub struct DecodeCache {
    cache: BlockCache,
    in_flight: Vec<InFlight>,
}

impl DecodeCache {
    /// A cache of about `blocks` decoded blocks.
    pub fn new(blocks: usize) -> Self {
        Self {
            cache: BlockCache::new(blocks),
            in_flight: (0..SHARDS).map(|_| Mutex::new(HashMap::new())).collect(),
        }
    }

    fn in_flight(&self, idx: u64) -> &InFlight {
        &self.in_flight[(idx as usize) & (SHARDS - 1)]
    }

    /// The block from the cache, or from the reader already decoding it, or
    /// from `decode` run here. Only readers of the same block wait.
    pub fn get_or_decode(
        &self,
        idx: u64,
        decode: impl FnOnce() -> Result<Vec<u8>>,
    ) -> Result<Arc<Vec<u8>>> {
        if let Some(b) = self.cache.get(idx) {
            return Ok(b);
        }
        match self.claim(idx) {
            Claim::Cached(b) => Ok(b),
            Claim::Wait(slot) => slot.wait().map_err(|msg| Error::Io(io::Error::other(msg))),
            Claim::Mine(slot) => self.decode(idx, &slot, decode),
        }
    }

    /// Decodes the block unless it is cached or being decoded; never waits for
    /// another reader (decode-ahead, experiment 0116).
    pub fn prefetch(&self, idx: u64, decode: impl FnOnce() -> Result<Vec<u8>>) -> Result<()> {
        if self.cache.contains(idx) {
            return Ok(());
        }
        match self.claim(idx) {
            Claim::Mine(slot) => self.decode(idx, &slot, decode).map(drop),
            Claim::Cached(_) | Claim::Wait(_) => Ok(()),
        }
    }

    /// True when the block is cached.
    pub fn contains(&self, idx: u64) -> bool {
        self.cache.contains(idx)
    }

    fn claim(&self, idx: u64) -> Claim {
        let mut map = self
            .in_flight(idx)
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        if let Some(slot) = map.get(&idx) {
            return Claim::Wait(Arc::clone(slot));
        }
        // A decoder caches its block before it leaves the map, so a block
        // finished since the first look is in the cache now.
        if let Some(b) = self.cache.get(idx) {
            return Claim::Cached(b);
        }
        let slot = Arc::new(Slot::default());
        map.insert(idx, Arc::clone(&slot));
        Claim::Mine(slot)
    }

    fn decode(
        &self,
        idx: u64,
        slot: &Arc<Slot>,
        decode: impl FnOnce() -> Result<Vec<u8>>,
    ) -> Result<Arc<Vec<u8>>> {
        let mut done = Release {
            owner: self,
            idx,
            slot,
            outcome: Err(format!("decoding block {idx} panicked")),
        };
        let r = decode().map(Arc::new);
        done.outcome = match &r {
            Ok(b) => {
                self.cache.insert(idx, Arc::clone(b));
                Ok(Arc::clone(b))
            }
            Err(e) => Err(e.to_string()),
        };
        r
    }
}

/// Ends a decode, also when it panics: the block leaves the in-flight map
/// and its waiting readers get the outcome.
struct Release<'a> {
    owner: &'a DecodeCache,
    idx: u64,
    slot: &'a Arc<Slot>,
    outcome: Outcome,
}

impl Drop for Release<'_> {
    fn drop(&mut self) {
        self.owner
            .in_flight(self.idx)
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .remove(&self.idx);
        let outcome = std::mem::replace(&mut self.outcome, Err(String::new()));
        *self
            .slot
            .outcome
            .lock()
            .unwrap_or_else(PoisonError::into_inner) = Some(outcome);
        self.slot.ready.notify_all();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Barrier;
    use std::time::{Duration, Instant};

    #[test]
    fn keeps_recent_blocks_and_evicts_old_ones() {
        let c = BlockCache::new(SHARDS); // one entry per shard
        c.insert(0, Arc::new(vec![0]));
        c.insert(SHARDS as u64, Arc::new(vec![1])); // same shard: evicts block 0
        assert!(c.get(0).is_none());
        assert_eq!(c.get(SHARDS as u64).unwrap().as_slice(), &[1]);
        c.insert(1, Arc::new(vec![2])); // another shard: both stay
        assert!(c.contains(1) && c.contains(SHARDS as u64));
    }

    #[test]
    fn a_get_refreshes_the_order() {
        let c = BlockCache::new(2 * SHARDS); // two entries per shard
        let s = SHARDS as u64;
        c.insert(0, Arc::new(vec![0]));
        c.insert(s, Arc::new(vec![1]));
        assert!(c.get(0).is_some()); // 0 is now the most recent
        c.insert(2 * s, Arc::new(vec![2])); // evicts s, not 0
        assert!(c.contains(0) && !c.contains(s) && c.contains(2 * s));
    }

    #[test]
    fn concurrent_readers_of_one_block_decode_it_once() {
        let c = DecodeCache::new(64);
        let decodes = AtomicUsize::new(0);
        let start = Barrier::new(8);
        let blocks: Vec<_> = std::thread::scope(|s| {
            let handles: Vec<_> = (0..8)
                .map(|_| {
                    s.spawn(|| {
                        start.wait();
                        c.get_or_decode(7, || {
                            decodes.fetch_add(1, Ordering::SeqCst);
                            std::thread::sleep(Duration::from_millis(100));
                            Ok(vec![7; 4])
                        })
                        .unwrap()
                    })
                })
                .collect();
            handles.into_iter().map(|h| h.join().unwrap()).collect()
        });
        assert_eq!(decodes.load(Ordering::SeqCst), 1);
        assert!(blocks.iter().all(|b| Arc::ptr_eq(b, &blocks[0])));
        assert!(c.contains(7));
    }

    #[test]
    fn a_slow_decode_does_not_delay_another_block() {
        let c = DecodeCache::new(64);
        // Block 0 and block SHARDS share a shard of the cache and of the
        // in-flight map, and would have shared a stripe of the old locks.
        let other = SHARDS as u64;
        let started = Barrier::new(2);
        std::thread::scope(|s| {
            let slow = s.spawn(|| {
                c.get_or_decode(0, || {
                    started.wait();
                    std::thread::sleep(Duration::from_millis(500));
                    Ok(vec![0])
                })
                .unwrap()
            });
            started.wait();
            let t = Instant::now();
            assert_eq!(c.get_or_decode(other, || Ok(vec![1])).unwrap()[0], 1);
            let fast = t.elapsed();
            assert!(!slow.is_finished(), "the slow decode should still run");
            assert!(fast < Duration::from_millis(250), "waited {fast:?}");
            // Decode-ahead of the block in flight returns without waiting.
            let t = Instant::now();
            c.prefetch(0, || panic!("block 0 is already being decoded"))
                .unwrap();
            assert!(t.elapsed() < Duration::from_millis(250));
            slow.join().unwrap();
        });
        assert!(c.contains(0) && c.contains(other));
    }

    #[test]
    fn prefetch_decodes_missing_blocks_and_skips_cached_ones() {
        let c = DecodeCache::new(64);
        c.prefetch(3, || Ok(vec![3])).unwrap();
        assert!(c.contains(3));
        c.prefetch(3, || panic!("block 3 is cached")).unwrap();
        assert_eq!(c.get_or_decode(3, || panic!("cached")).unwrap()[0], 3);
    }

    #[test]
    fn failures_reach_the_waiters_and_are_not_cached() {
        let c = DecodeCache::new(64);
        let start = Barrier::new(2);
        std::thread::scope(|s| {
            let waiter = s.spawn(|| {
                start.wait();
                std::thread::sleep(Duration::from_millis(50));
                c.get_or_decode(5, || Ok(vec![5]))
            });
            let r = c.get_or_decode(5, || {
                start.wait();
                std::thread::sleep(Duration::from_millis(200));
                Err(Error::format("test", "bad block"))
            });
            assert!(r.is_err());
            assert!(waiter
                .join()
                .unwrap()
                .unwrap_err()
                .to_string()
                .contains("bad block"));
        });
        assert!(!c.contains(5));
        // The next reader decodes it again.
        assert_eq!(c.get_or_decode(5, || Ok(vec![5])).unwrap()[0], 5);
    }

    #[test]
    fn a_panicking_decode_releases_its_waiters() {
        let c = DecodeCache::new(64);
        let start = Barrier::new(2);
        std::thread::scope(|s| {
            let waiter = s.spawn(|| {
                start.wait();
                std::thread::sleep(Duration::from_millis(50));
                c.get_or_decode(9, || Ok(vec![9]))
            });
            let p = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                c.get_or_decode(9, || {
                    start.wait();
                    std::thread::sleep(Duration::from_millis(200));
                    panic!("decoder bug")
                })
            }));
            assert!(p.is_err());
            assert!(waiter.join().unwrap().is_err());
        });
        assert_eq!(c.get_or_decode(9, || Ok(vec![9])).unwrap()[0], 9);
    }

    #[test]
    fn cache_size_from_the_default() {
        // BC5_MOUNT_CACHE_MIB is not set in the test environment.
        if std::env::var_os("BC5_MOUNT_CACHE_MIB").is_none() {
            assert_eq!(cache_blocks(16, 64 << 10), 256);
            assert_eq!(cache_blocks(0, 64 << 10), 1);
        }
    }
}
