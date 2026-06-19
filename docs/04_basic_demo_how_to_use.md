# Basic demo and how to use

## Demo goal

Demonstrate that the module consumes RGB-D camera streams and publishes human body detections as ROS 2 and ROS4HRI-style topics.

## Run

```bash
cd ros2_ws
source install/setup.bash
ros2 launch hri_person_detect hri_person_detect.launch.py
```

## Inspect output topics

```bash
ros2 topic list | grep humans
ros2 topic echo /humans/bodies/tracked
ros2 topic echo /vision/bounding_boxes_3d
```

## D4 note

Add screenshots, RViz output, logs, or a recorded-data demo before final submission.
