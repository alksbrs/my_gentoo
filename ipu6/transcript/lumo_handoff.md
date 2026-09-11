IPU6 Camera Zero-Copy Debugging Session — Technical Handoff
Session Metadata
Field	Value
Date	30 Aug 2026
Kernel	6.18.48-gentoo
Driver	intel_ipu6_isys (module) + xe (GPU driver for both iGPU + dGPU)
Sensor	OV2740 (1932×1092 active mode)
Target	Intel Alder Lake-P (iGPU Iris Xe) + DG2 Arc A370M (dGPU)
Priority	Zero-copy DMA-BUF import (highest priority)
Problem Statement

Symptom: eglCreateImageKHR fails every frame during DMA-BUF texture import on xe driver.

Error Log:
[0:25:57.656779590] [3017] DEBUG eGL egl.cpp:212 eglCreateImageKHR fail

Root Cause Identified:
IPU6 ISYS stride:    3904 bytes (ALIGN(3864, 64))
xe driver requirement: 4096 bytes (PAGE_SIZE aligned)
Difference:          192 bytes shortfall → import rejected
System Configuration (Verified)
GPU Drivers
0000:00:02.0 VGA compatible controller: Intel Corporation Alder Lake-P GT2 [Iris Xe Graphics]
    Kernel driver in use: xe

0000:03:00.0 Display controller: Intel Corporation DG2 [Arc A370M]
    Kernel driver in use: xe

Critical Finding: Both iGPU and dGPU use xe kernel driver → same 4096-byte stride requirement.
CMA Heap (Fixed)
# Verified after reboot with cma=128M boot parameter
drwxr-xr-x  2 root root     100 Aug 30 11:11 /dev/dma_heap/
crw-rw----  1 root video 252, 1 default_cma_region  ← CMA heap exists
crw-rw----  1 root video 252, 2 reserved           ← CMA heap exists
crw-rw----  1 root video 252, 0 system            ← System heap (fallback)
libcamera Environment
export LIBCAMERA_DMA_HEAP=/dev/dma_heap/default_cma_region
export LIBCAMERA_LOG_LEVELS="*:DEBUG"
export LIBCAMERA_SOFTISP_MODE=gpu
Investigation Timeline
Phase 1: Heap Allocation
Test	Result	Conclusion
CMA heap created via cma=128M	✅ PASS	Heap exists at boot
Permissions fixed (chmod 660)	✅ PASS	Non-root can open
Force LIBCAMERA_DMA_HEAP=/dev/dma_heap/default_cma_region	✅ PASS	libcamera allocates from CMA
eglCreateImageKHR with CMA buffers	❌ FAIL	Stride alignment still blocking

Finding: Heap selection is NOT the problem. Both CMA and system heaps have same stride issue.
Phase 2: iGPU vs dGPU Alignment
Claim	Verification	Verdict
iGPU uses i915 → 64-byte alignment	❌ False	Both GPUs use xe driver
xe requires 4096-byte stride	✅ Confirmed	Upstream xe_gem_import → xe_vm_bind enforces PAGE_SIZE alignment
LIBCAMERA_SOFTISP_MODE=cpu avoids problem	✅ True (but loses GPU accel)	Not acceptable per zero-copy priority
Phase 3: Module Parameters
Attempt	Result	Verdict
/etc/modprobe.d/ipu6_isys.conf with line_align=256	❌ Parameter doesn't exist	Discarded
modinfo intel_ipu6_isys -p	Shows: debug, fw_path, fw_name, poll_interval, reset_delay	No stride control via modparams

Finding: Cannot tune stride via module parameters — kernel source modification required.
Phase 4: Source Code Analysis
File	Location	Finding
ipu6-isys-queue.c	drivers/media/pci/intel/ipu6/	stride = ALIGN(stride, av->isys->line_align)
ipu6-isys.c	drivers/media/pci/intel/ipu6/	line_align set during pipeline init (likely value: 64)

Finding: line_align field is set internally at runtime. Changing it from 64 → 256 gives:
ALIGN(3864, 256) = 4096  ← satisfies xe driver
Options Considered & Discarded
Option	Description	Why Discarded	Priority Impact
A. Force i915 for iGPU	i915.force_probe=46a6 xe.force_probe=5693	Both GPUs need xe; reverting iGPU to legacy breaks consistency	Zero-copy ✗
B. CPU SoftISP (LIBCAMERA_SOFTISP_MODE=cpu)	Skip GPU entirely	Loses GPU acceleration; no zero-copy	Zero-copy ✗
C. Change capture resolution (1924×1092)	Alter cam command	Stride set by IPU6 ISYS driver, not capture dims	Zero-copy ✗
D. Modprobe parameter (line_align=256)	Add to /etc/modprobe.d/	Parameter doesn't exist in upstream	Zero-copy ✗
E. CPU staging buffer (libcamera patch)	Align in userspace	Requires CPU copy → defeats zero-copy	Zero-copy ✗
F. Keep system heap	Accept current state	eglCreateImageKHR still fails (3904 < 4096)	Zero-copy ✗
Final Recommendation (Accepted)

