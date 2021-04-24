import CBEngine
import json
import traceback
import argparse
import logging
import os
import sys
import time
from pathlib import Path
import re
import gym
import numpy as np
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

gym.logger.setLevel(gym.logger.ERROR)


def pretty_files(path):
    contents = os.listdir(path)
    return "[{}]".format(", ".join(contents))


def resolve_dirs(root_path: str, input_dir: str = None, output_dir: str = None):
    root_path = Path(root_path)

    logger.info(f"root_path={pretty_files(root_path)}")

    if input_dir is not None:
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)

        # path in cfg must be consistent with middle_output_dir
        submission_dir = input_dir
        scores_dir = output_dir

        logger.info(f"input_dir={pretty_files(input_dir)}")
        logger.info(f"output_dir={pretty_files(output_dir)}")
    else:
        raise ValueError('need input dir')
        # # XXX: The examples in starter_kit is what submissions are based
        # #      on, and are end-end functional on their own.
        # submission_dir = (root_path / "../../starter_kit/rllib_example").resolve()
        # eval_scenarios_dir = (root_path / "../../dataset_evaluation").resolve()
        # scores_dir = (root_path / "../../scores").resolve()

    if not scores_dir.exists():
        os.makedirs(scores_dir)

    logger.info(f"submission_dir={pretty_files(submission_dir)}")
    logger.info(f"scores_dir={pretty_files(scores_dir)}")
    output_path = scores_dir / "scores.txt"

    if not submission_dir.is_dir():
        logger.warning(f"submission_dir={submission_dir} does not exist")

    return submission_dir, scores_dir


def load_agent_submission(submission_dir: Path):
    logger.info(f"files under submission dir:{pretty_files(submission_dir)}")

    # find agent.py
    module_path = None
    cfg_path = None
    for dirpath, dirnames, file_names in os.walk(submission_dir):
        for file_name in [f for f in file_names if f.endswith(".py")]:
            if file_name == "agent.py":
                module_path = dirpath

            if file_name == "gym_cfg.py":
                cfg_path = dirpath

        # for file_name in [f for f in file_names if f.endswith(".txt")]:
        #     if file_name == "requirements.txt":
        #         logger.info("find requirments.txt, installing requirements")
        #         os.system(f"pip install -r {dirpath}/{file_name}")

    assert (
        module_path is not None
    ), "Cannot find file named agent.py, please check your submission zip"
    assert(
        cfg_path is not None
    ), "Cannot find file named gym_cfg.py, please check your submission zip"
    sys.path.append(str(module_path))


    # This will fail w/ an import error of the submissions directory does not exist
    import gym_cfg as gym_cfg_submission
    import agent_DQN as agent_submission

    gym_cfg_instance = gym_cfg_submission.gym_cfg()

    return  agent_submission.agent_specs,gym_cfg_instance


