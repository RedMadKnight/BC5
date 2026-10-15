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
}

impl<T: ReadAt + ?Sized> ReadAt for &T {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
    }
}

impl<T: ReadAt + ?Sized> ReadAt for Arc<T> {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
    }
}

impl<T: ReadAt + ?Sized> ReadAt for Box<T> {
    fn len(&self) -> u64 {
        (**self).len()
    }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        (**self).read_at(offset, buf)
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
/// containers are immutable while mounted.
#[derive(Debug)]
pub struct FileSource {
    file: File,
    len: u64,
}

impl FileSource {
    /// Opens `path` read-only.
    pub fn open(path: impl AsRef<Path>) -> io::Result<Self> {
        let file = File::open(path)?;
        let len = file.metadata()?.len();
        Ok(Self { file, len })
    }
}

impl ReadAt for FileSource {
    fn len(&self) -> u64 {
        self.len
    }

    #[cfg(unix)]
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        use std::os::unix::fs::FileExt;
        self.file.read_at(buf, offset)
    }

    #[cfg(windows)]
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> io::Result<usize> {
        use std::os::windows::fs::FileExt;
        self.file.seek_read(buf, offset)
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
}
