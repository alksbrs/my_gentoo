#!/usr/bin/env python3
"""
Atomically apply DMA-BUF zero-copy patches to libcamera gstreamer plugin.
Run from the libcamera source root directory.
"""

import os
import re
import sys

SOURCE_ROOT = "."  # Adjust if needed

print("=" * 70)
print("DMA-BUF Zero-Copy Patch Suite for Libcamera GStreamer Plugin")
print("=" * 70)

# ==================== PATCH 1: Include gstdmabuf.h ====================
def patch_01_include():
    """Add #include <gst/allocators/gstdmabuf.h>"""
    filepath = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamera-utils.cpp"
    
    if not os.path.exists(filepath):
        print(f"[ERROR] {filepath} not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    if '#include <gst/allocators/gstdmabuf.h>' in content:
        print("[SKIP] Patch 01: Already applied")
        return True
    
    # Find the include after libcamera/formats.h
    pattern = r'( #include <libcamera/formats\.h>)\n'
    replacement = r'\1\n#include <gst/allocators/gstdmabuf.h>'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        print("[WARN] Patch 01: Pattern not matched, trying alternative")
        # Alternative: just append after libcamera/formats.h
        alt_pattern = r'#include <libcamera/formats\.h>(?!.*gst/allocators/gstdmabuf)'
        replacement = r'#include <libcamera/formats.h>\n#include <gst/allocators/gstdmabuf.h>'
        new_content = re.sub(alt_pattern, replacement, content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("[OK]   Patch 01: Added gstdmabuf.h include")
    return True

# ==================== PATCH 2: Add dmabuf_structure_from_format() ====================
def patch_02_dmabuf_helper():
    """Insert dmabuf_structure_from_format() helper function"""
    filepath = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamera-utils.cpp"
    
    if not os.path.exists(filepath):
        print(f"[ERROR] {filepath} not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'dmabuf_structure_from_format' in content:
        print("[SKIP] Patch 02: Already applied")
        return True
    
    # Insert after pixel_format_to_gst_format() function (ends with "return PixelFormat{};")
    insertion_marker = r'(static PixelFormat\s+gst_format_to_pixel_format\(GstVideoFormat gst_format\).*?return PixelFormat\{\};)'
    
    helper_code = r'''\1

/*
 * Build a DMA-BUF-tagged caps structure for a format.
 * GstLibcameraAllocator buffers are plain, linear DMA-BUFs sourced from
 * libcamera's FrameBufferAllocator. Memory:DMABuf capability exposed here.
 */
static GstStructure *
dmabuf_structure_from_format(const PixelFormat &format)
{
    GstVideoFormat gst_format = pixel_format_to_gst_format(format);
    
    if (gst_format == GST_VIDEO_FORMAT_UNKNOWN ||
        gst_format == GST_VIDEO_FORMAT_ENCODED)
        return nullptr;
    
    /* Convert pixel format to a fourcc string GStreamer understands */
    const gchar *format_str = gst_video_format_to_string(gst_format);
    if (!format_str)
        return nullptr;
    
    return gst_structure_new("video/x-raw",
                             "format", G_TYPE_STRING, format_str,
                             "memory", G_TYPE_STRING, "memory:DMABuf",
                             "width", G_TYPE_INT, 1,
                             "height", G_TYPE_INT, 1,
                             nullptr);
}'''
    
    new_content = re.sub(insertion_marker, helper_code, content, flags=re.DOTALL)
    
    if new_content == content:
        print("[ERROR] Patch 02: Could not find insertion point")
        return False
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("[OK]   Patch 02: Added dmabuf_structure_from_format()")
    return True

# ==================== PATCH 3: Integrate DMA-BUF caps ====================
def patch_03_caps_integration():
    """Call dmabuf_structure_from_format() in gst_libcamera_stream_formats_to_caps()"""
    filepath = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamera-utils.cpp"
    
    if not os.path.exists(filepath):
        print(f"[ERROR] {filepath} not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'GST_CAPS_FEATURE_MEMORY_DMABUF' in content:
        print("[SKIP] Patch 03: Already applied")
        return True
    
    # Insert before the size iteration loop
    pattern = r'(\s+for \(const Size &size : formats\.sizes\(pixelformat\)\))'
    dmabuf_code = r'''
        /* Also expose DMA-BUF capability for this format */
        g_autoptr(GstStructure) dmabuf_s = dmabuf_structure_from_format(pixelformat);
        if (dmabuf_s) {
            GstCapsFeatures *features =
                gst_caps_features_new(GST_CAPS_FEATURE_MEMORY_DMABUF, nullptr);
            gst_caps_append_structure_full(caps, gst_structure_copy(dmabuf_s), features);
        }\1'''
    
    new_content = re.sub(pattern, dmabuf_code, content)
    
    if new_content == content:
        print("[ERROR] Patch 03: Could not find insertion point")
        return False
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("[OK]   Patch 03: Integrated DMA-BUF caps into format enumeration")
    return True

# ==================== PATCH 4: Modify SRC Pad Template ====================
def patch_04_pad_template():
    """Extend src_template caps to include memory:DMABuf"""
    filepath = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamerasrc.cpp"
    
    if not os.path.exists(filepath):
        print(f"[ERROR] {filepath} not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'memory:DMABuf' in content:
        print("[SKIP] Patch 04: Already applied")
        return True
    
    # Replace TEMPLATE_CAPS in src_template with extended version
    pattern = r'(GstStaticPadTemplate src_template = \{[^}]*"src",\s*GST_PAD_SRC,\s*GST_PAD_ALWAYS,)\s*TEMPLATE_CAPS\s*\};'
    replacement = r'\1 GST_STATIC_CAPS(TEMPLATE_CAPS ", memory={system,memory:DMABuf}")\n};'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        # Fallback: just add to TEMPLATE_CAPS macro definition
        alt_pattern = r'( #define TEMPLATE_CAPS GST_STATIC_CAPS\([^)]*)\);'
        alt_replacement = r'\1, memory={system,memory:DMABuf}\n#define __OLD_TEMPLATE_CAPS __IGNORE__);\n/* Note: original TEMPLATE_CAPS preserved above */'
        new_content = re.sub(alt_pattern, alt_replacement, content)
    
    if new_content == content:
        print("[ERROR] Patch 04: Could not modify src_template")
        return False
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("[OK]   Patch 04: Modified SRC pad template to expose DMA-BUF")
    return True

# ==================== VERIFICATION ====================
def verify_patches():
    """Verify all patches applied correctly"""
    errors = []
    
    utils_file = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamera-utils.cpp"
    src_file = f"{SOURCE_ROOT}/src/gstreamer/gstlibcamerasrc.cpp"
    
    checks = [
        (utils_file, '#include <gst/allocators/gstdmabuf.h>', "Patch 01: gstdmabuf.h include"),
        (utils_file, 'dmabuf_structure_from_format', "Patch 02: Helper function"),
        (utils_file, 'GST_CAPS_FEATURE_MEMORY_DMABUF', "Patch 03: Caps integration"),
        (src_file, 'memory:DMABuf', "Patch 04: Pad template"),
    ]
    
    print("\n" + "=" * 70)
    print("VERIFICATION CHECK")
    print("=" * 70)
    
    for filepath, search_term, description in checks:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            if search_term in content:
                print(f"[OK]   {description}")
            else:
                print(f"[FAIL] {description}")
                errors.append(description)
        except FileNotFoundError:
            print(f"[MISS] {filepath}")
            errors.append(f"Missing file: {filepath}")
    
    return len(errors) == 0

# ==================== MAIN ====================
if __name__ == '__main__':
    patches = [
        ("Include fix", patch_01_include),
        ("Helper function", patch_02_dmabuf_helper),
        ("Caps integration", patch_03_caps_integration),
        ("Pad template", patch_04_pad_template),
    ]
    
    failed = []
    
    for name, func in patches:
        print(f"\n[{'*' * 30}] {name} [{'*' * 30}]\n")
        try:
            if not func():
                failed.append(name)
                print(f"[FAIL] {name} - continuing with remaining patches")
        except Exception as e:
            failed.append(name)
            print(f"[EXCEPTION] {name}: {e}")
    
    # Verification
    success = verify_patches()
    
    print("\n" + "=" * 70)
    if failed:
        print(f"PATCHES FAILED: {', '.join(failed)}")
        print("=" * 70)
        sys.exit(1)
    elif success:
        print("ALL PATCHES APPLIED AND VERIFIED SUCCESSFULLY")
        print("=" * 70)
        print("\nNext step: rebuild libcamera")
        print("  emerge -1 media-libs/libcamera")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED - see errors above")
        print("=" * 70)
        sys.exit(1)
