#!/usr/bin/env python
import rospy

import copy
import sys

from mir100_driver import rosbridge
from rospy_message_converter import message_converter

from actionlib_msgs.msg import GoalID, GoalStatusArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from dynamic_reconfigure.msg import Config, ConfigDescription
from geometry_msgs.msg import PolygonStamped, Pose, PoseArray, PoseStamped, PoseWithCovarianceStamped, Twist
from mir_actions.msg import *
from mirMsgs.msg import *
from move_base_msgs.msg import MoveBaseActionFeedback, MoveBaseActionGoal, MoveBaseActionResult, MoveBaseFeedback, MoveBaseResult
from nav_msgs.msg import GridCells, MapMetaData, OccupancyGrid, Odometry, Path
from rosgraph_msgs.msg import Log
from sbpl_lattice_planner.msg import SBPLLatticePlannerStats
from sensor_msgs.msg import Imu, LaserScan, PointCloud2, Range
from std_msgs.msg import Float64, String
from tf.msg import tfMessage
from visualization_msgs.msg import Marker, MarkerArray

class TopicConfig(object):
    def __init__(self, topic, topic_type, latch=False, dict_filter=None):
        self.topic = topic
        self.topic_type = topic_type
        self.latch = latch
        self.dict_filter = dict_filter

# remap mir_actions/MirMoveBaseAction => move_base_msgs/MoveBaseAction
def _move_base_feedback_dict_filter(msg_dict):
    # filter out slots from the dict that are not in our message definition
    # e.g., MiRMoveBaseFeedback has the field "state", which MoveBaseFeedback doesn't
    filtered_msg_dict = copy.deepcopy(msg_dict)
    filtered_msg_dict['feedback'] = {key: msg_dict['feedback'][key] for key in MoveBaseFeedback.__slots__}
    return filtered_msg_dict

def _move_base_result_dict_filter(msg_dict):
    filtered_msg_dict = copy.deepcopy(msg_dict)
    filtered_msg_dict['result'] = {key: msg_dict['result'][key] for key in MoveBaseResult.__slots__}
    return filtered_msg_dict

