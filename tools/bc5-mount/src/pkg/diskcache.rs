// SPDX-License-Identifier: GPL-2.0-only
//! Decoded Kraken blocks kept on disk between mounts (experiment 0112). A title
//! reads the same ~2 GB at every start, and decoding it costs seconds the game
//! spends waiting. With a cache directory, a block decoded once is written to a
//! sparse data file at `index × block size`, and an entry in a map file records
//! its length and CRC-32. A later mount reads it back instead of decoding; an
//! entry whose CRC does not match is dropped and the block decoded again.
//!
//! Files: `<key>.data` (sparse, one slot per block), `<key>.map` (8 bytes per
//! block, little-endian: CRC-32 in the high half, length in the low half, 0 =
//! absent) and `<key>.use` (4 bytes per block: the minute it was last read or
//! written, 0 = not known). The key is derived from the stored image, so another
//! package gets its own files.
//!
//! The limit (experiment 0447) is ONE total for every image in the directory. `BC5_MOUNT_DISK_CACHE_MIB=<n>` sets
//! it; without the word it is taken from the drive when the files are opened: [`FREE_SHARE_PERCENT`] of what the
//! drive would have free above the floor with the directory empty. The floor is [`FREE_FLOOR_MIB`], or
//! `BC5_MOUNT_DISK_CACHE_FLOOR_MIB=<n>`. With the limit from the drive nothing is added while the drive has less
//! than the floor free (looked at again every [`FLOOR_CHECK_EVERY`] blocks).
//!
//! Written blocks do not stay in memory as dirty pages: after every [`WRITE_BACK_MIB`] written, the data file is
//! written back and its pages are dropped (experiment 0447: a title's first start left 0.9-1.25 GiB of dirty
//! pages in its first minute, more than a title near the memory wall has).
//!
//! At the total the least recently used blocks are dropped to make room: first from the files of the OTHER images
//! that no mount has open, the oldest minutes first across them, and only when those have nothing left from this
//! image's own blocks of earlier mounts, oldest first (the title being played keeps its own before another's:
//! by plain age its blocks of last week would go before another title's of yesterday, just as it reads them
//! again). A block read or written since this mount opened is never dropped, and neither is anything of an image
//! another mount holds (each mount keeps a shared lock on its map file; the dropper takes an exclusive one or
//! leaves the image alone). Under
//! the floor a block is added only after at least as much was dropped, so the directory does not grow there. When
//! nothing may be dropped, writing stops as before. Each drop is reported on stderr.

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::Mutex;

use sha2::{Digest, Sha256};

use crate::io::ReadAt;

/// The total when the drive's free space cannot be read, in MiB (the fixed limit of experiment 0112).
pub const FALLBACK_LIMIT_MIB: u64 = 8192;
/// Free space the cache leaves on its drive, in MiB: with the limit taken from the drive, nothing is added while
/// less than this is free. 32 GiB, the value agreed for the dev box (experiment 0447): on its 475 GB drive with
/// 84 GB free one shared directory then stops at about 60 GB free, where a floor of 64 GiB left the cache 7 GiB,
/// less than one title's start (9-11 GiB); the drive's own trouble began at 14-21 GB free.
/// `BC5_MOUNT_DISK_CACHE_FLOOR_MIB` sets another.
pub const FREE_FLOOR_MIB: u64 = 32 * 1024;
/// With the limit taken from the drive: the share of the space above the floor (free space plus what the cache
/// directory holds already) that all the images' cache files together may hold.
pub const FREE_SHARE_PERCENT: u64 = 50;
/// With the limit taken from the drive: the free space is read again every this many stored blocks.
pub const FLOOR_CHECK_EVERY: u64 = 64;
/// After this many MiB written to the data file it is written back and its pages are dropped. 64 MiB: the dirty
/// pages stay an order under the 0.9-1.25 GiB measured on a first start and under a fifth of what the title with
/// the least memory keeps available (0.6 GiB), for one `fdatasync` about every half second at a first start's
/// write rate (some 100 MiB/s); less would stall the writer more often, more would hold more memory.
pub const WRITE_BACK_MIB: u64 = 64;
/// When room is made, this much more than needed is dropped at once (or a sixteenth of the total if that is
/// less), so the files are not walked for every block.
pub const DROP_BATCH: u64 = 256 << 20;

/// How much decoded data the cache directory may hold, all images together.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Limit {
    /// At most this many bytes, whatever the drive has free.
    Bytes(u64),
    /// Taken from the drive's free space when the files are opened, with the floor kept free.
    FromDrive,
}

impl Limit {
    /// The limit named by `BC5_MOUNT_DISK_CACHE_MIB` (`word`): a number of MiB, else the drive's.
    pub fn from_word(word: Option<&str>) -> Self {
        word.and_then(|w| w.trim().parse::<u64>().ok())
            .map_or(Self::FromDrive, |mib| {
                Self::Bytes(mib.saturating_mul(1 << 20))
            })
    }
}

