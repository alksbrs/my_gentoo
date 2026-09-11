# Debugging session transcript

## 1. System

`/var/db/repos/local/media-libs/libcamera` (package dir; Manifest regenerated 09-Sep)
`-Dipas=simple` `-Dsoftisp-gpu=enabled` `-Dpipelines=simple,uvcvideo,vimc`
PATCHES=( agc.h.patch, agc.cpp.patch, egl-r16-import.patch, bayer-r10p-scale-fix.patch )
`cam` CLI: `cam -c 1 -C6 -F'/tmp/x#.ppm' -s role=viewfinder,width=1932,height=1092`
Capture output: P6 PPM, ABGR8888-as-RGB (3 B/px, 6316128 B/frame at 1928x1092)
Tuning: `/usr/share/libcamera/ipa/simple/ov2740.yaml`
`Agc: maxGain` is a LOCAL key added by agc.h.patch/agc.cpp.patch — absent from all upstream ov2740.yaml revisions (v1-v4); user hand-edits it per lighting condition (confirmed intentional, not drift)
Upstream checkout: gitlab.freedesktop.org/camera/libcamera.git tag v0.7.2, commit bdbf1453fb63cc7f40157ae86fcb0f9b7c57d773
Running binary: libcamera v0.7.2+dirty (timestamp moves per rebuild — use as deploy fingerprint)

## 2. Environment vars

`export LIBCAMERA_SOFTISP_MODE=gpu|cpu` (explicit value, never omitted)
`export LIBCAMERA_LOG_LEVELS="*:DEBUG"` (REQUIRED — probes log at DEBUG; dropping it silences diagnostics)
`export DRI_PRIME=pci-0000_00_02_0` (iGPU; `DRI_PRIME=0` is INVALID, Mesa ignores it)
`LIBCAMERA_DMA_HEAP` — RETIRED: v0.7.2 allocator ignores it (built-in candidate list linux,cma → reserved → system; log-verified); `default_cma_region` is mode 0600 root-only anyway

## 3. Resolved and confirmed (final)

GPU path black-frame root cause: RAW10P scale collapse — R16-imported texel delivers p.r=v/65535, p.g=0 (single channel); old macro `p.r/4 + p.g*64` output ≈ v/262140 ≈ 0 → RGB 0,0,0 with alpha 255 (probe-proven)
Fix: `#define pixel(p) p.r * 64.0` in `src/libcamera/shaders/bayer_unpacked.frag` (RAW10P block) — probe flipped to fluctuating nonzero, frame mean 10.51 / max 255 / 49% nonzero (night + flashlight, matches CPU-mode reference scale)
glsl_shaders.h is BUILD-GENERATED from .frag sources (upstream meson gen-shader-headers; confirmed via upstream patchwork + absent from src/) — the .frag IS the fix point in this tree
dma-heap EXONERATED: system heap operative (allocation+mmap roundtrip OK full frame size 8666112 B); default_cma_region 0600 blocks non-root (housekeeping item only)
Binary provenance exonerated as cause: controlled rebuild (patched tree, verify-then-build) reproduced black → fault is in code path, not binary history
CPU/GPU A/B (explicit SOFTISP_MODE): CPU mean ~21/49%-ish, GPU bit-exact zero (pre-fix) — GPU-path isolation confirmed
Post-fix validation: probe 0,0,0,255 → 16,16,16 / 0,12,3 / 8,11,0... ; full-frame 49.22% nonzero, max 255, mean 10.51; zero eglCreateImageKHR failures; ~30 fps cadence; IRIS Xe (ADL GT2)
Overlay self-sufficiency PROVEN: ebuild clean prepare from nothing → 4/4 patches [ok] (fuzz 2 on egl-r16-import hunk 2 — benign, known)
Daylight scale CLOSED: stabilized frames (post-AGC-ramp) mean 111.36-112.36, nonzero 98.59-98.64% — inside predicted 80-170 daylight range; shader fix holds under both night+flashlight and cloudy daylight
Color (green-cast) root cause CLOSED: local `ov2740.yaml` CCM table had two corrupted entries vs upstream — ct:3239 held a mis-copied fragment of upstream's ct:4939 matrix; ct:3865 was a verbatim duplicate of ct:6302. ct:2884 and ct:4136 anchors (present upstream) were missing entirely. Fixed by restoring all four entries from upstream v3/v4 (patchwork.libcamera.org series 5948). ct:2319/2854/4939/6302 were already correct — not touched
Color fix VERIFIED via per-channel PPM analysis (R/G/B means, not just luminance) across two independent lighting conditions: bright cloudy daylight G/R 1.217→1.038, G/B 1.186→1.038; dim/later-hour daylight G/R settled 1.031-1.054, G/B 1.026-1.052 — both post-fix results inside ±0.05-of-neutral band
KNOWN LIMITATION, accepted (not fixed, per user call): true-neutral reference test (white paper, dim conditions) showed residual G/R 1.17-1.20 (G/B near-neutral 1.04-1.05). AWB log showed scene temperature estimated at 9540-9556K — ~3200K past the highest calibrated CCM anchor (6302K). No AIQB calibration data exists above 6302K (upstream or local); `Ccm::prepare()` (src/ipa/simple/algorithms/ccm.cpp) interpolates unconditionally from AWB's estimated temperatureK with no confirmed in-tree clamp behavior verified. Residual attributed to CT-estimate exceeding calibrated coverage, not to a defect in the restored CCM data. User closed image quality on this basis — see §7

