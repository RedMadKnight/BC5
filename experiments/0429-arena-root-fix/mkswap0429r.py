#!/usr/bin/env python3
"""BC5 exp 0429, the shared swap of R: candidate R on by default for every title, exp 0425's wake slice removed.
    mkswap0429r.py <tree root> [--keep-slice] [--stressor]
The maintainer, 2026-11-18, through the top session: "Wlaczyc R domyslnie we wspolnych buildach => tak, od razu posprzataj
inne rzeczy, ktore po wprowadzeniu R stają się zbedne". On the shared tree at patch 940e8f36 (exp 0432's build 5).
The swap form (no option), both builds:
  - src/kernel/pthread.cpp: exp 0425 C1 (the 200 us wake slice: Bc5SchedAttr, Bc5WakeSliceUs, Bc5ApplyWakeSlice and its
    call) replaced by rrshared0429.cpp (R, from mkrshared0429.py); two Pthread fields (bc5_rr_sleeper, bc5_rr_main);
    MainThread marked; Bc5RrApply at the end of Bc5ApplyGuestPriority;
  - src/kernel/semaphore.cpp: the sleeper hook after a waiter's resume (the place it had in the tested build 14) and
    its declaration;
  - src/bc5/switch_defaults.hpp: kSoft's KYTY_BC5_0425_WAKE_SLICE_US row replaced by KYTY_BC5_0429_RR=1
    (KYTY_BC5_0429_RR=0 turns R off with no build).
Private test builds only, never shared:
  --keep-slice  keeps exp 0425 C1 (code and kSoft row) next to R: the slice-on arm of the stressed pair;
  --stressor    adds exp 0429's KYTY_BC5_0429_GUEST_CPUS (affinity0429.cpp; off unless set): the crash stressor.
Every anchor must occur once; line endings are kept; each unit is checked against its 940e8f36 md5 first, and nothing
is written unless all edits succeed."""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PINS = {  # md5 of the units at patch 940e8f36 (laptop tree f266548 + 940e8f36, its diff reproduces 940e8f36; 2026-11-18)
    'src/kernel/pthread.cpp': None,
    'src/kernel/semaphore.cpp': None,
    'src/bc5/switch_defaults.hpp': None,
}
PINS_FILE = os.path.join(HERE, 'pins-swap0429r.txt')  # "md5 path" lines


def stop(msg):
    sys.exit('mkswap0429r STOP: ' + msg)


def one(text, old, new, what):
    if text.count(old) != 1:
        stop('%s: anchor occurs %d times' % (what, text.count(old)))
    return text.replace(old, new)


def load(path):
    raw = open(path, 'rb').read()
    return raw, b'\r\n' in raw, raw.decode('utf-8').replace('\r\n', '\n')


C1_START = '// ---- experiment 0425 C1: KYTY_BC5_0425_WAKE_SLICE_US=<100..3000> -----------------------------------------------------\n'
C1_END = '// ---- end of experiment 0425 C1 ------------------------------------------------------------------------------------\n'
C1_CALL = '\tBc5ApplyWakeSlice(thread, why); // experiment 0425 C1 (after the nice, which it keeps)\n'
C1_ROW = '''    // exp 0425 C1 (2026-11-16, the maintainer's word): a 200 us EEVDF wake slice for guest threads below priority
    // 733 (pthread.cpp). Soft, so KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off.
    {"KYTY_BC5_0425_WAKE_SLICE_US", "200"},
'''
R_ROW = '''    // exp 0429 R (2026-11-18, the maintainer's word): SCHED_RR through rtkit for the guest's job-worker families
    // (pthread.cpp), in place of exp 0425's wake slice. Soft, so KYTY_BC5_0429_RR=0 turns it off.
    {"KYTY_BC5_0429_RR", "1"},
'''


