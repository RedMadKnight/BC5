// SPDX-License-Identifier: GPL-2.0-only
//! What the title reads a second time (exp 0381, F505's re-reads). The kernel
//! answers a read from its page cache without asking the mount, so with the
//! default open flags a page that reaches the mount twice was evicted between
//! the two reads. Pages are tracked per 256 KiB chunk of a file; the age and the
//! bytes served since the chunk's last read say how much longer the page would
//! have had to stay. An upper bound of an LRU stack distance: bytes served twice
//! in between count twice. Kept only with `BC5_MOUNT_STATS`.

use std::collections::HashMap;

const PAGE_BITS: u32 = 12;
const CHUNK_BITS: u32 = 18;

/// Upper ends of the age buckets, in seconds; the last bucket has no end.
pub const AGE_LIMITS: [f64; 5] = [1.0, 4.0, 16.0, 64.0, 256.0];
/// Upper ends of the distance buckets, in MiB; the last bucket has no end.
pub const DISTANCE_LIMITS_MIB: [u64; 4] = [64, 256, 1024, 4096];

#[derive(Debug, Clone, Copy)]
struct Chunk {
    /// Pages read at least once, one bit per 4 KiB.
    seen: u64,
    last_secs: f64,
    last_total: u64,
}

/// The counters at one moment.
#[derive(Debug, Default, Clone, Copy, PartialEq)]
pub struct Totals {
    /// Bytes read for the first time.
    pub first: u64,
    /// Bytes read again.
    pub again: u64,
    /// Bytes read again by age.
    pub by_age: [u64; AGE_LIMITS.len() + 1],
    /// Bytes read again by the bytes served since.
    pub by_distance: [u64; DISTANCE_LIMITS_MIB.len() + 1],
}

/// One file's first and repeated bytes.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct FileBytes {
    /// Bytes read for the first time.
    pub first: u64,
    /// Bytes read again.
    pub again: u64,
}

/// The reads of a mount, by file.
#[derive(Debug, Default)]
pub struct Reuse {
    chunks: HashMap<(usize, u64), Chunk>,
    files: HashMap<usize, FileBytes>,
    totals: Totals,
}

impl Reuse {
    /// Counts a read of `len` bytes at `offset` of file `file` at time `now_secs`.
    /// A page read in part counts whole, as the page cache holds it.
    pub fn read(&mut self, file: usize, offset: u64, len: u64, now_secs: f64) {
        if len == 0 {
            return;
        }
        let first_page = offset >> PAGE_BITS;
        let end_page = (offset + len - 1) >> PAGE_BITS;
        let mut page = first_page;
        while page <= end_page {
            let chunk = page >> (CHUNK_BITS - PAGE_BITS);
            let last_in_chunk = ((chunk + 1) << (CHUNK_BITS - PAGE_BITS)) - 1;
            let upto = end_page.min(last_in_chunk);
            let low = page & ((1 << (CHUNK_BITS - PAGE_BITS)) - 1);
            let count = upto - page + 1;
            let mask = if count == 64 {
                u64::MAX
            } else {
                ((1u64 << count) - 1) << low
            };
            self.read_chunk(file, chunk, mask, now_secs);
            page = upto + 1;
        }
    }

    fn read_chunk(&mut self, file: usize, chunk: u64, mask: u64, now_secs: f64) {
        let total = self.totals.first + self.totals.again;
        let e = self.chunks.entry((file, chunk)).or_insert(Chunk {
            seen: 0,
            last_secs: now_secs,
            last_total: total,
        });
        let again = u64::from((mask & e.seen).count_ones()) << PAGE_BITS;
        let first = u64::from((mask & !e.seen).count_ones()) << PAGE_BITS;
        let age = now_secs - e.last_secs;
        let distance = total - e.last_total;
        e.seen |= mask;
        e.last_secs = now_secs;
        e.last_total = total;
        self.totals.first += first;
        self.totals.again += again;
        if again != 0 {
            let a = AGE_LIMITS
                .iter()
                .position(|&l| age < l)
                .unwrap_or(AGE_LIMITS.len());
            self.totals.by_age[a] += again;
            let d = DISTANCE_LIMITS_MIB
                .iter()
                .position(|&l| distance < l << 20)
                .unwrap_or(DISTANCE_LIMITS_MIB.len());
            self.totals.by_distance[d] += again;
        }
        let f = self.files.entry(file).or_default();
        f.first += first;
        f.again += again;
    }

