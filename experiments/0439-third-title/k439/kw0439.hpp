// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag kw439): candidate G, BC5_0439_KEEP_XQ_WAITS=1 (README item 49; the top session, 11-22 ~09:30).
// The host decides a cross-queue WAIT_REG_MEM at the submit: kept for the GPU when memory does not satisfy it yet and a
// ring will satisfy it, else served on the CPU, given up, or, when memory satisfies it already, dropped ("met at
// submit"). The console's GPU decides every such wait at the packet. G keeps, on a compute ring, a wait on a label the
// buffer does not write itself even when memory satisfies it at the submit, so the GPU decides it at the packet.
// Not kept by G: a wait in a GFX-ring buffer (the game thread's dcb waits stay as they are), a wait on a label the
// buffer writes itself (the filter's own rule), and a wait memory does not satisfy (the existing rule decides those).
// Deadlock on our side that the console cannot have: none found. A kept satisfied wait passes at the packet unless the
// title rewrites the label before the packet; its later writer is then either on another ring (submitted before or
// after: ours do not hold one ring behind another), in this queue's own later buffers (the same order the console
// has), or in the open chain, which the caller flushes first.
#pragma once

namespace bc5::kw439 {

// on: the switch; acb: the buffer is an acb; compute: it goes to a compute ring; self: the buffer writes the label
// itself earlier; satisfied: memory satisfies the wait now.
inline bool keep_satisfied(bool on, bool acb, bool compute, bool self, bool satisfied) {
#if defined(BC5_KW439_PLANT_GFX) // the planted bug: GFX-ring buffers kept too
    return on && acb && !self && satisfied;
#else
    return on && acb && compute && !self && satisfied;
#endif
}

} // namespace bc5::kw439
