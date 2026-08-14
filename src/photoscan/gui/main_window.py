# ruff: noqa: N802
from pathlib import Path

import cv2
from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from photoscan.application.api import DocumentScanner, ScanResult
from photoscan.domain.models import Corner, OrderedCorners, ScanMode, ScanSettings
from photoscan.domain.project import PageProjectSettings, ProjectModel
from photoscan.gui.corner_editor import CornerEditor
from photoscan.gui.worker import ScanWorker
from photoscan.infrastructure.persistence import ProjectStore


class PhotoScanWindow(QMainWindow):
    """
    Main application window of the PhotoScan PySide6 Desktop GUI.
    Coordinates import lists, background worker updates, manual edits, and exports.
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PhotoScan - Document Scanner")
        self.resize(1100, 750)

        # Domain Models
        self.project = ProjectModel()
        self.current_page_idx: int = -1
        self.project_store = ProjectStore()

        # History stacks for Undo/Redo
        self.undo_stack: list[ProjectModel] = []
        self.redo_stack: list[ProjectModel] = []

        # UI Setup
        self._init_actions()
        self._init_toolbar()
        self._init_menu()
        self._init_central_widget()
        self._init_statusbar()

        # State
        self.active_worker: ScanWorker | None = None

    def _push_history(self) -> None:
        """Pushes current project state to undo stack and clears redo stack."""
        self.undo_stack.append(self.project.model_copy(deep=True))
        self.redo_stack.clear()

    def _init_actions(self) -> None:
        self.act_import = QAction("&Import Images...", self)
        self.act_import.setShortcut("Ctrl+I")
        self.act_import.triggered.connect(self.import_images)

        self.act_save_proj = QAction("&Save Project...", self)
        self.act_save_proj.setShortcut("Ctrl+S")
        self.act_save_proj.triggered.connect(self.save_project)

        self.act_open_proj = QAction("&Open Project...", self)
        self.act_open_proj.setShortcut("Ctrl+O")
        self.act_open_proj.triggered.connect(self.open_project)

        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self.undo_action)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.triggered.connect(self.redo_action)

        self.act_rotate_l = QAction("Rotate Left", self)
        self.act_rotate_l.setShortcut("Ctrl+L")
        self.act_rotate_l.triggered.connect(self.rotate_left)

        self.act_rotate_r = QAction("Rotate Right", self)
        self.act_rotate_r.setShortcut("Ctrl+R")
        self.act_rotate_r.triggered.connect(self.rotate_right)

        self.act_export = QAction("&Export Document...", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.triggered.connect(self.export_document)

    def _init_toolbar(self) -> None:
        toolbar = QToolBar("Main Operations", self)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_import)
        toolbar.addAction(self.act_open_proj)
        toolbar.addAction(self.act_save_proj)
        toolbar.addSeparator()
        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)
        toolbar.addSeparator()
        toolbar.addAction(self.act_rotate_l)
        toolbar.addAction(self.act_rotate_r)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export)

    def _init_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.act_import)
        file_menu.addAction(self.act_open_proj)
        file_menu.addAction(self.act_save_proj)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export)

        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addAction(self.act_rotate_l)
        edit_menu.addAction(self.act_rotate_r)

    def _init_central_widget(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # 1. Left Thumbnail panel
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Document Pages"))
        self.thumbnail_list = QListWidget(self)
        self.thumbnail_list.currentRowChanged.connect(self.on_page_selected)
        left_layout.addWidget(self.thumbnail_list)
        left_panel.setFixedWidth(200)

        # 2. Central Editor panel
        center_panel = QWidget(self)
        center_layout = QVBoxLayout(center_panel)
        self.corner_editor = CornerEditor(self)
        self.corner_editor.corners_changed.connect(self.on_corners_manually_changed)
        center_layout.addWidget(self.corner_editor)

        # Bottom Central Preview Controls
        preview_ctrls = QHBoxLayout()
        btn_reset_auto = QPushButton("Reset to Auto Detection", self)
        btn_reset_auto.clicked.connect(self.reset_to_auto)
        btn_full_image = QPushButton("Full Image (Safe Fallback)", self)
        btn_full_image.clicked.connect(self.reset_to_full_image)
        preview_ctrls.addWidget(btn_reset_auto)
        preview_ctrls.addWidget(btn_full_image)
        center_layout.addLayout(preview_ctrls)

        # 3. Right Settings panel
        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFixedWidth(300)

        # Scan modes
        mode_group = QGroupBox("Scan Processing Mode", self)
        mode_layout = QVBoxLayout(mode_group)
        self.combo_mode = QComboBox(self)
        for m in ScanMode:
            self.combo_mode.addItem(m.value.replace("_", " ").title(), m)
        self.combo_mode.currentIndexChanged.connect(self.on_settings_changed)
        mode_layout.addWidget(self.combo_mode)
        right_layout.addWidget(mode_group)

        # Advanced adjustment sliders
        sliders_group = QGroupBox("Advanced Adjustments", self)
        sliders_form = QFormLayout(sliders_group)

        self.slider_brightness = QSlider(Qt.Horizontal, self)
        self.slider_brightness.setRange(-100, 100)
        self.slider_brightness.setValue(0)
        self.slider_brightness.valueChanged.connect(self.on_settings_changed)
        sliders_form.addRow("Brightness", self.slider_brightness)

        self.slider_contrast = QSlider(Qt.Horizontal, self)
        self.slider_contrast.setRange(10, 30) # mapped to 0.1 to 3.0
        self.slider_contrast.setValue(10)
        self.slider_contrast.valueChanged.connect(self.on_settings_changed)
        sliders_form.addRow("Contrast", self.slider_contrast)

        self.slider_sharpness = QSlider(Qt.Horizontal, self)
        self.slider_sharpness.setRange(0, 20) # mapped to 0.0 to 2.0
        self.slider_sharpness.setValue(0)
        self.slider_sharpness.valueChanged.connect(self.on_settings_changed)
        sliders_form.addRow("Sharpening", self.slider_sharpness)

        self.slider_saturation = QSlider(Qt.Horizontal, self)
        self.slider_saturation.setRange(0, 20) # mapped to 0.0 to 2.0
        self.slider_saturation.setValue(10)
        self.slider_saturation.valueChanged.connect(self.on_settings_changed)
        sliders_form.addRow("Saturation", self.slider_saturation)

        self.slider_shadow = QSlider(Qt.Horizontal, self)
        self.slider_shadow.setRange(0, 10) # mapped to 0.0 to 1.0
        self.slider_shadow.setValue(5)
        self.slider_shadow.valueChanged.connect(self.on_settings_changed)
        sliders_form.addRow("Shadow Removal", self.slider_shadow)

        right_layout.addWidget(sliders_group)
        right_layout.addStretch()

        # Add everything to main layout
        layout.addWidget(left_panel)
        layout.addWidget(center_panel, stretch=1)
        layout.addWidget(right_panel)

    def _init_statusbar(self) -> None:
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.status.showMessage("Ready. Import photos of documents to begin.")

    # Slots / Callbacks
    @Slot()
    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Document Images",
            "",
            "Images (*.png *.jpg *.jpeg *.tiff *.tif *.bmp *.webp)"
        )
        if not files:
            return

        self._push_history()

        for f in files:
            page_id = f"page-{len(self.project.pages)+1}"
            page = PageProjectSettings(
                id=page_id,
                source_path=f,
                label=Path(f).name
            )
            self.project.pages.append(page)

            # Add to UI thumbnail list
            item = QListWidgetItem(page.label)
            item.setData(Qt.UserRole, page_id)
            self.thumbnail_list.addItem(item)

        # Select first page of imports
        if self.thumbnail_list.count() > 0:
            self.thumbnail_list.setCurrentRow(self.thumbnail_list.count() - len(files))

    @Slot(int)
    def on_page_selected(self, index: int) -> None:
        if index < 0 or index >= len(self.project.pages):
            return

        self.current_page_idx = index
        page = self.project.pages[index]

        # Cancel current active background scanning worker if active
        if self.active_worker:
            self.active_worker.cancel()
            self.active_worker = None

        self.status.showMessage("Scanning & detecting page region in background...")

        # Run detection and enhancement asynchronously
        self.active_worker = ScanWorker(
            source=page.source_path,
            settings=page.settings,
            corners=page.corners
        )
        self.active_worker.finished.connect(self.on_scan_completed)
        self.active_worker.error.connect(self.on_scan_failed)
        self.active_worker.start()

    @Slot(object)
    def on_scan_completed(self, result: ScanResult) -> None:
        self.status.showMessage("Enhancements processed successfully.")

        # Store auto corners if we didn't have any set
        page = self.project.pages[self.current_page_idx]
        if not page.corners:
            page.corners = result.corners

        # Display enhanced image preview in CornerEditor
        # Convert NumPy array (RGB) to QImage, then QPixmap
        h, w, c = result.enhanced_image.shape
        bytes_per_line = c * w
        from PySide6.QtGui import QImage
        qimg = QImage(result.enhanced_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        self.corner_editor.set_image(pixmap, page.corners)

        # Show any warnings from Quality Report
        if result.quality_report.warnings:
            self.status.showMessage(f"Quality Warning: {result.quality_report.warnings[0]}")

    @Slot(str)
    def on_scan_failed(self, error_msg: str) -> None:
        self.status.showMessage(f"Error scanning page: {error_msg}")
        QMessageBox.warning(self, "Scanning Failed", f"An error occurred during scanning:\n{error_msg}")

    @Slot(object)
    def on_corners_manually_changed(self, corners: OrderedCorners) -> None:
        if self.current_page_idx < 0:
            return
        self._push_history()
        self.project.pages[self.current_page_idx].corners = corners
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def on_settings_changed(self) -> None:
        if self.current_page_idx < 0:
            return

        # Fetch values from sliders
        settings = ScanSettings(
            mode=self.combo_mode.currentData(),
            brightness=self.slider_brightness.value() / 100.0,
            contrast=self.slider_contrast.value() / 10.0,
            sharpening_amount=self.slider_sharpness.value() / 10.0,
            saturation=self.slider_saturation.value() / 10.0,
            shadow_removal_strength=self.slider_shadow.value() / 10.0,
        )

        self.project.pages[self.current_page_idx].settings = settings
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def reset_to_auto(self) -> None:
        if self.current_page_idx < 0:
            return
        self._push_history()
        self.project.pages[self.current_page_idx].corners = None
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def reset_to_full_image(self) -> None:
        if self.current_page_idx < 0:
            return
        self._push_history()
        self.project.pages[self.current_page_idx].corners = OrderedCorners(
            top_left=Corner(x=0.0, y=0.0),
            top_right=Corner(x=1.0, y=0.0),
            bottom_right=Corner(x=1.0, y=1.0),
            bottom_left=Corner(x=0.0, y=1.0),
        )
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def rotate_left(self) -> None:
        if self.current_page_idx < 0:
            return
        self._push_history()
        page = self.project.pages[self.current_page_idx]
        page.rotation = (page.rotation + 270) % 360
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def rotate_right(self) -> None:
        if self.current_page_idx < 0:
            return
        self._push_history()
        page = self.project.pages[self.current_page_idx]
        page.rotation = (page.rotation + 90) % 360
        self.on_page_selected(self.current_page_idx)

    @Slot()
    def undo_action(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self.project.model_copy(deep=True))
        self.project = self.undo_stack.pop()
        self.refresh_ui_from_project()

    @Slot()
    def redo_action(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(self.project.model_copy(deep=True))
        self.project = self.redo_stack.pop()
        self.refresh_ui_from_project()

    def refresh_ui_from_project(self) -> None:
        """Re-syncs PySide6 lists and editor states matching the project model."""
        self.thumbnail_list.clear()
        for page in self.project.pages:
            item = QListWidgetItem(page.label)
            item.setData(Qt.UserRole, page.id)
            self.thumbnail_list.addItem(item)
        if len(self.project.pages) > 0:
            self.thumbnail_list.setCurrentRow(0)

    @Slot()
    def save_project(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "PhotoScan Projects (*.photoscan)"
        )
        if not file_path:
            return
        try:
            self.project_store.save_project(self.project, file_path)
            self.status.showMessage(f"Project saved to: {Path(file_path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save project:\n{e}")

    @Slot()
    def open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "PhotoScan Projects (*.photoscan)"
        )
        if not file_path:
            return
        try:
            self.project = self.project_store.load_project(file_path)
            self.refresh_ui_from_project()
            self.status.showMessage(f"Project loaded: {Path(file_path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", f"Could not load project:\n{e}")

    @Slot()
    def export_document(self) -> None:
        if not self.project.pages:
            QMessageBox.warning(self, "Export Failed", "There are no pages to export.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Document",
            "",
            "PDF Document (*.pdf);;PNG Image (*.png);;JPEG Image (*.jpg);;TIFF Image (*.tiff)"
        )
        if not file_path:
            return

        fmt = "PDF"
        if "png" in selected_filter.lower():
            fmt = "PNG"
        elif "jpg" in selected_filter.lower() or "jpeg" in selected_filter.lower():
            fmt = "JPEG"
        elif "tiff" in selected_filter.lower():
            fmt = "TIFF"

        self.status.showMessage("Exporting document...")
        try:
            # Process and collect all pages
            scanner = DocumentScanner()
            scanned_pages = []
            for page in self.project.pages:
                res = scanner.scan(page.source_path, settings=page.settings, corners=page.corners)

                # Apply rotation in result before exporting if needed
                img = res.enhanced_image
                if page.rotation == 90:
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif page.rotation == 180:
                    img = cv2.rotate(img, cv2.ROTATE_180)
                elif page.rotation == 270:
                    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

                scanned_pages.append(img)

            from photoscan.export.exporter import DocumentExporter
            exporter = DocumentExporter()
            if fmt == "PDF" or len(scanned_pages) > 1:
                exporter.export_multipage(scanned_pages, file_path, fmt)
            else:
                exporter.export_single_page(scanned_pages[0], file_path, fmt)

            self.status.showMessage("Document exported successfully!")
            QMessageBox.information(self, "Export Complete", f"Successfully exported scans to:\n{file_path}")
        except Exception as e:
            self.status.showMessage("Export failed.")
            QMessageBox.critical(self, "Export Failed", f"Failed to export scanned pages:\n{e}")

    def closeEvent(self, event) -> None:
        if self.active_worker:
            self.active_worker.cancel()
            self.active_worker.wait()
        event.accept()
