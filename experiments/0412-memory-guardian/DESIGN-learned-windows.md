# Learned windows: what they are, why they exist, and the rule that replaces them (exp 0412, 2026-11-12)

On the maintainer's word of 2026-11-12: "Wyuczone okna nie są rozwiązaniem tylko obejściem. Zleć znalezienie
rozwiązania". Marks: [C] read in our code, [M] measured (with its source), [I] inferred. `P` is
`backend/kytyplus-patches/0001-bc5-lle-agc.patch`, `HO` is `docs/HANDOFF.md`.

## 1. What a learned window is [C]

- A line `0x<lo> 0x<bytes>` in the file `BC5_DIRECT_LEARNED` names (the second title: `~/bc5-work/direct-learned-pkg.txt`).
  The emulator writes it itself: after a 2 s fence timeout it reads the last GPU fault address from the kernel
  (`AMDGPU_INFO_GPUVM_FAULT`) and `learned_add` saves 96 MiB around it (the address rounded down to 64 MiB, minus
  32 MiB; P:29546). A fault costs 14 s (2 s timeout, 12 s reset and reopen; F44, F53). Nothing checks the address:
  junk addresses are saved like real ones (exp 0040).
- `learned_apply` (P:29694) runs before a submission whenever the layout generation changed, and for every window:
  1. `direct_force`: every 2 MiB chunk of the direct-memory file (and of the private-memory file) that lies under
     any view inside the window is imported and pinned, written or not, lazy heap or not;
  2. `map_window`: every writable anonymous VMA inside the window not mapped yet becomes a userptr BO;
  3. `scratch_fill`: every address inside the window where the guest has **no range at all** gets our shared 2 MiB
     zero buffer mapped over it (reads give zero, writes land in the shared buffer and mean nothing).
  The same pass puts 2 MiB of zero buffer behind every eager heap of 32 MiB or more (exp 0037).
- It is a memory of earlier runs: per title, per version of the title, per heap placement. F473 (exp 0364) states it:
  "the list grows one hang at a time and the title's heap placement moves".

## 2. History [M, from the experiments' own READMEs]

| when | what | source |
|---|---|---|
| 2026-09-30 | introduced for ASTRO BOT: texture fetches from GPU-generated surfaces the CPU never touched faulted, because only CPU-written pages were imported; one region learned per run | exp 0016 runs 32–37, F30 |
| 2026-10-09 | the second title gets its own file; its faults in `CommitIABufferAllocator` were cured mainly by the eager list | exp 0036, 0037, D15 |
| 2026-10 | reads up to 122 MiB past heap ends, in guest holes: the zero buffer | exp 0037, 0042 |
| 2026-10-22 | 9 windows in the AMM window: the title's first-use clears write 64 KiB blocks of sparse UI targets it never backs; "the console drops such writes" | F257 (exp 0199) |
| 2026-10-24 | 107 lines: 46 at junk addresses (a bit above 40 set, or 0), 61 real, 3,884 MiB of address space | F353 (exp 0288) |
| 2026-10-28 | pointers in shader user data into heaps the lazy list leaves out (`orbis_user_malloc`, `FileSystem`); 31 windows dropped, three runs still passed | F468, F472, F473 (exp 0364) |
| 2026-11 | 109–112 lines; the windows inside eager heaps add nothing | exp 0379, F622 |

Counts on file over time: 2, 5, 18, 95, 102, 107, 108, 109, 112. The file on the box today and what each window
brings in during a run: section 6 (to be measured, `learnclass0412.py`).

## 3. The root cause [C][I]

