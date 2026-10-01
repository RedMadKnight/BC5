# 0020 — Past the intro: what the game needs from the host after its video (F43)

**Question.** With the GPU path carrying the game through its whole intro (experiment 0018, run
93), what stops it next, and can the host provide it without system modules (there is no firmware
dump to load any from)?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`; host as of experiment 0018 on
the dma-buf backing (`KYTY_BC5_DMABUF=1`), run command as in experiment 0017. Function names of
unresolved imports come from a public NID table (`ps5rs`, `data/nids.csv`).

**Result.**

*Run 93* (experiment 0018) ended in 124 calls to two unresolved `sce::Json` imports
(`Value::referValue(const String&)`, `Value::toString(String&) const`) and a null write.
KytyPlus has an HLE `Json2` library; it lacked those two and 26 more the game imports
(`Array`/`Object` iterators, copy constructors, setters, `getUInteger`, `String` comparisons).
All 28 were added (patch 0001, `libJson2.cpp`; layout assumptions for iterators and the object
iterator's pair are marked `TODO(verify)`). Without the GPU every `Json2` import resolves;
116 imports of other libraries remain unresolved (kernel 30, voice chat 17, audio propagation
16, …), none of them called so far.

*Run 94* (15:44, GPU): 14,199 submissions, none failed, 933 flips, the whole intro again. No
unresolved JSON call any more. The game now stops on **its own assertion**: in its network
module's JSON helper a value it expects to be a boolean has another type, and the assert handler
writes through a null pointer. Which document and which member is not visible in the log, so the
library got a trace (`KYTY_BC5_JSON_TRACE=1`: keys, types, parsed and produced text).

**Verdict.** Open: the next run, with the trace on, names the member; then either the library's
answer for it is wrong or the document comes from a service the host answers with nothing.
