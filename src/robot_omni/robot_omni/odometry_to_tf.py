#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped


class OdometryToTf(Node):
    def __init__(self):
        super().__init__('odometry_to_tf')
        
        self.tf_broadcaster = TransformBroadcaster(self)
        
        # Subscribe to odometry topic
        self.subscription = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )
        
    def odom_callback(self, msg: Odometry):
        """Convert odometry message to TF transform"""
        t = TransformStamped()
        
        # Header info
        t.header.stamp = msg.header.stamp
        t.header.frame_id = msg.header.frame_id  # Usually "odom"
        t.child_frame_id = msg.child_frame_id    # Usually "base_footprint"
        
        # Position
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        
        # Orientation
        t.transform.rotation = msg.pose.pose.orientation
        
        # Publish TF
        self.tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = OdometryToTf()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
