// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount`: read-only access to `.ffpfsc` containers (see `docs/formats/ffpfsc.md`).

pub mod error;
pub mod exfat;
pub mod io;
pub mod pfs;
pub mod pfsc;

pub use error::{Error, Result};

/// Crate version, as reported by `bc5-mount --version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
