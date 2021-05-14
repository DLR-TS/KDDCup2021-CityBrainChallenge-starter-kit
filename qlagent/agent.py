import os
import sys
from collections import defaultdict

from gym_cfg import HEADWAY, SLOW_THRESH, JAM_THRESH, MIN_CHECK_LENGTH, JAM_BONUS, MAX_GREEN_SEC, PREFER_DUAL_THRESHOLD



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

PRED_LANES = {
       13 : [ 6,  8, 10],
       14 : [ 6,  8, 10],
       15 : [ 6,  8, 10],
       16 : [ 9, 11,  1],
       17 : [ 9, 11,  1],
       18 : [ 9, 11,  1],
       19 : [12,  2,  4],
       20 : [12,  2,  4],
       21 : [12,  2,  4],
       22 : [ 3,  5,  7],
       23 : [ 3,  5,  7],
       24 : [ 3,  5,  7],
        }

VEH_LENGTH = 5.0  # length read from infos, should be valid, optimize JAM_THRESH instead


class TestAgent():
    def __init__(self):
        self.now_phase = {}
        self.green_sec = 40
        self.max_phase = 4
        self.last_change_step = {}
        self.agent_list = []
        self.phase_passablelane = {}
        self.intersections = {}
        self.roads = {}
        self.agents = {}
        self.agentFiles = {}
        # lane -> bonus
        self.jammed_lanes = defaultdict(lambda : 0)
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

    def get_queue_lengths(self, now_step, agent, phase, laneVehs):
        """return total queue length and maximum lane queue length"""

        result = 0
        assert(len(PHASE_LANES[phase]) == 2)
        queueLengths = [-1, -1]
        # count vehicles that are "slow" or that can reach the intersection
        # within the next 10s
        hasRoad = False
        hasDestRoad = False
        for resultIndex, index in enumerate(PHASE_LANES[phase]):
            laneQ = 0
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

            # road is full and slow
            if dstSum * VEH_LENGTH > dstLength * JAM_THRESH and dstRelSpeed < 0.1:
                print("%s ignoring queue phase=%s index=%s lane=%s targetRoad=%s len=%s targetVehs=%s, dstSpeed=%s, dstRelSpeed=%s" % (
                    agent, phase, index, lane, dstRoad, dstLength, dstSum, dstSpeed, dstRelSpeed))
                continue

            for veh, vehData in laneVehs[lane]:
                lastEdge = vehData['route'][-1]
                if road != lastEdge:
                    speed = vehData['speed'][0]
                    stoplineDist = length - vehData['distance'][0]
                    if (speed < SLOW_THRESH * speedLimit) or (stoplineDist / speedLimit < 10):
                        laneQ += 1
                        vehs.append(veh)

            if length < MIN_CHECK_LENGTH:
                # extend queue upstream
                fromNode = self.roads[road]['start_inter']
                upstreamLanes = self.intersections[fromNode]['lanes']
                signalized = self.intersections[fromNode]['have_signal']

                predLanes = []
                # only signalized nodes define 'lanes'
                if len(upstreamLanes) > 0 and False:
                    assert(lane in upstreamLanes)
                    outIndex = upstreamLanes.index(lane) + 1 # 1-based
                    for predIndex in PRED_LANES[outIndex]:
                        predLane = upstreamLanes[predIndex - 1]
                        if predLane >= 0:
                            predLanes.append(predLane)
                if not signalized:
                    for predRoad in self.intersections[fromNode]['end_roads']:
                        # ignore turnaround
                        if predRoad >= 0 and self.roads[predRoad]['start_inter'] != agent:
                            # add straight connected lane
                            predLanes.append(predRoad * 100 + 1)

                for predLane in predLanes:
                    predRoad = int(predLane / 100)
                    predLength = self.roads[predRoad]['length']
                    for veh, vehData in laneVehs[predLane]:
                        lastEdge = vehData['route'][-1]
                        if predRoad != lastEdge:
                            speed = vehData['speed'][0]
                            stoplineDist = length + predLength - vehData['distance'][0]
                            if (speed < 0.5 * speedLimit) or (stoplineDist / speedLimit < 10):
                                laneQ += 1
                                vehs.append(veh)
                                #print("%s adding pred phase=%s index=%s lane=%s len=%s predRoad=%s predVeh=%s" % (
                                #    agent, phase, index, lane, length, predRoad, veh))

            # apply jam bonus (there might be more vehicles over the horizon)

            #print(phase, index, lane, vehs)
            queueLengths[resultIndex] = laneQ + self.jammed_lanes[lane]

        if hasRoad and hasDestRoad:
            # maximize flow:
            # if two lanes can be discharged (above a minimum queue length) this is always better than discharging only a single lane
            dualFlow = min(queueLengths)
            if dualFlow < PREFER_DUAL_THRESHOLD:
                # sort by total flow instead
                dualFlow = 0
            totalFlow = sum([max(q, 0) for q in queueLengths])
            return dualFlow, totalFlow
        else:
            return -1, -1

    def act(self, obs):
        # observations is returned 'observation' of env.step()
        # info is returned 'info' of env.step()
        observations = obs['observations']
        info = obs['info']
        #print(obs)

        # select the now_step
        now_step = list(observations.values())[0][0]
        actions = {}

        laneVehs = defaultdict(list) # lane -> (veh, vehData)
        for veh, vehData in info.items():
            laneVehs[vehData['drivable'][0]].append((veh, vehData))

        # detect jammed lanes
        checked_lanes = set()
        for agent in self.agent_list:
            for lane in self.intersections[agent]['lanes']:
                if lane >= 0 and lane not in checked_lanes:
                    checked_lanes.add(lane)
                    speedSum = 0
                    numVehs = len(laneVehs[lane])
                    for veh, vehData in laneVehs[lane]:
                        speedSum += vehData['speed'][0]
                    road = int(lane / 100)
                    speedLimit = self.roads[road]['speed_limit']
                    length = self.roads[road]['length']
                    relSpeed = (speedSum / numVehs) / speedLimit if numVehs > 0 else 1.0
                    # road is full and slow
                    if numVehs * VEH_LENGTH > length * JAM_THRESH and relSpeed < 0.1:
                        self.jammed_lanes[lane] += JAM_BONUS


        # get actions
        for agent in self.agent_list:
            if self.agentFiles.get(agent) is None:
                if not os.path.isdir('custom_output'):
                    os.makedirs('custom_output')
                self.agentFiles[agent] = open('custom_output/%s.txt' % agent, 'w')
                self.agentFiles[agent].write('#lanes: %s\n' % self.intersections[agent]['lanes'])
                self.agentFiles[agent].write('#step oldPhase duration newPhase queueLengths jammedBonus\n')

            step_diff = now_step - self.last_change_step[agent]

            DEBUGID = None # 42381408549

            oldPhase = self.now_phase[agent]
            newPhase = oldPhase
            queue_lengths = list([(self.get_queue_lengths(now_step, agent, p, laneVehs), p) for p in range(1,9)])
            assert(queue_lengths[oldPhase - 1][1] == oldPhase)
            dual, total = queue_lengths[oldPhase - 1][0]
            queue_lengths.sort(reverse=True)
            bestDual, bestTotal = queue_lengths[0][0]
            if dual > 0 or (bestDual == 0 and total * HEADWAY > 10):
                # dualFlow > 0 already means it's above PREFER_DUAL_THRESHOLD
                # keep current phase
                if agent == DEBUGID:
                    print(now_step, agent, "keep oldPhase", oldPhase)
            else:
                lengths, newPhase = queue_lengths[0]

            if step_diff > MAX_GREEN_SEC:
                nextBest = 0
                while newPhase == oldPhase:
                    length, newPhase = queue_lengths[nextBest]
                    nextBest += 1
                if agent == DEBUGID:
                    print(now_step, agent, "oldPhase", oldPhase, "maxDuration, newPhase", newPhase)

            self.now_phase[agent] = newPhase
            if agent == DEBUGID:
                print(now_step, agent, queue_lengths, newPhase)
            if newPhase != oldPhase:
                bonus = list([self.jammed_lanes[lane] for lane in self.intersections[agent]['lanes'][:12]])
                self.agentFiles[agent].write('%s %s %s %s %s %s\n' % (now_step, oldPhase, step_diff, newPhase, queue_lengths, bonus))
                self.agentFiles[agent].flush()
                self.last_change_step[agent] = now_step
                # reset jam bonus
                for index in PHASE_LANES[newPhase]:
                    lane = self.intersections[agent]['lanes'][index - 1]
                    self.jammed_lanes[lane] = 0

                # result action
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

