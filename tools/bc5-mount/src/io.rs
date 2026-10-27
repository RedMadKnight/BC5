// SPDX-License-Identifier: GPL-2.0-only
//! Positional reads. Every layer reads through [`ReadAt`] so the same parsers
//! run on a file, on an in-memory fixture, or on the decoded PFSC stream.

use std::fs::File;
use std::io;
use std::path::Path;
use std::sync::Arc;

/// A byte source with a fixed length that can be read at any offset from
/// several threads at once.
pub trait ReadAt: Send + Sync {
    /// Total length in bytes.
    fn len(&self) -> u64;

    /// Reads up to `buf.len()` bytes starting at `offset`; returns 0 at or
    /// past the end.
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize>;

    /// True when the source has no bytes.
    fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Fills `buf` completely or fails with `UnexpectedEof`.
    fn read_exact_at(&self, mut offset: u64, mut buf: &mut [u8]) -> io::Result<()> {
        while !buf.is_empty() {
            let n = self.read_at(offset, buf)?;
            if n == 0 {
                return Err(io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    format!("read past end of source at offset {offset}"),
                ));
            }
            buf = &mut buf[n..];
            offset += n as u64;
        }
        Ok(())
    }

    /// Convenience: allocates and fills a vector of `len` bytes.
    fn read_vec_at(&self, offset: u64, len: usize) -> io::Result<Vec<u8>> {
        let mut v = vec![0u8; len];
        self.read_exact_at(offset, &mut v)?;
        Ok(v)
    }

    /// Hint that `[offset, offset + len)` is read soon (decode-ahead). A
    /// decoding layer decodes the blocks that are neither cached nor being
    /// decoded by another reader, and never waits for one; plain sources do
    /// nothing.
    fn prefetch(&self, offset: u64, len: u64) -> io::Result<()> {
        let _ = (offset, len);
        Ok(())
    }
}

impl<T: ReadAt + ?Sized> ReadAt for &T {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
    }
    fn prefetch(&self, offset: u64, len: u64) -> io::Result<()> {
        (**self).prefetch(offset, len)
    }
}

impl<T: ReadAt + ?Sized> ReadAt for Arc<T> {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
    }
    fn prefetch(&self, offset: u64, len: u64) -> io::Result<()> {
        (**self).prefetch(offset, len)
    }
}

impl<T: ReadAt + ?Sized> ReadAt for Box<T> {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
    }
    fn prefetch(&self, offset: u64, len: u64) -> io::Result<()> {
        (**self).prefetch(offset, len)
    }
}

impl ReadAt for [u8] {
    fn len(&self) -> u64 {
        <[u8]>::len(self) as u64
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        let Ok(start) = usize::try_from(offset) else {
            return Ok(0);
        };
        if start >= <[u8]>::len(self) {
            return Ok(0);
        }
        let n = buf.len().min(<[u8]>::len(self) - start);
        buf[..n].copy_from_slice(&self[start..start + n]);
        Ok(n)
    }
}

impl ReadAt for Vec<u8> {
    fn len(&self) -> u64 {
        self.as_slice().len() as u64
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        self.as_slice().read_at(offset, buf)
    }
}

/// A file opened for positional reads. The length is captured at open time;
/// containers are immutable while mounted. Its reads go to the
/// `BC5_MOUNT_TRACE` trace when that is set (ADR 0014), unless it was opened
/// with [`FileSource::open_untraced`]. The kernel's readahead is turned off for
/// it, unless `BC5_MOUNT_READAHEAD=1` (`advise_readahead_off`).
#[derive(Debug)]
pub struct FileSource {
    file: File,
    len: u64,
    traced: bool,
}

impl FileSource {
    /// Opens `path` read-only.
    pub fn open(path: impl AsRef<Path>) -> io::Result<Self> {
        Self::open_with(path, true)
    }

    /// Opens `path` read-only, its reads left out of the `BC5_MOUNT_TRACE`
    /// trace (the preload's own reads, ADR 0014).
    pub fn open_untraced(path: impl AsRef<Path>) -> io::Result<Self> {
        Self::open_with(path, false)
    }

    fn open_with(path: impl AsRef<Path>, traced: bool) -> io::Result<Self> {
        let file = File::open(path)?;
        let len = file.metadata()?.len();
        advise_readahead_off(&file);
        Ok(Self { file, len, traced })
    }
}

/// Turns the kernel's readahead off for `file` alone (`POSIX_FADV_RANDOM`),
/// unless `BC5_MOUNT_READAHEAD=1` keeps it. The image and the disk cache's data
/// file are read a block at a time, in pieces of tens of KiB, and on the dev
/// box's btrfs (bdi readahead 4096 KiB) the readahead fetched 78 % more than
/// was asked for, all of it through a page cache the game was short of (F396).
/// With the box's readahead at 128 KiB the surplus fell to 7 % and the memory
/// stall by five sixths (F397). This does the same for these files alone, with
/// no root (experiment 0331). The advice is best effort: a failure leaves the
/// readahead as it was.
pub(crate) fn advise_readahead_off(file: &File) {
    if std::env::var_os("BC5_MOUNT_READAHEAD").as_deref() != Some(std::ffi::OsStr::new("1")) {
        advise_random(file);
    }
}

#[cfg(target_os = "linux")]
fn advise_random(file: &File) {
    use nix::fcntl::{posix_fadvise, PosixFadviseAdvice};
    use std::os::unix::io::AsRawFd;
    let _ = posix_fadvise(
        file.as_raw_fd(),
        0,
        0,
        PosixFadviseAdvice::POSIX_FADV_RANDOM,
    );
}

