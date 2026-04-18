#!/usr/bin/env python3
"""
Test script để demonstrate Genetic Algorithm Room Optimizer
Không yêu cầu ROS2 running
"""

import math
import re
import random
import numpy as np
import matplotlib.pyplot as plt

POINTS_FILE_PATH = '/home/sup/Downloads/points.txt'


def parse_points_file(file_path: str) -> dict:
    """Parse points.txt file và tạo dict rooms.
    Mỗi 3 điểm liên tiếp là: door, inside, center
    """
    rooms = {}
    points = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file: {file_path}")
        return {}
    
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


class GeneticAlgorithmRoomOptimizer:
    """Thuật toán GA để tối ưu hóa thứ tự thăm phòng"""
    
    def __init__(self, rooms: dict, pop_size: int = 50, num_generations: int = 100):
        self.rooms = rooms
        self.room_list = list(rooms.keys())
        self.num_rooms = len(self.room_list)
        self.pop_size = pop_size
        self.num_generations = num_generations
        self.best_costs = []
        
    def distance_between_rooms(self, room_id1: str, room_id2: str) -> float:
        """Tính khoảng cách giữa trung tâm của hai phòng"""
        pos1 = self.rooms[room_id1]['center']
        pos2 = self.rooms[room_id2]['center']
        
        dist = math.sqrt(
            (pos1['x'] - pos2['x'])**2 + 
            (pos1['y'] - pos2['y'])**2
        )
        return dist
    
    def calculate_route_cost(self, route: list) -> float:
        """Tính tổng chi phí của một lộ trình (tổng khoảng cách)"""
        if len(route) <= 1:
            return 0
        
        total_distance = 0
        for i in range(len(route)):
            current_room = self.room_list[route[i]]
            next_room = self.room_list[route[(i + 1) % len(route)]]
            total_distance += self.distance_between_rooms(current_room, next_room)
        
        return total_distance
    
    def random_route(self) -> list:
        """Tạo một lộ trình ngẫu nhiên"""
        route = list(range(self.num_rooms))
        random.shuffle(route)
        return route
    
    def crossover(self, parent1: list, parent2: list) -> list:
        """Order Crossover (OX) - Tạo con từ 2 cha"""
        a, b = sorted(random.sample(range(self.num_rooms), 2))
        child = [-1] * self.num_rooms
        child[a:b] = parent1[a:b]
        fill = [gene for gene in parent2 if gene not in child]
        idx = 0
        for i in range(self.num_rooms):
            if child[i] == -1:
                child[i] = fill[idx]
                idx += 1
        return child
    
    def mutate(self, route: list) -> list:
        """Mutation - Hoán đổi hai phòng ngẫu nhiên"""
        i, j = random.sample(range(self.num_rooms), 2)
        route[i], route[j] = route[j], route[i]
        return route
    
    def optimize(self, verbose: bool = True) -> tuple:
        """
        Chạy thuật toán GA để tìm lộ trình tối ưu
        
        Returns:
            (best_route, best_cost, room_order_names)
        """
        # Khởi tạo quần thể
        population = [self.random_route() for _ in range(self.pop_size)]
        self.best_costs = []
        
        # Vòng lặp GA
        for gen in range(self.num_generations):
            # Sắp xếp theo chi phí (tính năng)
            population.sort(key=self.calculate_route_cost)
            best_cost = self.calculate_route_cost(population[0])
            self.best_costs.append(best_cost)
            
            if verbose and gen % 10 == 0:
                print(f"[GA] Generation {gen+1}/{self.num_generations}: Best cost = {best_cost:.4f}")
            
            # Tạo quần thể mới
            new_pop = population[:10]  # Elitism: giữ top 10
            
            # Crossover: 32 con
            for _ in range(32):
                p1, p2 = random.sample(population[:25], 2)
                new_pop.append(self.crossover(p1.copy(), p2.copy()))
            
            # Mutation: 14 con
            for _ in range(14):
                p = random.choice(population[:20])
                new_pop.append(self.mutate(p.copy()))
            
            # Random routes: 4 con
            for _ in range(4):
                new_pop.append(self.random_route())
            
            population = new_pop
        
        # Kết quả cuối cùng
        best_route = min(population, key=self.calculate_route_cost)
        best_cost = self.calculate_route_cost(best_route)
        
        # Chuyển đổi indices thành tên phòng
        room_order_names = [self.room_list[idx] for idx in best_route]
        
        if verbose:
            print(f"\n✅ [GA] Tối ưu hóa hoàn thành!")
            print(f"   Chi phí tối thiểu: {best_cost:.4f}")
            print(f"   Thứ tự phòng: {room_order_names}")
        
        return best_route, best_cost, room_order_names


