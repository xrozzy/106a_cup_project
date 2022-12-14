from collections import OrderedDict
import numpy as np
from sawyer_control.envs.sawyer_env_base import SawyerEnvBase
from sawyer_control.core.serializable import Serializable
from sawyer_control.core.eval_util import get_stat_in_paths, \
    create_stats_ordered_dict
from gym.spaces import Box
import rospy

import time

class SawyerReachXYZEnv(SawyerEnvBase):
    def __init__(self,
                 fixed_goal=(1, 1, 1),
                 indicator_threshold=.05,
                 reward_type='hand_distance',
                 goal_low=None,
                 goal_high=None,
                 **kwargs
                 ):
        Serializable.quick_init(self, locals())
        SawyerEnvBase.__init__(self, **kwargs)
        if self.action_mode == 'torque':
            if goal_low is None:
                goal_low = self.config.TORQUE_SAFETY_BOX.low
            if goal_high is None:
                goal_high = self.config.TORQUE_SAFETY_BOX.high
        else:
            if goal_low is None:
                goal_low = self.config.POSITION_SAFETY_BOX.low
            if goal_high is None:
                goal_high = self.config.POSITION_SAFETY_BOX.high
        self.goal_space = Box(goal_low, goal_high, dtype=np.float32)
        self.indicator_threshold=indicator_threshold
        self.reward_type = reward_type
        self._state_goal = np.array(fixed_goal)

    def _get_obs(self):
        if self.action_mode=='position':
            return self._get_endeffector_pose()[:3]
        else:
            return super()._get_obs()

    def compute_rewards(self, actions, obs, goals):
        distances = np.linalg.norm(obs - goals, axis=1)
        if self.reward_type == 'hand_distance':
            r = -distances
        elif self.reward_type == 'hand_success':
            r = -(distances < self.indicator_threshold).astype(float)
        else:
            raise NotImplementedError("Invalid/no reward type.")
        return r

    def _get_info(self):
        hand_distance = np.linalg.norm(self._state_goal - self._get_endeffector_pose()[:3])
        return dict(
            hand_distance=hand_distance,
            hand_success=(hand_distance<self.indicator_threshold).astype(float)
        )
    def _set_observation_space(self):
        if self.action_mode=='position':
            lows = np.hstack((
                self.config.END_EFFECTOR_VALUE_LOW['position'],
            ))
            highs = np.hstack((
                self.config.END_EFFECTOR_VALUE_HIGH['position'],
            ))
        else:
            lows = np.hstack((
                self.config.JOINT_VALUE_LOW['position'],
                self.config.JOINT_VALUE_LOW['velocity'],
                self.config.END_EFFECTOR_VALUE_LOW['position'],
                self.config.END_EFFECTOR_VALUE_LOW['angle'],
            ))
            highs = np.hstack((
                self.config.JOINT_VALUE_HIGH['position'],
                self.config.JOINT_VALUE_HIGH['velocity'],
                self.config.END_EFFECTOR_VALUE_HIGH['position'],
                self.config.END_EFFECTOR_VALUE_HIGH['angle'],
            ))

        self.observation_space = Box(
            lows,
            highs,
            dtype=np.float32,
        )

    def get_diagnostics(self, paths, prefix=''):
        statistics = OrderedDict()
        for stat_name in []:
            stat_name = stat_name
            stat = get_stat_in_paths(paths, 'env_infos', stat_name)
            statistics.update(create_stats_ordered_dict(
                '%s%s' % (prefix, stat_name),
                stat,
                always_show_all_stats=True,
                ))
            statistics.update(create_stats_ordered_dict(
                'Final %s%s' % (prefix, stat_name),
                [s[-1] for s in stat],
                always_show_all_stats=True,
                ))
        return statistics

    """
    Multitask functions
    """

    @property
    def goal_dim(self):
        return 3

    def convert_obs_to_goals(self, obs):
        return obs[:, -3:]

    def set_to_goal(self, goal):
        print("setting to goal", goal)
        for _ in range(50):
            action = goal - self._get_endeffector_pose()[:3]
            clip = True
            #print(action)
            self._position_act(action * self.position_action_scale, clip, self.pos_control_ee_orientation)
            time.sleep(0.05)

        tmp = "r"
        while tmp == "r":
            tmp = input("Press Enter When Ready")

        return self._get_endeffector_pose()[:3]

    def reach_goal_with_tol(self, goal, tol = 0.001, t = 10, orientation = None): # choose larger t here
        self._state_goal = goal
        start_time = rospy.get_time()  # in seconds
        finish_time = start_time + t  # in seconds
        time = rospy.get_time()
        dist = np.inf
        while dist > tol and time < finish_time:
            err = goal - self._get_endeffector_pose()[:3]
            dist = np.linalg.norm(err)
            print('error [m]: ', dist)
            self._position_act(err, clip = False, orientation = orientation) 
            time = rospy.get_time()