def read_config(cfg_file):
    configs = {}
    with open(cfg_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = line.rstrip('\n').split(' ')
            if(len(line) == 3 and line[0][0] != '#'):
                configs[line[0]] = line[-1]
    return configs


def process_roadnet(roadnet_file):
    intersections = {}
    roads = {}
    agents = {}
    lane_vehicle_state = {}
    with open(roadnet_file, 'r') as f:
        lines = f.readlines()
        cnt = 0
        pre_road = 0
        is_obverse = 0
        for line in lines:
            line = line.rstrip('\n').split(' ')
            if ('' in line):
                line.remove('')
            if (len(line) == 1):
                if (cnt == 0):
                    agent_num = int(line[0])
                    cnt += 1
                elif (cnt == 1):
                    road_num = int(line[0]) * 2
                    cnt += 1
                elif (cnt == 2):
                    signal_num = int(line[0])
                    cnt += 1
            else:
                if (cnt == 1):
                    intersections[int(line[2])] = {
                        'latitude': float(line[0]),
                        'longitude': float(line[1]),
                        'have_signal': int(line[3]),
                        'end_roads': []
                    }
                elif (cnt == 2):
                    if (len(line) != 8):
                        road_id = pre_road[is_obverse]
                        roads[road_id]['lanes'] = {}
                        for i in range(roads[road_id]['num_lanes']):
                            roads[road_id]['lanes'][road_id * 100 +
                                                    i] = list(map(int, line[i * 3:i * 3 + 3]))
                            lane_vehicle_state[road_id * 100 + i] = set()
                        is_obverse ^= 1
                    else:
                        roads[int(line[-2])] = {
                            'start_inter': int(line[0]),
                            'end_inter': int(line[1]),
                            'length': float(line[2]),
                            'speed_limit': float(line[3]),
                            'num_lanes': int(line[4])
                        }
                        roads[int(line[-1])] = {
                            'start_inter': int(line[1]),
                            'end_inter': int(line[0]),
                            'length': float(line[2]),
                            'speed_limit': float(line[3]),
                            'num_lanes': int(line[5])
                        }
                        intersections[int(line[0])]['end_roads'].append(
                            int(line[-1]))
                        intersections[int(line[1])]['end_roads'].append(
                            int(line[-2]))
                        pre_road = (int(line[-2]), int(line[-1]))
                else:
                    # 4 out-roads
                    # agents[int(line[0])] = list(map(int,line[1:]))
                    # 4 in-roads
                    agents[int(line[0])] = intersections[int(
                        line[0])]['end_roads']
    return intersections, roads, agents


def process_delay_index(lines, roads, step):
    vehicles = {}

    for i in range(len(lines)):
        line = lines[i]
        if(line[0] == 'for'):
            vehicle_id = int(line[2])
            now_dict = {
                'distance': float(lines[i + 1][2]),
                'drivable': int(float(lines[i + 2][2])),
                'road': int(float(lines[i + 3][2])),
                'route': list(map(int, list(map(float, lines[i + 4][2:])))),
                'speed': float(lines[i + 5][2]),
                'start_time': float(lines[i + 6][2]),
                't_ff': float(lines[i+7][2])
            }
            vehicles[vehicle_id] = now_dict
            tt = step - now_dict['start_time']
            tt_ff = now_dict['t_ff']
            tt_f_r = 0.0
            current_road_pos = 0
            for pos in range(len(now_dict['route'])):
                if(now_dict['road'] == now_dict['route'][pos]):
                    current_road_pos = pos
            for pos in range(len(now_dict['route'])):
                road_id = now_dict['route'][pos]
                if(pos == current_road_pos):
                    tt_f_r += (roads[road_id]['length'] -
                               now_dict['distance']) / roads[road_id]['speed_limit']
                elif(pos > current_road_pos):
                    tt_f_r += roads[road_id]['length'] / roads[road_id]['speed_limit']

            vehicles[vehicle_id]['delay_index'] = (tt + tt_f_r) / tt_ff

    vehicle_list = list(vehicles.keys())
    delay_index_list = []
    for vehicle_id, dict in vehicles.items():
        # res = max(res, dict['delay_index'])
        delay_index_list.append(dict['delay_index'])

    return delay_index_list, vehicle_list, vehicles


def train(agent_spec, simulator_cfg_file, gym_cfg):
    logger.info("\n")
    logger.info("*" * 40)

    gym_configs = gym_cfg.cfg
    simulator_configs = read_config(simulator_cfg_file)
    env = gym.make(
        'CBEngine-v0',
        simulator_cfg_file=simulator_cfg_file,
        thread_num=1,
        gym_dict=gym_configs
    )
    scenario = [
        'test'
    ]

    done = False

    roadnet_path = Path(simulator_configs['road_file_addr'])

    intersections, roads, agents = process_roadnet(roadnet_path)

    observations, infos = env.reset()
    agent_id_list = []
    for k in observations:
        agent_id_list.append(int(k.split('_')[0]))
    agent_id_list = list(set(agent_id_list))
    agent = agent_spec[scenario[0]]
    agent.load_agent_list(agent_id_list)

    # Here begins the code for training

    total_decision_num = 0
    env.set_log(0)
    env.set_warning(0)
    # agent.load_model(args.save_dir, 199)

    # The main loop
    for e in range(args.episodes):
        print("----------------------------------------------------{}/{}".format(e, args.episodes))
        last_obs = env.reset()
        episodes_rewards = {}
        for agent_id in agent_id_list:
            episodes_rewards[agent_id] = 0
        episodes_decision_num = 0

        # Begins one simulation.
        i = 0
        while i < args.steps:
            if i % args.action_interval == 0:
                if isinstance(last_obs, tuple):
                    observations = last_obs[0]
                else:
                    observations = last_obs
                actions = {}

                # Get the state.

                observations_for_agent = {}
                for key, val in observations.items():
                    observations_agent_id = int(key.split('_')[0])
                    observations_feature = key.split('_')[1]
                    if (observations_agent_id not in observations_for_agent.keys()):
                        observations_for_agent[observations_agent_id] = {}
                    val = val[1:]
                    while len(val) < agent.ob_length:
                        val.append(0)
                    observations_for_agent[observations_agent_id][observations_feature] = val

                # Get the action, note that we use act_() for training.
                actions = agent.act_(observations_for_agent)

                rewards_list = {}

                actions_ = {}
                for key in actions.keys():
                    actions_[key] = actions[key] + 1

                # We keep the same action for a certain time
                for _ in range(args.action_interval):
                    # print(i)
                    i += 1

                    # Interacts with the environment and get the reward.
                    observations, rewards, dones, infos = env.step(actions_)
                    for agent_id in agent_id_list:
                        lane_vehicle = observations["{}_lane_vehicle_num".format(agent_id)]
                        pressure = (np.sum(lane_vehicle[13: 25]) - np.sum(lane_vehicle[1: 13])) / args.action_interval
                        if agent_id in rewards_list:
                            rewards_list[agent_id] += pressure
                        else:
                            rewards_list[agent_id] = pressure


                rewards = rewards_list
                new_observations_for_agent = {}

                # Get next state.

                for key, val in observations.items():
                    observations_agent_id = int(key.split('_')[0])
                    observations_feature = key.split('_')[1]
                    if (observations_agent_id not in new_observations_for_agent.keys()):
                        new_observations_for_agent[observations_agent_id] = {}
                    val = val[1:]
                    while len(val) < agent.ob_length:
                        val.append(0)
                    new_observations_for_agent[observations_agent_id][observations_feature] = val

                # Remember (state, action, reward, next_state) into memory buffer.
                for agent_id in agent_id_list:
                    agent.remember(observations_for_agent[agent_id]['lane'], actions[agent_id], rewards[agent_id],
                                   new_observations_for_agent[agent_id]['lane'])
                    episodes_rewards[agent_id] += rewards[agent_id]
                episodes_decision_num += 1
                total_decision_num += 1

                last_obs = observations

            # Update the network
            if total_decision_num > agent.learning_start and total_decision_num % agent.update_model_freq == agent.update_model_freq - 1:
                agent.replay()
            if total_decision_num > agent.learning_start and total_decision_num % agent.update_target_model_freq == agent.update_target_model_freq - 1:
                agent.update_target_network()
            if all(dones.values()):
                break
        if e % args.save_rate == args.save_rate - 1:
            if not os.path.exists(args.save_dir):
                os.makedirs(args.save_dir)
            agent.save_model(args.save_dir, e)
        logger.info(
            "episode:{}/{}, average travel time:{}".format(e, args.episodes, env.eng.get_average_travel_time()))
        for agent_id in agent_id_list:
            logger.info(
                "agent:{}, mean_episode_reward:{}".format(agent_id,
                                                          episodes_rewards[agent_id] / episodes_decision_num))


def run_simulation(agent_spec, simulator_cfg_file, gym_cfg):
    logger.info("\n")
    logger.info("*" * 40)

    gym_configs = gym_cfg.cfg
    simulator_configs = read_config(simulator_cfg_file)
    env = gym.make(
        'CBEngine-v0',
        simulator_cfg_file=simulator_cfg_file,
        thread_num=1,
        gym_dict=gym_configs
    )
    scenario = [
        'test'
    ]

    done = False

    roadnet_path = Path(simulator_configs['road_file_addr'])

    intersections, roads, agents = process_roadnet(roadnet_path)

    observations, infos = env.reset()
    agent_id_list = []
    for k in observations:
        agent_id_list.append(int(k.split('_')[0]))
    agent_id_list = list(set(agent_id_list))
    agent = agent_spec[scenario[0]]
    agent.load_agent_list(agent_id_list)

    env.set_log(1)
    env.set_warning(1)
    agent.epsilon = 0

    step = 0

    while not done:
        actions = {}
        step += 1
        all_info = {
            'observations': observations,
            'info': infos
        }
        actions = agent.act(all_info)
        observations, rewards, dones, infos = env.step(actions)
        for agent_id in agent_id_list:
            if (dones[agent_id]):
                done = True
    time = env.eng.get_average_travel_time()

    # read log file
    log_path = Path(simulator_configs['report_log_addr'])
    result = {}
    vehicle_last_occur = {}
    for dirpath, dirnames, file_names in os.walk(log_path):
        for file_name in [f for f in file_names if f.endswith(".log") and f.startswith('info_step')]:
            with open(log_path / file_name, 'r') as log_file:
                pattern = '[0-9]+'
                step = list(map(int, re.findall(pattern, file_name)))[0]
                if (step >= int(simulator_configs['max_time_epoch'])):
                    continue
                lines = log_file.readlines()
                lines = list(map(lambda x: x.rstrip('\n').split(' '), lines))
                result[step] = {}
                # result[step]['vehicle_num'] = int(lines[0][0])

                # process delay index
                # delay_index, vehicle_list = process_delay_index(lines, roads, step)
                delay_index_list, vehicle_list, vehicles = process_delay_index(lines, roads, step)

                result[step]['vehicle_list'] = vehicle_list
                result[step]['delay_index'] = delay_index_list
                result[step]['vehicles'] = vehicles
    steps = list(result.keys())
    steps.sort()
    for step in steps:
        for vehicle in result[step]['vehicles'].keys():
            vehicle_last_occur[vehicle] = result[step]['vehicles'][vehicle]

    delay_index_temp = {}
    for vehicle in vehicle_last_occur.keys():
        res = vehicle_last_occur[vehicle]['delay_index']
        delay_index_temp[vehicle] = res

    # last calc
    vehicle_total_set = set()
    delay_index = []
    for k, v in result.items():
        # vehicle_num.append(v['vehicle_num'])
        vehicle_total_set = vehicle_total_set | set(v['vehicle_list'])
        # delay_index.append(v['delay_index'])
        delay_index += delay_index_list
    if (len(delay_index) > 0):
        d_i = np.mean(delay_index)
    else:
        d_i = -1

    last_d_i = np.mean(list(delay_index_temp.values()))
    delay_index = list(delay_index_temp.values())

    return len(vehicle_total_set), last_d_i


# def write_result(result, output_path):
#     score_line = "{}: {:.4f}\n{}: {:.4f}".format('total_served_vehicles', score[0],
#                                                  'delay_index', score[1])
#     logger.info('Writing "{}"'.format(score_line))
#     with open(output_path, "w+") as output_file:
#         output_file.write(score_line + "\n")
#

def format_exception(grep_word):
    exception_list = traceback.format_stack()
    exception_list = exception_list[:-2]
    exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
    exception_list.extend(traceback.format_exception_only(
        sys.exc_info()[0], sys.exc_info()[1]))
    filtered = []
    for m in exception_list:
        if str(grep_word) in m:
            filtered.append(m)

    exception_str = "Traceback (most recent call last):\n"
    exception_str += "".join(filtered)
    # Removing the last \n
    exception_str = exception_str[:-1]

    return exception_str

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog="evaluation",
        description="1"
    )

    parser.add_argument(
        "--input_dir",
        help="The path to the directory containing the reference "
             "data and user submission data.",
        default=None,
        type=str,
    )

    parser.add_argument(
        "--output_dir",
        help="The path to the directory where the submission's "
             "scores.txt file will be written to.",
        default=None,
        type=str,
    )

    parser.add_argument(
        "--sim_cfg",
        help='The path to the simulator cfg',
        default=None,
        type=str
    )

    # Add more argument for training.

    parser.add_argument('--thread', type=int, default=8, help='number of threads')
    parser.add_argument('--steps', type=int, default=360, help='number of steps')
    parser.add_argument('--action_interval', type=int, default=2, help='how often agent make decisions')
    parser.add_argument('--episodes', type=int, default=100, help='training episodes')
    parser.add_argument('--save_model', action="store_true", default=False)
    parser.add_argument('--load_model', action="store_true", default=False)
    parser.add_argument("--save_rate", type=int, default=5,
                        help="save model once every time this many episodes are completed")
    parser.add_argument('--save_dir', type=str, default="model/dqn_warm_up",
                        help='directory in which model should be saved')
    parser.add_argument('--log_dir', type=str, default="cmd_log/dqn_warm_up", help='directory in which logs should be saved')

    result = {
        "success": False,
        "error_msg": "",
        "data": {
            "total_served_vehicles": -1,
            "delay_index": -1
        }
    }

    args = parser.parse_args()
    if not os.path.exists(args.log_dir):
        os.makedirs(args.log_dir)
    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(args.log_dir, datetime.now().strftime('%Y%m%d-%H%M%S') + ".log"))
    fh.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    logger.addHandler(fh)
    logger.addHandler(sh)

    msg = None

    simulator_cfg_file = args.sim_cfg
    try:
        submission_dir, scores_dir = resolve_dirs(
            os.path.dirname(__file__), args.input_dir, args.output_dir
        )
    except Exception as e:
        msg = format_exception(e)
        result['error_msg'] = msg
        json.dump(result,open(scores_dir / "scores.json",'w'),indent=2)
        raise AssertionError()
    # submission_dir, eval_scenarios_dir, scores_dir = Path("submit"), Path("../scenarios"), Path("output")
    try:
        agent_spec,gym_cfg = load_agent_submission(submission_dir)
    except Exception as e:
        msg = format_exception(e)
        result['error_msg'] = msg
        json.dump(result,open(scores_dir / "scores.json",'w'),indent=2)
        raise AssertionError()

    logger.info(f"Loaded user agent instance={agent_spec}")

    start_time = time.time()
    try:
        # train(agent_spec, simulator_cfg_file, gym_cfg)
        scores = run_simulation(agent_spec, simulator_cfg_file, gym_cfg)
    except Exception as e:
        msg = format_exception(e)
        result['error_msg'] = msg
        json.dump(result,open(scores_dir / "scores.json",'w'),indent=2)
        raise AssertionError()

    result['data']['total_served_vehicles'] = scores[0]
    result['data']['delay_index'] = scores[1]
    result['success'] = True

    # cal time
    end_time = time.time()

    logger.info(f"total evaluation cost {end_time-start_time} s")

    # write score
    logger.info("\n\n")
    logger.info("*" * 40)

    json.dump(result, open(scores_dir / "scores.json", 'w'), indent=2)

    logger.info("Evaluation complete")