## 4. Commands used

Capture (canonical form): `DRI_PRIME=... LIBCAMERA_SOFTISP_MODE=gpu LIBCAMERA_LOG_LEVELS="*:DEBUG" timeout 10 cam -c 1 -C6 -F'/tmp/x#.ppm' -s role=viewfinder,width=1932,height=1092 2>&1 | tee /tmp/x.log`
PPM measurement (luminance): python3 heredoc P6 parser — nonzero %, max, mean (3 B/px PPM semantics)
PPM measurement (per-channel color): python3 heredoc P6 parser — R/G/B means via `data[0::3]`/`data[1::3]`/`data[2::3]` slicing, reports G/R and G/B ratios (~1.0 = neutral, ±0.05 tolerance in use this session)
PPM→PNG for visual confirmation: ImageMagick `magick "$f" "${f%.ppm}.png"` (v7 binary name; `convert` is the legacy alias, present on some distros)
AWB/AGC diagnosis: `grep -i -E "awb|gain" /tmp/x.log` — surfaces `IPASoftAwb awb.cpp:91 gain R/B: Vector {...}; temperature: N` and `IPASoftExposure agc.cpp:139 Clamping AGC max gain to N (driver-reported max was M)`
FBO readback probe: glFinish + glReadPixels 1x1 center + LOG(Debug) in debayerGPU() else-branch
Deploy verification: `strings /usr/lib64/libcamera.so.0.7.2 | grep -c "<literal string>"` (probe = 1 present / 0 retired); version timestamp in capture log header
Overlay ops: `sudo tee file <<'PATCH'` for root-owned files/ patch creation (sudo cat > FAILS: redirect runs as user)
Patch acceptance: `sudo cat -A` byte audit (blank context line = leading space, LF-only, no ^M); `ebuild ... manifest` after ANY files/ addition; `ebuild clean prepare` + grep trio (R16=1, scale-fix=1, probe=0)
Rebuild ritual (MANDATORY after manual tree edits): rm .compiled stamp + rm -rf build/ + keepwork compile/install/merge — incremental ninja silently skipped sudo-edited files twice (mtime-trust failure)
Tree-edit transport: python scripts written via cat > /tmp (user), applied via sudo python3 (only elevated step); anchors matched verbatim, abort-if-already-patched, abort-if-anchor-missing

## 5. Upstream consultation (completed)

