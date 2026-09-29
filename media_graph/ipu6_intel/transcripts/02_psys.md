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
| `CONFIG_VIDEO_INTEL_IPU6=m`, `CONFIG_IPU_BRIDGE=m`, `CONFIG_INTEL_SKL_INT3472=m` | Kernel config options `ipu6-drivers`' README lists as hard requirements | **Confirmed set**, both before and after the `6.18.48`→`6.18.52` upgrade |
| `CONFIG_V4L2_CCI_I2C` | Required by `ipu6-drivers`' `dkms.conf` `BUILD_EXCLUSIVE_CONFIG` for kernel ≥ 6.8.0 | Was unset — **fixed** by enabling `VIDEO_IMX219` (pulls it in as a dependency-free transitive `select`, no other effect) |

## 4. Phase 2 — status (updated: items 1–4 CLOSED, item 5 in progress)

1. **CLOSED.** PCI ID `8086:465d` — "Alder Lake Imaging Signal Processor" →
   confirms `ipu6ep` variant. iGPU confirmed same trip: `8086:46a6`, Iris Xe,
   Alder Lake-P GT2
2. **CLOSED.** Kernel `6.18.52-gentoo` (upgraded from `6.18.48` mid-phase via
   `make olddefconfig`; all downstream config prerequisites confirmed carried
   forward unchanged)
3. **CLOSED, practically.** `lsmod | grep vsc` empty; `dkms.conf`'s own
   version-gated module list (below) confirms IVSC/LJCA modules are excluded
   by upstream design for kernel ≥ 6.6, independent of this hardware's actual
   IVSC presence — no open question remains here
4. **CLOSED — narrower scope than expected.** `ipu6-camera-bins`'s license
   concern applies only to its proprietary `.so` library set
   (`libia_aiq`, `libia_cca`, `libia_isp_bxt`, `libgcss`, `libia_ltm`,
   `libia_dvs`, etc. — confirmed present, no source, per-IPU-variant suffixed).
   **Firmware itself does NOT require this repo or ACCEPT_LICENSE handling as
   a separate concern**: `ipu6ep_fw.bin` is upstreamed into the standard
   `linux-firmware` project (confirmed — Arch's `linux-firmware-intel`
   package lists `intel/ipu/ipu6ep_fw.bin.zst` directly; Phoronix confirms
   "IPU6 Firmware Binaries Upstreamed" as a mainline `linux-firmware` commit).
   The file already present on this system at
   `/lib/firmware/intel/ipu/ipu6ep_fw.bin` matches that exact upstream path
   convention — very likely sourced from `sys-kernel/linux-firmware`, not
   hand-extracted from `ipu6-camera-bins`. Provenance not yet directly
   confirmed — `equery belongs /lib/firmware/intel/ipu/ipu6ep_fw.bin` still
   outstanding, low priority since the practical answer (no separate firmware
   fetch needed) is already established
5. **IN PROGRESS — kernel module build/probe done, HAL/plugin not started.**
   Corrected component list, with real category names verified against two
   independent existing Gentoo overlays (`EmilienMottet`, `bt4`/`fol4`) rather
   than assumed — all four land in `/var/db/repos/local/` (same overlay as
   the existing `libcamera-9999` ebuild) but in their own category
   subdirectories, not alongside it:
   - `media-video/ipu6-drivers` — DKMS kernel module. **Built and probing
     successfully on 6.18.52** (see §6) — raw `dkms` proven working; not yet
     wrapped as a local overlay ebuild (Option B, agreed direction, deferred
     until HAL/plugin chain is also proven)
   - `sys-firmware/ipu6-camera-bins` — proprietary `.so` libraries only (see
     item 4 above re: firmware). Binary-install ebuild, no compilation
   - `sys-apps/ipu6-camera-hal` — userspace HAL. **CMake** build
     (`-DIPU_VERSIONS="ipu6;ipu6ep;ipu6epmtl"`), depends on
     `ipu6-camera-bins`, needs `libexpat`, `automake`, `libtool`,
     `gstreamer1.0-dev`, `gst-plugins-base-dev`, `libdrm-dev`
   - `media-plugins/gst-plugins-icamerasrc` — GStreamer source element,
     **replaces `libcamerasrc` entirely** for this route (Phase 1's GStreamer
     work is not reused here). **Autotools** build (`autogen.sh`/`configure`/
     `make`), **must use branch `icamerasrc_slim_api`, not `master`** (the
     default branch is the wrong one — confirmed by inspecting the actual
     repo). Needs `libdrm-dev`, `libva-dev`, `gst-plugins-bad1.0-dev`
   - `v4l2loopback` + `v4l2-relayd` — expose result as `/dev/videoN`, not
     started
   Two favorable findings from direct repo inspection, resolving earlier open
   concerns: (a) `icamerasrc`'s own documented example for "12th/13th Gen
   Intel Core Processors (with ... ov2740 ... sensor)" outputs
   `format=NV12` directly — the RGBA/NV12 mismatch that blocked `vah264enc`
   in Phase 1 does not apply to this route; (b) DMA-BUF zero-copy is
   supported here too via `--enable-gstdrmformat=yes` (gated on GStreamer >
   1.22.0; this system has 1.26.11)
