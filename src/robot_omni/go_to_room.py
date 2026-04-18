#!/usr/bin/env python3
"""
Navigation controller for omnidirectional robot using Nav2.
Navigates robot to specific rooms using coordinates stored in YAML configuration.
"""


import math
import re
import random
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

POINTS_FILE_PATH = '/home/sup/ros2_ws/points.txt'

def euler_to_quaternion(yaw: float) -> tuple:
    half = yaw / 2
    return (0.0, 0.0, math.sin(half), math.cos(half))

def reverse_yaw(yaw: float) -> float:
    new_yaw = yaw + math.pi
    return math.atan2(math.sin(new_yaw), math.cos(new_yaw))

def parse_points_file(file_path: str) -> dict:
    """Parse points.txt file và tạo dict rooms. Mỗi 3 điểm liên tiếp là: door, inside, center"""
    rooms = {}
    points = []
    with open(file_path, 'r') as f:
        content = f.read()
    blocks = content.strip().split('---')
    for block in blocks:
        if not block.strip():
            continue
        x_match = re.search(r'x:\s*([\d\-\.]+)', block)
        y_match = re.search(r'y:\s*([\d\-\.]+)', block)
        z_match = re.search(r'z:\s*([\d\-\.]+)', block)
        if x_match and y_match:
            points.append({
                'x': float(x_match.group(1)),
                'y': float(y_match.group(1)),
                'z': float(z_match.group(1)) if z_match else 0.0
            })
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

def solve_tsp_ga(room_indices, room_points, n_gen=60, pop_size=40):
    # room_indices: list of room numbers (e.g. [2,5,7])
    # room_points: list of (x, y) for each room
    n = len(room_indices)
    dist = lambda i, j: np.linalg.norm(np.array(room_points[i]) - np.array(room_points[j]))
    def route_cost(route):
        return sum(dist(route[i], route[(i+1)%n]) for i in range(n))
    def random_chrom():
        chrom = list(range(n))
        random.shuffle(chrom)
        return chrom
    def crossover(p1, p2):
        a, b = sorted(random.sample(range(n), 2))
        child = [-1]*n
        child[a:b] = p1[a:b]
        fill = [g for g in p2 if g not in child]
        idx = 0
        for i in range(n):
            if child[i] == -1:
                child[i] = fill[idx]
                idx += 1
        return child
    def mutate(chrom):
        i, j = random.sample(range(n), 2)
        chrom[i], chrom[j] = chrom[j], chrom[i]
        return chrom
    # GA loop
    pop = [random_chrom() for _ in range(pop_size)]
    for _ in range(n_gen):
        pop.sort(key=route_cost)
        new_pop = pop[:8]
        for _ in range(20):
            p1, p2 = random.sample(pop[:20], 2)
            new_pop.append(crossover(p1, p2))
        for _ in range(10):
            p = random.choice(pop[:15])
            new_pop.append(mutate(p.copy()))
        pop = new_pop
    best = min(pop, key=route_cost)
    return [room_indices[i] for i in best]


class RoomNavigator(Node):
    def __init__(self):
        super().__init__('room_navigator')
        self._client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
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
        self.get_logger().info(f"➡️ {label}: x={pose['x']:.2f}, y={pose['y']:.2f}")
        self._client.wait_for_server()
        future = self._client.send_goal_async(self._build_goal(pose))
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error(" Goal bị từ chối!")
            return False
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        return True

    def go_to_room(self, room_num: str):
        room_id = f'room_{room_num}'
        if room_id not in self.rooms:
            print(f" Không tìm thấy phòng: {room_num}")
            return
        if self.current_room == room_num:
            print(" Robot đã ở phòng này rồi!")
            return
        target_room = self.rooms[room_id]
        print(f"\n Phòng hiện tại: {self.current_room}")
        print(f" Đang đi đến phòng: {room_num}")
        # Thoát phòng hiện tại
        if self.current_room is not None:
            current_id = f'room_{self.current_room}'
            current_room = self.rooms[current_id]
            print(f" Thoát phòng {self.current_room}...")
            inside_rev = self.reverse_pose(current_room['inside'])
            if not self.navigate_to(inside_rev, f"thoát inside phòng {self.current_room}"):
                return
            door_rev = self.reverse_pose(current_room['door'])
            if not self.navigate_to(door_rev, f"thoát cửa phòng {self.current_room}"):
                return
        # Đến phòng mới
        print(f" [1/3] Đến cửa phòng {room_num}...")
        if not self.navigate_to(target_room['door'], f"cửa phòng {room_num}"):
            return
        print(f" [2/3] Vào trong phòng {room_num}...")
        if not self.navigate_to(target_room['inside'], f"trong phòng {room_num}"):
            return
        print(f" [3/3] Đến trung tâm phòng {room_num}...")
        if self.navigate_to(target_room['center'], f"trung tâm phòng {room_num}"):
            self.current_room = room_num
            print(f"🏁 Hoàn thành! Robot đang ở phòng {room_num}.")

def main():
    rclpy.init()
    navigator = RoomNavigator()
    print('\n--- HỆ THỐNG ĐIỀU HƯỚNG ROBOT OMNI ---')
    while rclpy.ok():
        try:
            user_input = input("\nNhập số phòng (vd: 5 hoặc 5 7 2) hoặc 'exit': ").strip()
            if user_input.lower() == 'exit':
                break
            if user_input:
                room_list = user_input.split()
                # Tối ưu thứ tự đi qua các phòng bằng GA
                if len(room_list) > 1:
                    # Lấy điểm 'door' của từng phòng
                    rooms_dict = navigator.rooms
                    room_indices = []
                    room_points = []
                    for room in room_list:
                        room_id = f'room_{room}'
                        if room_id in rooms_dict:
                            pt = rooms_dict[room_id]['door']
                            room_indices.append(room)
                            room_points.append((pt['x'], pt['y']))
                    if len(room_indices) > 1:
                        order = solve_tsp_ga(room_indices, room_points)
                        print("\n==============================")
                        print("🔎 Thứ tự phòng tối ưu (GA):")
                        for idx, room in enumerate(order):
                            print(f"  {idx+1}. Phòng {room}")
                        print("==============================\n")
                        for room in order:
                            navigator.go_to_room(room)
                        continue
                # Nếu chỉ 1 phòng hoặc không đủ dữ liệu, đi lần lượt
                for room in room_list:
                    navigator.go_to_room(room)
        except KeyboardInterrupt:
            break
    navigator.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()