/// The floor in bytes named by `BC5_MOUNT_DISK_CACHE_FLOOR_MIB` (`word`): a number of MiB, else
/// [`FREE_FLOOR_MIB`].
pub fn floor_from_word(word: Option<&str>) -> u64 {
    word.and_then(|w| w.trim().parse::<u64>().ok())
        .unwrap_or(FREE_FLOOR_MIB)
        .saturating_mul(1 << 20)
}

/// The directory's total taken from the drive: the cache files hold `all` bytes, the drive has `free` bytes free
/// (`None`: not known) and `floor` bytes of it are to stay free. The total is the share of `free + all` above the
/// floor, that is, of the space the drive would have above the floor with the directory empty.
pub fn total_from_drive(all: u64, free: Option<u64>, floor: u64) -> u64 {
    match free {
        Some(free) => {
            let above = free.saturating_add(all).saturating_sub(floor);
            let p = FREE_SHARE_PERCENT;
            (above / 100) * p + (above % 100) * p / 100
        }
        None => FALLBACK_LIMIT_MIB << 20,
    }
}

/// Bytes free for an unprivileged writer on the drive that holds `dir`, if that can be read.
#[cfg(unix)]
pub fn free_bytes(dir: &Path) -> Option<u64> {
    let vfs = nix::sys::statvfs::statvfs(dir).ok()?;
    Some(vfs.blocks_available() * vfs.fragment_size())
}

/// Bytes free on the drive that holds `dir`: not read on this platform.
#[cfg(not(unix))]
pub fn free_bytes(_dir: &Path) -> Option<u64> {
    None
}

/// The minute now, counted from the Unix epoch (the unit of the `.use` file).
fn minute_now() -> u32 {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    u32::try_from(secs / 60).unwrap_or(u32::MAX).max(1)
}

/// The cache files of one package image.
#[derive(Debug)]
pub struct DiskCache {
    dir: PathBuf,
    key: String,
    data: File,
    map: File,
    used_file: File,
    entries: Vec<AtomicU64>,
    /// Per block, the minute it was last read or written (0: not known, the oldest).
    used: Vec<AtomicU32>,
    block_bytes: u64,
    /// The directory's total.
    total: u64,
    /// Bytes the other images' files held when last counted (at open and whenever room is made).
    others: AtomicU64,
    written: AtomicU64,
    /// The minute this mount opened the files: its own blocks used since are never dropped.
    opened: u32,
    /// The limit was taken from the drive: the floor is watched.
    watch: bool,
    /// Bytes the drive is to keep free.
    floor: u64,
    /// Bytes written to the data file since it was last written back, and after how many that happens.
    unsynced: AtomicU64,
    write_back_every: u64,
    /// One thread writes back at a time; how often it happened.
    writing_back: Mutex<()>,
    written_back: AtomicU64,
    puts: AtomicU64,
    low: AtomicBool,
    /// One thread makes room at a time; the others skip their block meanwhile.
    room: Mutex<()>,
    /// The minute the `.use` file was last written.
    flushed: AtomicU32,
    dropped: AtomicU64,
    /// Tests set the minute; 0 means the clock.
    minute: AtomicU32,
    /// The shared lock on the map file that tells a dropper in another mount this image is open.
    #[cfg(unix)]
    _held: Option<nix::fcntl::Flock<File>>,
}

fn crc32(bytes: &[u8]) -> u32 {
    let mut c = flate2::Crc::new();
    c.update(bytes);
    c.sum()
}

#[cfg(unix)]
fn read_exact_at(f: &File, buf: &mut [u8], offset: u64) -> io::Result<()> {
    std::os::unix::fs::FileExt::read_exact_at(f, buf, offset)
}

#[cfg(unix)]
fn write_all_at(f: &File, buf: &[u8], offset: u64) -> io::Result<()> {
    std::os::unix::fs::FileExt::write_all_at(f, buf, offset)
}

#[cfg(windows)]
fn read_exact_at(f: &File, mut buf: &mut [u8], mut offset: u64) -> io::Result<()> {
    while !buf.is_empty() {
        let n = std::os::windows::fs::FileExt::seek_read(f, buf, offset)?;
        if n == 0 {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }
        buf = &mut buf[n..];
        offset += n as u64;
    }
    Ok(())
}

#[cfg(windows)]
fn write_all_at(f: &File, mut buf: &[u8], mut offset: u64) -> io::Result<()> {
    while !buf.is_empty() {
        let n = std::os::windows::fs::FileExt::seek_write(f, buf, offset)?;
        if n == 0 {
            return Err(io::ErrorKind::WriteZero.into());
        }
        buf = &buf[n..];
        offset += n as u64;
    }
    Ok(())
}

/// Gives the bytes `[offset, offset + len)` of a sparse file back to the drive.
#[cfg(target_os = "linux")]
fn punch(f: &File, offset: u64, len: u64) {
    use nix::fcntl::{fallocate, FallocateFlags};
    use std::os::unix::io::AsRawFd;
    if let (Ok(off), Ok(len)) = (i64::try_from(offset), i64::try_from(len)) {
        let _ = fallocate(
            f.as_raw_fd(),
            FallocateFlags::FALLOC_FL_PUNCH_HOLE | FallocateFlags::FALLOC_FL_KEEP_SIZE,
            off,
            len,
        );
    }
}