# topics we want to publish to ROS (and subscribe to from the MiR)
PUB_TOPICS = [
              TopicConfig('LightCtrl/us_list', Range),
              TopicConfig('MissionController/CheckArea/visualization_marker', Marker),
              TopicConfig('SickPLC/parameter_descriptions', ConfigDescription),
              TopicConfig('SickPLC/parameter_updates', Config),
              TopicConfig('amcl_pose', PoseWithCovarianceStamped),
              TopicConfig('b_raw_scan', LaserScan),
              TopicConfig('b_scan', LaserScan),
              TopicConfig('camera_floor/background', PointCloud2),
              TopicConfig('camera_floor/depth/parameter_descriptions', ConfigDescription),
              TopicConfig('camera_floor/depth/parameter_updates', Config),
              TopicConfig('camera_floor/depth/points', PointCloud2),
              TopicConfig('camera_floor/filter/parameter_descriptions', ConfigDescription),
              TopicConfig('camera_floor/filter/parameter_updates', Config),
              TopicConfig('camera_floor/floor', PointCloud2),
              TopicConfig('camera_floor/obstacles', PointCloud2),
              TopicConfig('camera_floor/transform/parameter_descriptions', ConfigDescription),
              TopicConfig('camera_floor/transform/parameter_updates', Config),
              TopicConfig('check_area/polygon', PolygonStamped),
              TopicConfig('diagnostics', DiagnosticArray),
              TopicConfig('diagnostics_agg', DiagnosticArray),
              TopicConfig('diagnostics_toplevel_state', DiagnosticStatus),
              TopicConfig('f_raw_scan', LaserScan),
              TopicConfig('f_scan', LaserScan),
              TopicConfig('imu_data', Imu),  # not available in simulation
              TopicConfig('laser_back/driver/parameter_descriptions', ConfigDescription),
              TopicConfig('laser_back/driver/parameter_updates', Config),
              TopicConfig('laser_back/transform/parameter_descriptions', ConfigDescription),
              TopicConfig('laser_back/transform/parameter_updates', Config),
              TopicConfig('laser_front/driver/parameter_descriptions', ConfigDescription),
              TopicConfig('laser_front/driver/parameter_updates', Config),
              TopicConfig('laser_front/transform/parameter_descriptions', ConfigDescription),
              TopicConfig('laser_front/transform/parameter_updates', Config),
              TopicConfig('map', OccupancyGrid, latch=True),
              TopicConfig('map_metadata', MapMetaData),
              TopicConfig('mir_amcl/parameter_descriptions', ConfigDescription),
              TopicConfig('mir_amcl/parameter_updates', Config),
              TopicConfig('mir_amcl/selected_points', PointCloud2),
              TopicConfig('mir_log', Log),
              TopicConfig('mir_serial_button', serial),
              TopicConfig('mir_sound', String),
              TopicConfig('mir_status', MirStatus),
              TopicConfig('mir_status_msg', String),
#              TopicConfig('mirspawn/node_events', LaunchItem),
              TopicConfig('mirwebapp/grid_map_metadata', LocalMapStat),
              TopicConfig('mirwebapp/laser_map_metadata', LocalMapStat),
#              TopicConfig('move_base/feedback', MirMoveBaseActionFeedback),
#              TopicConfig('move_base/result', MirMoveBaseActionResult),
              TopicConfig('move_base/feedback', MoveBaseActionFeedback, dict_filter=_move_base_feedback_dict_filter),  # really mir_actions/MirMoveBaseActionFeedback
              TopicConfig('move_base/result',   MoveBaseActionResult,   dict_filter=_move_base_result_dict_filter),    # really mir_actions/MirMoveBaseActionResult
              TopicConfig('move_base/status', GoalStatusArray),
              TopicConfig('move_base_node/MIRPlannerROS/cost_cloud', PointCloud2),
              TopicConfig('move_base_node/MIRPlannerROS/global_plan', Path),
              TopicConfig('move_base_node/MIRPlannerROS/len_to_goal', Float64),
              TopicConfig('move_base_node/MIRPlannerROS/local_plan', Path),
              TopicConfig('move_base_node/MIRPlannerROS/parameter_descriptions', ConfigDescription),
              TopicConfig('move_base_node/MIRPlannerROS/parameter_updates', Config),
              TopicConfig('move_base_node/SBPLLatticePlanner/plan', Path),
              TopicConfig('move_base_node/SBPLLatticePlanner/sbpl_lattice_planner_stats', SBPLLatticePlannerStats),
              TopicConfig('move_base_node/SBPLLatticePlanner/visualization_marker', MarkerArray),
              TopicConfig('move_base_node/current_goal', PoseStamped),
              TopicConfig('move_base_node/global_costmap/forbidden_area', GridCells),
              TopicConfig('move_base_node/global_costmap/inflated_obstacles', GridCells),
              TopicConfig('move_base_node/global_costmap/obstacles', GridCells),
              TopicConfig('move_base_node/global_costmap/parameter_descriptions', ConfigDescription),
              TopicConfig('move_base_node/global_costmap/parameter_updates', Config),
              TopicConfig('move_base_node/global_costmap/robot_footprint', PolygonStamped),
              TopicConfig('move_base_node/global_costmap/unknown_space', GridCells),
              TopicConfig('move_base_node/global_plan', Path),
              TopicConfig('move_base_node/local_costmap/forbidden_area', GridCells),
              TopicConfig('move_base_node/local_costmap/inflated_obstacles', GridCells),
              TopicConfig('move_base_node/local_costmap/obstacles', GridCells),
              TopicConfig('move_base_node/local_costmap/parameter_descriptions', ConfigDescription),
              TopicConfig('move_base_node/local_costmap/parameter_updates', Config),
              TopicConfig('move_base_node/local_costmap/robot_footprint', PolygonStamped),
              TopicConfig('move_base_node/local_costmap/unknown_space', GridCells),
              TopicConfig('move_base_node/mir_escape_recovery/visualization_marker', Marker),
              TopicConfig('move_base_node/parameter_descriptions', ConfigDescription),
              TopicConfig('move_base_node/parameter_updates', Config),
              TopicConfig('odom_comb', Odometry),    # odom_comb on real robot, odom on simulator
              TopicConfig('odom_enc', Odometry),
              TopicConfig('particlecloud', PoseArray),
              TopicConfig('relative_move_action/feedback', RelativeMoveActionFeedback),
              TopicConfig('relative_move_action/result', RelativeMoveActionResult),
              TopicConfig('relative_move_action/status', GoalStatusArray),
              TopicConfig('relative_move_node/parameter_descriptions', ConfigDescription),
              TopicConfig('relative_move_node/parameter_updates', Config),
              TopicConfig('relative_move_node/time_to_coll', Float64),
              TopicConfig('relative_move_node/visualization_marker', Marker),
              TopicConfig('robot_mode', RobotMode),
              TopicConfig('robot_pose', Pose),
              TopicConfig('robot_state', RobotState),
              TopicConfig('rosout_agg', Log),
              TopicConfig('scan', LaserScan),
              TopicConfig('scan_filter/visualization_marker', Marker),
              TopicConfig('tf', tfMessage),
              TopicConfig('transform_footprint/parameter_descriptions', ConfigDescription),
              TopicConfig('transform_footprint/parameter_updates', Config),
              TopicConfig('transform_imu/parameter_descriptions', ConfigDescription),
              TopicConfig('transform_imu/parameter_updates', Config)]

