"""Sawppy drive for Webots.

Port of rover_motor_controller vel_parser_node.py plus rover_teleop keys.
Wheel layout matches NASA Sojourner in webots-master: 6 drive, 4 steer,
passive bogies. Wheels are velocity-mode. On a turn the mid wheels drop
torque (Sojourner move_4_wheels) so the Ackermann corners are not fighting
the middle pair.
"""

import math

from controller import Keyboard, Robot

D1 = 23.0
D2 = 25.5
D3 = 28.5
D4 = 26.0
MAX_RADIUS = 255.0
MIN_TURN = 5.0
MAX_WHEEL = 2.5
MID_TORQUE = 2.0

WHEELS = [
    "front_left_wheel_joint",
    "mid_left_wheel_joint",
    "back_left_wheel_joint",
    "front_right_wheel_joint",
    "mid_right_wheel_joint",
    "back_right_wheel_joint",
]
CORNERS = [
    "front_left_corner_joint",
    "front_right_corner_joint",
    "back_left_corner_joint",
    "back_right_corner_joint",
]
PASSIVE = ["left_bogie_joint", "right_bogie_joint", "diff_brace_joint"]
MIDS = ("mid_left_wheel_joint", "mid_right_wheel_joint")


def calculate_velocity(v, radius):
    if v == 0:
        return [0.0] * 6
    if abs(radius) <= MIN_TURN:
        return [v, v, v, -v, -v, -v]

    r = MAX_RADIUS - (((MAX_RADIUS - 55.0) * abs(radius)) / 100.0)
    a = D2 ** 2
    b = D3 ** 2
    c = (r + D1) ** 2
    d = (r - D1) ** 2
    e = r - D4
    f = r + D4
    rx = math.sqrt(b + c) if r < 111 else f

    abs_v1 = abs(v) * math.sqrt(b + c) / rx
    abs_v2 = abs(v) * (f / rx)
    abs_v3 = abs(v) * math.sqrt(a + c) / rx
    abs_v4 = abs(v) * math.sqrt(b + d) / rx
    abs_v5 = abs(v) * (e / rx)
    abs_v6 = abs(v) * math.sqrt(a + d) / rx

    if v < 0:
        if radius < 0:
            vel = [-abs_v4, -abs_v5, -abs_v6, abs_v1, abs_v2, abs_v3]
        else:
            vel = [-abs_v1, -abs_v2, -abs_v3, abs_v4, abs_v5, abs_v6]
    else:
        if radius < 0:
            vel = [abs_v4, abs_v5, abs_v6, -abs_v1, -abs_v2, -abs_v3]
        else:
            vel = [abs_v1, abs_v2, abs_v3, -abs_v4, -abs_v5, -abs_v6]
    return vel


def calculate_target_deg(radius):
    if radius == 0:
        r = MAX_RADIUS
    elif -100 <= radius <= 100:
        r = MAX_RADIUS - abs(radius) * int(MAX_RADIUS / 100)
    else:
        r = MAX_RADIUS
    if r == MAX_RADIUS:
        return [0.0] * 4

    ang7 = math.degrees(math.atan(D3 / (abs(r) + D1)))
    ang8 = math.degrees(math.atan(D3 / (abs(r) - D1)))
    ang9 = math.degrees(math.atan(D2 / (abs(r) + D1)))
    ang10 = math.degrees(math.atan(D2 / (abs(r) - D1)))
    if radius < 0:
        return [-ang8, -ang7, ang10, ang9]
    return [ang7, ang8, -ang9, -ang10]


def _device(robot, name):
    try:
        return robot.getDevice(name)
    except Exception:
        return None


def main():
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    wheels = []
    for name in WHEELS:
        motor = robot.getDevice(name)
        motor.setPosition(float("inf"))
        motor.setVelocity(0.0)
        wheels.append(motor)
    corners = [robot.getDevice(name) for name in CORNERS]
    for name in PASSIVE:
        joint = _device(robot, name)
        if joint is not None:
            try:
                joint.setAvailableTorque(0.0)
            except Exception:
                pass

    lidar = _device(robot, "lidar")
    if lidar is not None:
        lidar.enable(timestep)
        try:
            lidar.enablePointCloud()
        except Exception:
            pass
    camera = _device(robot, "camera")
    if camera is not None:
        camera.enable(timestep)
        try:
            camera.recognitionEnable(timestep)
        except Exception:
            pass
    depth = _device(robot, "depth")
    if depth is not None:
        depth.enable(timestep)
    gps = _device(robot, "gps")
    if gps is not None:
        gps.enable(timestep)
    imu = _device(robot, "imu")
    if imu is not None:
        imu.enable(timestep)
    accel = _device(robot, "accel")
    if accel is not None:
        accel.enable(timestep)
    gyro = _device(robot, "gyro")
    if gyro is not None:
        gyro.enable(timestep)

    keyboard = Keyboard()
    keyboard.enable(timestep)

    linear = 0.0
    angular = 0.0
    tick = 0
    print("sawppy_drive: click the 3D view")
    print("  W forwards   X back   A left   D right   S stop")
    print("  Q / E forwards-left / forwards-right (Sojourner keys)")

    while robot.step(timestep) != -1:
        key = keyboard.getKey()
        if key in (ord("W"), Keyboard.UP):
            linear, angular = 50.0, 0.0
        elif key in (ord("X"), Keyboard.DOWN):
            linear, angular = -50.0, 0.0
        elif key in (ord("A"), Keyboard.LEFT, ord("Q")):
            linear, angular = 35.0, -55.0
        elif key in (ord("D"), Keyboard.RIGHT, ord("E")):
            linear, angular = 35.0, 55.0
        elif key == ord("Y"):
            linear, angular = -35.0, -55.0
        elif key == ord("C"):
            linear, angular = -35.0, 55.0
        elif key == ord("S"):
            linear, angular = 0.0, 0.0

        turning = abs(angular) > MIN_TURN
        speeds = calculate_velocity(linear, angular)
        degrees = calculate_target_deg(angular)
        for motor, cmd in zip(wheels, speeds):
            rad_s = (cmd / 100.0) * MAX_WHEEL
            if motor.getName().endswith("right_wheel_joint"):
                rad_s = -rad_s
            if motor.getName() in MIDS:
                try:
                    motor.setAvailableTorque(0.0 if turning else MID_TORQUE)
                except Exception:
                    pass
            motor.setVelocity(max(-8.0, min(8.0, rad_s)))
        for motor, deg in zip(corners, degrees):
            motor.setPosition(max(-1.2, min(1.2, math.radians(deg))))

        tick += 1
        if tick % 80 == 0:
            pose = gps.getValues() if gps is not None else (0, 0, 0)
            close = None
            if lidar is not None:
                ranges = [r for r in lidar.getRangeImage() if math.isfinite(r) and r > 0.4]
                if ranges:
                    close = min(ranges)
            n_obj = 0
            if camera is not None:
                try:
                    objs = camera.getRecognitionObjects()
                    n_obj = len(objs) if objs is not None else 0
                except Exception:
                    pass
            print(
                "gps=%.2f %.2f %.2f lidar_min=%s rec=%d cmd lin=%.0f ang=%.0f"
                % (
                    pose[0],
                    pose[1],
                    pose[2],
                    "%.2f" % close if close else "-",
                    n_obj,
                    linear,
                    angular,
                )
            )


if __name__ == "__main__":
    main()
