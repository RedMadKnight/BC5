# 0195 — The compute-only buffer of session 0808 ran another process's program: COMPUTE_PGM_LO/HI left by Mesa on the shared GFX ring

**Question.** In session 0808 (experiment 0192, F251) a one-off 328-dword graphics buffer ran its three
`DISPATCH_DIRECT`s (2×1×1, user data in the layout of program 0x11d039cd00) with `COMPUTE_PGM_HI` 0x80 and
`COMPUTE_PGM_LO` 0x50. The shader instruction fetch then faulted at 0x0000800000005000 (SQC inst) and the gfx ring was
reset. Where did that program address come from, and which program does the title expect the buffer to inherit?

**Setup.**
- Offline only: no GPU run and no submission. The box is the BC-250 dev box, 2026-10-22 10:20–10:50, kernel
  7.2.9-ogc3.1, Mesa 26.2.4 (desktop drivers; source cited at the sparse clone `~/src/mesa` 0866ae7), libdrm source
  `~/src/libdrm` b97cbde. The host source is `~/src/KytyPlus/src/libs/bc5LleAgc.cpp` of 2026-10-21 23:45:38, the
  file patch 0001 carries (its `bc5LleAgc.cpp` section equals `git diff f266548` of that file, 8,968 lines). The backend
  source is `~/src/bc5/backend` (`full_state.cpp`, `policy.cpp`).
- Data on the box (not committed): the timeout probe's dump `~/bc5-data/captures/play-20261022-0808/gc/ib-timeout-00476912-dcb-328.bin`
  and that session's journal. The 3.6-GB dispatch journal of session 0933 (`play-20261022-0933/gc/direct.log`,
  `BC5_DIRECT_DISPATCH_JOURNAL=1`). The 364 command-buffer dumps (`ib-*.bin`) of 2026-10-18..22 under `~/bc5-data/captures/*/gc/`.
- Scripts (this directory):
  - `scan_ud.py`: buffers holding the user-data layout of 0x11d039cd00 (`COMPUTE_USER_DATA_0..3` = aef90000 00300011
    00069000 00005204) and the packets around it.
  - `inherit_check.py`: an offline replica of the new host check.
  - `addr32.py`: the 32-bit VA window libdrm gives a Mesa process. It makes read-only libdrm calls (`amdgpu_device_initialize`,
    `amdgpu_query_sw_info`) and submits nothing.
  - `cs_check.cpp`: the two new host functions, extracted verbatim, run on captures with the backend's own `bc5::full_state`.
  - `build0195.py`: the separate binary, built as exp 0193's `build0193.py` does.
- Raw: `raw/0808-around-timeout.txt`, `raw/0933-heads.txt`, `raw/0933-layout-counts.txt`, `raw/layout-scan.txt`,
  `raw/normal-group-1739.txt`, `raw/group-bindings.txt`, `raw/inherit-check.txt`, `raw/cs-check.txt`,
  `raw/address32.txt`.

**Result.**
- **0x800000005000 is a Mesa client's shader address, not one of the title's.**
  - Mesa writes `COMPUTE_PGM_HI` once per command stream, in the compute preamble, as `S_00B834_DATA(address32_hi >> 8)`
    (`src/amd/common/ac_cmdbuf.c:26,64` @ 0866ae7). After that it writes only `COMPUTE_PGM_LO` = shader VA >> 8 for
    each dispatch (radeonsi `src/gallium/drivers/radeonsi/gfx/si_compute.c:401`; RADV `src/amd/vulkan/radv_cmd_buffer.c:3264`).
  - RADV puts every shader in the 32-bit window (`radv_shader.c:1171`, `RADEON_FLAG_32BIT`). The window starts at the
    kernel's high VA offset (libdrm `amdgpu/amdgpu_vamgr.c:365-367`), and `address32_hi` is its top dword
    (`amdgpu/amdgpu_device.c:389-391`, b97cbde).
  - On the box `address32_hi` is 0xffff8000 (`raw/address32.txt`). `COMPUTE_PGM_HI` DATA is bits 7:0 (Mesa gfx10
    register JSON), so Mesa writes 0x80, and a shader at window offset 0x5000 is GPU address 0x800000005000, the fault.
  - The title's programs are at 0x11d0xxxxxx and 0x909xxxxxxx, and the host writes `COMPUTE_PGM_LO` only through the
    prefix's tracked values.
  - The 0x80 is therefore not the title's tag of F109/F110. It is Mesa's high byte, and with LO 0x50 it is the leftover
    of some other amdgpu client's compute dispatch on the BC-250's one GFX ring. KytyPlus's renderer records no
    dispatch of its own, though RADV's internal copies may. The desktop's radeonsi/RADV clients share the ring (F204).
    Which client it was is not identified.
  - The host's own source already recorded this address once: run 123's pieces "faulted from the first frames
    (0x800000005000, a shader fetch with foreign state)", and run 44 hit 0x800000400000 with "a foreign
    COMPUTE_PGM_LO" (`bc5LleAgc.cpp:4030, 4166`).