# topics we want to subscribe to from ROS (and publish to the MiR)
SUB_TOPICS = [TopicConfig('cmd_vel', Twist),
              TopicConfig('initialpose', PoseWithCovarianceStamped),
              TopicConfig('light_cmd', String),
              TopicConfig('mir_cmd', String),
              TopicConfig('move_base/cancel', GoalID),
#              TopicConfig('move_base/goal', MirMoveBaseActionGoal),
              TopicConfig('move_base/goal', MoveBaseActionGoal),  # really mir_actions/MirMoveBaseActionGoal
              TopicConfig('move_base_simple/goal', PoseStamped),
              TopicConfig('relative_move_action/cancel', GoalID),
              TopicConfig('relative_move_action/goal', RelativeMoveActionGoal)]

class PublisherWrapper(rospy.SubscribeListener):
    def __init__(self, topic_config, robot):
        self.topic_config = topic_config
        self.robot = robot
        self.connected = False
        self.pub = rospy.Publisher(name=topic_config.topic,
                                   data_class=topic_config.topic_type,
                                   subscriber_listener=self,
                                   latch=topic_config.latch,
                                   queue_size=1)
        rospy.loginfo("[%s] publishing topic '%s' [%s]",
                      rospy.get_name(), topic_config.topic, topic_config.topic_type._type)
        # latched topics must be subscribed immediately
        if topic_config.latch:
            self.peer_subscribe(None, None, None)


    def peer_subscribe(self, topic_name, topic_publish, peer_publish):
        if (self.pub.get_num_connections() == 1 and not self.connected) or self.topic_config.latch:
            rospy.loginfo("[%s] starting to stream messages on topic '%s'", rospy.get_name(), self.topic_config.topic)
            self.robot.subscribe(topic=('/' + self.topic_config.topic), callback=self.callback)

    def peer_unsubscribe(self, topic_name, num_peers):
        pass
## doesn't work: once ubsubscribed, robot doesn't let us subscribe again
#         if self.pub.get_num_connections() == 0:
#             rospy.loginfo("[%s] stopping to stream messages on topic '%s'", rospy.get_name(), self.topic_config.topic)
#             self.robot.unsubscribe(topic=('/' + self.topic_config.topic))

    def callback(self, msg_dict):
        if self.topic_config.dict_filter is not None:
            msg_dict = self.topic_config.dict_filter(msg_dict)
        msg = message_converter.convert_dictionary_to_ros_message(self.topic_config.topic_type._type, msg_dict)
        self.pub.publish(msg)

