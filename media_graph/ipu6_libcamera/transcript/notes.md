# 1. libcamera-0.7.2 Meson Build Arguments

Category	Argument        Default Type	Recommendation	Purpose

Core Build	-Dwerror=true	true	bool
✓ Keep	Treat compiler warnings as errors; catches undefined behavior early. Essential for production builds. From default_options in meson.build.

Core Build	-Dwarning_level=2	2	int
✓ Keep	Warning level 2 = -Wall -Wextra; production-grade validation. From default_options in meson.build.

Core Build	`-Dcpp_std=c++20	c++20	string
✓ Keep	C++20 required per meson.build. Mandatory; no older standard supported in 0.7.2.
Pipelines	-Dpipelines=['auto']	['auto']	array	Conditional	Auto-selects pipelines for target architecture. Use 'all' for maximum coverage, or specify ['ipu3','rkisp1','rpi/vc4','simple','uvcvideo'] for minimal bloat.

IPAs	-Dipas=['<list>']	empty	array
Conditional	IPA (Image Processing Algorithm) modules. Choices: ipu3, mali-c55, rkisp1, rpi/pisp, rpi/vc4, simple, vimc. Match selected pipelines.

Applications	-Dcam=auto	auto	feature
Recommended	Build cam test utility (lightweight camera testing tool). Essential for validation.

Applications	-Dcam-output-kms=auto	auto	feature	Optional
KMS sink for cam (requires libdrm-dev). Useful for hardware-accelerated display on embedded systems.

Applications	-Dcam-output-sdl2=auto	auto	feature
Optional	SDL2 sink for cam (requires libsdl2-dev). Good for X11/Wayland preview during testing.

Applications	-Dcam-jpeg=auto	auto	feature	Optional
JPEG encoding in cam (requires libjpeg-dev). Minimal overhead if SDL2 enabled.
Applications	-Dqcam=auto	auto	feature	Optional	Qt6-based GUI camera application (requires qt6-base-dev). Heavier than cam but user-friendly.

Multimedia	-Dgstreamer=auto	auto	feature	Optional
GStreamer plugin libcamerasrc (requires libgstreamer1.0-dev). Essential for media frameworks (PipeWire, Pulseaudio integration).

Debugging	-Dlibdw=auto	auto	feature	Recommended
libdw for detailed backtraces (requires libdw-dev). Improves crash debugging on production systems.

Debugging	-Dlibunwind=auto	auto	feature	Optional
libunwind as fallback backtrace (requires libunwind-dev). Less detailed than libdw but lighter.

Hotplug	-Dudev=auto	auto	feature	Recommended
libudev for camera hotplug detection (requires libudev-dev). Critical for dynamic camera enumeration.

Tracing	-Dtracing=auto	auto	feature	Optional
LTTng-based kernel-level tracing (requires liblttng-ust-dev). For production performance profiling.

Documentation	-Ddocumentation=auto	auto	feature	Optional
Doxygen HTML/PDF docs (requires doxygen, graphviz, sphinx). Only needed if building docs.
Documentation	-Ddoc_werror=false	false	bool
✓ Keep	Fail on doc warnings. Keep false unless shipping docs to end-users.

Testing	-Dtest=true/false	false	bool	Recommended=true
Compile unit tests (requires libgtest-dev, libevent-dev). Always true for CI/release validation. Adds vimc pipeline automatically.

Testing	-Dlc-compliance=auto	auto	feature	Optional
Camera HAL compliance checker (requires libgtest-dev, libevent-dev). For validating IPA module stability.

V4L2 Layer	-Dv4l2=auto	auto	feature	Conditional
V4L2 compatibility layer (allows legacy V4L2 apps to use libcamera). Enable on systems with legacy camera software.

Android	-Dandroid=disabled	disabled	feature	Usually=disabled
Android Camera3 HAL (requires android, libexif-dev, libjpeg-dev). Only if building for Android.

Android	-Dandroid_platform=generic	generic	combo	–	Platform: 'generic' or 'cros' (Chrome OS). Only relevant if android=enabled.

RPi Extended	-Drpi-awb-nn=auto	auto	feature	Optional
Raspberry Pi Neural Network AWB (Auto White Balance). Improves RPi color accuracy if rpi/vc4 or rpi/pisp pipeline enabled.

ISP GPU	-Dsoftisp-gpu=auto	auto	feature	amd64: enabled
GPU acceleration for software ISP (requires OpenGL ES 3.1+ via Mesa, libdrm). See Part 2 for amd64 configuration.

DNG Output	-Dapps-output-dng=auto	auto	feature	Optional
DNG file format writing in cam/qcam (requires libtiff-dev). Useful for RAW image debugging.

Python	-Dpycamera=auto	auto	feature	Optional
Python bindings (requires libpython3-dev, pybind11-dev). For Python-based camera applications (GStreamer Python scripts).

# 2. Meson Build Config for amd64

#!/bin/bash
# libcamera-0.7.2 build for amd64 with GPU-accelerated SoftISP
## Target: modern Intel/AMD desktop/laptop with integrated GPU

## Install build dependencies
sudo apt update
sudo apt install -y \
  python3-pip meson ninja-build pkg-config \
  gcc g++ git \
  libpython3-dev pybind11-dev \
  libyaml-dev libevent-dev \
  libgtest-dev libtiff-dev \
  gstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
  libudev-dev libdw-dev \
  libdrm-dev libglvnd-dev mesa-common-dev \
  libegl1-mesa-dev libgles2-mesa-dev \
  qt6-base-dev libsdl2-dev \
  doxygen graphviz sphinx-common

## Clone and prepare libcamera
git clone https://gitlab.freedesktop.org/camera/libcamera.git
cd libcamera
git checkout v0.7.2

## Setup Meson build with GPU-accelerated SoftISP
meson setup build \
  --prefix=/usr/local \
  --libdir=/usr/local/lib \
  -Dwerror=true \
  -Dwarning_level=2 \
  -Dcpp_std=c++20 \
  -Dpipelines='[auto]' \
  -Dipas='[simple,ipu3]' \
  -Dcam=enabled \
  -Dcam-output-sdl2=enabled \
  -Dcam-jpeg=enabled \
  -Dqcam=enabled \
  -Dgstreamer=enabled \
  -Dudev=enabled \
  -Dlibdw=enabled \
  -Dtracing=auto \
  -Dsoftisp-gpu=enabled \
  -Dtest=true \
  -Dv4l2=enabled

## Compile and install
ninja -C build
sudo ninja -C build install
sudo ldconfig

## Verify GPU acceleration availability
echo "=== Checking EGL/OpenGL ES availability ==="
glxinfo | grep -A 2 "OpenGL ES"
eglinfo 2>/dev/null | head -20 || echo "eglinfo not installed; GPU should still work"

## Test libcamera with GPU SoftISP
echo "=== Testing libcamera with GPU acceleration ==="
export LIBCAMERA_LOG_LEVEL=1  # Info level
/usr/local/bin/cam --list 2>&1 | head -20


## GPU debayering

Software ISP GPU acceleration in libcamera-0.7.2 is enabled by default in v0.7.0+ as "gpuisp" and uses Mesa OpenGL ES 3.1 via EGL with the surfaceless platform.

# Verification

aleksei:~ LIBCAMERA_LOG_LEVEL=1 cam --list 2>&1 | grep -i "gpu\|egl\|debayer"
aleksei:~

## Check if GPU ISP object files were compiled
file /usr/local/lib/libcamera/ipa/*.so | grep -i "elf"

## Inspect symbol table for GPU-related functions
nm /usr/local/lib/libcamera-internal.so.0 2>/dev/null | \
  grep -i "gpu\|egl\|debayer" | head -10

## Alternative: strings dump (slower but universal)
strings /usr/local/lib/libcamera.so.0 | grep -i "gpu_\|egl_" | head -5

