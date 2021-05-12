import os
import sys
from collections import defaultdict


PHASE_LANES = {
        1 : [ 1,  7],
        2 : [ 2,  8],
        3 : [ 4, 10],
        4 : [ 5, 11],
        5 : [ 1,  2],
        6 : [ 4,  5],
        7 : [ 7,  8],
        8 : [10, 11],
        }

DEST_LANES = {
        1 : [16, 17, 18],
        2 : [19, 20, 21],
        3 : [22, 23, 24],
        4 : [19, 20, 21],
        5 : [22, 23, 24],
        6 : [13, 14, 15],
        7 : [22, 23, 24],
        8 : [13, 14, 15],
        9 : [16, 17, 18],
       10 : [13, 14, 15],
       11 : [16, 17, 18],
       12 : [19, 20, 21],
        }

VEH_LENGTH = 5.0


class TestAgent():
    def __init__(self):
        self.now_phase = {}
        self.green_sec = 40
        self.green_sec_max = 180
        self.max_phase = 4
        self.last_change_step = {}
        self.agent_list = []
        self.phase_passablelane = {}
        self.intersections = {}
        self.roads = {}
        self.agents = {}
    ################################
    # don't modify this function.
    # agent_list is a list of agent_id
    def load_agent_list(self,agent_list):
        self.agent_list = agent_list
        self.now_phase = dict.fromkeys(self.agent_list,1)
        self.last_change_step = dict.fromkeys(self.agent_list,0)

    # intersections[key_id] = {
    #     'have_signal': bool,
    #     'end_roads': list of road_id. Roads that end at this intersection. The order is random.
    #     'start_roads': list of road_id. Roads that start at this intersection. The order is random.
    #     'lanes': list, contains the lane_id in. The order is explained in Docs.
    # }
    # roads[road_id] = {
    #     'start_inter':int. Start intersection_id.
    #     'end_inter':int. End intersection_id.
    #     'length': float. Road length.
    #     'speed_limit': float. Road speed limit.
    #     'num_lanes': int. Number of lanes in this road.
    #     'inverse_road':  Road_id of inverse_road.
    #     'lanes': dict. roads[road_id]['lanes'][lane_id] = list of 3 int value. Contains the Steerability of lanes.
    #               lane_id is road_id*100 + 0/1/2... For example, if road 9 have 3 lanes, then their id are 900, 901, 902
    # }
    # agents[agent_id] = list of length 8. contains the inroad0_id, inroad1_id, inroad2_id,inroad3_id, outroad0_id, outroad1_id, outroad2_id, outroad3_id
    def load_roadnet(self,intersections, roads, agents):
        self.intersections = intersections
        self.roads = roads
        self.agents = agents
    ################################

    def get_queue_lengths(self, agent, phase, laneVehs):
        result = 0
        # count vehicles that are "slow" or that can reach the intersection
        # within the next 10s
        hasRoad = False
        hasDestRoad = False
        for index in PHASE_LANES[phase]:
            vehs = []
            lane = self.intersections[agent]['lanes'][index - 1]
            if lane == -1:
                continue
            hasRoad = True
            road = int(lane / 100)
            speedLimit = self.roads[road]['speed_limit']
            length = self.roads[road]['length']
            dstLane0 = self.intersections[agent]['lanes'][DEST_LANES[index][0] - 1]
            if dstLane0 == -1:
                continue
            hasDestRoad = True
            dstRoad = int(dstLane0 / 100)
            dstLength = self.roads[dstRoad]['length']
            dstSum = 0
            dstSpeed = 0
            dstSpeedLimit = self.roads[dstRoad]['speed_limit']
            for dstIndex in DEST_LANES[index]:
                dstLane = self.intersections[agent]['lanes'][dstIndex - 1]
                dstSum += len(laneVehs[dstLane])
                for veh, vehData in laneVehs[dstLane]:
                    dstSpeed += vehData['speed'][0]
            dstRelSpeed = (dstSpeed / dstSum) / dstSpeedLimit if dstSum > 0 else 1.0

            # road is more than 66% full and slow
            if dstSum * VEH_LENGTH > dstLength * 3 / 1.5 and dstRelSpeed < 0.1:
                print("%s ignoring queue phase=%s index=%s lane=%s targetRoad=%s len=%s targetVehs=%s, dstSpeed=%s, dstRelSpeed=%s" % (
                    agent, phase, index, lane, dstRoad, dstLength, dstSum, dstSpeed, dstRelSpeed))
                continue

            for veh, vehData in laneVehs[lane]:
                lastEdge = vehData['route'][-1]
                if road != lastEdge:
                    speed = vehData['speed'][0]
                    stoplineDist = length - vehData['distance'][0]
                    if (speed < 0.5 * speedLimit) or (stoplineDist / speedLimit < 10):
                        result += 1
                        vehs.append(veh)
            #print(phase, index, lane, vehs)
        if hasRoad and hasDestRoad:
            return result
        else:
            return -1


    def act(self, obs):

        #print(self.intersections['12372852614']['lanes'])
        #for junctionID in self.intersections:
        #    print(junctionID, self.intersections[junctionID]['lanes'])
        #sys.exit()



        """ !!! MUST BE OVERRIDED !!!
        """
        # here obs contains all of the observations and infos

        # observations is returned 'observation' of env.step()
        # info is returned 'info' of env.step()
        observations = obs['observations']
        info = obs['info']
        #print(obs)
        actions = {}


        # preprocess observations
        observations_for_agent = {}
        for key,val in observations.items():
            observations_agent_id = int(key.split('_')[0])
            observations_feature = key[key.find('_')+1:]
            if(observations_agent_id not in observations_for_agent.keys()):
                observations_for_agent[observations_agent_id] = {}
            observations_for_agent[observations_agent_id][observations_feature] = val

        laneVehs = defaultdict(list) # lane -> (veh, vehData)
        for veh, vehData in info.items():
            laneVehs[vehData['drivable'][0]].append((veh, vehData))


        # get actions
        for agent in self.agent_list:
            # select the now_step
            for k,v in observations_for_agent[agent].items():
                now_step = v[0]
                break
            step_diff = now_step - self.last_change_step[agent]

            #numVehs = observations_for_agent[agent]['lane_vehicle_num']
            #vehSpeeds = observations_for_agent[agent]['lane_speed']

            DEBUGID = None # 42381408549

            queue_lengths = [(self.get_queue_lengths(agent, p, laneVehs), p) for p in range(1,9)]
            queue_lengths.sort(reverse=True)
            length, newPhase = queue_lengths[0]
            oldPhase = self.now_phase[agent]
            if step_diff > self.green_sec_max and newPhase == oldPhase:
                length, newPhase = queue_lengths[1]
                if agent == DEBUGID:
                    print(now_step, agent, "oldPhase", oldPhase, "maxDuration, newPhase", newPhase)
            self.now_phase[agent] = newPhase
            if agent == DEBUGID:
                print(now_step, agent, queue_lengths, newPhase)
            if newPhase != oldPhase:
                self.last_change_step[agent] = now_step
                actions[agent] = self.now_phase[agent]
                if agent == DEBUGID:
                    print(now_step, agent, newPhase)

        # print(self.intersections,self.roads,self.agents)
        #print(now_step, actions)
        return actions

scenario_dirs = [
    "test"
]

agent_specs = dict.fromkeys(scenario_dirs, None)
for i, k in enumerate(scenario_dirs):
    # initialize an AgentSpec instance with configuration
    agent_specs[k] = TestAgent()