6. Post-build: A/B image-quality comparison against the Phase 1 fallback,
   same PPM-capture/luminance-measurement methodology already established
   (transcript.md §4)

## 6. PSYS kernel-module build — progress log

`CONFIG_V4L2_CCI_I2C` (required by `dkms.conf`'s version-gated
`BUILD_EXCLUSIVE_CONFIG` for kernel ≥ 6.8.0, specifically triggered by the
`ov05c10` sensor branch which fires unconditionally for any kernel this new)
was unset — root-caused via direct Kconfig trace (`select`-only symbol, no
direct prompt); resolved by enabling `VIDEO_IMX219` (clean dependency pull,
no side effects: `V4L2_CCI_I2C`/`V4L2_CCI`/`REGMAP_I2C` are all
dependency-free `tristate` helpers) and rebuilding modules (no full kernel
reinstall/reboot needed)
`sudo dkms autoinstall ipu6-drivers/0.0.0` — **succeeded** on 6.18.52,
building `intel-ipu6-psys.ko` plus several unrelated sensor modules
(`hm11b1`, `ov01a1s`, `ov02c10`, `ov02e10`, `hm2170`, `hm2172`, `ov05c10`,
`s5k3j1`) that are harmless no-ops on this hardware (no matching device).
Single kernel-compat patch applied automatically:
`0001-v6.10-IPU6-headers-used-by-PSYS.patch`
`sudo modprobe intel-ipu6-psys` — **clean probe**, no errors:
`pkg_dir entry count:8`, `psys probe minor: 0`, bound to `intel_ipu6.psys.40`.
`/dev/ipu-psys0` created. This was NOT the predicted outcome (a
firmware-not-found failure was expected and stated in advance) — noting the
miss rather than silently treating the clean result as if it were expected
Firmware load/execution itself remains UNVERIFIED — PSYS drivers of this
design defer `request_firmware()` to first real processing request, not
module-load time; no userspace client capable of issuing one exists yet
(mainline libcamera has no PSYS-capable pipeline handler at all — confirmed,
no `ipu6` entry in `meson_options.txt`'s `pipelines` choices). This is
exactly what `ipu6-camera-hal`/`icamerasrc` (item 5 above) are needed to test

## 7. Local overlay ebuilds — build log, both packages emerged successfully

**`sys-firmware/ipu6-camera-bins-9999`** — pinned `EGIT_COMMIT` to commit
`30e87664829782811a765b0ca9eea3a878a7ff29`. License accepted via
`ACCEPT_LICENSE="*"` (already set — no `package.license` entry needed, that
file is a single regular file, not a directory, on this system).
`ipu6ep`-only files installed (19 `.so.0`, 2 `.a`, 3 `.pc`, verified by exact
glob-count match against the real upstream tree before writing the ebuild);
`.pc` `libdir` patched from upstream's hardcoded `/usr/lib` to `/usr/lib64`.
Firmware NOT installed by this ebuild — the existing
`/lib/firmware/intel/ipu/ipu6ep_fw.bin` (sha256
`60105304e5b66a5a85aac7541b31dc71740240c6dc1a144036b4b72ef2fb1ba1`) is
**byte-identical** to the copy inside this same bins commit, confirmed by
direct hash comparison — no separate firmware fetch was ever needed.
**Emerged successfully.** `scanelf` flagged NULL `DT_RUNPATH` on 4 of the 19
prebuilt libs (`libia_exc`/`nvm`/`coordinate`/`log`-ipu6ep) — left as-is,
patching prebuilt binaries would violate the redistribution-only license
**`sys-apps/ipu6-camera-hal-9999`** — pinned `EGIT_COMMIT` to
`7ccab62d133e053c8628f3591b636a761f06c956` (2026-09-25, ~15 months after the
bins commit — build-tested compatible in an isolated sandbox before writing
this ebuild, not merely assumed). `-Werror` stripped from upstream's
`CMakeLists.txt` in `src_prepare` (newer Gentoo GCC than upstream tests
against should not fail the build on new warnings); built restricted to
`-DIPU_VERSIONS=ipu6ep` only. **Emerged successfully** — CMake 4 vs.
upstream's `cmake_minimum_required(VERSION 2.8)` triggered Gentoo's known,
tracked automatic workaround (`-DCMAKE_POLICY_VERSION_MINIMUM=3.5`, bug
#951350) — informational, not a build failure, no action needed. Verified
post-install: `/usr/lib64/libcamhal/plugins/ipu6ep.so` present,
`/etc/camera/ipu6ep/sensors/ov2740-uf.xml` present (matches this machine's
actual topology: CSI port 1, `1932x1092 SGRBG10_1X10`, ships
`OV2740_CJFLE23_ADL.aiqb` — Chicony-module calibration; this machine is an
Acer, so tuning accuracy is an open runtime question, not a build one),
`pkg-config --exists libcamhal` succeeds, `libdir` reports `/usr/lib64`
correctly (no lib/lib64 mismatch to fix in the later `icamerasrc` ebuild)

**Sandbox build-compatibility test (Ubuntu 24.04 container, not this
machine):** confirmed the full source chain compiles and links end-to-end —
`ipu6-camera-bins` (installed the same way the ebuild does) →
`ipu6-camera-hal` master → `icamerasrc` (`icamerasrc_slim_api` branch,
`--enable-gstdrmformat=yes`, confirmed `GST_DRM_FORMAT` defined in the
resulting `config.h`) — before writing any ebuild for these, specifically to
retire the bins/HAL date-gap risk flagged in §4 item 5. This proves
compile/link compatibility only, not runtime behavior on real IPU6 hardware

## 8. Local overlay survival — `emerge --depclean` removal risk, fixed

**Found:** both packages above were installed with `emerge -1`
(`--oneshot`), which deliberately does not record them in
`/var/lib/portage/world`. `sudo emerge --depclean --ask --with-bdeps=y
--verbose` marked both for removal, since `depclean` only protects packages
in `@world` (or depended on by something in `@world`) and nothing on this
system depends on either package yet
**Fix, applied:** `sudo emerge --noreplace sys-firmware/ipu6-camera-bins
sys-apps/ipu6-camera-hal` — adds both to `world` without rebuilding (already
same version merged), confirmed by grepping `/var/lib/portage/world`
**Standing rule for the remainder of this phase:** every subsequent install
(`media-video/ipu6-drivers`, `media-plugins/gst-plugins-icamerasrc`,
`v4l2loopback`, `v4l2-relayd`) uses plain `sudo emerge <pkg>` — **never
`-1`/`--oneshot`** — specifically so a future `--depclean` doesn't silently
remove this phase's work. Re-verify with `sudo emerge --depclean --ask
--with-bdeps=y --verbose` (dry-run via `--pretend` first, since `--ask`
already gives a confirmation prompt) after each new package lands, not only
at the end of the phase

## 5. Known risks — accepted (user-directed) vs. newly found (verify after build)

**Accepted per §0, unchanged:**
- IPU6 firmware re-authentication failure after S3 suspend on kernel 6.16+,
  unfixed upstream (`intel/ipu6-drivers#381`) — accepted as lower priority
  than image quality/HDR
- DKMS rebuild required on every kernel update; out-of-tree repo has a
  documented history of lagging kernel API changes
- No official Gentoo-tree package for any of the 4 out-of-tree components
  (corrected count — IVSC is not needed, see §4 item 3); third-party overlay
  only, unofficial, same category of risk as the current `libcamera-9999`
  live ebuild but across a larger dependency surface
- HDR capability on this route is not yet confirmed to exist at all — pursuing
  PSYS does not guarantee an HDR fix, only dedicated-hardware debayer/ISP
  processing; still open pending investigation

**Newly found this phase — not yet encountered directly, flagged to verify
once the HAL/plugin build reaches the same test stage, so a real occurrence
isn't mistaken for something novel:**
- A Gentoo forum report (Lenovo X1 Carbon 12th-gen, IPU6, same
  `icamerasrc`/HAL stack) hit the **same `not-negotiated (-4)` failure
  class** already seen once this project (Phase 1's `vah264enc` test) — this
  time through PipeWire's `pipewiresrc`/`GstAutoVideoSrc`, unresolved as of
  that thread's last activity, despite the reporter using the same
  PipeWire/libcamera patch set referenced from Hans de Goede's work
- A separate Gentoo overlay maintainer (`bt4`/`fol4`) documents that this
  stack's kernel modules **must load in a specific order**, and states they
  had not found a reliable way to force correct load ordering at boot as of
  their writeup — a boot-reliability risk distinct from the already-accepted
  suspend/resume issue
