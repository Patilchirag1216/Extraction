"""OpenCV based image loading and preprocessing."""
from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np

from . import config


def load_image(path: str) -> np.ndarray:
    """Load an image from disk as a BGR numpy array.

    Raises FileNotFoundError for a missing file and ValueError when the file
    is not a decodable image.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")
    # cv2.imread does not handle unicode paths on Windows reliably; use
    # imdecode with a byte buffer instead.
    with open(path, "rb") as fh:
        buf = np.frombuffer(fh.read(), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not decode image: {path}")
    return img


def decode_image(data: bytes) -> np.ndarray:
    """Decode raw image bytes to a BGR numpy array."""
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    return img


def encode_png(image: np.ndarray) -> bytes:
    """Encode a BGR image as PNG bytes (for previews)."""
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode image")
    return buf.tobytes()


def estimate_skew_angle(image: np.ndarray) -> float:
    """Estimate the small skew angle (degrees) of a document image."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Ignore near-90 rotations (portrait text detection noise).
    if abs(angle) > 20:
        return 0.0
    return float(angle)


def rotate_bound(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate an image by ``angle`` degrees without cropping the content."""
    if abs(angle) < 0.1:
        return image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(m[0, 0])
    sin = abs(m[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    m[0, 2] += (new_w / 2) - center[0]
    m[1, 2] += (new_h / 2) - center[1]
    return cv2.warpAffine(
        image, m, (new_w, new_h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )


def _upscale_if_small(image: np.ndarray, min_width: int, max_factor: float) -> np.ndarray:
    h, w = image.shape[:2]
    if w >= min_width:
        return image
    factor = min(max_factor, min_width / float(w))
    if factor <= 1.0:
        return image
    return cv2.resize(
        image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC
    )


def _increase_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _denoise(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)


def _sharpen(image: np.ndarray) -> np.ndarray:
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, kernel)


def preprocess(
    image: np.ndarray,
    upscale: bool = True,
    denoise: bool = False,
    contrast: bool = True,
    sharpen: bool = True,
    deskew: bool = True,
) -> np.ndarray:
    """Apply the requested preprocessing steps and return a new BGR image.

    The defaults are conservative: they help OCR on small / low-contrast
    phone photos without destroying fine print.
    """
    out = image.copy()
    if upscale:
        out = _upscale_if_small(
            out, config.PREPROC_UPSCALE_MIN_WIDTH, config.PREPROC_UPSCALE_MAX_FACTOR
        )
    if denoise:
        out = _denoise(out)
    if contrast:
        out = _increase_contrast(out)
    if sharpen:
        out = _sharpen(out)
    if deskew:
        angle = estimate_skew_angle(out)
        if abs(angle) >= 0.5:
            out = rotate_bound(out, angle)
    return out


def downscale_for_preview(image: np.ndarray, max_width: int = 900) -> np.ndarray:
    """Downscale an image so it fits comfortably in the browser."""
    h, w = image.shape[:2]
    if w <= max_width:
        return image
    factor = max_width / float(w)
    return cv2.resize(
        image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_AREA
    )
