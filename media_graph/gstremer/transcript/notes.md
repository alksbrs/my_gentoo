# *linbcamera* config

## cam utility use for test captures

DRI_PRIME=pci-0000_00_02_0 LIBCAMERA_SOFTISP_MODE=gpu LIBCAMERA_LOG_LEVELS="*:DEBUG" \
timeout 10 cam -c 1 -C6 -F'/tmp/xday#.ppm' -s role=viewfinder,width=1932,height=1092 \
2>&1 | tee /tmp/xday.log

## script to measure .ppm RGB values:

cat > ~/measure_ppm_rgb.py <<'PY'
#!/usr/bin/env python3
import sys

def measure(path):
    with open(path, 'rb') as f:
        magic = f.readline().strip()
        if magic != b'P6':
            raise ValueError(f"{path}: not a P6 PPM (got {magic})")
        vals = []
        while len(vals) < 3:
            line = f.readline()
            if line.startswith(b'#'):
                continue
            vals.extend(line.split())
        width, height, maxval = (int(v) for v in vals)
        data = f.read(width * height * 3)

    r = data[0::3]
    g = data[1::3]
    b = data[2::3]
    mr, mg, mb = sum(r)/len(r), sum(g)/len(g), sum(b)/len(b)
    print(f"{path}: R={mr:.2f} G={mg:.2f} B={mb:.2f}  G/R={mg/mr:.3f}  G/B={mg/mb:.3f}")

for p in sys.argv[1:]:
    measure(p)
PY

then run: python3 ~/measure_ppm_rgb.py /tmp/xdaycam0-stream0-00000{2,3,4,5}.ppm

## Convert .ppm files to .png

for f in /tmp/xdaycam0-stream0-00000{2,3,4,5}.ppm; do
  magick "$f" "${f%.ppm}.png"
done

# *D-Bus*

D-Bus is Linux's standard inter-process message bus — a way for unrelated processes to call methods on each other, listen for signals, and discover services by name, without needing to know each other's PID or set up their own socket protocol. Two buses run on a typical desktop: a session bus (per logged-in user — things like desktop notifications) and a system bus (one per machine, root-privileged operations — hardware access, power management). The one that matters for your audio gap is the system bus.

# *pipewire + GStreamer + Wayland* integration

PipeWire + GStreamer + Wayland: how the pieces fit together

PipeWire is the low-level media server — a single daemon that handles both audio and video routing on modern Linux. It replaced PulseAudio (audio) and pieces of the older Wayland screen-capture stack (video) with one graph-based engine. Every audio/video source and sink — a microphone, your headphone jack, a browser tab requesting your camera — becomes a node in a graph that PipeWire connects and routes in real time, at the sample/frame level.

