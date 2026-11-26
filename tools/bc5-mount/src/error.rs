// SPDX-License-Identifier: GPL-2.0-only
//! One error type for every layer. Parsers report malformed input through
//! [`Error::Format`] with the layer name, and never panic.

/// Errors produced while opening or reading a container.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The underlying file could not be read.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    /// The input violates the format described in `docs/formats/ffpfsc.md`.
    #[error("{layer}: {msg}")]
    Format {
        /// `pfs`, `pfsc`, `exfat` or `container`.
        layer: &'static str,
        /// What was found and, where useful, what was expected.
        msg: String,
    },
    /// Valid input that this implementation deliberately does not handle.
    #[error("unsupported: {0}")]
    Unsupported(String),
    /// A path lookup failed.
    #[error("not found: {0}")]
    NotFound(String),
}

/// Result alias used throughout the crate.
pub type Result<T> = std::result::Result<T, Error>;

impl Error {
    /// Builds a [`Error::Format`] for `layer`.
    pub fn format(layer: &'static str, msg: impl Into<String>) -> Self {
        Error::Format {
            layer,
            msg: msg.into(),
        }
    }
}

/// `bail!`-style early return with a formatted [`Error::Format`].
macro_rules! bail_format {
    ($layer:expr, $($arg:tt)*) => {
        return Err($crate::error::Error::format($layer, format!($($arg)*)))
    };
}
pub(crate) use bail_format;
