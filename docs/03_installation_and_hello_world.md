# Installation and hello world

## Native ROS 2/Vulcanexus workspace

```bash
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_person_detect hri_person_detect.launch.py
```

## Expected result

The node starts as `/camera_subscriber`, loads the configured RTMDet checkpoint, checks for the configured RealSense topics, and publishes body/detection outputs once synchronized RGB-D streams are available.

## Hardware note

The full execution path expects RealSense-style RGB-D topics. For D4 reproducibility without the original hardware, add a recorded rosbag or mock publisher under `examples/`.
