#!/usr/bin/env python3
import os
import argparse
import shutil
import subprocess
import atexit
import json
import uuid
import glob
import datetime
import hashlib
from collections import defaultdict


def start_evaluation(param, names, args, flow="0"):
    if args.agent.endswith("/"):
        agent = args.agent[:-1]
    else:
        agent = args.agent
    if args.uuid:
        par_agent = "%s_%s" % (agent, uuid.uuid1())
    else:
        par_agent = agent + "_".join([("%s_%.3f" % (n[:3], p)).rstrip("0") for n, p in zip(names, param)])
    if args.max_time != 3600:
        par_agent += "_t%s" % args.max_time
    par_agent += "_f%s" % flow
    print("copying", agent, "to", par_agent)
    shutil.rmtree(par_agent, ignore_errors=True)
    os.makedirs(par_agent, exist_ok=True)
    open(os.path.join(par_agent, ".gitignore"), "w").close()
    for py in glob.glob(os.path.join(agent, "*.py")):
        shutil.copy2(py, par_agent)
    with open(os.path.join(agent, "gym_cfg.py")) as cfg_in, open(os.path.join(par_agent, "gym_cfg.py"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            for n, val in zip(names, param):
                if ls and ls[0] == n:
                    ls[2] = "%s" % val
                    line = " ".join(ls) + "\n"
                    break
            cfg.write(line)
    with open(args.simulator_cfg) as cfg_in, open(os.path.join(par_agent, "simulator.cfg"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            if ls and ls[0] == 'report_log_addr':
                ls[2] = "./%s/" % par_agent
                line = " ".join(ls) + "\n"
            if ls and ls[0] == 'max_time_epoch':
                ls[2] = "%s" % args.max_time
                line = " ".join(ls) + "\n"
            if ls and ls[0] == 'vehicle_file_addr':
                ls[2] = ls[2].replace("flow0.txt", "flow%s.txt" % flow)
                line = " ".join(ls) + "\n"
            cfg.write(line)
    return subprocess.Popen("docker run -v $PWD:/starter-kit kdd /starter-kit/run.sh %s" % par_agent, shell=True), par_agent, tuple(param), flow

def get_score(par_agent, flow="0"):
    scores = json.load(open(os.path.join(par_agent, flow, "scores.json")))
    return scores["data"]["delay_index"]

def run_evaluation(par, names, args):
    procs = []
    scores = 0
    for f in range(args.flows):
        flow = str(f)
        procs.append(start_evaluation(par, names, args, flow))
    for proc, agent_dir, par, flow in procs:
        proc.wait()
        scores += get_score(agent_dir, flow)
    return scores

def parallel_single_parameter(names, init, ranges, args):
    values = list(init)
    for idx in range(len(init)):
        scores = defaultdict(float)
        step = (ranges[idx][1] - ranges[idx][0]) / args.steps
        procs = []
        for i in range(args.steps):
            values[idx] = ranges[idx][0] + i * step
            for f in range(args.flows):
                flow = str(f)
                procs.append(start_evaluation(values, names, args, flow))
                if args.threads and len(procs) == args.threads:
                    for proc, agent_dir, par, flow in procs:
                        proc.wait()
                        scores[par] += get_score(agent_dir, flow)
                    procs = []
        for proc, agent_dir, par, flow in procs:
            proc.wait()
            scores[par] += get_score(agent_dir, flow)
        procs = []
        with open("optimize.log", "a") as log:
            hasher = hashlib.md5()
            hasher.update(open(os.path.join(args.agent, 'agent.py'), 'rb').read())
            print(hasher.hexdigest(), datetime.datetime.now(), file=log)
            print(args, list(zip(names, ranges)), file=log)
            print("scores", scores)
            print("scores", scores, file=log)
            min_par, min_score = min(scores.items(), key=lambda i: i[1])
            print("min", min_par, min_score)
            print("min", min_par, min_score, file=log)
            print(file=log)
        values[idx] = min_par[idx]
    return values

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("agent")
    parser.add_argument("-t", "--threads", type=int, default=10)
    parser.add_argument("-s", "--steps", type=int, default=10)
    parser.add_argument("-f", "--flows", type=int, default=3)
    parser.add_argument("-a", "--max-time", type=int, default=3600)
    parser.add_argument("-c", "--simulator-cfg", default="cfg/simulator.cfg")
    parser.add_argument("-m", "--method", default="plain")
    parser.add_argument("-u", "--uuid", action="store_true", default=False)
    args = parser.parse_args()

    init = []
    ranges = []
    names = []
    for line in open(os.path.join(args.agent, "gym_cfg.py")):
        r = None
        if "optimized" in line:
            ls = line.split()
            try:
                initial = float(ls[2])
                r = (float(ls[-2]), float(ls[-1]))
            except:
                pass
        if r:
            init.append(initial)
            ranges.append(r)
            names.append(ls[0])
    print("optimizing", names, init, ranges)
    atexit.register(lambda: subprocess.call("docker kill $(docker ps -q)", shell=True))
    if args.method == "plain":
        opt = parallel_single_parameter(names, init, ranges, args)
    elif args.method == "cobyla":
        def constr(x, names, args):
            print(x)
            for v, (lower, upper) in zip(x, ranges):
                if v < lower or v > upper:
                    return -1
            return 1
        from scipy.optimize import fmin_cobyla
        fmin_cobyla(run_evaluation, init, cons=[constr], args=(names, args), rhoend=1e-7)
    elif args.method == "optim":
        # this needs pip install optimparallel
        from optimparallel import minimize_parallel
        opt = minimize_parallel(run_evaluation, init, (names, args), bounds=ranges, options={"eps":0.01})
    else:
        # this needs pip install scikit-optimize
        from skopt import Optimizer
        # from skopt.space import Real  # to be used for the dimensions argument like [Real(-5.0, 10.0), Real(0.0, 15.0)]
        from joblib import Parallel, delayed

        optimizer = Optimizer(dimensions=ranges, random_state=42)
        for i in range(args.steps):
            x = optimizer.ask(n_points=args.threads)  # x is a list of n_points points
            y = Parallel(n_jobs=args.threads)(delayed(lambda x: run_evaluation(x, names, args))(v) for v in x)  # evaluate points in parallel
            optimizer.tell(x, y)
        opt = min(optimizer.yi)
