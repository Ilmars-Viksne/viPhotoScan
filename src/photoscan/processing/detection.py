from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from photoscan.domain.models import Corner, OrderedCorners


class DetectionCandidate(BaseModel):
    corners: OrderedCorners
    confidence: float
    scores: dict[str, float] = Field(default_factory=dict)

class DetectionResult(BaseModel):
    success: bool
    best_candidate: DetectionCandidate
    alternatives: list[DetectionCandidate] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 points into [top-left, top-right, bottom-right, bottom-left].
    pts should be a numpy array of shape (4, 2).
    """
    # Sort points according to their x-coordinates
    x_sorted = pts[pts[:, 0].argsort()]

    # Grab the left-most and right-most points
    left_most = x_sorted[:2, :]
    right_most = x_sorted[2:, :]

    # Of the left-most points, the one with the higher y-coordinate is the bottom-left,
    # and the one with the lower y-coordinate is the top-left
    left_most = left_most[left_most[:, 1].argsort()]
    (tl, bl) = left_most[0], left_most[1]

    # Of the right-most points, the one with the higher y-coordinate is the bottom-right,
    # and the one with the lower y-coordinate is the top-right
    right_most = right_most[right_most[:, 1].argsort()]
    (tr, br) = right_most[0], right_most[1]

    return np.array([tl, tr, br, bl], dtype="float32")

class DocumentDetector:
    """
    Automatic document boundary detector using multi-scale classical computer vision.
    Evaluates edge strength, contour geometry, and contrast to find document quadrilaterals.
    """
    def __init__(self, min_area_ratio: float = 0.1, max_area_ratio: float = 0.99) -> None:
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio

    def detect(self, rgb_image: np.ndarray) -> DetectionResult:
        """
        Detects document corners in the RGB image.
        Returns a DetectionResult containing ordered corners, confidence, alternatives, and diagnostics.
        """
        h, w = rgb_image.shape[:2]
        w * h

        # Create safe fallback (5% margin)
        fallback_corners = OrderedCorners(
            top_left=Corner(x=0.05, y=0.05),
            top_right=Corner(x=0.95, y=0.05),
            bottom_right=Corner(x=0.95, y=0.95),
            bottom_left=Corner(x=0.05, y=0.95)
        )
        fallback_candidate = DetectionCandidate(
            corners=fallback_corners,
            confidence=0.0,
            scores={"reason": 0.0}  # 0 logic score
        )

        diagnostics: dict[str, Any] = {}

        # 1. Downscale image for analysis to speed up processing (max dimension 800)
        scale_target = 800.0
        scale = min(1.0, scale_target / max(w, h))
        dw = int(w * scale)
        dh = int(h * scale)

        if dw <= 0 or dh <= 0:
            diagnostics["fail_reason"] = "Degenerate image dimensions"
            return DetectionResult(success=False, best_candidate=fallback_candidate, diagnostics=diagnostics)

        resized = cv2.resize(rgb_image, (dw, dh), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)

        # 2. Apply bilateral filter to smooth textures while preserving document edges
        smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

        # 3. Use multi-channel / multi-threshold approach to capture different contrast situations
        edge_maps = []

        # Canny edge map
        v = np.median(smoothed)
        lower = int(max(0, (1.0 - 0.33) * v))
        upper = int(min(255, (1.0 + 0.33) * v))
        canny = cv2.Canny(smoothed, lower, upper)
        edge_maps.append(canny)

        # Otsu thresholding + morphology
        _, otsu = cv2.threshold(smoothed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        otsu_edges = cv2.Canny(otsu, 100, 200)
        edge_maps.append(otsu_edges)

        # Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(
            smoothed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        adaptive_edges = cv2.Canny(adaptive, 100, 200)
        edge_maps.append(adaptive_edges)

        candidates: list[DetectionCandidate] = []

        # Find contours from all generated edge maps
        for _idx, edges in enumerate(edge_maps):
            # Dilate to close gaps
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            dilated = cv2.dilate(edges, kernel, iterations=1)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)

                # Check if it has 4 corners and is convex
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    # Reshape to (4, 2)
                    pts = approx.reshape(4, 2)

                    # Normalize points (relative to resized image coordinates)
                    norm_pts = []
                    for pt in pts:
                        norm_pts.append((float(pt[0]) / dw, float(pt[1]) / dh))

                    # Order the corners
                    ordered_pts = order_points(np.array(norm_pts, dtype="float32"))

                    candidate_corners = OrderedCorners(
                        top_left=Corner(x=float(ordered_pts[0][0]), y=float(ordered_pts[0][1])),
                        top_right=Corner(x=float(ordered_pts[1][0]), y=float(ordered_pts[1][1])),
                        bottom_right=Corner(x=float(ordered_pts[2][0]), y=float(ordered_pts[2][1])),
                        bottom_left=Corner(x=float(ordered_pts[3][0]), y=float(ordered_pts[3][1])),
                    )

                    # Compute scores
                    scores = self._score_quadrilateral(candidate_corners, rgb_image)
                    confidence = float(np.mean(list(scores.values())))

                    # Check area constraints
                    if self.min_area_ratio <= scores.get("area_ratio", 0.0) <= self.max_area_ratio:
                        candidates.append(
                            DetectionCandidate(
                                corners=candidate_corners,
                                confidence=confidence,
                                scores=scores
                            )
                        )

        # De-duplicate candidates by comparing corner positions
        unique_candidates: list[DetectionCandidate] = []
        for cand in sorted(candidates, key=lambda x: x.confidence, reverse=True):
            is_dup = False
            for u in unique_candidates:
                dist = np.mean([
                    np.hypot(cand.corners.top_left.x - u.corners.top_left.x, cand.corners.top_left.y - u.corners.top_left.y),
                    np.hypot(cand.corners.top_right.x - u.corners.top_right.x, cand.corners.top_right.y - u.corners.top_right.y),
                    np.hypot(cand.corners.bottom_right.x - u.corners.bottom_right.x, cand.corners.bottom_right.y - u.corners.bottom_right.y),
                    np.hypot(cand.corners.bottom_left.x - u.corners.bottom_left.x, cand.corners.bottom_left.y - u.corners.bottom_left.y),
                ])
                if dist < 0.05:  # within 5% of coordinate space
                    is_dup = True
                    break
            if not is_dup:
                unique_candidates.append(cand)

        diagnostics["total_candidates_found"] = len(unique_candidates)

        if not unique_candidates:
            diagnostics["fail_reason"] = "No valid convex quadrilaterals detected matching constraints"
            return DetectionResult(
                success=False,
                best_candidate=fallback_candidate,
                alternatives=[],
                diagnostics=diagnostics
            )

        # Run optional subpixel corner refinement on the original image for the best candidate
        best_cand = unique_candidates[0]
        refined_corners = self._refine_corners(best_cand.corners, rgb_image)
        best_cand.corners = refined_corners

        return DetectionResult(
            success=True,
            best_candidate=best_cand,
            alternatives=unique_candidates[1:5],  # Top 4 alternatives
            diagnostics=diagnostics
        )

    def _score_quadrilateral(self, corners: OrderedCorners, original_image: np.ndarray) -> dict[str, float]:
        """
        Scores a candidate based on geometry metrics: area ratio, rectangularity, corner angle plausibility,
        and distance from image boundaries. Returns a dict of normalized score metrics.
        """
        # Convert corners to image coordinates
        h, w = original_image.shape[:2]
        pts = np.array([
            [corners.top_left.x * w, corners.top_left.y * h],
            [corners.top_right.x * w, corners.top_right.y * h],
            [corners.bottom_right.x * w, corners.bottom_right.y * h],
            [corners.bottom_left.x * w, corners.bottom_left.y * h],
        ], dtype=np.float32)

        # 1. Area ratio
        area = cv2.contourArea(pts)
        img_area = w * h
        area_ratio = float(area / img_area)

        # 2. Rectangularity / Simplicity
        # Compute bounding rectangle and its area
        rect = cv2.minAreaRect(pts)
        rect_area = rect[1][0] * rect[1][1]
        rectangularity = float(area / rect_area) if rect_area > 0 else 0.0

        # 3. Corner angle plausibility
        # Compute angles of internal corners. Perfect would be 90 degrees.
        angles = []
        indices = [(0, 1, 2), (1, 2, 3), (2, 3, 0), (3, 0, 1)]
        for i, j, k in indices:
            v1 = pts[i] - pts[j]
            v2 = pts[k] - pts[j]
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
            angle = np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))
            angles.append(angle)

        # Penality for deviating far from 90 degrees
        angle_deviation = float(np.mean([abs(a - 90.0) for a in angles]))
        angle_score = float(max(0.0, 1.0 - (angle_deviation / 45.0)))

        # 4. Aspect Ratio Plausibility
        # Compute lengths of top, bottom, left, right edges
        top_len = np.linalg.norm(pts[0] - pts[1])
        right_len = np.linalg.norm(pts[1] - pts[2])
        bottom_len = np.linalg.norm(pts[2] - pts[3])
        left_len = np.linalg.norm(pts[3] - pts[0])

        # Expect left & right, top & bottom to be relatively similar
        w_ratio = min(top_len, bottom_len) / (max(top_len, bottom_len) + 1e-8)
        h_ratio = min(left_len, right_len) / (max(left_len, right_len) + 1e-8)
        symmetry_score = float((w_ratio + h_ratio) / 2.0)

        return {
            "area_ratio": area_ratio,
            "rectangularity": rectangularity,
            "angle_plausibility": angle_score,
            "symmetry_score": symmetry_score,
        }

    def _refine_corners(self, corners: OrderedCorners, original_image: np.ndarray) -> OrderedCorners:
        """
        Refines corner coordinates using OpenCV subpixel optimization.
        """
        h, w = original_image.shape[:2]
        gray = cv2.cvtColor(original_image, cv2.COLOR_RGB2GRAY)

        # Coordinates in original scale
        pts = np.array([
            [corners.top_left.x * w, corners.top_left.y * h],
            [corners.top_right.x * w, corners.top_right.y * h],
            [corners.bottom_right.x * w, corners.bottom_right.y * h],
            [corners.bottom_left.x * w, corners.bottom_left.y * h],
        ], dtype=np.float32)

        import contextlib
        # Refine corner locations
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
        with contextlib.suppress(Exception):
            cv2.cornerSubPix(gray, pts, (5, 5), (-1, -1), criteria)

        return OrderedCorners(
            top_left=Corner(x=float(np.clip(pts[0][0] / w, 0.0, 1.0)), y=float(np.clip(pts[0][1] / h, 0.0, 1.0))),
            top_right=Corner(x=float(np.clip(pts[1][0] / w, 0.0, 1.0)), y=float(np.clip(pts[1][1] / h, 0.0, 1.0))),
            bottom_right=Corner(x=float(np.clip(pts[2][0] / w, 0.0, 1.0)), y=float(np.clip(pts[2][1] / h, 0.0, 1.0))),
            bottom_left=Corner(x=float(np.clip(pts[3][0] / w, 0.0, 1.0)), y=float(np.clip(pts[3][1] / h, 0.0, 1.0))),
        )
