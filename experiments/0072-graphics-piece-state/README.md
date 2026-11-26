# 0072 — what a graphics piece replaying its own packets would lose (ADR 0008, step 1)

**Question.** Splitting the main graphics buffer at a cross-queue wait faulted in runs 44 and 123
(a shader fetch at `0x800000005000`). There, each later piece had only its own buffer's
register-setting packets replayed before it. ADR 0008 supposes that a piece also relies on state
set by earlier buffers of the frame, and that other processes' work on the ring between two
pieces destroys that state. How much state is that?

**Setup.** `backend/experiments/piece-check` (new, no GPU) reads the 60 buffers of a later level
dumped in experiment 0061, in submission order: about three frames, private.

For each buffer it collects the registers set by:
- `SET_CONFIG/CONTEXT/SH/UCONFIG_REG[_INDEX]`;
- the register ranges of `LOAD_*_REG`;
- `LOAD_*_REG_INDEX` with consecutive registers.

Indexed loads in pairs format keep their registers in memory, which a dump does not have; they
are counted as "unknown". At every memory `WAIT_REG_MEM[64]` of a graphics buffer of 1,000 dwords
or more, it reports two numbers per register space: the registers set in the buffer before the
wait, and those set only by earlier buffers. Output: `raw/piece-check.txt` (file names
shortened).

**Result.** At every such wait of the frame's main graphics buffers (50,000–118,000 dwords),
from the second frame on:

| State | set by this buffer before the wait | set only by earlier buffers |
|---|---|---|
| context registers | 0 | 921 |
| SH registers | 0–91 | 86–177 |
| UCONFIG registers | 3 | 57 |
| packet state (`SET_BASE`, `INDEX_*`, …) | | 0–1 kinds |
| indexed loads in pairs format (registers unknown) | 6–1,357 | 700–4,100 |

The buffers set their context registers only through indexed tables, and none at all before
their first waits.

**Verdict.** Passed for its question: a piece that replays only its own buffer's packets misses
more than a thousand registers. The frame's state builds up across buffers, the console's
preamble and header buffers included. This fits the run-123 fault. The prefix of ADR 0008 has to
come from a tracker that follows every buffer of the context and reads the indexed tables from
memory, which the host can do and a dump cannot. Next (step 1 continued): that tracker in the
backend, checked in the host without submitting the pieces.
