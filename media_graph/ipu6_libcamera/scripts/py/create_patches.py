#!/usr/bin/env python3
import os

OVERLAY = "/var/db/repos/local/media-libs/libcamera/files"

patches = {
    "libcamera-9999-softisp-adjust-yaml.patch": r'''From: libcamera softisp adjust YAML tuning <user@local>
Date: Mon, 25 Aug 2026 00:00:00 +0000
Subject: [PATCH] softisp: adjust: Read gamma/contrast/saturation from YAML

---
 a/src/ipa/softisp/algorithms/adjust.cpp
+++ b/src/ipa/softisp/algorithms/adjust.cpp
@@ -19,20 +19,27 @@
 
 namespace ipa::softisp::algorithms {
 
-constexpr float kDefaultContrast = 1.0f;
-constexpr float kDefaultSaturation = 1.0f;
-
 LOG_DEFINE_CATEGORY(IPASoftIspAdjust)
 
-int Adjust::init(IPAContext &context, [[maybe_unused]] const ValueNode &tuningData)
+int Adjust::init(IPAContext &context, const ValueNode &tuningData)
 {
+	defaultGamma_ = tuningData["gamma"].get<float>().value_or(kDefaultGamma);
+	defaultContrast_ = tuningData["contrast"].get<float>().value_or(1.0f);
+	defaultSaturation_ = tuningData["saturation"].get<float>().value_or(1.0f);
+
 	context.ctrlMap[&controls::Gamma] =
-		ControlInfo(0.1f, 10.0f, kDefaultGamma);
+		ControlInfo(0.1f, 10.0f, defaultGamma_);
 	context.ctrlMap[&controls::Contrast] =
-		ControlInfo(0.0f, 2.0f, kDefaultContrast);
+		ControlInfo(0.0f, 2.0f, defaultContrast_);
 	if (context.ccmEnabled)
 		context.ctrlMap[&controls::Saturation] =
-			ControlInfo(0.0f, 2.0f, kDefaultSaturation);
+			ControlInfo(0.0f, 2.0f, defaultSaturation_);
+
+	LOG(IPASoftIspAdjust, Debug)
+		<< "Adjust: gamma " << defaultGamma_
+		<< ", contrast " << defaultContrast_
+		<< ", saturation " << defaultSaturation_;
+
 	return 0;
 }
 
@@ -40,8 +47,8 @@
 		      [[maybe_unused]] const IPAConfigInfo &configInfo)
 {
 	context.activeState.knobs.gamma = kDefaultGamma;
-	context.activeState.knobs.contrast = std::optional<float>();
-	context.activeState.knobs.saturation = std::optional<float>();
+	context.activeState.knobs.contrast = defaultContrast_;
+	context.activeState.knobs.saturation = defaultSaturation_;
 
 	return 0;
 }
@@ -59,13 +66,13 @@
 
 	const auto &contrast = controls.get(controls::Contrast);
 	if (contrast.has_value()) {
-		context.activeState.knobs.contrast = contrast;
+		context.activeState.knobs.contrast = contrast.value();
 		LOG(IPASoftIspAdjust, Debug) << "Setting contrast to " << contrast.value();
 	}
 
 	const auto &saturation = controls.get(controls::Saturation);
 	if (saturation.has_value()) {
-		context.activeState.knobs.saturation = saturation;
+		context.activeState.knobs.saturation = saturation.value();
 		LOG(IPASoftIspAdjust, Debug) << "Setting saturation to " << saturation.value();
 	}
 }
@@ -100,15 +107,15 @@
 	frameContext.gamma = context.activeState.knobs.gamma;
 	frameContext.contrast = context.activeState.knobs.contrast;
 
-	auto &saturation = context.activeState.knobs.saturation;
-	if (context.ccmEnabled && saturation) {
-		applySaturation(context.activeState.combinedMatrix, saturation.value());
+	const float saturation = context.activeState.knobs.saturation;
+	if (context.ccmEnabled) {
+		applySaturation(context.activeState.combinedMatrix, saturation);
 		frameContext.saturation = saturation;
 	}
 
 	params->gamma = 1.0 / context.activeState.knobs.gamma;
-	const float contrast = context.activeState.knobs.contrast.value_or(kDefaultContrast);
-	params->contrastExp = tan(std::clamp(contrast * M_PI_4, 0.0, M_PI_2 - 0.00001));
+	params->contrastExp = tan(std::clamp(context.activeState.knobs.contrast * M_PI_4,
+						     0.0, M_PI_2 - 0.00001));
 }
 
 void Adjust::process([[maybe_unused]] IPAContext &context,
@@ -117,14 +124,9 @@
 		     [[maybe_unused]] const SwIspStats *stats,
 		     ControlList &metadata)
 {
-	const auto &gamma = frameContext.gamma;
-	metadata.set(controls::Gamma, gamma);
-
-	const auto &contrast = frameContext.contrast;
-	metadata.set(controls::Contrast, contrast.value_or(kDefaultContrast));
-
-	const auto &saturation = frameContext.saturation;
-	metadata.set(controls::Saturation, saturation.value_or(kDefaultSaturation));
+	metadata.set(controls::Gamma, frameContext.gamma);
+	metadata.set(controls::Contrast, frameContext.contrast);
+	metadata.set(controls::Saturation, frameContext.saturation);
 }
 
 REGISTER_IPA_ALGORITHM(Adjust, "Adjust")
--- a/src/ipa/softisp/algorithms/adjust.h
+++ b/src/ipa/softisp/algorithms/adjust.h
@@ -41,6 +41,10 @@
 
 private:
 	void applySaturation(Matrix<float, 3, 3> &ccm, float saturation);
+
+	float defaultGamma_ = kDefaultGamma;
+	float defaultContrast_ = 1.0f;
+	float defaultSaturation_ = 1.0f;
 };
 
 } /* namespace ipa::softisp::algorithms */
''',

    "libcamera-9999-softisp-agc-yaml.patch": r'''From: libcamera softisp agc YAML tuning <user@local>
Date: Mon, 25 Aug 2026 00:00:00 +0000
Subject: [PATCH] softisp: agc: Make exposure constants configurable from YAML

---
 a/src/ipa/softisp/algorithms/agc.cpp
+++ b/src/ipa/softisp/algorithms/agc.cpp
@@ -28,45 +28,56 @@ static constexpr unsigned int kExposureBinsCount = 5;
 
 /*
  * The exposure is optimal when the mean sample value of the histogram is
- * in the middle of the range.
+ * in the middle of the range.  Overridable via YAML exposureTarget.
  */
-static constexpr float kExposureOptimal = kExposureBinsCount / 2.0;
+static constexpr float kExposureTargetDefault = kExposureBinsCount / 2.0;
 
 /*
  * This implements the hysteresis for the exposure adjustment.
  * It is small enough to have the exposure close to the optimal, and is big
  * enough to prevent the exposure from wobbling around the optimal value.
+ * Overridable via YAML hysteresis.
  */
-static constexpr float kExposureSatisfactory = 0.2;
+static constexpr float kHysteresisDefault = 0.2;
 
 /*
  * Proportional gain for exposure/gain adjustment.  Maps the MSV error to a
  * multiplicative correction factor:
  *
- *   factor = 1.0 + kExpProportionalGain * error
+ *   factor = 1.0 + proportionalGain_ * error
  *
- * With kExpProportionalGain = 0.04:
+ * With proportionalGain_ = 0.04:
  *   - max error ~2.5 -> factor 1.10 (~10% step, same as before)
  *   - error 1.0      -> factor 1.04 (~4% step)
  *   - error 0.3      -> factor 1.012 (~1.2% step)
  *
  * This replaces the fixed 10% bang-bang step with a proportional correction
  * that converges smoothly and avoids overshooting near the target.
+ * Overridable via YAML proportionalGain.
  */
-static constexpr float kExpProportionalGain = 0.04;
+static constexpr float kProportionalGainDefault = 0.04;
 
 /*
  * Maximum multiplicative step per frame, to bound the correction when the
  * scene changes dramatically.
+ * Overridable via YAML maxStep.
  */
-static constexpr float kExpMaxStep = 0.15;
+static constexpr float kMaxStepDefault = 0.15;
 
 Agc::Agc()
 {
 }
+
+int Agc::init([[maybe_unused]] IPAContext &context, const ValueNode &tuningData)
+{
+	exposureTarget_ = tuningData["exposureTarget"].get<float>().value_or(kExposureTargetDefault);
+	hysteresis_ = tuningData["hysteresis"].get<float>().value_or(kHysteresisDefault);
+	proportionalGain_ = tuningData["proportionalGain"].get<float>().value_or(kProportionalGainDefault);
+	maxStep_ = tuningData["maxStep"].get<float>().value_or(kMaxStepDefault);
+
+	LOG(IPASoftIspExposure, Debug)
+		<< "AGC: exposureTarget " << exposureTarget_
+		<< ", hysteresis " << hysteresis_
+		<< ", proportionalGain " << proportionalGain_
+		<< ", maxStep " << maxStep_;
+
+	return 0;
+}
 
 void Agc::updateExposure(IPAContext &context, IPAFrameContext &frameContext, double exposureMSV)
 {
@@ -70,9 +81,9 @@
 	int32_t &exposure = frameContext.sensor.exposure;
 	double &again = frameContext.sensor.gain;
 
-	double error = kExposureOptimal - exposureMSV;
+	double error = exposureTarget_ - exposureMSV;
 
-	if (std::abs(error) <= kExposureSatisfactory)
+	if (std::abs(error) <= hysteresis_)
 		return;
 
 	/*
@@ -80,8 +91,8 @@
 	 * determines the direction: positive error means too dark (increase),
 	 * negative means too bright (decrease).
 	 */
-	float step = std::clamp(static_cast<float>(error) * kExpProportionalGain,
-				-kExpMaxStep, kExpMaxStep);
+	float step = std::clamp(static_cast<float>(error) * proportionalGain_,
+				-maxStep_, maxStep_);
 	float factor = 1.0f + step;
 
 	if (factor > 1.0f) {
--- a/src/ipa/softisp/algorithms/agc.h
+++ b/src/ipa/softisp/algorithms/agc.h
@@ -17,6 +17,8 @@
 	Agc();
 	~Agc() = default;
 
+	int init(IPAContext &context, const ValueNode &tuningData) override;
+
 	void process(IPAContext &context, const uint32_t frame,
 		     IPAFrameContext &frameContext,
 		     const SwIspStats *stats,
@@ -24,6 +26,11 @@
 
 private:
 	void updateExposure(IPAContext &context, IPAFrameContext &frameContext, double exposureMSV);
+
+	float exposureTarget_ = kExposureTargetDefault;
+	float hysteresis_ = kHysteresisDefault;
+	float proportionalGain_ = kProportionalGainDefault;
+	float maxStep_ = kMaxStepDefault;
 };
 
 } /* namespace ipa::softisp::algorithms */
''',

    "libcamera-9999-softisp-awb-yaml.patch": r'''From: libcamera softisp awb YAML tuning <user@local>
Date: Mon, 25 Aug 2026 00:00:00 +0000
Subject: [PATCH] softisp: awb: Add gain clamping and temporal smoothing from YAML

---
 a/src/ipa/softisp/algorithms/awb.cpp
+++ b/src/ipa/softisp/algorithms/awb.cpp
@@ -7,6 +7,7 @@
 
 #include "awb.h"
 
+#include <algorithm>
 #include <numeric>
 #include <stdint.h>
 
@@ -76,7 +77,20 @@
  */
 int Awb::init(IPAContext &context, const ValueNode &tuningData)
 {
-	return awbAlgo_.init(tuningData, context.ctrlMap);
+	int ret = awbAlgo_.init(tuningData, context.ctrlMap);
+	if (ret)
+		return ret;
+
+	maxGainR_ = tuningData["maxGainR"].get<float>().value_or(4.0f);
+	maxGainB_ = tuningData["maxGainB"].get<float>().value_or(4.0f);
+	speed_ = tuningData["speed"].get<float>().value_or(1.0f);
+
+	LOG(IPASoftIspAwb, Debug)
+		<< "AWB: maxGainR " << maxGainR_
+		<< ", maxGainB " << maxGainB_
+		<< ", speed " << speed_;
+
+	return 0;
 }
 
 /**
@@ -155,6 +169,34 @@
 
 	awbAlgo_.process(context.activeState.awb, frameContext.awb, awbStats,
 			 kDefaultLux, metadata);
+
+	/* Post-process: clamp and smooth gains */
+	auto &gains = frameContext.awb.gains;
+
+	double rawR = gains.r();
+	double rawB = gains.b();
+
+	/* Clamp to prevent extreme color casts */
+	rawR = std::min(rawR, static_cast<double>(maxGainR_));
+	rawB = std::min(rawB, static_cast<double>(maxGainB_));
+
+	/* Apply temporal smoothing */
+	double alpha = std::clamp(speed_, 0.01, 1.0);
+	double smoothedR = prevRGain_ * (1.0 - alpha) + rawR * alpha;
+	double smoothedB = prevBGain_ * (1.0 - alpha) + rawB * alpha;
+
+	gains.r() = smoothedR;
+	gains.g() = 1.0;
+	gains.b() = smoothedB;
+
+	/* Update active state and metadata with smoothed gains */
+	context.activeState.awb.automatic.gains = gains;
+	metadata.set(controls::ColourGains,
+		     Span<const float, 2>{ { static_cast<float>(smoothedR),
+					     static_cast<float>(smoothedB) } });
+
+	prevRGain_ = smoothedR;
+	prevBGain_ = smoothedB;
 }
 
 REGISTER_IPA_ALGORITHM(Awb, "Awb")
--- a/src/ipa/softisp/algorithms/awb.h
+++ b/src/ipa/softisp/algorithms/awb.h
@@ -55,6 +55,12 @@
 	 * reasonable.
 	 */
 	AwbAlgorithm<UQ<2, 8>> awbAlgo_;
+
+	float maxGainR_ = 4.0f;
+	float maxGainB_ = 4.0f;
+	float speed_ = 1.0f;
+	double prevRGain_ = 1.0;
+	double prevBGain_ = 1.0;
 };
 
 } /* namespace ipa::softisp::algorithms */
''',

    "libcamera-9999-softisp-context-float.patch": r'''From: libcamera softisp context float knobs <user@local>
Date: Mon, 25 Aug 2026 00:00:00 +0000
Subject: [PATCH] softisp: ipa_context: Use plain float for contrast/saturation knobs

---
 a/src/ipa/softisp/ipa_context.h
+++ b/src/ipa/softisp/ipa_context.h
@@ -58,8 +58,8 @@
 	struct {
 		float gamma;
 		/* 0..2 range, 1.0 = normal */
-		std::optional<float> contrast;
-		std::optional<float> saturation;
+		float contrast;
+		float saturation;
 	} knobs;
 };
 
@@ -73,8 +73,8 @@
 	} sensor;
 
 	float gamma;
-	std::optional<float> contrast;
-	std::optional<float> saturation;
+	float contrast;
+	float saturation;
 };
 
 struct IPAContext {
'''
}

def main():
    os.makedirs(OVERLAY, exist_ok=True)
    for name, content in patches.items():
        path = os.path.join(OVERLAY, name)
        with open(path, 'w') as f:
            f.write(content)
        tab_count = content.count('\t')
        print(f"Wrote {path} ({len(content)} bytes, {tab_count} tabs)")

    print("\nNow update your ebuild PATCHES array and run:")
    print("  cd /var/db/repos/local/media-libs/libcamera")
    print("  sudo ebuild libcamera-9999.ebuild manifest")
    print("  sudo emerge -1av media-libs/libcamera")

if __name__ == '__main__':
    main()
