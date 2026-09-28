// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount`: read-only access to `.ffpfsc` containers.
//!
//! Layering, bottom-up (see `docs/formats/ffpfsc.md`):
//!
//! * [`pfs`] — the PFS v2 image: superblock, inode table, directory entries.
//! * [`pfsc`] — the PFSC stream stored in the payload inode: 64 KiB logical
//!   blocks, each raw or zlib-compressed, exposed as one [`io::ReadAt`].
//! * [`exfat`] — the exFAT volume inside the PFSC stream: the game's `app0`.
//! * [`container`] — ties the three together and answers "inspect".
//! * [`fixture`] — writes synthetic containers for tests (never real dumps).
//! * `fuse` — the FUSE glue (Linux, feature `fuse`).
//!
//! Every parser rejects malformed input with [`Error`] and never panics.

pub mod container;
pub mod error;
pub mod exfat;
pub mod fixture;
pub mod io;
pub mod pfs;
pub mod pfsc;
pub mod verify;

#[cfg(all(feature = "fuse", target_os = "linux"))]
pub mod fuse;

pub use error::{Error, Result};

/// Crate version, as reported by `bc5-mount --version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
