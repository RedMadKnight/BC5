#!/usr/bin/env python3
# BC5 exp 0439 (tag im439): objective picture measures from the private screenshots (top's order of 11-22 ~19:30: the
# maintainer's eyes cannot rank the runs). No image library: PNG decoded with zlib and numpy (8-bit RGB/RGBA, any filter).
# PNG -> BMP first: PowerShell System.Drawing (see the README). The game window is the shot's region inside the emulator window (fixed: x 320..1600, y 172..891 on the 1920x1080
# desktop shots of the box, read from the shots of 11-22). Measures per shot:
#   luma     mean luma of the window (0..255)
#   noise    share of window pixels that are near-saturated (luma > 235) AND more than 60 above the mean of their 4
#            neighbours: isolated bright speckle, the white noise patches on 3D surfaces
#   dark     share of window pixels with luma < 8 (a black picture)
# With two shots of the same run (k, k+1) also mean |delta luma| between them.
#   python imgm439.py <dir with run folders> <t seconds,...>   prints one line per run and time
import os
import struct
import sys
import zlib

import numpy as np

X0, X1, Y0, Y1 = 320, 1600, 262, 800  # the picture inside the cinematic bars (11-22 shots); MangoHud's box masked below
MX1, MY1 = 610, 340  # MangoHud's overlay box in desktop coordinates (top-left of the window)


def png(path):
    """24-bit BMP beside the PNG (converted with .NET System.Drawing on the laptop: no image library here), else fail."""
    bmp = path[:-4] + '.bmp'
    b = open(bmp, 'rb').read()
    off = struct.unpack('<I', b[10:14])[0]
    w, h = struct.unpack('<ii', b[18:26])
    bpp = struct.unpack('<H', b[28:30])[0]
    assert bpp == 24, bpp
    stride = (w * 3 + 3) & ~3
    a = np.frombuffer(b, np.uint8, stride * abs(h), off).reshape(abs(h), stride)[:, :w * 3].reshape(abs(h), w, 3)
    if h > 0:
        a = a[::-1]
    return a[:, :, ::-1].astype(np.float32)  # BGR -> RGB


def luma(img):
    win = img[Y0:Y1, X0:X1].copy()
    y = 0.299 * win[:, :, 0] + 0.587 * win[:, :, 1] + 0.114 * win[:, :, 2]
    y[: MY1 - Y0, : MX1 - X0] = np.nan  # MangoHud's box
    return y


def measures(path):
    y = luma(png(path))
    nb = (np.roll(y, 1, 0) + np.roll(y, -1, 0) + np.roll(y, 1, 1) + np.roll(y, -1, 1)) / 4.0
    ok = ~np.isnan(y) & ~np.isnan(nb)
    noise = float(np.mean(((y > 235) & (y - nb > 60))[ok]))
    yf = np.where(np.isnan(y), np.nanmean(y), y)
    return float(np.nanmean(y)), noise, float(np.mean(y[~np.isnan(y)] < 8)), yf


def bands(y):
    """Horizontal bands: rows that differ sharply from the row 3 above over most of the width; consecutive such rows
    grouped. Returns [(y_window, height, mean step)]."""
    d = np.abs(y[3:] - y[:-3])
    frac = np.mean(d > 40, axis=1)
    rows = np.where(frac > 0.6)[0] + 3
    out, start, prev = [], None, None
    for r in rows:
        if start is None:
            start = prev = r
        elif r <= prev + 3:
            prev = r
        else:
            out.append((int(start), int(prev - start + 1)))
            start = prev = r
    if start is not None:
        out.append((int(start), int(prev - start + 1)))
    return out


def grid_pitch(y):
    """Axis-aligned edge periodicity: the column profile of strong vertical edges (|step| > 30), its autocorrelation
    peak over lags 4..90 window pixels. The window shows the 3840x2160 surface scaled by 1/3, so the surface pitch is
    about lag x 3 (TODO(verify) the scaling of the shot against the surface). Also the row profile for horizontal edges."""
    res = []
    for axis in (1, 0):
        e = np.abs(np.diff(y, axis=axis)) > 30
        prof = e.sum(axis=1 - axis).astype(np.float64)
        prof -= prof.mean()
        if prof.std() == 0:
            res.append((0, 0.0))
            continue
        ac = np.correlate(prof, prof, 'full')[len(prof) - 1:]
        ac /= ac[0]
        # a true period is a LOCAL maximum of the autocorrelation (a smooth decay from lag 0 is no period)
        peaks = [k for k in range(4, min(91, len(ac) - 1)) if ac[k] > ac[k - 1] and ac[k] >= ac[k + 1] and ac[k] > 0.15]
        if not peaks:
            res.append((0, 0.0))
            continue
        k = max(peaks, key=lambda q: ac[q])
        res.append((int(k), float(ac[k])))
    return res  # [(lag_x, strength_x), (lag_y, strength_y)]


def main():
    base = sys.argv[1]
    if sys.argv[2] == 'all':  # every t*.bmp of each run: flash frames (picture luma > 150) and black frames (dark > 95 %)
        for run in sorted(os.listdir(base)):
            d = os.path.join(base, run)
            if not os.path.isdir(d):
                continue
            ts = sorted(int(f[1:4]) for f in os.listdir(d) if f.startswith('t') and f.endswith('s.bmp'))
            fl, bk, nz, n = [], [], [], 0
            for t in ts:
                m, nn, dk, _ = measures(os.path.join(d, 't%03ds.png' % t))
                n += 1
                if m > 150: fl.append(t)
                if dk > 0.95: bk.append(t)
                elif t >= 60: nz.append(nn)
            print('%s: %d shots; flash frames %s; first black %s; noise in non-black scene shots mean %.4f%% max %.4f%%' % (
                run, n, fl, bk[0] if bk else '-', 100 * (sum(nz) / len(nz) if nz else 0), 100 * (max(nz) if nz else 0)))
        return
    times = [int(t) for t in sys.argv[2].split(',')]
    for run in sorted(os.listdir(base)):
        d = os.path.join(base, run)
        if not os.path.isdir(d):
            continue
        for t in times:
            p = os.path.join(d, 't%03ds.png' % t)
            if not os.path.exists(p):
                print('%s t%03d: missing' % (run, t))
                continue
            try:
                m, n, dk, y = measures(p)
                bs = bands(y)
                (gx, sx), (gy, sy) = grid_pitch(y)
                print('%s t%03d: luma %.1f noise %.4f%% dark %.1f%% bands %d %s grid x %d (%.2f) y %d (%.2f) window px' % (
                    run, t, m, 100 * n, 100 * dk, len(bs), ' '.join('y%d+%d' % b for b in bs[:6]), gx, sx, gy, sy))
            except Exception as e:  # a shot that does not decode is reported, not fatal
                print('%s t%03d: %s' % (run, t, e))


if __name__ == '__main__':
    main()
