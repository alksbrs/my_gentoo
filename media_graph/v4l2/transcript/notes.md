# Media Graph manual configuration

The pipeline is to be configured as:

Sensor: ov2740 -> CSI2 1 (Enabled, Immutable).
CSI2 1: Format SGRBG10_1X10/1932x1092.
Link: CSI2 1 -> Capture 8 (Enabled).
V4L2 Node: /dev/video8 set to BA10 (10-bit Bayer).


aleksei:~ media-ctl -d /dev/media0 -r

aleksei:~ media-ctl -d /dev/media0 -l '"ov2740 10-0036":0 -> "Intel IPU6 CSI2 1":0 [1]'
aleksei:~ media-ctl -d /dev/media0 -V '"Intel IPU6 CSI2 1":0 [fmt:SRGGB10_1X10/1932x1092]'

## Enable the link from CSI2 1 (pad 1) to Capture 8 (pad 0)
media-ctl -d /dev/media0 -l '"Intel IPU6 CSI2 1":1 -> "Intel IPU6 ISYS Capture 8":0 [1]'

## Set CSI2 1 Sink format to match Sensor (SGRBG10)
media-ctl -d /dev/media0 -V '"Intel IPU6 CSI2 1":0 [fmt:SGRBG10_1X10/1932x1092]'
## Verify the link is enabled
media-ctl -d /dev/media0 -p | grep -A 2 "CSI2 1" | grep "Capture 8"




aleksei:~ media-ctl -d /dev/media0 -p | grep -A 5 "ov2740"
		<- "ov2740 10-0036":0 [ENABLED,IMMUTABLE]
	pad1: SOURCE
		[stream:0 fmt:SRGGB10_1X10/1932x1092 field:none
		crop.bounds:(0,0)/1932x1092
		crop:(0,0)/1932x1092]
		-> "Intel IPU6 ISYS Capture 8":0 []
--
- entity 233: ov2740 10-0036 (1 pad, 1 link, 0 routes)
              type V4L2 subdev subtype Sensor flags 0
              device node name /dev/v4l-subdev4
	pad0: SOURCE
		[stream:0 fmt:SGRBG10_1X10/1932x1092 field:none]
		-> "Intel IPU6 CSI2 1":0 [ENABLED,IMMUTABLE]

## Atuomatic negotiation of 'RG10' bus format is not what we need

aleksei:~ v4l2-ctl --device=/dev/video8 --get-fmt-video
Format Video Capture:
	Width/Height      : 1932/1092
	Pixel Format      : 'RG10' (10-bit Bayer RGRG/GBGB)
	Field             : None
	Bytes per Line    : 4096
	Size Image        : 4476928
	Colorspace        : Raw
	Transfer Function : Default (maps to None)
	YCbCr/HSV Encoding: Default (maps to ITU-R 601)
	Quantization      : Default (maps to Full Range)
	Flags             : 

## Set 'BA10' bus format and confirm

aleksei:~ v4l2-ctl --device=/dev/video8 --set-fmt-video=width=1932,height=1092,pixelformat=BA10

aleksei:~ v4l2-ctl --device=/dev/video8 --get-fmt-video
Format Video Capture:
	Width/Height      : 1932/1092
	Pixel Format      : 'BA10' (10-bit Bayer GRGR/BGBG)
	Field             : None
	Bytes per Line    : 4096
	Size Image        : 4476928
	Colorspace        : Raw
	Transfer Function : Default (maps to None)
	YCbCr/HSV Encoding: Default (maps to ITU-R 601)
	Quantization      : Default (maps to Full Range)
	Flags             : 
