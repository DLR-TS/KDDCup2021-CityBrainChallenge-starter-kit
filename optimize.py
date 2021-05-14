#!/usr/bin/env python3
import os
import argparse
import shutil
import subprocess
import atexit

#from optimparallel import minimize_parallel

def run_evaluation(par, names, agent):
    if agent.endswith("/"):
        agent = agent[:-1]
    par_agent = agent + "_".join(["_".join(p) for p in zip(names, [str(pp) for pp in par])])
    print("copying", agent, "to", par_agent)
    shutil.rmtree(par_agent, ignore_errors=True)
    os.makedirs(par_agent, exist_ok=True)
    shutil.copy2(os.path.join(agent, "agent.py"), par_agent)
    with open(os.path.join(agent, "gym_cfg.py")) as cfg_in, open(os.path.join(par_agent, "gym_cfg.py"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            for n, val in zip(names, par):
                if ls and ls[0] == n:
                    ls[2] = str(val)
                    line = " ".join(ls) + "\n"
                    break
            cfg.write(line)
    return subprocess.Popen("docker run -v $PWD:/starter-kit kdd /starter-kit/run.sh %s" % par_agent, shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("agent")
    parser.add_argument("-t", "--threads", type=int)
    parser.add_argument("-s", "--steps", type=int, default=10)
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
    for idx in range(len(init)):
        step = (ranges[idx][1] - ranges[idx][0]) / args.steps
        values = list(init)
        procs = []
        for i in range(args.steps):
            values[idx] = ranges[idx][0] + i * step
            procs.append(run_evaluation(values, names, args.agent))
            if args.threads and len(procs) == args.threads:
                for p in procs:
                    p.wait()
                procs = []
        for p in procs:
            p.wait()
#    opt = minimize_parallel(run_evaluation, init, names, bounds=ranges)