- **The title expects the buffer to inherit 0x11d039cd00, bound at the end of its previous graphics buffer.**
  - The 78 earlier buffers carrying the layout (`raw/layout-scan.txt`, sessions 2026-10-18..21) hold 43 dispatch
    groups. The other hits are copies of the user data in the host's full-state prefix. Every one of the 43 groups has
    a `LOAD_SH_REG_INDEX` of ten (offset, value) pairs, the program's binding, one packet before it (18 groups) or three
    packets before it, behind an `EVENT_WRITE` + `ACQUIRE_MEM` (25 groups, session 1937). See `raw/group-bindings.txt`.
    For example `ib-00391955` at 11647 has table 0x11e0bbfc1c, count 0xa. After the dispatches comes the end of a
    large dcb: label `RELEASE_MEM`s and `WAIT_REG_MEM64`s (`raw/normal-group-1739.txt`).
  - The 328-dword buffer is that end and nothing else, with a dcb opening in front. The opening is `ACQUIRE_MEM` in the
    form at offset 0 of the captured dcbs, then empty `LOAD_CONTEXT_REG_INDEX` / `LOAD_SH_REG_INDEX` (address 0, count
    0), as captured dcbs open too (`ib-00391955` 0–18, `ib-00392227` 0–8). Then come the user data, the three
    dispatches and the same label traffic as `ib-00391955` 10558–10662. Its only `LOAD_SH_REG_INDEX` is the empty
    one: the binding is not in it.
  - The timeout probe's dump is the buffer before the filter (`sub_ib`, `bc5LleAgc.cpp:7815, 7828`). So the empty tables
    are the title's own. The filter then dropped them as unmapped ("unmapped 2"; `policy.cpp:526-531` NOPs them).
  - In session 0933 the same dcb opening, three dispatches at 32/51/70, occurs three times among 15,203 dispatch lines
    of this layout (`raw/0933-layout-counts.txt`). The host's carried state (`g_carried`, exp 0161) names their program
    0x11d039cd00, although the previous dcb's last dispatch ran 0x11d0288a00 (twice) or 0x11d0404200. That state
    follows `SET_SH_REG` and `LOAD_SH_REG_INDEX` tables, so the binding was in the previous buffer, after its last
    dispatch (`raw/0933-heads.txt`).
  - In the captured dcbs the group's binding also follows a dispatch of 0x11d0288a00 with `ud0-3 2adc0000 …`
    (`ib-00391955` 11560–11571; session 1937 at 1706–1717). That is the last dispatch before two of the 0933 heads.
  - In each 0933 head chain the head part stands first with no prefix. The draw prefix's packet block follows, then
    the rest. The block is the `SET_BASE` at 1249 of every prefixed dcb in that journal, here at 1577, 1465 and 1577:
    after head parts of 328, 216 and 328 dwords. Session 0808's 328 + 6012 dwords has the same shape.
  - On the console the graphics queue keeps its SH registers between buffers, so the dispatches run 0x11d039cd00.
  - The title opens other dcbs the same way. Five large draw dcbs of 2026-10-18 (sessions 1729, 1809) start with
    dispatches at offset 8–27 that set only user data (`raw/inherit-check.txt`). Those draw, so the default draw
    prefix (`BC5_DIRECT_PREFIX_ALL` = draws, exp 0157) restores their program. Only a buffer that draws nothing goes
    without it.
- **Why only in 0808.**
  - The 328-dword buffer draws nothing, so it got no prefix (`bc5LleAgc.cpp:4036`, `ib_has_draw`).
  - It went to the kernel as its own chain, after 15.3 ms of sync and 3.5 ms of hints (journaled at t 467.984 s,
    submitted at about 468.003 s). The title's jobs #476900–#476911 had completed by 467.994 s
    (`raw/0808-around-timeout.txt`).
  - Other processes' jobs ran on the idle ring in that gap. In 0933 the three heads went without a foreign compute
    dispatch in between and ran correctly.
  - The fault, the 87 suppressed SQC faults and the ring timeout follow from a wave fetching from an address our VM
    does not map.
