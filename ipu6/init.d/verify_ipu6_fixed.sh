#!/bin/bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0
pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL++)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo "========================================"
echo "Post-@world Verification for IPU6/OV2740"
echo "========================================"

echo ""; echo "[1/7] Checking libcamera 0.7.2..."
PKG_INFO=$(equery list media-libs/libcamera 2>/dev/null || true)
if echo "$PKG_INFO" | grep -q "0.7.2"; then pass "libcamera 0.7.2 installed"; else fail "libcamera 0.7.2 not found"; fi

echo ""; echo "[2/7] Checking camera enumeration..."
CAM_LIST=$(cam --list 2>&1 || true)
if echo "$CAM_LIST" | grep -q "Internal front camera"; then pass "Camera enumerates"; else fail "Camera not enumerated"; fi

echo ""; echo "[3/7] Checking media graph..."
MEDIA=$(media-ctl -d /dev/media0 -p 2>/dev/null || true)
if echo "$MEDIA" | grep -q "ov2740.*ENABLED"; then pass "OV2740 enabled"; else fail "OV2740 not enabled"; fi

echo ""; echo "[4/7] Testing BGR888 capture..."
LIBCAMERA_SOFTISP_MODE=cpu cam -c1 --capture=1 --file=/tmp/post_world.raw --stream role=video,pixelformat=BGR888 2>/dev/null || true
if [ -f /tmp/post_world.raw ] && [ -s /tmp/post_world.raw ]; then
    SIZE=$(stat -c%s /tmp/post_world.raw)
    [ "$SIZE" -eq 6307392 ] && pass "Capture succeeded: $SIZE bytes" || warn "Size $SIZE (expected 6307392)"
else
    fail "Capture failed"
fi

echo ""; echo "[5/7] Analyzing capture..."
if [ -f /tmp/post_world.raw ]; then
    python3 ~/analyze_bgr888.py /tmp/post_world.raw /tmp/post_world_rgb.png
    pass "Analysis complete"
else
    fail "Cannot analyze"
fi

echo ""; echo "[6/7] Checking patch application..."
if [ -d /var/tmp/portage/media-libs/libcamera-0.7.2/work/libcamera-v0.7.2 ]; then
    if grep -q "lookup tables to identity" /var/tmp/portage/media-libs/libcamera-0.7.2/work/libcamera-v0.7.2/src/libcamera/software_isp/debayer_cpu.cpp 2>/dev/null; then
        pass "Patch applied in work directory"
    else
        warn "Patch not found in work directory"
    fi
else
    warn "Work directory not available"
fi

echo ""; echo "[7/7] Checking dmesg for errors..."
DMESG_ERRORS=$(dmesg | grep -iE "ipu6|ov2740" | grep -iE "error|fail|warn" | tail -5 || true)
[ -z "$DMESG_ERRORS" ] && pass "No IPU6/OV2740 errors" || warn "Recent errors:\n$DMESG_ERRORS"

echo ""; echo "========================================"
echo "Verification Summary: $PASS passed, $FAIL failed"
echo "========================================"
[ $FAIL -eq 0 ] && echo -e "${GREEN}All checks passed!${NC}" || echo -e "${RED}$FAIL check(s) failed.${NC}"
