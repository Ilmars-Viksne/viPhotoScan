from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from photoscan.application.api import DocumentScanner
from photoscan.domain.models import OrderedCorners, ScanSettings


class ScanWorker(QThread):
    """
    Background worker thread to run CPU-intensive document scans,
    warping, and enhancements without freezing the PySide6 UI.
    """
    progress = Signal(int)
    finished = Signal(object)  # ScanResult on success
    error = Signal(str)

    def __init__(
        self,
        source: Path | str | np.ndarray,
        settings: ScanSettings,
        corners: OrderedCorners | None = None,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.settings = settings
        self.corners = corners
        self._is_cancelled = False

    def cancel(self) -> None:
        """Flags the thread for cancellation."""
        self._is_cancelled = True

    def run(self) -> None:
        if self._is_cancelled:
            self.finished.emit(None)
            return

        self.progress.emit(20)
        try:
            scanner = DocumentScanner()
            if self._is_cancelled:
                self.finished.emit(None)
                return

            self.progress.emit(50)
            result = scanner.scan(self.source, settings=self.settings, corners=self.corners)

            if self._is_cancelled:
                self.finished.emit(None)
                return

            self.progress.emit(100)
            self.finished.emit(result)
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))
            else:
                self.finished.emit(None)
