#!/usr/bin/env python3
"""
Stride-aware libcamera raw frame converter.

Fixes the core bug in cam_convert_robust.py: that script assumed the raw
file is tightly packed (width * height * bpp == filesize). It isn't.
`cam --file` dumps the plane exactly as produced by
DebayerCpu::strideAndFrameSize(), which pads each line's stride up to a
multiple of 8 bytes:

    stride = (width * bpp/8 + 7) & ~7
    filesize = stride * height

For 1924x1092 RGB888 (3 bytes/px): stride = 5776 (not 5772), so the file is
6,307,392 bytes. That number also happens to factor as 1444x1092x4 or
1444x1456x3 -- which is why the old script's factorization found a bogus
"1444" width and produced a sheared, "distorted" image.

This script computes the expected stride the same way libcamera does,
matches candidate (width, height, bpp) against the real stride*height,
and strips the row padding before reshaping.
"""

import numpy as np
from PIL import Image
import os, sys, glob

CANDIDATE_DIMS = [
    (1924, 1092),   # softisp debayer output (expected)
    (1932, 1092),   # OV2740 native active mode
    (1920, 1080),   # standard 1080p
    (1280, 720),
    (640, 480),
]

# (mode_name, bytes_per_pixel, description)
BPP_MODES = [
    ("rgb24", 3, "RGB888"),
    ("rgba",  4, "XRGB8888 / ARGB8888"),
]


def libcamera_stride(width, bpp):
    """Reproduce DebayerCpu::strideAndFrameSize()'s rounding exactly."""
    raw_bytes_per_line = width * bpp  # bpp here is bytes/pixel already
    return (raw_bytes_per_line + 7) & ~7


def find_matching_dims(file_size):
    """Find (w, h, bpp, stride, mode_name, desc) matching file_size via
    stride*height, not width*height*bpp."""
    matches = []
    for w, h in CANDIDATE_DIMS:
        for mode_name, bpp, desc in BPP_MODES:
            stride = libcamera_stride(w, bpp)
            if stride * h == file_size:
                matches.append((w, h, bpp, stride, mode_name, desc))
    return matches


def save_png(path, arr):
    img = Image.fromarray(arr)
    img.save(path)
    mean = arr.mean(axis=(0, 1))
    if arr.shape[2] == 4:
        print(f"  {path}: mean RGBA = {mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}, {mean[3]:.1f}")
    else:
        print(f"  {path}: mean RGB = {mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}")


def main():
    f = "test.raw"
    if not os.path.exists(f):
        candidates = sorted(glob.glob("test.*"))
        if not candidates:
            print("No test.* files found.")
            sys.exit(1)
        f = candidates[-1]

    size = os.path.getsize(f)
    print(f"File: {f}, size: {size} bytes")
    print()

    raw = np.fromfile(f, dtype=np.uint8)
    matches = find_matching_dims(size)

    if not matches:
        print("WARNING: No exact stride*height match found for known dims.")
        print("Brute-forcing stride/height combinations...")
        for bpp in (3, 4):
            for h in range(1000, 1200):
                if size % h == 0:
                    stride = size // h
                    # recover width such that libcamera_stride(width, bpp) == stride
                    # stride is a multiple of 8; raw bytes/line is stride or stride-1..-7
                    for pad in range(8):
                        raw_bpl = stride - pad
                        if raw_bpl % bpp == 0:
                            w = raw_bpl // bpp
                            if 1200 <= w <= 2000 and libcamera_stride(w, bpp) == stride:
                                matches.append((w, h, bpp, stride, "auto", f"auto-detected {bpp} Bpp"))
        if not matches:
            print("No plausible dimensions found.")
            sys.exit(1)

    print(f"Found {len(matches)} exact match(es) accounting for stride padding:")
    for w, h, bpp, stride, mode_name, desc in matches:
        pad = stride - w * bpp
        print(f"  {w}x{h} @ {desc} ({bpp} Bpp), stride={stride}B, padding={pad}B/line")
    print()

    for w, h, bpp, stride, mode_name, desc in matches:
        print(f"--- Processing as {w}x{h} @ {desc} (stride {stride}) ---")
        # Reshape as (height, stride) first, THEN strip padding, THEN reshape to pixels.
        lines = raw.reshape((h, stride))
        pixel_bytes = lines[:, : w * bpp]
        arr = pixel_bytes.reshape((h, w, bpp))

        if bpp == 3:
            save_png(f"test_{w}x{h}_rgb.png", arr)                 # native RGB (RGB888 per current debayer.cpp)
            save_png(f"test_{w}x{h}_bgr.png", arr[:, :, ::-1])     # swapped, for comparison only
        elif bpp == 4:
            save_png(f"test_{w}x{h}_bgra.png", arr)
            save_png(f"test_{w}x{h}_rgba.png", arr[:, :, [2, 1, 0, 3]])
            save_png(f"test_{w}x{h}_argb.png", arr[:, :, [3, 2, 1, 0]])

        print()

    print("Done. The un-sheared image should now be geometrically correct.")
    print("Confirmed output format after the patch is RGB888, so 'test_1924x1092_rgb.png' is the one to check.")


if __name__ == "__main__":
    main()
