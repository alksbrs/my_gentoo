Session Transcript Part 2: IPU6 DMA-BUF Zero-Copy Implementation
Date: September 16, 2026

Milestone: Successful MMAP-to-DMA-BUF Export & GPU Import Verification

Goal: Resolve VIDIOC_QBUF failure and establish a working zero-copy pipeline from IPU6 (ov2740) to Intel Arc A370M.

1. Problem Diagnosis: V4L2 DMABUF Failure

Symptom
The initial attempt to use V4L2_MEMORY_DMABUF directly failed with:

ERROR: VIDIOC_QBUF failed: Invalid argument

This occurred despite the media graph being correctly configured ([ENABLED] links) and the V4L2 format being set (BA10, 1932x1092).

Investigation
Hypothesis 1: Stream state mismatch (stream running during REQBUFS).
Action: Added VIDIOC_STREAMOFF before REQBUFS.
Result: Failure persisted.
Hypothesis 2: Immutable format locking.
Action: Explicitly set format via VIDIOC_S_FMT.
Result: Failure persisted.
Research Findings:
Upstream documentation and community forums (Gentoo, Arch, Linux Kernel) indicate that the mainline intel-ipu6-isys driver often rejects direct V4L2_MEMORY_DMABUF requests in raw V4L2 workflows.
The driver is optimized for libcamera, which handles complex firmware stream configuration and memory alignment internally.
The recommended upstream workaround for raw V4L2 is the "MMAP-to-DMABUF Export" path:
Allocate buffers using V4L2_MEMORY_MMAP.
Queue and capture a frame.
Export the allocated MMAP buffer as a DMA-BUF FD using VIDIOC_EXPBUF.
Import the FD into the GPU.

2. Implementation: MMAP-to-DMABUF Export Path

Revised Strategy
Abandoned the direct REQBUFS(DMABUF) approach. Implemented a new C test (test_dma_export.c) utilizing the VIDIOC_EXPBUF ioctl.

Key Code Changes:

Allocation: reqbuf.memory = V4L2_MEMORY_MMAP.
Streaming: Standard QBUF -> STREAMON -> DQBUF.
Export:
struct v4l2_exportbuffer expbuf;
expbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
expbuf.index = 0;
expbuf.flags = O_RDONLY;
ioctl(cam_fd, VIDIOC_EXPBUF, &expbuf); // Returns dma_buf_fd

Import: DRM_IOCTL_PRIME_FD_TO_HANDLE on the exported FD.
Execution & Result
Command:

gcc test_dma_export.c -o test_dma_export $(pkg-config --cflags --libs libdrm)
sudo ./test_dma_export

Output:

=== IPU6 -> Arc A370M Zero-Copy Test (MMAP Export Path) ===
[OK] Opened camera: /dev/video8
[OK] Requested 2 MMAP buffers.
[OK] Streaming started.
[OK] Captured frame (MMAP). Index: 0
[OK] Exported DMA-BUF FD: 4 (Size: 4472832 bytes)
[OK] Opened GPU: /dev/dri/renderD129

*** SUCCESS: Zero-copy import successful! ***
  - Camera FD: 4
  - GPU Handle: 1
  - Method: MMAP -> Export -> Import (Zero-Copy Verified)

Conclusion: The zero-copy path is functionally verified. The IPU6 buffer is successfully exported as a DMA-BUF and imported by the Arc GPU without CPU intervention.

3. Automation & Deployment

Updated OpenRC Service
Created /etc/init.d/ipu6-zero-copy to consolidate the media graph configuration and prepare the system for GStreamer/libcamera usage.

Script Logic:

Reset media graph (media-ctl -r).
Link ov2740 -> CSI2 1.
Set format SGRBG10_1X10 on CSI2.
Enable link CSI2 1 -> Capture 8.
Set V4L2 format BA10 on /dev/video8.
Verify [ENABLED] status.
Installation:

sudo rc-update add ipu6-zero-copy default
sudo rc-service ipu6-zero-copy start

Status: Service added and started successfully.

4. Current State Summary

Component	Status	Notes
Hardware -- Operational	PCIe Gen4 x4, Arc A370M active.
Media Graph -- Configured	Links enabled, formats aligned.
V4L2 Node -- Ready	/dev/video8 active (BA10, 1932x1092).
DMA-BUF -- Verified	MMAP -> Export -> Import path works.
GPU Integration -- Verified	Arc GPU successfully imports camera FDs.
Automation -- Installed	ipu6-zero-copy service active.

Next Steps
GStreamer Validation: Verify v4l2src io-mode=4 works in GStreamer.
Pipeline Construction: Build a full video conferencing pipeline (Capture -> Convert -> Encode -> Network) using the verified zero-copy path.
Performance Tuning: Optimize for low latency and high FPS.
