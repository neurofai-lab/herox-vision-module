from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE_FILE = ROOT / "hri_person_detect" / "node_person_detector.py"
SETUP_FILE = ROOT / "setup.py"


def test_node_source_is_valid_python():
    """Check that the main node contains valid Python syntax."""
    source = NODE_FILE.read_text(encoding="utf-8")
    compile(source, str(NODE_FILE), "exec")


def test_expected_output_topics_are_declared():
    """Check that the documented ROS 2 output topics exist in the code."""
    source = NODE_FILE.read_text(encoding="utf-8")

    expected_topics = [
        "/camera_1/bounding_boxes_3d",
        "/camera_2/bounding_boxes_3d",
        "/vision/bounding_boxes_3d",
        "/humans/bodies/tracked",
        "/humans/bodies/{body_id}/roi",
        "/humans/bodies/{body_id}/position",
    ]

    for topic in expected_topics:
        assert topic in source


def test_required_files_exist():
    """Check that required model and configuration files are included."""
    assert (ROOT / "config" / "00-defaults.yml").is_file()
    assert (ROOT / "config" / "model_cfg_latest_person_tiny.py").is_file()
    assert (
        ROOT
        / "models"
        / "rtmdet-ins_tiny_8xb32-300e_coco_20221130_151727-ec670f7e.pth"
    ).is_file()


def test_console_entry_point_is_declared():
    """Check that the ROS 2 executable is registered."""
    source = SETUP_FILE.read_text(encoding="utf-8")

    assert (
        "hri_person_detect = "
        "hri_person_detect.node_person_detector:main"
    ) in source
