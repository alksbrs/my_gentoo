# Debugging session transcript

## Table of Contents

1. [System](#system)
2. [Environment vars](#environment-vars)
3. [Resolved and confirmed](#resolved-and-confirmed)
4. [Commands used](#commands-used)
5. [Current blocker](#current-blocker)
6. [Root cause](#root-cause)
7. [Next steps](#next-steps)
8. [Directories and files](#directories-and-files)

## 1. System

  - OS:        Gentoo Linux
  - Hardware:  IPU6 (Alder Lake) + OV2740 sensor
  - Sensor:    1932x1092 active mode (V4L2-confirmed native, subdev4 ov2740 15-0036)
  - SoftISP:   1924x1092 debayer output (alignment-related crop)
  - Package:   local overlay at `/var/db/repos/local/media-libs/libcamera-9999` v0.7.2 pinned git ebuild with `-Dipas=simple`, IPA Module `ipa_soft_simple.so` (Simple pipeline), backend `LIBCAMERA_SOFTISP_MODE=gpu`
  - Build root (${S}): `/var/tmp/portage/media-libs/libcamera-9999/work/libcamera-9999`
  - Capture Tool: `cam` (libcamera CLI), output format	PPM (RGB3, ~6.1MB per frame)
  - Configuration: official upstream baseline tuning file `/usr/share/libcamera/ipa/softisp/ov2740.yaml`

## 2. Environment vars

`export LIBCAMERA_SOFTISP_MODE=gpu`
`export LIBCAMERA_LOG_LEVELS="*:DEBUG"`

## 3. Resolved and confirmed

  - configured `libcamera-9999.ebuild` with `EGIT_COMMIT="v0.7.2"`
  - ov2740.yaml updated with upstream official v0.7.2 calibrated version

## Patch

Adds two new, genuinely functional YAML keys to the `Agc:` block — `maxGain` and
`minGain` — that clamp the analogue-gain range the proportional AGC controller is
allowed to use. Today, those bounds come only from the sensor driver's reported
`V4L2_CID_ANALOGUE_GAIN` range (via `CameraSensorHelper`), with no tuning-file
override anywhere in the call path. This patch adds that override.

- `agc.h.patch` — adds `#include <optional>`, forward-declares `ValueNode`, adds
  `init()`/`configure()` overrides, adds `maxGainOverride_`/`minGainOverride_`
  members (`std::optional<double>`).
- `agc.cpp.patch` — adds `#include "libcamera/internal/yaml_parser.h"`, implements
  `Agc::init()` (reads `maxGain`/`minGain` from the algorithm's own YAML sub-block)
  and `Agc::configure()` (clamps `context.configuration.agc.againMax`/`againMin`
  if the tuning file requested a tighter bound than the driver default).
- Wired into the ebuild via a `PATCHES=()` array pointing at `${FILESDIR}/agc.h.patch` and `${FILESDIR}/agc.cpp.patch`.

## 4. Commands used

### `cam` utility for test captures

`cam -c 1 -C6 -F'/tmp/frame#.ppm' -s role=viewfinder,width=1932,height=1092`

### PY script to convert *.ppm to *.png starting with frame 2

```
python3 << 'PYSCRIPT'
from PIL import Image
import glob
files = sorted(glob.glob('/tmp/framecam*.ppm'))
for f in files[2:]:
    img = Image.open(f)
    out = f.replace('.ppm', '.png')
    img.save(out)
    print(f'{f.split("/")[-1]} → {out.split("/")[-1]}')
PYSCRIPT
```

## 5. Current blocker

## 6. Root cause

 `agc.cpp` / `agc.h` (original) `Agc` has no `init()` override at all — it reads zero YAML. All exposure/gain bounds it uses (`exposureMax`, `againMax`, `againMin`, `again10`, `againMinStep`) come from `IPAContext.configuration.agc`, populated elsewhere. Confirmed the "Failed Approaches" style keys speculated earlier (`minGain`/`maxGain`/`targetBrightness` under `Agc:`) had no code path to consume them.

## 7. Next steps

  - proceed with configuring SoftISP to run on Intel Arc

## 8. Directories and files

- Local overlay directory structure

/var/db/repos/local/media-libs/libcamera/
├── files
│   └── libcamera-9999-debayer-disable-bgr.patch
├── libcamera-9999.ebuild
└── Manifest

