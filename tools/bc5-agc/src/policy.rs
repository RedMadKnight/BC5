// SPDX-License-Identifier: GPL-2.0-only
//! The submission policy of ADR 0005 (`backend/policy/pm4-policy.tsv`): for every packet of a
//! console-format stream, would the BC5 backend pass it to the CP as-is, drop it (NOP it) or
//! rewrite it? `bc5-agc check` applies the table offline so the numbers exist before anything
//! is submitted.

use std::collections::BTreeMap;
use std::fmt::Write;
use std::sync::OnceLock;

use crate::pm4::{Packet, Parsed};
use crate::regdb::{Block, RegDb};

const POLICY_TSV: &str = include_str!("../../../backend/policy/pm4-policy.tsv");

/// What the backend does with a packet or a register write.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Verdict {
    /// Copied verbatim into the scratch IB.
    Pass,
    /// Copied with a field changed (CU mask AND, interrupt select cleared).
    Rewrite,
    /// A `SET_*_REG` packet whose registers have different verdicts: the backend splits it.
    Split,
    /// Replaced by NOPs of the same length.
    Drop,
}

impl Verdict {
    fn parse(s: &str) -> Option<Self> {
        match s {
            "pass" => Some(Verdict::Pass),
            "rewrite" => Some(Verdict::Rewrite),
            "drop" => Some(Verdict::Drop),
            _ => None,
        }
    }

    /// Short label for reports.
    pub fn label(self) -> &'static str {
        match self {
            Verdict::Pass => "pass",
            Verdict::Rewrite => "rewrite",
            Verdict::Split => "split",
            Verdict::Drop => "drop",
        }
    }
}

/// The parsed table.
#[derive(Debug)]
pub struct Policy {
    ops: BTreeMap<u8, Verdict>,
    /// `(first, last, verdict)` MMIO dword ranges, inclusive.
    regs: Vec<(u32, u32, Verdict)>,
    default_op: Verdict,
    default_reg: Verdict,
    type0: Verdict,
}

fn parse_hex(s: &str) -> Option<u32> {
    u32::from_str_radix(s.trim().trim_start_matches("0x"), 16).ok()
}

impl Policy {
    /// Parses a policy table; `Err` names the first bad line.
    pub fn parse(text: &str) -> Result<Self, String> {
        let mut p = Policy {
            ops: BTreeMap::new(),
            regs: Vec::new(),
            default_op: Verdict::Drop,
            default_reg: Verdict::Pass,
            type0: Verdict::Drop,
        };
        for (n, line) in text.lines().enumerate() {
            let line = line.trim_end();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let cols: Vec<&str> = line.split('\t').collect();
            let bad = |what: &str| format!("pm4-policy.tsv line {}: {what}", n + 1);
            match cols.as_slice() {
                ["default-op", v, ..] => {
                    p.default_op = Verdict::parse(v).ok_or_else(|| bad("verdict"))?;
                }
                ["default-reg", v, ..] => {
                    p.default_reg = Verdict::parse(v).ok_or_else(|| bad("verdict"))?;
                }
                ["type0", v, ..] => p.type0 = Verdict::parse(v).ok_or_else(|| bad("verdict"))?,
                ["op", key, v, ..] => {
                    let op = parse_hex(key)
                        .filter(|&o| o <= 0xff)
                        .ok_or_else(|| bad("opcode"))?;
                    p.ops
                        .insert(op as u8, Verdict::parse(v).ok_or_else(|| bad("verdict"))?);
                }
                ["reg", key, v, ..] => {
                    let (a, b) = match key.split_once('-') {
                        Some((a, b)) => (parse_hex(a), parse_hex(b)),
                        None => (parse_hex(key), parse_hex(key)),
                    };
                    let (a, b) = (
                        a.ok_or_else(|| bad("register"))?,
                        b.ok_or_else(|| bad("register"))?,
                    );
                    p.regs
                        .push((a, b, Verdict::parse(v).ok_or_else(|| bad("verdict"))?));
                }
                _ => return Err(bad("unknown kind")),
            }
        }
        Ok(p)
    }

