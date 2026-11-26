#!/usr/bin/env python3
# BC5 exp 0444: the host unit's side of the master switch BC5_DIRECT_GPU_WAITS (bc5::gpu_waits_on(),
# backend/include/bc5/gpu_waits.hpp; default off). Every edit is "if the switch is on, do not decide":
# with the switch off the unit behaves byte for byte as its input. The map of what goes is
# inventory.md section 1; the ids below are inventory-unit.md's.
#   E0  #include "bc5/gpu_waits.hpp"
#   E1  H1 + H8/H9 + H10-H14 + H11 + H20 + H22: submit_split's wait branch is skipped: a memory wait on a
#       label the buffer does not write earlier goes to the GPU as it is (no ho430, no chain flush, no
#       flip-label wait or forced clear, no keep test, no CPU wait, no split, no give-up). The backend
#       passes it (gpu_waits::apply) and reports it executed, so the soft CP never polls it.
#   E2  H4-H6 + H17: the bc5-ring gate does not call acb_ready: every slice is taken at once (no hold,
#       no head split, no ng438, no 10-s fallback).
#   E3  H7: r438 early registration off (r438_on false), so no game-thread wait on an early writer.
#   E4  H18/H19: each guest queue gets a libdrm compute ring at its first acb (round robin in order of
#       first use) and keeps it for the run: no 256-acb move, no wait-idle. Binding lines (not lean).
#   E5  H18 (B7): an acb the policy refuses for a compute ring still goes to the GFX ring (it cannot run
#       on the MEC), but under the switch it is counted as a queue split: that queue's order across
#       the two rings is not kept. A measure, journaled at powers of two.
#   E6  H16: the soft CP's replay never polls a WAIT_REG_MEM[64] on the CPU under the switch (a wait the
#       backend dropped, e.g. on an unmapped label, is not served by the host either).
# Usage: python mk444.py IN.cpp OUT.cpp
# IN is the shared unit (589ef163's src/libs/bc5LleAgc.cpp, md5 ed489aca) or a private unit derived
# from it (exp 0439's k439/new); every anchor must appear exactly once, or nothing is written.
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '#include "bc5/gpu_waits.hpp"' not in s, 'already has mk444'
T = '\t'


def rep(tag, old, new):
    global s
    n = s.count(old)
    assert n == 1, '%s: anchor found %d times' % (tag, n)
    s = s.replace(old, new)


# E0
rep('E0', '#include "bc5/direct.hpp"\n',
    '#include "bc5/direct.hpp"\n#include "bc5/gpu_waits.hpp" // exp 0444: BC5_DIRECT_GPU_WAITS, the GPU decides every wait\n')

# E1: the wait branch of submit_split
a1 = (T * 4 + 'if (std::find(written.begin(), written.end(), label) == written.end()) {\n' +
      T * 5 + 'ho430::at_wait(')
rep('E1', a1,
    T * 4 + 'if (std::find(written.begin(), written.end(), label) == written.end()) {\n' +
    T * 5 + 'if (bc5::gpu_waits_on()) { i += len; continue; } // exp 0444: the wait goes to the GPU as it is; the host decides nothing\n' +
    T * 5 + 'ho430::at_wait(')

# E2: the bc5-ring gate
rep('E2', 'if (ta != 0 && tn != 0 && !Direct::acb_ready(',
    'if (ta != 0 && tn != 0 && !bc5::gpu_waits_on() && !Direct::acb_ready(')  # exp 0444: no hold

# E3: r438 off under the switch
rep('E3', T + T + 'const char* e = std::getenv("BC5_0438_EARLYREG");\n' + T + T + 'return !(',
    T + T + 'const char* e = std::getenv("BC5_0438_EARLYREG");\n' + T + T +
    'return !bc5::gpu_waits_on() && !(')  # exp 0444: no early registration

# E4: the fixed queue-to-ring binding
rep('E4a', 'static int                      g_w428_busy = 0;\n',
    'static int                      g_w428_busy = 0;\n'
    'static int                      g_w444_next = 0; // exp 0444: the next ring of the fixed binding\n')
