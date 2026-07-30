import rclpy
import pytest

from geometry_msgs.msg import PointStamped
from hri_msgs.msg import IdsList, NormalizedRegionOfInterest2D
from vision_msgs.msg import BoundingBox3DArray

from hri_person_detect.node_person_detector import CameraSubscriber


@pytest.fixture
def vision_node(monkeypatch):
    """Create the node without loading the detector model."""

    # Model loading requires MMDetection, CUDA and the checkpoint.
    monkeypatch.setattr(CameraSubscriber, "init_model", lambda self: None)

    if not rclpy.ok():
        rclpy.init()

    node = CameraSubscriber(
        distance_threshold=200.0,
        detection_confidence_score=0.5,
        device="cpu",
    )

    yield node

    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


def test_node_starts(vision_node):
    """Verify that the ROS 2 node can be constructed."""

    assert vision_node.get_name() == "camera_subscriber"


def test_expected_detection_publishers_exist(vision_node):
    """Verify the main 3D detection output interfaces."""

    cam_1_pub = vision_node.bbox3d_publishers["cam_1"]
    cam_2_pub = vision_node.bbox3d_publishers["cam_2"]
    combined_pub = vision_node.bbox3d_all_publisher

    assert cam_1_pub.topic_name == "/camera_1/bounding_boxes_3d"
    assert cam_1_pub.msg_type is BoundingBox3DArray

    assert cam_2_pub.topic_name == "/camera_2/bounding_boxes_3d"
    assert cam_2_pub.msg_type is BoundingBox3DArray

    assert combined_pub.topic_name == "/vision/bounding_boxes_3d"
    assert combined_pub.msg_type is BoundingBox3DArray


def test_expected_ros4hri_publishers_exist(vision_node):
    """Verify the standard ROS4HRI body interfaces."""

    tracked_pub = vision_node.hri_bodies_tracked_pub

    assert tracked_pub.topic_name == "/humans/bodies/tracked"
    assert tracked_pub.msg_type is IdsList

    roi_pub, position_pub = vision_node._get_hri_body_publishers(
        "person_c1_test"
    )

    assert roi_pub.topic_name == "/humans/bodies/person_c1_test/roi"
    assert roi_pub.msg_type is NormalizedRegionOfInterest2D

    assert position_pub.topic_name == "/humans/bodies/person_c1_test/position"
    assert position_pub.msg_type is PointStamped


def test_body_id_format(vision_node):
    """Verify the body-ID format documented by the module."""

    assert vision_node._make_hri_body_id("cam_1", 4) == "person_c1_4"
    assert vision_node._make_hri_body_id("cam_2", 7) == "person_c2_7"
