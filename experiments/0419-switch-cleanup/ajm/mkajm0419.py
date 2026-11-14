#!/usr/bin/env python3
r"""BC5 experiment 0419, tag ajt: three AJM switches for the next private build, all off by default.
  KYTY_BC5_AUDIO_TRAIL=1   catcher: the last 256 AJM calls in a ring; when the guest faults the handler prints the
                           ring and 0x200 bytes around rdi, rsi, rbx, rcx, r13, r15, naming every value that lies in
                           an AJM buffer of the ring
  KYTY_BC5_AJM_DEFER=1     fix candidate: a batch's jobs run at sceAjmBatchStart (the console's order), not when added
  KYTY_BC5_AJM_LIVE_IDS=1  fix candidate: an instance id still alive is not given out again
Always on, one line each for the first 8: an instance id given out while alive, a job on an instance that does not
exist. With all three unset the calls do what they did (the job's work first, then the job is appended).
Edits src/libs/ajm.cpp and src/loader/runtimeLinker.cpp and copies ajm_trail.hpp to src/bc5/. Every edit must match
exactly once. NOT compiled on the laptop (ajm.cpp needs the ffmpeg headers, the handler is Linux only): the pure part
is tested by test0419ajm.cpp, the rest compiles first on the box.
usage: mkajm0419.py <tree root>"""
import os, re, shutil, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ed0419g import File

root = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
shutil.copyfile(os.path.join(here, "ajm_trail.hpp"), os.path.join(root, "src", "bc5", "ajm_trail.hpp"))

f = File(os.path.join(root, "src", "libs", "ajm.cpp"))
assert not f.crlf
f.gone("Bc5Ajm", "ajm_trail")

f.sub('#include "kernel/pthread.h" // BC5 (experiment 0183): KernelGetProcessTime for the AJM dump\n',
      '#include "kernel/pthread.h" // BC5 (experiment 0183): KernelGetProcessTime for the AJM dump\n'
      '#include "bc5/ajm_trail.hpp" // BC5 exp 0419 (ajt)\n'
      '#include "bc5/env_rule.hpp"\n'
      '#include "common/threads.h"\n'
      '#include <functional>\n')

