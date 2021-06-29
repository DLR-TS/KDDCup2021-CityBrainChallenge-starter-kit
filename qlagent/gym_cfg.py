class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_vehicle_num','classic'],
            'observation_dimension':40,
            'custom_observation' : True
        }

DUAL_SWITCH_THRESH = 0.1 # difference in queue lengths which triggers switch optimized -1 19#
SWITCH_THRESH = 0.15 # difference in queue lengths which triggers switch optimized -0.1 0.9#
ROUTE_LENGTH_WEIGHT = 689.0 # to be optimized 500 900#
MIN_CHECK_LENGTH = 37.0 # look upstream to find more queued vehicles if a lane is shorter than this optimized 25 65
JAM_THRESH = 1.8 # at which relative occupancy a lane is considered jammed, to be optimized 0 1#
HEADWAY = 1.8 # to be optimized 1.2 2.2
SLOW_THRESH = 0 # at which relative speed a vehicle is considered slow, to be optimized 0.05 0.15#
JAM_BONUS = 6 # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green optimized 1 11#
SPEED_THRESH = 0 # at which relative speed a lane is considered jammed, to be optimized 0.01 0.11#
MAX_GREEN_SEC = 164.0 # to be optimized 140 220#
PREFER_DUAL_THRESHOLD = 4.0 # How many vehicles could pass the intersection in 5s all red (if we have more vehicles in a dual queue switching, beats single queue discharge) optimized 1 11#
STOP_LINE_HEADWAY = 10.8 # seconds to the stopline to be included in the queue optimized 8 12#
BUFFER_THRESH = 1.0 # number of vehicles in lane insertion buffer to consider lane jammed optimized 1 11#
FUTURE_JAM_LOOKAHEAD = 7.0 # number of edges optimized 0 10#
SATURATED_THRESHOLD = 44 # optimized 30 50#
SATURATION_INC = 5 # optimized 5 15#
MIN_ROUTE_PROB = 0.9 # optimized 0 0.5#
MIN_ROUTE_COUNT = 7.0 # optimized 0 20#
DELAY_WEIGHT = 35.0 # optimized 0 50#
LEFT_TURN_BONUS = 30 # optimized 0 50#
BUFFER_JAM_THRESH = 1.8
BUFFER_SPEED_THRESH = 0