glsl_shaders.h is meson-generated from shader sources (patchwork "meson: Automatically generate glsl_shaders.h from specified shader programs"); src/libcamera/shaders/meson.build subdir('shaders') wires it — .frag files are the source of truth
bayer_unpacked.frag RAW10P macro confirmed at line 46 verbatim; RAW12P sibling (line 49) carries the same structural flaw under R16 — DORMANT (validated set is 8/10-bit only); queued
Mesa policy (prior session, still standing): dmabuf import is external-sampling only, per-driver fourcc lists; R16 relabel remains the legitimate layout-true workaround
ov2740.yaml traced to patchwork.libcamera.org series 5948 "ipa: simple: Add OV2740 tuning file" (Javier Tia; v1/26682, v2/26699, v3/26715, v4/26760, June 2026) — calibrated from OV2740_CJFLE23_ADL.aiqb (Lenovo X1 Carbon Gen 10, Chicony CJFLE23), 8 CCM anchors 2319-6302K
Confirmed line-by-line: local file's ct:3239/ct:3865 entries diverged from upstream v3/v4 (corruption, not intentional local tuning); ct:2319/2854/4939/6302 matched upstream exactly; ct:2884/4136 anchors absent locally — all four discrepancies corrected against upstream v3/v4 data
Confirmed: `Agc:` block in every upstream revision (v1-v4) ends at the bare YAML end-of-document marker (`...`) with no sub-keys — `maxGain` is not and has never been an upstream-calibrated value; it's the local agc.*.patch addition (see §1)
`Ccm::prepare()` (src/ipa/simple/algorithms/ccm.cpp, confirmed via patchwork history of the "simple" IPA) calls `ccm_.getInterpolated(ct)` using `context.activeState.awb.temperatureK` every frame (subject to a 100K change-threshold gate) — confirms the interpolation mechanism feeding the CCM defect and the high-CT limitation in §3

## 6. Root cause (updated, final)

BLACK FRAMES (GPU only): RAW10P reconstruction assumed GL_LUMINANCE byte-pair texel layout; after R16 relabel the sampler delivers one 16-bit channel — `.g` term reads 0, `.r` term scale ≈ 1/262140 → shader writes RGB=0, alpha=255. Import itself was already fixed and healthy (0 eglCreateImageKHR failures, AGC stats healthy on CPU-mapped input). One-line scale fix closes it. Evidence chain: probe 0,0,0,255 ×6 (pre) → 16,16,16/0,12,3/8,11,0 ×6 (post); full-frame max 255, 49% nonzero.
GREEN CAST (color, all lighting): local `ov2740.yaml` CCM table carried copy/paste-type corruption at two of six populated anchors (ct:3239, ct:3865) and was missing two upstream anchors (ct:2884, ct:4136) outright — table was never a faithful copy of the calibrated upstream data it claimed to be sourced from. Fix: restore all four entries verbatim from upstream v3/v4. Evidence chain: G/R 1.217→1.038 and G/B 1.186→1.038 (bright daylight, frames 2-5); G/R settling 1.031-1.054 (dim daylight, frames 2-5) — both within ±0.05 of neutral, reproduced across two independent lighting conditions.
AGGREGATING LESSON (meta): two false trails (provenance panic on pristine tree; stale-binary suspicion) consumed sessions — both died the moment evidence was demanded before inference. A third pattern surfaced this session: ratio-close-to-1.0 results from grey-world AWB on arbitrary scenes only prove the algorithm satisfied its own assumption, not that color is accurate — a true-neutral reference target (white paper) was needed to catch the residual high-CT limitation, and should be the default test going forward, not an afterthought. Rule enforced: grep-before-filter, verify deployed artifact contents (strings), never assume rebuild = recompile, never trust a non-reference scene to validate color accuracy.

## 7. Open items