def pthread(text, keep_slice, stressor):
    rr = open(os.path.join(HERE, 'rrshared0429.cpp'), encoding='utf-8').read()
    if text.count(C1_START) != 1 or text.count(C1_END) != 1:
        stop('pthread: C1 markers')
    i, j = text.index(C1_START), text.index(C1_END) + len(C1_END)
    block = text[i:j] if keep_slice else ''
    aff = ''
    if stressor:
        aff = open(os.path.join(HERE, 'affinity0429.cpp'), encoding='utf-8').read()
    text = text[:i] + block + aff + rr.lstrip('\n') + text[j:]
    text = one(text, '\tstd::atomic<uint64_t> pending_signal_mask {0};\n',
               '\tstd::atomic<uint64_t> pending_signal_mask {0};\n'
               '\tbool                  bc5_rr_sleeper = false; // experiment 0429 R: slept on its worker family\'s semaphore\n'
               '\tbool                  bc5_rr_main    = false; // experiment 0429 R: the runtime main thread, never promoted\n',
               'pthread R fields')
    text = one(text, '\tg_pthread_self->name            = "MainThread";\n',
               '\tg_pthread_self->name            = "MainThread";\n'
               '\tg_pthread_self->bc5_rr_main     = true; // experiment 0429 R: the runtime main thread is never promoted\n',
               'pthread R main mark')
    text = one(text, C1_CALL, (C1_CALL if keep_slice else '') + '\tBc5RrApply(thread, why); // experiment 0429 R\n', 'pthread R hook')
    if 'Bc5ApplyWakeSlice' in text and not keep_slice:
        stop('pthread: Bc5ApplyWakeSlice is left')
    if stressor:  # exp 0429's guest CPU mapping (mk0429.py's edits), private test builds only
        text = one(text, '\t(*attr)->affinity       = 0x7f;\n',
                   '\t(*attr)->affinity       = Bc5GuestDefaultMask(); // experiment 0429: one guest CPU per host CPU when mapping\n',
                   'pthread attr init')
        text = one(text, 'int KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n',
                   'static uint64_t Bc5GuestDefaultMask(); // experiment 0429, defined with its guest CPU block\n\n'
                   'int KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n', 'pthread forward')
        text = one(text, '\tBc5ApplyGuestPriority(thread, "start");\n#endif\n',
                   '\tBc5ApplyGuestPriority(thread, "start");\n\tBc5ApplyAffinity(thread, "start"); // experiment 0429\n#endif\n',
                   'pthread start')
        text = one(text, '''	auto result = PthreadAttrSetaffinity(&thread->attr, mask);

	return result;
}''', '''	auto result = PthreadAttrSetaffinity(&thread->attr, mask);
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	if (result == OK) {
		Bc5ApplyAffinity(thread, "setaffinity"); // experiment 0429
	}
#endif

	return result;
}''', 'pthread setaffinity')
        text = one(text, '\tBc5ApplyGuestPriority(thread, "setprio");\n#endif\n',
                   '\tBc5ApplyGuestPriority(thread, "setprio");\n\tif (Bc5AffinityTrace()) {\n'
                   '\t\tBc5ApplyAffinity(thread, "setprio"); // experiment 0429: the trace line; the mask is unchanged\n\t}\n#endif\n',
                   'pthread setprio')
    return text


def semaphore(text):
    text = one(text, '#include "bc5/load_stat.hpp" // experiment 0415 (ls415)\n',
               '#include "bc5/load_stat.hpp" // experiment 0415 (ls415)\n\n#ifdef __linux__\n'
               'extern "C" void bc5_0429_r_on_sleep(const void* sem); // kernel/pthread.cpp, experiment 0429 R\n#endif\n',
               'semaphore declaration')
    text = one(text, '''	RemoveWaiter(&waiter);

	if (ptr_micros != nullptr) {
		*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);
	}
''', '''	RemoveWaiter(&waiter);
#ifdef __linux__
	bc5_0429_r_on_sleep(this); // experiment 0429 R: a guest thread that slept here and was woken is a sleeper
#endif

	if (ptr_micros != nullptr) {
		*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);
	}
''', 'semaphore resume hook')
    return text


def defaults(text, keep_slice):
    return one(text, C1_ROW, (C1_ROW if keep_slice else '') + R_ROW, 'kSoft row')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if len(args) != 1 or flags - {'--keep-slice', '--stressor', '--pins'}:
        sys.exit(__doc__)
    t = args[0].rstrip('/') + '/'
    if '--pins' in flags:  # writes the pins file from this tree (run once, on the laptop tree that reproduces 940e8f36)
        with open(PINS_FILE, 'w', newline='\n') as f:
            for u in PINS:
                f.write('%s %s\n' % (hashlib.md5(open(t + u, 'rb').read()).hexdigest(), u))
        print('mkswap0429r: pins written')
        return
    pins = dict(reversed(l.split()) for l in open(PINS_FILE) if l.strip())
    out = {}
    for u, fn in (('src/kernel/pthread.cpp', lambda x: pthread(x, '--keep-slice' in flags, '--stressor' in flags)),
                  ('src/kernel/semaphore.cpp', semaphore),
                  ('src/bc5/switch_defaults.hpp', lambda x: defaults(x, '--keep-slice' in flags))):
        raw, crlf, text = load(t + u)
        if hashlib.md5(raw).hexdigest() != pins[u]:
            stop('%s is not its pin' % u)
        new = fn(text)
        out[u] = (new.replace('\n', '\r\n') if crlf else new).encode('utf-8')
    for u, b in out.items():
        open(t + u, 'wb').write(b)
        print('mkswap0429r: %s md5 %s' % (u, hashlib.md5(b).hexdigest()[:8]))
    print('mkswap0429r: done (%s)' % (' '.join(sorted(flags)) or 'the swap form'))


if __name__ == '__main__':
    main()