def visualize_route(rooms: dict, route_indices: list, room_names: list, best_cost: float):
    """Vẽ biểu đồ lộ trình tối ưu"""
    plt.figure(figsize=(10, 8))
    
    # Lấy tọa độ các phòng theo thứ tự tối ưu
    route_coords = []
    for room_id in room_names:
        center = rooms[room_id]['center']
        route_coords.append([center['x'], center['y']])
    
    route_coords = np.array(route_coords)
    
    # Vẽ các điểm
    plt.scatter(route_coords[:, 0], route_coords[:, 1], s=100, c='red', zorder=3, label='Phòng')
    
    # Vẽ đường đi (thêm điểm đầu tiên ở cuối để tạo vòng kín)
    route_closed = np.vstack([route_coords, route_coords[0]])
    plt.plot(route_closed[:, 0], route_closed[:, 1], 'b-', linewidth=2, zorder=2, label='Lộ trình')
    
    # Ghi nhãn các phòng
    for i, (coord, room_id) in enumerate(zip(route_coords, room_names)):
        room_num = room_id.split('_')[1]
        plt.annotate(f'{room_num}', xy=coord, xytext=(5, 5), textcoords='offset points', fontsize=10)
    
    plt.title(f'Lộ trình tối ưu - Tổng khoảng cách: {best_cost:.2f}', fontsize=14, fontweight='bold')
    plt.xlabel('X (m)')
    plt.ylabel('Y (m)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig('/home/sup/Downloads/ga_optimized_route.png', dpi=150)
    print(f"📊 Biểu đồ đã được lưu: /home/sup/Downloads/ga_optimized_route.png")
    plt.show()


def plot_convergence(best_costs: list):
    """Vẽ biểu đồ hội tụ của GA"""
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, len(best_costs) + 1), best_costs, marker='o', linewidth=2)
    plt.title('GA Convergence - Chi phí tốt nhất qua các thế hệ', fontsize=14, fontweight='bold')
    plt.xlabel('Thế hệ')
    plt.ylabel('Chi phí tốt nhất')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('/home/sup/Downloads/ga_convergence.png', dpi=150)
    print(f"📊 Biểu đồ hội tụ đã được lưu: /home/sup/Downloads/ga_convergence.png")
    plt.show()


def main():
    print("="*70)
    print("🤖 TEST GENETIC ALGORITHM ROOM OPTIMIZER")
    print("="*70)
    
    # Đọc dữ liệu phòng
    print("\n📂 Đang đọc dữ liệu phòng từ points.txt...")
    rooms = parse_points_file(POINTS_FILE_PATH)
    
    if not rooms:
        print("❌ Không thể đọc dữ liệu phòng!")
        return
    
    print(f"✅ Đã tải {len(rooms)} phòng")
    print(f"   Danh sách phòng: {list(rooms.keys())}\n")
    
    # Hiển thị tọa độ của các phòng
    print("📍 Tọa độ các phòng (center):")
    for room_id in sorted(rooms.keys()):
        center = rooms[room_id]['center']
        print(f"   {room_id}: ({center['x']:.2f}, {center['y']:.2f})")
    
    # Chạy GA optimizer
    print("\n" + "="*70)
    print("🚀 Chạy Genetic Algorithm...")
    print("="*70 + "\n")
    
    optimizer = GeneticAlgorithmRoomOptimizer(
        rooms=rooms,
        pop_size=50,
        num_generations=100
    )
    
    best_route, best_cost, room_order_names = optimizer.optimize(verbose=True)
    
    # Kết quả chi tiết
    print("\n" + "="*70)
    print("📊 KẾT QUẢ CUỐI CÙNG")
    print("="*70)
    print(f"✅ Tổng khoảng cách: {best_cost:.4f} (đơn vị)")
    print(f"✅ Số phòng: {len(room_order_names)}")
    room_numbers = [rid.split('_')[1] for rid in room_order_names]
    print(f"✅ Thứ tự phòng tối ưu: {' → '.join(room_numbers)}")
    print(f"✅ Chi phí ban đầu (random): {optimizer.calculate_route_cost(list(range(len(rooms)))):.4f}")
    print(f"✅ Cải thiện: {optimizer.calculate_route_cost(list(range(len(rooms)))) - best_cost:.4f}")
    improvement_percent = ((optimizer.calculate_route_cost(list(range(len(rooms)))) - best_cost) / optimizer.calculate_route_cost(list(range(len(rooms))))) * 100
    print(f"✅ Tỷ lệ cải thiện: {improvement_percent:.2f}%")
    print("="*70)
    
    # Vẽ biểu đồ
    print("\n📊 Vẽ biểu đồ...")
    visualize_route(rooms, best_route, room_order_names, best_cost)
    plot_convergence(optimizer.best_costs)
    
    print("\n✅ Hoàn thành!")


if __name__ == '__main__':
    main()