#[cfg(not(target_os = "linux"))]
fn advise_random(_file: &File) {}

impl ReadAt for FileSource {
    fn len(&self) -> u64 {
        self.len
    }

    #[cfg(unix)]
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        use std::os::unix::fs::FileExt;
        let n = self.file.read_at(buf, offset)?;
        if self.traced {
            crate::preload::trace(offset, n as u64);
        }
        Ok(n)
    }

    #[cfg(windows)]
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        use std::os::windows::fs::FileExt;
        let n = self.file.seek_read(buf, offset)?;
        if self.traced {
            crate::preload::trace(offset, n as u64);
        }
        Ok(n)
    }
}

/// A window `[offset, offset + len)` onto another source.
#[derive(Debug, Clone)]
pub struct Window<R> {
    inner: R,
    offset: u64,
    len: u64,
}

impl<R: ReadAt> Window<R> {
    /// Creates a window; fails if it does not fit inside `inner`.
    pub fn new(inner: R, offset: u64, len: u64) -> io::Result<Self> {
        let end = offset
            .checked_add(len)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "window overflows"))?;
        if end > inner.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!(
                    "window [{offset}, {end}) exceeds source length {}",
                    inner.len()
                ),
            ));
        }
        Ok(Self { inner, offset, len })
    }
}

impl<R: ReadAt> ReadAt for Window<R> {
    fn len(&self) -> u64 {
        self.len
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        if offset >= self.len {
            return Ok(0);
        }
        let avail = usize::try_from(self.len - offset).unwrap_or(usize::MAX);
        let n = buf.len().min(avail);
        self.inner.read_at(self.offset + offset, &mut buf[..n])
    }
    fn prefetch(&self, offset: u64, len: u64) -> io::Result<()> {
        if offset >= self.len {
            return Ok(());
        }
        let n = len.min(self.len - offset);
        self.inner.prefetch(self.offset + offset, n)
    }
}

/// Little-endian field access on a byte slice with bounds checks. Every
/// accessor returns `None` instead of panicking on a short buffer.
#[derive(Debug, Clone, Copy)]
pub struct Le<'a>(pub &'a [u8]);

impl Le<'_> {
    fn bytes<const N: usize>(self, off: usize) -> Option<[u8; N]> {
        let end = off.checked_add(N)?;
        self.0.get(off..end)?.try_into().ok()
    }
    /// u8 at `off`.
    pub fn u8(self, off: usize) -> Option<u8> {
        self.0.get(off).copied()
    }
    /// u16 at `off`.
    pub fn u16(self, off: usize) -> Option<u16> {
        self.bytes(off).map(u16::from_le_bytes)
    }
    /// u32 at `off`.
    pub fn u32(self, off: usize) -> Option<u32> {
        self.bytes(off).map(u32::from_le_bytes)
    }
    /// i32 at `off`.
    pub fn i32(self, off: usize) -> Option<i32> {
        self.bytes(off).map(i32::from_le_bytes)
    }
    /// u64 at `off`.
    pub fn u64(self, off: usize) -> Option<u64> {
        self.bytes(off).map(u64::from_le_bytes)
    }
    /// i64 at `off`.
    pub fn i64(self, off: usize) -> Option<i64> {
        self.bytes(off).map(i64::from_le_bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slice_reads_are_bounded() {
        let data = vec![1u8, 2, 3, 4, 5];
        let mut buf = [0u8; 3];
        assert_eq!(data.read_at(3, &mut buf).unwrap(), 2);
        assert_eq!(&buf[..2], &[4, 5]);
        assert_eq!(data.read_at(5, &mut buf).unwrap(), 0);
        assert_eq!(data.read_at(u64::MAX, &mut buf).unwrap(), 0);
        assert!(data.read_exact_at(4, &mut buf).is_err());
    }

    #[test]
    fn window_clamps_to_its_range() {
        let data: Vec<u8> = (0..10).collect();
        let w = Window::new(&data, 2, 5).unwrap();
        assert_eq!(w.read_vec_at(0, 5).unwrap(), vec![2, 3, 4, 5, 6]);
        assert!(w.read_vec_at(3, 3).is_err());
        assert!(Window::new(&data, 8, 5).is_err());
    }

    #[test]
    fn le_accessors_never_panic() {
        let le = Le(&[1, 0, 0, 0, 2]);
        assert_eq!(le.u32(0), Some(1));
        assert_eq!(le.u32(2), None);
        assert_eq!(le.u8(4), Some(2));
        assert_eq!(le.u64(usize::MAX), None);
    }

    #[test]
    fn file_reads_are_unchanged_by_the_random_advice() {
        let data: Vec<u8> = (0..300_000u32).map(|i| (i * 7 % 251) as u8).collect();
        let path = std::env::temp_dir().join(format!("bc5-mount-io-{}.bin", std::process::id()));
        std::fs::write(&path, &data).unwrap();
        let f = FileSource::open(&path).unwrap();
        assert_eq!(f.len(), data.len() as u64);
        let mut buf = vec![0u8; 4096];
        for off in [0u64, 65_536, 131_000, 295_000] {
            let n = f.read_at(off, &mut buf).unwrap();
            assert_eq!(&buf[..n], &data[off as usize..off as usize + n]);
        }
        // The advice again on a fresh descriptor, as the preload's own open does.
        let g = File::open(&path).unwrap();
        advise_random(&g);
        assert_eq!(
            FileSource::open_untraced(&path)
                .unwrap()
                .read_vec_at(131_000, 100)
                .unwrap(),
            &data[131_000..131_100]
        );
        std::fs::remove_file(&path).unwrap();
    }
}
