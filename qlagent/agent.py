import os
from collections import defaultdict

from gym_cfg import HEADWAY, SLOW_THRESH, JAM_THRESH, MIN_CHECK_LENGTH, JAM_BONUS, MAX_GREEN_SEC, PREFER_DUAL_THRESHOLD
from gym_cfg import SPEED_THRESH, STOP_LINE_HEADWAY, BUFFER_THRESH, ROUTE_LENGTH_WEIGHT, SWITCH_THRESH
from gym_cfg import FUTURE_JAM_LOOKAHEAD, SATURATED_THRESHOLD, SATURATION_INC


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
SLICE = 1200

# (inEdge, outEdge) -> lane on inEdge
TURN_LANE_CACHE = {}

# vehID -> [lane0, lane1, ...]
ROUTE_LANES_CACHE= {}

class TestAgent():
    def __init__(self):
        self.now_phase = {}
        self.last_change_step = {}
        self.agent_list = []
        self.phase_passablelane = {}
        self.intersections = {}
        self.roads = {}
        self.agents = {}
        self.agentFiles = {}
        # lane -> bonus
        self.jammed_lanes = defaultdict(lambda : 0)
        # road -> (from, to, dist[in s])
        self.tls_dist = {}
        # agent -> total queue size each action step
        self.total_queues = defaultdict(list)

    ################################
    # don't modify this function.
    # agent_list is a list of agent_id
    def load_agent_list(self,agent_list):
        self.agent_list = [int(a) for a in agent_list]
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
        for road, road_data in roads.items():
            if intersections[road_data['start_inter']]['have_signal'] and intersections[road_data['end_inter']]['have_signal']:
                self.tls_dist[road] = (road_data['start_inter'], road_data['end_inter'], road_data['length'] / road_data['speed_limit'])
        self.agents = agents
    ################################

    def getTurnLane(self, inRoad, outRoad):
        inOut = (inRoad, outRoad)
        if not inOut in TURN_LANE_CACHE:
            junction = self.roads[inRoad]['end_inter']
            nextLanes = self.intersections[junction]['lanes']
            if len(nextLanes) == 0:
                # only signalized nodes define 'lanes'
                TURN_LANE_CACHE[inOut] = None
            else:
                found = False
                for index in range(12):
                    inRoad2 = int(nextLanes[index] / 100)
                    # +1 / -1 to convert between zero-based and 1-based list indices
                    outRoad2 = int(nextLanes[DEST_LANES[index + 1][0] - 1] / 100)
                    if inRoad == inRoad2 and outRoad == outRoad2:
                        found = True
                        TURN_LANE_CACHE[inOut] = nextLanes[index]
                        break
                if not found:
                    print("Found no lane that connects road %s with %s at junction %s (broken route?)" % (inRoad, outRoad, junction))
                    TURN_LANE_CACHE[inOut] = None
        return TURN_LANE_CACHE[inOut]

    def get_queue_lengths(self, now_step, agent, laneVehs, route_length_weight):
        """return list of phase queue lengths for all phases"""
        laneQueues = {}
        for index in range(1, 13):
            laneQueues[index] = self.get_lane_queue_length(now_step, agent, index, laneVehs, route_length_weight)

        return list([(self.get_phase_queue_lengths(now_step, agent, p, laneQueues), p) for p in range(1,9)])


    def get_phase_queue_lengths(self, now_step, agent, phase, laneQueues):
        """return total queue length and maximum lane queue length"""

        assert(len(PHASE_LANES[phase]) == 2)
        queueLengths = []
        hasDst = False
        for index in PHASE_LANES[phase]:
            lane = self.intersections[agent]['lanes'][index - 1]
            if lane == -1:
                return -1, -1

            if self.intersections[agent]['lanes'][DEST_LANES[index][0] - 1] != -1:
                hasDst = True
            #print(agent, index, lane, laneQueues)
            queueLengths.append(laneQueues[index])

        if not hasDst:
            return -1, -1

        # maximize flow:
        # if two lanes can be discharged (above a minimum queue length) this is always better than discharging only a single lane
        dualFlow = min(queueLengths)
        if dualFlow < PREFER_DUAL_THRESHOLD[now_step // SLICE]:
            # sort by total flow instead
            dualFlow = 0
        totalFlow = sum([max(q, 0) for q in queueLengths])
        return dualFlow, totalFlow


    def get_lane_queue_length(self, now_step, agent, index, laneVehs, route_length_weight):
        """return length of queue for the given lane id or -1 if the lane is not
        valid (because it doesn't exist or has not destination)"""

        # count vehicles that are "slow" or that can reach the intersection
        # within the next 10s
        lane = self.intersections[agent]['lanes'][index - 1]
        if lane == -1:
            # lane does not exist
            return -1;
        if self.intersections[agent]['lanes'][DEST_LANES[index][0] - 1] == -1:
            # destination edge does not exist
            return -1;

        laneQ = 0
        vehs = []
        road = int(lane / 100)
        speedLimit = self.roads[road]['speed_limit']
        length = self.roads[road]['length']

        dstLane0 = self.intersections[agent]['lanes'][DEST_LANES[index][0] - 1]
        dstRoad = int(dstLane0 / 100)
        dstLength = self.roads[dstRoad]['length']
        dstSpeedLimit = self.roads[dstRoad]['speed_limit']
        dstLanesJammed = {}
        for dstIndex in DEST_LANES[index]:
            dstSpeed = 0
            dstLane = self.intersections[agent]['lanes'][dstIndex - 1]
            dstVehs = len(laneVehs[dstLane])
            bufferVehs = 0 # count vehicles in the "insertion buffer". They also block upstream flow
            for veh, vehData in laneVehs[dstLane]:
                speed = vehData['speed'][0]
                pos = vehData['distance'][0]
                dstSpeed += speed
                if pos < 5 and speed == 0:
                    bufferVehs += 1
            dstRelSpeed = (dstSpeed / dstVehs) / dstSpeedLimit if dstVehs > 0 else 1.0
            if (dstVehs * VEH_LENGTH >= dstLength * JAM_THRESH[now_step // SLICE] and dstRelSpeed < SPEED_THRESH[now_step // SLICE]) or bufferVehs > BUFFER_THRESH[now_step // SLICE]:
                # lane is full and slow
                dstLanesJammed[dstLane] = True
                #print("%s agent %s ignoring target lane %s dstVehs=%s, dstSpeed=%s, dstRelSpeed=%s" % (
                #    now_step, agent, dstLane, dstVehs, dstSpeed, dstRelSpeed))


        for veh, vehData in laneVehs[lane]:
            route = vehData.get('route')
            if route is None or road != route[-1]:
                speed = vehData['speed'][0]
                stoplineDist = length - vehData['distance'][0]
                if (speed < SLOW_THRESH[now_step // SLICE] * speedLimit) or (stoplineDist / speedLimit < STOP_LINE_HEADWAY[now_step // SLICE]):
                    if not self.targetLaneJammed(veh, route, dstLanesJammed):
                        # delayIndex is impacted more strongly by vehicles with short routes
                        # median t_ff is ~720
#                        fjPenalty = self.getFutureJamPenalty(route, now_step)
#                        laneQ += (route_length_weight + 10) / (now_step - vehData['start_time'][0] + 10) / fjPenalty
                        laneQ += 1
                        vehs.append(veh)

                    # count all vehicles without penalties
                    self.total_queues[agent][-1] += 1

        if length < MIN_CHECK_LENGTH[now_step // SLICE]:
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
                    if 'route' not in vehData or predRoad != vehData['route'][-1]:
                        speed = vehData['speed'][0]
                        stoplineDist = length + predLength - vehData['distance'][0]
                        if (speed < SLOW_THRESH[now_step // SLICE] * speedLimit) or (stoplineDist / speedLimit < STOP_LINE_HEADWAY[now_step // SLICE]):
                            # laneQ += route_length_weight / vehData['t_ff'][0]
                            laneQ += 1
                            vehs.append(veh)
                            #print("%s adding pred phase=%s index=%s lane=%s len=%s predRoad=%s predVeh=%s" % (
                            #    agent, phase, index, lane, length, predRoad, veh))

        # apply jam bonus (there might be more vehicles over the horizon)

        #print(phase, index, lane, vehs)
        return laneQ + self.jammed_lanes[lane]


    def targetLaneJammed(self, veh, route, dstLanesJammed):
        if len(dstLanesJammed) == 0:
            return False
        elif len(dstLanesJammed) == 3:
            return True
        elif route is None or len(route) == 1:
            # route does not go past the junction
            return False
        elif len(route) == 2:
            # route ends after beyond the current junction
            # all target lanes are permitted
            allJammed = len(dstLanesJammed) == 3
            return allJammed
        else:
            lane = self.getTurnLane(route[1], route[2])
            if lane is None:
                # only signalized nodes define 'lanes'
                # we already know that at least one lane is jammed so let's assume the worst
                return True
            elif lane in dstLanesJammed:
                #print("targetLaneJammed for veh %s with route %s, targetLane=%s inRoad=%s outRoad=%s" % (
                #    veh, route, lane, route[1], route[2]))
                return True
            else:
                return False

    def getFutureJamPenalty(self, route, now_step):
        result = 1.0
        if route is not None:
            saturated = SATURATED_THRESHOLD[now_step // SLICE]
            for i in range(1, min(len(route), int(FUTURE_JAM_LOOKAHEAD[now_step // SLICE] + 0.5))):
                junction = self.roads[route[i]]['end_inter']
                totals = self.total_queues.get(junction, [])
                if len(totals) > 1:
                    prevStepQueue = totals[-2]
                    # discount future jams
                    result *= max(1, prevStepQueue / saturated)
                saturated += SATURATION_INC[now_step // SLICE]
        return result

    def act(self, obs):
        # observations is returned 'observation' of env.step()
        # info is returned 'info' of env.step()
        observations = obs['observations']
        info = obs['info']

        # select the now_step
        now_step = info['step'] * 10
        actions = {}

        laneVehs = defaultdict(list) # lane -> (veh, vehData)
        for lane, vehicles in list(observations.values())[0].items():
            speedSum = 0
            numVehs = len(vehicles)
            for veh in vehicles:
                laneVehs[lane].append((veh, info[veh]))
                speedSum += info[veh]['speed'][0]
            road = int(lane / 100)
            speedLimit = self.roads[road]['speed_limit']
            length = self.roads[road]['length']
            relSpeed = (speedSum / numVehs) / speedLimit if numVehs > 0 else 1.0
            # road is full and slow
            if numVehs * VEH_LENGTH > length * JAM_THRESH[now_step // SLICE] and relSpeed < SPEED_THRESH[now_step // SLICE]:
                self.jammed_lanes[lane] += JAM_BONUS[now_step // SLICE]
        ttFFMean = ROUTE_LENGTH_WEIGHT[now_step // SLICE]

        # get actions
        for agent in self.agent_list:
            if agent not in self.agentFiles:
                try:
                    if not os.path.isdir('custom_output'):
                        os.makedirs('custom_output')
                    self.agentFiles[agent] = open('custom_output/%s.txt' % agent, 'w')
                    self.agentFiles[agent].write('#lanes: %s\n' % self.intersections[agent]['lanes'])
                    self.agentFiles[agent].write('#step oldPhase duration newPhase totalQueued queueLengths jammedBonus\n')
                except:
                    pass

            self.total_queues[agent].append(0)
            step_diff = now_step - self.last_change_step[agent]

            DEBUGID = None # 42381408549

            oldPhase = self.now_phase[agent]
            newPhase = oldPhase

            queue_lengths = self.get_queue_lengths(now_step, agent, laneVehs, ttFFMean)
            assert(queue_lengths[oldPhase - 1][1] == oldPhase)
            dual, total = queue_lengths[oldPhase - 1][0]
            queue_lengths.sort(reverse=True)
            (bestDual, bestTotal), newPhase = queue_lengths[0]
            if dual > 0 or (bestDual == 0 and (total * HEADWAY[now_step // SLICE] > 10 or bestTotal - total <= SWITCH_THRESH[now_step // SLICE])):
                # dualFlow > 0 already means it's above PREFER_DUAL_THRESHOLD
                newPhase = oldPhase
                if agent == DEBUGID:
                    print(now_step, agent, "keep oldPhase", oldPhase)

            if step_diff > MAX_GREEN_SEC[now_step // SLICE]:
                nextBest = 0
                while newPhase == oldPhase:
                    newPhase = queue_lengths[nextBest][1]
                    nextBest += 1
                if agent == DEBUGID:
                    print(now_step, agent, "oldPhase", oldPhase, "maxDuration, newPhase", newPhase)

            self.now_phase[agent] = newPhase
            if agent == DEBUGID:
                print(now_step, agent, queue_lengths, newPhase)
            if newPhase != oldPhase:
                bonus = list([self.jammed_lanes[lane] for lane in self.intersections[agent]['lanes'][:12]])
                if agent in self.agentFiles:
                    self.agentFiles[agent].write('%s %s %s %s %.2f %s %s\n' % (now_step, oldPhase, step_diff, newPhase, self.total_queues[agent][-1], queue_lengths, bonus))
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
        print(now_step, SLICE, now_step // SLICE, SWITCH_THRESH[now_step // SLICE])
        return actions

scenario_dirs = [
    "test"
]

agent_specs = dict.fromkeys(scenario_dirs, None)
for i, k in enumerate(scenario_dirs):
    # initialize an AgentSpec instance with configuration
    agent_specs[k] = TestAgent()

