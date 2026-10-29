# SPDX-License-Identifier: GPL-2.0-only
"""Tests for bc5-gpu-stall-sampler (exp 0373, T0). No device access; stdlib unittest.

    python tools/scripts/gpu-stall-sampler/test_bc5_gpu_stall_sampler.py -v

The source-checked tests read the kernel files the sampler cites, when BC5_LINUX_SRC names a directory that holds them
(flat, by basename): amdgpu_debugfs.c, gfx_v10_0.c, amdgpu_fence.c, amdgpu_job.c, gc_10_1_0_offset.h,
gc_10_1_0_sh_mask.h, cyan_skillfish_ip_offset.h, all from Linux v7.2 (github.com/torvalds/linux commit
8d3ae59288f1e7d58d76558a6ee96d533bc5019f), e.g.
    curl -o DIR/amdgpu_debugfs.c https://raw.githubusercontent.com/torvalds/linux/<commit>/drivers/gpu/drm/amd/amdgpu/amdgpu_debugfs.c
Without it those tests are skipped; the rest still run. The Mesa register database vendored in the repo
(tools/bc5-agc/regdb/gfx10.json, Mesa fe554882) is a second, independent check of the offsets.
"""
import collections
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("bc5_gpu_stall_sampler", os.path.join(HERE, "bc5-gpu-stall-sampler"))
S = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(S)
SRC = os.environ.get("BC5_LINUX_SRC")
MESA = os.path.join(HERE, "..", "..", "bc5-agc", "regdb", "gfx10.json")


def src(name):
    if not SRC:
        raise unittest.SkipTest("BC5_LINUX_SRC not set")
    p = os.path.join(SRC, name)
    if not os.path.exists(p):
        raise unittest.SkipTest("%s not in BC5_LINUX_SRC" % name)
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def c_function(text, name):
    """The body of a C function definition `name(` in text."""
    m = re.search(r"^[^\n;]*\b%s\(" % re.escape(name), text, re.M)
    if not m:
        raise AssertionError("no %s in source" % name)
    i = text.index("{", m.end())
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i:j + 1]
    raise AssertionError("unbalanced %s" % name)


# ---------------------------------------------------------------------------------------------------------------
# A model of the kernel side, transcribed from v7.2 (the oracle the sampler is checked against)
# ---------------------------------------------------------------------------------------------------------------

def _read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


def genmask(hi, lo):
    return ((1 << (hi - lo + 1)) - 1) << lo


# amdgpu_debugfs.c:1168-1174 (amdgpu_debugfs_wave_read)
WAVE_POS_FIELDS = {"offset": (6, 0), "se": (14, 7), "sh": (22, 15), "cu": (30, 23), "wave": (36, 31), "simd": (44, 37)}
# gfx_v10_0.c:4506-4523 (gfx_v10_0_read_wave_data): version 2, then these ix registers in this order
GFX10_WAVE_IX = ("ixSQ_WAVE_STATUS", "ixSQ_WAVE_PC_LO", "ixSQ_WAVE_PC_HI", "ixSQ_WAVE_EXEC_LO", "ixSQ_WAVE_EXEC_HI",
                 "ixSQ_WAVE_HW_ID1", "ixSQ_WAVE_HW_ID2", "ixSQ_WAVE_INST_DW0", "ixSQ_WAVE_GPR_ALLOC",
                 "ixSQ_WAVE_LDS_ALLOC", "ixSQ_WAVE_TRAPSTS", "ixSQ_WAVE_IB_STS", "ixSQ_WAVE_IB_STS2",
                 "ixSQ_WAVE_IB_DBG1", "ixSQ_WAVE_M0", "ixSQ_WAVE_MODE")


def kernel_wave_read(pos, size, slot_regs, warnings):
    """amdgpu_debugfs_wave_read + gfx_v10_0_read_wave_data over a dict {(se, sh, instance, wave): {ix name: value}}."""
    if size & 3 or pos & 3:
        raise OSError(22, "EINVAL")
    f = {k: (pos & genmask(hi, lo)) >> lo for k, (hi, lo) in WAVE_POS_FIELDS.items()}
    if f["simd"] != 0:
        warnings.append("WARN_ON(simd != 0) at pos 0x%x" % pos)
    regs = slot_regs.get((f["se"], f["sh"], f["cu"], f["wave"]), {})
    data = [2] + [regs.get(ix, 0) for ix in GFX10_WAVE_IX]
    out, off = [], f["offset"]
    while size and off < len(data) * 4:
        out.append(data[off >> 2])
        off += 4
        size -= 4
    return struct.pack("<%dI" % len(out), *out)


