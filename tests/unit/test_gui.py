# Ensure PySide6 platform is set to offscreen before testing
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from photoscan.domain.models import Corner, OrderedCorners
from photoscan.domain.project import PageProjectSettings
from photoscan.gui.corner_editor import CornerEditor
from photoscan.gui.main_window import PhotoScanWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"

def test_corner_editor_coordinates_conversion(qtbot):
    widget = CornerEditor()
    qtbot.addWidget(widget)
    widget.resize(400, 300)

    # Use a solid blank pixmap for testing coordinates
    img = QImage(200, 150, QImage.Format_RGB888)
    img.fill(Qt.white)
    pixmap = QPixmap.fromImage(img)

    corners = OrderedCorners(
        top_left=Corner(x=0.0, y=0.0),
        top_right=Corner(x=1.0, y=0.0),
        bottom_right=Corner(x=1.0, y=1.0),
        bottom_left=Corner(x=0.0, y=1.0),
    )
    widget.set_image(pixmap, corners)

    # Convert coordinates and verify
    # Widget center should translate back to 0.5, 0.5
    cx, cy = widget._widget_to_norm(widget.width() / 2, widget.height() / 2)
    assert abs(cx - 0.5) < 0.01
    assert abs(cy - 0.5) < 0.01

def test_main_window_widget_structure(qtbot):
    window = PhotoScanWindow()
    qtbot.addWidget(window)

    # Check existence of structural elements
    assert window.thumbnail_list is not None
    assert window.corner_editor is not None
    assert window.combo_mode is not None
    assert window.slider_brightness is not None
    assert window.slider_contrast is not None
    assert window.slider_sharpness is not None
    assert window.slider_saturation is not None
    assert window.slider_shadow is not None

def test_undo_redo_history(qtbot):
    window = PhotoScanWindow()
    qtbot.addWidget(window)
    # Mock background page loading/scanning thread for history testing
    window.on_page_selected = lambda idx: None

    # Initialize empty project list
    assert len(window.project.pages) == 0

    # Add a mock page and check undo stack
    window._push_history()
    window.project.pages.append(PageProjectSettings(id="p1", source_path="dummy.png"))
    assert len(window.project.pages) == 1
    assert len(window.undo_stack) == 1

    # Undo
    window.undo_action()
    assert len(window.project.pages) == 0
    assert len(window.redo_stack) == 1

    # Redo
    window.redo_action()
    assert len(window.project.pages) == 1
    assert len(window.undo_stack) == 1

def test_rapid_slider_adjustments(qtbot, tmp_path):
    # Create a small dummy image for testing worker execution
    img_path = tmp_path / "test_doc.png"
    img = QImage(100, 100, QImage.Format_RGB888)
    img.fill(Qt.white)
    img.save(str(img_path))

    window = PhotoScanWindow()
    qtbot.addWidget(window)

    page = PageProjectSettings(id="p1", source_path=str(img_path))
    window.project.pages.append(page)
    window.current_page_idx = 0

    # Simulate rapid slider changes
    for val in range(-50, 50, 5):
        window.slider_brightness.setValue(val)
        window.slider_contrast.setValue(15)

    # Trigger debounce timer completion
    if window._settings_debounce_timer.isActive():
        window._settings_debounce_timer.timeout.emit()

    # Wait until workers finish running
    qtbot.waitUntil(lambda: len(window._workers) == 0, timeout=3000)
    assert len(window._workers) == 0

    window.close()
