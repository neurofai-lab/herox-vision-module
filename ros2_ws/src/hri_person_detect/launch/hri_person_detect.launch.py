from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('distance_threshold', default_value='200'),
        DeclareLaunchArgument('detection_confidence_score', default_value='0.5'),
        DeclareLaunchArgument('num_cameras', default_value='4'),
        DeclareLaunchArgument('debug_dir', default_value='./debug_output'),
        DeclareLaunchArgument('device', default_value='cuda:0'),
        DeclareLaunchArgument('hri_track_timeout', default_value='1.0'),

        Node(
            package='hri_person_detect',
            executable='hri_person_detect',
            name='camera_subscriber',
            output='screen',
            arguments=[
                '--distance_threshold', LaunchConfiguration('distance_threshold'),
                '--detection_confidence_score', LaunchConfiguration('detection_confidence_score'),
                '--num_cameras', LaunchConfiguration('num_cameras'),
                '--debug_dir', LaunchConfiguration('debug_dir'),
                '--device', LaunchConfiguration('device'),
                '--hri_track_timeout', LaunchConfiguration('hri_track_timeout'),
            ],
        )
    ])
