Session Transcript: IPU6 Camera & Arc A370M Zero-Copy Pipeline Setup
Date: September 16, 2026
Goal: Configure Intel IPU6 (ov2740) camera to stream raw Bayer data directly to Intel Arc A370M VRAM/System Memory via DMA-BUF for zero-copy video conferencing.
Environment: Gentoo Linux, Alder Lake-P CPU, Intel Arc A370M (Discrete), Intel Iris Xe (Integrated).

1. Hardware Verification & PCIe Topology

Initial Discovery
GPU Detection: The Arc A370M was initially invisible to lspci due to power management states (D3cold).
Topology Identification: lspci -t revealed the device is behind a PCIe switch:
Root Port: 00:06.0
Bridge: 01:00.0
Target: 03:00.0 (Intel DG2 [Arc A370M])
Link Speed Verification:
Command: lspci -vv -s 0000:00:06.0 | grep LnkSta
Result: Speed 16GT/s, Width x4 (PCIe Gen 4.0 x4).
Conclusion: Bandwidth (~6.3 GB/s) is >20x sufficient for raw 4K/1080p camera streams. No bottleneck.
Driver State
Initial State: i915 driver loaded, but Arc node (card1/renderD129) missing. GPU in sleep (0% usage).
Action: Forced re-bind of i915 driver (unbind/bind via sysfs) to wake the device.
Result: /dev/dri/card1 and /dev/dri/renderD129 appeared. GPU active (100% in powertop).
2. Camera Driver & Media Graph Configuration

Initial State
Modules Loaded: intel_ipu6, intel_ipu6_isys, ov2740 confirmed via lsmod.
Issue: v4l2-ctl failed to list the camera; media-ctl showed links were present but not fully enabled or misconfigured.
Entity Names: Corrected from generic guesses to exact names:
Sensor: "ov2740 10-0036"
Bridge: "Intel IPU6 CSI2 1"
Capture: "Intel IPU6 ISYS Capture 8" (/dev/video8)
Manual Configuration Steps (Successful)
Reset Graph: media-ctl -d /dev/media0 -r
Link Sensor: "ov2740 10-0036":0 -> "Intel IPU6 CSI2 1":0 [1]
Set Media Format: "Intel IPU6 CSI2 1":0 [fmt:SGRBG10_1X10/1932x1092]
Enable Critical Link: "Intel IPU6 CSI2 1":1 -> "Intel IPU6 ISYS Capture 8":0 [1] (This link was missing [ENABLED] initially).
Set V4L2 Format: /dev/video8 set to BA10 (10-bit Bayer), 1932x1092.
Verification:
media-ctl: Confirmed [ENABLED] on the Capture 8 link.
v4l2-ctl: Confirmed Pixel Format: 'BA10', 1932x1092.
v4l2-ctl --stream: Confirmed 30.03 fps capture working.
3. Automation: OpenRC Service

Created /etc/init.d/ipu6-camera to automate the configuration at boot.

Script Logic:

Reset media graph.
Link ov2740 to CSI2 1.
Set CSI2 1 format to SGRBG10_1X10.
Enable link to Capture 8.
Set /dev/video8 format to BA10.
Verify link status.
Status:

Service added to default runlevel.
Manual start successful: Pipeline configured successfully.
Final verification confirms [ENABLED] link and correct V4L2 format.
4. Challenges Encountered

lspci Visibility: Arc GPU hidden in D3cold state; required manual driver re-bind.
VIDIOC_QBUF Failure: Initial C code attempts to use DMA-BUF failed with Invalid argument.
Cause: Driver state mismatch (stream running during REQBUFS, or immutable format locking).
Resolution: Identified that manual V4L2 DMA-BUF flow is fragile for this driver.
Entity Naming: Incorrect sensor names (1-0036 vs 10-0036) caused link failures.
5. Current Milestone Status

- Hardware: PCIe Gen4 x4 link confirmed.
- Drivers: i915, intel-ipu6-isys, ov2740 loaded and functional.
- Media Graph: Fully configured with [ENABLED] links.
- V4L2 Node: /dev/video8 ready with correct format (BA10, 1932x1092).
- Automation: Boot-time configuration script installed and tested.

Next Phase:

- Implement the DMA-BUF Zero-Copy Pipeline (IPU6 -> System RAM -> Arc GPU) using libcamera or a refined V4L2 approach to feed the GPU encoder.