    /// The counters now.
    pub fn totals(&self) -> Totals {
        self.totals
    }

    /// The `n` files with the most bytes read again, most first.
    pub fn top_files(&self, n: usize) -> Vec<(usize, FileBytes)> {
        let mut v: Vec<_> = self.files.iter().map(|(&i, &b)| (i, b)).collect();
        v.sort_by_key(|&(i, b)| (std::cmp::Reverse(b.again), i));
        v.truncate(n);
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const P: u64 = 1 << PAGE_BITS;
    const C: u64 = 1 << CHUNK_BITS;

    #[test]
    fn neighbours_in_one_chunk_are_not_repeats() {
        let mut r = Reuse::default();
        r.read(1, 0, 128 << 10, 0.0);
        r.read(1, 128 << 10, 128 << 10, 0.1);
        assert_eq!(r.totals().first, C);
        assert_eq!(r.totals().again, 0);
    }

    #[test]
    fn a_repeat_counts_its_pages_with_age_and_distance() {
        let mut r = Reuse::default();
        r.read(1, 0, 8 * P, 0.0);
        r.read(2, 0, 100 << 20, 1.0);
        r.read(1, 4 * P, 8 * P, 5.0);
        let t = r.totals();
        assert_eq!(t.again, 4 * P);
        assert_eq!(t.first, 8 * P + (100 << 20) + 4 * P);
        assert_eq!(t.by_age[2], 4 * P); // 5 s: under 16
        assert_eq!(t.by_distance[1], 4 * P); // ~100 MiB: under 256
    }

    #[test]
    fn a_read_across_chunks_and_a_whole_chunk() {
        let mut r = Reuse::default();
        r.read(1, C - P, 2 * P, 0.0);
        assert_eq!(r.totals().first, 2 * P);
        r.read(1, C, C, 1.0);
        assert_eq!(r.totals().first, P + C);
        assert_eq!(r.totals().again, P);
    }

    #[test]
    fn a_partial_page_counts_whole_and_empty_reads_nothing() {
        let mut r = Reuse::default();
        r.read(1, 10, 1, 0.0);
        r.read(1, 100, 1, 0.0);
        r.read(1, 100, 0, 0.0);
        assert_eq!(r.totals().first, P);
        assert_eq!(r.totals().again, P);
    }

    #[test]
    fn old_repeats_land_in_the_last_buckets() {
        let mut r = Reuse::default();
        r.read(1, 0, P, 0.0);
        r.read(2, 0, 5 << 30, 1.0);
        r.read(1, 0, P, 1000.0);
        let t = r.totals();
        assert_eq!(t.by_age[AGE_LIMITS.len()], P);
        assert_eq!(t.by_distance[DISTANCE_LIMITS_MIB.len()], P);
    }

    #[test]
    fn top_files_sort_by_repeats() {
        let mut r = Reuse::default();
        r.read(1, 0, P, 0.0);
        r.read(1, 0, P, 1.0);
        r.read(2, 0, 2 * P, 0.0);
        r.read(2, 0, 2 * P, 1.0);
        r.read(3, 0, 9 * P, 0.0);
        let top = r.top_files(2);
        assert_eq!(top[0].0, 2);
        assert_eq!(top[1].0, 1);
        assert_eq!(top[0].1.again, 2 * P);
    }
}
