#!/usr/bin/env python3
# BC5 experiment 0291: apply patch_0291-lf.diff's change to a copy of the shared tree's videoOut.cpp while keeping its
# line endings: each new line takes the ending of the line it is inserted after, so a CRLF region stays CRLF and an LF
# one LF. (Editing the file on the Windows laptop rewrote every ending; the diff is therefore written as text here and
# applied on the box.) Every anchor must occur exactly once, else nothing is written.
# usage: apply0291.py <in videoOut.cpp> <out videoOut.cpp>   (on the box; then diff -u in out for the exact patch)
import sys

REGISTER_AFTER = '\t     attribute->option, category);'
REGISTER_NEW = [
    '\t// BC5 (experiment 0291): the registered display buffers\' size on stderr, once per registration (the LOGF above is',
    '\t// silent in play), for the A/B of KYTY_BC5_VIDEOOUT_REPORT.',
    '\tstd::fprintf(stderr,',
    '\t             "bc5 videoout: RegisterBuffers2 set %d, %d buffers from index %d: %ux%u, pitch %u, pixel format 0x%016" PRIx64',
    '\t             ", tiling %u, category %d\\n",',
    '\t             set_index, buffer_num, buffer_index_start, attribute->width, attribute->height, attribute->pitch_in_pixel,',
    '\t             attribute->pixel_format, attribute->tiling_mode, category);',
]
STATUS_BEFORE = 'KYTY_SYSV_ABI int VideoOutGetOutputStatus(int handle, VideoOutOutputStatus* status) {'
STATUS_HELPER = [
    '// BC5 (experiment 0291): KYTY_BC5_VIDEOOUT_REPORT sets the resolution field that VideoOutGetOutputStatus returns, for',
    '// an A/B of whether the second title chooses its display buffers or its render size from it. "2160p" or "4k" gives 2,',
    '// "1080p" gives 1, a number gives that value. Unset (the default) keeps the base\'s answer: 2 when the VideoOut size is',
    '// at least 3840 wide or 2160 high, else 1. That size is the --screen-width/--screen-height config (1280x720 unless',
    '// given), not the window\'s; --fullscreen alone leaves it, so the host answers 1 today.',
    '// TODO(verify) the field\'s encoding on the console (what 1 and 2 stand for).',
    'static int Bc5VideoOutReport() {',
    '\tstatic const int v = [] {',
    '\t\tconst char* e = std::getenv("KYTY_BC5_VIDEOOUT_REPORT");',
    '\t\tif (e == nullptr || *e == 0) {',
    '\t\t\treturn -1;',
    '\t\t}',
    '\t\tif (std::strcmp(e, "2160p") == 0 || std::strcmp(e, "4k") == 0 || std::strcmp(e, "4K") == 0) {',
    '\t\t\treturn 2;',
    '\t\t}',
    '\t\tif (std::strcmp(e, "1080p") == 0) {',
    '\t\t\treturn 1;',
    '\t\t}',
    '\t\treturn static_cast<int>(std::strtol(e, nullptr, 10));',
    '\t}();',
    '\treturn v;',
    '}',
    '',
]
RES_OLD = '\tstatus->resolution   = (ctx->width >= 3840 || ctx->height >= 2160 ? 2u : 1u);'
RES_NEW = [
    '\tconst uint32_t base_resolution = (ctx->width >= 3840 || ctx->height >= 2160 ? 2u : 1u);',
    '\tconst uint32_t size_w = ctx->width, size_h = ctx->height;',
    '\tstatus->resolution   = Bc5VideoOutReport() >= 0 ? static_cast<uint32_t>(Bc5VideoOutReport()) : base_resolution;',
]
STATUS_UNLOCK = '\tctx->mutex.Unlock();'
STATUS_LOG = [
    '',
    '\t// BC5 (experiment 0291): the first call, and the first call with another answer, as one stderr line each, so a run',
    '\t// shows whether and how often the title asks.',
    '\tstatic std::atomic<uint64_t> calls {0};',
    '\tstatic std::atomic<int64_t>  last_told {-1};',
    '\tconst uint64_t               n = ++calls;',
    '\tif (last_told.exchange(status->resolution) != static_cast<int64_t>(status->resolution)) {',
    '\t\tstd::fprintf(stderr,',
    '\t\t             "bc5 videoout: GetOutputStatus call %" PRIu64 " (handle %d) -> resolution %u (base %u, KYTY_BC5_VIDEOOUT_REPORT %s), "',
    '\t\t             "dynamic range %u, refresh rate %" PRIu64 ", VideoOut size %ux%u\\n",',
    '\t\t             n, handle, status->resolution, base_resolution, Bc5VideoOutReport() >= 0 ? "set" : "unset",',
    '\t\t             status->dynamicRange, status->refreshRate, size_w, size_h);',
    '\t}',
]
SUPPORTED_HEAD = 'KYTY_SYSV_ABI int VideoOutIsOutputSupported(int handle, uint64_t mode,'
SUPPORTED_NEW = [
    '\t// BC5 (experiment 0291): the output modes the title asks about, its first 16 calls, on stderr (this host supports',
    '\t// only VIDEO_OUT_OUTPUT_MODE_DEFAULT and _119_88HZ, see ValidateOutputConfig).',
    '\tstatic std::atomic<int> bc5_supported_calls {0};',
    '\tif (bc5_supported_calls.fetch_add(1) < 16) {',
    '\t\tstd::fprintf(stderr, "bc5 videoout: IsOutputSupported (handle %d) mode 0x%016" PRIx64 "\\n", handle, mode);',
    '\t}',
]
CONFIGURE_HEAD = 'KYTY_SYSV_ABI int VideoOutConfigureOutput(int handle, uint64_t mode,'
CONFIGURE_NEW = [
    '\t// BC5 (experiment 0291): every output mode the title configures, on stderr.',
    '\tstd::fprintf(stderr, "bc5 videoout: ConfigureOutput (handle %d) mode 0x%016" PRIx64 "\\n", handle, mode);',
]


