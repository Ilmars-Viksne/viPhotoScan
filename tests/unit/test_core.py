import numpy as np
import pytest

from photoscan.domain.exceptions import InvalidGeometryError
from photoscan.domain.models import Corner, OrderedCorners, ScanMode, ScanSettings
from photoscan.export.exporter import DocumentExporter
from photoscan.processing.detection import DocumentDetector, order_points
from photoscan.processing.enhancement import DocumentEnhancer, sauvola_threshold
from photoscan.processing.geometry import Rectifier
from photoscan.processing.quality import QualityAssessor


def test_corner_ordering():
    # Points in randomized order
    pts = np.array([
        [100, 100],  # top-left
        [100, 400],  # bottom-left
        [400, 400],  # bottom-right
        [400, 100],  # top-right
    ], dtype=np.float32)

    ordered = order_points(pts)

    # Expected order: top-left, top-right, bottom-right, bottom-left
    assert np.allclose(ordered[0], [100, 100])
    assert np.allclose(ordered[1], [400, 100])
    assert np.allclose(ordered[2], [400, 400])
    assert np.allclose(ordered[3], [100, 400])

def test_sauvola_thresholding():
    # Simple gradient image
    gray = np.linspace(0, 255, 100).reshape(10, 10).astype(np.uint8)
    binary = sauvola_threshold(gray, window_size=3, k=0.2)
    assert binary.shape == (10, 10)
    assert binary.dtype == np.uint8

def test_rectifier_validation(tmp_path):
    rectifier = Rectifier()

    # Valid corners
    valid_corners = OrderedCorners(
        top_left=Corner(x=0.1, y=0.1),
        top_right=Corner(x=0.9, y=0.1),
        bottom_right=Corner(x=0.9, y=0.9),
        bottom_left=Corner(x=0.1, y=0.9)
    )
    rectifier.validate_geometry(valid_corners, (1000, 1000))

    # Self-intersecting corners (invalid)
    invalid_corners = OrderedCorners(
        top_left=Corner(x=0.1, y=0.1),
        top_right=Corner(x=0.1, y=0.9),  # Crossed!
        bottom_right=Corner(x=0.9, y=0.1),
        bottom_left=Corner(x=0.9, y=0.9)
    )
    with pytest.raises(InvalidGeometryError):
        rectifier.validate_geometry(invalid_corners, (1000, 1000))

def test_document_detection_and_enhancement():
    # Create synthetic image: dark background with a bright rectangular paper
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    # White document sheet
    img[50:350, 50:350, :] = 220

    detector = DocumentDetector()
    res = detector.detect(img)

    assert res.success is True
    # The best candidate should be very close to the 50, 350 bounds (which translates to 0.125 and 0.875)
    best = res.best_candidate
    assert abs(best.corners.top_left.x - 0.125) < 0.05
    assert abs(best.corners.top_left.y - 0.125) < 0.05

    # Test Rectifier
    rectifier = Rectifier()
    warped = rectifier.warp_perspective(img, best.corners)
    assert warped.shape[0] > 0
    assert warped.shape[1] > 0

    # Test Enhancer
    enhancer = DocumentEnhancer()
    settings = ScanSettings(mode=ScanMode.COLOR)
    enhanced = enhancer.enhance(warped, settings)
    assert enhanced.shape == warped.shape

def test_quality_assessor():
    # Pure gray image
    img = np.full((300, 300, 3), 128, dtype=np.uint8)
    assessor = QualityAssessor()
    report = assessor.assess(img, detection_success=True, detection_confidence=0.9)

    assert report.detection_confidence == 0.9
    assert report.blur_estimate >= 0.0

def test_exporter(tmp_path):
    img = np.ones((200, 200, 3), dtype=np.uint8) * 150
    exporter = DocumentExporter()

    dest_png = tmp_path / "scan.png"
    exporter.export_single_page(img, dest_png, "png")
    assert dest_png.exists()
    assert dest_png.stat().st_size > 0

    # Test multi-page PDF export
    dest_pdf = tmp_path / "scans.pdf"
    exporter.export_multipage([img, img], dest_pdf, "pdf")
    assert dest_pdf.exists()
    assert dest_pdf.stat().st_size > 0
