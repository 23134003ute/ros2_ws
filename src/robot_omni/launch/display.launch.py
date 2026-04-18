from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    pkg_path = get_package_share_directory('robot_omni')
    urdf_path = os.path.join(pkg_path, 'urdf', 'omni_base.urdf')

    with open(urdf_path, 'r') as infp:
        robot_description = infp.read()

    return LaunchDescription([

        # Publish robot TF
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[
                {'robot_description': robot_description},
                {'publish_frequency': 10.0},
                {'frame_prefix': ''}
            ],
            output='screen'
        ),

        # Static transform: base_footprint
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0.0762', '0', '0', '0', 'base_footprint', 'base_link'],
            output='screen'
        ),

        # Static transform: odom → base_footprint
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_footprint'],
            output='screen'
        ),

        # Joint State Publisher 

        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen'
        ),

    ])