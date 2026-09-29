# IPU6 Camera Project — Phase 2 Transcript: PSYS Hardware-ISP Evaluation

Supersedes nothing — this is a new phase document, opened alongside the existing
`transcript.md` (Phase 1: SoftISP/GStreamer/DMA-BUF work). Phase 1's pipeline is
now the **fallback stack**, not abandoned. See §0.

## 0. Status of Phase 1 (SoftISP/libcamera route) — FALLBACK, not closed

Decision, stated explicitly by user: current libcamera + SoftISP + GStreamer
DMA-BUF pipeline is demoted to fallback status while PSYS is evaluated in
parallel, not because it's broken, but because measured image quality in
real-world use (Firefox video conferencing) is unsatisfactory and it has no
HDR path
User's explicit risk tradeoff, recorded verbatim in substance: IPU6's known
suspend/resume breakage on the PSYS route is accepted as a lesser problem than
current low video quality and absence of HDR — this is the user's own
prioritization, not this assistant's recommendation (the recommendation given
was to stay on the fallback route; noted for the record, not overridden)
Everything closed in Phase 1 remains valid and reusable regardless of Phase 2's
outcome: DMA-BUF zero-copy caps advertisement (GStreamer `libcamerasrc`),
RAW10P GPU black-frame shader fix, CCM/green-cast color calibration, AGC
`maxGain` local patch
Open thread carried over, not yet actioned: a libcamera upstream patch series
(merged into `master` 2026-05-07, author Javier Tia — same person as this
project's original `ov2740.yaml` patchwork author) root-causes the SoftISP
green-cast bug differently than this project's local CCM-restoration fix (an
AWB statistics bit-depth normalization bug in `swstats_cpu.cpp`, not a CCM
defect) and also fixes an AGC bang-bang flicker controller. Not in this
project's pinned `v0.7.2` tag. Worth evaluating as a lower-risk quality
improvement to the fallback stack independent of the Phase 2 PSYS decision
Open thread carried over: OV2740 "staggered HDR" claim (OmniVision marketing
page) is UNVERIFIED — `ov2740.c` (this project's actual kernel driver source)
exposes zero HDR/staggered/WDR/dual-exposure controls; confirmed absent, not
merely undocumented
Rollback-in-progress artifacts still pending from Phase 1, on hold: `debayer_egl.cpp`/`.h` still not obtained; needed if/when Option 1 (retarget GPU
debayer to stay GPU-resident) is revisited instead of or alongside PSYS
Still queued, unrelated to either route, non-blocking: PipeWire audio (`wpctl`
shows no ALSA device reaching the graph — diagnostics never run), Epiphany/.mp4
VA-API playback (root cause unconfirmed)

## 1. Hardware baseline (confirmed this project, with evidence)

**CPU/iGPU:** Intel integrated GPU, Iris Xe, ADL GT2 (Alder Lake generation) —
confirmed via GPU debayer probe logs and `vah264enc`'s VA-API context
(`gst.va.display.handle`, `"Intel(R) Gen Graphics"`, `/dev/dri/renderD128`)
**Camera sensor:** OmniVision OV2740, I2C address `10-0036`
**Sensor native format:** 10-bit Bayer, `SGRBG10_1X10` — confirmed twice
independently: (a) runtime negotiation log, (b) `ov2740.c` driver source,
`ov2740_enum_mbus_code()`/`ov2740_enum_frame_size()` hard-reject any other
mbus code, index>0 returns `-EINVAL`. Sensor has no other native mode
**Sensor bit-depth ceiling:** confirmed 10-bit is the ADC's actual limit, not a
driver restriction — cross-checked against OmniVision's own product page and
Intel's public RealSense D400-series datasheet, both state `10-bit RAW`, no
alternate bit-depth mode documented anywhere
**IPU generation:** Intel IPU6 — **exact PCI ID NOT YET CONFIRMED for this
specific machine.** Blocking task for Phase 2, see §4
**Media topology (confirmed, from capture logs):** `/dev/media0` ("intel-ipu6")
→ `ov2740 10-0036`[0] → `Intel IPU6 CSI2 1`[0] → `Intel IPU6 ISYS Capture 8`[0]
→ exposed as `/dev/video8`
**IVSC (privacy-shutter sensor-power controller) presence:** UNCONFIRMED for
this hardware — no IVSC-related errors ever appeared in any capture log this
project, which may mean this platform's signal path doesn't include one
(unlike the ThinkPad-class hardware most public IPU6 guides target), but this
has not been directly checked. Task for Phase 2, see §4
**GPU DMA-heap backend (confirmed, repeated log evidence):** `/dev/dma_heap/system` — `linux,cma` and `reserved` heaps both fail to open
("No such file or directory") on this system; system heap is the operative
one. `default_cma_region` exists but is mode 0600 root-only (non-blocking
housekeeping item, unrelated to either route)

## 2. Software baseline (confirmed this project, with evidence)

**Distro:** Gentoo Linux
**Init system:** OpenRC, no systemd — `dmesg`/`rc-status` used in place of
`journalctl`, `elogind` presumed (not directly confirmed) to manage
`/dev/snd/*` ACLs
**Kernel version:** **NOT YET CONFIRMED** — no `uname -r` has been run or
pasted this project. Needed before selecting IPU6 kernel-module tags/branches
for Phase 2 (upstream guidance shows IPU6 driver API compatibility is
kernel-version-sensitive — one documented case of DKMS modules failing to
build at all on kernel 6.19 against Intel's out-of-tree repo)
**libcamera:** v0.7.2, commit `bdbf1453fb63cc7f40157ae86fcb0f9b7c57d773`,
built via live ebuild `media-libs/libcamera-9999`
(`EGIT_REPO_URI="https://gitlab.freedesktop.org/camera/libcamera.git/"`,
`EGIT_COMMIT="v0.7.2"`)
**libcamera build configuration (verified against actual ebuild `src_configure()`):**
```
-Dbuildtype=plain -Ddocumentation=disabled -Dpycamera=disabled
-Dpipelines=simple -Dipas=simple -Dlc-compliance=disabled -Dqcam=disabled
-Dsoftisp-gpu=enabled
$(meson_feature gstreamer)   $(meson_feature trace tracing)
$(meson_feature unwind libunwind)   $(meson_feature elfutils libdw)
$(meson_feature udev)   $(meson_feature v4l v4l2)   $(meson_use test)
```
**libcamera USE flags, current (user recompiled without `test`/`tools` since
last check):** `drm` + , `elfutils` − , `gstreamer` + , `gui` − , `jpeg` + ,
`openssl` − , `sdl` − , `test` − , `tiff` + , `tools` − (confirmed inert —
declared in `IUSE`, wired to nothing in this ebuild), `trace` − , `udev` + ,
`unwind` − , `v4l` +
**GStreamer:** 1.26.11 (`gstreamer-1.0` and `gstreamer-allocators-1.0`, both
confirmed via `pkg-config --modversion`)
**PipeWire:** 1.6.8, confirmed alive with real clients connected
(`xdg-desktop-portal`, `xdg-desktop-portal-wlr` ×4, `firefox`, `wpctl`) —
audio-device graph gap still open and unrelated to either camera route
**GStreamer VA plugin:** `libgstva.so` (current/correct plugin — `vah264enc`,
`vah264lpenc` present and functional); confirmed NOT the deprecated
`libgstvaapi.so`, which is expected to be absent, not a bug
**Debayer backend in use:** `DebayerEGL` (GPU/EGL path), Iris Xe, zero
`eglCreateImageKHR` failures — default-selected because `-Dsoftisp-gpu=enabled`
and no `LIBCAMERA_SOFTISP_MODE` override was set in the runs that showed this
**Debayer output format (confirmed, log-literal):** `ABGR8888`, 8 bits/channel,
32 bpp — the actual bit-depth ceiling this project is trying to move past

## 3. Environment variables — confirmed useful so far, Phase 1 + carried forward

| Variable | Purpose | Status |
|---|---|---|
| `LIBCAMERA_SOFTISP_MODE=gpu\|cpu` | Force debayer backend for A/B testing | Active, Phase 1 |
| `LIBCAMERA_LOG_LEVELS="*:DEBUG"` | Required — probes/diagnostics log at DEBUG only | Active, Phase 1 |
| `DRI_PRIME=pci-0000_00_02_0` | Selects iGPU explicitly (`DRI_PRIME=0` is INVALID on this system, Mesa ignores it) | Active, Phase 1 |
| `LIBCAMERA_DMA_HEAP` | RETIRED — v0.7.2's allocator ignores it (log-verified, built-in candidate list used instead) | Historical only |
| `GST_DEBUG=GST_CAPS:6` / `GST_MEMORY:6` / `GST_ALLOCATOR:6` / `libcamerasrc:6` | Caps/memory/allocator tracing, used throughout DMA-BUF verification | Active, Phase 1 |

**Anticipated for Phase 2, NOT yet verified against this system — noted from
public documentation only, confirm before relying on them:**

| Variable | Purpose | Source |
|---|---|---|
| `firefox`: `media.webrtc.camera.allow-pipewire` → `true` in `about:config` | Only relevant if Phase 2 route is made to integrate with PipeWire instead of the `v4l2loopback` shim | Community migration writeup — **NOTE:** the PSYS/`icamerasrc` route as documented does NOT go through PipeWire at all; it exposes a plain `/dev/videoN` via `v4l2loopback`, which Firefox already treats as an ordinary V4L2 webcam with no special flag needed. This flag only applies if PipeWire integration is deliberately added on top |
| `CONFIG_VIDEO_INTEL_IPU6=m`, `CONFIG_INTEL_VSC=m`, `CONFIG_INTEL_SKL_INT3472=m` | Kernel config options the PSYS/IVSC modules need to build against | Needs verification against this system's actual kernel `.config` — not yet checked |

## 4. Phase 2 — blocking tasks, not yet started

1. **BLOCKING:** `lspci -nn | grep -i "Image Processing\|IPU6\|8086:46"` —
   determines exact PCI ID, which selects the correct HAL/firmware variant
   (`ipu6` / `ipu6ep` / `ipu6epmtl`) and matching `ipu6-camera-bins` tag.
   Guessing wrong wastes a full build cycle on a mismatched proprietary blob
2. `uname -r` — kernel version, needed before selecting `ipu6-drivers` branch/
   tag; upstream compatibility is kernel-version-sensitive (documented DKMS
   build failure on kernel 6.19 against one repo state)
3. `lsmod | grep -E "ivsc|mei_vsc"` — determine whether this hardware's signal
   path includes an IVSC privacy-controller stage at all (unconfirmed, §1)
4. License/packaging decision for `intel/ipu6-camera-bins` (binary-only
   firmware/ISP-algorithm blobs, no source) — affects how a local Gentoo
   ebuild would need to declare `ACCEPT_LICENSE`
5. Components required, once 1–3 are answered: `intel/ipu6-drivers` (DKMS
   kernel module), `intel/ipu6-camera-bins` (proprietary firmware),
   `intel/ipu6-camera-hal` (userspace HAL), `intel/icamerasrc` branch
   `icamerasrc_slim_api` (GStreamer source element — replaces `libcamerasrc`
   entirely for this route, does not reuse any of Phase 1's GStreamer work),
   `v4l2loopback` + `v4l2-relayd` (expose result as `/dev/videoN`)
6. Post-build: A/B image-quality comparison against the Phase 1 fallback,
   same PPM-capture/luminance-measurement methodology already established
   (transcript.md §4)

## 5. Known risks accepted for this phase (user-directed, recorded per §0)

- IPU6 firmware re-authentication failure after S3 suspend on kernel 6.16+,
  unfixed upstream (`intel/ipu6-drivers#381`) — accepted as lower priority
  than image quality/HDR
- DKMS rebuild required on every kernel update; out-of-tree repo has a
  documented history of lagging kernel API changes
- No official Gentoo-tree package for any of the 5 out-of-tree components;
  third-party overlay only, unofficial, same category of risk as the current
  `libcamera-9999` live ebuild but across a much larger dependency surface
- HDR capability on this route is not yet confirmed to exist at all — pursuing
  PSYS does not guarantee an HDR fix, only dedicated-hardware debayer/ISP
  processing; still open pending investigation