    /// The table shipped with the repository.
    pub fn get() -> &'static Policy {
        static POLICY: OnceLock<Policy> = OnceLock::new();
        POLICY.get_or_init(|| Policy::parse(POLICY_TSV).expect("pm4-policy.tsv is well-formed"))
    }

    /// Verdict for one register write (MMIO dword offset).
    pub fn register(&self, mm: u32) -> Verdict {
        self.regs
            .iter()
            .find(|(a, b, _)| (*a..=*b).contains(&mm))
            .map_or(self.default_reg, |&(_, _, v)| v)
    }

    /// Verdict for a whole packet. `SET_*_REG` packets take the verdict of their registers:
    /// all equal → that verdict; mixed → `Split`.
    pub fn packet(&self, packet: &Packet) -> Verdict {
        match packet {
            Packet::Type2 => Verdict::Pass,
            Packet::Type0 { .. } => self.type0,
            Packet::Type3 {
                opcode, payload, ..
            } => {
                let op_verdict = self.ops.get(opcode).copied().unwrap_or(self.default_op);
                // WRITE_DATA with DST_SEL 0 (bits 11:8 of the control dword) writes a register;
                // the register policy covers SET_* only, so it is dropped (mirrors policy.cpp).
                if *opcode == 0x37 && payload.first().is_some_and(|c| c & 0xf00 == 0) {
                    return Verdict::Drop;
                }
                let is_plain_set = matches!(opcode, 0x68 | 0x69 | 0x76 | 0x79 | 0x9b);
                if op_verdict != Verdict::Pass || !is_plain_set {
                    return op_verdict;
                }
                let (Some(block), Some(first)) = (Block::for_opcode(*opcode), payload.first())
                else {
                    return op_verdict;
                };
                let offset = first & 0xffff;
                let mut verdicts: Vec<Verdict> = (0..payload.len().saturating_sub(1))
                    .map(|i| self.register(block.base() + offset + i as u32))
                    .collect();
                verdicts.dedup();
                match verdicts.as_slice() {
                    [] => Verdict::Pass,
                    [one] => *one,
                    _ => Verdict::Split,
                }
            }
        }
    }
}

/// Counts of what the policy would do over one or more streams.
#[derive(Debug, Default, Clone)]
pub struct Check {
    /// Streams checked.
    pub streams: usize,
    /// Packets (all types).
    pub packets: u64,
    /// Dwords that would reach the CP unchanged or rewritten.
    pub dwords_kept: u64,
    /// Dwords replaced by NOPs.
    pub dwords_dropped: u64,
    /// Verdict → packets.
    pub by_verdict: BTreeMap<Verdict, u64>,
    /// Opcode → packets dropped.
    pub dropped_ops: BTreeMap<u8, u64>,
    /// Opcode → packets split.
    pub split_ops: BTreeMap<u8, u64>,
    /// MMIO offset → register writes dropped (inside dropped or split packets).
    pub dropped_regs: BTreeMap<u32, u64>,
    /// MMIO offset → register writes rewritten.
    pub rewritten_regs: BTreeMap<u32, u64>,
    /// Opcode → packets rewritten (non-register rewrites).
    pub rewritten_ops: BTreeMap<u8, u64>,
    /// `WAIT_REG_MEM[64]` packets dropped because nothing earlier in the stream writes their label.
    pub unsatisfiable_waits: u64,
}