/// Off Linux a dropped block keeps its bytes on the drive until its slot is written again.
#[cfg(not(target_os = "linux"))]
fn punch(_f: &File, _offset: u64, _len: u64) {}

/// Tells the kernel the pages of `f` are not needed in memory (after a write-back they are clean and go).
#[cfg(target_os = "linux")]
fn drop_pages(f: &File) {
    use nix::fcntl::{posix_fadvise, PosixFadviseAdvice};
    use std::os::unix::io::AsRawFd;
    let _ = posix_fadvise(f.as_raw_fd(), 0, 0, PosixFadviseAdvice::POSIX_FADV_DONTNEED);
}

/// Off Linux the pages stay until the kernel reclaims them.
#[cfg(not(target_os = "linux"))]
fn drop_pages(_f: &File) {}

/// The lengths in a map file's bytes, one per block (0: absent).
fn map_lens(raw: &[u8]) -> impl Iterator<Item = u64> + '_ {
    raw.chunks_exact(8)
        .map(|c| u64::from_le_bytes(c.try_into().unwrap_or([0; 8])) & 0xffff_ffff)
}

/// The cache files of another image, held with an exclusive lock while blocks are dropped from them.
#[cfg(unix)]
struct Other {
    key: String,
    map: nix::fcntl::Flock<File>,
    data: File,
    lens: Vec<u64>,
    used: Vec<u32>,
    block_bytes: u64,
}

#[cfg(unix)]
impl Other {
    /// Opens the files of `key` in `dir` if no mount holds them; `None` when one does or they cannot be read.
    fn open(dir: &Path, key: &str) -> Option<Self> {
        use nix::fcntl::{Flock, FlockArg};
        let rw = |ext: &str| {
            OpenOptions::new()
                .read(true)
                .write(true)
                .open(dir.join(format!("{key}.{ext}")))
                .ok()
        };
        let map = Flock::lock(rw("map")?, FlockArg::LockExclusiveNonblock).ok()?;
        let data = rw("data")?;
        let raw = std::fs::read(dir.join(format!("{key}.map"))).ok()?;
        let lens: Vec<u64> = map_lens(&raw).collect();
        if lens.is_empty() {
            return None;
        }
        let block_bytes = data.metadata().ok()?.len() / lens.len() as u64;
        let mut used = vec![0u32; lens.len()];
        if let Ok(u) = std::fs::read(dir.join(format!("{key}.use"))) {
            if u.len() == lens.len() * 4 {
                for (slot, c) in used.iter_mut().zip(u.chunks_exact(4)) {
                    *slot = u32::from_le_bytes(c.try_into().unwrap_or([0; 4]));
                }
            }
        }
        Some(Self {
            key: key.to_owned(),
            map,
            data,
            lens,
            used,
            block_bytes,
        })
    }

    /// Drops block `index`; returns its length.
    fn drop_block(&mut self, index: usize) -> u64 {
        let len = self.lens[index];
        if len == 0 || write_all_at(&self.map, &[0u8; 8], index as u64 * 8).is_err() {
            return 0;
        }
        punch(
            &self.data,
            index as u64 * self.block_bytes,
            self.block_bytes,
        );
        self.lens[index] = 0;
        len
    }
}

/// The keys of the other images with cache files in `dir`.
fn other_keys(dir: &Path, own: &str) -> Vec<String> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut keys: Vec<String> = entries
        .filter_map(std::result::Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|x| x == "map"))
        .filter_map(|p| p.file_stem().and_then(|s| s.to_str()).map(str::to_owned))
        .filter(|k| k != own)
        .collect();
    keys.sort();
    keys
}

/// Bytes the other images' files in `dir` hold, by their map files.
fn others_bytes(dir: &Path, own: &str) -> u64 {
    other_keys(dir, own)
        .iter()
        .filter_map(|k| std::fs::read(dir.join(format!("{k}.map"))).ok())
        .map(|raw| map_lens(&raw).sum::<u64>())
        .sum()
}

/// A key naming the cache files of `image`: its length and the SHA-256 of its
/// first 64 KiB.
pub fn image_key<R: ReadAt>(image: &R) -> io::Result<String> {
    let head = image.read_vec_at(0, usize::try_from(image.len().min(64 << 10)).unwrap_or(0))?;
    let mut h = Sha256::new();
    h.update(image.len().to_le_bytes());
    h.update(&head);
    let digest = h.finalize();
    Ok(digest[..8].iter().fold(String::new(), |mut s, b| {
        use std::fmt::Write as _;
        let _ = write!(s, "{b:02x}");
        s
    }))
}

