# Copyright 2019 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Get robot_omni package share directory
    pkg_omni = get_package_share_directory('robot_omni')
    
    # Read URDF file
    urdf_file = os.path.join(pkg_omni, 'urdf', 'omni_base.urdf')
    with open(urdf_file, 'r') as f:
        robot_description = f.read()
    
    map_dir = LaunchConfiguration(
        'map',
        default=os.path.join(pkg_omni, 'maps', 'map_hospital_1.yaml'))

    param_dir = LaunchConfiguration(
        'params_file',
        default=os.path.join(pkg_omni, 'config', 'nav2_omni.yaml'))

    nav2_launch_file_dir = os.path.join(get_package_share_directory('nav2_bringup'), 'launch')

    rviz_config_dir = os.path.join(pkg_omni, 'config', 'rviz', 'omni_nav2.rviz')
    
    # Robot state publisher to broadcast transforms from URDF
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[
            {'robot_description': robot_description},
            {'use_sim_time': use_sim_time},
            {'publish_frequency': 10.0},
            {'frame_prefix': ''}
        ],
        output='screen'
    )
    
    # Static transform: base_footprint (fallback if robot_state_publisher fails)
    static_tf_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0.0762', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'base_footprint', '--child-frame-id', 'base_link'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Static transforms for odometry frame (required for stable localization)
    static_tf_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'odom', '--child-frame-id', 'base_footprint'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'map', '--child-frame-id', 'odom'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Odometry to TF broadcaster (converts /odom topic to TF)
    odometry_to_tf = Node(
        package='manual_navigation',
        executable='odometry_to_tf',
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Relay node: relay smoothed cmd_vel from Nav2 to mobile_base_controller
    relay_node = Node(
        package='topic_tools',
        executable='relay',
        name='relay_cmd_vel',
        arguments=['/cmd_vel_smoothed', '/mobile_base_controller/reference'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Nav2 bringup (delayed to ensure transforms and map are ready)
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([nav2_launch_file_dir, '/bringup_launch.py']),
        launch_arguments={
            'map': map_dir,
            'use_sim_time': use_sim_time,
            'params_file': param_dir}.items(),
    )
    
    delayed_nav2 = TimerAction(period=15.0, actions=[nav2_launch])

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value=map_dir,
            description='Full path to map file to load'),

        DeclareLaunchArgument(
            'params_file',
            default_value=param_dir,
            description='Full path to param file to load'),

        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'),

        robot_state_publisher,

        static_tf_publisher,

        static_tf_map_odom,

        static_tf_odom,

        odometry_to_tf,

        relay_node,

        delayed_nav2,

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_dir],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'),
    ])
