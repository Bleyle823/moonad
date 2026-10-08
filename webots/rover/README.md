# Sawppy rover, Webots port

From `ros2_rover-jazzy`, converted with [urdf2webots](https://github.com/cyberbotics/urdf2webots). Open `worlds/moon.wbt` (gravity 1.62) or `worlds/mars.wbt` (gravity 3.71). Both worlds are ENU, Z-up, to match the ROS URDF.

World layout follows Webots samples: NASA Sojourner (`projects/robots/nasa`) for rocker-bogie springs, wheel torque, 16 ms step, and `maxContactJoints`; Hokuyo / camera_recognition / GPS / IMU device worlds for lidar, RGB-D recognition, and IMU lookup tables; `Soil`, `Rock`, and `TexturedBackground` from `projects/objects`.

`protos/Sawppy.proto` comes from `rover_description/rover.urdf` (`expand_xacro.py` then `xacro`, then the importer). Mesh URLs in the proto are absolute on this machine. After a convert, re-apply the Webots devices (Lidar, Camera, RangeFinder, GPS, IMU, Accelerometer, Gyro) and the smaller collision volumes — urdf2webots does not emit sensors, and `--box-collision` copies the body box onto the rocker, bogie, and steering links.

```
python webots/rover/expand_xacro.py
xacro rover_description/_expanded/robots/rover.urdf.xacro -o rover_description/rover.urdf
python -m urdf2webots.importer --input=rover_description/rover.urdf --output=webots/rover/protos/Sawppy.proto --box-collision
```

`PYTHONPATH` must include the `urdf2webots-master` folder.

This is a 6-wheel, 4-steer Sawppy (rocker-bogie). Wheels are velocity mode. Corner joints steer. Bogie and differential brace run with zero motor torque so the suspension can sag.

Click the 3D view, then **w** forward, **x** back, **a** left, **d** right, **s** stop.

## Package map

| ROS package | Webots file | What carried over |
| --- | --- | --- |
| rover_description | protos/Sawppy.proto | Joint tree, STL/DAE meshes. Lidar, RGB-D, GPS, IMU. |
| rover_motor_controller | controllers/sawppy_drive/sawppy_drive.py | `calculate_velocity` and `calculate_target_deg`. Distances 23, 25.5, 28.5, 26 cm. |
| rover_motor_controller_cpp | same controller | LX-16A bus is not used. |
| rover_msgs | URDF joint names on the proto | `*_wheel_joint` (6), `*_corner_joint` (4). Radians. |
| rover_teleop | same controller | w / a / s / d / x. |
| rover_gazebo | worlds/moon.wbt, worlds/mars.wbt | Moon 1.62 m/s², Mars 3.71 m/s². |
| rover_localization | GPS, IMU, camera, range-finder | Ground truth in Webots. EKF and RTAB-Map stay in ROS. |
| rover_navigation | not ported | Nav2 stays in ROS. |

The ROS parser negates the right drive commands because those servos are mounted backwards. The Webots controller does the same: `(command / 100) * MAX_WHEEL`, then negate right wheels.

`worlds/moon.wbt` includes a hidden `mcp_bridge` supervisor so the Webots MCP can inspect sensors and command motors.
