#!/usr/bin/env python3
import os
import argparse
import shutil
import subprocess
import atexit
import json
import uuid


def start_evaluation(param, names, agent, simcfg, useUuid):
    if agent.endswith("/"):
        agent = agent[:-1]
    if useUuid:
        par_agent = "%s_%s" % (agent, uuid.uuid1())
    else:
        par_agent = agent + "_".join([("%s_%.3f" % (n[:3], p)).rstrip("0") for n, p in zip(names, param)])
    print("copying", agent, "to", par_agent)
    shutil.rmtree(par_agent, ignore_errors=True)
    os.makedirs(par_agent, exist_ok=True)
    open(os.path.join(par_agent, ".gitignore"), "w").close()
    shutil.copy2(os.path.join(agent, "agent.py"), par_agent)
    with open(os.path.join(agent, "gym_cfg.py")) as cfg_in, open(os.path.join(par_agent, "gym_cfg.py"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            for n, val in zip(names, param):
                if ls and ls[0] == n:
                    ls[2] = str(val)
                    line = " ".join(ls) + "\n"
                    break
            cfg.write(line)
    with open(simcfg) as cfg_in, open(os.path.join(par_agent, "simulator.cfg"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            if ls and ls[0] == 'report_log_addr':
                ls[2] = "./%s/" % par_agent
                line = " ".join(ls) + "\n"
            cfg.write(line)
    return subprocess.Popen("docker run -v $PWD:/starter-kit kdd /starter-kit/run.sh %s" % par_agent, shell=True), par_agent, list(param)

def get_score(par_agent):
    scores = json.load(open(os.path.join(par_agent, "scores.json")))
    return scores["data"]["delay_index"]

def run_evaluation(par, names, args):
    p, par_agent, _ = start_evaluation(par, names, args.agent, args.simulator_cfg, args.uuid)
    p.wait()
    return get_score(par_agent)

def parallel_single_parameter(names, init, ranges, args):
    values = list(init)
    for idx in range(len(init)):
        scores = {}
        step = (ranges[idx][1] - ranges[idx][0]) / args.steps
        procs = []
        for i in range(args.steps):
            values[idx] = ranges[idx][0] + i * step
            procs.append(start_evaluation(values, names, args.agent, args.simulator_cfg, args.uuid))
            if args.threads and len(procs) == args.threads:
                for proc, a, par in procs:
                    proc.wait()
                    scores[a] = (par, get_score(a))
                procs = []
        for proc, a, par in procs:
            proc.wait()
            scores[a] = (par, get_score(a))
        procs = []
        min_agent, (min_par, min_score) = min(scores.items(), key=lambda i: i[1][1])
        print("scores", scores)
        print("min", min_agent, min_par, min_score)
        values[idx] = min_par[idx]
    return values

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("agent")
    parser.add_argument("-t", "--threads", type=int)
    parser.add_argument("-s", "--steps", type=int, default=10)
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
    elif args.method == "optim":
        # this needs pip install optimparallel
        from optimparallel import minimize_parallel
        opt = minimize_parallel(run_evaluation, init, (names, args), bounds=ranges, options={"eps":0.01})
    else:
        # this needs pip install scikit-optimize
        from skopt import gp_minimize
        opt = gp_minimize(lambda x: run_evaluation(x, names, args), ranges)
