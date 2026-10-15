"""Drawing helpers used to overlay OCR results on the original card."""
from __future__ import annotations

from typing import List, Sequence

import cv2
import numpy as np


def draw_boxes(image: np.ndarray, boxes, highlight=None) -> np.ndarray:
    """Return a copy of ``image`` with OCR polygons drawn on top.

    ``boxes`` is a sequence of objects exposing ``box`` (4 points) and ``text``.
    ``highlight`` may be a set/list of indices to draw in a different colour.
    """
    out = image.copy()
    highlight = set(highlight or [])
    for idx, b in enumerate(boxes):
        pts = np.asarray(b.box, dtype=np.int32).reshape(-1, 1, 2)
        color = (0, 140, 255) if idx in highlight else (60, 180, 75)
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
    return out


def draw_lines(image: np.ndarray, lines, colour=(220, 40, 40)) -> np.ndarray:
    out = image.copy()
    for ln in lines:
        cv2.rectangle(
            out,
            (int(ln.x_min), int(ln.y_min)),
            (int(ln.x_max), int(ln.y_max)),
            colour,
            2,
        )
    return out
