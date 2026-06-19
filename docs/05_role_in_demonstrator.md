# Role in the HERoX demonstrator

The vision module provides the human perception layer of the HERoX demonstrator. It detects people in the robot environment, tracks them across frames, estimates their 3D position using depth information, and exposes body state outputs that can be consumed by downstream HRI, safety, task-assistance, or robot-control components.

The reusable extraction keeps the perception node, launch files, model configuration, checkpoint reference, ROS 2 topics, and ROS4HRI-style body outputs. Demonstrator-specific deployment assumptions, such as exact camera placement and robot-cell configuration, should be documented separately in the D4 report.
