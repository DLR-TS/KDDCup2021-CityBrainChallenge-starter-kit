import os
from collections import defaultdict

from gym_cfg import HEADWAY, SLOW_THRESH, JAM_THRESH, MIN_CHECK_LENGTH, JAM_BONUS, MAX_GREEN_SEC, PREFER_DUAL_THRESHOLD
from gym_cfg import SPEED_THRESH, STOP_LINE_HEADWAY, BUFFER_THRESH, ROUTE_LENGTH_WEIGHT, SWITCH_THRESH
from gym_cfg import FUTURE_JAM_LOOKAHEAD, SATURATED_THRESHOLD, SATURATION_INC, MIN_ROUTE_COUNT, MIN_ROUTE_PROB
import dijkstra


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
        self.vehicle_routes = {}

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
        self.roadgraph = {}
        for road, road_data in roads.items():
            if intersections[road_data['start_inter']]['have_signal'] and intersections[road_data['end_inter']]['have_signal']:
                self.tls_dist[road] = (road_data['start_inter'], road_data['end_inter'], road_data['length'] / road_data['speed_limit'])
            self.roadgraph[road] = dijkstra.Edge(road, road_data['length'])
        for road, road_data in roads.items():
            for nextRoad in self.intersections[road_data['end_inter']]['start_roads']:
                self.roadgraph[road].addOut(self.roadgraph[nextRoad])
        self.agents = agents
    ################################

    def getTurnLane(self, inRoad, outRoad, warn=True):
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
                    if warn:
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
        if dualFlow < PREFER_DUAL_THRESHOLD:
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
            if (dstVehs * VEH_LENGTH >= dstLength * JAM_THRESH and dstRelSpeed < SPEED_THRESH) or bufferVehs > BUFFER_THRESH:
                # lane is full and slow
                dstLanesJammed[dstLane] = True
                #print("%s agent %s ignoring target lane %s dstVehs=%s, dstSpeed=%s, dstRelSpeed=%s" % (
                #    now_step, agent, dstLane, dstVehs, dstSpeed, dstRelSpeed))


        for veh, vehData in laneVehs[lane]:
            route = self.routedist.get(road)
#            route = self.lanedist.get(lane)
#            route = None
            speed = vehData['speed'][0]
            meanSpeed = (speed + speedLimit) / 2
            stoplineDist = length - vehData['distance'][0]
            if (speed < SLOW_THRESH * speedLimit) or (stoplineDist / meanSpeed < STOP_LINE_HEADWAY):
                tlJamProb = self.targetLaneJammed(veh, route, dstLanesJammed)
                # delayIndex is impacted more strongly by vehicles with short routes
                # median t_ff is ~720
                baseWeight = (now_step - vehData['start_time'][0]) / vehData['t_ff'][0]
#                baseWeight = (route_length_weight / vehData.get('t_ff', [route_length_weight])[0])
#                baseWeight = 1.
#                fjPenalty = self.getFutureJamPenalty(route, now_step)
                fjPenalty = 1.
                laneQ +=  (1. - tlJamProb) * baseWeight / fjPenalty
                vehs.append(veh)

                # count all vehicles without penalties
                self.total_queues[agent][-1] += 1

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
                        predLanes += [predRoad * 100 + 1]

            for predLane in predLanes:
                predRoad = int(predLane / 100)
                predLength = self.roads[predRoad]['length']
                for veh, vehData in laneVehs[predLane]:
                    if 'route' not in vehData or predRoad != vehData['route'][-1]:
                        speed = vehData['speed'][0]
                        meanSpeed = (speed + speedLimit) / 2
                        stoplineDist = length + predLength - vehData['distance'][0]
                        if (speed < SLOW_THRESH * speedLimit) or (stoplineDist / meanSpeed < STOP_LINE_HEADWAY):
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
            return 0.
        if len(dstLanesJammed) == 3:
            return 1.
        if route is None:
            return 1.
        total = 0.
        for subroute, prob in route.items():
            if len(subroute) == 2 and subroute[1] == -1:
                # route does not go past the junction
                continue
            elif len(subroute) == 3 and subroute[2] == -1:
                # route ends after beyond the current junction
                # all target lanes are permitted
                if len(dstLanesJammed) == 3:
                    total += prob
            elif len(subroute) > 2:
                lane = self.getTurnLane(subroute[1], subroute[2])
                if lane is None:
                    # only signalized nodes define 'lanes'
                    # we already know that at least one lane is jammed so let's assume the worst
                    total += prob
                elif lane in dstLanesJammed:
                    #print("targetLaneJammed for veh %s with route %s, targetLane=%s inRoad=%s outRoad=%s" % (
                    #    veh, route, lane, route[1], route[2]))
                    total += prob
            else:
                total += prob
        return total

    def getFutureJamPenalty(self, route, now_step):
        if route is None:
            return 1.
        total = 0
        for subroute, prob in route.items():
            result = 1.0
            saturated = SATURATED_THRESHOLD
            for i in range(1, min(len(subroute), int(FUTURE_JAM_LOOKAHEAD + 0.5))):
                if subroute[i] == -1:
                    break
                junction = self.roads[subroute[i]]['end_inter']
                totals = self.total_queues.get(junction, [])
                if len(totals) > 1:
                    prevStepQueue = totals[-2]
                    # discount future jams
                    result *= max(1, prevStepQueue / saturated)
                saturated += SATURATION_INC
            total += result * prob
        return total

    def calculateRouteDist(self):
        laneMap = defaultdict(lambda: defaultdict(int))
        edgeMap = defaultdict(lambda: defaultdict(int))
        for route in self.vehicle_routes.values():
            for idx, (lane, change) in enumerate(route):
                subroute = tuple([int(r / 100) for r, _ in route[idx:idx+7]])
                if change:
                    laneMap[lane][subroute] += 1
                edgeMap[int(lane / 100)][subroute] += 1
        self.routedist = defaultdict(dict)
        for edge, freq in edgeMap.items():
            total = 0
            for subroute, count in freq.items():
                total += count
            for subroute, count in freq.items():
                if total > MIN_ROUTE_COUNT and count / total > MIN_ROUTE_PROB:
                    self.routedist[edge][subroute] = count / total
        self.lanedist = defaultdict(dict)
        for lane, freq in laneMap.items():
            total = 0
            for subroute, count in freq.items():
                total += count
            for subroute, count in freq.items():
                if total > MIN_ROUTE_COUNT and count / total > MIN_ROUTE_PROB:
                    self.lanedist[lane][subroute] = count / total
