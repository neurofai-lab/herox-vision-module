# Interfaces

## ROS 2 / Vulcanexus interface

| Element | Name | Type | Description |
|---|---|---|---|
| Node | `/camera_subscriber` | ROS 2 node | Runs human detection, tracking, depth association, and body-state publishing. |
| Subscribes | `/camera_1/realsense_camera_1/color/image_raw` | `sensor_msgs/Image` | RGB stream for camera 1. |
| Subscribes | `/camera_1/realsense_camera_1/depth/image_rect_raw` | `sensor_msgs/Image` | Depth stream for camera 1. |
| Subscribes | `/camera_1/realsense_camera_1/depth/camera_info` | `sensor_msgs/CameraInfo` | Camera intrinsics for camera 1. |
| Subscribes | `/camera_2/realsense_camera_2/color/image_raw` | `sensor_msgs/Image` | RGB stream for camera 2. |
| Subscribes | `/camera_2/realsense_camera_2/depth/image_rect_raw` | `sensor_msgs/Image` | Depth stream for camera 2. |
| Subscribes | `/camera_2/realsense_camera_2/depth/camera_info` | `sensor_msgs/CameraInfo` | Camera intrinsics for camera 2. |
| Publishes | `/camera_1/bounding_boxes_3d` | `vision_msgs/BoundingBox3DArray` | 3D person detections from camera 1. |
| Publishes | `/camera_2/bounding_boxes_3d` | `vision_msgs/BoundingBox3DArray` | 3D person detections from camera 2. |
| Publishes | `/vision/bounding_boxes_3d` | `vision_msgs/BoundingBox3DArray` | Combined 3D detections from all active cameras. |
| Publishes | `/humans/bodies/tracked` | `hri_msgs/IdsList` | Tracked body identifiers. |
| Publishes | `/humans/bodies/<body_id>/roi` | `hri_msgs/NormalizedRegionOfInterest2D` | Normalized image ROI for each tracked body. |
| Publishes | `/humans/bodies/<body_id>/position` | `geometry_msgs/PointStamped` | Estimated 3D body position for each tracked body. |
| Launch file | `hri_person_detect.launch.py` | ROS 2 launch | Starts the detector node with configurable runtime arguments. |

## ROS4HRI / ROS4RI alignment

The module aligns with ROS4HRI body concepts by publishing tracked body IDs, ROI information, and body positions under `/humans/bodies/...` topics. Body IDs are generated from DeepSort track IDs and camera identifiers.

## FIWARE / NGSI-LD mapping

A full Context Broker integration is not included in the current open package. The ROS outputs can be mapped to NGSI-LD entities representing detected humans, their body ROI, confidence, source camera, and 3D position. Example mapping files should be placed in `config/` before final D4 submission.

## DDS NGSI-LD integration

DDS Enabler configuration is not included in the current code package. If required for D4, add a mapping file in `config/` and reference the ROS 2 topics listed above.
