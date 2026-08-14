import contextlib
import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from photoscan.domain.exceptions import ExportFailureError, InvalidImageError


class DocumentExporter:
    """
    Handles high-quality transactional exports to PNG, JPEG, TIFF, and PDF.
    Guarantees atomic file operations so failed exports never leave corrupted files.
    """

    def export_single_page(
        self,
        rgb_array: np.ndarray,
        destination: Path | str,
        format_name: str,
        dpi: int = 300,
        jpeg_quality: int = 90,
        grayscale: bool = False
    ) -> None:
        """
        Exports a single page to the requested destination using transactional logic.
        """
        dest_path = Path(destination)
        # Check parent directory permissions
        if not dest_path.parent.exists():
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ExportFailureError(f"Cannot create destination directory: {e}") from e

        # Create PIL Image
        pil_img = Image.fromarray(rgb_array)
        if grayscale:
            pil_img = pil_img.convert("L")

        # Determine save parameters
        save_params = {}
        fmt = format_name.upper()
        if fmt in ["JPEG", "JPG"]:
            save_params["quality"] = jpeg_quality
            save_params["dpi"] = (dpi, dpi)
            fmt = "JPEG"
        elif fmt == "PNG":
            save_params["dpi"] = (dpi, dpi)
            save_params["optimize"] = True
        elif fmt in ["TIFF", "TIF"]:
            save_params["dpi"] = (dpi, dpi)
            # Use TIFF compression (LZW)
            save_params["compression"] = "tiff_lzw"
            fmt = "TIFF"
        elif fmt == "PDF":
            save_params["resolution"] = float(dpi)
            fmt = "PDF"
        else:
            raise ExportFailureError(f"Unsupported export format: {format_name}")

        # Write to temporary file first (transactional export)
        # Use same directory to ensure atomic os.replace is on the same volume
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dest_path.parent,
                suffix=f".tmp.{format_name.lower()}",
                delete=False
            ) as tmp:
                temp_file = Path(tmp.name)

            # Save image to temp file
            pil_img.save(temp_file, format=fmt, **save_params)

            # Validate generated output
            self._validate_file(temp_file, fmt)

            # Atomic rename / replace
            os.replace(temp_file, dest_path)

        except Exception as e:
            # Clean up temp file if something failed
            if temp_file and temp_file.exists():
                with contextlib.suppress(Exception):
                    temp_file.unlink()
            raise ExportFailureError(f"Failed to export page: {e}") from e

    def export_multipage(
        self,
        rgb_arrays: list[np.ndarray],
        destination: Path | str,
        format_name: str,
        dpi: int = 300,
        jpeg_quality: int = 90
    ) -> None:
        """
        Exports multiple pages into a single multipage document (TIFF or PDF) transactionally.
        """
        if not rgb_arrays:
            raise ExportFailureError("Cannot export empty page list.")

        dest_path = Path(destination)
        if not dest_path.parent.exists():
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ExportFailureError(f"Cannot create destination directory: {e}") from e

        fmt = format_name.upper()
        if fmt not in ["PDF", "TIFF", "TIF"]:
            raise ExportFailureError(f"Multipage export not supported for format: {format_name}")

        pil_images = [Image.fromarray(arr) for arr in rgb_arrays]
        first_img = pil_images[0]
        other_imgs = pil_images[1:]

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dest_path.parent,
                suffix=f".tmp.{format_name.lower()}",
                delete=False
            ) as tmp:
                temp_file = Path(tmp.name)

            if fmt == "PDF":
                first_img.save(
                    temp_file,
                    format="PDF",
                    resolution=float(dpi),
                    save_all=True,
                    append_images=other_imgs
                )
            else:  # TIFF
                first_img.save(
                    temp_file,
                    format="TIFF",
                    dpi=(dpi, dpi),
                    compression="tiff_lzw",
                    save_all=True,
                    append_images=other_imgs
                )

            # Validate
            self._validate_file(temp_file, fmt)

            # Atomic replacement
            os.replace(temp_file, dest_path)

        except Exception as e:
            if temp_file and temp_file.exists():
                with contextlib.suppress(Exception):
                    temp_file.unlink()
            raise ExportFailureError(f"Failed to export multipage document: {e}") from e

    def _validate_file(self, file_path: Path, format_name: str) -> None:
        """
        Validates that the exported file is well-formed.
        """
        if not file_path.exists():
            raise InvalidImageError("Exported file does not exist.")

        size = file_path.stat().st_size
        if size == 0:
            raise InvalidImageError("Exported file is empty (0 bytes).")

        # For PDF/TIFF/JPEG/PNG, try opening with Pillow to verify headers are intact
        if format_name in ["JPEG", "PNG", "TIFF", "TIF"]:
            try:
                with Image.open(file_path) as img:
                    img.verify()
            except Exception as e:
                raise InvalidImageError(f"Generated image is corrupt: {e}") from e
        elif format_name == "PDF":
            # Just do basic check of file headers: %PDF-
            try:
                with open(file_path, "rb") as f:
                    header = f.read(5)
                    if header != b"%PDF-":
                        raise InvalidImageError("Generated PDF does not start with standard PDF header.")
            except Exception as e:
                raise InvalidImageError(f"Generated PDF header check failed: {e}") from e
