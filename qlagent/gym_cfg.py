class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_speed','lane_vehicle_num']
        }

ROUTE_LENGTH_WEIGHT = 710.0 # to be optimized 670 770
MIN_CHECK_LENGTH = 41.0 # look upstream to find more queued vehicles if a lane is shorter than this optimized 35 55
JAM_THRESH = 0.91  # at which relative occupancy a lane is considered jammed, to be optimized 0.9 0.95#
HEADWAY = 1.8 # to be optimized 1.2 2.2
SLOW_THRESH = 0.1 # at which relative speed a vehicle is considered slow, to be optimized 0.05 0.15#
SPEED_THRESH = 0.05 # at which relative speed a lane is considered jammed, to be optimized 0.01 0.11#
JAM_BONUS = 6.0  # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green optimized 1 11#
MAX_GREEN_SEC = 180.0 # to be optimized 140 220
PREFER_DUAL_THRESHOLD = 7.0 # How many vehicles could pass the intersection in 5s all red (if we have more vehicles in a dual queue switching, beats single queue discharge) optimized 1 11
STOP_LINE_HEADWAY = 10.0  # seconds to the stopline to be included in the queue optimized 8 12#
BUFFER_THRESH = 2.0  # number of vehicles in lane insertion buffer to consider lane jammed optimized 1 11#
SWITCH_THRESH = 0.5 # difference in queue lengths which triggers switch optimized -0.5 4.5
