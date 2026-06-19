#!/usr/bin/env python3
import os
import cv2
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

import torch
import argparse
import numpy as np
import pyrealsense2 as rs2
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge, CvBridgeError
from vision_msgs.msg import BoundingBox3D, BoundingBox3DArray
from deep_sort_realtime.deepsort_tracker import DeepSort
from mmdet.apis import init_detector, inference_detector
from message_filters import Subscriber, ApproximateTimeSynchronizer
from geometry_msgs.msg import Pose, Vector3
from std_msgs.msg import Header

import traceback
from collections import deque
import signal
from datetime import datetime
import time


class CameraSubscriber(Node):
    """
    A ROS2 node that subscribes to camera topics, processes color and depth images,
    and publishes the distance and 3D world coordinates of detected objects.
    """

    PERSON_CLASS_ID = 0  # COCO person

    def __init__(self, distance_threshold, detection_confidence_score=0.5,
                 debug=False, debug_dir='./debug_output'):
        super().__init__('camera_subscriber')

        self.declare_parameter('camera_frame', 'camera_link')
        self.bridge = CvBridge()
        self.counters = {'cam_1': 0, 'cam_2': 0}

        self.distance_threshold = distance_threshold
        self.detection_confidence_score = detection_confidence_score

        self.inference_stats = {
            'cam_1': {'count': 0, 'total_ms': 0.0, 'min_ms': float('inf'), 'max_ms': 0.0},
            'cam_2': {'count': 0, 'total_ms': 0.0, 'min_ms': float('inf'), 'max_ms': 0.0},
        }

        # Debug settings
        self.debug = debug
        self.debug_dir = debug_dir
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)
            self.get_logger().info(f"Debug mode enabled. Saving images to: {self.debug_dir}")

        # Initialize queues for custom scheduling
        self.queues = {name: deque() for name in ['cam_1', 'cam_2']}

        # Initialize intrinsics for each camera
        self.intrinsics = {name: None for name in ['cam_1', 'cam_2']}

        # Initialize DeepSort trackers
        self.trackers = {name: DeepSort(max_age=10, n_init=3) for name in ['cam_1', 'cam_2']}

        self.init_model()

        # Timer to alternate processing between cameras
        self.timer = self.create_timer(0.01, self.process_images_from_queue)

        # Add signal handler for graceful shutdown
        signal.signal(signal.SIGINT, lambda sig, frame: self.stop_node())

        # Publishers for BoundingBox3DArray messages
        self.bbox3d_publishers = {
            'cam_1': self.create_publisher(BoundingBox3DArray, '/camera_1/bounding_boxes_3d', 10),
            'cam_2': self.create_publisher(BoundingBox3DArray, '/camera_2/bounding_boxes_3d', 10),
        }

        # Combined publisher for all cameras
        self.bbox3d_all_publisher = self.create_publisher(BoundingBox3DArray, '/vision/bounding_boxes_3d', 10)

        # Camera topic names
        camera_topics = {
            'cam_1': (
                '/camera_1/realsense_camera_1/color/image_raw',
                '/camera_1/realsense_camera_1/depth/image_rect_raw',
                '/camera_1/realsense_camera_1/depth/camera_info'
            ),
            'cam_2': (
                '/camera_2/realsense_camera_2/color/image_raw',
                '/camera_2/realsense_camera_2/depth/image_rect_raw',
                '/camera_2/realsense_camera_2/depth/camera_info'
            ),
        }

        available_topics = [topic[0] for topic in self.get_topic_names_and_types()]

        # Subscriptions and synchronization for each camera
        for cam_name, topics in camera_topics.items():
            if topics[0] in available_topics and topics[1] in available_topics and topics[2] in available_topics:
                self.create_subscription(
                    CameraInfo,
                    topics[2],
                    lambda msg, cam=cam_name: self.imageDepthInfoCallback(msg, cam),
                    10
                )
                self.get_logger().info(f"Subscribed to {topics[2]}")

                sync = ApproximateTimeSynchronizer(
                    [
                        Subscriber(self, Image, topics[0]),
                        Subscriber(self, Image, topics[1])
                    ],
                    queue_size=10,
                    slop=0.1
                )

                sync.registerCallback(
                    lambda color_data, depth_data, cam=cam_name: self.queue_images(cam, color_data, depth_data)
                )
                self.get_logger().info(f"Synchronized {topics[0]} and {topics[1]}")
            else:
                self.get_logger().info(f"Failed to subscribe or synchronize {cam_name}")

    def init_model(self):
        """Initialize the model."""
        self.get_logger().info("Initializing vision guided detection model...")

        try:
            model_cfg = "model_cfg_latest_person_tiny.py"
            checkpoint = "rtmdet-ins_tiny_8xb32-300e_coco_20221130_151727-ec670f7e.pth"
            self.model = init_detector(model_cfg, checkpoint, device="cuda:0")
            self.get_logger().info(f"Loaded detector with checkpoint: {checkpoint}")
        except Exception as e:
            self.get_logger().error(f"Error initializing model: {e}")
            self.get_logger().error(traceback.format_exc())

    def get_intrinsics(self, camera_info):
        """Get camera intrinsics from CameraInfo message."""
        intrinsics = rs2.intrinsics()
        intrinsics.width = camera_info.width
        intrinsics.height = camera_info.height
        intrinsics.ppx = camera_info.k[2]
        intrinsics.ppy = camera_info.k[5]
        intrinsics.fx = camera_info.k[0]
        intrinsics.fy = camera_info.k[4]

        if camera_info.distortion_model == 'plumb_bob':
            intrinsics.model = rs2.distortion.brown_conrady
        elif camera_info.distortion_model == 'equidistant':
            intrinsics.model = rs2.distortion.kannala_brandt4

        intrinsics.coeffs = [i for i in camera_info.d]
        return intrinsics

    def imageDepthInfoCallback(self, cameraInfo, camera_name):
        """Process camera info and initialize camera intrinsics."""
        try:
            if self.intrinsics[camera_name] is None:
                self.intrinsics[camera_name] = self.get_intrinsics(cameraInfo)
                self.get_logger().info(f"{camera_name} intrinsics initialized: {self.intrinsics[camera_name]}")
        except CvBridgeError as e:
            self.get_logger().error(f"Error initializing camera intrinsics: {e}")

    def convert_bbox_to_meters(self, x1, y1, x2, y2, depth_scale, intrinsics):
        """Convert bounding box dimensions from pixels to meters."""
        bbox_width_pixels = x2 - x1
        bbox_height_pixels = y2 - y1

        bbox_width_m = (bbox_width_pixels * depth_scale) / intrinsics.fx
        bbox_height_m = (bbox_height_pixels * depth_scale) / intrinsics.fy

        return bbox_width_m, bbox_height_m

    def map_to_3d(self, x, y, depth_image, intrinsics):
        """Map 2D pixel coordinates to 3D real-world coordinates."""
        try:
            depth_pixel = [x, y]
            depth_value = depth_image[int(y), int(x)]
            depth_point = rs2.rs2_deproject_pixel_to_point(
                intrinsics, [depth_pixel[0], depth_pixel[1]], depth_value
            )
            return depth_point
        except Exception as e:
            self.get_logger().error(f"Error mapping to 3D coordinates: {e}")
            return None

    def queue_images(self, camera_name, color_data, depth_data):
        """Queue images from a camera."""
        self.queues[camera_name].append((color_data, depth_data))

    def process_images_from_queue(self):
        """Process images from the queue, alternating between cameras."""
        for cam_name in ['cam_1', 'cam_2']:
            if self.queues[cam_name]:
                color_data, depth_data = self.queues[cam_name].popleft()
                self.process_images(color_data, depth_data, cam_name)

    def calculate_min_distance(self, segm_coords, depth_image):
        if segm_coords is None or len(segm_coords) != 2:
            return float('inf'), None, None, 0.0

        y_coords, x_coords = segm_coords
        if y_coords is None or x_coords is None or y_coords.size == 0 or x_coords.size == 0:
            return float('inf'), None, None, 0.0

        h, w = depth_image.shape[:2]

        mask = np.zeros((h, w), dtype=np.uint8)
        y_clipped = np.clip(y_coords, 0, h - 1)
        x_clipped = np.clip(x_coords, 0, w - 1)
        mask[y_clipped, x_clipped] = 1

        # Stronger erosion for a stable inner body region
        kernel = np.ones((7, 7), dtype=np.uint8)
        mask_eroded = cv2.erode(mask, kernel, iterations=1)
        if not np.any(mask_eroded):
            mask_eroded = mask.copy()

        ys, xs = np.where(mask_eroded > 0)
        if ys.size == 0:
            return float('inf'), None, None, 0.0

        y1, y2 = ys.min(), ys.max()
        x1, x2 = xs.min(), xs.max()

        # Torso/core ROI
        roi_y1 = int(y1 + 0.35 * (y2 - y1))
        roi_y2 = int(y1 + 0.85 * (y2 - y1))
        roi_x1 = int(x1 + 0.30 * (x2 - x1))
        roi_x2 = int(x1 + 0.70 * (x2 - x1))

        core_mask = np.zeros_like(mask_eroded, dtype=bool)
        core_mask[roi_y1:roi_y2 + 1, roi_x1:roi_x2 + 1] = True
        core_mask = core_mask & (mask_eroded > 0)

        if not np.any(core_mask):
            core_mask = mask_eroded > 0

        depths = depth_image[core_mask]
        depths = depths[np.isfinite(depths) & (depths > 0)]
        if depths.size < 10:
            return float('inf'), None, None, 0.0

        depths_cm = depths / 10.0

        # Robust center by median + MAD filtering
        med = np.median(depths_cm)
        mad = np.median(np.abs(depths_cm - med))
        if mad < 1e-6:
            inliers = depths_cm
        else:
            inliers = depths_cm[np.abs(depths_cm - med) <= 2.5 * 1.4826 * mad]

        if inliers.size == 0:
            inliers = depths_cm

        robust_cm = float(np.median(inliers))

        # Representative pixel closest to robust depth
        ys, xs = np.where(core_mask)
        cand_cm = depth_image[ys, xs] / 10.0
        valid = np.isfinite(cand_cm) & (cand_cm > 0)
        ys, xs, cand_cm = ys[valid], xs[valid], cand_cm[valid]

        if cand_cm.size == 0:
            return robust_cm, None, None, 0.0

        idx = int(np.argmin(np.abs(cand_cm - robust_cm)))
        rep_y = int(ys[idx])
        rep_x = int(xs[idx])

        # Simple quality score
        quality = float(min(1.0, inliers.size / 100.0))

        return robust_cm, rep_x, rep_y
        
    def create_boundingbox3d_msg(self, center_3d, bbox_width_m, bbox_height_m, bbox_size_z):
        """Create a BoundingBox3D message."""
        bbox3d = BoundingBox3D()

        bbox3d.center = Pose()
        bbox3d.center.position.x = float(center_3d[0])
        bbox3d.center.position.y = float(center_3d[1])
        bbox3d.center.position.z = float(center_3d[2])

        bbox3d.center.orientation.x = 0.0
        bbox3d.center.orientation.y = 0.0
        bbox3d.center.orientation.z = 0.0
        bbox3d.center.orientation.w = 1.0

        bbox3d.size = Vector3()
        bbox3d.size.x = float(bbox_width_m)
        bbox3d.size.y = float(bbox_height_m)
        bbox3d.size.z = float(bbox_size_z)

        return bbox3d

    def save_debug_visualization(self, image, camera_name, frame_num, detections):
        """
        Save debug visualization image with person detections only.

        detections: list of dicts with keys:
            bbox: [x1, y1, x2, y2]
            score: float or None
            mask: np.ndarray or torch tensor or None
            meta_lines: list[str] optional
        """
        try:
            vis_image = image.copy()

            for det in detections:
                x1, y1, x2, y2 = det['bbox']
                score = det.get('score', None)
                mask = det.get('mask', None)
                meta_lines = det.get('meta_lines', [])

                # Draw mask overlay if present
                if mask is not None:
                    if torch.is_tensor(mask):
                        mask_np = mask.detach().cpu().numpy().astype(np.uint8)
                    else:
                        mask_np = np.asarray(mask).astype(np.uint8)

                    if mask_np.shape[:2] != vis_image.shape[:2]:
                        mask_np = cv2.resize(
                            mask_np,
                            (vis_image.shape[1], vis_image.shape[0]),
                            interpolation=cv2.INTER_NEAREST
                        )

                    colored_mask = np.zeros_like(vis_image, dtype=np.uint8)
                    colored_mask[:, :, 1] = mask_np * 180  # green mask
                    vis_image = cv2.addWeighted(vis_image, 1.0, colored_mask, 0.35, 0)

                # Draw bbox
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Build label lines
                lines = []
                if score is not None:
                    lines.append(f"person {score:.2f}")
                else:
                    lines.append("person")
                lines.extend(meta_lines)

                # Draw label background + text
                line_height = 20
                max_text_width = 0
                for line in lines:
                    (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    max_text_width = max(max_text_width, tw)

                box_top = max(0, y1 - line_height * len(lines) - 8)
                box_bottom = y1

                cv2.rectangle(
                    vis_image,
                    (x1, box_top),
                    (x1 + max_text_width + 10, box_bottom),
                    (0, 0, 0),
                    -1
                )

                y_text = box_top + 15
                for line in lines:
                    cv2.putText(
                        vis_image,
                        line,
                        (x1 + 5, y_text),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2
                    )
                    y_text += line_height

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = os.path.join(
                self.debug_dir,
                f"{camera_name}_frame_{frame_num}_{timestamp}.jpg"
            )
            cv2.imwrite(filename, vis_image)
            self.get_logger().info(f"Saved debug image: {filename}")

        except Exception as e:
            self.get_logger().error(f"Error saving debug visualization: {e}")
            self.get_logger().error(traceback.format_exc())

    def update_inference_stats(self, camera_name, inference_time_ms):
        """Update and log inference timing statistics."""
        stats = self.inference_stats[camera_name]
        stats['count'] += 1
        stats['total_ms'] += inference_time_ms
        stats['min_ms'] = min(stats['min_ms'], inference_time_ms)
        stats['max_ms'] = max(stats['max_ms'], inference_time_ms)

        avg_ms = stats['total_ms'] / stats['count']
        fps = 1000.0 / inference_time_ms if inference_time_ms > 0 else 0.0

        self.get_logger().info(
            f"[{camera_name}] Inference: {inference_time_ms:.2f} ms | "
            f"Avg: {avg_ms:.2f} ms | Min: {stats['min_ms']:.2f} ms | "
            f"Max: {stats['max_ms']:.2f} ms | FPS: {fps:.2f}"
        )

    def process_images(self, color_data, depth_data, camera_name):
        """
        Process the color and depth images, detect objects, and publish distance and coordinates.
        """
        try:
            color_image = self.bridge.imgmsg_to_cv2(color_data, desired_encoding='bgr8')
            depth_image = self.bridge.imgmsg_to_cv2(depth_data, desired_encoding='passthrough')

            if depth_image is None or np.all(depth_image == 0):
                self.get_logger().warning("Depth image is invalid or not available.")
                return

            depth_image = np.asanyarray(depth_image, dtype=np.float32)
            # resized_depth_img = cv2.resize(depth_image, (color_image.shape[1], color_image.shape[0]))
            resized_depth_img = cv2.resize(
                depth_image,
                (color_image.shape[1], color_image.shape[0]),
                interpolation=cv2.INTER_NEAREST
            )

            # Measure detector inference time accurately on GPU
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            start_time = time.perf_counter()

            with torch.no_grad():
                result = inference_detector(self.model, color_image)

            if torch.cuda.is_available():
                torch.cuda.synchronize()
            end_time = time.perf_counter()

            inference_time_ms = (end_time - start_time) * 1000.0
            self.update_inference_stats(camera_name, inference_time_ms)

            masks = result.pred_instances.masks
            bbox_info = result.pred_instances.bboxes.tolist()
            scores = result.pred_instances.scores.tolist()
            classes = result.pred_instances.labels.tolist()

            detect = []
            filtered_masks = []

            # This is the one debug list that will show segmented person + metadata
            tracked_debug_detections = []

            # Keep only person detections
            for idx, (bbox, score, class_id) in enumerate(zip(bbox_info, scores, classes)):
                if score >= self.detection_confidence_score and class_id == self.PERSON_CLASS_ID:
                    x1, y1, x2, y2 = map(int, bbox)
                    detect.append([[x1, y1, x2 - x1, y2 - y1], score, class_id])
                    filtered_masks.append(masks[idx].cpu())

            bbox3d_array_msg = BoundingBox3DArray()
            bbox3d_array_msg.header = Header()
            bbox3d_array_msg.header.stamp = self.get_clock().now().to_msg()
            bbox3d_array_msg.header.frame_id = camera_name

            for track in self.trackers[camera_name].update_tracks(
                detect,
                instance_masks=filtered_masks,
                frame=color_image
            ):
                if not track.is_confirmed() and track.get_instance_mask() is None:
                    continue

                mask = track.get_instance_mask()
                if mask is None:
                    continue

                segm_cords = np.where(mask)
                object_distance, rep_x, rep_y = self.calculate_min_distance(segm_cords, resized_depth_img)

                if object_distance <= self.distance_threshold:
                    y_cords, x_cords = segm_cords
                    if len(y_cords) > 0 and len(x_cords) > 0:
                        y1, y2 = np.min(y_cords), np.max(y_cords)
                        x1, x2 = np.min(x_cords), np.max(x_cords)
                    else:
                        continue

                    object_distance = object_distance / 100  # cm -> m

                    self.get_logger().info(
                        f"Obstacle detected! from {camera_name} distance: {object_distance} meters"
                    )

                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)

                    if self.intrinsics[camera_name] is None:
                        self.get_logger().warning(f"Intrinsics for {camera_name} not initialized yet.")
                        continue

                    bbox_width_m, bbox_height_m = self.convert_bbox_to_meters(
                        x1, y1, x2, y2, object_distance, self.intrinsics[camera_name]
                    )

                    coordinates_data = self.map_to_3d(
                        rep_x, rep_y, resized_depth_img, self.intrinsics[camera_name]
                    )
                    if coordinates_data is None:
                        continue

                    bbox_size_z = object_distance
                    bbox3d_msg = self.create_boundingbox3d_msg(
                        coordinates_data, bbox_width_m, bbox_height_m, bbox_size_z
                    )
                    bbox3d_array_msg.boxes.append(bbox3d_msg)

                    # Debug image entry: segmented person with distance/height/width metadata
                    if self.debug:
                        tracked_debug_detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'score': None,
                            'mask': mask,
                            'meta_lines': [
                                f"dist: {object_distance:.2f} m",
                                f"height: {bbox_height_m:.2f} m",
                                f"width: {bbox_width_m:.2f} m"
                            ]
                        })

            self.bbox3d_publishers[camera_name].publish(bbox3d_array_msg)
            self.bbox3d_all_publisher.publish(bbox3d_array_msg)
            self.get_logger().info(
                f"Published {len(bbox3d_array_msg.boxes)} bounding boxes on /{camera_name}/bounding_boxes_3d"
            )

            # Save only the enriched debug image
            if self.debug and tracked_debug_detections:
                self.counters[camera_name] += 1
                self.save_debug_visualization(
                    image=color_image,
                    camera_name=camera_name,
                    frame_num=self.counters[camera_name],
                    detections=tracked_debug_detections
                )

            if not detect:
                self.get_logger().info(f"[{camera_name}] No person detections in this frame.")
            else:
                self.get_logger().info(f"[{camera_name}] Processed frame with {len(detect)} person detections.")

        except Exception as e:
            self.get_logger().error(f"Unexpected Error: {e}")
            self.get_logger().error(traceback.format_exc())

    def stop_node(self):
        self.get_logger().info("Shutting down...")
        self.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--distance_threshold',
        type=float,
        default=200,
        help='Distance threshold for object detection. Default is set to 50 CM.'
    )
    parser.add_argument(
        '--detection_confidence_score',
        type=float,
        default=0.5,
        help='Detection confidence score to filter detections. Default is 0.5.'
    )
    parser.add_argument(
        '--num_cameras',
        type=int,
        default=4,
        help='Number of cameras to subscribe. Same for number of CPU Cores to be utilized. Default is 4.'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable saving debug visualization images.'
    )
    parser.add_argument(
        '--debug_dir',
        type=str,
        default='./debug_output',
        help='Directory to save debug visualization images.'
    )
    args = parser.parse_args()

    rclpy.init(args=None)
    camera_subscriber = CameraSubscriber(
        args.distance_threshold,
        args.detection_confidence_score,
        debug=args.debug,
        debug_dir=args.debug_dir
    )

    executor = MultiThreadedExecutor(num_threads=args.num_cameras)
    executor.add_node(camera_subscriber)

    try:
        executor.spin()
    finally:
        camera_subscriber.destroy_node()
        rclpy.shutdown()