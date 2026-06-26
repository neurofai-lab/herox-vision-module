#!/usr/bin/env python3
"""Compatibility wrapper for the original direct-run command.

You can still run:
    python3 latest_publish_nav_cams_correctdistance_people_only.py

The actual packaged ROS2 node lives in:
    hri_person_detect/node_person_detector.py
"""

from hri_person_detect.node_person_detector import main


if __name__ == "__main__":
    main()
