# Debugging session transcript

## 1. System

  - OS: Gentoo Linux
  - Hardware: IPU6 (Alder Lake) + OV2740 sensor
  - iGPU (Alder Lake-P GT2 Iris Xe Graphics, ADL GT2, pci 0000:00:02.0, card0/renderD128)
  - dGPU (DG2 Arc A370M, pci-0000:03:00.0, card1/renderD129)
  - ´xe´ kernel module (6.18.48-gentoo official kernel), Mesa 26.1.8 userspace, Xe KMD flagged experimental by Mesa
  - Sensor: 1932x1092 active mode (V4L2-confirmed native, subdev4 ov2740 15-0036)
  - SoftISP: 1924/1928x1092 debayer output (alignment-related crop)
  - Package: local overlay at `/var/db/repos/local/media-libs/libcamera` (package dir; note: NOT media-libs/libcamera-9999/files), v0.7.2 pinned git ebuild, `-Dipas=simple`, `-Dsoftisp-gpu=enabled`, `-Dpipelines=simple,uvcvideo,vimc`
  - Patch mechanism: ebuild `PATCHES=()` array (applies agc.h.patch, agc.cpp.patch, ipu6-egl-import-debug.patch from files/)
  - Capture Tool: `cam` (libcamera CLI), output PPM (ABGR8888, ~6.3MB per frame at 1928x1092)
  - Tuning file: `/usr/share/libcamera/ipa/simple/ov2740.yaml` (note: path is `simple/`, not `softisp/` as earlier stated)

## 2. Environment vars

`export LIBCAMERA_SOFTISP_MODE=gpu`
`export LIBCAMERA_LOG_LEVELS="*:DEBUG"`
`export LIBCAMERA_DMA_HEAP=/dev/dma_heap/default_cma_region`
`export DRI_PRIME=pci-0000_00_02_0` (iGPU — VALID form; `DRI_PRIME=0` is INVALID, Mesa ignores it)

## 3. Resolved and confirmed (final)

  - Stride kernel patch (line_align 64 → 256 in ipu6-isys-video.c): stride 4096 confirmed
  - V4L2 BA10 is 10-bit values EXPANDED to 16-bit words (kernel.org V4L2 SGRBG10 spec) — NOT 4px/5B packed; earlier "packed 10-bit" root-cause statement was WRONG; packed pseudo-format at this device is pgAA-family only
  - Mesa rejects via createImageFromDmaBufs → EGL_BAD_MATCH (0x3009); attributed at libEGL debug layer
  - eglQueryDmaBufFormatsEXT per-device (65 formats, identical on both GPUs): NO Bayer fourccs; R8, R16, GR88, RG16, NV12, P010 present
  - DRI_PRIME=0 invalid; iGPU/dGPU targeting verified via distinct GL_RENDERER strings (probe helper eglformats.c v2)
  - KEY code finding: GPUISP egl.cpp NEVER sends Bayer fourcc to Mesa — the drm_format derives from eglImage.format_ (GL enum): GL_LUMINANCE→R8, GL_RG→RG88, GL_RGBA→ARGB8888. The failing input import was GR88 (drm_format 943212370), glformat 33319 = GL_RG, passing output import was ARGB8888 (875713089)
  - Input-only failure isolated (output dma-heap ARGB8888 imports always succeeded) — producer-specific
  - Explicit EGL_DMA_BUF_PLANE0_MODIFIER_LO/HI_EXT = 0,0 attribs EXONERATED (failure identical with them removed, implicit linear)
  - ROOT CAUSE (working): GR88 fourcc rejected per-format at Mesa import; relabeling the SAME dmabuf fd as DRM_FORMAT_R16 (memory-layout-true: 2 B/px, 10-in-16-bit LE words, stride 4096 = 2048 samples × 2) CLEARS EGL_BAD_MATCH
  - FINAL working build state (sed-applied to live tree, FEATURES=keepwork retained):
    * line 183: DRM_FORMAT_RG88 → DRM_FORMAT_R16
    * two modifier attribs deleted from image_attrs
    * (diagnostics instrumentation from 17:25 build — NOT in current build; tree lost them in a re-unpack; acceptable, probe complete)
  - VALIDATION RUN (3:43): 6 frames native 1932x1092, GL_RENDERER = Iris Xe (ADL GT2), 0 eglCreateImageKHR failures, steady 29.99–30.06 fps, AWB converged (R 1.954→1.941, B 1.920, T≈4.6k), output 1928x1092-ABGR8888 8666112 B/frame = stride×height exact
  - ALL THREE SUCCESS CRITERIA MET: zero-copy capture, full hw acceleration, native 30 fps at native resolution

