import os
from collections import defaultdict

from gym_cfg import HEADWAY, SLOW_THRESH, JAM_THRESH, MIN_CHECK_LENGTH, JAM_BONUS, MAX_GREEN_SEC, PREFER_DUAL_THRESHOLD
from gym_cfg import SPEED_THRESH, STOP_LINE_HEADWAY, BUFFER_THRESH, ROUTE_LENGTH_WEIGHT, SWITCH_THRESH



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

TURN_LANE_CACHE = {}

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


    def get_queue_lengths(self, now_step, agent, phase, laneVehs, route_length_weight):
        """return total queue length and maximum lane queue length"""

        result = 0
        assert(len(PHASE_LANES[phase]) == 2)
        queueLengths = [-1, -1]
        # count vehicles that are "slow" or that can reach the intersection
        # within the next 10s
        hasLane = False
        hasDst = False
        for phaseIndex in PHASE_LANES[phase]:
            if self.intersections[agent]['lanes'][phaseIndex - 1] != -1:
                hasLane = True
            #if self.intersections[agent]['lanes'][phaseIndex - 1] == -1:
                #return -1, -1
            if self.intersections[agent]['lanes'][DEST_LANES[phaseIndex][0] - 1] != -1:
                hasDst = True
        if not hasLane or not hasDst:
            return -1, -1

        for resultIndex, index in enumerate(PHASE_LANES[phase]):
            laneQ = 0
            vehs = []
            lane = self.intersections[agent]['lanes'][index - 1]
            if lane == -1:
                continue
            road = int(lane / 100)
            speedLimit = self.roads[road]['speed_limit']
            length = self.roads[road]['length']

            dstLane0 = self.intersections[agent]['lanes'][DEST_LANES[index][0] - 1]
            if dstLane0 == -1:
                continue
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
                if (dstVehs * VEH_LENGTH >= dstLength * JAM_THRESH and dstRelSpeed < SPEED_THRESH) or bufferVehs > BUFFER_THRESH:
                    # lane is full and slow
                    dstLanesJammed[dstLane] = True
                    #print("%s agent %s ignoring target lane %s dstVehs=%s, dstSpeed=%s, dstRelSpeed=%s" % (
                    #    now_step, agent, dstLane, dstVehs, dstSpeed, dstRelSpeed))


            for veh, vehData in laneVehs[lane]:
                lastEdge = vehData['route'][-1]
                if road != lastEdge:
                    speed = vehData['speed'][0]
                    stoplineDist = length - vehData['distance'][0]
                    if ((speed < SLOW_THRESH * speedLimit) or (stoplineDist / speedLimit < STOP_LINE_HEADWAY)
                            and not self.targetLaneJammed(veh, vehData['route'], dstLanesJammed)):
                        # delayIndex is impacted more strongly by vehicles with short routes
                        # median t_ff is ~720
                        laneQ += route_length_weight / vehData['t_ff'][0]
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
                            if (speed < SLOW_THRESH * speedLimit) or (stoplineDist / speedLimit < STOP_LINE_HEADWAY):
                                # laneQ += route_length_weight / vehData['t_ff'][0]
                                laneQ += 1
                                vehs.append(veh)
                                #print("%s adding pred phase=%s index=%s lane=%s len=%s predRoad=%s predVeh=%s" % (
                                #    agent, phase, index, lane, length, predRoad, veh))

            # apply jam bonus (there might be more vehicles over the horizon)

            #print(phase, index, lane, vehs)
            queueLengths[resultIndex] = laneQ + self.jammed_lanes[lane]

        # maximize flow:
        # if two lanes can be discharged (above a minimum queue length) this is always better than discharging only a single lane
        dualFlow = min(queueLengths)
        if dualFlow < PREFER_DUAL_THRESHOLD:
            # sort by total flow instead
            dualFlow = 0
        totalFlow = sum([max(q, 0) for q in queueLengths])
        return dualFlow, totalFlow

    def targetLaneJammed(self, veh, route, dstLanesJammed):
        if len(dstLanesJammed) == 0:
            return False
        elif len(dstLanesJammed) == 3:
            return True
        elif len(route) == 1:
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
        roadUsage = defaultdict(int)
        ttFF = []
        for veh, vehData in info.items():
            laneVehs[vehData['drivable'][0]].append((veh, vehData))
            if vehData['road'][0] != vehData['route'][-1]:
                ttFF.append(vehData['t_ff'][0])
                for r in vehData['route'][vehData['route'].index(vehData['road'][0]):]:
                    roadUsage[r] += 1
        #ttFFMean = sorted(ttFF)[len(ttFF) // 2] if ttFF else ROUTE_LENGTH_WEIGHT
        #ttFFMean = sum(ttFF) / len(ttFF) if ttFF else ROUTE_LENGTH_WEIGHT
        #print(ttFFMean)
        ttFFMean = ROUTE_LENGTH_WEIGHT
        #for tls_road, dist in sorted(self.tls_dist.items(), key=lambda i: i[1][2])[:100]:
        #    if roadUsage[tls_road] > 100:
        #        print(tls_road, dist, roadUsage[tls_road])

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
                    if numVehs * VEH_LENGTH > length * JAM_THRESH and relSpeed < SPEED_THRESH:
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
            queue_lengths = list([(self.get_queue_lengths(now_step, agent, p, laneVehs, ttFFMean), p) for p in range(1,9)])
            assert(queue_lengths[oldPhase - 1][1] == oldPhase)
            dual, total = queue_lengths[oldPhase - 1][0]
            queue_lengths.sort(reverse=True)
            (bestDual, bestTotal), newPhase = queue_lengths[0]
            if dual > 0 or (bestDual == 0 and (total * HEADWAY > 10 or bestTotal - total <= SWITCH_THRESH)):
                # dualFlow > 0 already means it's above PREFER_DUAL_THRESHOLD
                newPhase = oldPhase
                if agent == DEBUGID:
                    print(now_step, agent, "keep oldPhase", oldPhase)

            if step_diff > MAX_GREEN_SEC:
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