#        print(self.routedist)
#        print(self.lanedist)

    def act(self, obs):
        # observations is returned 'observation' of env.step()
        # info is returned 'info' of env.step()
        observations = obs['observations']
        info = obs['info']

        # select the now_step
        now_step = info['step'] * 10
        actions = {}

        unSeen = set(self.vehicle_routes)
        laneVehs = defaultdict(list) # lane -> (veh, vehData)
        for lane, vehicles in list(observations.values())[0].items():
            speedSum = 0
            road = int(lane / 100)
            numVehs = len(vehicles)
            length = self.roads[road]['length']
            speedLimit = self.roads[road]['speed_limit']
            for veh in vehicles:
                laneVehs[lane].append((veh, info[veh]))
                speedSum += info[veh]['speed'][0]
                if veh in self.vehicle_routes:
                    if lane != self.vehicle_routes[veh][-1][0]:
                        prevLane = self.vehicle_routes[veh][-1][0]
                        prevRoad = int(prevLane / 100)
                        if road == prevRoad:
                            self.vehicle_routes[veh][-1] = (lane, True)
                        else:
                            turnLane = self.getTurnLane(prevRoad, road, False)
                            if turnLane is None:
                                nextRoads = self.intersections[self.roads[prevRoad]['end_inter']]['start_roads']
                                if road in nextRoads:
                                    # non signalized intersection
                                    self.vehicle_routes[veh][-1] = (prevLane, True)
                                else:
                                    for intermed in nextRoads:
                                        turnLane2 = self.getTurnLane(intermed, road, False)
                                        if turnLane2 is None:
                                            nextRoads2 = self.intersections[self.roads[intermed]['end_inter']]['start_roads']
                                            if road in nextRoads2:
                                                turnLane = self.getTurnLane(prevRoad, intermed)
                                                if turnLane is None:
                                                    # another non signalized intersection
                                                    self.vehicle_routes[veh][-1] = (prevLane, True)
                                                else:
                                                    self.vehicle_routes[veh][-1] = (turnLane, True)
                                                self.vehicle_routes[veh].append((intermed * 100 + lane % 100, True))
                                                break
                                        else:
                                            turnLane = self.getTurnLane(prevRoad, intermed)
                                            if turnLane is None:
                                                # non signalized intersection
                                                self.vehicle_routes[veh][-1] = (prevLane, True)
                                            else:
                                                self.vehicle_routes[veh][-1] = (turnLane, True)
                                            self.vehicle_routes[veh].append((turnLane2, True))
                                            break
                                    else:
                                        path = self.roadgraph[prevRoad].getShortestPath(self.roadgraph[road])
                                        for e in path[0][1:-1]:
                                            # TODO this is not lane specific
                                            self.vehicle_routes[veh].append((e.id * 100, False))
#                                        print("no intermediate edge connecting %s and %s %s" % (prevRoad, road, [e.id for e in path[0]]))
                            else:
                                self.vehicle_routes[veh][-1] = (turnLane, True)
                            self.vehicle_routes[veh].append((lane, False))
                    unSeen.discard(veh)
                else:
                    self.vehicle_routes[veh] = [(lane, False)]
                t_ff = 0
                for rl, _ in self.vehicle_routes[veh]:
                    rr = int(rl / 100)
                    t_ff += self.roads[rr]['length'] / self.roads[rr]['speed_limit']
                info[veh]['t_ff'] = [t_ff]
            relSpeed = (speedSum / numVehs) / speedLimit if numVehs > 0 else 1.0
            # road is full and slow
            if numVehs * VEH_LENGTH > length * JAM_THRESH and relSpeed < SPEED_THRESH:
                self.jammed_lanes[lane] += JAM_BONUS
        ttFFMean = ROUTE_LENGTH_WEIGHT
        for veh in unSeen:
            if self.vehicle_routes[veh][-1][0] != -100:
                self.vehicle_routes[veh].append((-100, False))
        self.calculateRouteDist()

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
        return actions

scenario_dirs = [
    "test"
]

agent_specs = dict.fromkeys(scenario_dirs, None)
for i, k in enumerate(scenario_dirs):
    # initialize an AgentSpec instance with configuration
    agent_specs[k] = TestAgent()

