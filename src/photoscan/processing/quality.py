
import cv2
import numpy as np

from photoscan.domain.models import OrderedCorners, QualityReport


class QualityAssessor:
    """
    Computes quality assessment metrics (blur, exposure, skew, highlights)
    and reports user-friendly diagnostic notices.
    """

    def assess(
        self,
        original_rgb: np.ndarray,
        detection_success: bool,
        detection_confidence: float,
        corners: OrderedCorners | None = None
    ) -> QualityReport:
        """
        Runs quality analysis on the original image and boundary coordinates.
        """
        h, w = original_rgb.shape[:2]
        gray = cv2.cvtColor(original_rgb, cv2.COLOR_RGB2GRAY)
        warnings: list[str] = []

        # 1. Blur estimation: Laplacian variance
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < 80.0:
            warnings.append("The image is strongly blurred; small text may remain unreadable.")
        elif laplacian_var < 200.0:
            warnings.append("The image has mild blur; readability of small fonts might be affected.")

        # 2. Exposure & Highlights/Shadows
        mean_intensity = float(np.mean(gray))
        exposure_quality = 1.0 - abs(mean_intensity - 127.5) / 127.5

        if mean_intensity > 230.0:
            warnings.append("The image appears overexposed or has bright glare.")
        elif mean_intensity < 40.0:
            warnings.append("The image is underexposed or very dark.")

        # Highlight clipping (pixels = 255)
        clipped_high = float(np.mean(gray >= 253))
        if clipped_high > 0.08:
            warnings.append("Glare or extreme highlights cover parts of the page.")

        # Shadow severity (pixels <= 15)
        clipped_low = float(np.mean(gray <= 15))
        if clipped_low > 0.15:
            warnings.append("Deep shadows or dark background clutter detected.")

        # 3. Geometry & Perspective Assessment
        skew_angle = 0.0
        perspective_severity = 0.0

        if corners:
            pts = np.array([
                [corners.top_left.x * w, corners.top_left.y * h],
                [corners.top_right.x * w, corners.top_right.y * h],
                [corners.bottom_right.x * w, corners.bottom_right.y * h],
                [corners.bottom_left.x * w, corners.bottom_left.y * h],
            ], dtype=np.float32)

            # Compute skew from top edge angle
            dx = pts[1][0] - pts[0][0]
            dy = pts[1][1] - pts[0][1]
            skew_angle = float(np.degrees(np.arctan2(dy, dx)))

            # Compute perspective severity (difference between top & bottom widths, or left & right heights)
            top_w = np.linalg.norm(pts[1] - pts[0])
            bot_w = np.linalg.norm(pts[2] - pts[3])
            left_h = np.linalg.norm(pts[3] - pts[0])
            right_h = np.linalg.norm(pts[2] - pts[1])

            perspective_severity = float(abs(top_w - bot_w) / (max(top_w, bot_w) + 1e-5) +
                                         abs(left_h - right_h) / (max(left_h, right_h) + 1e-5))

            if perspective_severity > 0.35:
                warnings.append("The page is photographed at an extreme perspective angle.")

            # Page area ratio
            area = cv2.contourArea(pts)
            area_ratio = area / (w * h)
            if area_ratio < 0.15:
                warnings.append("The detected page is very small relative to the photograph.")
        else:
            if not detection_success:
                warnings.append("The page edges could not be detected reliably.")

        # 4. Output contrast
        hist, _ = np.histogram(gray, bins=256, range=(0, 256))
        # Cumulative distribution to get contrast
        cdf = hist.cumsum()
        cdf_normalized = cdf * (1.0 / cdf[-1])
        low_val = int(np.searchsorted(cdf_normalized, 0.05))
        high_val = int(np.searchsorted(cdf_normalized, 0.95))
        contrast_range = float(high_val - low_val)

        # Estimate readable resolution
        # A simple model: Megapixel count scaled by blur factor
        megapixels = (w * h) / 1_000_000.0
        readable_res = "High"
        if megapixels < 2.0 or laplacian_var < 100.0:
            readable_res = "Low"
        elif megapixels < 5.0 or laplacian_var < 180.0:
            readable_res = "Medium"

        return QualityReport(
            detection_confidence=float(detection_confidence),
            blur_estimate=laplacian_var,
            exposure_quality=exposure_quality,
            highlight_clipping=clipped_high,
            shadow_severity=clipped_low,
            skew_angle=skew_angle,
            perspective_severity=perspective_severity,
            estimated_readable_resolution=readable_res,
            output_contrast=contrast_range,
            potential_text_stroke_loss=(contrast_range < 50 or laplacian_var < 80.0),
            possible_glare_or_occlusion=(clipped_high > 0.12),
            warnings=warnings
        )
