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
from scipy.stats import t
from son.profile.helper import write_yaml, read_yaml
import logging
import operator
from collections import defaultdict, OrderedDict
import matplotlib.pyplot as plt
import multiprocessing

LOG = logging.getLogger('Profiler')
LOG.setLevel(level=logging.INFO)
LOG.propagate = True

# TODO read from ped file or config file
SON_EMU_IP = '172.17.0.1'
SON_EMU_IP = 'localhost'
SON_EMU_REST_API_PORT = 5001
SON_EMU_API = "http://{0}:{1}".format(SON_EMU_IP, SON_EMU_REST_API_PORT)

# path+file to store the results (working directory = default)
RESULT_FILE = "test_results.yml"

# call from son-profile
class Emu_Profiler():

    def __init__(self, input_msd_path, output_msd_path, experiment, **kwargs):

        self.configuration_space = experiment.configuration_space_list
        self.pre_config_commands = experiment.pre_configuration
        self.overload_vnf_list = experiment.overload_vnf_list
        self.timeout = int(experiment.time_limit)
        self.experiment_name = experiment.name
        self.experiment = experiment

        # Grafana dashboard title
        defaults = {
            'title':'son-profile',
        }
        defaults.update(kwargs)
        self.title = defaults.get('title')

        # results file
        self.results_file = defaults.get('results_file', RESULT_FILE)
        # graph only option
        self.graph_only = defaults.get('graph_only', False)

        # generate profiling results
        self.profiling_results = list()
        self.profile_calc = ProfileCalculator(self.experiment)

        # only display graph of previous profile run
        if self.graph_only:
            self.profile_calc.display_graph(file=self.results_file)
            return
        else:
            self.profile_calc.start_plot()
            self.profile_calc.enable_updating.set()

        #class to control son-emu (export/query metrics)
        self.emu = Emu(SON_EMU_API)
        # list of class Metric
        self.input_metrics = []
        self.input_msd = None
        if input_msd_path:
            self.input_msd = msd(input_msd_path, self.emu, title=self.title)
            self.input_metrics = self.input_msd.get_metrics_list()
            LOG.info('input metrics:{0}'.format(self.input_metrics))
        self.output_metrics = []
        self.output_msd = None
        if output_msd_path:
            self.output_msd = msd(output_msd_path, self.emu, title=self.title)
            self.output_metrics = self.output_msd.get_metrics_list()
            LOG.debug('output metrics:{0}'.format(self.output_metrics))

        # the configuration commands that needs to be executed before the load starts
        LOG.info("configuration commands:{0}".format(self.pre_config_commands))

        # time the test that is running
        if self.timeout < 11:
            LOG.warning("timeout should be > 10 to allow overload detection")

        # the resource configuration of the current experiment
        self.resource_configuration = defaultdict(dict)
        # check if prometheus is running
        sonmonitor.monitor.start_containers()

        # export msd's to Grafana
        overwrite = True
        if input_msd_path:
            self.input_msd.start(overwrite=overwrite)
            overwrite = False
        if output_msd_path:
            self.output_msd.start(overwrite=overwrite)

        LOG.info('overload_vnf_list: {0}'.format(self.overload_vnf_list))
        self.overload_monitor = Overload_Monitor(vnf_list=self.overload_vnf_list)
        # host overload flag
        self.overload = self.overload_monitor.overload_flag

        # profiling threaded function
        self.profiling_thread = threading.Thread(target=self.profiling_loop)

        # the number of the current profiling run
        self.run_number = 1

        # display option
        self.no_display = defaults.get('no_display', False)


    def start_experiment(self):
        if self.graph_only:
            return

         # start pre-configuration commands
        for vnf_name, cmd_list in self.pre_config_commands.items():
            for cmd in cmd_list:
                self.emu.exec(vnf_name=vnf_name, cmd=cmd)

        # start overload detection
        #if len(self.overload_vnf_list) > 0 :
        self.overload_monitor.start(self.emu)

        # start the profling loop
        self.profiling_thread.start()

        if self.no_display == False:
            # nicely print values
            rows, columns = os.popen('stty size', 'r').read().split()
            # Set the Terminal window size larger than its default
            # to make sure the profiling results are fitting
            if int(rows) < 40 or int(columns) < 130:
                sys.stdout.write("\x1b[8;{rows};{cols}t".format(rows=40, cols=130))
            # print something to reset terminal
            print("")
            n = os.system("clear")
            # Add a delay to allow settings to settle...
            time.sleep(1)
            curses.wrapper(self.display_loop)
        else:
            # wait for profiling thread to end
            self.profiling_thread.join()

        # stop overload detection
        self.overload_monitor.stop(self.emu)

        # write results to file
        self.write_results_to_file(self.results_file)

        #finalize the calculation of the performance profile
        self.profile_calc.finalize_graph(show_final=self.no_display)


    def profiling_loop(self):

        # start with empty results
        self.profiling_results.clear()
        self.run_number = 1

        # one cmd_dict per profile run
        for experiment in self.configuration_space:

            # parse the experiment's parameters
            resource_dict = defaultdict(dict)
            cmd_dict = {}
            vnf_name2order = dict()
            for key, value in experiment.items():
                array = key.split(':')
                if len(array) < 3:
                    continue
                type, vnf_name, param = array
                if type == 'measurement_point' and param == 'cmd':
                    cmd_dict[vnf_name] = value
                elif type == 'measurement_point' and param == 'cmd_order':
                    vnf_name2order[vnf_name] = int(value)
                elif type == 'resource_limitation':
                    resource_dict[vnf_name][param] = value

            self.resource_configuration = resource_dict
            LOG.info("resource config: {0}".format(resource_dict))


            # create ordered list of vnf_names, so the commands are always executed in a defined order
            vnforder_dict = OrderedDict(sorted(vnf_name2order.items(), key=operator.itemgetter(1)))
            vnforder_list = [vnf_name for vnf_name, order in vnforder_dict.items()]
            # also get the vnfs which do not have an cmd_order specified, and add them to the list
            leftover_vnfs = [vnf_name for vnf_name in cmd_dict if vnf_name not in vnforder_list]
            vnforder_list = vnforder_list + leftover_vnfs
            LOG.debug("vnf order:{0}".format(vnforder_list))

            # allocate the specified resources
            self.set_resources()

            # reset metrics
            for metric in self.input_metrics + self.output_metrics:
                metric.reset()

            LOG.info("vnf commands: {0}".format(cmd_dict))
            # start the load
            for vnf_name in vnforder_list:
                cmd = cmd_dict.get(vnf_name)
                self.emu.exec(vnf_name=vnf_name, cmd=cmd)

            # let the load stabilize
            time.sleep(1)
            # reset the overload monitor
            self.overload_monitor.reset()

            # monitor the metrics
            start_time = time.time()
            LOG.info('waiting {} seconds while gathering metrics...'.format(self.timeout))

            while((time.time()-start_time) < self.timeout):
                # add the new metric values to the list
                input_metrics = self.query_metrics(self.input_metrics)
                output_metrics = self.query_metrics(self.output_metrics)
                time.sleep(1)
                if self.overload.is_set():
                    LOG.info('overload detected')

            # stop the load
            LOG.info('end of experiment: {0} - run{1}/{2}'.format(self.experiment_name, self.run_number, len(self.configuration_space)))
            for vnf_name, cmd in cmd_dict.items():
                self.emu.exec(vnf_name=vnf_name, cmd=cmd, action='stop')

            # add the result of this profiling run to the results list
            profiling_result = dict(
                resource_alloc=(self.resource_configuration),
                input_metrics=(input_metrics),
                output_metrics=(output_metrics),
                name=self.experiment_name,
                run=self.run_number,
                total=len(self.configuration_space)
            )
            result = self.filter_profile_results(profiling_result)
            self.profiling_results.append(result)
            # update the plot
            self.profile_calc.update_results(result)

            self.run_number += 1

        LOG.info('end of experiment: {}'.format(self.experiment_name))


    def display_loop(self, stdscr):
        # while profiling loop is running, display the metrics on the CLI
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
        LOG.propagate = False
        logging.getLogger('son_emu_lib').propagate=False
        LOG.addHandler(CursesHandler(logwin))

        stdscr.clear()

        i = 0
        resultwin.addstr(i, 0, "---- Run: {2}/{3}  -----  Timer: {0} secs ----".format(
            0, self.timeout, self.run_number, len(self.configuration_space)))
        i += 1
        resultwin.addstr(i, 0, "------------ resource allocation ------------")
        i += 1
        len_resources = 0
        for vnf_name, resource_dict in self.resource_configuration.items():
            for resource in resource_dict:
                resultwin.addstr(len_resources+i, 0, "{0}".format(resource))
                len_resources += 1

        i += 2 + len_resources
        resultwin.addstr(i, 0, "------------ input metrics ------------")
        i += 1
        for metric in self.input_metrics:
            resultwin.addstr(i, 0, "{0} ({1})".format(metric.metric_name, metric.unit))
            i += 1

        i += 2
        resultwin.addstr(i, 0 , "------------ output metrics ------------")
        i += 1
        for metric in self.output_metrics:
            resultwin.addstr(i, 0, "{0} ({1})".format(metric.metric_name, metric.unit))
            i += 1

        maxy, maxx = stdscr.getmaxyx()
        resultwin.refresh(0, 0, 0, 0, height, maxx-1)

        time_counter = 0
        while self.profiling_thread.isAlive():
            resultwin.addstr(0, 0, "---- Run: {2}/{3}  ----- Timer: {0} secs ----".format(
                time_counter, self.timeout, self.run_number, len(self.configuration_space)))
            i = 2
            for vnf_name, resource_dict in self.resource_configuration.items():
                for resource, value in resource_dict.items():
                    resultwin.addstr(i, 50, "{0}".format(value))
                    i += 1

            # start from length of resource parameters
            i += 3
            for metric in self.input_metrics:
                resultwin.addstr(i, 50, "{0:.2f}".format(metric.last_value))
                i += 1

            i += 3
            for metric in self.output_metrics:
                resultwin.addstr(i, 50, "{0:.2f}".format(metric.last_value))
                i += 1

            maxy, maxx = stdscr.getmaxyx()
            resultwin.refresh(0, 0, 0, 0, height, maxx-1)
            time.sleep(1)
            time_counter += 1

        # print the final result
        result_number = 1
        for result in self.profiling_results:

            # start from length of resource parameters
            i = len_resources + 5
            for metric in result['input_metrics']:
                resultwin.addstr(i, 40 * result_number,
                              "{0:.2f} ({1:.2f},{2:.2f})".format(metric['average'], metric['CI_low'], metric['CI_high']))
                i += 1

            i += 3
            for metric in result['output_metrics']:
                resultwin.addstr(i, 40 * result_number,
                              "{0:.2f} ({1:.2f},{2:.2f})".format(metric['average'], metric['CI_low'], metric['CI_high']))
                i += 1

            result_number += 1



        #wait for input keypress
        resultwin.addstr(i + 1, 0, "press a key to close this window...")
        maxy, maxx = stdscr.getmaxyx()
        resultwin.refresh(0, 0, 0, 0, height, maxx - 1)
        #stdscr.refresh()
        resultwin.getkey()
        LOG.removeHandler(CursesHandler(logwin))
        LOG.propagate = True
        logging.getLogger('son_emu_lib').propagate = True
        # curses.endwin()
        # LOG.addHandler(logging.StreamHandler())
        # wait until curses is finished
        # while not curses.isendwin():
        #    time.sleep(0.5)

    def write_results_to_file(self, file_name):
        write_yaml(file_name, self.profiling_results)

    def filter_profile_results(self, profile_result):
        result = dict()
        result['name'] = profile_result['name'] + str(profile_result['run'])
        result['input_metrics'] = []
        result['output_metrics'] = []
        result['resource_alloc'] = dict()
        for metric in profile_result['input_metrics']:
            metric_dict = dict(
                name = metric.metric_name,
                type = metric.metric_type,
                unit = metric.unit,
                average = metric.average,
                desc = metric.desc,
                CI_low = float(metric.CI[0]),
                CI_high = float(metric.CI[1]),
            )
            result['input_metrics'].append(metric_dict)

        for metric in profile_result['output_metrics']:
            metric_dict = dict(
                name=metric.metric_name,
                type=metric.metric_type,
                unit=metric.unit,
                average=metric.average,
                desc=metric.desc,
                CI_low=float(metric.CI[0]),
                CI_high=float(metric.CI[1]),
            )
            result['output_metrics'].append(metric_dict)

        # avoid copying empty dicts into the results
        for vnf_name in profile_result['resource_alloc']:
            if len(profile_result['resource_alloc'][vnf_name]) > 0:
                result['resource_alloc'][vnf_name] = profile_result['resource_alloc'][vnf_name]

        return result

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
                LOG.debug('metric: {0}={1}'.format(metric.metric_name, float(ret[1])))
            except:
                 LOG.info('Prometheus query failed: {0} \nquery: {1} \nerror:{2}'.format(ret, query, sys.exc_info()[0]))
                 continue
            #metric_name = metric.metric_name
            #metric_unit = metric.unit
            #LOG.info("metric query: {1} {0} {2}".format(metric.value, metric_name, metric_unit))
        return metrics

    def set_resources(self):
        """
        Allocate the specified resources
        :param resource_dict:
        {"vnf_name1" : {"param1":value,...},
         "vnf_name2" : {"param1":value,...},
         ...
        }
        :return:
        """
        res = copy.deepcopy(self.resource_configuration)
        for vnf_name in res:
            resource_config = res[vnf_name]
            self.emu.update_vnf_resources(vnf_name, resource_config)

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


