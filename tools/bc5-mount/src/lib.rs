// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-mount`: read-only access to `.ffpfsc` containers.
//!
//! Layering (see `docs/formats/ffpfsc.md`, not written yet): PFS v2 image ->
//! PFSC-compressed inner file -> exFAT image -> `app0` tree. No format parser
//! exists yet; phase 0a step 1 (format research) comes first.

/// Crate version, as reported by `bc5-mount --version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