WirePlumber is PipeWire's session/policy manager. PipeWire itself doesn't decide which microphone is "default" or how a new headphone should auto-connect when plugged in — that policy logic lives in WirePlumber. As of WirePlumber ≥0.5 (which Gentoo's current media-video/wireplumber ships), configuration moved from Lua scripts to SPA-JSON .conf files under /usr/share/wireplumber/wireplumber.conf.d/ (system defaults) and ~/.config/wireplumber/wireplumber.conf.d/ (your overrides) — Lua is now scripting-only, not config. This matters directly for you: if you find any guide online still talking about editing .lua files for policy, it's stale for your version.

GStreamer sits a layer above both — it's an application-facing multimedia framework. GStreamer doesn't talk to your headphone jack directly; it has a pipewiresrc/pipewiresink element pair that connects a GStreamer pipeline (used by apps: browsers via WebRTC, video players, your cam-adjacent tooling) to PipeWire as a node in its graph. So the chain for something like a video call is: app → GStreamer pipeline → pipewiresrc/sink element → PipeWire graph node → WirePlumber-assigned route → ALSA/kernel driver → hardware.

Where native Wayland fits in: Wayland itself doesn't carry audio or PipeWire traffic — it's a separate protocol for display/input. The connection point is xdg-desktop-portal (specifically the wlr-screencast/pipewire portal backend under wlroots-based compositors, or the equivalent under GNOME/KDE's own portal implementations), which brokers permission for an app to open a PipeWire video stream (e.g., screen-share) without that app needing direct access to your compositor. Audio doesn't go through the portal at all — apps talk to PipeWire directly for audio, portal-mediated permission is a video/screen-capture-specific concern. This distinction matters for your camera work (portal-relevant) vs. your headphone issue (not portal-relevant, pure PipeWire+WirePlumber+ALSA).


pkill wireplumber

LIBCAMERA_SOFTISP_MODE=gpu DRI_PRIME=pci-0000_00_02_0 LIBCAMERA_LOG_LEVELS="*:DEBUG" \
WIREPLUMBER_DEBUG=4:s-monitors-libcam,m-monitor wireplumber 2>&1 | tee /tmp/wp-gpu-check.log &
sleep 3

wpctl status -n

grep -i -E "debayer_egl|eglCreateImageKHR" /tmp/wp-gpu-check.log


*camera frames flow test*
gst-launch-1.0 pipewiresrc target-object="libcamera_input.__SB_.PC00.LNK0" ! videoconvert ! autovideosink

## gstreamer test captures (synthetic video source)

# AV1 primary
gst-launch-1.0 videotestsrc num-buffers=90 ! video/x-raw,width=1280,height=720 ! \
  varenderD129postproc ! video/x-raw\(memory:VAMemory\),format=NV12 ! \
  varenderD129av1lpenc rate-control=cbr bitrate=2000 ! av1parse ! matroskamux ! \
  filesink location=/tmp/va-av1-test.mkv

# VP9 fallback
gst-launch-1.0 videotestsrc num-buffers=90 ! video/x-raw,width=1280,height=720 ! \
  varenderD129postproc ! video/x-raw\(memory:VAMemory\),format=NV12 ! \
  varenderD129vp9lpenc rate-control=cbr bitrate=2000 ! matroskamux ! \
  filesink location=/tmp/va-vp9-test.mkv

## gstreamer test captures (webcam's native 1932x1092px)

# AV1, near-native resolution, live camera source
gst-launch-1.0 pipewiresrc target-object="libcamera_input.__SB_.PC00.LNK0" ! \
  video/x-raw,width=1920,height=1080 ! videoconvert ! \
  varenderD129postproc ! video/x-raw\(memory:VAMemory\),format=NV12 ! \
  varenderD129av1lpenc rate-control=cbr bitrate=4000 ! av1parse ! matroskamux ! \
  filesink location=/tmp/va-av1-native.mkv

# VP9, near-native resolution, live camera source
gst-launch-1.0 pipewiresrc target-object="libcamera_input.__SB_.PC00.LNK0" ! \
  video/x-raw,width=1920,height=1080 ! videoconvert ! \
  varenderD129postproc ! video/x-raw\(memory:VAMemory\),format=NV12 ! \
  varenderD129vp9lpenc rate-control=cbr bitrate=4000 ! matroskamux ! \
  filesink location=/tmp/va-vp9-native.mkv

## test capture to the screen

gst-launch-1.0 pipewiresrc target-object="libcamera_input.__SB_.PC00.LNK0" ! \
  video/x-raw,width=1920,height=1080 ! videoconvert ! \
  varenderD129postproc ! video/x-raw\(memory:VAMemory\),format=NV12 ! \
  varenderD129postproc ! video/x-raw ! videoconvert ! autovideosink

## playback of test captures

gst-launch-1.0 filesrc location=/tmp/va-vp9-native.mkv ! matroskademux ! \
  vp9parse ! varenderD129vp9dec ! videoconvert ! autovideosink

gst-launch-1.0 filesrc location=/tmp/va-av1-native.mkv ! matroskademux ! \
  av1parse ! varenderD129av1dec ! videoconvert ! autovideosink

## gstreamer live video capture test

* shell 1



* shell 2



*TO-DO*

OPTION 1

Use Epiphany for WebRTC but mitigate the memory-residency issue:

# Force VA surfaces to stay on GPU by ranking VA-API decoders highest
export GST_PLUGIN_FEATURE_RANK="vaapih264enc:MARGINAL,vaapih264dec:PRIMARY"

# Set memory limit to prevent implicit swaps
export GST_ALLOCATOR_VSP2_FORCE_CONTIGUOUS=1
export VA_DRIVER_NAME=iHD  # Intel only; AMD use radeonsi


# Force VA surfaces to stay on GPU by ranking VA-API decoders highest
export GST_PLUGIN_FEATURE_RANK="vaapih264enc:MARGINAL,vaapih264dec:PRIMARY"

# Set memory limit to prevent implicit swaps
export GST_ALLOCATOR_VSP2_FORCE_CONTIGUOUS=1
export VA_DRIVER_NAME=iHD  # Intel only; AMD use radeonsi
Reality check: This is band-aid territory. The GStreamer pipeline still lacks architectural commitment to GPU residency. You'll achieve ~70-80% success compared to FFmpeg's near-100%.


OPTION 2

libva directly	✅ Excellent — Full control, true zero-copy with DMA-BUF export	⚠️ Manual Wayland integration, must use DRM/EGL	High	Intel/AMD/NVIDIA	Optimal for custom pipelines; steepest learning curve

OPTION 3

Investigate V4L2 M2M if your dGPU supports it (check vainfo for V4L2 codec exposure)
On Raspberry Pi and some embedded Intel platforms, V4L2-M2M is native zero-copy
Unlikely on your discrete x86 dGPU, but worth verifying

OPTION 4

If Epiphany is mandatory (e.g., tight GNOME integration), use it for video playback only, and route WebRTC conferencing through a separate standalone CLI app (using FFmpeg directly) with Epiphany displaying the output via HTTP streams or local sockets.




----------------------

OTHER TRICKS:

# write to protected directories/files use 'tee' command

sudo tee /etc/portage/repos.conf/emilienmottet.conf > /dev/null << 'EOF'
...
EOF

# configure Epiphany's USER_AGENT:

WEBKIT_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36" epiphany 2>/dev/null &!