Option 1: Kernel Source Patch

Change line_align from 64 → 256 in drivers/media/pci/intel/ipu6/ipu6-isys.c.
Criterion	Assessment
Zero-copy achievable	✅ Yes (0 copies, native DMA-BUF path)
Effort	High (kernel rebuild + module install + test)
Risk	Low (isolated to IPU6 ISYS driver; 256 is standard alignment value)
Reversibility	High (revert patch, rebuild)
Future-proof	Medium (upstream may change; patch must be maintained)
Implementation Plan
Step 1: Locate line_align Assignment
# Find exact line
grep -rn "line_align\s*=" /usr/src/linux/drivers/media/pci/intel/ipu6/
# Expected: ipu6-isys.c or ipu6-isys-subdev.c
Step 2: Create Patch

File: drivers/media/pci/intel/ipu6/ipu6-isys.c (or -subdev.c)

Before:
isys->line_align = 64;

After:
isys->line_align = 256;
Step 3: Rebuild Module
cd /usr/src/linux-6.18.48-gentoo
make M=drivers/media/pci/intel/ipu6 modules
sudo make M=drivers/media/pci/intel/ipu6 modules_install
Step 4: Reload & Verify
# Reload module
sudo modprobe -r intel_ipu6_isys
sudo modprobe intel_ipu6_isys

# Check new stride in dmesg
dmesg | grep -i stride
# Expected: Stride 4096

# Test capture
export LIBCAMERA_DMA_HEAP=/dev/dma_heap/default_cma_region
export LIBCAMERA_LOG_LEVELS="*:DEBUG"
export LIBCAMERA_SOFTISP_MODE=gpu

cam -c 1 -C6 -F'/tmp/frame_zero_copy#.ppm' \
    -s role=viewfinder,width=1924,height=1092 \
    2>&1 | grep -i "eglCreateImage"
# Expected: NO failure messages
Step 5: Create Permanent udev Rule (For Heap Permissions)

File: /etc/udev/rules.d/99-dma-heaps.rules
# CMA heap permissions
KERNEL=="default_cma_region", MODE="0660", GROUP="video"
KERNEL=="reserved", MODE="0660", GROUP="video"

Apply:
sudo udevadm control --reload-rules
sudo udevadm trigger
Verification Criteria
Check	Command	Success Indicator
Stride alignment	dmesg | grep -i stride	Stride 4096
GPU import	cam ... 2>&1 | grep eglCreateImage	NO failure lines
Zero-copy confirmation	dmesg | grep -i "dma_buf|heap"	Allocation from default_cma_region, not system
Frame capture	ls -la /tmp/frame_zero_copy*.ppm	Files created (6.1MB per frame)
Risks & Mitigations
Risk	Likelihood	Impact	Mitigation
IPU6 firmware rejects 4096 stride	Low	Medium	Watch dmesg for errors; revert patch if corrupted frames
Kernel upgrade overwrites patch	High	Medium	Document patch for future rebuilds
Other drivers affected by xe change	Low	Low	Change isolated to IPU6 ISYS; xe unchanged
Permission regression on reboots	Medium	Low	udev rule installed permanently
Out-of-Scope Items (Discarded During Session)
Item	Reason
i915.force_probe vs xe.force_probe split	Both GPUs need consistent xe driver
V4L2 format negotiation	Already confirmed native 1932×1092 works
SoftISP shader debugging	Shaders compile and execute successfully
DmaBufAllocator heap selection	Confirmed CMA heap used when configured
Memory leak analysis	Not observed in logs
Pending Actions
Task	Owner	Status
Locate line_align assignment in kernel source	Engineer	Ready to start
Create patch (64 → 256)	Engineer	Next step
Rebuild intel_ipu6_isys module	Engineer	Pending patch
Reload module & test	Engineer	Pending rebuild
Verify zero-copy via dmesg logs	Engineer	Pending test
Install udev rule for heap permissions	Engineer	Post-test
References
Source	URL
IPU6 ISYS Queue (stride ALIGN)	drivers/media/pci/intel/ipu6/ipu6-isys-queue.c
xe driver DMA-BUF import	drivers/gpu/drm/xe/xe_gem.c → xe_vm_bind.c
CMA heap documentation	Documentation/admin-guide/dma-buf-heaps.rst
libcamera SoftISP (debayer_egl.cpp)	src/libcamera/ipa/softisp/debayer_egl.cpp
Session Conclusion

Decision: Proceed with kernel patch (Option 1) to achieve zero-copy.

Rationale: Only path that delivers true zero-copy (0 CPU copies between IPU6 and GPU).

Next Action: Execute Step 1 (locate line_align assignment) and report findings before applying patch.

