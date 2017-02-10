"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.
This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).
"""

"""
Performance profiling function available in the SONATA SDK
(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>

1) via the selected vim, start a VNF and chain it to a traffic generator and sink

2) steer the traffic generation to reach the max performance in an optimal way

3) gather metrics while traffic is flowing

4) return a table with the test results
"""

import time
import curses
import sys
import copy
import os

from son.monitor.msd import msd
from son.monitor.son_emu import Emu
import son.monitor.monitor as sonmonitor

from son.monitor.prometheus_lib import query_Prometheus, compute2vnfquery

import threading
from collections import deque
import numpy as np
from scipy.stats import norm, t


import logging
LOG = logging.getLogger('Profiler')
LOG.setLevel(level=logging.DEBUG)
#LOG.addHandler(logging.StreamHandler())
LOG.propagate = False
#logging.getLogger().removeHandler(logging.StreamHandler())


# TODO read from ped file
SON_EMU_IP = '172.17.0.1'
SON_EMU_IP = 'localhost'
SON_EMU_REST_API_PORT = 5001
SON_EMU_API = "http://{0}:{1}".format(SON_EMU_IP, SON_EMU_REST_API_PORT)


# TODO call from son-profile
class Emu_Profiler():

    def __init__(self, input_msd_path, output_msd_path, input_commands, configuration_commands, **kwargs):

        # Grafana dashboard title
        defaults = {
            'title':'son-profile',
            'timeout':20,
            'overload_vnf_list':[]
        }
        defaults.update(kwargs)
        self.title = defaults.get('title')
        #class to control son-emu (export/query metrics)
        self.emu = Emu(SON_EMU_API)
        # list of class Metric
        self.input_msd = msd(input_msd_path, self.emu, title=self.title)
        self.input_metrics = self.input_msd.get_metrics_list()
        LOG.info('input metrics:{0}'.format(self.input_metrics))

        self.output_msd = msd(output_msd_path, self.emu, title=self.title)
        self.output_metrics = self.output_msd.get_metrics_list()
        LOG.info('output metrics:{0}'.format(self.output_metrics))


        # each list item is a dict with {vnf_name:"cmd_to_execute", ..}
        self.input_commands = input_commands
        LOG.info('input commands:{0}'.format(self.input_commands))

        # the configuration commands that need to be executed before the load starts
        self.configuration_commands = configuration_commands
        LOG.info("configuration commands:{0}".format(self.configuration_commands))


        self.timeout = int(defaults.get('timeout'))

        # check if prometheus is running
        sonmonitor.monitor.start_containers()

        # export msd's to Grafana
        self.input_msd.start()
        self.output_msd.start(overwrite=False)

        overload_vnf_list = defaults.get('overload_vnf_list')
        self.overload_monitor = Overload_Monitor(vnf_list=overload_vnf_list)
        # host overload flag
        self.overload = self.overload_monitor.overload_flag

        # profiling threaded function
        self.profiling_thread = threading.Thread(target=self.profling_loop)

        # list of dict for profiling results
        self.profiling_results = list()

        # the number of the current profiling run
        self.run_number = 0

        # display option
        self.no_display = defaults.get('no_display', False)

    def start_experiment(self):
        # start configuration commands
        for vnf_name, cmd_list in self.configuration_commands.items():
            for cmd in cmd_list:
                self.emu.docker_exec(vnf_name=vnf_name, cmd=cmd)

        # start overload detection
        self.overload_monitor.start(self.emu)

        # start the profling loop
        self.profiling_thread.start()

        if self.no_display == False:
            # nicely print values
            rows, columns = os.popen('stty size', 'r').read().split()
            # Set the Terminal window size larger than its default
            # to make sure the profiling results are fitting
            if int(rows) < 40 or int(columns) < 120:
                sys.stdout.write("\x1b[8;{rows};{cols}t".format(rows=40, cols=120))
            # print something to reset terminal
            print("")
            n = os.system("clear")
            # Add a delay to allow settings to settle...
            time.sleep(1)
            curses.wrapper(self.display_loop)


        # stop overload detection
        self.overload_monitor.stop(self.emu)


    def profling_loop(self):

        # start with empty results
        self.profiling_results.clear()
        self.run_number = 1

        # one cmd_dict per profile run
        for cmd_dict in self.input_commands:
            # reset metrics
            for metric in self.input_metrics+self.output_metrics:
                metric.reset()

            # start the load
            for vnf_name, cmd in cmd_dict.items():
                self.emu.docker_exec(vnf_name=vnf_name, cmd=cmd)

            # let the load stabilize
            time.sleep(2)
            # reset the overload monitor
            self.overload_monitor.reset()

            # monitor the metrics
            start_time = time.time()

            while((time.time()-start_time) < self.timeout):
                # add the new metric values to the list
                input_metrics = self.query_metrics(self.input_metrics)
                output_metrics = self.query_metrics(self.output_metrics)
                time.sleep(1)
                if self.overload.is_set():
                    LOG.info('overload detected')

            # stop the load
            for vnf_name, cmd in cmd_dict.items():
                self.emu.docker_exec(vnf_name=vnf_name, cmd=cmd, action='stop')

            # add the result of this profiling run to the results list
            profiling_result = dict(
                input_metrics=copy.deepcopy(input_metrics),
                output_metrics=copy.deepcopy(output_metrics)
            )
            self.profiling_results.append(profiling_result)
            self.run_number += 1


    def display_loop(self, stdscr):
        # while profiling loop is running, display the metrics
        # Clear screen
        stdscr.clear()
        # screen = curses.initscr()

        maxy, maxx = stdscr.getmaxyx()


        log_height = 10
        log_begin_y = maxy - log_height
        width = maxx
        logwin = curses.newwin(log_height, width, log_begin_y, 0)
        logwin.scrollok(True)

        height = maxy - log_height
        width = maxx
        # take large window to hold results
        resultwin = curses.newpad(height, 10000)
        resultwin.scrollok(True)

        # curses.setsyx(-1, -1)
        # win.setscrreg(begin_y, begin_y+height)
        # win.idlok(True)
        # win.leaveok(True)

        # LOG.removeHandler(logging.StreamHandler())
        LOG.addHandler(CursesHandler(logwin))

        stdscr.clear()

        resultwin.addstr(0, 0, "------------ input metrics ------------")
        i = 1
        for metric in self.input_metrics:
            resultwin.addstr(i, 0, "{0} ({1})".format(metric.metric_name, metric.unit))
            i += 1

        resultwin.addstr(len(self.input_metrics) + i, 0 , "------------ output metrics ------------")
        i = len(self.input_metrics) + i + 1
        for metric in self.output_metrics:
            resultwin.addstr(i, 0, "{0} ({1})".format(metric.metric_name, metric.unit))
            i += 1

        maxy, maxx = stdscr.getmaxyx()
        resultwin.refresh(0, 0, 0, 0, height, maxx-1)

        while self.profiling_thread.isAlive():
            i = 1
            for metric in self.input_metrics:
                resultwin.addstr(i, 40*self.run_number, "{0:.2f}".format(metric.last_value))
                i += 1

            i = len(self.input_metrics) + i + 1
            for metric in self.output_metrics:
                resultwin.addstr(i, 40*self.run_number, "{0:.2f}".format(metric.last_value))
                i += 1

            # print the final result
            result_number = 1
            for result in self.profiling_results:

                i = 1
                for metric in result['input_metrics']:
                    resultwin.addstr(i, 40*result_number, "{0:.2f} ({1:.2f},{2:.2f})".format(metric.average, metric.CI[0], metric.CI[1]))
                    i += 1

                i = len(self.input_metrics) + i + 1
                for metric in result['output_metrics']:
                    resultwin.addstr(i, 40*result_number, "{0:.2f} ({1:.2f},{2:.2f})".format(metric.average, metric.CI[0], metric.CI[1]))
                    i += 1

                result_number += 1

            maxy, maxx = stdscr.getmaxyx()
            resultwin.refresh(0, 0, 0, 0, height, maxx-1)
            time.sleep(1)

        # print the final result
        result_number = 1
        for result in self.profiling_results:

            i = 1
            for metric in result['input_metrics']:
                resultwin.addstr(i, 40 * result_number,
                              "{0:.2f} ({1:.2f},{2:.2f})".format(metric.average, metric.CI[0], metric.CI[1]))
                i += 1

            i = len(self.input_metrics) + i + 1
            for metric in result['output_metrics']:
                resultwin.addstr(i, 40 * result_number,
                              "{0:.2f} ({1:.2f},{2:.2f})".format(metric.average, metric.CI[0], metric.CI[1]))
                i += 1

            result_number += 1



        #wait for input keypress
        resultwin.addstr(i + 1, 0, "press a key to close this window...")
        maxy, maxx = stdscr.getmaxyx()
        resultwin.refresh(0, 0, 0, 0, height, maxx - 1)
        #stdscr.refresh()
        resultwin.getkey()
        LOG.removeHandler(CursesHandler(logwin))
        # curses.endwin()
        # LOG.addHandler(logging.StreamHandler())
        # wait until curses is finished
        # while not curses.isendwin():
        #    time.sleep(0.5)

    def stop_experiment(self):
        self.input_msd.stop()
        self.output_msd.stop()

    def query_metrics(self, metrics):
        # fill the values of the metrics
        for metric in metrics:
            query = metric.query
            try:
                ret = query_Prometheus(query)
                metric.addValue(float(ret[1]))
            except:
                 LOG.info('Prometheus query failed: {0} \nquery: {1} \nerror:{2}'.format(ret, query, sys.exc_info()[0]))
                 continue
            #metric_name = metric.metric_name
            #metric_unit = metric.unit
            #LOG.info("metric query: {1} {0} {2}".format(metric.value, metric_name, metric_unit))
        return metrics


class Overload_Monitor():

    def __init__(self, vnf_list):
        # host cpu query
        self.host_cpu_query = compute2vnfquery['host_cpu'].query_template.format('')
        self.host_cpu_values = deque(maxlen=10)
        self.vnf_list = vnf_list

        # query the number of available cores
        host_num_cpu_query = compute2vnfquery['num_cores'].query_template.format('')
        ret = query_Prometheus(host_num_cpu_query)
        self.num_cores = int(ret[1])

        # cpu skewness query
        self.skew_query_dict = {}
        self.skew_value_dict = {}
        for vnf_name in vnf_list:
            skew_query = compute2vnfquery['skew_cpu'].query_template.format(vnf_name)
            self.skew_query_dict[vnf_name] = skew_query
            self.skew_value_dict[vnf_name] = deque(maxlen=5)

        self.monitor = None
        self.stop_event = threading.Event()
        self.overload_flag = threading.Event()


    def query_metrics(self):
        # query the skewness metric from a vnf ever 2 secs
        # calculate the running average over 5 samples
        # query the host_cpu metric from a vnf ever 2 secs
        # calculate the running average and confidence intervals over 10 samples

        while not self.stop_event.is_set():
            # query host cpu
            try:
                ret = query_Prometheus(self.host_cpu_query)
                value = float(ret[1])/self.num_cores
                self.host_cpu_values.append(value)
            except:
                LOG.info('Prometheus query failed: {0} \nquery: {1}'.format(ret, self.host_cpu_query))

            # query skewness cpu
            try:
                for vnf_name, query in self.skew_query_dict.items():

                    ret = query_Prometheus(query)
                    value = float(ret[1])
                    self.skew_value_dict[vnf_name].append(value)
            except:
                LOG.info('Prometheus query failed: {0} \nquery: {1}'.format(ret, query))

            # check overload
            N = len(self.host_cpu_values)

            if N < 5:
                time.sleep(2)
                continue

            mu = np.mean(self.host_cpu_values)
            sigma = np.std(self.host_cpu_values)
            R = t.interval(0.95, N - 1, loc=mu, scale=sigma / np.sqrt(N))
            host_cpu_load = float(R[1])
            if host_cpu_load > 95 :
                LOG.info("host cpu overload CI: {0}".format(R))


            skew_list = []
            for vnf_name, values in self.skew_value_dict.items():
                skew_avg = np.mean(values)
                skew_list.append(skew_avg)
                #LOG.info("{0} skewness avg: {1}".format(vnf_name, np.mean(values)))
                if skew_avg < 0:
                    LOG.info("{0} skewness overload: {1}".format(vnf_name, skew_avg))

            negative_skews = [s for s in skew_list if s < 0]
            if (host_cpu_load > 95) or (len(negative_skews) > 0) :
                self.overload_flag.set()
            else:
                self.overload_flag.clear()

            time.sleep(2)



    def start(self, son_emu):
        if self.monitor is not None:
            LOG.warning('Overload monitor thread is already running')
            return

        # start skewness monitor
        for vnf_name in self.vnf_list:
            son_emu.update_skewness_monitor(vnf_name=vnf_name, resource_name='cpu', action='start')

        # wait some time until first metrics are gathered
        time.sleep(2)
        self.monitor = threading.Thread(target=self.query_metrics)
        self.monitor.start()


    def stop(self, son_emu):
        self.stop_event.set()
        for vnf_name in self.vnf_list:
            son_emu.update_skewness_monitor(vnf_name=vnf_name, resource_name='cpu', action='stop')


    def reset(self):
        self.host_cpu_values.clear()
        for vnf_name, query in self.skew_query_dict.items():
            self.skew_value_dict[vnf_name].clear()




class CursesHandler(logging.Handler):

    def __init__(self, screen):
        logging.Handler.__init__(self)
        self.screen = screen

    def emit(self, record):
        try:
            msg = self.format(record)
            screen = self.screen
            fs = "%s\n"
            screen.addstr(fs % msg)
            maxy, maxx = screen.getmaxyx()
            screen.resize(maxy, maxx)
            screen.refresh()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)