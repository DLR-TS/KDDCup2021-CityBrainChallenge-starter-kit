class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_speed','lane_vehicle_num']
        }

MIN_CHECK_LENGTH = 80  # look upstream to find more queued vehicles if a lane is shorter than this optimized 60 90
JAM_THRESH  = 0.95  # at which relative occupancy a lane is considered jammed, to be optimized 0.9 0.95
HEADWAY = 2.0  # to be optimized 1 2
SLOW_THRESH = 0.5  # at which relative speed a vehicle is considered slow, to be optimized 0.1 0.8
SPEED_THRESH = 0.1  # at which relative speed a lane is considered jammed, to be optimized 0.05 0.55
JAM_BONUS = 5  # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green optimized 1 11
MAX_GREEN_SEC = 180  # to be optimized 140 190
PREFER_DUAL_THRESHOLD = 7  # How many vehicles could pass the intersection in 5s allread (if we have more vehicles in a dual queue switching, beats single queue discharge) optimized 1 11
STOP_LINE_HEADWAY = 10  # seconds to the stopline to be included in the queue optimized 8 12
