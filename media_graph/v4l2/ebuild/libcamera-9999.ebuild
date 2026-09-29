# Copyright 2025-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..14} )

inherit git-r3 meson

DESCRIPTION="Complex camera support library"
HOMEPAGE="https://libcamera.org"
EGIT_REPO_URI="https://gitlab.freedesktop.org/camera/libcamera.git/"
EGIT_BRANCH="master"
EGIT_CLONE_TYPE="single"
EGIT_COMMIT="v0.7.2"


S="${WORKDIR}/libcamera-${PV}"

LICENSE="Apache-2.0 CC0-1.0 BSD BSD-2 CC-BY-4.0 CC-BY-SA-4.0 GPL-2+ GPL-2 LGPL-2.1+ MIT"




SLOT="0/${PV}"
KEYWORDS="amd64 arm arm64 ~riscv x86"
IUSE="drm elfutils gstreamer gui jpeg openssl sdl test tiff tools trace +udev unwind v4l"
RESTRICT="
	!test? ( test )
"

PATCHES=(
	"${FILESDIR}/agc.h.patch"
	"${FILESDIR}/agc.cpp.patch"
	"${FILESDIR}/bayer-r10p-scale-fix.patch"
	"${FILESDIR}/egl-r16-import.patch"
)

DEPEND="dev-libs/libyaml:= media-libs/mesa[egl(+),gles2(+)] sys-apps/kmod sys-libs/libcap virtual/libudev:= drm? ( x11-libs/libdrm ) elfutils? ( dev-libs/elfutils ) gstreamer? ( media-libs/gstreamer:1.0 media-libs/gst-plugins-base:1.0 ) jpeg? ( media-libs/libjpeg-turbo:= ) openssl? ( dev-libs/openssl:= ) sdl? ( media-libs/libsdl2 ) trace? ( dev-util/lttng-ust:= ) unwind? ( sys-libs/libunwind:= ) udev? ( virtual/libudev:= )"
RDEPEND="${DEPEND}"
BDEPEND="dev-build/meson dev-python/ply virtual/pkgconfig"

src_configure() {
	local emesonargs=(
		-Dbuildtype=plain -Ddocumentation=disabled -Dpycamera=disabled
		-Dpipelines=simple,uvcvideo,vimc
		-Dipas=simple
		-Dlc-compliance=disabled
		$(meson_feature gstreamer) $(meson_feature trace tracing)
		$(meson_feature unwind libunwind) $(meson_feature elfutils libdw)
		$(meson_feature udev) $(meson_feature v4l v4l2)
		$(meson_use test) -Dqcam=disabled -Dsoftisp-gpu=enabled
	)
	meson_src_configure
}
