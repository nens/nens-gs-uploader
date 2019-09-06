# -*- coding: utf-8 -*-
"""#
Created on Tue Apr 30 11:56:20 2019

@author: chris.kerklaan - N&S
"""
# system imports
import os
import logging
import datetime

# Globals
time_last_print_small = datetime.datetime.now()
time_last_print_large = datetime.datetime.now()


def log_time(log_type, s1="", s2="", size="s"):
    time = print_time(s1=s1, s2=s2, size="s")

    if log_type is "info":
        logging.info("%s - %s", s1, s2)
    elif log_type is "debug":
        logging.debug("%s - %s", s1, s2)
    elif log_type is "warning":
        logging.warning("%s - %s", s1, s2)
    elif log_type is "error":
        logging.error("%s - %s", s1, s2)
    else:
        print("no log")

    print(time)


def print_time(s1="", s2="", size="s"):
    global time_last_print_small
    global time_last_print_large

    now = datetime.datetime.now()
    if size == "s":
        _print = "{} - {} - {} - {}".format(
            now, now - time_last_print_small, s1, s2
        )

    elif size == "l":
        _print = "{} - {} - {} - {}".format(
            now, now - time_last_print_large, s1, s2
        )

    else:
        pass

    time_last_print_small = now
    time_last_print_large = now
    return print(_print)


def percentage(count, total):
    return str((count / total) * 100) + "%"


def mk_temp(path=os.getcwd()):
    tempfolder = os.path.join(path, "temp")
    if not os.path.exists(tempfolder):
        os.mkdir(tempfolder)
    return tempfolder
