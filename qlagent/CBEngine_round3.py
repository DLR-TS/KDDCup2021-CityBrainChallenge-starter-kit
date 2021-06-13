# -*- coding: utf-8 -*-
from CBEngine_rllib.CBEngine_rllib import CBEngine_rllib as CBEngine_rllib_class


class CBEngine_round3(CBEngine_rllib_class):
    """See CBEngine_rllib_class in /CBEngine_env/env/CBEngine_rllib/CBEngine_rllib.py

    Need to implement reward.

    implementation of observation is optional

    """

    def __init__(self, config):
        super(CBEngine_round3, self).__init__(config)
        self.observation_features = self.gym_dict['observation_features']
        self.custom_observation = self.gym_dict['custom_observation']
        self.observation_dimension = self.gym_dict['observation_dimension']

    def _get_observations(self):

        if (self.custom_observation == False):
            obs = super(CBEngine_round3, self)._get_observations()
            return obs
        else:
            ############
            # implement your own observation
            #
            obs = {}
            lane_vehs = self.eng.get_lane_vehicles()
            for agent_id, roads in self.agent_signals.items():
                obs[str(agent_id)] = lane_vehs
            return obs
            ############

    def _get_reward(self):

        rwds = {}

        ##################
        ## Example : pressure as reward.
        lane_vehicle = self.eng.get_lane_vehicles()
        for agent_id, roads in self.agent_signals.items():
            result_obs = []
            for lane in self.intersections[agent_id]['lanes']:
                # -1 indicates empty roads in 'signal' of roadnet file
                if (lane == -1):
                    result_obs.append(-1)
                else:
                    # -2 indicates there's no vehicle on this lane
                    if (lane not in lane_vehicle.keys()):
                        result_obs.append(0)
                    else:
                        # the vehicle number of this lane
                        result_obs.append(len(lane_vehicle[lane]))
            pressure = (sum(result_obs[12: 24]) - sum(result_obs[0: 12]))
            rwds[str(agent_id)] = pressure
        ##################

        return rwds