## 4. Commands used

  - eglformats.c helper (v2): per-GPU eglQueryDmaBufFormatsEXT/modifiers + GL_RENDERER dump
  - v4l2-ctl: --get-fmt-video, --list-formats-ext on /dev/video8
  - cam captures with LIBCAMERA_LOG_LEVELS="*:DEBUG", EGL_LOG_LEVEL=debug, MESA_DEBUG=1
  - equery u mesa; ls /var/db/repos/gentoo/media-libs/mesa/
  - ebuild manifest / compile / install / merge workflows; FEATURES=keepwork retention
  - sed in-place edits + diff -u patch generation from live tree (transport-proof patch method)
  - ebuild phase-stamp manipulation (.prepared) for keepwork prepare-skip

## 5. Mesa/upstream consultation (completed)

  - No Bayer dmabuf import MR/issue in Mesa; policy: dmabuf import for external sampling only, per-driver fourcc lists; iris will never list Bayer
  - Mesa 26.1.8 → 26.2.1: no changelog evidence of new Intel import formats; USE flags gate driver builds not fourcc tables — upgrade REJECTED as remedy
  - Upstream libcamera: Hans de Goede RFC "egl: Implement DMABuf import for input buffers" (2026-Feb 057319; Jan 056430) — import-with-CPU-fallback; degrades to fallback on Intel
  - Similar-platform workarounds: raw16 unpack (Jetson) / vendor tricks (NXP GL_VIV_direct_texture, YUV misdeclaration) — NXP-style misdeclaration legitimate here ONLY when memory layout matches (it does: R16)
  - pgAA confirmed packed ("10-bit Bayer Packed") — dead end confirmed

## 6. Root cause (updated, final)

  - EGL_BAD_MATCH was NOT Bayer-fourcc gating (fourcc never transmitted) and NOT the explicit-zero modifier attribs
  - GR88 fourcc import of the ISYS buffer rejected per-format by Mesa; DRM_FORMAT_R16 (true layout match: single 16-bit sample/px) ACCEPTS the same fd → zero-copy import succeeds
  - Root cause statement: Mesa's GR88 dmabuf import path rejects the ISYS-produced buffer (specific per-format gate; exact Mesa match-check unresolved — closed as non-blocking); R16 relabel bypasses legitimately

## 7. Open items

  - SCALE CHECK UNDECIDED: R16 normalization may land ~64× low (shader RAW10P macro `pixel(p) = p.r/4 + p.g*64` written for byte-pair reconstruction). Tonight's captures under flashlight cannot discriminate dark-room vs scale error. VERIFY in daylight; if confirmed, one-line shader fix in glsl_shaders.h RAW10P block: `p.r * 64.0`
  - Consolidate final patch into overlay BEFORE next plain emerge (work tree unprotected without keepwork):
    1. DRM_FORMAT_RG88 → DRM_FORMAT_R16 (egl.cpp, was line 183)
    2. delete EGL_DMA_BUF_PLANE0_MODIFIER_LO/HI_EXT, 0 lines
    3. + shader scale fix IF daylight test demands it
    4. REPLACE malformed ipu6-egl-import-debug.patch currently in files/ (it fails prepare on fresh unpacks)
  - dma-heap naming/perms (linux,cma vs default_cma_region) — preserved, non-blocking (system heap works)
  - Dual-GPU split (iGPU debayer, dGPU encode) — deferred; iGPU now proven end-to-end
  - Cherry-pick de Goede RFC for logging robustness — optional, low priority
  - Mesa debug dive for exact BAD_MATCH check — closed as unnecessary (outcome achieved via relabel)

### Overall strategy going forward:

  - Session focus complete: IPU6 camera operating zero-copy, GPU-accelerated, at native mode
  - Next session: daylight re-test → scale verdict → consolidated overlay patch → video-conferencing integration test (PipeWire)
