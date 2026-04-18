# Robot Omni

Dự án này là một workspace ROS 2 cho robot omni, bao gồm các cấu hình, launch files, mô hình 3D, bản đồ và mã nguồn điều khiển robot.

## Cấu trúc thư mục

- `config/` - Các file cấu hình cho robot, SLAM, navigation, rviz...
- `launch/` - Các file launch cho ROS 2 (khởi động mô phỏng, SLAM, navigation...)
- `maps/` - Bản đồ sử dụng cho SLAM và navigation
- `meshes/` - Meshes 3D cho các thành phần robot (base, wheels, sensors...)
- `models/` - Các mô hình 3D cho môi trường mô phỏng (bệnh viện, đồ vật...)
- `robot_omni/` - Mã nguồn chính của package
- `urdf/` - File mô tả robot URDF
- `worlds/` - Các file mô phỏng thế giới (Gazebo)
- `go_to_room.py` - Script điều khiển robot di chuyển đến phòng
- `CMakeLists.txt`, `package.xml` - File cấu hình ROS 2 package

## Hướng dẫn sử dụng

1. **Cài đặt ROS 2** (Jazzy)
2. **Clone repository:**
   ```bash
   git clone [<repo_url>](https://github.com/23134003ute/ros2_ws.git)
   ```
3. **Build workspace:**
   ```bash
   colcon build
   ```
4. **Nguồn workspace:**
   ```bash
   source install/setup.bash
   ```
5. **Chạy mô phỏng hoặc các launch file:**
   ```bash
   ros2 launch robot_omni gazebo_control_with_slam.launch.py disable_map_publish:=true -> Chạy Gazebo và Spawn Robot Omni
   ros2 launch robot_omni navigation2.launch.py -> Chạy NAV2 để điều khiển robot
   python3 go_to_room.py -> Điều khiển Robot tới số phòng 
   ```

## Thông tin thêm
- Cấu hình chi tiết trong các file `.yaml` trong thư mục `config/`
- Có thể chỉnh sửa mô hình robot trong `urdf/`
- Thêm bản đồ mới vào `maps/`
- Thêm mô hình môi trường vào `models/`

## Thành viên
Lương Gia Bảo - 23134003
Trịnh Nhựt Phát - 23134044

---


