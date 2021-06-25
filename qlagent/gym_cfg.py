class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_vehicle_num','classic'],
            'observation_dimension':40,
            'custom_observation' : True
        }

SWITCH_THRESH = 0.129028946101 # difference in queue lengths which triggers switch optimized -0.1 0.9
ROUTE_LENGTH_WEIGHT = 689.0 # to be optimized 500 900#
MIN_CHECK_LENGTH = 26.1063446586 # look upstream to find more queued vehicles if a lane is shorter than this optimized 10 40
JAM_THRESH = 2.05960305211 # at which relative occupancy a lane is considered jammed, to be optimized 0.9 0.95
HEADWAY = 1.7435735323 # to be optimized 1.2 2.2
SLOW_THRESH = -0.872116041309 # at which relative speed a vehicle is considered slow, to be optimized 0.05 0.15
SPEED_THRESH = -0.12400580418 # at which relative speed a lane is considered jammed, to be optimized 0.01 0.11
JAM_BONUS = 8.69098703656 # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green optimized 1 11
MAX_GREEN_SEC = 163.754776109 # to be optimized 140 220
PREFER_DUAL_THRESHOLD = 3.7633706592 # How many vehicles could pass the intersection in 5s all red (if we have more vehicles in a dual queue switching, beats single queue discharge) optimized 1 11
STOP_LINE_HEADWAY = 10.8642197888 # seconds to the stopline to be included in the queue optimized 8 12
BUFFER_THRESH = 1.08255842145 # number of vehicles in lane insertion buffer to consider lane jammed optimized 1 11
FUTURE_JAM_LOOKAHEAD = 6.70099390142 # number of edges optimized 0 10
SATURATED_THRESHOLD = 44 # optimized 30 50#
SATURATION_INC = 5 # optimized 5 15#
MIN_ROUTE_PROB = 0.729343794407 # optimized 0 0.5
MIN_ROUTE_COUNT = 5.83099827334 # optimized 0 20
DELAY_WEIGHT = 34.8994938622 # optimized 0 50
