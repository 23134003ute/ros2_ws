import math
import re
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

POINTS_FILE_PATH = '/home/sup/Downloads/points.txt'


def euler_to_quaternion(yaw: float) -> tuple:
    half = yaw / 2
    return (0.0, 0.0, math.sin(half), math.cos(half))


def reverse_yaw(yaw: float) -> float:
    new_yaw = yaw + math.pi
    return math.atan2(math.sin(new_yaw), math.cos(new_yaw))


def parse_points_file(file_path: str) -> dict:
    """Parse points.txt file và tạo dict rooms.
    Mỗi 3 điểm liên tiếp là: door, inside, center
    """
    rooms = {}
    points = []
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Tách các block điểm bằng dấu ---
    blocks = content.strip().split('---')
    
    for block in blocks:
        if not block.strip():
            continue
        
        # Parse từng block để lấy x, y, z
        x_match = re.search(r'x:\s*([\d\-\.]+)', block)
        y_match = re.search(r'y:\s*([\d\-\.]+)', block)
        z_match = re.search(r'z:\s*([\d\-\.]+)', block)
        
        if x_match and y_match:
            points.append({
                'x': float(x_match.group(1)),
                'y': float(y_match.group(1)),
                'z': float(z_match.group(1)) if z_match else 0.0
            })
    
    # Nhóm 3 điểm thành 1 phòng
    for i in range(0, len(points), 3):
        if i + 2 < len(points):
            room_num = i // 3 + 1
            room_id = f'room_{room_num}'
            
            rooms[room_id] = {
                'door': points[i],
                'inside': points[i + 1],
                'center': points[i + 2]
            }
    
    return rooms


class RoomNavigator(Node):
    def __init__(self):
        super().__init__('room_navigator')

        self._client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Parse dữ liệu từ points.txt
        self.rooms = parse_points_file(POINTS_FILE_PATH)

        self.current_room = None

        self.get_logger().info(f"Đã tải {len(self.rooms)} phòng từ points.txt")

    def reverse_pose(self, pose: dict) -> dict:
        return {
            'x': pose['x'],
            'y': pose['y'],
            'yaw': reverse_yaw(float(pose.get('yaw', 0.0)))
        }

    def _build_goal(self, pose: dict) -> NavigateToPose.Goal:
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = float(pose['x'])
        goal.pose.pose.position.y = float(pose['y'])

        qx, qy, qz, qw = euler_to_quaternion(float(pose.get('yaw', 0.0)))
        goal.pose.pose.orientation.x = qx
        goal.pose.pose.orientation.y = qy
        goal.pose.pose.orientation.z = qz
        goal.pose.pose.orientation.w = qw

        return goal

    def navigate_to(self, pose: dict, label: str = '') -> bool:
        self.get_logger().info(
            f"➡️ {label}: x={pose['x']:.2f}, y={pose['y']:.2f}"
        )

        self._client.wait_for_server()

        future = self._client.send_goal_async(self._build_goal(pose))
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()

        if not handle.accepted:
            self.get_logger().error("❌ Goal bị từ chối!")
            return False

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        return True

    def go_to_room(self, room_num: str):
        room_id = f'room_{room_num}'

        if room_id not in self.rooms:
            print(f"❌ Không tìm thấy phòng: {room_num}")
            return

        # ✅ tránh đi lại cùng phòng
        if self.current_room == room_num:
            print("⚠️ Robot đã ở phòng này rồi!")
            return

        target_room = self.rooms[room_id]

        print(f"\n📍 Phòng hiện tại: {self.current_room}")
        print(f"➡️ Đang đi đến phòng: {room_num}")

        # =========================
        # 🟥 1. THOÁT PHÒNG HIỆN TẠI
        # =========================
        if self.current_room is not None:
            current_id = f'room_{self.current_room}'
            current_room = self.rooms[current_id]

            print(f"🔙 Thoát phòng {self.current_room}...")

            # center -> inside (quay đầu)
            inside_rev = self.reverse_pose(current_room['inside'])
            if not self.navigate_to(inside_rev, f"thoát inside phòng {self.current_room}"):
                return

            # inside -> door (quay đầu)
            door_rev = self.reverse_pose(current_room['door'])
            if not self.navigate_to(door_rev, f"thoát cửa phòng {self.current_room}"):
                return

        # =========================
        # 🟩 2. ĐI ĐẾN PHÒNG MỚI
        # =========================
        print(f"🚀 [1/3] Đến cửa phòng {room_num}...")
        if not self.navigate_to(target_room['door'], f"cửa phòng {room_num}"):
            return

        print(f"🚀 [2/3] Vào trong phòng {room_num}...")
        if not self.navigate_to(target_room['inside'], f"trong phòng {room_num}"):
            return

        print(f"🚀 [3/3] Đến trung tâm phòng {room_num}...")
        if self.navigate_to(target_room['center'], f"trung tâm phòng {room_num}"):
            self.current_room = room_num
            print(f"🏁 Hoàn thành! Robot đang ở phòng {room_num}.")

    def go_to_multiple_rooms(self, room_numbers: list):
        """Điều hướng robot đến 3 phòng liên tiếp"""
        if not room_numbers:
            print("❌ Danh sách phòng trống!")
            return

        print(f"\n🗺️ LỘ TRÌNH: {' → '.join(map(str, room_numbers))}")
        print(f"📊 Tổng số phòng: {len(room_numbers)}")

        for idx, room_num in enumerate(room_numbers, 1):
            print(f"\n{'='*50}")
            print(f"🔢 PHÒNG {idx}/{len(room_numbers)}: {room_num}")
            print(f"{'='*50}")
            self.go_to_room(room_num)
            if self.current_room != room_num:
                print(f"❌ Không thể đến phòng {room_num}! Dừng lộ trình.")
                break

        print(f"\n{'='*50}")
        print(f"✅ HOÀN THÀNH LỘ TRÌNH!")
        print(f"{'='*50}\n")


def main():
    rclpy.init()
    navigator = RoomNavigator()

    print('\n--- HỆ THỐNG ĐIỀU HƯỚNG ROBOT BỆNH VIỆN ---')

    while rclpy.ok():
        try:
            user_input = input("\nNhập số phòng (vd: 1 2 3) hoặc 'exit': ").strip()

            if user_input.lower() == 'exit':
                break

            if user_input:
                # Chuyển đổi input thành danh sách các phòng
                rooms = user_input.split()
                
                if len(rooms) <= 3:
                    navigator.go_to_multiple_rooms(rooms)
                else:
                    print(f"⚠️ Quá nhiều phòng! Chỉ hỗ trợ tối đa 3 phòng, bạn nhập {len(rooms)} phòng.")

        except KeyboardInterrupt:
            break

    navigator.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()