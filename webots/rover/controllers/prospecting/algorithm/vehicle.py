"""Speed policy from the contest Vehicle class, mapped to Sawppy (linear, radius).

Teleop uses linear 50 for forward. Values here are the same units as sawppy_drive.
"""


class Vehicle(object):
    def __init__(self):
        self.max_v = 55.0
        self.max_ang = 55.0
        self.angle_threshold = 0.45

    def vehicle_modify_pts(self, pts_count):
        if pts_count >= 20:
            self.max_v = 55.0
            self.max_ang = 55.0
        elif 8 < pts_count < 20:
            self.max_v = 40.0
            self.max_ang = 50.0
        else:
            self.max_v = 32.0
            self.max_ang = 45.0
        self.angle_threshold = 0.4

    def vehicle_modify_ratio(self, ratio):
        if ratio < 40:
            self.max_v = min(40.0, self.max_v)
            self.max_ang = min(50.0, self.max_ang)

    def sawppy_command(self, heading_err):
        """heading_err in radians, wrapped to (-pi, pi). Returns (linear, radius)."""
        if heading_err > self.angle_threshold:
            return 28.0, -self.max_ang
        if heading_err < -self.angle_threshold:
            return 28.0, self.max_ang
        if abs(heading_err) > 0.15:
            return self.max_v * 0.75, -self.max_ang * (heading_err / 0.8)
        return self.max_v, 0.0
