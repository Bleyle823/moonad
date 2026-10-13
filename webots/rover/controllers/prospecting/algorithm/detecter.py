"""Obstacle and orange-target detector for the 160x120 depth camera and 320x240 RGB."""

from __future__ import annotations

import math

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None


def _rgb_to_hsv_pixel(r, g, b):
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx = max(rf, gf, bf)
    mn = min(rf, gf, bf)
    df = mx - mn
    if df == 0:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / df) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / df) + 120) % 360
    else:
        h = (60 * ((rf - gf) / df) + 240) % 360
    s = 0.0 if mx == 0 else df / mx
    return h, s * 255.0, mx * 255.0


class Detecter(object):
    def __init__(self, width=160, height=120):
        self.width = width
        self.height = height
        self.window_width = min(80, width - 2)
        if self.window_width % 2:
            self.window_width -= 1
        self.window_height = min(50, height - 2)
        if self.window_height % 2:
            self.window_height -= 1
        # Camera pitches down: lower rows are regolith. Obstacles show in the upper band.
        self.band_top = max(0, int(height * 0.12))
        self.band_bottom = max(self.band_top + 4, int(height * 0.48))
        self.threshold_low_detect = 0.32
        self.obstacle_vs_median = 0.82
        self.low_hsv = (0, 80, 80)
        self.high_hsv = (25, 254, 255)

    def detect_targets(self, rgb):
        """Forward RGB only. Returns (found, centroids). rgb is HxWx3 RGB uint8 or nested lists."""
        if rgb is None:
            return False, []
        if cv2 is not None and np is not None:
            arr = np.asarray(rgb, dtype=np.uint8)
            if arr.ndim == 3 and arr.shape[2] >= 3:
                hsv = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2HSV)
                lo = np.array(self.low_hsv, dtype=np.uint8)
                hi = np.array(self.high_hsv, dtype=np.uint8)
                mask = cv2.inRange(hsv, lo, hi)
                if mask.sum() == 0:
                    return False, []
                k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
                mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open), cv2.MORPH_CLOSE, k_close)
                _n, _lab, _st, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
                cents = []
                for c in centroids[1:]:
                    cents.append((int(c[0]), int(c[1])))
                return len(cents) > 0, cents
        hits = 0
        h = len(rgb)
        w = len(rgb[0]) if h else 0
        for y in range(0, h, 4):
            row = rgb[y]
            for x in range(0, w, 4):
                pix = row[x]
                r, g, b = int(pix[0]), int(pix[1]), int(pix[2])
                hh, ss, vv = _rgb_to_hsv_pixel(r, g, b)
                if self.low_hsv[0] <= hh <= self.high_hsv[0] and ss >= self.low_hsv[1] and vv >= self.low_hsv[2]:
                    hits += 1
        return hits > 12, []

    def detect_obstacles(self, depth):
        """depth: flat list or 2d of metres. Returns (hit, min_depth)."""
        if not depth:
            return False, -1.0
        if np is not None:
            arr = np.asarray(depth, dtype=float).reshape(-1)
            if arr.size >= self.width * self.height:
                arr = arr[: self.width * self.height].reshape(self.height, self.width)
            else:
                n = int(math.sqrt(arr.size))
                arr = arr[: n * n].reshape(n, n)
            hx = self.window_width // 2
            mid = arr.shape[1] // 2
            x0 = max(0, mid - hx)
            x1 = min(arr.shape[1], mid + hx)
            y0 = min(self.band_top, arr.shape[0] - 1)
            y1 = min(self.band_bottom, arr.shape[0])
            win = arr[y0:y1, x0:x1]
            finite = win[np.isfinite(win) & (win > 0.2)]
            if finite.size < 8:
                return False, -1.0
            close = float(finite.min())
            med = float(np.median(finite))
            if close < self.threshold_low_detect:
                return True, close
            if close < 0.55 and close < med * self.obstacle_vs_median:
                return True, close
            return False, close
        vals = []
        if isinstance(depth[0], (list, tuple)):
            rows = depth
        else:
            rows = []
            w = self.width
            for i in range(0, min(len(depth), self.width * self.height), w):
                rows.append(depth[i : i + w])
        hx = self.window_width // 2
        y0 = min(self.band_top, len(rows) - 1)
        y1 = min(self.band_bottom, len(rows))
        mid = len(rows[0]) // 2 if rows and rows[0] else 0
        for y in range(y0, y1):
            row = rows[y]
            for x in range(max(0, mid - hx), min(len(row), mid + hx)):
                d = row[x]
                if d is None:
                    continue
                try:
                    fd = float(d)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(fd) and fd > 0.15:
                    vals.append(fd)
        if len(vals) < 8:
            return False, -1.0
        close = min(vals)
        med = sorted(vals)[len(vals) // 2]
        if close < self.threshold_low_detect:
            return True, close
        if close < 0.55 and close < med * self.obstacle_vs_median:
            return True, close
        return False, close