On the console the GPU works in the title's own address space: whatever the title mapped, the GPU can reach at the same
address, and an access to an address with nothing mapped does not stop the GPU (F257: such writes are dropped; F162:
PRT pages, reads 0 and writes dropped, are what the title's own AMM code expects) [M for the AMM window, I beyond it].
Our GPU address space is instead **a subset** of the guest's, and four heuristics decide what is in it:

| heuristic | what it imports | what it is |
|---|---|---|
| "has data" (`SEEK_DATA`, P:28996–29006) | a chunk of a heap once the **CPU** wrote into it | a guess: GPU-written memory (render targets, compute outputs) is never "data" before its first use |
| `BC5_DIRECT_EAGER_NAMES` / `LAZY_NAMES` | named heaps whole / never | a per-title list, the same kind of memory as the learned file |
| hints (target bases ±32 MiB, shader user data) | what a command buffer names | sees only what the buffer names, not what a shader computes |
| learned windows | 96 MiB around a past fault | the catch-all for the three above |

So the learned windows do not cover a call we fail to handle or a late mapping: nothing in the history shows one.
They cover **our own choice to leave mapped guest memory out** (kinds K1, K2) and **the missing "no fault" behaviour of
unmapped addresses** (K3, K4):

| kind | what the address was | cure by rule |
|---|---|---|
| K1 | memory under a view of direct memory that we had not imported: never written by the CPU, or in a lazy-listed heap | R1 |
| K2 | writable anonymous guest memory (flexible memory, stacks) not handed to the GPU | R1 (the anonymous sync) |
| K3 | an address near real heaps where the guest has no range: reads past a heap's end, sparse AMM blocks never backed | R2 |
| K4 | a junk address: a bit above 40 set, address 0 (46 of 107 lines on 10-24) | R2 |

## 4. The rule

- **R1, map when the title maps.** Every range the title maps as direct memory is imported and GPU-mapped in full at
  the sync that follows its map call (the views' generation already triggers that sync before the next submission
  reaches the kernel), with no name list and no "has data" test. In code this is one condition in `direct_sync_one`
  (P:28990: every view is treated as the eager ones are today). The eager and lazy lists then mean nothing.
- **R2, unmapped addresses read zero and drop writes.** One PRT mapping (`AMDGPU_VM_PAGE_PRT`, no BO, no memory) under
  the whole guest address span at device open; real mappings replace it and are replaced by it again
  (`Device::map_prt_window`, `va_map`/`va_unmap` with `AMDGPU_VA_OP_REPLACE`: all there since exp 0102, used today
  only for the AMM window behind `BC5_DIRECT_AMM_PRT`). It replaces `scratch_fill`, the 2 MiB guards and the junk
  windows. gfx1013 takes PRT mappings without fault: F162, and F260's 19-minute session with no GPU fault of any kind.
- **Nothing remembered.** The file is not read. `learned_add` stays as a catcher behind a switch: it journals
  "would learn 0x…" and adds nothing.

What then runs before a submission: nothing of `learned_apply` (no window pass, no fill pass). That removes the 1.9 s
of device-mutex time exp 0415 measured in the menu load, and 2.0 s per 34 s of play.

## 5. The price in pinned memory, and what pays for it

R1 pins every view. Under views in play: 12,189 MiB; pinned today at the wall 11,700–11,930 MiB (README sections
35, 36) [M]. **So R1 costs more pinned memory than today: +768 MiB measured on the scripted route (README section 51: views 12,186 MiB, pinned under a view 11,418; the 0.26–0.49 GiB first written here compared against a pin that included orphans)**, in the heaps imported "by
data" (`AssetHeap` 1,166 under views, 730–930 pinned; `InitAllocator` 652, 414–450 pinned) and the lazy `Wwise`
(220). The learned windows pin part of that already; how much is the first measurement (section 6). R2 costs nothing
and gives back the zero buffer's mappings.

This goes the wrong way at the wall (deficit 0.4–0.5 GiB today), and it has to be said plainly. It is paid by the
options of `DESIGN-memory-architecture.md`:
- **A** (the console's budget outside the title): 0.7–1.1 GiB; first measurement in section 50.
- **B** (never-written pages are not created): with R2 in place a never-written chunk can stay PRT, where a GPU *read*
  is already correct (the file holds zeros there). Only a GPU *write* into such a chunk is lost. That is exactly the
  open half of experiment E1; until it is answered R1 stays "pin whole".
- **C** (CPU-purpose heaps out of the pin) is unchanged.

A cheaper R1 that keeps "by data" and relies on PRT for the rest would hide GPU writes silently, the defect of the
zero skip (section 48). Not proposed.

## 6. Measurements (the first is README section 51; kind K2 measured as 0 MiB today)

1. The file on the box: lines, kinds K1–K4, what each window brings in during a run (`learnclass0412.py` on a
   journal of a normal run); the ledger's "learned-forced" pin.
2. A scripted run with an **empty** learned file on today's build (no code change): which faults come back. Each is a
   14 s freeze and a GPU reset, so it needs its own slot and the kernel log streamed.
3. Build with three default-off switches (fixes first): `BC5_GUARD_MAP_RULE=1` (R1), `BC5_GUARD_PRT_BG=1` (R2),
   `BC5_GUARD_LEARN_LOG=1` (the catcher). Gate: R1+R2 on, the file off: no GPU fault, no "would learn" line over the
   scripted route and a long play of his; the pin and the lowest available memory against fast8.

Open before the build: whether one PRT mapping over the whole span is accepted and what it costs in page tables
(exp 0102 mapped 64 GiB); with R2 on a miss of R1 no longer faults, so R1 is tested first **without** R2.

## 7. After the order of 2026-11-13: no windows, rules by kind

The maintainer: the learned windows are to go, and the solution is to be in software. Since 08:17 the second title's
launchers read no learned file and the catcher only logs (README section 60); `mknl0412.py` (tag nl412) takes the
path out of the unit. **A GPU fault is from now on a bug report with an address and a kind, never a window.** The
catcher's line gives the kind (`mr412::classify`): K1 a view not imported (by-data, lazy, or eager and failed), K2
anonymous guest memory not mapped, K3 no guest range (a hole), K4 a junk address, K5 imported but not mapped at the
fault, K6 mapped (a protection fault or a stale report).

What replaces the windows is not "pin everything" (R1: section 5, and README section 53: the box cannot hold it) but
one exact rule per kind, each taken from what the title itself tells the host:

| kind | what the title tells us, and when | the rule | state |
|---|---|---|---|
| K1, GPU-written memory the CPU never wrote | the address of every colour target, depth and stencil buffer, every destination of a copy or resolve, every buffer a shader may write (its descriptors in the user data), is in registers and packets of the command buffer **before** the job runs | **import at bind time, exactly**: the range the descriptor names (base and size from the surface's or buffer's own description), not a ±32 MiB guess around a base. The hints path already reads the target bases (`hint_targets`) and the user-data hint reads shader buffers (exp 0364); they are made exact and complete | to build: the next unit |
| K1, a lazy-listed heap the GPU reads | the same descriptors name it when it is used | the same rule; the lazy list then only says "do not import by data", never "do not import when named" | follows from the rule above |
| K3, an address near real memory with nothing mapped (reads past a heap's end, sparse AMM blocks the title never backs) | the title's own map calls say where nothing is mapped | over **true holes only**: the console's behaviour (reads zero, writes dropped; E1 cases 1 and 3, F257). Never over a range the title mapped and we did not import: there a fault must stay loud | to build; see below |
| K4, a junk address | nothing: the address is not the title's | the same true-hole behaviour up to the end of the guest's span; beyond it a fault is a bug of ours in a register or a shader operand (F663) and is reported | to build |
| K2, anonymous guest memory | the anonymous sync | measured 0 MiB in the windows (README section 51); no rule needed until a line of this kind appears | none |
| K5, K6 | | not a mapping question: timing or a protection bug; each is investigated as a defect | none |

**True holes without a per-hole pass.** `scratch_fill` walked windows and mapped a zero buffer piece by piece. The
rule form: one PRT mapping under the guest's span at device open (as `BC5_GUARD_PRT_BG` does), and in the mapping
rebuild every part of a **view that is not imported** is taken out of it again (`AMDGPU_VA_OP_CLEAR` on that range),
so that an access there faults and is named. The rebuild already computes, per view, which chunks are imported; the
complement under views is the list to clear. The cost in page tables and time of a clear per unimported run is the
first thing to measure (E1 measured neither).

**Order of work.**
1. nl412 in the next patch (the integrator's vehicle), with or without the heap-end guards as the top decides; the
   guards are themselves the K3 rule in a narrow form (2 MiB behind each eager heap, only where the guest has no range).
2. The K1 rule: exact import at bind time. First step is a catcher on the laptop's side of the build: for every
   target, depth buffer and shader-written buffer a submission names, journal when its range is not fully imported
   at submission (it would have faulted without the hint's ±32 MiB): that count says how much the guesses still do.
3. The K3/K4 rule as above, tested first on a run that is not at the wall (README section 54's lesson).
4. Every "would learn" line of his play is classified and answered by one of these rules; the table grows only by
   kinds, never by addresses.

### 7.1 The alias rule (the second remembered list; the top session's direction of 2026-11-13)

No title constant and no remembered line: **when the title names a GPU address A that is not mapped, and A with its
top byte (bits 47:40) cleared lies in a mapped guest view, that view is also mapped at the tagged address**, at bind
time, for any tag and any title. An address whose untagged form is not mapped either stays unmapped and loud.

Where the tagged pointers are first visible to the host [M, exp 0056]: **not in a register and not in a packet
operand**. No program register carries the byte (exp 0055). The title's programs load the pointer from a constant
buffer and call through it: `s_buffer_load_dwordx2 s[14:15], s[4:7], 0x70`, a test for non-zero, `s_swappc_b64`.
The buffer's descriptor (s[4:7], user-data registers 4 to 7) IS in the command buffer before the job runs; the
pointer is inside the buffer, at an offset the program chooses (0x70 in the one disassembled).

So the host can apply the rule only by reading the constant buffers the descriptors name, as the hints path
already does for shader buffers (exp 0364) and as the scan of README sections 39 and 48 did for tables (the first
2 KiB behind every address a buffer names): look for 8-byte values whose bits 47:40 are non-zero, whose low 40 bits
lie in a mapped view, and whose tagged form is not mapped; alias that view under that byte. Two things bound the
cost (the table scan of section 39 took 8 % of the submitting threads when run on every buffer):
1. an alias is per (view, byte), not per pointer: once the code heap is mapped under 0x80 every later pointer of
   that kind is already served, so a scan that finds nothing new ends at once per descriptor (one lookup);
2. only a program that calls through a pointer needs its buffers read. Whether a program does is a property of its
   code: one pass over a program the first time its address is bound, looking for the indirect call's encoding
   (to be taken from LLVM's AMDGPU instruction tables with the file and commit, not from memory), cached by
   program address.
What it does not cover: a pointer the shader computes, or one in a buffer reached through a second pointer. The
catcher's K4 line (a tagged fault whose low 40 bits are guest memory) is the report for those.

Order: the rule behind a default-off switch with the list still present and a line "alias by rule would map view X
under byte B" (does the rule find the one real line by itself on the route?); then a run with the list cut to
nothing and the rule on; then the list, `alias_learn` and the file's read are removed as the learned windows were.