BLOCK = r'''
// ---- BC5 experiment 0419, tag ajt (mkajm0419.py): KYTY_BC5_AUDIO_TRAIL, KYTY_BC5_AJM_DEFER, KYTY_BC5_AJM_LIVE_IDS ----
// The title's CPU fault at eboot+0x1b349f (audio-record-fault.md): a catcher and two fix candidates, all off by default.
bool Bc5AudioTrailOn();
bool Bc5AjmTrailWhere(uint64_t v, char* buf, size_t cap);
void Bc5AjmTrailDump(void (*out)(const char*, ...));

static bool Bc5AjmSwitch(const char* name, const char* what) {
	const bool on = bc5::env_rule::on(std::getenv(name));
	std::fprintf(stderr, "[bc5] exp 0419 ajt: %s %s (%s)\n", what, on ? "on" : "off", name);
	return on;
}
bool Bc5AudioTrailOn() {
	static const bool on = Bc5AjmSwitch("KYTY_BC5_AUDIO_TRAIL", "ajm trail");
	return on;
}
static bool Bc5AjmDeferOn() {
	static const bool on = Bc5AjmSwitch("KYTY_BC5_AJM_DEFER", "ajm jobs run at the batch start");
	return on;
}
static bool Bc5AjmLiveIdsOn() {
	static const bool on = Bc5AjmSwitch("KYTY_BC5_AJM_LIVE_IDS", "ajm live instance ids kept");
	return on;
}

static bc5::ajm_trail::Trail   g_bc5_ajm_trail;
static bc5::ajm_trail::Pending g_bc5_ajm_pending;
static std::atomic<uint64_t>   g_bc5_ajm_creates {0}, g_bc5_ajm_destroys {0}, g_bc5_ajm_dups {0}, g_bc5_ajm_missing {0},
    g_bc5_ajm_dropped {0};

static void Bc5AjmNote(const char* kind, uint32_t instance, const void* in, size_t in_size, const void* out,
                       size_t out_size, const AjmDecodeResult* res) {
	if (!Bc5AudioTrailOn()) {
		return;
	}
	bc5::ajm_trail::Rec r;
	r.t_us     = LibKernel::KernelGetProcessTime();
	r.kind     = kind;
	r.instance = instance;
	r.tid      = Common::Thread::GetThreadIdUnique();
	r.in       = reinterpret_cast<uint64_t>(in);
	r.in_size  = in_size;
	r.out      = reinterpret_cast<uint64_t>(out);
	r.out_size = out_size;
	if (res != nullptr) {
		r.result   = res->result;
		r.internal = res->internal_result;
		r.consumed = static_cast<uint32_t>(res->input_consumed);
		r.produced = static_cast<uint32_t>(res->output_written);
		r.frames   = res->frames;
	}
	g_bc5_ajm_trail.add(r);
}

static void Bc5AjmCreated(uint32_t instance, uint32_t skipped) {
	const uint64_t n = g_bc5_ajm_creates.fetch_add(1, std::memory_order_relaxed) + 1;
	if ((n & 0xfffu) == 0 && Bc5AudioTrailOn()) { // the rate of creates: the 14-bit slot wraps at 16,384
		std::fprintf(stderr, "[bc5] exp 0419 ajt: %" PRIu64 " instances created, %" PRIu64 " destroyed, t %.3f s\n", n,
		             g_bc5_ajm_destroys.load(std::memory_order_relaxed), static_cast<double>(LibKernel::KernelGetProcessTime()) / 1e6);
	}
	if (skipped != 0 && !Bc5AjmLiveIdsOn()) {
		if (g_bc5_ajm_dups.fetch_add(1, std::memory_order_relaxed) < 8) {
			std::fprintf(stderr, "[bc5] exp 0419 ajt: instance id 0x%08" PRIx32 " given out while still alive (create #%" PRIu64
			                     "): the older instance's decoder is replaced\n", instance, n);
		}
		Bc5AjmNote("create-while-alive", instance, nullptr, 0, nullptr, 0, nullptr);
		return;
	}
	if (skipped != 0 && g_bc5_ajm_dups.fetch_add(1, std::memory_order_relaxed) < 8) {
		std::fprintf(stderr, "[bc5] exp 0419 ajt: %" PRIu32 " live instance id(s) passed over, 0x%08" PRIx32 " given (create #%" PRIu64 ")\n",
		             skipped, instance, n);
	}
	Bc5AjmNote("create", instance, nullptr, 0, nullptr, 0, nullptr);
}

static void Bc5AjmDestroyed(uint32_t instance, bool existed) {
	g_bc5_ajm_destroys.fetch_add(1, std::memory_order_relaxed);
	Bc5AjmNote(existed ? "destroy" : "destroy-missing", instance, nullptr, 0, nullptr, 0, nullptr);
}

static void Bc5AjmMissing(uint32_t instance) {
	if (g_bc5_ajm_missing.fetch_add(1, std::memory_order_relaxed) < 8) {
		std::fprintf(stderr, "[bc5] exp 0419 ajt: a job on instance 0x%08" PRIx32 ", which does not exist or has no decoder\n", instance);
	}
}

// A job of a batch: today its work runs when the job is added; with KYTY_BC5_AJM_DEFER it runs at sceAjmBatchStart,
// and a job that did not fit into the batch does not run at all.
static int AjmAppendJob(AjmBatchInfo* info, size_t job_size, const char* name);
static int Bc5AjmJob(AjmBatchInfo* info, size_t job_size, const char* name, std::function<void()> work) {
	if (!Bc5AjmDeferOn()) {
		work();
		return AjmAppendJob(info, job_size, name);
	}
	const int rc = AjmAppendJob(info, job_size, name);
	if (rc == OK) {
		g_bc5_ajm_pending.push(info->buffer, std::move(work));
	}
	return rc;
}

bool Bc5AjmTrailWhere(uint64_t v, char* buf, size_t cap) {
	bc5::ajm_trail::Rec r;
	bool                is_out = false;
	uint64_t            off    = 0;
	if (v < 0x10000 || !g_bc5_ajm_trail.where(v, &r, &is_out, &off)) {
		return false;
	}
	std::snprintf(buf, cap, "ajm #%" PRIu64 " %s instance 0x%08" PRIx32 " %s+0x%" PRIx64, r.seq, r.kind, r.instance,
	              is_out ? "out" : "in", off);
	return true;
}

// Called by the guest fault handler: no lock, no allocation.
void Bc5AjmTrailDump(void (*out)(const char*, ...)) {
	out("ajm trail: %" PRIu64 " records in all; creates %" PRIu64 ", destroys %" PRIu64 ", ids given out or passed over while alive %" PRIu64
	    ", jobs on a missing instance %" PRIu64 ", deferred jobs never started %" PRIu64 "\n",
	    g_bc5_ajm_trail.end(), g_bc5_ajm_creates.load(), g_bc5_ajm_destroys.load(), g_bc5_ajm_dups.load(), g_bc5_ajm_missing.load(),
	    g_bc5_ajm_dropped.load());
	for (uint64_t i = g_bc5_ajm_trail.first(); i < g_bc5_ajm_trail.end(); i++) {
		const auto& r = g_bc5_ajm_trail.at(i);
		out("ajm trail: #%" PRIu64 " t %" PRIu64 " us thread %d %s instance 0x%08" PRIx32 " in %016" PRIx64 "+%" PRIx64 " out %016" PRIx64 "+%" PRIx64
		    " result %08" PRIx32 "/%08" PRIx32 " consumed %" PRIu32 " produced %" PRIu32 " frames %" PRIu32 "\n",
		    r.seq, r.t_us, r.tid, r.kind, r.instance, r.in, r.in_size, r.out, r.out_size, static_cast<uint32_t>(r.result),
		    static_cast<uint32_t>(r.internal), r.consumed, r.produced, r.frames);
	}
}
// ---- end of ajt's block ----

'''
f.sub("static uint8_t* AjmReserveJob(AjmBatchInfo* info, size_t job_size) {\n",
      BLOCK.lstrip("\n") + "static uint8_t* AjmReserveJob(AjmBatchInfo* info, size_t job_size) {\n")