def body(line):
    return line.rstrip('\r\n')


def ending(line):
    return line[len(body(line)):] or '\n'


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, 'r', newline='').read()
    lines = [l for l in text.split('\n')]
    lines = [l + '\n' for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])  # split at LF only, endings kept
    out = []

    def find_one(text, start=0):
        hits = [k for k in range(start, len(lines)) if body(lines[k]) == text]
        if len(hits) != 1:
            sys.exit('anchor %r found %d times' % (text, len(hits)))
        return hits[0]

    reg = find_one(REGISTER_AFTER)
    st = find_one(STATUS_BEFORE)
    res = find_one(RES_OLD, st)
    unl = [k for k in range(res, len(lines)) if body(lines[k]) == STATUS_UNLOCK][0]
    sup = find_one(SUPPORTED_HEAD)
    sup_pn = [k for k in range(sup, sup + 6) if body(lines[k]) == '\tPRINT_NAME();'][0]
    cfg = find_one(CONFIGURE_HEAD)
    cfg_pn = [k for k in range(cfg, cfg + 6) if body(lines[k]) == '\tPRINT_NAME();'][0]
    if not (reg < st < res < unl < st + 40 < sup < cfg):
        sys.exit('anchors out of order: %d %d %d %d %d %d' % (reg, st, res, unl, sup, cfg))
    for k, line in enumerate(lines):
        eol = ending(line)
        if k == st:
            out += [t + eol for t in STATUS_HELPER]
        if k == res:
            out += [t + eol for t in RES_NEW]
            continue
        out.append(line)
        if k == reg:
            out += [t + eol for t in REGISTER_NEW]
        if k == unl:
            out += [t + eol for t in STATUS_LOG]
        if k == sup_pn:
            out += [t + eol for t in SUPPORTED_NEW]
        if k == cfg_pn:
            out += [t + eol for t in CONFIGURE_NEW]
    open(dst, 'w', newline='').write(''.join(out))
    crlf = sum(1 for l in out if l.endswith('\r\n'))
    print('%s: %d lines (%d CRLF) -> %s: %d lines (%d CRLF)' % (src, len(lines), sum(1 for l in lines if l.endswith('\r\n')),
                                                               dst, len(out), crlf))


main()
