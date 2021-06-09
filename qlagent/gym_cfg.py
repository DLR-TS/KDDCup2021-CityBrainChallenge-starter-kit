class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_speed','lane_vehicle_num']
        }

SWITCH_THRESH = 0.5000000000000001 # difference in queue lengths which triggers switch optimized -0.1 0.9
ROUTE_LENGTH_WEIGHT = 690.0 # to be optimized 690 715
MIN_CHECK_LENGTH = 43.0 # look upstream to find more queued vehicles if a lane is shorter than this optimized 35 55
JAM_THRESH = 0.91 # at which relative occupancy a lane is considered jammed, to be optimized 0.9 0.95
HEADWAY = 1.5 # to be optimized 1.2 2.2
SLOW_THRESH = 0.09999999999999999 # at which relative speed a vehicle is considered slow, to be optimized 0.05 0.15
SPEED_THRESH = 0.05 # at which relative speed a lane is considered jammed, to be optimized 0.01 0.11
JAM_BONUS = 5.0 # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green optimized 1 11
MAX_GREEN_SEC = 180.0 # to be optimized 140 220
PREFER_DUAL_THRESHOLD = 8.0 # How many vehicles could pass the intersection in 5s all red (if we have more vehicles in a dual queue switching, beats single queue discharge) optimized 1 11
STOP_LINE_HEADWAY = 10.4 # seconds to the stopline to be included in the queue optimized 8 12
BUFFER_THRESH = 2.0 # number of vehicles in lane insertion buffer to consider lane jammed optimized 1 11
FUTURE_JAM_LOOKAHEAD = 7.0 # number of edges optimized 0 10
SATURATED_THRESHOLD = 44.0 # optimized 30 50
SATURATION_INC = 10.0 # optimized 5 15
