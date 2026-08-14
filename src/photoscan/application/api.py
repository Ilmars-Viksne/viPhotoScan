from pathlib import Path

import numpy as np

from photoscan.domain.exceptions import ProcessingFailureError
from photoscan.domain.models import OrderedCorners, QualityReport, ScanSettings
from photoscan.export.exporter import DocumentExporter
from photoscan.processing.decoding import load_image_to_rgb
from photoscan.processing.detection import DocumentDetector
from photoscan.processing.enhancement import DocumentEnhancer
from photoscan.processing.geometry import Rectifier
from photoscan.processing.quality import QualityAssessor


class ScanResult:
    """
    Encapsulates the output of a single document page scanning operation.
    """
    def __init__(
        self,
        original_image: np.ndarray,
        rectified_image: np.ndarray,
        enhanced_image: np.ndarray,
        corners: OrderedCorners,
        quality_report: QualityReport
    ) -> None:
        self.original_image = original_image
        self.rectified_image = rectified_image
        self.enhanced_image = enhanced_image
        self.corners = corners
        self.quality_report = quality_report

    def save(
        self,
        destination: Path | str,
        format_name: str = "PNG",
        dpi: int = 300,
        jpeg_quality: int = 90,
        grayscale: bool = False
    ) -> None:
        """
        Saves the enhanced scan result to the requested destination.
        """
        exporter = DocumentExporter()
        exporter.export_single_page(
            self.enhanced_image,
            destination,
            format_name,
            dpi=dpi,
            jpeg_quality=jpeg_quality,
            grayscale=grayscale
        )

class DocumentScanner:
    """
    High-level, production-grade document scanning API.
    Provides complete end-to-end load, detect, warp, enhance, and assess pipelines.
    """
    def __init__(self, default_settings: ScanSettings | None = None) -> None:
        self.default_settings = default_settings or ScanSettings()
        self._detector = DocumentDetector()
        self._rectifier = Rectifier()
        self._enhancer = DocumentEnhancer()
        self._assessor = QualityAssessor()

    def scan(
        self,
        source: Path | str | bytes | np.ndarray,
        settings: ScanSettings | None = None,
        corners: OrderedCorners | None = None
    ) -> ScanResult:
        """
        Processes a single source input and returns a structured ScanResult.

        Args:
            source: Path, raw bytes, or an already decoded RGB NumPy array.
            settings: Scan settings to override defaults.
            corners: Optional manual corners; if not provided, automatic detection runs.
        """
        # 1. Image decoding & normalization
        rgb_img = source if isinstance(source, np.ndarray) else load_image_to_rgb(source)

        run_settings = settings or self.default_settings

        # 2. Page boundary detection or corner assignment
        detection_success = True
        detection_confidence = 1.0

        if corners is None:
            detection_res = self._detector.detect(rgb_img)
            corners = detection_res.best_candidate.corners
            detection_success = detection_res.success
            detection_confidence = detection_res.best_candidate.confidence

        try:
            # 3. Perspective transformation
            rectified = self._rectifier.warp_perspective(
                rgb_img,
                corners,
                paper_size=run_settings.paper_size,
                dpi=run_settings.output_dpi,
                padding_pct=run_settings.padding
            )

            # 4. Mode-specific enhancement & illumination correction
            enhanced = self._enhancer.enhance(rectified, run_settings)

            # 5. Quality assessment
            quality_report = self._assessor.assess(
                rgb_img,
                detection_success,
                detection_confidence,
                corners
            )

        except Exception as e:
            if isinstance(e, ProcessingFailureError):
                raise
            raise ProcessingFailureError(f"Scanning pipeline failed: {e}") from e

        return ScanResult(
            original_image=rgb_img,
            rectified_image=rectified,
            enhanced_image=enhanced,
            corners=corners,
            quality_report=quality_report
        )
