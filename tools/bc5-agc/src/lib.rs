// SPDX-License-Identifier: GPL-2.0-only
//! `bc5-agc`: decodes PM4 command streams as PS5 AGC submits them
//! (`docs/formats/agc.md`). Three layers:
//!
//! * [`pm4`] — packet framing (types 0/2/3), never panics, reports where a
//!   stream stops making sense;
//! * [`regdb`] — GFX10 register names and PM4 opcode names, vendored from
//!   Mesa (`regdb/NOTICE.md`);
//! * [`decode`] — packets → events (register writes, draws, …) and the
//!   report that counts unknown opcodes and unresolved register offsets;
//! * [`policy`] — the submission policy of ADR 0005 (pass / drop / rewrite),
//!   read from `backend/policy/pm4-policy.tsv`, applied offline by `check`.

pub mod decode;
pub mod pm4;
pub mod policy;
pub mod regdb;

/// Crate version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