# the decode: a record of every one, and the missing instance counted
f.cut("static AjmDecodeResult AjmDecodeInstance(uint32_t instance, const void* input, size_t input_size,\n",
      "&state->gapless);\n}\n",
      r'''static AjmDecodeResult AjmDecodeInstance(uint32_t instance, const void* input, size_t input_size,
                                         void* output, size_t output_size, bool multiple_frames) {
	std::scoped_lock lock(g_ajm_instances_mutex);
	auto*            state = AjmFindInstanceLocked(instance);
	if (state == nullptr || state->decoder == nullptr) {
		AjmDecodeResult result {};
		result.result = AJM_RESULT_INVALID_PARAMETER;
		Bc5AjmMissing(instance); // BC5 exp 0419 (ajt)
		Bc5AjmNote("decode-missing", instance, input, input_size, output, output_size, &result);
		return result;
	}

	const auto bc5_result = state->decoder->Decode(input, input_size, output, output_size, multiple_frames,
	                                               &state->gapless);
	Bc5AjmNote(multiple_frames ? "decode" : "decode-1", instance, input, input_size, output, output_size, &bc5_result); // ajt
	return bc5_result;
}
''')
# the split decode works on host copies: the guest's output pieces get records of their own
f.sub("\t\toutput_offset += output_buffers[i].size;\n\t}\n\n\treturn result;\n}\n",
      "\t\toutput_offset += output_buffers[i].size;\n"
      "\t\tBc5AjmNote(\"split-out\", instance, nullptr, 0, output_buffers[i].address, output_buffers[i].size, &result); // BC5 exp 0419 (ajt)\n"
      "\t}\n\n\treturn result;\n}\n")

