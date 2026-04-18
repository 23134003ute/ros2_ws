#!/usr/bin/env python3
#
# Copyright 2019 ROBOTIS CO., LTD.
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
#
# Authors: Joep Tool, Hyungyu Kim

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_path = get_package_share_directory('robot_simulation')
    pkg_share = FindPackageShare('robot_simulation')

    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    sanitized_ld_library_path = ':'.join(
        p for p in ld_library_path.split(':')
        if p and not p.startswith('/snap/')
    )

    # VS Code installed via Snap can inject GTK/XDG vars that may break rviz2.
    # Clear these per-process to keep rviz2 stable.
    clean_gui_env = {
        'LD_LIBRARY_PATH': sanitized_ld_library_path,
        'GTK_PATH': '',
        'GTK_MODULES': '',
        'GTK_EXE_PREFIX': '',
        'XDG_DATA_DIRS': '/usr/local/share:/usr/share',
    }

    # Keep arguments similar to the TurtleBot3 tutorial style.
    use_sim_time = LaunchConfiguration('use_sim_time')
    gui = LaunchConfiguration('gui')
    use_cmd_vel_relay = LaunchConfiguration('use_cmd_vel_relay')

    start_rviz = LaunchConfiguration('start_rviz')
    start_delay_sec = LaunchConfiguration('start_delay_sec')
    scan_topic = LaunchConfiguration('scan_topic')

    config_dir = PathJoinSubstitution([pkg_share, 'config', 'cartographer'])
    rviz_config = PathJoinSubstitution([pkg_share, 'config', 'rviz', 'omni_cartographer.rviz'])

    urdf_file = os.path.join(robot_path, 'urdf', 'omni_base.urdf')
    with open(urdf_file, 'r', encoding='utf-8') as urdf_fp:
        robot_description = urdf_fp.read()

    # TurtleBot3-like "create_map": start sim + SLAM + RViz.
    # Bringup Gazebo/spawn/bridges/controllers from our existing launch.
    sim_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_share, 'launch', 'controler.launch.py'])
        ),
        launch_arguments={
            'gui': gui,
            'use_cmd_vel_relay': use_cmd_vel_relay,
        }.items(),
    )

    cartographer_node = Node(
        package='cartographer_ros',
        executable='cartographer_node',
        name='cartographer_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        additional_env=clean_gui_env,
        arguments=[
            '-configuration_directory', config_dir,
            '-configuration_basename', 'omni_base_2d.lua',
        ],
        remappings=[
            ('scan', scan_topic),
        ],
    )

    occupancy_grid_node = Node(
        package='cartographer_ros',
        executable='cartographer_occupancy_grid_node',
        name='cartographer_occupancy_grid_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'resolution': 0.05},
            {'publish_period_sec': 1.0},
        ],
        additional_env=clean_gui_env,
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[
            {'use_sim_time': use_sim_time},
            {'robot_description': robot_description},
        ],
        additional_env=clean_gui_env,
        condition=IfCondition(start_rviz),
    )

    # Bridge frame naming differences:
    # The controller publishes Odometry with frame_id "robot_simulation/odom".
    # Cartographer publishes TF using "odom" and "map". This identity transform
    # allows RViz to visualize the Odometry arrow in the map frame.
    odom_frame_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='odom_frame_bridge',
        output='screen',
        arguments=[
            '--frame-id', 'odom',
            '--child-frame-id', 'robot_simulation/odom',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        additional_env=clean_gui_env,
    )

    # Cartographer needs TF + LaserScan; delay startup so Gazebo + bridges are ready.
    start_slam = TimerAction(
        period=start_delay_sec,
        actions=[odom_frame_bridge, cartographer_node, occupancy_grid_node, rviz_node],
    )




    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true.',
        ),
        DeclareLaunchArgument(
            'scan_topic',
            default_value='/scan_front',
            description='LaserScan topic to use for SLAM (e.g. /scan_front).',
        ),
        DeclareLaunchArgument(
            'gui',
            default_value='true',
            description='Run Gazebo with GUI (true) or server-only/headless (false).',
        ),
        DeclareLaunchArgument(
            'use_cmd_vel_relay',
            default_value='true',
            description='Relay /cmd_vel (Twist) to controller reference (TwistStamped).',
        ),
        DeclareLaunchArgument(
            'start_rviz',
            default_value='true',
            description='Start RViz with packaged config.',
        ),
        DeclareLaunchArgument(
            'start_delay_sec',
            default_value='6.0',
            description='Delay before starting Cartographer/RViz (seconds).',
        ),
        sim_bringup,
        start_slam,
    ])
