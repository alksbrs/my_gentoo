# Debugging session transcript

## 1. System

`/var/db/repos/local/media-libs/libcamera` (package dir; Manifest regenerated 09-Sep)
`-Dipas=simple` `-Dsoftisp-gpu=enabled` `-Dpipelines=simple,uvcvideo,vimc`
PATCHES=( agc.h.patch, agc.cpp.patch, egl-r16-import.patch, bayer-r10p-scale-fix.patch )
`cam` CLI: `cam -c 1 -C6 -F'/tmp/x#.ppm' -s role=viewfinder,width=1932,height=1092`
Capture output: P6 PPM, ABGR8888-as-RGB (3 B/px, 6316128 B/frame at 1928x1092)
Tuning: `/usr/share/libcamera/ipa/simple/ov2740.yaml`
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

## 4. Commands used

Capture (canonical form): `DRI_PRIME=... LIBCAMERA_SOFTISP_MODE=gpu LIBCAMERA_LOG_LEVELS="*:DEBUG" timeout 10 cam -c 1 -C6 -F'/tmp/x#.ppm' -s role=viewfinder,width=1932,height=1092 2>&1 | tee /tmp/x.log`
PPM measurement: python3 heredoc P6 parser — nonzero %, max, mean (script in session; use 3 B/px PPM semantics)
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

## 6. Root cause (updated, final)

BLACK FRAMES (GPU only): RAW10P reconstruction assumed GL_LUMINANCE byte-pair texel layout; after R16 relabel the sampler delivers one 16-bit channel — `.g` term reads 0, `.r` term scale ≈ 1/262140 → shader writes RGB=0, alpha=255. Import itself was already fixed and healthy (0 eglCreateImageKHR failures, AGC stats healthy on CPU-mapped input). One-line scale fix closes it. Evidence chain: probe 0,0,0,255 ×6 (pre) → 16,16,16/0,12,3/8,11,0 ×6 (post); full-frame max 255, 49% nonzero.
AGGREGATING LESSON (meta): two false trails (provenance panic on pristine tree; stale-binary suspicion) consumed sessions — both died the moment evidence was demanded before inference. Rule enforced: grep-before-filter, verify deployed artifact contents (strings), never assume rebuild = recompile.

## 7. Open items

Daylight re-test — formal scale closer (flashlight night: mean 10.51 plausible, not dispositive; expect ~80-170 daylight mean)
PipeWire video-conferencing integration test — the project objective
RAW12P fix: same one-line pattern (`p.r * 16.0`) IF 12-bit ever enters validated set — do not touch now
default_cma_region perms (0600 root) — housekeeping, non-blocking (system heap is operative)
Retire legacy references to malformed ipu6-egl-import-debug.patch name (superseded by egl-r16-import.patch)
Periodic: version-timestamp fingerprint check after every merge (static timestamp = deploy integrity alarm)

### Overall strategy going forward:

 Next session single entry point: daylight capture → mean measurement → scale verdict
 Then PipeWire integration (conference stack end-to-end)
 Overlay is sole source of truth; keepwork is convenience only