impl Check {
    /// Applies the policy to one parsed stream.
    pub fn add(&mut self, policy: &Policy, parsed: &Parsed) {
        self.streams += 1;
        // Labels written earlier in this stream (mirrors policy.cpp: WRITE_DATA to memory,
        // RELEASE_MEM, EVENT_WRITE_EOP, ATOMIC_MEM); a wait on anything else is dropped.
        let mut written: std::collections::HashSet<u64> = std::collections::HashSet::new();
        let addr = |lo: u32, hi: u32| (u64::from(lo) & !3) | (u64::from(hi & 0xffff) << 32);
        for (_, packet) in &parsed.packets {
            self.packets += 1;
            let mut v = policy.packet(packet);
            if let Packet::Type3 {
                opcode, payload, ..
            } = packet
            {
                if matches!(opcode, 0x3c | 0x93) && payload.len() >= 3 && v != Verdict::Drop {
                    let mem_space = (payload[0] >> 4) & 1 != 0;
                    if !mem_space || !written.contains(&addr(payload[1], payload[2])) {
                        v = Verdict::Drop;
                        self.unsatisfiable_waits += 1;
                    }
                }
                if v != Verdict::Drop {
                    let dst_sel = (payload.first().copied().unwrap_or(0) >> 8) & 0xf;
                    let label = match opcode {
                        0x37 if payload.len() >= 3 && matches!(dst_sel, 1 | 2 | 5) => {
                            addr(payload[1], payload[2])
                        }
                        0x49 if payload.len() >= 5 => addr(payload[3], payload[4]),
                        0x47 | 0x1e if payload.len() >= 3 => addr(payload[1], payload[2]),
                        _ => 0,
                    };
                    if label != 0 {
                        written.insert(label);
                    }
                }
            }
            *self.by_verdict.entry(v).or_default() += 1;
            let len = packet.len() as u64;
            match v {
                Verdict::Drop => self.dwords_dropped += len,
                _ => self.dwords_kept += len,
            }
            if let Packet::Type3 {
                opcode, payload, ..
            } = packet
            {
                match v {
                    Verdict::Drop => *self.dropped_ops.entry(*opcode).or_default() += 1,
                    Verdict::Split => *self.split_ops.entry(*opcode).or_default() += 1,
                    Verdict::Rewrite if !matches!(opcode, 0x68 | 0x69 | 0x76 | 0x79 | 0x9b) => {
                        *self.rewritten_ops.entry(*opcode).or_default() += 1;
                    }
                    _ => {}
                }
                if matches!(v, Verdict::Split | Verdict::Rewrite | Verdict::Drop)
                    && matches!(opcode, 0x68 | 0x69 | 0x76 | 0x79 | 0x9b)
                {
                    if let (Some(block), Some(first)) =
                        (Block::for_opcode(*opcode), payload.first())
                    {
                        let offset = first & 0xffff;
                        for i in 0..payload.len().saturating_sub(1) {
                            let mm = block.base() + offset + i as u32;
                            match policy.register(mm) {
                                Verdict::Drop => *self.dropped_regs.entry(mm).or_default() += 1,
                                Verdict::Rewrite => {
                                    *self.rewritten_regs.entry(mm).or_default() += 1;
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
    }

    /// Human-readable summary.
    pub fn render(&self) -> String {
        let db = RegDb::get();
        let mut s = String::new();
        let _ = writeln!(
            s,
            "streams: {}  packets: {}  dwords kept: {}  dwords dropped: {}",
            self.streams, self.packets, self.dwords_kept, self.dwords_dropped
        );
        for (v, n) in &self.by_verdict {
            let _ = writeln!(s, "  {:<8} {n}", v.label());
        }
        let _ = writeln!(s, "  waits dropped (label never written in the stream): {}", self.unsatisfiable_waits);
        let name = |op: &u8| db.opcode_name(*op).unwrap_or("-");
        let _ = writeln!(s, "dropped packets by opcode ({}):", self.dropped_ops.len());
        for (op, n) in &self.dropped_ops {
            let _ = writeln!(s, "  {op:#04x} {:<28} {n}", name(op));
        }
        let _ = writeln!(
            s,
            "rewritten packets by opcode ({}):",
            self.rewritten_ops.len()
        );
        for (op, n) in &self.rewritten_ops {
            let _ = writeln!(s, "  {op:#04x} {:<28} {n}", name(op));
        }
        let _ = writeln!(
            s,
            "split SET_*_REG packets by opcode ({}):",
            self.split_ops.len()
        );
        for (op, n) in &self.split_ops {
            let _ = writeln!(s, "  {op:#04x} {:<28} {n}", name(op));
        }
        let rname = |mm: &u32| db.register_name(*mm).unwrap_or("(unresolved)");
        let _ = writeln!(s, "dropped register writes ({}):", self.dropped_regs.len());
        for (mm, n) in &self.dropped_regs {
            let _ = writeln!(s, "  mm {mm:#07x} {:<36} {n}", rname(mm));
        }
        let _ = writeln!(
            s,
            "rewritten register writes ({}):",
            self.rewritten_regs.len()
        );
        for (mm, n) in &self.rewritten_regs {
            let _ = writeln!(s, "  mm {mm:#07x} {:<36} {n}", rname(mm));
        }
        s
    }
}

#[cfg(test)]
#[allow(clippy::unreadable_literal)]
mod tests {
    use super::*;
    use crate::pm4::parse;

    #[test]
    fn shipped_table_parses_and_has_the_known_entries() {
        let p = Policy::get();
        assert_eq!(
            p.packet(&Packet::Type3 {
                opcode: 0x10,
                predicate: false,
                shader_type: false,
                payload: vec![]
            }),
            Verdict::Pass
        );
        assert_eq!(
            p.packet(&Packet::Type3 {
                opcode: 0x8e,
                predicate: false,
                shader_type: false,
                payload: vec![0; 4]
            }),
            Verdict::Drop
        );
        assert_eq!(
            p.packet(&Packet::Type3 {
                opcode: 0xee,
                predicate: false,
                shader_type: false,
                payload: vec![]
            }),
            Verdict::Drop
        );
        assert_eq!(
            p.packet(&Packet::Type0 {
                base: 0,
                values: vec![1]
            }),
            Verdict::Drop
        );
        assert_eq!(p.register(0x2e16), Verdict::Rewrite);
        assert_eq!(p.register(0xc342), Verdict::Drop);
        assert_eq!(p.register(0xa000), Verdict::Pass);
    }

    #[test]
    fn set_sh_reg_takes_the_verdict_of_its_registers() {
        let p = Policy::get();
        // SET_SH_REG COMPUTE_USER_DATA_0..1 (0x2e40): pass.
        let s = parse(&[0xC0027600, 0x240, 1, 2]);
        assert_eq!(p.packet(&s.packets[0].1), Verdict::Pass);
        // SET_SH_REG_INDEX at 0x216 (SE0, SE1 masks): rewrite.
        let s = parse(&[0xC0029B00, 0x30000216, 0xffffffff, 0xffffffff]);
        assert_eq!(p.packet(&s.packets[0].1), Verdict::Rewrite);
        // A range mixing pass and drop registers (0x27f..0x280): split.
        let s = parse(&[0xC0027600, 0x27f, 0, 0]);
        assert_eq!(p.packet(&s.packets[0].1), Verdict::Split);
    }

    #[test]
    fn check_counts_dwords_and_packets() {
        let p = Policy::get();
        let s = parse(&[0xffff1000, 0xC0038E00, 0, 0, 0, 0, 0xC0027900, 0x342, 5, 6]);
        let mut c = Check::default();
        c.add(p, &s);
        assert_eq!(c.packets, 3);
        assert_eq!(c.by_verdict[&Verdict::Pass], 1);
        assert_eq!(c.by_verdict[&Verdict::Drop], 2);
        assert_eq!(c.dwords_dropped, 5 + 4);
        assert_eq!(c.dwords_kept, 1);
        assert_eq!(c.dropped_regs[&0xc342], 1);
        assert_eq!(c.dropped_regs[&0xc343], 1);
    }
}
