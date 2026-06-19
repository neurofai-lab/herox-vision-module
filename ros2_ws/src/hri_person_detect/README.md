# hri_person_detect

ROS2-style package wrapping the original `latest_publish_nav_cams_correctdistance_people_only.py` script.

The active node preserves the original person-only RTMDet + DeepSort + Realsense depth flow:

- subscribes to synchronized color/depth image streams from two Realsense cameras
- loads `model_cfg_latest_person_tiny.py`
- loads `rtmdet-ins_tiny_8xb32-300e_coco_20221130_151727-ec670f7e.pth`
- filters detections to COCO person class only
- estimates robust depth from the instance mask/core body region
- publishes `vision_msgs/BoundingBox3DArray`

The original script, config, and checkpoint are kept untouched in `legacy/`.

## Docker run

Load the prebuilt image:

```bash
gunzip -c vulx-mmdet_jp6-cu122.tar.gz | sudo docker load
sudo docker images
```

Run the image and mount this repo at `/app`:

```bash
sudo docker run --rm -it --name vulx_from_tar_test \
  --runtime=nvidia \
  --network=host --ipc=host \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -v /usr/local/cuda:/usr/local/cuda:ro \
  -v /lib/aarch64-linux-gnu/libcudnn.so.8:/lib/aarch64-linux-gnu/libcudnn.so.8:ro \
  -v /lib/aarch64-linux-gnu/libcudnn_ops_infer.so.8:/lib/aarch64-linux-gnu/libcudnn_ops_infer.so.8:ro \
  -v /lib/aarch64-linux-gnu/libcudnn_ops_train.so.8:/lib/aarch64-linux-gnu/libcudnn_ops_train.so.8:ro \
  -v /lib/aarch64-linux-gnu/libcudnn_cnn_infer.so.8:/lib/aarch64-linux-gnu/libcudnn_cnn_infer.so.8:ro \
  -v /lib/aarch64-linux-gnu/libcudnn_cnn_train.so.8:/lib/aarch64-linux-gnu/libcudnn_cnn_train.so.8:ro \
  -v /usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu/nvidia:ro \
  -v /path-to-hri_person_detect_repo:/app \
  vulx-mmdet:jp6-cu122 bash
```

## Run without building

```bash
cd /app
python3 latest_publish_nav_cams_correctdistance_people_only.py
```

or:

```bash
cd /app
python3 -m hri_person_detect.node_person_detector
```

## Run as a ROS2 package

```bash
cd /app
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_person_detect hri_person_detect.launch.py
```

## Useful options

```bash
python3 -m hri_person_detect.node_person_detector \
  --distance_threshold 200 \
  --detection_confidence_score 0.5 \
  --num_cameras 4 \
  --device cuda:0
```

Override model/config paths:

```bash
python3 -m hri_person_detect.node_person_detector \
  --model_cfg /path/to/model_cfg_latest_person_tiny.py \
  --checkpoint /path/to/rtmdet-ins_tiny_8xb32-300e_coco_20221130_151727-ec670f7e.pth
```

## Integrity notes

The active package node keeps the original algorithmic flow. The only intentional code changes are:

1. package-safe model/config/checkpoint path resolution
2. ROS2 console entry point via `main()`
3. optional CLI args for model config, checkpoint, and detector device
4. a tuple-return fix in `calculate_min_distance()` so the function always returns three values, matching the existing caller


## ROS4HRI body topics

The original `BoundingBox3DArray` topics are preserved for backward compatibility:

- `/camera_1/bounding_boxes_3d`
- `/camera_2/bounding_boxes_3d`
- `/vision/bounding_boxes_3d`

The node also publishes ROS4HRI-compatible body topics using DeepSort track IDs:

- `/humans/bodies/tracked` (`hri_msgs/IdsList`)
- `/humans/bodies/<body_id>/roi` (`hri_msgs/NormalizedRegionOfInterest2D`)
- `/humans/bodies/<body_id>/position` (`geometry_msgs/PointStamped`)

Body IDs are generated as `person_c1_<track_id>` and `person_c2_<track_id>` to keep IDs stable and unique across both cameras.