impl DiskCache {
    /// Opens (or creates) the cache files for `blocks` blocks of at most
    /// `block_bytes` each. Files from a different layout are started afresh.
    pub fn open(
        dir: &Path,
        key: &str,
        blocks: usize,
        block_bytes: u64,
        limit: Limit,
    ) -> io::Result<Self> {
        std::fs::create_dir_all(dir)?;
        let open = |name: String| {
            OpenOptions::new()
                .read(true)
                .write(true)
                .create(true)
                .truncate(false)
                .open(dir.join(name))
        };
        let data = open(format!("{key}.data"))?;
        crate::io::advise_readahead_off(&data); // read a block at a time, as the image (experiment 0331)
        let map = open(format!("{key}.map"))?;
        // Held for as long as these files are open: a dropper in another mount leaves a held image alone. Taken
        // before anything is read, so a dropper at work has finished with the files first.
        #[cfg(unix)]
        let held = map
            .try_clone()
            .ok()
            .and_then(|f| nix::fcntl::Flock::lock(f, nix::fcntl::FlockArg::LockShared).ok());
        let used_file = open(format!("{key}.use"))?;
        let map_len = blocks as u64 * 8;
        let data_len = blocks as u64 * block_bytes;
        let mut raw = vec![0u8; usize::try_from(map_len).unwrap_or(0)];
        let fresh = map.metadata()?.len() != map_len || read_exact_at(&map, &mut raw, 0).is_err();
        if fresh {
            raw.fill(0);
            map.set_len(0)?;
            map.set_len(map_len)?;
            data.set_len(0)?;
            used_file.set_len(0)?;
        }
        if data.metadata()?.len() != data_len {
            data.set_len(data_len)?; // sparse: only written slots take space
        }
        let mut written = 0u64;
        let entries = raw
            .chunks_exact(8)
            .map(|c| {
                let e = u64::from_le_bytes(c.try_into().unwrap_or([0; 8]));
                if (e & 0xffff_ffff) > block_bytes {
                    return AtomicU64::new(0); // not a length this layout can have
                }
                written += e & 0xffff_ffff;
                AtomicU64::new(e)
            })
            .collect();
        let mut stamps = vec![0u8; blocks * 4];
        if used_file.metadata()?.len() != stamps.len() as u64
            || read_exact_at(&used_file, &mut stamps, 0).is_err()
        {
            stamps.fill(0);
            used_file.set_len(stamps.len() as u64)?;
        }
        let used = stamps
            .chunks_exact(4)
            .map(|c| AtomicU32::new(u32::from_le_bytes(c.try_into().unwrap_or([0; 4]))))
            .collect();
        let others = others_bytes(dir, key);
        let floor = floor_from_word(
            std::env::var("BC5_MOUNT_DISK_CACHE_FLOOR_MIB")
                .ok()
                .as_deref(),
        );
        let (total, watch, low) = match limit {
            Limit::Bytes(b) => (b, false, false),
            Limit::FromDrive => {
                let free = free_bytes(dir);
                (
                    total_from_drive(others + written, free, floor),
                    true,
                    free.is_some_and(|f| f < floor),
                )
            }
        };
        let now = minute_now();
        Ok(Self {
            dir: dir.to_path_buf(),
            key: key.to_owned(),
            data,
            map,
            used_file,
            entries,
            used,
            block_bytes,
            total,
            others: AtomicU64::new(others),
            written: AtomicU64::new(written),
            opened: now,
            watch,
            floor,
            unsynced: AtomicU64::new(0),
            write_back_every: WRITE_BACK_MIB << 20,
            writing_back: Mutex::new(()),
            written_back: AtomicU64::new(0),
            puts: AtomicU64::new(0),
            low: AtomicBool::new(low),
            room: Mutex::new(()),
            flushed: AtomicU32::new(now),
            dropped: AtomicU64::new(0),
            minute: AtomicU32::new(0),
            #[cfg(unix)]
            _held: held,
        })
    }

    /// The minute now (a test's, when it set one).
    fn now(&self) -> u32 {
        match self.minute.load(Ordering::Relaxed) {
            0 => minute_now(),
            m => m,
        }
    }

    /// Marks block `index` used now and, once a minute, writes the `.use` file.
    fn touch(&self, index: usize) {
        let now = self.now();
        if let Some(u) = self.used.get(index) {
            u.store(now, Ordering::Relaxed);
        }
        let last = self.flushed.load(Ordering::Relaxed);
        if now > last
            && self
                .flushed
                .compare_exchange(last, now, Ordering::Relaxed, Ordering::Relaxed)
                .is_ok()
        {
            self.flush_used();
        }
    }

    /// Writes the `.use` file. Errors are ignored: without it the blocks only count as old.
    fn flush_used(&self) {
        let mut raw = Vec::with_capacity(self.used.len() * 4);
        for u in &self.used {
            raw.extend_from_slice(&u.load(Ordering::Relaxed).to_le_bytes());
        }
        let _ = write_all_at(&self.used_file, &raw, 0);
    }

    /// With the limit taken from the drive: whether the drive is under its floor, read again every
    /// [`FLOOR_CHECK_EVERY`] calls.
    fn drive_low(&self) -> bool {
        if !self.watch {
            return false;
        }
        if self.puts.fetch_add(1, Ordering::Relaxed) % FLOOR_CHECK_EVERY == FLOOR_CHECK_EVERY - 1 {
            if let Some(free) = free_bytes(&self.dir) {
                self.low.store(free < self.floor, Ordering::Relaxed);
            }
        }
        self.low.load(Ordering::Relaxed)
    }

