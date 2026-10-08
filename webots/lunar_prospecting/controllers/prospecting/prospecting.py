"""Lunar prospecting controller.

Drive: Sawppy-style 6-wheel, 4-corner steer (ros2_rover vel_parser).
Plan: A* on a blocked grid, lidar slowdown and stop (SJTU planner / detector ideas).
Record: local peaqOS-shaped events. No keys, no chain calls.
"""

from __future__ import annotations

import json
import math
import os
from heapq import heappop, heappush

from controller import Robot

# Sawppy wheel from rover_description/urdf/wheels/wheel.urdf.xacro
WHEEL_RADIUS = 0.06
# Body-scale distances in metres (xacro hardware_distances were centimetres).
TRACK = 0.32
WHEELBASE = 0.44
MAX_STEER = 0.6  # rad, inside the ±pi corner limit in the URDF
MAX_WHEEL_RAD_S = 6.0

CELL = 0.5
GRID_MIN = -10.0
GRID_N = 40

# Circles (x, z, radius) matching the world obstacles.
OBSTACLES = [
    (3.0, 1.0, 1.1),
    (-2.5, 2.5, 0.9),
    (1.5, 5.5, 1.0),
    (-5.0, -1.0, 1.2),
    (6.0, -2.0, 0.8),
]

SAMPLES = [
    ("ilmenite_01", 4.2, 3.2),
    ("ilmenite_02", -3.2, 6.0),
]
LANDER = (0.0, -7.0)

LOG_PATH = os.path.join(os.path.dirname(__file__), "peaq_events.jsonl")


def cell_of(x, z):
    i = int((x - GRID_MIN) / CELL)
    j = int((z - GRID_MIN) / CELL)
    return i, j


def world_of(i, j):
    return GRID_MIN + (i + 0.5) * CELL, GRID_MIN + (j + 0.5) * CELL


def blocked(i, j):
    if i < 1 or j < 1 or i >= GRID_N - 1 or j >= GRID_N - 1:
        return True
    x, z = world_of(i, j)
    for ox, oz, r in OBSTACLES:
        if (x - ox) ** 2 + (z - oz) ** 2 < (r + 0.35) ** 2:
            return True
    return False


def astar(start, goal):
    si, sj = cell_of(*start)
    gi, gj = cell_of(*goal)
    if blocked(gi, gj):
        # Nudge the goal to the nearest free cell.
        best = None
        for di in range(-3, 4):
            for dj in range(-3, 4):
                ni, nj = gi + di, gj + dj
                if not blocked(ni, nj):
                    d = di * di + dj * dj
                    if best is None or d < best[0]:
                        best = (d, ni, nj)
        if best is None:
            return [start, goal]
        gi, gj = best[1], best[2]
    if blocked(si, sj):
        return [start, goal]

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
            if blocked(ni, nj):
                continue
            step = 1.414 if di and dj else 1.0
            ng = gscore[(i, j)] + step
            if ng < gscore.get((ni, nj), 1e9):
                gscore[(ni, nj)] = ng
                came[(ni, nj)] = (i, j)
                h = math.hypot(ni - gi, nj - gj)
                heappush(openq, (ng + h, ni, nj))
    return [start, goal]


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class Prospecting:
    def __init__(self):
        self.robot = Robot()
        self.dt = int(self.robot.getBasicTimeStep())
        self.wheels = []
        for name in (
            "fl_wheel", "ml_wheel", "bl_wheel",
            "fr_wheel", "mr_wheel", "br_wheel",
        ):
            m = self.robot.getDevice(name)
            m.setPosition(float("inf"))
            m.setVelocity(0.0)
            self.wheels.append(m)
        self.steers = [self.robot.getDevice(n) for n in ("fl_steer", "fr_steer", "bl_steer", "br_steer")]
        self.lidar = self.robot.getDevice("lidar")
        self.lidar.enable(self.dt)
        self.lidar.enablePointCloud()
        self.cam = self.robot.getDevice("camera")
        self.cam.enable(self.dt)
        self.cam.recognitionEnable(self.dt)
        self.gps = self.robot.getDevice("gps")
        self.gps.enable(self.dt)
        self.imu = self.robot.getDevice("imu")
        self.imu.enable(self.dt)
        self.goals = list(SAMPLES) + [("lander", LANDER[0], LANDER[1])]
        self.goal_i = 0
        self.path = []
        self.path_i = 0
        self.found = set()
        self.last_pose = None
        self.travelled = 0.0
        self.last_event_m = 0.0
        self._log("machine_online", {"machine_type": "lunar_prospector", "chassis": "sawppy_rocker_bogie"})
        self._replan()

    def _log(self, kind, payload):
        rec = {"event": kind, "payload": payload}
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print("[peaq]", kind, payload)

    def _pose(self):
        x, _, z = self.gps.getValues()
        # Webots IMU yaw is rotation about Y.
        yaw = self.imu.getRollPitchYaw()[2]
        return x, z, yaw

    def _replan(self):
        name, gx, gz = self.goals[self.goal_i]
        x, z, _ = self._pose()
        self.path = astar((x, z), (gx, gz))
        self.path_i = 0
        print("plan to", name, "waypoints", len(self.path))

    def _lidar_stats(self):
        ranges = self.lidar.getRangeImage()
        if not ranges:
            return 99.0, 0
        n = len(ranges)
        mid = n // 2
        front = ranges[mid - 8 : mid + 8]
        finite = [r for r in front if math.isfinite(r) and r > 0.05]
        close = min(finite) if finite else 99.0
        hits = sum(1 for r in ranges if math.isfinite(r) and 0.05 < r < 8.0)
        return close, hits

    def _ackermann(self, v, yaw_rate):
        """Per-wheel rad/s and four corner angles. Middle wheels do not steer."""
        v = max(-0.35, min(0.35, v))
        yaw_rate = max(-0.4, min(0.4, yaw_rate))
        if abs(v) < 0.02 and abs(yaw_rate) < 0.02:
            for w in self.wheels:
                w.setVelocity(0.0)
            for s in self.steers:
                s.setPosition(0.0)
            return
        if abs(v) < 0.05:
            v = 0.05 if yaw_rate >= 0 else -0.05
        kappa = yaw_rate / v
        # Clamp radius so steer stays inside the servo limit.
        if abs(kappa) > 1.6:
            kappa = 1.6 if kappa > 0 else -1.6
        steer = math.atan(WHEELBASE * 0.5 * kappa)
        steer = max(-MAX_STEER, min(MAX_STEER, steer))
        # fl, fr, bl, br. Rear opposite of front (Sawppy corner steer).
        self.steers[0].setPosition(steer)
        self.steers[1].setPosition(steer)
        self.steers[2].setPosition(-steer)
        self.steers[3].setPosition(-steer)
        half = TRACK * 0.5
        # Left side is +x in this model; positive yaw (CCW) speeds the right wheels.
        left = v * (1.0 - half * kappa)
        right = v * (1.0 + half * kappa)
        speeds = [left, left, left, right, right, right]
        for motor, spd in zip(self.wheels, speeds):
            motor.setVelocity(max(-MAX_WHEEL_RAD_S, min(MAX_WHEEL_RAD_S, spd / WHEEL_RADIUS)))

    def _see_samples(self, x, z):
        if not self.cam.hasRecognition():
            return
        for obj in self.cam.getRecognitionObjects():
            name = obj.getModel()
            if not name.startswith("ilmenite"):
                continue
            if name in self.found:
                continue
            # Camera frame: object position is relative. Use GPS proximity instead.
            for sname, sx, sz in SAMPLES:
                if sname == name and math.hypot(x - sx, z - sz) < 1.6:
                    self.found.add(name)
                    self._log("sample_found", {"id": name, "x": round(sx, 2), "z": round(sz, 2)})

    def step(self):
        if self.robot.step(self.dt) == -1:
            return False
        x, z, yaw = self._pose()
        if self.last_pose is not None:
            self.travelled += math.hypot(x - self.last_pose[0], z - self.last_pose[1])
        self.last_pose = (x, z)

        if self.travelled - self.last_event_m > 3.0:
            self.last_event_m = self.travelled
            self._log("traverse", {"x": round(x, 2), "z": round(z, 2), "metres": round(self.travelled, 1)})

        self._see_samples(x, z)

        name, gx, gz = self.goals[self.goal_i]
        if math.hypot(x - gx, z - gz) < 1.3:
            if name == "lander":
                self._log("sample_delivered", {"count": len(self.found), "metres": round(self.travelled, 1)})
                self._ackermann(0.0, 0.0)
                return True
            print("reached", name)
            self.goal_i += 1
            self._replan()
            return True

        close, hits = self._lidar_stats()
        # Feature-poor ground: fewer returns, slower, same idea as vehicle_modify_pts.
        speed_cap = 0.28
        if hits < 40:
            speed_cap = 0.12
        elif hits < 80:
            speed_cap = 0.18
        if close < 0.7:
            self._ackermann(0.0, 0.35 if yaw > 0 else -0.35)
            return True

        if self.path_i >= len(self.path):
            self._replan()
            return True
        tx, tz = self.path[self.path_i]
        if math.hypot(tx - x, tz - z) < 0.45:
            self.path_i += 1
            return True
        desired = math.atan2(tx - x, tz - z)
        err = wrap(desired - yaw)
        v = speed_cap if abs(err) < 0.7 else 0.08
        self._ackermann(v, max(-0.35, min(0.35, 0.8 * err)))
        return True


def main():
    app = Prospecting()
    while app.step():
        pass


if __name__ == "__main__":
    main()
