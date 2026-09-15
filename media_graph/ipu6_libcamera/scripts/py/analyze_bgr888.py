import numpy as np
from PIL import Image
import sys

FRAME_SIZE = 6307392  # bytes per BGR888 frame (1092 rows × 5776 stride)
raw = np.fromfile(sys.argv[1], dtype=np.uint8)
n_frames = len(raw) // FRAME_SIZE
print(f'Total frames in file: {n_frames}')

# Extract last frame (AWB-converged)
last = raw[(n_frames - 1) * FRAME_SIZE : n_frames * FRAME_SIZE]
stride = FRAME_SIZE // 1092
img = last.reshape((1092, stride))[:, :1924*3].reshape((1092, 1924, 3))

print('Channel stats (last frame):')
for i, n in enumerate(['R','G','B']):
    ch = img[:,:,i]
    print(f'  {n}: min={ch.min():3d} max={ch.max():3d} mean={ch.mean():6.1f} unique={len(np.unique(ch))}')

# Save as-is (empirically RGB byte order)
Image.fromarray(img).save(sys.argv[2])
print(f'Saved {sys.argv[2]}')
