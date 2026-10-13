"""Forward-camera feature count and track ratio for the speed policy.

GPS is the pose used for the path. This module only measures how rich the view is.
Intrinsics match the Sawppy Camera: 320x240, fieldOfView 1.0472.
"""

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


class Odometer(object):
    def __init__(self, width=320, height=240, fov=1.0472):
        self.width = width
        self.height = height
        fx = (0.5 * width) / math.tan(0.5 * fov)
        self.K = None
        if np is not None:
            self.K = np.array([[fx, 0.0, width * 0.5], [0.0, fx, height * 0.5], [0.0, 0.0, 1.0]])
        self.feature_params = dict(maxCorners=200, qualityLevel=0.02, minDistance=6, blockSize=5)
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=3,
            criteria=(3, 20, 0.03) if cv2 is None else (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )
        self.prev_gray = None
        self.kp = None
        self.pts_count = 0

    def _gray(self, rgb):
        if rgb is None:
            return None
        if np is not None:
            arr = np.asarray(rgb)
            if arr.ndim == 3:
                if arr.shape[0] == self.width and arr.shape[1] == self.height:
                    arr = arr.transpose(1, 0, 2)
                return (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype("uint8")
            return arr.astype("uint8")
        h = len(rgb)
        w = len(rgb[0]) if h else 0
        out = []
        for y in range(h):
            row = rgb[y]
            line = []
            for x in range(w):
                p = row[x]
                line.append(int(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]))
            out.append(line)
        return out

    def update(self, rgb):
        """Returns (pts_count, track_ratio)."""
        gray = self._gray(rgb)
        if gray is None:
            return 0, 100.0
        if cv2 is not None and np is not None:
            g = np.asarray(gray, dtype=np.uint8)
            pts = cv2.goodFeaturesToTrack(g, mask=None, **self.feature_params)
            count = 0 if pts is None else int(len(pts))
            ratio = 100.0
            if self.prev_gray is not None and self.kp is not None and len(self.kp) >= 8:
                nxt, status, _err = cv2.calcOpticalFlowPyrLK(self.prev_gray, g, self.kp, None, **self.lk_params)
                if nxt is not None and status is not None:
                    good = int(status.reshape(-1).sum())
                    ratio = round(100.0 * good / max(len(self.kp), 1), 2)
            self.prev_gray = g
            self.kp = pts
            self.pts_count = count
            return count, ratio
        count = self._edge_count(gray)
        ratio = 100.0
        if self.prev_gray is not None:
            ratio = self._sad_ratio(self.prev_gray, gray)
        self.prev_gray = gray
        self.pts_count = count
        return count, ratio

    def _edge_count(self, gray):
        if np is not None:
            g = np.asarray(gray, dtype=float)
            dx = np.abs(g[:, 1:] - g[:, :-1])
            dy = np.abs(g[1:, :] - g[:-1, :])
            return int(((dx > 18).sum() + (dy > 18).sum()) / 40)
        n = 0
        h = len(gray)
        w = len(gray[0]) if h else 0
        for y in range(1, h, 2):
            for x in range(1, w, 2):
                if abs(gray[y][x] - gray[y][x - 1]) > 18:
                    n += 1
        return n

    def _sad_ratio(self, a, b):
        if np is not None:
            aa = np.asarray(a, dtype=float)
            bb = np.asarray(b, dtype=float)
            if aa.shape != bb.shape:
                return 50.0
            diff = np.mean(np.abs(aa - bb))
            return max(0.0, min(100.0, 100.0 - diff))
        return 70.0