# instance ids
f.sub("\tconst auto slot = (g_ajm_next_instance.fetch_add(1, std::memory_order_relaxed) & 0x3fffu);\n"
      "\t*instance       = (codec << 14u) | slot;\n",
      "\t// BC5 exp 0419 (ajt): the same id rule ((codec << 14) | a 14-bit slot from the counter); whether the id is alive is\n"
      "\t// counted, and with KYTY_BC5_AJM_LIVE_IDS a live one is passed over\n"
      "\tuint32_t bc5_skipped = 0;\n"
      "\t{\n"
      "\t\tstd::scoped_lock lock(g_ajm_instances_mutex);\n"
      "\t\t*instance = bc5::ajm_trail::next_id(\n"
      "\t\t    g_ajm_next_instance, codec, Bc5AjmLiveIdsOn(), [](uint32_t id) { return g_ajm_instances.find(id) != g_ajm_instances.end(); },\n"
      "\t\t    &bc5_skipped);\n"
      "\t}\n"
      "\tBc5AjmCreated(*instance, bc5_skipped);\n")
f.sub("\tstd::scoped_lock lock(g_ajm_instances_mutex);\n\tg_ajm_instances.erase(instance);\n\n\treturn OK;\n",
      "\tsize_t bc5_n = 0; // BC5 exp 0419 (ajt)\n"
      "\t{\n"
      "\t\tstd::scoped_lock lock(g_ajm_instances_mutex);\n"
      "\t\tbc5_n = g_ajm_instances.erase(instance);\n"
      "\t}\n"
      "\tBc5AjmDestroyed(instance, bc5_n != 0);\n\n\treturn OK;\n")

# the batch
f.sub("\tinfo->last_good_job    = nullptr;\n\tinfo->last_good_job_ra = nullptr;\n\n\treturn OK;\n",
      "\tinfo->last_good_job    = nullptr;\n\tinfo->last_good_job_ra = nullptr;\n"
      "\tif (Bc5AjmDeferOn()) { // BC5 exp 0419 (ajt): jobs of this buffer that were never started do not run\n"
      "\t\tg_bc5_ajm_dropped.fetch_add(g_bc5_ajm_pending.reset(buffer), std::memory_order_relaxed);\n"
      "\t}\n\n\treturn OK;\n")
f.sub("\t*batch = g_ajm_next_batch.fetch_add(1, std::memory_order_relaxed);\n",
      "\t*batch = g_ajm_next_batch.fetch_add(1, std::memory_order_relaxed);\n"
      "\t{ // BC5 exp 0419 (ajt): with KYTY_BC5_AJM_DEFER the batch's jobs run here, in order, before the start returns\n"
      "\t\tAjmDecodeResult bc5_r {};\n"
      "\t\tbc5_r.frames = static_cast<uint32_t>(Bc5AjmDeferOn() ? g_bc5_ajm_pending.run(info->buffer) : 0);\n"
      "\t\tBc5AjmNote(\"batch-start\", *batch, info->buffer, info->offset, nullptr, 0, &bc5_r);\n"
      "\t}\n")
f.sub('\tLOGF("\\t context = %" PRIu32 ", batch = %" PRIu32 "\\n", context, batch);\n\treturn OK;\n',
      '\tLOGF("\\t context = %" PRIu32 ", batch = %" PRIu32 "\\n", context, batch);\n'
      '\tBc5AjmNote("batch-cancel", batch, nullptr, 0, nullptr, 0, nullptr); // BC5 exp 0419 (ajt)\n\treturn OK;\n')

# the jobs that read or change an instance: their work becomes a callable
HEAD = b"\tPRINT_NAME();\n\tEXIT_NOT_IMPLEMENTED(info == nullptr);\n"
JOBS = ["initialize", "clear-context", "decode", "decode-single", "decode-split", "get-info", "get-codec-info", "set-gapless",
        "get-gapless", "get-resample-info", "control", "run", "run-split"]