RAW12P fix: same one-line pattern (`p.r * 16.0`) IF 12-bit ever enters validated set — do not touch now
default_cma_region perms (0600 root) — housekeeping, non-blocking (system heap is operative)
Retire legacy references to malformed ipu6-egl-import-debug.patch name (superseded by egl-r16-import.patch)
High-CT CCM coverage gap (>6302K, observed residual at measured 9540K) — accepted as a known limitation this session, not queued for active work; revisit only if it becomes a practical problem in real use
Periodic: version-timestamp fingerprint check after every merge (static timestamp = deploy integrity alarm)

## 8. PipeWire sub-project (scope defined this session)

PipeWire config has never been directly addressed — user has managed sound exclusively through ALSA to date; no prior PipeWire audio configuration exists (not a regression, the unconfigured starting state)
Three domains in scope: VIDEO (camera → PipeWire, the original project objective), SOUND (headphone routing, currently broken — see §9), SCREEN SHARING (portal-mediated, `xdg-desktop-portal-wlr` already present as a running client per `wpctl status`, not yet configured/tested)
Priority order (user-set): video first → sound + screen sharing next → GStreamer/application-level integration only after PipeWire itself is working end-to-end
Init system constraint: OpenRC only, no systemd — `dmesg`/`dmesg -w` in place of `journalctl`; `rc-status` for service state; `elogind` (not `systemd-logind`) presumed to manage `/dev/snd/*` ACLs — unconfirmed, queued in §9

## 9. PipeWire audio — initial diagnostic (open, unresolved)

`wpctl status`: Audio → Devices and Audio → Sources both empty; only sink present is "Dummy Output" — PipeWire's built-in fallback node, generated when no real ALSA hardware is exposed to it. Confirms the problem is "no audio device in the PipeWire graph," not a headphone-specific symptom
`dmesg -w` (zero jack-detect activity) + `pw-mon` (zero node activity while flexing cable): BOTH INCONCLUSIVE, not reassuring — with no real device enumerated, neither signal has anything to originate from. Does NOT constitute evidence the physical connector is healthy; the planned hardware-vs-software test never actually reached real hardware
RTKit warnings present (`org.freedesktop.DBus.Error.ServiceUnknown`, ×3 in `wpctl status` output) — `rtkit-daemon` D-Bus service not registered, most likely because nothing starts it under OpenRC (normally systemd-activated elsewhere). Degrades realtime thread scheduling (falls back to `MaxRealtimePriority`/nice-level defaults) but does not by itself explain zero enumerated devices — secondary finding, non-blocking, fix after the primary gap
PipeWire 1.6.8 daemon confirmed alive and functioning as a bus (multiple real clients connected: `xdg-desktop-portal`, `xdg-desktop-portal-wlr` ×4 instances, `firefox`, `wpctl`) — the gap is specifically ALSA hardware never reaching the PipeWire graph, not the daemon being down
Diagnostics queued, not yet run: `/proc/asound/cards`, `aplay -l` (kernel/ALSA-level: is the card detected at all), `ps aux | grep -E "pipewire|wireplumber|rtkit"` + `rc-status` (are the right daemons actually running under OpenRC), `groups` + `ls -l /dev/snd/` (permission/group-membership gate, likely elogind-managed under this init system) — result determines whether the fix is kernel/ALSA-level or WirePlumber-ALSA-monitor/permissions-level

### Overall strategy going forward:

 Image quality (exposure + color) CLOSED — both daylight scale and green-cast verified fixed; high-CT residual documented and accepted, not blocking
 PipeWire is now a full sub-project: VIDEO → SOUND → SCREEN SHARING, in that order, before any GStreamer/application-level work begins
 Immediate next step (video priority): resume the camera-into-PipeWire integration test per §1 tooling
 Audio next step (queued, not blocking video): run the §9 diagnostics (`/proc/asound/cards`, `aplay -l`, `ps aux`, `rc-status`, `groups`, `ls -l /dev/snd/`) to localize the "no ALSA device reaches PipeWire" gap before proposing any config change
 Overlay is sole source of truth; keepwork is convenience only
