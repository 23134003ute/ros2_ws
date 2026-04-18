import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, SetEnvironmentVariable, DeclareLaunchArgument
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg = get_package_share_directory('robot_omni')
    
    # ====================== LAUNCH CONFIGURATIONS ======================
    disable_map_publish = LaunchConfiguration('disable_map_publish', default='false')
    
    urdf_file = os.path.join(pkg, 'urdf', 'omni_base.urdf')
    # Use absolute path to world file in source directory
    world_file = '/home/sup/ros2_ws/src/robot_omni/worlds/hospital_full.world'
    bridge_config = os.path.join(pkg, 'config', 'bridge_config.yaml')
    controller_config = os.path.join(pkg, 'config', 'configuration.yaml')

    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    # ====================== ENVIRONMENT ======================
    # Set resource path to find models in source directory
    robot_omni_src = '/home/sup/ros2_ws/src/robot_omni'
    src_models_path = os.path.join(robot_omni_src, 'models')
    src_worlds_path = os.path.join(robot_omni_src, 'worlds')
    hospital_models_path = '/home/sup/ros2_ws/src/aws-robomaker-hospital-world/models'
    
    set_gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=f"{robot_omni_src}:{src_models_path}:{src_worlds_path}:{hospital_models_path}"
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

    # ====================== CORE NODES ======================
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
        arguments=['--x', '0', '--y', '0', '--z', '0.0762', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'base_footprint', '--child-frame-id', 'base_link'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # Static transform: odom → base_footprint (required by local costmap)
    static_tf_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'odom', '--child-frame-id', 'base_footprint'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # Static transform: map → odom (fallback if AMCL hasn't initialized)
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0', '--frame-id', 'map', '--child-frame-id', 'odom'],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': f'-r {world_file}'}.items(),
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-topic', 'robot_description',
            '-name', 'omni_base',
            '-x', '0.0',
            '-y', '12',
            '-z', '0.15',
            '-Y', '4.712'
        ],
        output='screen'
    )

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

    # ====================== SLAM ======================
    cartographer_config_dir = os.path.join(pkg, 'config')

    cartographer_node = Node(
        package='cartographer_ros',
        executable='cartographer_node',
        name='cartographer_node',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=[
            '-configuration_directory', cartographer_config_dir,
            '-configuration_basename', 'omni_2d.lua'
        ],
        remappings=[('scan', 'scan_1')]
    )

    occupancy_grid_node = Node(
        package='cartographer_ros',
        executable='cartographer_occupancy_grid_node',
        name='cartographer_occupancy_grid_node',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=['-resolution', '0.05', '-publish_period_sec', '1.0'],
        condition=UnlessCondition(disable_map_publish)
    )

    # ====================== VISUALIZATION & CONTROL ======================
    # (RViz and rqt_steering removed - only Gazebo)

    # ====================== DELAYS ======================
    delayed_spawn = TimerAction(period=20.0, actions=[spawn_robot])
    delayed_bridge = TimerAction(period=22.0, actions=[bridge])
    delayed_odometry_to_tf = TimerAction(period=25.0, actions=[odometry_to_tf])
    delayed_controllers = TimerAction(period=27.0, actions=[joint_state_broadcaster, mobile_base_controller])
    delayed_slam = TimerAction(
        period=30.0,
        actions=[cartographer_node, occupancy_grid_node]
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'disable_map_publish',
            default_value='false',
            description='Whether to disable Cartographer map publishing to occupancy_grid_node...'
        ),
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
        delayed_slam,
    ])