    /// The decoded block `index`, if it was stored and its CRC matches.
    pub fn get(&self, index: usize) -> Option<Vec<u8>> {
        let slot = self.entries.get(index)?;
        let e = slot.load(Ordering::Acquire);
        let len = usize::try_from(e & 0xffff_ffff).ok()?;
        if len == 0 {
            return None;
        }
        let mut buf = vec![0u8; len];
        if read_exact_at(&self.data, &mut buf, index as u64 * self.block_bytes).is_err()
            || crc32(&buf) != (e >> 32) as u32
        {
            if slot
                .compare_exchange(e, 0, Ordering::AcqRel, Ordering::Acquire)
                .is_ok()
            {
                self.written.fetch_sub(len as u64, Ordering::Relaxed);
            }
            return None;
        }
        self.touch(index);
        Some(buf)
    }

    /// Stores decoded block `index` unless it is stored already or there is no room and none can be made.
    /// Data first, then the map entry, so an entry never names unwritten data. Errors are ignored: the
    /// cache is only an optimisation.
    pub fn put(&self, index: usize, block: &[u8]) {
        let Some(slot) = self.entries.get(index) else {
            return;
        };
        let len = block.len() as u64;
        if slot.load(Ordering::Acquire) != 0 || len == 0 || len > self.block_bytes {
            return;
        }
        let low = self.drive_low();
        let held = self.others.load(Ordering::Relaxed) + self.written.load(Ordering::Relaxed);
        if (low || held + len > self.total) && !self.make_room(len, low) {
            return;
        }
        if write_all_at(&self.data, block, index as u64 * self.block_bytes).is_err() {
            return;
        }
        let e = (u64::from(crc32(block)) << 32) | len;
        if write_all_at(&self.map, &e.to_le_bytes(), index as u64 * 8).is_ok() {
            slot.store(e, Ordering::Release);
            self.written.fetch_add(len, Ordering::Relaxed);
            self.touch(index);
            if self.unsynced.fetch_add(len, Ordering::Relaxed) + len >= self.write_back_every {
                self.write_back();
            }
        }
    }

    /// Writes the data file back and drops its pages, so written blocks do not stay in memory as dirty pages.
    /// One thread at a time; another that comes meanwhile leaves it to that one.
    fn write_back(&self) {
        let Ok(_guard) = self.writing_back.try_lock() else {
            return;
        };
        self.unsynced.store(0, Ordering::Relaxed);
        if self.data.sync_data().is_ok() {
            drop_pages(&self.data);
            self.written_back.fetch_add(1, Ordering::Relaxed);
        }
    }

    /// Drops least recently used blocks so that `len` more bytes fit under the total (with `low`, the drive under
    /// its floor: so that at least `len` bytes were dropped). True when the block may be written now.
    fn make_room(&self, len: u64, low: bool) -> bool {
        let Ok(_guard) = self.room.try_lock() else {
            return false; // another thread is at it; this block is not kept
        };
        #[cfg(unix)]
        let mut others: Vec<Other> = other_keys(&self.dir, &self.key)
            .iter()
            .filter_map(|k| Other::open(&self.dir, k))
            .collect();
        // What the other images hold now: the open ones by their map files, the rest as just read.
        let other_total = others_bytes(&self.dir, &self.key);
        self.others.store(other_total, Ordering::Relaxed);
        let held = other_total + self.written.load(Ordering::Relaxed);
        let over = (held + len).saturating_sub(self.total);
        let need = if low { over.max(len) } else { over };
        if need == 0 {
            return true;
        }
        let want = need + DROP_BATCH.min(self.total / 16);
        // The oldest minutes go until `want` bytes are reached: first over the images no mount holds, then, for
        // what is still missing, over this image's blocks of earlier mounts.
        let cutoff_of = |by_minute: &BTreeMap<u32, u64>, want: u64| {
            let mut cutoff = None;
            let mut sum = 0u64;
            for (m, bytes) in by_minute {
                cutoff = Some(*m);
                sum += bytes;
                if sum >= want {
                    break;
                }
            }
            cutoff
        };
        let mut freed = 0u64;
        let mut report = Vec::new();
        #[cfg(unix)]
        {
            let mut by_minute: BTreeMap<u32, u64> = BTreeMap::new();
            for o in &others {
                for (l, m) in o.lens.iter().zip(&o.used) {
                    if *l != 0 {
                        *by_minute.entry(*m).or_default() += *l;
                    }
                }
            }
            if let Some(cutoff) = cutoff_of(&by_minute, want) {
                for o in &mut others {
                    let mut here = 0u64;
                    let mut i = 0;
                    while i < o.lens.len() && freed + here < want {
                        if o.lens[i] != 0 && o.used[i] <= cutoff {
                            here += o.drop_block(i);
                        }
                        i += 1;
                    }
                    if here != 0 {
                        report.push(format!(
                            "{here} bytes of {} last used at minute {cutoff} or before",
                            o.key
                        ));
                        freed += here;
                        self.others
                            .fetch_sub(here.min(other_total), Ordering::Relaxed);
                    }
                }
            }
        }
        if freed < want {
            let mut by_minute: BTreeMap<u32, u64> = BTreeMap::new();
            for (slot, used) in self.entries.iter().zip(&self.used) {
                let l = slot.load(Ordering::Relaxed) & 0xffff_ffff;
                let m = used.load(Ordering::Relaxed);
                if l != 0 && m < self.opened {
                    *by_minute.entry(m).or_default() += l;
                }
            }
            if let Some(cutoff) = cutoff_of(&by_minute, want - freed) {
                let mut own = 0u64;
                for (i, (slot, used)) in self.entries.iter().zip(&self.used).enumerate() {
                    if freed + own >= want {
                        break;
                    }
                    let e = slot.load(Ordering::Acquire);
                    let l = e & 0xffff_ffff;
                    let m = used.load(Ordering::Relaxed);
                    if l == 0 || m >= self.opened || m > cutoff {
                        continue;
                    }
                    if slot
                        .compare_exchange(e, 0, Ordering::AcqRel, Ordering::Acquire)
                        .is_ok()
                    {
                        let _ = write_all_at(&self.map, &[0u8; 8], i as u64 * 8);
                        punch(&self.data, i as u64 * self.block_bytes, self.block_bytes);
                        self.written.fetch_sub(l, Ordering::Relaxed);
                        own += l;
                    }
                }
                if own != 0 {
                    report.push(format!(
                        "{own} bytes of this image's earlier mounts last used at minute {cutoff} or before"
                    ));
                    freed += own;
                }
            }
        }
        if freed == 0 {
            return false; // nothing may be dropped: writing stops, as before experiment 0447
        }
        self.dropped.fetch_add(freed, Ordering::Relaxed);
        eprintln!(
            "bc5-mount: on-disk block cache at its total of {} MiB: dropped {}",
            self.total >> 20,
            report.join(", ")
        );
        freed >= need
    }

