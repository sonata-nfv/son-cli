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

from requests import get, put, delete, Session
from son.monitor.utils import *
from son.monitor.prometheus_lib import query_Prometheus
from son.monitor.grafana_lib import Grafana
from  son.monitor.profiler import Emu_Profiler
from subprocess import Popen
import os
import sys
import pkg_resources
from shutil import copy, rmtree, copytree
import paramiko
import shlex
import select
from time import sleep, time, perf_counter
from threading import Thread

from son.monitor.msd import msd as msd_object

import re

import math

import logging
logging.basicConfig(level=logging.INFO)
#logging.getLogger("requests").setLevel(logging.WARNING)

import pprint
pp = pprint.PrettyPrinter(indent=4)

import docker

import numpy as np
from scipy.stats import norm, lognorm, skew, skewtest, normaltest, t, mode
import scikits.bootstrap as bootstrap
import scipy


"""
This class implements the son-emu commands via its REST api.
"""

class emu():

    def __init__(self, REST_api, docker_api='local', ip='localhost', vm=False, user=None, password=None):
        self.url = REST_api
        self.docker_client = self.get_docker_api(docker_api)
        self.tmp_dir = '/tmp/son-monitor'
        self.docker_dir = '/tmp/son-monitor/docker'
        self.prometheus_dir = '/tmp/son-monitor/prometheus'
        self.grafana_dir = '/tmp/son-monitor/grafana'
        for dir in [self.docker_dir, self.prometheus_dir, self.grafana_dir]:
            if not os.path.exists(dir):
                # make local working directory
                os.makedirs(dir)

        self.docker_based = os.getenv('SON_CLI_IN_DOCKER', False)

        # remote son-emu parameters
        self.son_emu_ip = ip
        self.emu_in_vm = vm
        self.ssh_user = user
        self.ssh_password = password


        self.grafana = None

        # Build up our session
        self.session = Session()
        self.session.headers = {
            "Accept": "application/json; charset=UTF-8"
        }

    def init(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_containers, 'stop': self.stop_containers}
        return actions[action](**kwargs)

    def get_docker_api(self, docker_api):
        if docker_api == 'local':
            # commect to local docker api
            return docker.from_env()
        else:
            # connect to remote docker pai eg. tcp://127.0.0.1:1234
            return docker.Client(base_url='docker_api')

    def msd(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_msd, 'stop': self.stop_msd}
        return actions[action](**kwargs)

    # parse the msd file and export the metrics from son-emu and show in grafana
    def start_msd(self, filepath=None, **kwargs):

        # also start son-monitor containers
        self.start_containers()

        # initialize msd object
        msd_obj = msd_object(filepath, self)
        msd_obj.start()

        # Parse the msd file
        #logging.info('parsing msd: {0}'.format(filepath))
        #msd = load_yaml(filepath)

        # initialize a new Grafana dashboard
        #self.grafana = Grafana()
        #dashboard_name = msd['dashboard']
        #self.grafana.init_dashboard(title=dashboard_name)

        # Install the vnf metrics
        #self.install_vnf_metrics(msd, dashboard_name)

        # install the link metrics
        #first make sure everything is stopped
        #self.install_nsd_links(msd, 'stop', dashboard_name)
        #self.install_nsd_links(msd, 'start', dashboard_name)

        # execute the SAP commands
        # first make sure everything is stopped
        #self.install_sap_commands(msd, "stop")
        #self.install_sap_commands(msd, "start")

        return 'msd metrics installed'

    def stop_msd(self, file=None, **kwargs):

        # initialize msd object
        msd_obj = msd_object(file, self)
        msd_obj.stop()

        logging.info('parsing msd: {0}'.format(file))
        msd = load_yaml(file)

        # clear the dashboard
        #self.grafana = Grafana()
        #dashboard_name = msd['dashboard']
        #self.grafana.del_dashboard(title=dashboard_name)

        # delete all installed flow_metrics
        #self.install_nsd_links(msd, 'stop', dashboard_name)

        # kill all the SAP commands
        self.install_sap_commands(msd, "stop")

        sleep(3)
        # also stop son-monitor containers
        self.stop_containers()

        return 'msd metrics deleted'

    # start or stop (kill) the sap commands
    def install_sap_commands(self, msd, action):
        # execute the SAP commands
        for sap in msd.get('saps', []):
            sap_docker_name = 'mn.' + sap['sap_name']
            wait =  sap.get('wait', False)
            for cmd in sap['commands']:
                if sap['method'] == 'son-emu-VM-ssh':
                    if action == "stop":
                        cmd = 'sudo docker exec -it ' + sap_docker_name + " pkill -9 -f '" + cmd + "'"
                        wait = True
                    else:
                        cmd = 'sudo docker exec -it ' + sap_docker_name + ' ' + cmd

                    thread = Thread(target=self.ssh_cmd, kwargs=dict(cmd=cmd, username=self.ssh_user, password=self.ssh_password))
                    thread.start()
                    if wait:
                        thread.join()
                    #process = self.ssh_cmd(cmd, username='steven', password='test', wait=wait)
                elif sap['method'] == 'son-emu-local':
                    process = self.docker_exec_cmd(cmd, sap_docker_name)

    # start the sdk monitoring framework (cAdvisor, Prometheus, Pushgateway, ...)
    def start_containers(self, **kwargs):
        # docker-compose up -d
        cmd = [
            'docker-compose',
            '-p sonmonitor',
            'up',
            '-d'
        ]

        if self.docker_based:
            # we are running son-cli in a docker container
            logging.info('son-cli is running inside a docker container')
            src_path = os.path.join('docker_compose_files', 'docker-compose-docker.yml')
        else:
            # we are running son-cli locally
            src_path = os.path.join('docker_compose_files', 'docker-compose-local.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        # copy the docker compose file to a working directory
        copy(srcfile, os.path.join(self.docker_dir, 'docker-compose.yml'))

        # copy the prometheus config file for use in the prometheus docker container
        src_path = os.path.join('prometheus', 'prometheus_sdk.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        copy(srcfile, self.prometheus_dir)

        # copy grafana directory
        src_path = os.path.join('grafana', 'grafana.db')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        copy(srcfile, self.grafana_dir)

        logging.info('Start son-monitor containers: {0}'.format(self.docker_dir))
        process = Popen(cmd, cwd=self.docker_dir)
        process.wait()

        # Wait a while for containers to be completely started
        sleep(4)
        return 'son-monitor started'

    # start the sdk monitoring framework
    def stop_containers(self, **kwargs):
        '''
        # hard stopping of containers
        cmd = [
            'docker',
            'rm',
            '-f',
            'grafana',
            'prometheus'
        ]
        logging.info('stop and remove son-monitor containers')
        process = Popen(cmd, cwd=self.docker_dir)
        process.wait()
        '''
        # docker-compose down, remove volumes
        cmd = [
            'docker-compose',
            '-p sonmonitor',
            'down',
            '-v'
        ]
        logging.info('stop and remove son-monitor containers')
        process = Popen(cmd, cwd=self.docker_dir)
        process.wait()
        #try to remove tmp directory
        try:
            if os.path.exists(self.tmp_dir):
                rmtree(self.tmp_dir)
        except:
            logging.info('cannot remove {0} (this is normal if mounted as a volume)'.format(self.tmp_dir))

        return 'son-monitor stopped'

    def ssh_cmd(self, cmd, host='localhost', port=22, username=None, password=None):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # ssh.connect(mgmt_ip, username='steven', password='test')
        ssh.connect(host, port=port, username=username, password=password)
        logging.info("executing command: {0}".format(cmd))
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

        # Wait for the command to terminate
        timer = 0
        while ( not stdout.channel.exit_status_ready() ) and timer < 3:
            # Only print data if there is data to read in the channel
            if stdout.channel.recv_ready():
                rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                if len(rl) > 0:
                    # Print data from stdout
                    logging.info(stdout.channel.recv(1024).decode("utf-8"))
                    timer = 0
            else:
                timer += 1
                sleep(1)

        ssh.close()

    def docker_exec_cmd(self, cmd, docker_name):
        cmd_list = shlex.split(cmd)
        cmd = [
            'docker',
            'exec',
            '-it',
            docker_name
        ]
        cmd = cmd + cmd_list
        logging.info("executing command: {0}".format(cmd))
        process = Popen(cmd)
        #process.wait()
        return process

    def docker_exec(self, cmd, vnf_name, action='start'):

        docker_name = 'mn.' + str(vnf_name)
        container = self.docker_client.get(docker_name)
        wait = False

        if action == "stop":
            cmd = " pkill -9 -f '" + cmd + "'"
            cmd_list = shlex.split(cmd)
            wait = True
        else:
            cmd_list = shlex.split(cmd)

        thread = Thread(target=container.exec_run, kwargs=dict(cmd=cmd_list, tty=True, detach=wait))
        thread.start()
        if wait:
            thread.join()


    # export a network interface traffic rate counter
    def monitor_interface(self, action, vnf_name, metric, **kwargs):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(action, vnf_name, metric):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)

        url = construct_url(self.url, 'restapi/monitor/interface',
                            vnf_name2, vnf_interface, metric)

        response = actions[action](url)
        return response.json()

    # export flow traffic counter, of a manually pre-installed flow entry, specified by its cookie
    def flow_mon(self, action, vnf_name, metric, cookie, **kwargs):
        # check required arguments
        actions = {'start': self.session.put, 'stop': self.session.delete}
        if not valid_arguments(action, vnf_name, metric, cookie):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)

        url = construct_url(self.url, 'restapi/monitor/flow',
                            vnf_name2, vnf_interface, metric, cookie)

        response = actions[action](url)

        return response.json()

    # install a flow match entry in the datacenter and export the flow counters
    def flow_entry(self, action, source, destination, **args):
        # check required arguments
        actions = {'start': self.session.put, 'stop':self.session.delete}
        if not valid_arguments(source, destination):
            return "arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_src_name = parse_vnf_name(source)
        vnf_dst_name = parse_vnf_name(destination)

        params = create_dict(
            vnf_src_interface=parse_vnf_interface(source),
            vnf_dst_interface=parse_vnf_interface(destination),
            skip_vlan_tag=True,
        )
        params.update(args)
            # weight=args.get("weight"),
            # match=args.get("match"),
            # bidirectional=args.get("bidirectional"),
            # priority=args.get("priority"),
            # cookie=args.get("cookie"),
            # skip_vlan_tag=True,
            # monitor=args.get("monitor"),
            # monitor_placement=args.get("monitor_placement"),
            # metric=args.get("metric"))

        response = actions[action]("{0}/restapi/monitor/link/{1}/{2}".format(
                    self.url,
                    vnf_src_name,
                    vnf_dst_name),
                    json=params)

        return response.text

    # install monitoring of a specific flow on a pre-existing link in the service.
    # the traffic counters of the newly installed monitor flow are exported
    def flow_total(self, action, source, destination, metric, cookie, **kwargs):
        # check required arguments
        actions = {'start': self.session.put, 'stop': self.session.delete}
        if not valid_arguments(source, destination, cookie):
            return "arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_src_name = parse_vnf_name(source)
        vnf_dst_name = parse_vnf_name(destination)

        monitor_placement = None
        if 'rx' in metric:
            monitor_placement = 'rx'
        elif 'tx' in metric:
            monitor_placement = 'tx'


        params = create_dict(
            vnf_src_interface=parse_vnf_interface(source),
            vnf_dst_interface=parse_vnf_interface(destination),
            weight=kwargs.get("weight"),
            match=kwargs.get("match"),
            bidirectional=kwargs.get("bidirectional"),
            priority=kwargs.get("priority"),
            cookie=cookie,
            skip_vlan_tag=True,
            monitor=True,
            monitor_placement=monitor_placement,
            metric=metric)

        # first add this specific flow to the emulator network
        ret1 = self.flow_entry(action ,source, destination, **params)
        return_value = "flow-entry:\n{0}".format(ret1)
        return return_value

    def query(self, vnf_name, query, datacenter=None, **kwargs):
        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)

        if datacenter is None:
            datacenter = self._find_dc(vnf_name2)
        dc_label = datacenter
        query = query
        vnf_status = get("{0}/restapi/compute/{1}/{2}".format(
                         self.url,
                         dc_label,
                         vnf_name2)).json()
        uuid = vnf_status['id']
        query = query.replace('<uuid>', uuid)

        r = query_Prometheus(query)
        return r

    def profile(self, args):

        return 'not yet fully implemented'

        nw_list = list()
        if args.get("network") is not None:
            nw_list = parse_network(args.get("network"))

        params = create_dict(
            network=nw_list,
            command=args.get("docker_command"),
            image=args.get("image"),
            input=args.get("input"),
            output=args.get("output"))

        profiler_emu = Emu_Profiler(self.url)

        # deploy the test service chain
        vnf_name = parse_vnf_name(args.get("vnf_name"))
        dc_label = args.get("datacenter")
        profiler_emu.deploy_chain(dc_label, vnf_name, params)

        # generate output table
        for output in profiler_emu.generate():
            print(output + '\n')

    def _find_dc(self, vnf_name):
        datacenter = None
        vnf_list = get("{0}/restapi/compute".format(self.url)).json()
        for vnf in vnf_list:
            if vnf[0] == vnf_name:
                datacenter = vnf[1]['datacenter']
        return datacenter

    def _find_dc_interface(self, vnf_name, vnf_interface):
        datacenter = None
        vnf_list = get("{0}/restapi/compute".format(self.url)).json()
        network = []
        dc_portname = None
        for vnf in vnf_list:
            if vnf[0] == vnf_name:
                network = vnf[1]['network']
                break
        for intf_dict in network:
            if intf_dict['intf_name'] == vnf_interface:
                dc_portname = intf_dict['dc_portname']
                break
        return dc_portname

    # find the public ip address where we can log into the node
    def _find_public_ip(self, vnf_name):
        dc_label = self._find_dc(vnf_name)
        vnf_status = get("{0}/restapi/compute/{1}/{2}".format(self.url, dc_label, vnf_name)).json()
        return vnf_status['docker_network']

    # find parameter the docker status output
    def _find_vnf_status_parameter(self, vnf_name, param):
        dc_label = self._find_dc(vnf_name)
        vnf_status = get("{0}/restapi/compute/{1}/{2}".format(self.url, dc_label, vnf_name)).json()
        return vnf_status[param]

    # start tcpdump for this interface
    def dump(self, action, vnf_name, file, **kwargs):

        if action == 'stop':
            #kill tcpdump
            Popen(['pkill', '-9', 'tcpdump'])
            return 'tcpdump stopped'

        elif action == 'start':
            vnf_name2 = parse_vnf_name(vnf_name)
            vnf_interface = parse_vnf_interface(vnf_name)
            dc_portname = self._find_dc_interface(vnf_name2, vnf_interface)
            log_string = "dump {0} at {1}".format(vnf_name, dc_portname)
            logging.info(log_string)

            process = self._tcpdump(dc_portname, file=file, title=log_string)
            logging.info("Close tcpdump window to stop capturing or do son-monitor dump stop")

            return 'tcpdump started'

    def _tcpdump(self, interface, file=None, options='', title='tcpdump'):

        tcpdump_cmd = "tcpdump -i {0} ".format(interface) + options
        #wireshark can also be started with -i option

        pcap_option = ' '
        if file:
            # start tcpdump in background
            pcap_option = ' -w {0} -U'.format(file)
            tcpdump_cmd = tcpdump_cmd + pcap_option
            return Popen(shlex.split(tcpdump_cmd))
        else:
            #start tcpdump in xterm
            xterm_cmd = "xterm -xrm 'XTerm.vt100.allowTitleOps: false' -T {0} -hold -e {1}".format("'"+title+"'", tcpdump_cmd)
            #logging.info(xterm_cmd)
            return Popen(shlex.split(xterm_cmd))

    # start an xterm for the specfified vnfs
    def xterm(self, vnf_names, **kwargs):
        # start xterm for all vnfs
        if len(vnf_names) == 0:
            vnf_list = get("{0}/restapi/compute".format(self.url)).json()
            vnf_names = [vnf[0] for vnf in vnf_list]

        for vnf_name in vnf_names:
            terminal_cmd = "docker exec -it mn.{0} /bin/bash".format(vnf_name)
            if self.emu_in_vm:
                terminal_cmd = "./ssh_login.exp {0} {1} {2} '{3}'".format(self.son_emu_ip, self.ssh_user,
                                                                       self.ssh_password, terminal_cmd)
            cmd = ['xterm', '-xrm', 'XTerm.vt100.allowTitleOps: false', '-T', vnf_name,
                   '-e', terminal_cmd]
            Popen(cmd)

        return 'xterms started for {0}'.format(vnf_names)

    # execute a command in a VNF
    def exec(self, vnf_name, docker_command, action, loop=False):
        sap = {}
        sap['sap_name'] = vnf_name
        sap['method'] = 'son-emu-VM-ssh'
        sap['wait'] = True
        sap['commands'] = []
        p = re.compile("{(.*)}M")
        m = p.search(docker_command)
        arg_list = m.group(1).split(',')

        #construct commands

        msd = {'saps':[sap]}
        #execute commands
        self.install_sap_commands(self, msd, action)

    # get statistics with certain frequency and export in file for further analysis
    def stats(self, vnf_name, **kwargs):
        docker_id = self._find_vnf_status_parameter(vnf_name, 'id')
        proc_file = '/sys/fs/cgroup/cpuacct/docker/{0}/cpuacct.usage'.format(docker_id)

        cpu_count0 = 0
        time0 = 0

        #out_file = '/home/steven/Documents/out.txt'
        #output = open(out_file, 'w')

        #milliseconds
        stat_delta = 10
        sample_T = 2000

        data = []
        n = 0

        fp = open(proc_file)

        moment1 = 0
        moment2 = 0
        moment3 = 0


        while True:
            #collect samples
            for n in range(0,round(sample_T/stat_delta)):
                # first measurement
                if cpu_count0 <= 0 or time0 <= 0:
                    #time0 = int(round(time() * 1000))
                    time0 = perf_counter()
                    #cpu_count0=int(open(proc_file).readline())
                    cpu_count0 = int(fp.read().strip())
                    fp.seek(0)
                    sleep(stat_delta/1000)
                    continue


                #time1 = int(round(time() * 1000))
                #perf_counter in seconds
                time1 = perf_counter()

                # cpu count in nanoseconds
                #cpu_count1 = int(open(proc_file).readline())
                cpu_count1 = int(fp.read().strip())
                fp.seek(0)

                cpu_delta = cpu_count1 - cpu_count0
                cpu_count0 = cpu_count1

                time_delta = time1 - time0
                time0 = time1

                #metric = (cpu_delta / (time_delta * 1e6))
                #work in nanoseconds
                metric = (cpu_delta / (time_delta * 1e9))

                #logging.info("cpu delta: {0}, time delta: {1}".format(cpu_delta, time_delta))
                #output.write(str(int(round(cpu_delta)))+'\n')
                #output.write(str(int(round(cpu_delta*(stat_delta/time_delta)))) + '\n')
                #output.write(str((cpu_delta / (time_delta*1e6))) + '\n')

                data.append(metric)
                #n += 1

                #running calculation of sample moments
                moment1 += metric
                temp = metric * metric
                moment2 += temp
                moment3 += temp * metric


                sleep(stat_delta/1000)


            # calc skew:
            M1 = (1 / n) * moment1
            M2 = ((1 / n) * moment2) - M1**2
            M3 = ((1 / n) * moment3) - (3 * M1 * ((1 / n) * moment2)) + (2 * M1**3)

            s2 = (math.sqrt(n*(n - 1))/(n - 2)) * (M3 / (M2)**1.5)

            # calc metrics:
            #s = skew(data)
            #mean = np.mean((data))
            #median = np.median((data))
            #logging.info("skew: {0:.2f}".format(s))
            logging.info("skew2: {0:.2f}".format(s2))
            #logging.info("skew2: {0:.2f}".format((mean - median)))
            #logging.info("mean: {0:.3f}".format(mean))
            #logging.info("median: {0:.3f}".format(median))


            #logging.info("\n\n")
            N = len(data)
            #print("num samples: {0}".format(N))

            #mu = mean
            #me = median
            #sigma = np.std(data)
            #interval = norm.interval(0.99, loc=mu, scale=sigma / np.sqrt(N))
            #R = t.interval(0.99, N - 1, loc=mu, scale=sigma / np.sqrt(N))

            #print("mean: {0}".format(mu))
            #print("median: {0}".format(me))
            #print("interval (%): {0}".format(1 - interval / mu))
            #print("interval: {0}".format(interval))
            #print("interval T (%): {0}".format(1 - R / mu))
            #print("interval T: {0}".format(R))

            logging.info("\n")

            # compute 95% confidence intervals around the mean
            #CIs = bootstrap.ci(data=data, statfunction=scipy.median, n_samples=30000)

            #logging.info("Bootstrapped 95% confidence intervals\nLow:{0}\nHigh:{1}".format(CIs[0], CIs[1]))
            #logging.info(CIs[0] / median)
            #logging.info(CIs[1] / median)
            #logging.info("\n\n")

            #write to file
            #out_file = '/home/steven/Documents/out.txt'
            #output = open(out_file, 'w')
            #for metric in data:
            #    output.write(str(metric) + '\n')
            #output.close()

            # reset metrics array
            data = []
            time0 = 0
            cpu_count0 = 0

            moment1 = 0
            moment2 = 0
            moment3 = 0

            #sleep(1)



