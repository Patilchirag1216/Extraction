"""Local OCR engine built on PaddleOCR.

Important: some PaddlePaddle 3.x builds crash on Windows/CPU when the MKLDNN
(MKL-DNN) run mode is selected through the PaddleX inference pipeline
(``ConvertPirAttribute2RuntimeAttribute not support`` error).  Disabling the
"mkldnn by default" flag forces the plain ``paddle`` run mode which is stable.
The environment variables must be set *before* importing paddleocr, therefore
they are assigned at the very top of this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from . import config

for _k, _v in config.PADDLE_ENV_DEFAULTS.items():
    os.environ.setdefault(_k, _v)

import numpy as np  # noqa: E402

# Imported lazily so a missing install produces a friendly message rather than
# crashing the whole application at import time.
_PADDLE_OCR_CLS = None
_IMPORT_ERROR: Optional[str] = None


def _import_paddleocr():
    global _PADDLE_OCR_CLS, _IMPORT_ERROR
    if _PADDLE_OCR_CLS is not None:
        return _PADDLE_OCR_CLS
    if _IMPORT_ERROR is not None:
        raise RuntimeError(_IMPORT_ERROR)
    try:
        from paddleocr import PaddleOCR  # type: ignore

        _PADDLE_OCR_CLS = PaddleOCR
        return _PADDLE_OCR_CLS
    except Exception as exc:  # pragma: no cover - environment specific
        _IMPORT_ERROR = (
            "PaddleOCR could not be imported. Make sure it is installed in the "
            f"active environment (pip install paddleocr paddlepaddle). Details: {exc}"
        )
        raise RuntimeError(_IMPORT_ERROR)


@dataclass
class OCRBox:
    """A single detected text region with geometry and confidence."""

    text: str
    score: float
    box: List[List[float]]  # 4 corner points [[x, y], ...]

    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0
    cx: float = 0.0
    cy: float = 0.0
    height: float = 0.0
    width: float = 0.0

    def __post_init__(self) -> None:
        pts = np.asarray(self.box, dtype=float).reshape(-1, 2)
        xs, ys = pts[:, 0], pts[:, 1]
        self.x_min = float(xs.min())
        self.x_max = float(xs.max())
        self.y_min = float(ys.min())
        self.y_max = float(ys.max())
        self.cx = float((self.x_min + self.x_max) / 2.0)
        self.cy = float((self.y_min + self.y_max) / 2.0)
        self.width = float(self.x_max - self.x_min)
        self.height = float(self.y_max - self.y_min)


class OCREngine:
    """Thin, cached wrapper around PaddleOCR."""

    def __init__(self, lang: str = config.OCR_LANG):
        self.lang = lang
        self._ocr = None

    def _ensure(self):
        if self._ocr is None:
            cls = _import_paddleocr()
            self._ocr = cls(
                lang=self.lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._ocr

    def warm_up(self) -> None:
        """Instantiate the underlying model (downloads weights on first use)."""
        self._ensure()

    def detect(self, image: np.ndarray) -> List[OCRBox]:
        """Run OCR on a BGR image and return a flat list of :class:`OCRBox`."""
        ocr = self._ensure()
        results = ocr.predict(image)
        boxes: List[OCRBox] = []
        for page in results or []:
            boxes.extend(_boxes_from_page(page))
        return boxes


def _boxes_from_page(page) -> List[OCRBox]:
    """Convert one PaddleOCR result page into :class:`OCRBox` objects."""
    texts = _get(page, "rec_texts") or []
    scores = _get(page, "rec_scores") or []
    polys = _get(page, "rec_polys")
    rects = _get(page, "rec_boxes")
    n = len(texts)
    out: List[OCRBox] = []
    for i in range(n):
        text = (texts[i] or "").strip()
        if not text:
            continue
        score = float(scores[i]) if i < len(scores) else 0.0
        poly = None
        if polys is not None and i < len(polys):
            poly = np.asarray(polys[i], dtype=float).tolist()
        elif rects is not None and i < len(rects):
            x0, y0, x1, y1 = [float(v) for v in np.asarray(rects[i]).reshape(-1)[:4]]
            poly = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        if not poly:
            continue
        out.append(OCRBox(text=text, score=score, box=poly))
    return out


def _get(page, key):
    """Safely read a key from a PaddleOCR page which may be dict-like."""
    try:
        if hasattr(page, "get"):
            return page.get(key)
        return page[key]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_ENGINE: Optional[OCREngine] = None


def get_engine(lang: str = config.OCR_LANG) -> OCREngine:
    global _ENGINE
    if _ENGINE is None or _ENGINE.lang != lang:
        _ENGINE = OCREngine(lang=lang)
    return _ENGINE


def reset_engine() -> None:
    global _ENGINE
    _ENGINE = None


def simple_ocr(image_path_or_array) -> List[OCRBox]:
    """Convenience helper used by the test scripts."""
    from . import preprocessing

    if isinstance(image_path_or_array, (str, bytes, os.PathLike)):
        image = preprocessing.load_image(str(image_path_or_array))
    else:
        image = image_path_or_array
    return get_engine().detect(image)
