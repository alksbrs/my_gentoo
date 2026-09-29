#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/videodev2.h>
#include <drm/drm_fourcc.h>
#include <xf86drm.h>
#include <drm/i915_drm.h>

#define VIDEO_DEVICE "/dev/video8"
#define DRM_RENDER_DEVICE "/dev/dri/renderD129"

int main() {
    int cam_fd = -1;
    int drm_fd = -1;
    int dma_buf_fd = -1;
    struct v4l2_requestbuffers reqbuf;
    struct v4l2_buffer buf;
    struct v4l2_format fmt;
    void *map_addr;
    int ret;

    printf("=== IPU6 -> Arc A370M Zero-Copy Test (MMAP Export Path) ===\n");

    // 1. Open Camera
    cam_fd = open(VIDEO_DEVICE, O_RDWR);
    if (cam_fd < 0) {
        perror("ERROR: Could not open " VIDEO_DEVICE);
        return 1;
    }
    printf("[OK] Opened camera: %s\n", VIDEO_DEVICE);

    // 2. Set Format (BA10)
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = 1932;
    fmt.fmt.pix.height = 1092;
    fmt.fmt.pix.pixelformat = v4l2_fourcc('B', 'A', '1', '0');
    fmt.fmt.pix.field = V4L2_FIELD_NONE;
    fmt.fmt.pix.bytesperline = 4096;
    fmt.fmt.pix.sizeimage = 4476928;

    if (ioctl(cam_fd, VIDIOC_S_FMT, &fmt) < 0) {
        perror("WARNING: S_FMT failed (immutable). Proceeding.");
    }

    // 3. Request MMAP Buffers (This usually works when DMABUF fails)
    memset(&reqbuf, 0, sizeof(reqbuf));
    reqbuf.count = 2;
    reqbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    reqbuf.memory = V4L2_MEMORY_MMAP;

    if (ioctl(cam_fd, VIDIOC_REQBUFS, &reqbuf) < 0) {
        perror("ERROR: VIDIOC_REQBUFS (MMAP) failed");
        close(cam_fd);
        return 1;
    }
    printf("[OK] Requested %d MMAP buffers.\n", reqbuf.count);

    // 4. Queue and Stream ON
    for (int i = 0; i < reqbuf.count; i++) {
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;
        if (ioctl(cam_fd, VIDIOC_QBUF, &buf) < 0) {
            perror("ERROR: VIDIOC_QBUF (MMAP) failed");
            close(cam_fd);
            return 1;
        }
    }

    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (ioctl(cam_fd, VIDIOC_STREAMON, &type) < 0) {
        perror("ERROR: VIDIOC_STREAMON failed");
        close(cam_fd);
        return 1;
    }
    printf("[OK] Streaming started.\n");

    // 5. Dequeue a buffer
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index = 0;
    if (ioctl(cam_fd, VIDIOC_DQBUF, &buf) < 0) {
        perror("ERROR: VIDIOC_DQBUF failed");
        close(cam_fd);
        return 1;
    }
    printf("[OK] Captured frame (MMAP). Index: %d\n", buf.index);

    // 6. EXPORT MMAP buffer to DMA-BUF FD (The Critical Step)
    struct v4l2_exportbuffer expbuf;
    memset(&expbuf, 0, sizeof(expbuf));
    expbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    expbuf.index = 0;
    expbuf.flags = O_RDONLY; // Read-only for GPU

    if (ioctl(cam_fd, VIDIOC_EXPBUF, &expbuf) < 0) {
        perror("ERROR: VIDIOC_EXPBUF failed (Export not supported?)");
        close(cam_fd);
        return 1;
    }

    dma_buf_fd = expbuf.fd;
    printf("[OK] Exported DMA-BUF FD: %d (Size: %d bytes)\n", dma_buf_fd, buf.bytesused);

    // 7. Open Arc GPU
    drm_fd = open(DRM_RENDER_DEVICE, O_RDWR);
    if (drm_fd < 0) {
        perror("ERROR: Could not open " DRM_RENDER_DEVICE);
        close(cam_fd);
        close(dma_buf_fd);
        return 1;
    }
    printf("[OK] Opened GPU: %s\n", DRM_RENDER_DEVICE);

    // 8. Import DMA-BUF into GPU
    struct drm_prime_handle prime_import = {
        .fd = dma_buf_fd,
        .flags = DRM_CLOEXEC,
        .handle = 0
    };

    ret = ioctl(drm_fd, DRM_IOCTL_PRIME_FD_TO_HANDLE, &prime_import);
    if (ret != 0) {
        perror("ERROR: DRM_IOCTL_PRIME_FD_TO_HANDLE failed");
        close(cam_fd);
        close(drm_fd);
        close(dma_buf_fd);
        return 1;
    }

    printf("\n*** SUCCESS: Zero-copy import successful! ***\n");
    printf("  - Camera FD: %d\n", dma_buf_fd);
    printf("  - GPU Handle: %u\n", prime_import.handle);
    printf("  - Method: MMAP -> Export -> Import (Zero-Copy Verified)\n");

    // Cleanup
    ioctl(drm_fd, DRM_IOCTL_GEM_CLOSE, &prime_import.handle);
    close(drm_fd);
    close(dma_buf_fd);
    ioctl(cam_fd, VIDIOC_STREAMOFF, &type);
    close(cam_fd);

    return 0;
}