    /// Bytes of decoded data stored for this image.
    pub fn stored_bytes(&self) -> u64 {
        self.written.load(Ordering::Relaxed)
    }

    /// The total in force for the directory, all images together.
    pub fn limit_bytes(&self) -> u64 {
        self.total
    }

    /// Whether the limit was taken from the drive (then the floor is watched too).
    pub fn limit_is_from_drive(&self) -> bool {
        self.watch
    }

    /// How many times the data file was written back and its pages dropped.
    pub fn write_backs(&self) -> u64 {
        self.written_back.load(Ordering::Relaxed)
    }

    /// Bytes this mount dropped to make room, from any image.
    pub fn dropped_bytes(&self) -> u64 {
        self.dropped.load(Ordering::Relaxed)
    }
}

impl Drop for DiskCache {
    fn drop(&mut self) {
        self.flush_used();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("bc5-diskcache-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    /// An image's cache in `dir` with a total of `total` bytes, 16-byte blocks, at minute `minute`.
    fn at(dir: &Path, key: &str, total: u64, minute: u32) -> DiskCache {
        let mut c = DiskCache::open(dir, key, 8, 16, Limit::Bytes(total)).unwrap();
        c.opened = minute;
        c.minute.store(minute, Ordering::Relaxed);
        c.flushed.store(minute, Ordering::Relaxed);
        c
    }

    fn have(c: &DiskCache) -> Vec<usize> {
        (0..8).filter(|i| c.get(*i).is_some()).collect()
    }

    #[test]
    fn stores_and_reads_back_across_opens() {
        let dir = temp_dir("roundtrip");
        let c = DiskCache::open(&dir, "k", 4, 16, Limit::Bytes(1 << 20)).unwrap();
        assert!(c.get(1).is_none());
        c.put(1, &[7u8; 16]);
        c.put(3, &[9u8; 5]); // a short last block
        assert_eq!(c.get(1).unwrap(), vec![7u8; 16]);
        drop(c);
        let c = DiskCache::open(&dir, "k", 4, 16, Limit::Bytes(1 << 20)).unwrap();
        assert_eq!(c.get(1).unwrap(), vec![7u8; 16]);
        assert_eq!(c.get(3).unwrap(), vec![9u8; 5]);
        assert!(c.get(0).is_none());
        assert_eq!(c.stored_bytes(), 21);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_corrupted_block_is_dropped() {
        let dir = temp_dir("corrupt");
        let c = DiskCache::open(&dir, "k", 2, 16, Limit::Bytes(1 << 20)).unwrap();
        c.put(0, &[1u8; 16]);
        drop(c);
        let f = OpenOptions::new()
            .write(true)
            .open(dir.join("k.data"))
            .unwrap();
        write_all_at(&f, &[2u8], 3).unwrap();
        drop(f);
        let c = DiskCache::open(&dir, "k", 2, 16, Limit::Bytes(1 << 20)).unwrap();
        assert!(c.get(0).is_none(), "the CRC must reject the changed byte");
        assert_eq!(c.stored_bytes(), 0, "and its bytes no longer count");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn writing_stops_at_the_total_when_nothing_may_be_dropped() {
        let dir = temp_dir("limit");
        let c = DiskCache::open(&dir, "k", 4, 16, Limit::Bytes(20)).unwrap();
        c.put(0, &[1u8; 16]);
        c.put(1, &[1u8; 16]); // would pass 20 bytes, and block 0 is this mount's own
        assert!(c.get(0).is_some() && c.get(1).is_none());
        assert_eq!(c.dropped_bytes(), 0);
        drop(c);
        let c = DiskCache::open(&dir, "k", 8, 16, Limit::Bytes(20)).unwrap(); // other block count
        assert!(c.get(0).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_word_is_mib_and_anything_else_means_the_drive() {
        assert_eq!(Limit::from_word(Some("16")), Limit::Bytes(16 << 20));
        assert_eq!(Limit::from_word(Some(" 0 ")), Limit::Bytes(0));
        assert_eq!(Limit::from_word(Some("")), Limit::FromDrive);
        assert_eq!(Limit::from_word(Some("lots")), Limit::FromDrive);
        assert_eq!(Limit::from_word(None), Limit::FromDrive);
    }

    #[test]
    fn the_drive_total_is_a_share_of_the_space_above_the_floor() {
        let floor = 32 << 30;
        // 8 GiB stored, 100 GiB free, a floor of 32: half of 100 + 8 - 32 = 38 GiB for the directory
        assert_eq!(total_from_drive(8 << 30, Some(100 << 30), floor), 38 << 30);
        // an empty directory: half of the 68 GiB above the floor
        assert_eq!(total_from_drive(0, Some(100 << 30), floor), 34 << 30);
        // the total does not move when one image has taken it: 34 stored, 66 free
        assert_eq!(total_from_drive(34 << 30, Some(66 << 30), floor), 34 << 30);
        // at or under the floor the total is under what is stored: nothing is added without a drop
        assert_eq!(total_from_drive(8 << 30, Some(floor), floor), 4 << 30);
        assert_eq!(total_from_drive(0, Some(0), floor), 0);
        // the default floor of 32 GiB: with 100 GiB free an empty directory may take 34 GiB
        assert_eq!(floor_from_word(None), 32 << 30);
        assert_eq!(
            total_from_drive(0, Some(100 << 30), floor_from_word(None)),
            34 << 30
        );
        // the floor's word is MiB; anything else means the default
        assert_eq!(floor_from_word(Some("1024")), 1 << 30);
        assert_eq!(floor_from_word(Some("")), 32 << 30);
        // free space not known: the old fixed limit
        assert_eq!(total_from_drive(0, None, floor), FALLBACK_LIMIT_MIB << 20);
    }

    #[test]
    fn a_fixed_limit_does_not_watch_the_drive_and_a_drive_limit_does() {
        let dir = temp_dir("watch");
        let c = DiskCache::open(&dir, "k", 4, 16, Limit::Bytes(64)).unwrap();
        assert!(!c.limit_is_from_drive());
        assert_eq!(c.limit_bytes(), 64);
        drop(c);
        let c = DiskCache::open(&dir, "k", 4, 16, Limit::FromDrive).unwrap();
        assert!(c.limit_is_from_drive());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_minutes_of_use_survive_a_reopen_and_a_read_renews_them() {
        let dir = temp_dir("use");
        let c = at(&dir, "k", 1 << 20, 10);
        c.put(0, &[1u8; 16]);
        c.put(1, &[2u8; 16]);
        drop(c);
        let c = at(&dir, "k", 1 << 20, 20);
        assert_eq!(c.used[0].load(Ordering::Relaxed), 10);
        assert!(c.get(1).is_some());
        drop(c);
        let c = at(&dir, "k", 1 << 20, 30);
        assert_eq!(c.used[0].load(Ordering::Relaxed), 10);
        assert_eq!(c.used[1].load(Ordering::Relaxed), 20);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn written_blocks_are_written_back_and_read_the_same() {
        let dir = temp_dir("writeback");
        let mut c = DiskCache::open(&dir, "k", 8, 16, Limit::Bytes(1 << 20)).unwrap();
        c.write_back_every = 40; // after every third block of 16 bytes
        for i in 0..8u8 {
            c.put(usize::from(i), &[i + 1; 16]);
        }
        assert_eq!(c.write_backs(), 2, "after the third and the sixth block");
        for i in 0..8u8 {
            assert_eq!(c.get(usize::from(i)).unwrap(), vec![i + 1; 16]);
        }
        drop(c);
        let c = DiskCache::open(&dir, "k", 8, 16, Limit::Bytes(1 << 20)).unwrap();
        assert_eq!(c.get(7).unwrap(), vec![8u8; 16]);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The order: the oldest minutes go first, across images, and no more than the batch.
    #[cfg(unix)]
    #[test]
    fn the_least_recently_used_blocks_of_a_closed_image_make_room() {
        let dir = temp_dir("lru");
        let total = 64; // four blocks; the batch is a sixteenth of it, 4 bytes
        let a = at(&dir, "a", total, 10);
        for (i, minute) in [(0usize, 10u32), (1, 13), (2, 11), (3, 12)] {
            a.minute.store(minute, Ordering::Relaxed);
            a.put(i, &[i as u8 + 1; 16]);
        }
        drop(a);
        let b = at(&dir, "b", total, 20);
        b.put(5, &[9u8; 16]); // needs 16 bytes: 16 + 4 wanted, so the two oldest blocks of a go
        assert_eq!(b.get(5).unwrap(), vec![9u8; 16]);
        assert_eq!(b.dropped_bytes(), 32);
        drop(b);
        let a = at(&dir, "a", total, 30);
        assert_eq!(
            have(&a),
            vec![1, 3],
            "minutes 10 and 11 went, 12 and 13 stayed"
        );
        assert_eq!(a.stored_bytes(), 32);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Whichever image was played last is served: the first one back drops the second's blocks in turn.
    #[cfg(unix)]
    #[test]
    fn two_images_take_turns_under_one_total() {
        let dir = temp_dir("turns");
        let total = 64;
        let a = at(&dir, "a", total, 10);
        (0..4).for_each(|i| a.put(i, &[1u8; 16]));
        drop(a);
        let b = at(&dir, "b", total, 20);
        (0..4).for_each(|i| b.put(i, &[2u8; 16]));
        assert_eq!(have(&b), vec![0, 1, 2, 3], "the second image got its room");
        drop(b);
        let a = at(&dir, "a", total, 30);
        assert!(have(&a).is_empty(), "the first image's old blocks all went");
        (0..4).for_each(|i| a.put(i, &[3u8; 16]));
        assert_eq!(have(&a), vec![0, 1, 2, 3], "and it is served again");
        drop(a);
        let b = at(&dir, "b", total, 40);
        assert!(have(&b).is_empty());
        assert!(others_bytes(&dir, "none") <= total);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Another closed image's blocks go before this image's own of an earlier mount, whatever their minutes.
    #[cfg(unix)]
    #[test]
    fn another_images_blocks_go_before_this_images_older_ones() {
        let dir = temp_dir("prefer");
        let total = 64;
        let a = at(&dir, "a", total, 10);
        (0..2).for_each(|i| a.put(i, &[1u8; 16]));
        drop(a);
        let b = at(&dir, "b", total, 20);
        (0..2).for_each(|i| b.put(i, &[2u8; 16]));
        drop(b);
        let a = at(&dir, "a", total, 30);
        a.put(4, &[3u8; 16]); // the directory is full: b's blocks of minute 20 go, a's of minute 10 stay
        assert_eq!(have(&a), vec![0, 1, 4]);
        drop(a);
        let b = at(&dir, "b", total, 40);
        assert!(have(&b).is_empty());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Nothing of an image a mount holds is dropped, and nothing this mount has used.
    #[cfg(unix)]
    #[test]
    fn an_open_image_and_this_mounts_own_blocks_are_left_alone() {
        let dir = temp_dir("held");
        let total = 64;
        let a = at(&dir, "a", total, 10);
        (0..4).for_each(|i| a.put(i, &[1u8; 16]));
        let b = at(&dir, "b", total, 20);
        b.put(0, &[2u8; 16]); // a is open in another mount: no room can be made
        assert!(b.get(0).is_none());
        assert_eq!(b.dropped_bytes(), 0);
        assert_eq!(have(&a), vec![0, 1, 2, 3]);
        drop(b);
        // a alone at its total: its own blocks of this mount stay, a new one is not kept
        a.put(4, &[3u8; 16]);
        assert_eq!(have(&a), vec![0, 1, 2, 3]);
        drop(a);
        // a again, later: the blocks of the earlier mount go, oldest first, those read in this mount stay
        let a = at(&dir, "a", total, 30);
        assert!(a.get(2).is_some());
        a.put(4, &[4u8; 16]);
        assert_eq!(
            have(&a),
            vec![2, 3, 4],
            "0 and 1 (minute 10) went; 2 was read at minute 30"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Under the floor a block is added only when at least as much was dropped: the directory does not grow.
    #[cfg(unix)]
    #[test]
    fn under_the_floor_the_directory_does_not_grow() {
        let dir = temp_dir("floor");
        let a = at(&dir, "a", 1 << 20, 10);
        (0..2).for_each(|i| a.put(i, &[1u8; 16]));
        drop(a);
        let mut b = at(&dir, "b", 1 << 20, 20); // far under its total
        b.watch = true;
        b.low.store(true, Ordering::Relaxed); // the drive is under its floor
        let before = others_bytes(&dir, "none");
        b.put(0, &[2u8; 16]);
        assert!(
            b.get(0).is_some(),
            "kept, because a's old blocks were dropped for it"
        );
        assert!(b.dropped_bytes() >= 16);
        assert!(others_bytes(&dir, "b") + b.stored_bytes() <= before);
        // with nothing left to drop a block is not kept under the floor
        b.put(1, &[2u8; 16]);
        b.put(2, &[2u8; 16]);
        b.put(3, &[2u8; 16]);
        assert!(others_bytes(&dir, "b") + b.stored_bytes() <= before);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