def kernel_regs_decode(pos):
    """amdgpu_debugfs_process_reg_op (amdgpu_debugfs.c:90-121): (byte offset, bank or None)."""
    if pos & 3 or ((pos >> 62) & 1 and (pos >> 61) & 1):
        raise OSError(22, "EINVAL")
    bank = None
    if pos & (1 << 62):
        bank = ((pos & genmask(33, 24)) >> 24, (pos & genmask(43, 34)) >> 34, (pos & genmask(53, 44)) >> 44)
    return pos & ((1 << 22) - 1), bank


class ModelDevice:
    """The sampler's device interface on top of the kernel model (what Device does with os.pread)."""

    def __init__(self, slot_regs, fences=None, gfxoff=0):
        self.slot_regs, self.warnings = slot_regs, []
        self.fences = fences or collections.OrderedDict([("gfx_0.0.0", (1, 2))])
        self.reg_log, self.wave_positions = [], []
        self.gfxoff = gfxoff

    def read_fence(self):
        return S.format_fence_info(self.fences)

    def read_reg(self, byte_off, bank=None):
        self.reg_log.append(kernel_regs_decode(S.regs_pos(byte_off, bank)))
        return 0x1000 + byte_off

    def read_gfxoff(self):
        return self.gfxoff

    def read_wave(self, se, sa, wgp, simd, wave):
        pos = S.wave_pos(se, sa, wgp, simd, wave)
        self.wave_positions.append(pos)
        b = kernel_wave_read(pos, S.WAVE_BYTES, self.slot_regs, self.warnings)
        return struct.unpack("<%dI" % (len(b) // 4), b)


def umr_many_to_instance(wgp, simd):
    return (simd & 3) | (wgp << 2)   # umr src/lib/scan_waves.c:30


# ---------------------------------------------------------------------------------------------------------------

class WaveRecord(unittest.TestCase):
    def slot_regs(self):
        regs = {}
        # two live waves and one halted, in different SEs/SAs/WGPs/SIMDs
        for (se, sa, wgp, simd, wave, pc, st) in ((0, 0, 0, 0, 0, 0x11D049AA00, 0x10000), (1, 1, 4, 3, 19, 0x909974404,
                                                   0x10020), (1, 0, 2, 1, 7, 0x1234500, 0x2000)):
            inst = umr_many_to_instance(wgp, simd)
            regs[(se, sa, inst, wave)] = {
                "ixSQ_WAVE_STATUS": st, "ixSQ_WAVE_PC_LO": pc & 0xFFFFFFFF, "ixSQ_WAVE_PC_HI": pc >> 32,
                "ixSQ_WAVE_EXEC_LO": 0xFFFFFFFF, "ixSQ_WAVE_EXEC_HI": 0x0,
                "ixSQ_WAVE_HW_ID1": (se << 18) | (sa << 16) | (wgp << 10) | (simd << 8) | wave,
                "ixSQ_WAVE_HW_ID2": (1 << 8) | (2 << 4) | 3 | (6 << 24), "ixSQ_WAVE_TRAPSTS": 0,
                "ixSQ_WAVE_IB_STS2": 0x800 if wave == 19 else 0, "ixSQ_WAVE_M0": 0xABCD}
        return regs

    def test_scan_through_the_kernel_model(self):
        dev = ModelDevice(self.slot_regs())
        cfg = S.Config()
        smp = S.take_sample(dev, cfg, "stall", 1.0, 1.0, "", True)
        self.assertEqual(dev.warnings, [], "a read set the simd field: the kernel would WARN_ON")
        self.assertEqual(smp.slots_read, 2 * 2 * 5 * 4 * 20)
        self.assertEqual(smp.wave_errors, 0)
        # every slot once, every position distinct, offset 0, instance = umr's MANY_TO_INSTANCE
        self.assertEqual(len(set(dev.wave_positions)), 1600)
        for p in dev.wave_positions:
            self.assertEqual(p & 0x7F, 0)
        kept = {w[:5]: S.decode_wave(w[5]) for w in smp.waves}
        self.assertEqual(sorted(kept), [(0, 0, 0, 0, 0), (1, 0, 2, 1, 7), (1, 1, 4, 3, 19)])
        d = kept[(1, 1, 4, 3, 19)]
        self.assertEqual(d["pc"], 0x909974404)
        self.assertEqual(d["hw"], (1, 1, 4, 3, 19))
        self.assertEqual((d["me"], d["pipe"], d["queue"], d["vmid"]), (1, 2, 3, 6))
        self.assertTrue(d["valid"] and d["wave64"] and "PRIV" in d["flags"])
        self.assertEqual(d["regs"]["M0"], 0xABCD)
        h = kept[(1, 0, 2, 1, 7)]
        self.assertTrue(h["halt"] and not h["valid"])
        self.assertEqual(S.hw_mismatches(smp), 0)
        self.assertEqual(S.valid_pcs(smp), collections.Counter({0x11D049AA00: 1, 0x909974404: 1}))

    def test_bin_round_trip_and_text(self):
        dev = ModelDevice(self.slot_regs())
        smp = S.take_sample(dev, S.Config(), "stall", 1.0, 1.0, "", True)
        back = S.unpack_waves_bin(S.pack_waves_bin(smp))
        self.assertEqual(back, [tuple(w) for w in smp.waves])
        txt = S.fmt_waves_txt(smp)
        self.assertIn("se1 sa1 wgp4 simd3 w19 00010020[PRIV,VALID] PC=000909974404 EXEC=ffffffff me1.p2.q3 vm6 w64\n",
                      txt)
        self.assertIn("se1 sa0 wgp2 simd1 w07 00002000[HALT] PC=000001234500", txt)

    def test_short_or_foreign_records(self):
        self.assertIsNone(S.decode_wave((2, 1, 2)))
        self.assertIsNone(S.decode_wave((1,) + (0,) * 16))          # a gfx9 record (version 1)
        self.assertFalse(S.slot_kept((2, 0xBEBEBEEF) + (0,) * 15))  # umr's no-data pattern (HALT bit set)
        self.assertFalse(S.slot_kept((2, 0xFFFFFFFF) + (0,) * 15))
        self.assertTrue(S.slot_kept((2, 0x2000) + (0,) * 15))       # halted, not valid: kept, as umr does

    def test_hw_id_mismatch_is_flagged(self):
        regs = self.slot_regs()
        regs[(0, 0, 0, 0)]["ixSQ_WAVE_HW_ID1"] = (1 << 18)   # says SE1 while we addressed SE0
        smp = S.take_sample(ModelDevice(regs), S.Config(), "stall", 1.0, 1.0, "", True)
        self.assertEqual(S.hw_mismatches(smp), 1)
        self.assertIn("HW_ID1-mismatch", S.fmt_waves_txt(smp))


class RegisterReads(unittest.TestCase):
    def test_positions_through_the_kernel_decode(self):
        dev = ModelDevice({})
        smp = S.take_sample(dev, S.Config(), "stall", 1.0, 1.0, "", True, regs_only=True, banked=True)
        offs = [o for o, b in dev.reg_log if b is None]
        want = []
        for n, mm, bi in S.REGS:
            want += [S.reg_byte(mm, bi)] * (S.HEADER_DUMP_PERIOD if n in S.HEADER_DUMPS else 1)
        self.assertEqual(offs, want)
        banked = [(o, b) for o, b in dev.reg_log if b is not None]
        self.assertEqual(len(banked), 2 * 2 * 2)
        self.assertEqual(sorted(set(b for o, b in banked)), [(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)])
        self.assertEqual(smp.reg_errors, 0)

    def test_header_dumps_eight_reads_by_default_none_when_zero(self):
        hd = set(S.reg_byte(mm, bi) for n, mm, bi in S.REGS if n in S.HEADER_DUMPS)
        dev = ModelDevice({})
        smp = S.take_sample(dev, S.Config(), "stall", 1.0, 1.0, "", True, regs_only=True)
        self.assertEqual(collections.Counter(o for o, b in dev.reg_log if o in hd), {o: 8 for o in hd})
        txt = S.fmt_regs(smp)
        self.assertIn("gfx1013.mmCP_PFP_HEADER_DUMP[7] =>", txt)
        self.assertNotIn("HEADER_DUMP[8]", txt)
        dev = ModelDevice({})
        S.take_sample(dev, S.Config(header_dump_reads=0), "stall", 1.0, 1.0, "", True, regs_only=True)
        self.assertFalse(hd & set(o for o, b in dev.reg_log))

    def test_header_dump_period_check(self):
        hd = set(S.reg_byte(mm, bi) for n, mm, bi in S.REGS if n in S.HEADER_DUMPS)

        class History(ModelDevice):   # a header history read cyclically with period p
            def __init__(self, p):
                ModelDevice.__init__(self, {})
                self.p, self.pos = p, collections.Counter()

            def read_reg(self, byte_off, bank=None):
                if byte_off in hd:
                    self.pos[byte_off] += 1
                    return 0xC0000000 | ((self.pos[byte_off] - 1) % self.p) << 8
                return ModelDevice.read_reg(self, byte_off, bank)
        for p, verdict in ((8, "yes"), (9, "NO")):
            smp = S.take_sample(History(p), S.Config(header_dump_reads=16), "once", 0, 0, "", True, regs_only=True)
            self.assertIn("# CP_PFP_HEADER_DUMP period 8: %s" % verdict, S.fmt_regs(smp))

    def test_offsets_against_mesa(self):
        with open(MESA) as fh:
            d = json.load(fh)
        mesa = {}
        for r in d["register_mappings"]:
            if r["map"].get("to") == "mm":
                mesa.setdefault(r["name"], r["map"]["at"])
        checked = 0
        for n, mm, bi in S.REGS + S.BANKED_REGS:
            if n in mesa:
                self.assertEqual(S.reg_byte(mm, bi), mesa[n], n)
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_offsets_against_gc_10_1_0_offset_h(self):
        h = src("gc_10_1_0_offset.h")
        for n, mm, bi in S.REGS + S.BANKED_REGS:
            m = re.search(r"^#define mm%s\s+(0x[0-9a-fA-F]+)\s*$" % n, h, re.M)
            b = re.search(r"^#define mm%s_BASE_IDX\s+(\d+)\s*$" % n, h, re.M)
            self.assertTrue(m and b, n)
            self.assertEqual((int(m.group(1), 16), int(b.group(1))), (mm, bi), n)
        self.assertRegex(h, r"(?m)^#define mmCP_RB_RPTR\s+0x0f60\s*$")    # D3's CP_RB_RPTR is CP_RB0_RPTR's offset

    def test_gc_base_against_cyan_skillfish_ip_offset_h(self):
        h = src("cyan_skillfish_ip_offset.h")
        m = re.search(r"IP_BASE GC_BASE\s*=\{ \{ \{ \{ (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+),", h)
        self.assertTrue(m)
        self.assertEqual((int(m.group(1), 16), int(m.group(2), 16)), S.GC_BASE)

    def test_kernel_regs_op_mask(self):
        body = c_function(src("amdgpu_debugfs.c"), "amdgpu_debugfs_process_reg_op")
        self.assertIn("*pos &= (1UL << 22) - 1;", body)
        self.assertIn("se_bank = (*pos & GENMASK_ULL(33, 24)) >> 24;", body)
        self.assertIn("sh_bank = (*pos & GENMASK_ULL(43, 34)) >> 34;", body)
        self.assertIn("instance_bank = (*pos & GENMASK_ULL(53, 44)) >> 44;", body)
        for n, mm, bi in S.REGS:
            self.assertEqual(kernel_regs_decode(S.regs_pos(S.reg_byte(mm, bi))), (S.reg_byte(mm, bi), None))


class KernelSourceLayout(unittest.TestCase):
    """The record layout and the debugfs position bits, read from the cited source text itself."""

    def test_wave_read_position_bits(self):
        body = c_function(src("amdgpu_debugfs.c"), "amdgpu_debugfs_wave_read")
        got = {}
        for var, hi, lo in re.findall(r"(\w+) = \(\*pos & GENMASK_ULL\((\d+), (\d+)\)\)", body):
            got[var] = (int(hi), int(lo))
        self.assertEqual(got, WAVE_POS_FIELDS)
        self.assertIn("amdgpu_gfx_select_se_sh(adev, se, sh, cu, 0);", body)
        self.assertIn("read_wave_data(adev, 0, simd, wave, data, &x)", body)

    def test_gfx10_record_order_and_simd_rule(self):
        body = c_function(src("gfx_v10_0.c"), "gfx_v10_0_read_wave_data")
        self.assertIn("WARN_ON(simd != 0);", body)
        self.assertRegex(body, r"dst\[\(\*no_fields\)\+\+\] = 2;")
        order = re.findall(r"wave_read_ind\(adev, wave, (ixSQ_WAVE_\w+)\)", body)
        self.assertEqual(tuple(order), GFX10_WAVE_IX)
        self.assertEqual(tuple(x[len("ixSQ_WAVE_"):] for x in order), S.WAVE_FIELDS)

    def test_field_masks(self):
        h = src("gc_10_1_0_sh_mask.h")

        def mask(reg, field):
            m = re.search(r"^#define %s__%s_MASK\s+(0x[0-9A-Fa-f]+)L" % (reg, field), h, re.M)
            self.assertTrue(m, (reg, field))
            return int(m.group(1), 16)
        self.assertEqual(mask("SQ_WAVE_STATUS", "VALID"), S.ST_VALID)
        self.assertEqual(mask("SQ_WAVE_STATUS", "HALT"), S.ST_HALT)
        for name, m in S.STATUS_BITS:
            self.assertEqual(mask("SQ_WAVE_STATUS", name), m, name)
        self.assertEqual(mask("SQ_WAVE_PC_HI", "PC_HI"), S.PC_HI_MASK)
        self.assertEqual(mask("SQ_WAVE_IB_STS2", "WAVE64"), S.IB_STS2_WAVE64)
        self.assertEqual(mask("SQ_WAVE_TRAPSTS", "EXCP"), S.TRAPSTS_EXCP_MASK)
        self.assertEqual(mask("SQ_WAVE_TRAPSTS", "ILLEGAL_INST"), S.TRAPSTS_ILLEGAL_INST)
        self.assertEqual(mask("SQ_WAVE_TRAPSTS", "XNACK_ERROR"), S.TRAPSTS_XNACK_ERROR)
        # decode_wave's HW_ID shifts against the masks: put all-ones in one field at a time
        for field, idx in (("SE_ID", 0), ("SA_ID", 1), ("WGP_ID", 2), ("SIMD_ID", 3), ("WAVE_ID", 4)):
            m = mask("SQ_WAVE_HW_ID1", field)
            rec = S.make_wave_record(S.ST_VALID, 0, hw1=m)
            want = [0] * 5
            want[idx] = m >> ((m & -m).bit_length() - 1)
            self.assertEqual(S.decode_wave(rec)["hw"], tuple(want), field)
        for field, key in (("QUEUE_ID", "queue"), ("PIPE_ID", "pipe"), ("ME_ID", "me"), ("STATE_ID", "state"),
                           ("WG_ID", "wg"), ("VM_ID", "vmid")):
            m = mask("SQ_WAVE_HW_ID2", field)
            self.assertEqual(S.decode_wave(S.make_wave_record(S.ST_VALID, 0, hw2=m))[key],
                             m >> ((m & -m).bit_length() - 1), field)
        # 20 wave slots fit SQ_IND_INDEX's WAVE_ID field and the debugfs wave field
        self.assertGreaterEqual(mask("SQ_IND_INDEX", "WAVE_ID"), 19)

    def test_fence_info_format(self):
        body = c_function(src("amdgpu_fence.c"), "amdgpu_debugfs_fence_info_show")
        fmts = re.findall(r'seq_printf\(m, "([^"]*)"', body)
        self.assertEqual(fmts[0], "--- ring %d (%s) ---\\n")
        # render a GFX ring (all lines) and a compute ring (the first three) with the kernel's own formats
        text = fmts[0].replace("\\n", "\n") % (0, "gfx_0.0.0")
        vals = [0x10, 0x12, 0x7, 0x8, 0, 0, 0]
        for f, v in zip(fmts[1:], vals):
            text += f.replace("\\n", "\n") % v
        text += fmts[0].replace("\\n", "\n") % (9, "comp_1.0.0")
        text += fmts[1].replace("\\n", "\n") % 0x55 + fmts[2].replace("\\n", "\n") % 0x55
        self.assertEqual(S.parse_fence_info(text), collections.OrderedDict([("gfx_0.0.0", (0x10, 0x12)),
                                                                            ("comp_1.0.0", (0x55, 0x55))]))

    def test_timeout_lines(self):
        body = c_function(src("amdgpu_job.c"), "amdgpu_job_timedout")
        fmts = re.findall(r'dev_err\(adev->dev, "([^"]*)"', body)
        timeouts = [f for f in fmts if "timeout" in f]
        self.assertEqual(len(timeouts), 2)
        for f in fmts:
            line = "amdgpu 0000:01:00.0: " + (f.replace("\\n", "").replace("%u", "%d") % (
                ("gfx_0.0.0",) + (5, 6)[: f.count("%u")]) if "%s" in f else f.replace("\\n", "").replace("%d", "0"))
            m = S.TIMEOUT_RE.search(line)
            if f in timeouts:
                self.assertTrue(m and m.group(1) == "gfx_0.0.0", line)
            else:
                self.assertIsNone(m, line)


class FenceAndKmsg(unittest.TestCase):
    def test_parse_fence_text(self):
        txt = S.format_fence_info(collections.OrderedDict([("gfx_0.0.0", (1, 2)), ("comp_1.0.0", (3, 3)),
                                                           ("sdma0", (9, 9)), ("kiq_0.2.1.0", (4, 4))]))
        self.assertEqual(list(S.parse_fence_info(txt).items()),
                         [("gfx_0.0.0", (1, 2)), ("comp_1.0.0", (3, 3)), ("sdma0", (9, 9)), ("kiq_0.2.1.0", (4, 4))])
        self.assertEqual(S.parse_fence_info("garbage\n--- ring 1 (x) ---\nLast emitted 0x5\n"), {})

    def test_kmsg_records(self):
        r = S.parse_kmsg_record("3,1234,5030000,-;amdgpu 0000:01:00.0: ring gfx_0.0.0 timeout, signaled seq=1, "
                                "emitted seq=2\n SUBSYSTEM=pci\n DEVICE=+pci:0000:01:00.0\n")
        self.assertEqual((r["facility"], r["level"], r["seq"], r["usec"]), (0, 3, 1234, 5030000))
        self.assertTrue(S.kmsg_amdgpu_line(r))
        self.assertEqual(S.TIMEOUT_RE.search(r["text"]).group(1), "gfx_0.0.0")
        watch = S.parse_kmsg_record("12,1235,5040000,-;bc5-gpu-watch: armed: amdgpu 0000:01:00.0: ring gfx_0.0.0 timeout")
        self.assertFalse(S.kmsg_amdgpu_line(watch))      # facility 1, and it quotes the amdgpu line (F420)
        self.assertFalse(S.kmsg_amdgpu_line(S.parse_kmsg_record("6,1,1,-;usb 1-1: new device")))
        self.assertIsNone(S.parse_kmsg_record("no semicolon"))
        self.assertIsNone(S.TIMEOUT_RE.search("amdgpu 0000:01:00.0: Ring gfx_0.0.0 reset succeeded"))


PCI = "0000:01:00.0" if os.name == "posix" else "0000_01_00.0"   # Windows test runs: no ':' in a directory name
PCI2 = PCI.replace("01", "05")


class DebugfsDiscovery(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="bc5-dri-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def mk(self, d, name, files=S.DEBUGFS_FILES):
        p = os.path.join(self.root, d)
        os.makedirs(p)
        if name is not None:
            with open(os.path.join(p, "name"), "w") as fh:
                fh.write(name + "\n")
        for f in files:
            open(os.path.join(p, f), "w").close()
        return p

    def test_v72_layout_pci_named_dir(self):
        self.mk(PCI2, "amdgpu dev=%s unique=%s" % (PCI2, PCI2))
        want = self.mk(PCI, "amdgpu dev=%s unique=%s" % (PCI, PCI))
        os.makedirs(os.path.join(self.root, "client-7"))
        d, name = S.find_debugfs_dir(PCI, self.root)
        self.assertEqual(d, want)

    def test_numbered_dirs_by_name_file(self):
        self.mk("0", "simpledrm dev=simple-framebuffer.0 unique=simple-framebuffer.0", files=())
        want = self.mk("1", "amdgpu dev=0000:01:00.0 master=0000:01:00.0 unique=0000:01:00.0")
        self.mk("128", "amdgpu dev=0000:01:00.0 unique=0000:01:00.0", files=("amdgpu_fence_info",))
        d, name = S.find_debugfs_dir("0000:01:00.0", self.root)
        self.assertEqual(d, want)

    def test_not_found(self):
        self.mk("0", "amdgpu dev=0000:03:00.0 unique=0000:03:00.0")
        with self.assertRaises(RuntimeError) as cm:
            S.find_debugfs_dir("0000:01:00.0", self.root)
        self.assertIn("0000:03:00.0", str(cm.exception))


class EngineScenarios(unittest.TestCase):
    """The tool's own --test scenarios (synthetic 60-Hz fence traces through the stall clock), as unit tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc5-stall-ut-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scenarios(self):
        for name, ev, chk in S.scenarios():
            with self.subTest(name):
                self.assertEqual(S.run_scenario(name, ev, chk, self.tmp), [])

    def test_second_stall_while_event_is_written(self):
        self.assertEqual(S.scenario_second_stall_while_writing(self.tmp), [])

    def test_replay_file_path(self):
        trace = os.path.join(self.tmp, "trace.txt")
        with open(trace, "w") as fh:
            fh.write("# a stall of 1.0 s on comp_1.2.0, a recovered one\n")
            fh.write("0.0 fence comp_1.2.0 0x10 0x10\n0.1 fence comp_1.2.0 0x10 0x11\n0.1 busy 12 0xfe00001ce4\n")
            fh.write("1.1 fence comp_1.2.0 0x11 0x11\n1.1 busy 0 0\n")
            fh.write("1.5 kmsg 6 amdgpu 0000:01:00.0: a comment-like # inside a kernel line stays\n2.0 end\n")
        with open(trace) as fh:
            ev = S.read_trace(fh)
        self.assertIn((1.5, "kmsg", "6 amdgpu 0000:01:00.0: a comment-like # inside a kernel line stays"), ev)
        eng, dev = S.replay(ev, self.tmp)
        self.assertEqual(len(eng.census), 1)
        self.assertIn("ring=comp_1.2.0", eng.census[0])
        self.assertIn("samples=2 ", eng.census[0])        # 0.5 and 0.8
        self.assertIn("top=0xfe00001ce4:12", eng.census[0])
        self.assertEqual(list(eng.events), [])

    def test_late_poll_skips_thresholds_without_a_burst(self):
        # the sampler itself held up (exp 0203 O2) after its 0.8-s sample: the next poll lands at clock ~1.47 s; that
        # one sample serves 1.1 (late) and 1.4 (within the 0.15-s tolerance), 1.4 counts as missed, 1.7 comes as usual
        ev = S.gen_trace([("gfx_0.0.0", 1.0, 3.5)], 4.0, rings=("gfx_0.0.0",))
        cfg = S.Config()
        clock_jumps = {"done": False}

        def on_tick(eng, t):
            if not clock_jumps["done"] and t > 1.9:
                eng.clock.advance(0.52)          # the next poll comes 0.52 s late
                clock_jumps["done"] = True
        eng, dev = S.replay(ev, self.tmp, cfg, on_tick=on_tick)
        self.assertTrue(clock_jumps["done"])
        self.assertIn("missed=1", eng.census[0])
        self.assertIn("samples=4 ", eng.census[0])

    def test_gfxoff_and_pending_gates(self):
        dev = ModelDevice({}, gfxoff=1)
        cfg = S.Config()
        s = S.take_sample(dev, cfg, "forced", 0, 0, "", pending=False, idle_ok=True)
        self.assertIn("GFXOFF", s.skipped)
        self.assertEqual(dev.reg_log, [])
        s = S.take_sample(dev, cfg, "forced", 0, 0, "", pending=False, idle_ok=False)
        self.assertIn("no job pending", s.skipped)
        s = S.take_sample(dev, cfg, "stall", 0, 0, "", pending=True)
        self.assertIsNone(s.skipped)                     # a job pending: GFX is up whatever gfx_off_state says
        self.assertEqual(s.slots_read, 1600)

    def test_forced_requests(self):
        clock = S.FakeClock(10.0)
        dev = S.FakeDevice(clock)
        out = self.tmp
        w = S.Writer(out, threaded=False, log=lambda s: None)
        eng = S.Engine(dev, w, S.Config(), clock=clock, wall=lambda: 1.8e9 + clock.t, log=lambda s: None)
        dev.fences["gfx_0.0.0"] = (5, 5)
        done = []
        req = S.parse_force_request("once\n")
        req["on_done"] = lambda: done.append(1)
        eng.request_force(req)
        eng.tick(clock.t)
        self.assertEqual(list(eng.forced), [])           # nothing pending: waits (D5)
        dev.fences["gfx_0.0.0"] = (5, 6)
        clock.advance(0.025)
        eng.tick(clock.t)
        self.assertEqual(len(eng.forced), 1)
        self.assertEqual(done, [1])
        self.assertIsNone(eng.force_req)
        files = sorted(os.listdir(os.path.join(out, eng.forced[0])))
        self.assertEqual(files, ["fence.txt", "regs-1.txt", "summary.txt", "waves-1.bin", "waves-1.txt"])
        self.assertIn("mmCC_GC_SHADER_ARRAY_CONFIG[se1.sa1]", _read(os.path.join(out, eng.forced[0], "regs-1.txt")))
        p = S.parse_force_request("30 regs")
        self.assertEqual((p["period"], p["regs"], p["once"]), (30.0, True, False))
        self.assertEqual(S.parse_force_request("2")["period"], 5.0)
        self.assertTrue(S.parse_force_request("once idle")["idle"])
        eng.request_force(S.parse_force_request("idle"))
        dev.fences["gfx_0.0.0"] = (6, 6)
        clock.advance(1.0)
        eng.tick(clock.t)
        self.assertEqual(len(eng.forced), 1)             # the 5-s floor between forced samples
        clock.advance(5.0)
        eng.tick(clock.t)
        self.assertEqual(len(eng.forced), 2)             # "idle": taken with nothing pending (gfxoff 0)
        self.assertTrue(any(l.split()[1] == "forced" for l in eng.census))


class Writer(unittest.TestCase):
    def test_files_modes_and_append(self):
        out = tempfile.mkdtemp(prefix="bc5-stall-w-")
        try:
            w = S.Writer(out, threaded=False)
            w.submit(("mkdir", "event-x"))
            w.submit(("files", "event-x", [("a.txt", "one\n"), ("b.bin", lambda: b"\x00\x01")]))
            w.submit(("files", "event-x", [("a.txt", "two\n")]))
            w.submit(("append", "event-x", "kmsg.txt", "l1\n"))
            w.submit(("append", "event-x", "kmsg.txt", "l2\n"))
            w.submit(("append", None, "stalls.log", "c1\n"))
            d = os.path.join(out, "event-x")
            self.assertEqual(sorted(os.listdir(d)), ["a.txt", "b.bin", "kmsg.txt"])
            self.assertEqual(_read(os.path.join(d, "a.txt")), "two\n")
            self.assertEqual(_read(os.path.join(d, "kmsg.txt")), "l1\nl2\n")
            self.assertEqual(_read(os.path.join(out, "stalls.log")), "c1\n")
            if os.name == "posix":
                self.assertEqual(os.stat(d).st_mode & 0o777, 0o700)
                self.assertEqual(os.stat(os.path.join(d, "a.txt")).st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                w.submit(("mkdir", "event-x"))
        finally:
            shutil.rmtree(out, ignore_errors=True)


class CompareCheck(unittest.TestCase):
    def test_table(self):
        regs = {n: S.reg_byte(mm, bi) for n, mm, bi in S.REGS}
        lines = ["## sampler read 1"]
        lines += ["gfx1013.mm%s => 0x%08x   (byte 0x%05x)" % (n, 0x100 + i, o) for i, (n, o) in enumerate(regs.items())]
        lines += ["gfx1013.mmCC_GC_SHADER_ARRAY_CONFIG[se0.sa0] => 0xffff0000", "## umr -r"]
        lines += ["gfx1013.mm%s => 0x%08x" % (n, 0x100 + i + (n == "CP_STAT")) for i, n in enumerate(regs)]
        lines += ["## umr -lr gfx1013"]
        lines += ["\tcyan_skillfish.gfx1013.mm%s (0) => 0x%05x" % (n, o // 4 + (n == "GRBM_STATUS")) for n, o in regs.items()]
        lines += ["## sampler read 2"]
        lines += ["gfx1013.mm%s => 0x%08x" % (n, 0x100 + i + (n == "CP_RB0_RPTR")) for i, n in enumerate(regs)]
        t = S.compare_check("\n".join(lines) + "\n")
        row = {l.split()[0]: l for l in t.splitlines()[1:-1]}
        self.assertIn("MISMATCH", row["CP_STAT"])
        self.assertIn("changing", row["CP_RB0_RPTR"])
        self.assertIn("ADDR DIFF", row["GRBM_STATUS"])
        self.assertIn("same", row["CP_ME_INSTR_PNTR"])
        self.assertIn("addr ok (dword)", row["CP_ME_INSTR_PNTR"])
        self.assertIn("not read", row["CC_GC_SHADER_ARRAY_CONFIG"])
        self.assertTrue(t.splitlines()[-1].startswith("totals: "))


if __name__ == "__main__":
    unittest.main()
