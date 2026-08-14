
import cv2
import numpy as np

from photoscan.domain.exceptions import InvalidGeometryError
from photoscan.domain.models import OrderedCorners


class Rectifier:
    """
    Handles perspective transformation and geometry corrections.
    Ensures safe, high-quality, and robust warping.
    """
    def __init__(self, max_dimension: int = 8000) -> None:
        self.max_dimension = max_dimension

    def validate_geometry(self, corners: OrderedCorners, img_shape: tuple[int, int]) -> None:
        """
        Validates the given corners against self-intersections, collinearity,
        and degenerate/extremely small areas.
        """
        h, w = img_shape[:2]
        pts = np.array([
            [corners.top_left.x * w, corners.top_left.y * h],
            [corners.top_right.x * w, corners.top_right.y * h],
            [corners.bottom_right.x * w, corners.bottom_right.y * h],
            [corners.bottom_left.x * w, corners.bottom_left.y * h],
        ], dtype=np.float32)

        # 1. Check area
        area = cv2.contourArea(pts)
        img_area = w * h
        if area < 100 or (area / img_area) < 0.001:
            raise InvalidGeometryError("The selected document region is too small or degenerate.")

        # 2. Check convexity (prevents self-intersection)
        if not cv2.isContourConvex(pts.astype(np.int32)):
            raise InvalidGeometryError("The selected corners create a self-intersecting or non-convex shape.")

        # 3. Check collinearity (cross-product of consecutive vectors should not be near zero)
        for i in range(4):
            v1 = pts[(i + 1) % 4] - pts[i]
            v2 = pts[(i + 2) % 4] - pts[(i + 1) % 4]
            cross = np.abs(v1[0] * v2[1] - v1[1] * v2[0])
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            if cross / (norm_v1 * norm_v2 + 1e-8) < 1e-3:
                raise InvalidGeometryError("Three or more points are nearly collinear.")

    def calculate_output_dimensions(
        self,
        corners: OrderedCorners,
        img_shape: tuple[int, int],
        paper_size: str | None = None,
        dpi: int = 300,
        padding_pct: float = 0.0
    ) -> tuple[int, int]:
        """
        Calculates output dimensions preserving aspect ratio or fitting specific standard sizes.
        """
        h, w = img_shape[:2]
        pts = np.array([
            [corners.top_left.x * w, corners.top_left.y * h],
            [corners.top_right.x * w, corners.top_right.y * h],
            [corners.bottom_right.x * w, corners.bottom_right.y * h],
            [corners.bottom_left.x * w, corners.bottom_left.y * h],
        ], dtype=np.float32)

        # Standard physical aspect ratios (height / width)
        paper_aspects: dict[str, float] = {
            "A4": 1.414,
            "Letter": 1.294,
            "Legal": 1.647,
        }

        # Calculate standard scanned width & height based on edge lengths
        width_top = np.linalg.norm(pts[0] - pts[1])
        width_bottom = np.linalg.norm(pts[2] - pts[3])
        max_width = int(max(width_top, width_bottom))

        height_left = np.linalg.norm(pts[0] - pts[3])
        height_right = np.linalg.norm(pts[1] - pts[2])
        max_height = int(max(height_left, height_right))

        if max_width <= 0 or max_height <= 0:
            raise InvalidGeometryError("Calculated dimensions are invalid (zero size).")

        # Handle paper size overrides
        if paper_size and paper_size.upper() in paper_aspects:
            aspect = paper_aspects[paper_size.upper()]
            # Determine if we are portrait or landscape based on max_width/max_height
            is_portrait = max_height >= max_width
            if is_portrait:
                max_height = int(max_width * aspect)
            else:
                max_width = int(max_height * aspect)

        # Limit maximum dimensions to avoid memory exhaustion
        if max_width > self.max_dimension or max_height > self.max_dimension:
            scale = self.max_dimension / max(max_width, max_height)
            max_width = int(max_width * scale)
            max_height = int(max_height * scale)

        return max(1, max_width), max(1, max_height)

    def warp_perspective(
        self,
        rgb_image: np.ndarray,
        corners: OrderedCorners,
        paper_size: str | None = None,
        dpi: int = 300,
        padding_pct: float = 0.0
    ) -> np.ndarray:
        """
        Applies a high-quality perspective transform to crop and warp the image into a rectangular document.
        """
        h, w = rgb_image.shape[:2]
        self.validate_geometry(corners, (h, w))

        out_w, out_h = self.calculate_output_dimensions(corners, (h, w), paper_size, dpi, padding_pct)

        src_pts = np.array([
            [corners.top_left.x * w, corners.top_left.y * h],
            [corners.top_right.x * w, corners.top_right.y * h],
            [corners.bottom_right.x * w, corners.bottom_right.y * h],
            [corners.bottom_left.x * w, corners.bottom_left.y * h],
        ], dtype=np.float32)

        # Target coordinate positions
        dst_pts = np.array([
            [0, 0],
            [out_w - 1, 0],
            [out_w - 1, out_h - 1],
            [0, out_h - 1],
        ], dtype=np.float32)

        m = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(rgb_image, m, (out_w, out_h), flags=cv2.INTER_LANCZOS4)

        # Apply configurable padding if requested (e.g. margin/border padding)
        if padding_pct > 0.0:
            pad_x = int(out_w * (padding_pct / 100.0))
            pad_y = int(out_h * (padding_pct / 100.0))
            warped = cv2.copyMakeBorder(
                warped, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )

        return warped