for name in JOBS:
    m = list(re.finditer(rb'\treturn AjmAppendJob\(info, ([^\n]+), "' + name.encode() + rb'"\);\n\}\n', f.b))
    assert len(m) == 1, (name, len(m))
    m = m[0]
    a = f.b.rfind(HEAD, 0, m.start())
    assert a > 0
    body = f.b[a + len(HEAD):m.start()]
    assert b"return" not in body and b"KYTY_SYSV_ABI" not in body, name
    pre = b""
    if name in ("decode-split", "run-split"):
        # the console copies the buffer lists into the batch when the job is made
        pre = (b"\t// BC5 exp 0419 (ajt): the two buffer lists are copied when the job is made\n"
               b"\tconst std::vector<AjmBuffer> bc5_in(input_buffers, input_buffers + (input_buffers != nullptr ? input_buffers_num : 0));\n"
               b"\tconst std::vector<AjmBuffer> bc5_out(output_buffers, output_buffers + (output_buffers != nullptr ? output_buffers_num : 0));\n")
        P_IN, P_OUT = rb"\binput_buffers\b(?! = 0x)", rb"\boutput_buffers\b(?! = 0x)"  # not the log line's own text
        n_in, n_out = len(re.findall(P_IN, body)), len(re.findall(P_OUT, body))
        assert n_in == 2 and n_out == 2, (name, n_in, n_out)
        body = re.sub(P_IN, b"bc5_in.data()", body)
        body = re.sub(P_OUT, b"bc5_out.data()", body)
    new = (HEAD + pre + b"\treturn Bc5AjmJob(info, " + m.group(1) + b', "' + name.encode() + b'", [=]() { // BC5 exp 0419 (ajt)\n'
           + body + b"\t});\n}\n")
    f.b = f.b[:a] + new + f.b[m.end():]
    f.n += 1
f.save()

g = File(os.path.join(root, "src", "loader", "runtimeLinker.cpp"))
g.gone("Bc5AjmTrail")
g.sub('#include "loader/runtimeLinker.h"\n',
      '#include "loader/runtimeLinker.h"\n'
      "namespace Libs::Audio::Ajm { // BC5 exp 0419 (ajt): KYTY_BC5_AUDIO_TRAIL, src/libs/ajm.cpp\n"
      "bool Bc5AudioTrailOn();\n"
      "bool Bc5AjmTrailWhere(uint64_t v, char* buf, size_t cap);\n"
      "void Bc5AjmTrailDump(void (*out)(const char*, ...));\n"
      "} // namespace Libs::Audio::Ajm\n")
g.sub('\t\tdump_guest_qwords("guest r15", info->r15);\n',
      '\t\tdump_guest_qwords("guest r15", info->r15);\n'
      + r'''		if (Libs::Audio::Ajm::Bc5AudioTrailOn()) { // BC5 exp 0419 (ajt): 0x200 bytes around six registers, then the AJM ring
			auto wide = [](const char* name, uint64_t reg) {
				const uint64_t a = (reg & ~7ull) - 0x100;
				if (reg < 0x10000 || !IsReadableRange(a, 0x200)) {
					return;
				}
				auto* q = reinterpret_cast<const uint64_t*>(a);
				for (uint32_t i = 0; i < 64; i++) {
					char w[112];
					if (i % 4 == 0) {
						Bc5CrashLog("%s%s %016" PRIx64 ":", i == 0 ? "" : "\n", name, a + 8ull * i);
					}
					Bc5CrashLog(" %016" PRIx64, q[i]);
					if (Libs::Audio::Ajm::Bc5AjmTrailWhere(q[i], w, sizeof(w))) {
						Bc5CrashLog(" <%s>", w);
					}
				}
				Bc5CrashLog("\n");
			};
			wide("wide rdi", info->rdi);
			wide("wide rsi", info->rsi);
			wide("wide rbx", info->rbx);
			wide("wide rcx", info->rcx);
			wide("wide r13", info->r13);
			wide("wide r15", info->r15);
			Libs::Audio::Ajm::Bc5AjmTrailDump(Bc5CrashLog);
		}
''')
g.save()