rep('E4b', T + T + 'e.n++;\n' + T + T + 'if (e.busy || e.n < 256) return e.ring;\n',
    T + T + 'e.n++;\n' +
    T + T + 'if (bc5::gpu_waits_on()) { // exp 0444: a ring at the first acb, kept for the run (no move, no wait-idle)\n' +
    T + T + T + 'if (e.n == 1) {\n' +
    T + T + T + T + 'e.ring = g_w444_next++ % w428_rings();\n' +
    T + T + T + T + 'e.busy = true;\n' +
    '#ifndef BC5_LEAN\n' +
    T + T + T + T + 'if (g_w444_next <= 64) std::fprintf(stderr, "[bc5] exp 0444: guest queue %d bound to compute ring %d (%d queues bound)\\n", t_queue_idx, e.ring, g_w444_next);\n' +
    '#endif\n' +
    T + T + T + '}\n' +
    T + T + T + 'return e.ring;\n' +
    T + T + '}\n' +
    T + T + 'if (e.busy || e.n < 256) return e.ring;\n')

# E5: the GFX fallback counted as a queue split
rep('E5a', 'static std::atomic<uint64_t> g_comp_jobs {0}, g_comp_refused {0};\n',
    'static std::atomic<uint64_t> g_comp_jobs {0}, g_comp_refused {0};\n'
    'static std::atomic<uint64_t> g_w444_split {0}; // exp 0444: refused acbs under the switch (queue order across two rings lost)\n')
rep('E5b', T + 'if ((g_comp_refused++ & 0x3ffu) == 0)\n',
    T + 'if (bc5::gpu_waits_on()) { // exp 0444: counted, journaled at powers of two\n' +
    T + T + 'const uint64_t k = ++g_w444_split;\n' +
    T + T + 'if ((k & (k - 1)) == 0) journal("exp 0444: queue %d: an acb of %u dwords goes to the GFX ring (%s): its queue\'s order across two rings is not kept (%" PRIu64 " so far)\\n", t_queue_idx, num_dwords, why, k);\n' +
    T + '}\n' +
    T + 'if ((g_comp_refused++ & 0x3ffu) == 0)\n')

# E6: the soft CP's poll
rep('E6a', 'case IT_WAIT_REG_MEM: if (!done) wait_reg_mem(p, false); break;',
    'case IT_WAIT_REG_MEM: if (!done && !bc5::gpu_waits_on()) wait_reg_mem(p, false); break; // exp 0444: never served by the host')
rep('E6b', 'case IT_WAIT_REG_MEM64: if (!done) wait_reg_mem(p, true); break;',
    'case IT_WAIT_REG_MEM64: if (!done && !bc5::gpu_waits_on()) wait_reg_mem(p, true); break; // exp 0444')

# E7: under the switch with fewer than 2 acb rings, every guest queue shares one ring with its writers:
# a GPU wait ahead of its writer on that ring waits until the kernel's job timeout. Said at start.
rep('E7', T + T + 'if (n > bc5::direct::kComputeRings) n = bc5::direct::kComputeRings;\n',
    T + T + 'if (n > bc5::direct::kComputeRings) n = bc5::direct::kComputeRings;\n' +
    T + T + 'if (bc5::gpu_waits_on() && n < 2) // exp 0444\n' +
    T + T + T + 'std::fprintf(stderr, "[bc5] exp 0444: BC5_DIRECT_GPU_WAITS with BC5_DIRECT_ACB_RINGS=%d: every guest queue shares one ring with its writers; a wait ahead of its writer waits for the kernel timeout\\n", n);\n')

b = s.encode('utf-8', 'surrogateescape')
open(dst, 'wb').write(b)
print('mk444: wrote', dst, hashlib.md5(b).hexdigest()[:8], 'from', hashlib.md5(open(src, 'rb').read()).hexdigest()[:8])
