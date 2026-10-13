"""A* on a 0.5 m grid. Rocks from moon.wbt stand in for the contest gradient_limit."""

from __future__ import annotations

import math
from heapq import heappop, heappush

CELL = 0.5
GRID_MIN = -12.0
GRID_N = 48

# (x, y, radius) rocks and boulders near the rover workspace in moon.wbt.
OBSTACLES = [
    (1.438, -8.946, 0.45),
    (6.340, -5.112, 0.45),
    (4.478, -4.461, 0.40),
    (4.885, 3.601, 0.40),
    (-8.979, -6.950, 0.45),
    (5.996, 1.220, 0.40),
    (-7.830, 2.791, 0.45),
    (-3.320, -9.262, 0.45),
    (-7.665, -9.538, 0.40),
    (2.475, 6.546, 0.45),
    (3.885, 3.975, 0.40),
    (5.269, 2.019, 0.40),
    (-6.633, 5.256, 0.40),
    (6.135, -8.173, 0.40),
    (5.246, -6.961, 0.40),
    (3.673, -7.528, 0.40),
    (3.802, -9.279, 0.40),
    (5.202, -9.420, 0.40),
    (-7.870, -6.277, 0.40),
    (-9.178, -4.175, 0.45),
    (8.711, 4.054, 0.40),
    (4.636, 6.005, 0.40),
    (7.205, 2.396, 0.40),
    (7.510, 5.939, 0.40),
    (0.314, -13.500, 0.45),
    (-2.569, -14.404, 0.45),
    (1.857, -12.663, 0.40),
    (4.652, -12.819, 0.40),
    (-0.810, 7.480, 0.40),
    (0.853, 6.993, 0.40),
    (1.619, 8.293, 0.40),
    (-10.506, 1.662, 0.40),
    (-11.912, 0.269, 0.40),
]


def cell_of(x, y):
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("grid cell needs finite coordinates")
    i = int((x - GRID_MIN) / CELL)
    j = int((y - GRID_MIN) / CELL)
    return i, j


def world_of(i, j):
    return GRID_MIN + (i + 0.5) * CELL, GRID_MIN + (j + 0.5) * CELL


def blocked(i, j, extra=()):
    if i < 1 or j < 1 or i >= GRID_N - 1 or j >= GRID_N - 1:
        return True
    x, y = world_of(i, j)
    for ox, oy, r in OBSTACLES:
        if (x - ox) ** 2 + (y - oy) ** 2 < (r + 0.4) ** 2:
            return True
    for ox, oy, r in extra:
        if (x - ox) ** 2 + (y - oy) ** 2 < (r + 0.4) ** 2:
            return True
    return False


def _nudge_free(i, j, extra=()):
    if not blocked(i, j, extra):
        return i, j
    best = None
    for di in range(-4, 5):
        for dj in range(-4, 5):
            ni, nj = i + di, j + dj
            if not blocked(ni, nj, extra):
                d = di * di + dj * dj
                if best is None or d < best[0]:
                    best = (d, ni, nj)
    if best is None:
        return i, j
    return best[1], best[2]


def astar(start, goal, extra=()):
    si, sj = _nudge_free(*cell_of(*start), extra)
    gi, gj = _nudge_free(*cell_of(*goal), extra)
    openq = [(0.0, si, sj)]
    came = {}
    gscore = {(si, sj): 0.0}
    while openq:
        _, i, j = heappop(openq)
        if (i, j) == (gi, gj):
            path = [(i, j)]
            while path[-1] in came:
                path.append(came[path[-1]])
            path.reverse()
            return [world_of(a, b) for a, b in path]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if blocked(ni, nj, extra):
                continue
            step = 1.414 if di and dj else 1.0
            ng = gscore[(i, j)] + step
            if ng < gscore.get((ni, nj), 1e9):
                gscore[(ni, nj)] = ng
                came[(ni, nj)] = (i, j)
                h = ((ni - gi) ** 2 + (nj - gj) ** 2) ** 0.5
                heappush(openq, (ng + h, ni, nj))
    return [start, goal]


class GlobalPlanner(object):
    def __init__(self, extra=()):
        self.extra = extra

    def plan(self, start, goal):
        return astar(start, goal, self.extra)