class SubscriberWrapper(object):
    def __init__(self, topic_config, robot):
        self.topic_config = topic_config
        self.robot = robot
        self.sub = rospy.Subscriber(name=topic_config.topic,
                                    data_class=topic_config.topic_type,
                                    callback=self.callback,
                                    queue_size=1)
        rospy.loginfo("[%s] subscribing to topic '%s' [%s]",
                      rospy.get_name(), topic_config.topic, topic_config.topic_type._type)

    def callback(self, msg):
        msg_dict = message_converter.convert_ros_message_to_dictionary(msg)
        if self.topic_config.dict_filter is not None:
            msg_dict = self.topic_config.dict_filter(msg_dict)
        self.robot.publish('/' + self.topic_config.topic, msg_dict)

class MiR100Bridge(object):
    def __init__(self):
        try:
            hostname = rospy.get_param('~hostname')
        except KeyError:
            rospy.logfatal('[%s] parameter "hostname" is not set!', rospy.get_name())
            sys.exit(-1)
        port = rospy.get_param('~port', 9090)

        rospy.loginfo('[%s] trying to connect to %s:%i...', rospy.get_name(), hostname, port)
        self.robot = rosbridge.RosbridgeSetup(hostname, port)

        r = rospy.Rate(10)
        i = 1
        while not self.robot.is_connected():
            if rospy.is_shutdown():
                sys.exit(0)
            if self.robot.is_errored():
                rospy.logfatal('[%s] connection error to %s:%i, giving up!', rospy.get_name(), hostname, port)
                sys.exit(-1)
            if i % 10 == 0:
                rospy.logwarn('[%s] still waiting for connection to %s:%i...', rospy.get_name(), hostname, port)
            i += 1
            r.sleep()

        rospy.loginfo('[%s] ... connected.', rospy.get_name())

        topics = self.get_topics()
        published_topics = [topic_name for (topic_name, _, has_publishers, _) in topics if has_publishers]
        subscribed_topics = [topic_name for (topic_name, _, _, has_subscribers) in topics if has_subscribers]

        for pub_topic in PUB_TOPICS:
            PublisherWrapper(pub_topic, self.robot)
            if ('/' + pub_topic.topic) not in published_topics:
                rospy.logwarn("[%s] topic '%s' is not published by the MiR!", rospy.get_name(), pub_topic.topic)

        for sub_topic in SUB_TOPICS:
            SubscriberWrapper(sub_topic, self.robot)
            if ('/' + sub_topic.topic) not in subscribed_topics:
                rospy.logwarn("[%s] topic '%s' is not yet subscribed to by the MiR!", rospy.get_name(), sub_topic.topic)

    def get_topics(self):
        srv_response = self.robot.callService('/rosapi/topics', msg={})
        topic_names = sorted(srv_response['topics'])
        topics = []

        for topic_name in topic_names:
            srv_response = self.robot.callService("/rosapi/topic_type", msg={'topic': topic_name})
            topic_type = srv_response['type']

            srv_response = self.robot.callService("/rosapi/publishers", msg={'topic': topic_name})
            has_publishers = True if len(srv_response['publishers']) > 0 else False

            srv_response = self.robot.callService("/rosapi/subscribers", msg={'topic': topic_name})
            has_subscribers = True if len(srv_response['subscribers']) > 0 else False

            topics.append([topic_name, topic_type, has_publishers, has_subscribers])

        print 'Publishers:'
        for (topic_name, topic_type, has_publishers, has_subscribers) in topics:
            if has_publishers:
                print ' * %s [%s]' % (topic_name, topic_type)

        print '\nSubscribers:'
        for (topic_name, topic_type, has_publishers, has_subscribers) in topics:
            if has_subscribers:
                print ' * %s [%s]' % (topic_name, topic_type)

        return topics


def main():
    rospy.init_node('mir100_bridge')
    MiR100Bridge()
    rospy.spin()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass