"""Sawppy prospecting controller.

Drive: Sawppy 6-wheel, 4-corner steer (sawppy_drive).
Plan: A* around rocks, slow down when the view is poor, stop on close depth.
Record: local peaqOS-shaped events. No keys, no chain calls.
"""

from __future__ import annotations

import json
import math
import os
import sys

from controller import Robot

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "sawppy_drive"))
sys.path.insert(0, _HERE)

from sawppy_drive import (  # noqa: E402
    CORNERS,
    MAX_WHEEL,
    MID_TORQUE,
    MIDS,
    MIN_TURN,
    PASSIVE,
    WHEELS,
    calculate_target_deg,
    calculate_velocity,
)

from algorithm.global_planner import GlobalPlanner  # noqa: E402
from algorithm.vehicle import Vehicle  # noqa: E402

SAMPLES = [
    ("sample_ilmenite", 1.8, -4.0),
    ("sample_ilmenite_02", 1.0, 2.2),
    ("sample_ilmenite_03", -4.5, 1.2),
]
LANDER = ("lander_pad", -5.2, -2.4)
LOG_PATH = os.path.join(_HERE, "peaq_events.jsonl")


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _finite(*vals):
    return all(math.isfinite(v) for v in vals)


def _device(robot, name):
    try:
        return robot.getDevice(name)
    except Exception:
        return None


class Prospecting:
    def __init__(self):
        self.robot = Robot()
        self.dt = int(self.robot.getBasicTimeStep())
        self.wheels = []
        for name in WHEELS:
            motor = self.robot.getDevice(name)
            motor.setPosition(float("inf"))
            motor.setVelocity(0.0)
            self.wheels.append(motor)
        self.corners = [self.robot.getDevice(name) for name in CORNERS]
        for name in PASSIVE:
            joint = _device(self.robot, name)
            if joint is not None:
                try:
                    joint.setAvailableTorque(0.0)
                except Exception:
                    pass
        self.lidar = _device(self.robot, "lidar")
        if self.lidar is not None:
            self.lidar.enable(self.dt)
        self.camera = _device(self.robot, "camera")
        if self.camera is not None:
            self.camera.enable(self.dt * 8)
            try:
                self.camera.recognitionEnable(self.dt * 8)
            except Exception:
                pass
        self.gps = _device(self.robot, "gps")
        if self.gps is not None:
            self.gps.enable(self.dt)
        self.imu = _device(self.robot, "imu")
        if self.imu is not None:
            self.imu.enable(self.dt)

        self.vehicle = Vehicle()
        self.planner = GlobalPlanner()
        self.goals = list(SAMPLES) + [LANDER]
        self.goals_sorted = False
        self.goal_i = 0
        self.path = []
        self.path_i = 0
        self.found = set()
        self.last_pose = None
        self.travelled = 0.0
        self.last_event_m = 0.0
        self.avoid_until = 0
        self.avoid_spins = 0
        self.tick = 0
        self._log("machine_online", {"machine_type": "lunar_prospector", "chassis": "sawppy_rocker_bogie"})

    def _log(self, kind, payload):
        rec = {"event": kind, "payload": payload}
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print("[peaq]", kind, payload)

    def _pose(self):
        if self.gps is None:
            return 0.0, 0.0, 0.0
        x, y, _z = self.gps.getValues()
        yaw = 0.0
        if self.imu is not None:
            yaw = self.imu.getRollPitchYaw()[2]
        return x, y, yaw

    def _replan(self):
        name, gx, gy = self.goals[self.goal_i]
        x, y, _ = self._pose()
        if not _finite(x, y):
            return False
        if not self.goals_sorted:
            samples = [g for g in self.goals if g[0] != "lander_pad"]
            lander = [g for g in self.goals if g[0] == "lander_pad"]
            samples.sort(key=lambda g: math.hypot(g[1] - x, g[2] - y))
            self.goals = samples + lander
            self.goals_sorted = True
            self.goal_i = 0
            name, gx, gy = self.goals[0]
        self.path = self.planner.plan((x, y), (gx, gy))
        self.path_i = 0
        print("plan to", name, "waypoints", len(self.path))
        return True

    def _lidar_close(self):
        if self.lidar is None:
            return 99.0
        try:
            ranges = self.lidar.getRangeImage()
        except Exception:
            return 99.0
        if not ranges:
            return 99.0
        n = len(ranges)
        mid = n // 2
        front = ranges[mid - 10 : mid + 10]
        finite = [r for r in front if math.isfinite(r) and r > 0.08]
        return min(finite) if finite else 99.0

    def _apply(self, linear, angular):
        turning = abs(angular) > MIN_TURN
        speeds = calculate_velocity(linear, angular)
        degrees = calculate_target_deg(angular)
        for motor, cmd in zip(self.wheels, speeds):
            rad_s = (cmd / 100.0) * MAX_WHEEL
            if motor.getName().endswith("right_wheel_joint"):
                rad_s = -rad_s
            if motor.getName() in MIDS:
                try:
                    motor.setAvailableTorque(0.0 if turning else MID_TORQUE)
                except Exception:
                    pass
            motor.setVelocity(max(-8.0, min(8.0, rad_s)))
        for motor, deg in zip(self.corners, degrees):
            motor.setPosition(max(-1.2, min(1.2, math.radians(deg))))

    def _see_samples(self, x, y):
        rec_names = []
        if self.camera is not None:
            try:
                for obj in self.camera.getRecognitionObjects():
                    rec_names.append(obj.getModel() or "")
            except Exception:
                pass
        for sname, sx, sy in SAMPLES:
            if sname in self.found:
                continue
            dist = math.hypot(x - sx, y - sy)
            if dist > 1.6:
                continue
            named = any(sname in n or "ilmenite" in n.lower() for n in rec_names)
            if named or dist < 1.2:
                self.found.add(sname)
                self._log("sample_found", {"id": sname, "x": round(sx, 2), "y": round(sy, 2)})

    def step(self):
        if self.robot.step(self.dt) == -1:
            return False
        self.tick += 1
        x, y, yaw = self._pose()
        if not _finite(x, y, yaw):
            self._apply(0.0, 0.0)
            return True
        if not self.path:
            self._replan()
            self._apply(0.0, 0.0)
            return True
        if self.last_pose is not None and _finite(self.last_pose[0], self.last_pose[1]):
            self.travelled += math.hypot(x - self.last_pose[0], y - self.last_pose[1])
        self.last_pose = (x, y)

        if self.travelled - self.last_event_m > 3.0:
            self.last_event_m = self.travelled
            self._log("traverse", {"x": round(x, 2), "y": round(y, 2), "metres": round(self.travelled, 1)})

        if self.tick % 8 == 0:
            self._see_samples(x, y)

        name, gx, gy = self.goals[self.goal_i]
        if math.hypot(x - gx, y - gy) < 1.3:
            if name == "lander_pad":
                self._log("sample_delivered", {"count": len(self.found), "metres": round(self.travelled, 1)})
                self._apply(0.0, 0.0)
                return True
            print("reached", name)
            self.goal_i += 1
            self._replan()
            return True

        lidar_close = self._lidar_close()
        if lidar_close < 0.5 and self.tick > self.avoid_until:
            print("obstacle lidar", round(lidar_close, 2), "replan")
            self._replan()
            self.avoid_until = self.tick + 90
            self.avoid_spins = 20
            self._apply(28.0, 50.0 if yaw >= 0 else -50.0)
            return True
        if self.avoid_spins > 0:
            self.avoid_spins -= 1
            self._apply(28.0, 50.0 if yaw >= 0 else -50.0)
            return True

        if self.path_i >= len(self.path):
            self._replan()
        else:
            tx, ty = self.path[self.path_i]
            if math.hypot(tx - x, ty - y) < 0.45:
                self.path_i += 1
                if self.path_i >= len(self.path):
                    self._replan()
        if self.path_i < len(self.path):
            tx, ty = self.path[self.path_i]
            desired = math.atan2(ty - y, tx - x)
            err = wrap(desired - yaw)
            linear, angular = self.vehicle.sawppy_command(err)
            self._apply(linear, angular)
        return True


def main():
    app = Prospecting()
    while app.step():
        pass


if __name__ == "__main__":
    main()
