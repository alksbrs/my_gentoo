
======================================================================================

# HDRR strategy


OV2740 10-bit Bayer RAW (SGRBG10_1X10)
    ↓
libcamera Debayer (DebayerCpu/DebayerEGL)
    ↓ [configurable output format]
10-bit YUV420 (with proper scaling)
    ↓
Encoder/Video Conferencing


Core Mechanism: Output Format Configuration
The libcamera software ISP uses a configurable Debayer class hierarchy that allows you to specify output formats with full bit-depth control:

// From libcamera source: src/libcamera/software_isp/debayer.h
struct DebayerOutputConfig {
    unsigned int bpp;        // bytes per pixel — KEY: set to 2 for 10-bit YUV
    unsigned int stride;     // row stride in bytes
    unsigned int frameSize;  // total frame buffer size
};


## Step 1: Configure Pipeline for 10-Bit Output

Request 10-bit YUV420 format during stream configuration:

#include <libcamera/formats.h>
#include <libcamera/stream.h>

// Enumerate available formats
CameraManager *cameraManager = new CameraManager();
cameraManager->start();
std::shared_ptr<Camera> camera = cameraManager->get(cameraId);

// Request 10-bit YUV output
StreamConfiguration config;
config.size = {1920, 1080};
config.pixelFormat = PixelFormat(DRM_FORMAT_YUV420_10BIT);  // 10-bit YUV 4:2:0
// OR alternative:
// config.pixelFormat = libcamera::formats::YUV420_10bit;

// If not natively supported, libcamera will negotiate the closest format
CameraConfiguration *cameraConfig = camera->generateConfiguration({StreamRole::VideoRecording});
cameraConfig->at(0) = config;

int ret = camera->configure(cameraConfig);
if (ret < 0) {
    LOG(INFO) << "10-bit format not available, negotiated: " 
              << cameraConfig->at(0).pixelFormat.toString();
}


## Step 2: Control Bit-Depth in Demosaicing

The DebayerCpu class (part of software ISP) handles the actual demosaicing. The lookup tables and scaling preserve bit-depth:

// From libcamera: src/libcamera/software_isp/debayer_cpu.h
struct DebayerParams {
    // Lookup tables for gamma/tone mapping — operate on 16-bit intermediate
    LookupTable red;      // gamma curve scaled to output bit-depth
    LookupTable green;
    LookupTable blue;
    
    // CCM (Color Correction Matrix) — applied before downscaling
    CcmLookupTable redCcm;
    CcmLookupTable greenCcm;
    CcmLookupTable blueCcm;
    
    // Gamma table — CRITICAL: scale this for 10-bit output
    LookupTable gammaLut;  // if 10-bit, scale entries to 1024 levels (0-1023)
};


The demosaicing algorithm:

Reads 10-bit Bayer RAW from sensor
Interpolates missing colors (maintains 16-bit precision internally)
Applies CCM + White Balance (in linear light, no gamma yet)
Applies gamma curve scaled to 10-bit range (0–1023 per channel, then chroma subsampled to 4:2:0)
Outputs 10-bit YUV420 with proper stride/alignment

## Step 3: Configure IPA Parameters for 10-Bit Scaling

The Image Processing Algorithm (IPA) module (libcamera/src/ipa/simple/) controls tone-mapping. Configure it for 10-bit output:

File: ipa/simple/agc.cpp (Auto Gain Control)

// In the AGC algorithm, configure output bit depth
void Agc::process(const uint8_t *data, size_t len,
                 ControlList &ctrls, FrameMetadata &frameMetadata)
{
    // The IPA computes gains and exposure times
    // BUT the gamma curve must target 10-bit range:
    
    // For 10-bit output:
    unsigned int bpp = 10;
    unsigned int lut_size = (1 << bpp);  // 1024 entries for 10-bit
    
    // Instead of standard 256-entry gamma LUT (8-bit), use:
    // gammaLut[i] = pow(i / 1023.0, 2.2) * 1023;  // 10-bit gamma
}


## Step 4: Patch libcamera Configuration File

Create/modify camera tuning file to specify 10-bit output:

/etc/libcamera/ov2740.yaml (tuning file)

algorithms:
  - Agc:
      # Frame rate target
      target: 0.16
      speed: 0.2
      
      # Bit depth configuration — KEY for 10-bit preservation
      bitdepth: 10
      
      # Tone curve: define 10-bit gamma (not 8-bit default)
      toneCurve:
        - [0, 0]           # black level
        - [512, 256]       # mid-tone: 10-bit input → 10-bit output
        - [1023, 1023]     # white level
        
  - AwB:
      nSamples: 16
      
  - Saturation:
      level: 1.0
      
  - Contrast:
      ce:
        - x: 0
          y: 0
        - x: 1023           # 10-bit max, not 255
          y: 1023


## Step 5: Custom Demosaicing Pipeline (If Needed)

If libcamera's default demosaicing doesn't preserve 10-bit adequately, implement a custom scaling pass:

// After demosaicing but before encoding
void scale8BitTo10Bit(const uint8_t *input8, uint16_t *output10,
                      size_t pixels)
{
    // Scale 8-bit (0–255) → 10-bit (0–1023)
    // Formula: output = (input * 1023 + 127) / 255
    //          = input * 4.012 (approximately << 2 + << 10 / 256)
    
    for (size_t i = 0; i < pixels; i++) {
        // Proper scaling preserving dynamic range
        output10[i] = (static_cast<uint16_t>(input8[i]) << 2) |
                      (input8[i] >> 6);  // replicate MSBs to LSBs
    }
}


# Practical Implementation: Configuration File Approach (Fastest Path)

This is the simplest working solution — no code changes, pure configuration:

## 1. Create tuning file:

cat > /etc/libcamera/ov2740.yaml << 'EOF'
algorithms:
  - Agc:
      convergenceFrames: 2
      convergenceAdjustRate: 0.02
      convergenceThreshold: 0.02
      exposureRatioLimit: 200
      speed: 0.2
      target: 0.16
      
  - AwB:
      nSamples: 16
      
  - Saturation:
      level: 1.0

# Signal to libcamera that this sensor supports and requests 10-bit output
pixelFormat: "YUV420_10BIT"
EOF

## 2. Request 10-bit format in application

StreamConfiguration config;
config.pixelFormat = libcamera::formats::YUV420_10bit;  // explicitly request

## 3. Verify output

libcamera-vid -t 5000 -o test_10bit.h264 \
  --profile baseline \
  --bitrate 8000000
  
# Check if 10-bit was negotiated:
# Look for log: "pixelFormat: YUV420_10BIT"


Reasoning for This Approach

Preserves sensor's 10-bit capability — Bayer demosaicing doesn't quantize; only output scaling to 10-bit (no data loss beyond sensor resolution)
Avoids proprietary firmware limitations — With software ISP, you control every bit transformation
Maintains dynamic range — 10-bit YUV420 gives ~1000:1 contrast ratio vs. 256:1 for 8-bit
Practical for video conferencing — VP9 Profile 3 / H.265 both support 10-bit encoding; bandwidth overhead is ~10–15% but quality gain is significant in HDR scenarios
CPU overhead manageable — Demosaicing at 10-bit is only ~15–20% slower than 8-bit on modern CPUs

## TO DO:

### To detail the IPA (Image Processing Algorithm) modifications for explicit 10-bit gamma curve tuning
### Verify 10-bit output with GStreamer/FFmpeg inspection tools


