// SPDX-License-Identifier: GPL-2.0-only
//! A decoded-block cache shared by reader threads: blocks are spread over
//! shards by index, each with its own lock and least-recently-used order, so
//! threads reading different blocks do not wait for each other (experiment
//! 0033). Values are reference-counted, so a reader copies out of a block
//! without holding any lock.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex, PoisonError};

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

#[cfg(test)]
mod tests {
    use super::*;

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
}
