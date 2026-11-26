/* BC5 experiment 0241: decode one raw Wwise ATRAC9 stream (the data chunk find0241.py copied out) with vgmstream's
 * ATRAC9 decoder (src/coding/libs/atrac9_dec.c @ 7c520e8, ISC; it knows channel configurations 6 "1.0 vibration" and
 * 7 "2.0 vibration (dual mono)", atrac9_dec.c:78-88) and print what came out. Optionally write a 16-bit WAV.
 *   dec0241 <config hex, 8 digits> <raw.at9> [out.wav]
 * Prints: the decoder's info, superframes, frames ok / failed, samples per channel, and per channel the peak, RMS and
 * share of zero samples. Build (ubuntu distrobox):
 *   gcc -O2 -Wall -I vgmstream/src/coding/libs dec0241.c vgmstream/src/coding/libs/atrac9_dec.c \
 *       vgmstream/src/coding/libs/atrac9_internal.c -lm -o dec0241
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "atrac9_dec.h"

static void put32(FILE* f, uint32_t v) { fwrite(&v, 4, 1, f); }
static void put16(FILE* f, uint16_t v) { fwrite(&v, 2, 1, f); }

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: dec0241 <cfg hex> <raw.at9> [out.wav]\n"); return 2; }
    uint32_t c = (uint32_t)strtoul(argv[1], NULL, 16);
    uint8_t cfg[4] = {(uint8_t)(c >> 24), (uint8_t)(c >> 16), (uint8_t)(c >> 8), (uint8_t)c};
    FILE* in = fopen(argv[2], "rb");
    if (!in) { perror(argv[2]); return 1; }
    fseek(in, 0, SEEK_END); long n = ftell(in); fseek(in, 0, SEEK_SET);
    uint8_t* buf = malloc(n > 0 ? n : 1);
    if (fread(buf, 1, n, in) != (size_t)n) { fprintf(stderr, "short read\n"); return 1; }
    fclose(in);

    atrac9_info_t info;
    if (atrac9_get_config_info(cfg, &info) != 0) { printf("config %08x: not accepted\n", c); return 1; }
    atrac9_handle_t* h = atrac9_init(cfg);
    if (!h) { printf("config %08x: init failed\n", c); return 1; }
    printf("config %08x: channels %d rate %d superframe %d bytes, %d frames x %d samples, dmc %d\n", c, info.channels,
           info.sample_rate, info.superframe_size, info.frames_per_superframe, info.frame_samples, info.dmc_mode);

    FILE* out = argc > 3 ? fopen(argv[3], "wb") : NULL;
    if (out) { fwrite("RIFF\0\0\0\0WAVEfmt ", 1, 16, out); put32(out, 16); put16(out, 1); put16(out, info.channels);
               put32(out, info.sample_rate); put32(out, info.sample_rate * info.channels * 2);
               put16(out, info.channels * 2); put16(out, 16); fwrite("data\0\0\0\0", 1, 8, out); }

    const int ch = info.channels;
    int16_t pcm[ATRAC9_MAX_FRAME_SAMPLES * 16];
    double sum2[16] = {0}; int peak[16] = {0}; long zeros[16] = {0};
    long frames_ok = 0, frames_bad = 0, samples = 0, superframes = 0, first_bad = -1;
    for (long pos = 0; pos + info.superframe_size <= n; pos += info.superframe_size, superframes++) {
        long off = pos;
        for (int f = 0; f < info.frames_per_superframe; f++) {
            int used = 0;
            int r = atrac9_decode_pcm16(h, buf + off, (int)(pos + info.superframe_size - off), pcm, &used);
            if (r <= 0 || used <= 0) {
                frames_bad++; if (first_bad < 0) first_bad = superframes;
                atrac9_reset(h); break;   /* skip the rest of this superframe */
            }
            frames_ok++; samples += r; off += used;
            for (int i = 0; i < r; i++)
                for (int k = 0; k < ch; k++) {
                    int v = pcm[i * ch + k]; sum2[k] += (double)v * v;
                    if (abs(v) > peak[k]) peak[k] = abs(v);
                    if (v == 0) zeros[k]++;
                }
            if (out) fwrite(pcm, 2, (size_t)r * ch, out);
        }
    }
    if (out) { long data = samples * ch * 2; fseek(out, 4, SEEK_SET); put32(out, (uint32_t)(36 + data));
               fseek(out, 40, SEEK_SET); put32(out, (uint32_t)data); fclose(out); }
    printf("bytes %ld superframes %ld frames ok %ld failed %ld (first failed superframe %ld) samples/ch %ld (%.2f s)\n",
           n, superframes, frames_ok, frames_bad, first_bad, samples, (double)samples / info.sample_rate);
    for (int k = 0; k < ch; k++)
        printf("  ch%d peak %d rms %.1f zero %.1f%%\n", k, peak[k], samples ? sqrt(sum2[k] / samples) : 0.0,
               samples ? 100.0 * zeros[k] / samples : 0.0);
    atrac9_free(h); free(buf);
    return frames_bad ? 3 : 0;
}
