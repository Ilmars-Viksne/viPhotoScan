import contextlib
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from photoscan.domain.exceptions import DecodeFailureError, InvalidImageError, UnsupportedInputError

# Limit decompression bomb size: 100 megapixels max
MAX_IMAGE_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

def load_image_to_rgb(image_path_or_bytes: Path | str | bytes) -> np.ndarray:
    """
    Loads an image from a path or raw bytes, normalizes the EXIF orientation,
    and returns a NumPy array in RGB format.
    Raises UnsupportedInputError or DecodeFailureError on invalid image data.
    """
    try:
        if isinstance(image_path_or_bytes, bytes):
            stream = io.BytesIO(image_path_or_bytes)
            pil_img = Image.open(stream)
        else:
            path = Path(image_path_or_bytes)
            if not path.exists():
                raise UnsupportedInputError(f"File not found: {path}")
            pil_img = Image.open(path)

        pil_img.load()  # Force loading of image data to trigger decompression checks
    except Image.DecompressionBombError as e:
        raise InvalidImageError(f"Decompression bomb detected: {e}") from e
    except Exception as e:
        if isinstance(e, UnsupportedInputError):
            raise
        raise DecodeFailureError(f"Failed to decode image: {e}") from e

    # Validate image dimensions
    w, h = pil_img.size
    if w * h > MAX_IMAGE_PIXELS:
        raise InvalidImageError(f"Image dimension exceeds limit of {MAX_IMAGE_PIXELS} pixels: {w}x{h}")
    if w == 0 or h == 0:
        raise InvalidImageError(f"Image has degenerate dimensions: {w}x{h}")

    # Normalize EXIF orientation
    with contextlib.suppress(Exception):
        pil_img = ImageOps.exif_transpose(pil_img)

    # Ensure format is RGB
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    return np.array(pil_img)