- **The bogus alias.** `alias_learn` (`bc5LleAgc.cpp:2168`) maps a 96-MiB window under any non-zero top byte. For
  this fault it saved "0x80 0x0 0x6000000", which maps guest 0–96 MiB under 0x80 in every later run. A foreign fetch
  like this one could then execute whatever guest bytes lie at 0x5000 instead of faulting.
- **Changes in the host (`patch_0195.diff`, against the 23:45:38 file; not applied to the shared tree).**
  - `BC5_DIRECT_CS_PREFIX=1` (off by default, D16): a graphics buffer that gets no other prefix and dispatches before it
    sets `COMPUTE_PGM_LO` gets the graphics queue's tracked compute registers in front, in the same chain segment.
    These are SH 0x204–0x3ff from `bc5::full_state`, the values the draw prefix already replays, one `SET_SH_REG` per
    run. A pair table that cannot be read, or an `INDIRECT_BUFFER`, counts as setting the program, so no prefix.
  - `BC5_DIRECT_CS_PREFIX=journal` is the probe: it only journals such buffers, with the program and RSRC1/2 the
    queue's state names (`cs prefix (exp 0195): …`; the first 64, then every 1024th).
  - `alias_learn` no longer learns a fault whose low 40 bits are not guest memory (journal "aliases: fault … no guest
    memory at …, not learned"). `BC5_DIRECT_ALIAS_LEARN_UNMAPPED=1` restores the old behaviour.
  - When the switch is off, every existing condition is unchanged: `cs_used` is false, and the tracker runs as before
    under the default prefix mode.
- **Checks.**
  - `cs_check.cpp` (`raw/cs-check.txt`): `cs_inherit_at` = 32 on the 0808 buffer and −1 on a prefixed dump.
  - The queue state the host tracked after `ib-00391955` (the full-state prefix of `ib-00391957`, 1,260 dwords) names
    0x11d039cd00. Its 58-dword compute prefix (nine `SET_SH_REG` runs from 0x204 to 0x280) reproduces all 40 tracked
    compute registers in a fresh tracker and no graphics register.
  - `inherit_check.py` over the 277 captured dcbs: six would be prefixed. The 0808 buffer is the only one without draws;
    the five draw dcbs above get the draw prefix instead.
  - The patch applies to the shared tree (`git apply --check`) and reproduces the built source byte for byte.
- **Build.** `~/bc5-work/exp0195/kyty_emulator` (2026-10-22 10:44:37, sha256 570deb873245bdee…, synced; build log
  `~/bc5-work/exp0195/build.log`): this unit compiled with the shared build's flags (no new warnings), linked with the
  shared build's other objects as of 10:22:48, which include exp 0193's touchpad mapping. The shared binary and
  `~/src/KytyPlus` are not modified.

**Verdict.**
- **Cause named.** The 328-dword compute-only buffer of session 0808 ran with another amdgpu client's compute program
  registers. Mesa's `COMPUTE_PGM_HI` 0x80 (address32_hi 0xffff8000) and a `COMPUTE_PGM_LO` of 0x50 were left on the
  shared GFX ring, giving 0x800000005000.
- The title relies on the console's graphics queue keeping the program it bound at the end of its previous buffer,
  0x11d039cd00. The host restores that state only in front of buffers that draw.
- The "title's tag" reading of F251 was wrong.
- This is a host defect of the shared ring, independent of the reflection fix. It also hits the default launcher
  whenever the title emits such a buffer and a desktop process dispatches compute in the gap.
- **Not yet verified on the GPU.** The fix and the probe are built into a separate binary, off by default.
  - Next, the probe: a session with `BC5_EMU=~/bc5-work/exp0195/kyty_emulator BC5_DIRECT_CS_PREFIX=journal` through the
    normal launcher (skips kept). It should journal 0x11d039cd00 for each such buffer.
  - Then `=1` in one short, watched run with the maintainer (D16), and only then in the "refleksy" shortcut. Removing
    skips stays the maintainer's call.
  - Applying `patch_0195.diff` to `~/src/KytyPlus`, and splicing it into patch 0001, waits for that run.
- Open: which desktop client dispatched compute in the gap (not needed for the fix).