class ProfileCalculator():
    """
    This class is used to calculate a perofrmance profile out of the test results of a ped experiment
    """
    def __init__(self, experiment):
        self.experiment = experiment
        self.profile_graphs = experiment.profile_calculations # this is the profile_calculation description from the ped-file
        self.results = []
        self.resultQ = multiprocessing.Queue()

        self.enable_updating = multiprocessing.Event()
        self.plot_process = multiprocessing.Process(target=self.update_graph, args=(self.resultQ, self.enable_updating))

    def start_plot(self):
        self.plot_process.start()

    def update_results(self, result):
        self.results.append(result)
        self.resultQ.put(self.results)

    def update_graph(self, resultQ, enable_updating):

        # wait until update is needed
        enable_updating.wait()

        n = len(self.profile_graphs)

        while enable_updating.is_set():
            results = resultQ.get()
            i = 1
            plt.close('all')
            plt.subplots(nrows=n, ncols=1)
            for profile in self.profile_graphs:
                plt.subplot(n, 1, i)
                x_metric_id = profile['input_metric']
                y_metric_id = profile['output_metric']

                x_metrics = self._find_metrics(x_metric_id, results)
                x_values = [m['average'] for m in x_metrics]
                x_err_high = [m['CI_high'] - m['average'] for m in x_metrics]
                x_err_low = [abs(m['CI_low'] - m['average']) for m in x_metrics]
                x_unit = x_metrics[0]['unit']

                y_metrics = self._find_metrics(y_metric_id, results)
                y_values = [m['average'] for m in y_metrics]
                y_err_high = [m['CI_high'] - m['average'] for m in y_metrics]
                y_err_low = [abs(m['CI_low'] - m['average']) for m in y_metrics]
                y_unit = y_metrics[0]['unit']

                plt.xlabel('{0}({1})'.format(x_metric_id, x_unit))
                plt.ylabel('{0}({1})'.format(y_metric_id, y_unit))

                plt.title(profile['name'])

                plt.grid(b=True, which='both', color='lightgrey', linestyle='--')
                plt.errorbar(x_values, y_values, xerr=[x_err_low, x_err_high], yerr=[y_err_low, y_err_high], fmt='--o',
                             capsize=2)

                i += 1

            plt.tight_layout()
            plt.draw()
            plt.show(block=False)

    def finalize_graph(self, show_final=False):
        self.enable_updating.clear()
        self.plot_process.join(timeout=3)
        self.plot_process.terminate()
        # show plot window as blocking
        if show_final:
            self.display_graph()

    def display_graph(self, file=None):
        if file:
            self.results = read_yaml(file)

        plt.close("all")
        plt.ioff()
        logging.info("profile graphs:{}".format(self.profile_graphs))
        n = len(self.profile_graphs)
        plt.subplots(nrows=n, ncols=1)
        i = 1
        for profile in self.profile_graphs:
            plt.subplot(n, 1, i)
            x_metric_id = profile['input_metric']
            y_metric_id = profile['output_metric']

            x_metrics = self._find_metrics(x_metric_id, self.results)
            x_values = [m['average'] for m in x_metrics]
            x_err_high = [m['CI_high']-m['average'] for m in x_metrics]
            x_err_low = [abs(m['CI_low']-m['average']) for m in x_metrics]
            x_unit = x_metrics[0]['unit']

            y_metrics = self._find_metrics(y_metric_id, self.results)
            y_values = [m['average'] for m in y_metrics]
            y_err_high = [m['CI_high']-m['average'] for m in y_metrics]
            y_err_low = [abs(m['CI_low']-m['average']) for m in y_metrics]
            y_unit = y_metrics[0]['unit']

            plt.xlabel('{0}({1})'.format(x_metric_id,x_unit))
            plt.ylabel('{0}({1})'.format(y_metric_id, y_unit))
            plt.title(profile['name'])

            plt.grid(b=True, which='both', color='lightgrey', linestyle='--')
            plt.errorbar(x_values, y_values, xerr=[x_err_low, x_err_high], yerr=[y_err_low, y_err_high], fmt='--o', capsize=2)

            i += 1
        plt.tight_layout()
        plt.show()

    def _find_metrics(self, metric_id, results):
        """
        return all metric measurement points as found in the results
        :param metric_id:
        :return:
        """
        metric_list = []
        for result in results:
            for metric_dict in result['input_metrics']:
                if metric_dict['name'] == metric_id:
                    metric_list.append(metric_dict)
            for metric_dict in result['output_metrics']:
                if metric_dict['name'] == metric_id:
                    metric_list.append(metric_dict)

        return metric_list