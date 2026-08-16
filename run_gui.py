import sys

from PySide6.QtWidgets import QApplication

from photoscan.gui.main_window import PhotoScanWindow


def main():
    app = QApplication(sys.argv)
    window = PhotoScanWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()