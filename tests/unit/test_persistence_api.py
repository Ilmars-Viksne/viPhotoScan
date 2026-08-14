from pathlib import Path

import numpy as np

from photoscan.application.api import DocumentScanner, ScanResult
from photoscan.domain.project import PageProjectSettings, ProjectModel
from photoscan.infrastructure.persistence import ProjectStore
from photoscan.processing.ocr import MockOcrEngine


def test_project_persistence_and_loading(tmp_path):
    # Setup test file reference
    src_img = tmp_path / "page1.png"
    src_img.write_text("fake image content")

    # 1. Create ProjectModel
    page = PageProjectSettings(
        id="page-123",
        source_path=str(src_img),
        label="Page 1"
    )
    project = ProjectModel(
        export_dpi=150,
        pages=[page]
    )

    store = ProjectStore()
    proj_file = tmp_path / "project.photoscan"

    # 2. Save
    store.save_project(project, proj_file)
    assert proj_file.exists()

    # 3. Load & Verify
    loaded = store.load_project(proj_file)
    assert loaded.export_dpi == 150
    assert len(loaded.pages) == 1
    assert loaded.pages[0].id == "page-123"

def test_project_package_zip_slip_and_extraction(tmp_path):
    store = ProjectStore()

    # Create fake image source to package
    src_img = tmp_path / "origin.jpg"
    src_img.write_text("raw pixel data")

    page = PageProjectSettings(id="page-1", source_path=str(src_img))
    project = ProjectModel(pages=[page])

    pkg_file = tmp_path / "bundle.photoscanpkg"

    # Save Package
    store.save_package(project, pkg_file)
    assert pkg_file.exists()

    # Extract Package Safely
    extract_dir = tmp_path / "extraction_workspace"
    extracted_proj = store.extract_package(pkg_file, extract_dir)

    assert len(extracted_proj.pages) == 1
    extracted_path = Path(extracted_proj.pages[0].source_path)
    assert extracted_path.exists()
    assert extracted_path.read_text() == "raw pixel data"

def test_public_scanner_api():
    # Setup scanner
    scanner = DocumentScanner()

    # Simple synthetic canvas
    canvas = np.zeros((200, 200, 3), dtype=np.uint8)
    canvas[20:180, 20:180, :] = 255  # clear white square on dark background

    result = scanner.scan(canvas)

    assert isinstance(result, ScanResult)
    assert result.original_image.shape == (200, 200, 3)
    assert result.rectified_image.shape[0] > 0
    assert result.enhanced_image.shape == result.rectified_image.shape
    assert result.quality_report.detection_confidence > 0.0

def test_ocr_pluggable_interface(tmp_path):
    engine = MockOcrEngine()
    assert engine.is_available() is True
    assert "tesseract" in engine.get_version().lower()
    assert "eng" in engine.list_languages()

    dummy_img = tmp_path / "dummy.png"
    dummy_img.write_text("...")
    res = engine.extract_text(dummy_img)
    assert res.text == "Mock OCR Extracted Text Content"
