class gym_cfg():
    def __init__(self):
        self.cfg = {
            'observation_features':['lane_speed','lane_vehicle_num']
        }

HEADWAY = 2.0  # to be optimized
SLOW_THRESH = 0.5  # at which relative speed a vehicle is considered slow, to be optimized
JAM_THRESH  = 2./3.  # at which relative occupancy a lane is considered jammed, to be optimized
MIN_CHECK_LENGTH = 100  # look upstream to find more queued vehicles if a lane is shorter than this
JAM_BONUS = 5  # bonus vehicles to add to a jammed lane per act call (every 10s) until it gets green
MAX_GREEN_SEC = 180  # to be optimized 120 240
PREFER_DUAL_THRESHOLD = 7  # How many vehicles could pass the intersection in 5s allread (if we have more vehicles in a dual queue switching, beats single queue discharge)
