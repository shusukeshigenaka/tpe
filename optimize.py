import time
from multiprocessing import Process, Lock
import csv
import os
import ConfigSpace as CS
import ConfigSpace.hyperparameters as CSH
from argparse import ArgumentParser as ArgPar
from sampler.tpe_sampler import TPESampler

def sample_target(model, num, n_jobs, lock, n_startup_trials = 10):
    def _imp(hp_info):
        target_cs = CS.ConfigurationSpace().add_hyperparameter(hp_info)
        return TPESampler(model, num, target_cs, n_jobs, lock, n_startup_trials = n_startup_trials).sample()

    return _imp

def create_hyperparameter(hp_type, name, lower, upper, default_value = None, log = False, q = None, choices = None):
    if hp_type == "int":
        return CSH.UniformIntegerHyperparameter(name = name, lower = lower, upper = upper, default_value = default_value, log = log, q = q)
    elif hp_type == "float":
        return CSH.UniformFloatHyperparameter(name = name, lower = lower, upper = upper, default_value = default_value, log = log, q = q)
    elif hp_type == "cat":
        return CSH.CategoricalHyperparameter(name = name, default_value = default_value, choices = choices)
    else:
        raise ValueError("The hp_type must be chosen from [int, float, cat]")

def save_evaluation(hp_dict, model, num, n_jobs):
    for var_name, hp in hp_dict.items():               
        with open("evaluation/{}/{:0>3}/{}.csv".format(model, num, var_name), "a", newline = "") as f:
            writer = csv.writer(f, delimiter = ",", quotechar = "'")
            writer.writerow([n_jobs, hp])

def print_iterations(n_jobs, loss, acc = None):
    print("")
    print("###################")
    print("# evaluation{: >5} #".format(n_jobs))
    print("###################")

    if acc:
        print("loss: {:.4f} acc: {:.2f}%".format(loss, acc * 100))
    else:
        print("loss: {:.4f}".format(loss))

def optimize(model, num, obj, max_jobs = 100, n_parallels = None):
    if n_parallels == None or n_parallels <= 1:
        _optimize_sequential(model, num, obj, max_jobs = max_jobs)
    else:
        _optimize_parallel(model, num, obj, max_jobs = max_jobs, n_parallels = n_parallels)
    

def _optimize_sequential(model, num, obj, max_jobs = 100):
    if os.path.isfile("evaluation/{}/{:0>3}/loss.csv".format(model, num)):
        with open("evaluation/{}/{:0>3}/loss.csv".format(model, num), "r", newline = "") as f:
            n_jobs = len(list(csv.reader(f, delimiter = ",")))
    else:
        n_jobs = 0
    max_jobs += n_jobs

    while True:
        n_cuda = 0

        obj(model, num, n_cuda, n_jobs)
        n_jobs += 1
            
        if n_jobs >= max_jobs:
            break

def _optimize_parallel(model, num, obj, max_jobs = 100, n_parallels = 4):
    if os.path.isfile("evaluation/{}/{:0>3}/loss.csv".format(model, num)):
        with open("evaluation/{}/{:0>3}/loss.csv".format(model, num), "r", newline = "") as f:
            n_jobs = len(list(csv.reader(f, delimiter = ",")))
    else:
        n_jobs = 0
    
    jobs = []
    n_runnings = 0
    max_jobs += n_jobs
    lock = Lock()

    while True:
        cudas = [False for _ in range(n_parallels)]
        if len(jobs) > 0:
            n_runnings = 0
            new_jobs = []
            for job in jobs:
                if job[1].is_alive():
                    new_jobs.append(job)
                    cudas[job[0]] = True
            jobs = new_jobs
            n_runnings = len(jobs)
        else:
            n_runnings = 0

        for _ in range(max(0, n_parallels - n_runnings)):
            n_cuda = cudas.index(False)
            p = Process(target = obj, args = (model, num, n_cuda, n_jobs, lock))
            p.start()
            jobs.append([n_cuda, p])
            n_jobs += 1
            
            if n_jobs >= max_jobs:
                break
            
            time.sleep(1.0e-6)
    
        if n_jobs >= max_jobs:
            break
