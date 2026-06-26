# HEROX Human Body Perception Module

Reusable ROS 2/Vulcanexus-compatible HRI vision module extracted from the HERoX demonstrator. The module detects and tracks humans from RGB-D camera streams, estimates 3D body positions using depth data, and publishes both legacy 3D bounding box outputs and ROS4HRI-style body topics.

## Repository layout

```text
herox-vision-module/
  README.md
  LICENSE
  docs/
    01_arise_context.md
    02_interfaces.md
    03_installation_and_hello_world.md
    04_basic_demo_how_to_use.md
    05_role_in_demonstrator.md
  ros2_ws/src/hri_person_detect/
    hri_person_detect/
    launch/
    config/
    models/
    legacy/
    package.xml
    setup.py
  examples/
  launch/
  config/
  media/
    architecture_diagram.png
    screenshots/
    video_link.md
  docker/
```

## Quick start

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_person_detect hri_person_detect.launch.py
```

The functional ROS 2 package is located in `ros2_ws/src/hri_person_detect`. The code was moved into the recommended ARISE repository structure without changing the core detector implementation.
