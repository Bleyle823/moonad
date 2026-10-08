# Lunar prospecting rover (Webots)

One rover, three codebases, three jobs. Do not merge their controllers into one blob.

| Job | Source | What we keep |
| --- | --- | --- |
| Chassis and drive | `ros2_rover-jazzy` (Sawppy, MIT) | 6 driven wheels, 4 corner steer servos, rocker-bogie, lidar + RGB-D + IMU. `cmd_vel` becomes per-wheel speed and corner angle the way `vel_parser_node.py` does. |
| Autonomy | SJTU prospecting repo | A* on a height/obstacle grid (`global_planner.py`), slow down when the view is poor (`Vehicle.vehicle_modify_pts`), depth-window obstacle check (`Detecter.detect_obstacles`), interest targets (`Detecter` HSV + YOLOv5). |
| Economy | `peaq-robotics-ros2-dev` `peaq_ros2_peaqos` | ROS 2 stays the control plane. peaqOS is identity, events, and payment. Keys never ride on a ROS message. |

The SJTU rover is a **4-wheel skid-steer**. This world is **not** that chassis. Their planner and detector sit on top of the Sawppy drive.

## Mechanics (from the URDF)

Taken from `rover_description`:

- Body box about 0.43 x 0.29 x 0.10 m, mass 1 kg in the xacro (sim mass; a flight rover is heavier).
- Wheel radius 0.060 m, width 0.100 m, mass 0.25 kg.
- Six velocity joints: front/mid/back, left and right. Limit in the xacro is ±10 rad/s.
- Four position joints for the corner steer: front and back, left and right.
- Middle wheels do not steer.
- Left and right rockers pitch on the body. Each bogie pitches on the rear of its rocker and carries the mid and rear wheels.
- The Gazebo model also has a differential between the rockers. This Webots model uses independent rockers with stops and damping. That still lets each side climb, and it is simpler to debug. A geared differential is a later swap.
- Moon gravity in this world is 1.62 m/s².

Drive law in `controllers/prospecting/prospecting.py` follows Sawppy, not skid-steer:

- Turning radius from yaw rate.
- Outer wheels faster than inner wheels.
- Front corners steer into the turn, rear corners steer the opposite way (four-wheel steer).

## Autonomy (from the prospecting stack)

The contest rover only had RGB-D cameras, planned on a coarse lunar height map, and searched for orange sample boxes.

This world:

1. Builds a 0.5 m grid. Craters and rocks from the world are marked blocked, same idea as `global_planner` rejecting steep cells (`gradient_limit`).
2. A* to the next sample, then to the lander pad.
3. Lidar sectors stand in for `Detecter.detect_obstacles` (a depth window in front of the camera). A close return forces a stop and a replan.
4. Few lidar returns (open, feature-poor ground) cut speed, same idea as `vehicle_modify_pts`.
5. Webots recognition stands in for HSV + YOLOv5. On a real camera, call `Detecter.detect_targets` and `yolov5/detectinterest.py` instead. Do not ship the whole YOLOv5 tree into the Webots controller.

## peaq (from peaqOS ROS 2)

`peaqos_node` already exposes wallet create, machine register, NFT mint, DID attributes, event submit, and MCR query. The Webots controller does not talk to the chain. It appends the same events a ROS 2 bridge would submit:

| Event | When | peaqOS call later |
| --- | --- | --- |
| `machine_online` | controller start | `machine/register` + DID attributes |
| `traverse` | every few metres | `events/submit` |
| `sample_found` | recognition in range | `events/submit` (trust level 1 once a tx exists) |
| `sample_delivered` | arrival at the lander pad | `events/submit`, then a USDT transfer via `peaq_ros2_tether` or Scale |

The log is `controllers/prospecting/peaq_events.jsonl`. A later ROS 2 node can tail that file and call `/peaqos_node/events/submit`. Private keys stay in the peaqOS wallet registry on the robot computer, not in Webots.

## Run

1. Open `worlds/lunar_prospecting.wbt` in Webots.
2. The robot controller is `prospecting`.
3. Watch the console for steer, samples, and the event log.

## What this world does not do

- It does not run Nav2, RTAB-Map, or the LX-16A bus. Those stay in `ros2_rover` for the real robot and Gazebo.
- It does not load `random_forest_model.pkl`. That file is an optional speed/terrain hint in the SJTU controller and is commented out there.
- It does not send a mainnet transaction. Registration on peaq was paused when last checked.
