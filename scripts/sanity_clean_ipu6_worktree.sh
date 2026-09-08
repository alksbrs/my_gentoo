#!/bin/bash
# IPU6 libcamera pre-compile sanity/cleanup script
# Checks for stray .orig/.rej/.bak files left over from patch application
# in the portage WORK tree (transient, safe to delete) — and separately
# flags (never deletes) any .bak_* files in the local overlay files/
# directory, which are intentional backups managed by
# backup_ipu6_session.sh.
#
# Default mode: report only. Pass --clean to actually delete.


# Auto-elevate: this script operates on portage-owned (0700 root/portage)
# paths that are unreadable by a regular user. Re-exec under sudo if not
# already running as root, so the caller never has to remember to prefix
# sudo manually.
if [ "$(id -u)" -ne 0 ]; then
    exec sudo "$0" "$@"
fi
set -o pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

WORK_ROOT="/var/tmp/portage/media-libs/libcamera-0.7.2/work"
OVERLAY_FILES_DIR="/var/db/repos/local/media-libs/libcamera/files"

CLEAN=0
if [ "$1" == "--clean" ]; then
    CLEAN=1
fi

echo "========================================"
echo "IPU6 libcamera Pre-Compile Sanity Check"
echo "========================================"
echo ""

if [ ! -d "${WORK_ROOT}" ]; then
    echo -e "${YELLOW}[WARN]${NC} Work tree not found at ${WORK_ROOT}"
    echo "       (nothing unpacked yet — run 'ebuild ... unpack' first, or this is expected pre-unpack)"
    exit 0
fi

echo "[1/3] Scanning work tree for stray .orig/.rej/.bak files..."
echo "      Root: ${WORK_ROOT}"
echo ""

mapfile -t stray_files < <(find "${WORK_ROOT}" -type f \( -name "*.orig" -o -name "*.rej" -o -name "*.bak" \) 2>/dev/null)

if [ ${#stray_files[@]} -eq 0 ]; then
    echo -e "${GREEN}[PASS]${NC} No stray .orig/.rej/.bak files found in work tree."
else
    echo -e "${YELLOW}[WARN]${NC} Found ${#stray_files[@]} stray file(s) in work tree:"
    for f in "${stray_files[@]}"; do
        echo "    $f"
    done
fi

echo ""
echo "[2/3] Checking overlay files/ directory (informational only — NEVER deleted by this script)..."
echo "      Root: ${OVERLAY_FILES_DIR}"
echo ""

if [ -d "${OVERLAY_FILES_DIR}" ]; then
    mapfile -t overlay_baks < <(find "${OVERLAY_FILES_DIR}" -maxdepth 1 -type f -name "*.bak_*" 2>/dev/null)
    if [ ${#overlay_baks[@]} -eq 0 ]; then
        echo -e "${GREEN}[PASS]${NC} No .bak_* files in overlay files/ directory."
    else
        echo -e "${GREEN}[INFO]${NC} ${#overlay_baks[@]} intentional .bak_* backup(s) present in overlay files/ (untouched):"
        for f in "${overlay_baks[@]}"; do
            echo "    $f"
        done
    fi
else
    echo -e "${YELLOW}[WARN]${NC} Overlay files/ directory not found at ${OVERLAY_FILES_DIR}"
fi

echo ""
echo "[3/3] Cleanup..."

if [ ${#stray_files[@]} -eq 0 ]; then
    echo -e "${GREEN}[PASS]${NC} Nothing to clean."
    echo ""
    echo "========================================"
    echo "Sanity check complete: work tree is clean."
    echo "========================================"
    exit 0
fi

if [ ${CLEAN} -eq 0 ]; then
    echo -e "${YELLOW}[DRY-RUN]${NC} ${#stray_files[@]} file(s) would be deleted."
    echo "          Re-run with --clean to actually delete them:"
    echo "          $0 --clean"
    echo ""
    echo "========================================"
    echo "Sanity check complete: cleanup NOT performed (dry-run)."
    echo "========================================"
    exit 2
fi

echo "Deleting ${#stray_files[@]} stray file(s)..."
for f in "${stray_files[@]}"; do
    rm --verbose "$f"
done

echo ""
echo "Verifying cleanup..."
remaining=$(find "${WORK_ROOT}" -type f \( -name "*.orig" -o -name "*.rej" -o -name "*.bak" \) 2>/dev/null | wc -l)

if [ "${remaining}" -eq 0 ]; then
    echo -e "${GREEN}[PASS]${NC} Confirmed via find: 0 stray .orig/.rej/.bak files remain."
    echo ""
    echo "========================================"
    echo "Sanity check complete: work tree cleaned."
    echo "========================================"
    exit 0
else
    echo -e "${RED}[FAIL]${NC} ${remaining} stray file(s) still present after cleanup — investigate manually."
    echo ""
    echo "========================================"
    echo "Sanity check complete: cleanup INCOMPLETE."
    echo "========================================"
    exit 1
fi
