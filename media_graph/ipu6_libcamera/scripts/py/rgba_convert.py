#!/usr/bin/env python3

# after `LIBCAMERA_LOG_LEVELS="*:DEBUG" cam -c1 --capture=10 --file=sequence.rgba´

import numpy as np
from PIL import Image

W, H, BPP = 1924, 1092, 4
FRAME_SIZE = W * H * BPP

raw = np.fromfile("sequence.rgba", dtype=np.uint8)
n_frames = len(raw) // FRAME_SIZE
print(f"Total frames: {n_frames}")

for i in [0, 4, 9]:
    if i >= n_frames: break
    frame = raw[i*FRAME_SIZE:(i+1)*FRAME_SIZE].reshape((H, W, 4))
    # BGRA → RGBA
    rgba = frame[:,:,[2,1,0,3]]
    img = Image.fromarray(rgba)
    img.save(f"frame_{i+1:02d}.png")
    mean = rgba[:,:,:3].mean(axis=(0,1))
    print(f"frame {i+1}: mean RGB = {mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}")
