import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg = get_package_share_directory('robot_omni')

    urdf_file = os.path.join(pkg, 'urdf', 'omni_base.urdf')
    world_file = os.path.join(pkg, 'worlds', 'hospital_full.world')
    bridge_config = os.path.join(pkg, 'config', 'bridge_config.yaml')
    controller_config = os.path.join(pkg, 'config', 'configuration.yaml')

    # Read URDF
    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    # ====================== ENVIRONMENT ======================
    # Cải thiện GZ_SIM_RESOURCE_PATH để Gazebo tìm được models trong hospital world
    models_path = os.path.join(pkg, 'models')
    worlds_path = os.path.join(pkg, 'worlds')

    set_gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=f"{models_path}:{worlds_path}:{os.path.dirname(pkg)}:{os.environ.get('GZ_SIM_RESOURCE_PATH', '')}"
    )

    set_ros_args = SetEnvironmentVariable(
        name='GZ_SIM_SYSTEM_PLUGIN_ARGS',
        value=f'--ros-args --params-file {controller_config}'
    )

    # ====================== GPU RENDERING ======================
    # Enable GPU rendering for better performance
    set_gz_render_engine = SetEnvironmentVariable(
        name='GAZEBO_RENDER_ENGINE',
        value='ogre2'
    )

    set_gz_gui_plugin_path = SetEnvironmentVariable(
        name='GAZEBO_GUI_PLUGIN_PATH',
        value='/opt/ros/jazzy/lib/gz-gui7/plugins'
    )

    # ====================== ROBOT STATE PUBLISHER ======================
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[
            {'robot_description': robot_description},
            {'use_sim_time': True},
            {'publish_frequency': 10.0},
            {'frame_prefix': ''}
        ],
        output='screen'
    )

    # Static transform: base_footprint (fallback if robot_state_publisher fails)
    static_tf_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0.0762', '0', '0', '0', 'base_footprint', 'base_link'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # Static transform: odom → base_footprint (required by local costmap)
    static_tf_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_footprint'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # Static transform: map → odom (fallback if AMCL hasn't initialized)
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # ====================== GAZEBO ======================
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('ros_gz_sim'),
                'launch',
                'gz_sim.launch.py'
            )
        ),
        launch_arguments={'gz_args': f'-r {world_file}'}.items(),
    )

    # ====================== SPAWN ROBOT ======================
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-topic', 'robot_description',
            '-name', 'omni_base',
            '-x', '0.0',
            '-y', '13.5',
            '-z', '0.15',
            '-Y', '1.5708',
        ],
        output='screen'
    )

    # ====================== BRIDGE ======================
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': bridge_config}],
        output='screen'
    )

    # ====================== ODOMETRY TO TF ======================
    # Convert odometry topic to TF transform (odom -> base_footprint)
    odometry_to_tf = Node(
        package='manual_navigation',
        executable='odometry_to_tf',
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # ====================== CONTROLLERS ======================
    joint_state_broadcaster = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    mobile_base_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['mobile_base_controller', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    # ====================== CMD_VEL MONITOR ======================
    # Ensure cmd_vel is published even if DWB has issues
    cmd_vel_monitor = Node(
        package='manual_navigation',
        executable='cmd_vel_monitor',
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # ====================== CARTOGRAPHER ======================
    cartographer_config_dir = os.path.join(pkg, 'config')
    configuration_basename = 'omni_2d.lua'

    cartographer_node = Node(
        package='cartographer_ros',
        executable='cartographer_node',
        name='cartographer_node',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=[
            '-configuration_directory', cartographer_config_dir,
            '-configuration_basename', configuration_basename
        ]
    )

    occupancy_grid_node = Node(
        package='cartographer_ros',
        executable='cartographer_occupancy_grid_node',
        name='cartographer_occupancy_grid_node',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=['-resolution', '0.05', '-publish_period_sec', '1.0']
    )

    # ====================== DELAYED ACTIONS ======================
    delayed_spawn = TimerAction(period=5.0, actions=[spawn_robot])      # tăng nhẹ vì world nặng
    delayed_bridge = TimerAction(period=7.0, actions=[bridge])
    delayed_odometry_to_tf = TimerAction(period=8.0, actions=[odometry_to_tf])  # Start after bridge
    delayed_controllers = TimerAction(
        period=10.0,
        actions=[joint_state_broadcaster, mobile_base_controller]
    )
    delayed_cmd_vel_monitor = TimerAction(period=12.0, actions=[cmd_vel_monitor])
    delayed_slam = TimerAction(
        period=15.0,   # tăng thêm vì world bệnh viện + cartographer
        actions=[cartographer_node, occupancy_grid_node]
    )

    # ====================== LAUNCH DESCRIPTION ======================
    return LaunchDescription([
        set_gz_resource_path,
        set_ros_args,
        set_gz_render_engine,
        set_gz_gui_plugin_path,
        robot_state_publisher,
        static_tf_publisher,
        static_tf_map_odom,
        static_tf_odom,
        gz_sim,
        delayed_spawn,
        delayed_bridge,
        delayed_odometry_to_tf,
        delayed_controllers,
        delayed_cmd_vel_monitor,
        delayed_slam,
    ])