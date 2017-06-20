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
from son.monitor.prometheus_lib import query_Prometheus, compute2vnfquery, network2vnfquery, test2vnfquery, \
    nsdlink_metrics, network_metrics, testvnf_metrics, compute_metrics
from subprocess import Popen
import paramiko
import shlex
import select
from time import sleep
from threading import Thread
from son.monitor.msd import msd as msd_object


import logging
LOG = logging.getLogger('son_emu_lib')
LOG.setLevel(level=logging.INFO)
#LOG.propagate = True
#logging.getLogger("requests").setLevel(logging.WARNING)

import pprint
pp = pprint.PrettyPrinter(indent=4)

import docker

"""
This class implements the son-emu commands via its REST api.
"""

class Emu():

    def __init__(self, REST_api, docker_api='local', ip='localhost', vm=False, user=None, password=None):
        self.url = REST_api
        self.docker_client = self.get_docker_api(docker_api)


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

    def get_docker_api(self, docker_api):
        if docker_api == 'local':
            # commect to local docker api
            return docker.from_env()
        else:
            # connect to remote docker pai eg. tcp://127.0.0.1:1234
            return docker.DockerClient(base_url=docker_api)

    def msd(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_msd, 'stop': self.stop_msd}
        return actions[action](**kwargs)

    # parse the msd file and export the metrics from son-emu and show in grafana
    def start_msd(self, file=None, **kwargs):
        # check if prometheus is running
        kwargs.get('monitor').start_containers()
        # initialize msd object
        msd_obj = msd_object(file, self)
        msd_obj.start()


        return 'msd metrics installed'

    def stop_msd(self, file=None, **kwargs):

        # initialize msd object
        msd_obj = msd_object(file, self)
        msd_obj.stop()

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


    def ssh_cmd(self, cmd, host='localhost', port=22, username=None, password=None):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # ssh.connect(mgmt_ip, username='steven', password='test')
        ssh.connect(host, port=port, username=username, password=password)
        LOG.info("executing command: {0}".format(cmd))
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

        # Wait for the command to terminate
        timer = 0
        while ( not stdout.channel.exit_status_ready() ) and timer < 3:
            # Only print data if there is data to read in the channel
            if stdout.channel.recv_ready():
                rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                if len(rl) > 0:
                    # Print data from stdout
                    LOG.info(stdout.channel.recv(1024).decode("utf-8"))
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
        LOG.info("executing command: {0}".format(cmd))
        process = Popen(cmd)
        #process.wait()
        return process

    def host_exec(self, cmd, action='start'):
        wait = False
        if action == "stop":
            # remove quotes from command
            # remove whole process tree
            # send SIGTERM (not SIGKILL -9)
            cmd_new = cmd.replace('"', '')
            cmd_new = "pkill -15 -f '" + cmd_new + "'"
            #cmd = "kill -TERM -- -$(pgrep -f '{cmd}')".format(cmd=cmd.replace('"',''))
            cmd_list = shlex.split(cmd_new)
            wait = True
        else:
            cmd_list = shlex.split(cmd)

        p = Popen(cmd_list)

        LOG.info('vnf: {0} executing command: {1}'.format('host', cmd_list))
        if wait:
            p.wait()
        else:
            # allow some time to start the cmd
            sleep(1)

    def docker_exec(self, cmd, vnf_name, action):

        docker_name = 'mn.' + str(vnf_name)
        container = self.docker_client.containers.get(docker_name)
        wait = False

        if action == "stop":
            # remove quotes from command
            # remove whole process tree
            # send SIGTERM (not SIGKILL -9)
            cmd_new = cmd.replace('"', '')
            cmd_new = "pkill -15 -f '" + cmd_new + "'"
            #cmd = "kill -TERM -- -$(pgrep -f '{cmd}')".format(cmd=cmd.replace('"',''))
            cmd_list = shlex.split(cmd_new)
            wait = True
        else:
            cmd_list = shlex.split(cmd)

        self.thread = Thread(target=container.exec_run,
                        kwargs=dict(cmd=cmd_list, tty=True, detach=(not wait), stdout=False, stderr=False))
        self.thread.start()

        LOG.info('vnf: {0} executing command: {1}'.format(vnf_name, cmd_list))
        if wait:
            self.thread.join()
        else:
            # allow some time to start the cmd
            sleep(1)

    def exec(self, cmd, vnf_name, action='start'):
        if vnf_name == 'host':
            self.host_exec(cmd, action)
        else:
            self.docker_exec(cmd, vnf_name, action)


    # export a network interface traffic rate counter
    def monitor_interface(self, action, vnf_name, metric, **kwargs):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(action, vnf_name, metric):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        params = create_dict(
            vnf_name=parse_vnf_name(vnf_name),
            vnf_interface=parse_vnf_interface(vnf_name),
            metric=metric,
        )

        url = "{0}/restapi/monitor/interface".format(self.url)
        response = actions[action](url, params=params)

        return response.text

    # export flow traffic counter, of a manually pre-installed flow entry, specified by its cookie
    def flow_mon(self, action, vnf_name, metric, cookie, **kwargs):
        # check required arguments
        actions = {'start': self.session.put, 'stop': self.session.delete}
        if not valid_arguments(action, vnf_name, metric, cookie):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        params = create_dict(
            vnf_name=parse_vnf_name(vnf_name),
            vnf_interface=parse_vnf_interface(vnf_name),
            metric=metric,
            cookie=cookie,
        )

        url = "{0}/restapi/monitor/flow".format(self.url)
        response = actions[action](url,params=params)

        return response.text

    # install a flow match entry in the datacenter and export the flow counters
    def flow_entry(self, action, source, destination, **args):
        # check required arguments
        actions = {'start': self.session.put, 'stop':self.session.delete}
        if not valid_arguments(source, destination):
            return "arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        params = create_dict(
            vnf_src_interface=parse_vnf_interface(source),
            vnf_dst_interface=parse_vnf_interface(destination),
            vnf_src_name=parse_vnf_name(source),
            vnf_dst_name=parse_vnf_name(destination),
            skip_vlan_tag=True,
        )
        params.update(args)

        response = actions[action]("{0}/restapi/monitor/link".format(self.url),
                    params=params)

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



        monitor_placement = None
        if 'rx' in metric:
            monitor_placement = 'rx'
        elif 'tx' in metric:
            monitor_placement = 'tx'


        params = create_dict(
            vnf_src_name=parse_vnf_name(source),
            vnf_dst_name = parse_vnf_name(destination),
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

    def query(self, vnf_name, **kwargs):

        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)
        metric = kwargs.get("metric")
        query = kwargs.get("query")
        datacenter = kwargs.get("datacenter")

        # Classify this type of metric
        metric_test = metric
        if metric[0:3] == 'tx_' or metric[0:3] == 'rx_':
            metric_test = metric[3:]

        if metric_test in testvnf_metrics:
            query = test2vnfquery[metric].query_template.format(vnf_name2)
        elif metric_test in compute_metrics:
            query = compute2vnfquery[metric].query_template.format(vnf_name2)
        elif metric_test in network_metrics:
            query = network2vnfquery[metric].query_template.format(vnf_name2, vnf_interface)
        elif not query:
            return 'metric is not suppported by the emulator, or a raw metric should be given'

        if datacenter is None:
            datacenter = self._find_dc(vnf_name2)
        dc_label = datacenter

        # Check if any replacements are needed in the raw query
        if '<uuid>' in query:
            vnf_status = get("{0}/restapi/compute/{1}/{2}".format(
                             self.url,
                             dc_label,
                             vnf_name2)).json()
            uuid = vnf_status['id']
            query = query.replace('<uuid>', uuid)

        LOG.info("query: {0} ".format(query))
        r = query_Prometheus(query)
        return r


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
            LOG.info(log_string)

            process = self._tcpdump(dc_portname, file=file, title=log_string)
            LOG.info("Close tcpdump window to stop capturing or do son-monitor dump stop")

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
            #LOG.info(xterm_cmd)
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
            cmd = ['xterm', '-xrm', 'XTerm*selectToClipboard: true', '-xrm', 'XTerm.vt100.allowTitleOps: false', '-T', vnf_name,
                   '-e', terminal_cmd]
            Popen(cmd)

        ret = 'xterms started for {0}'.format(vnf_names)
        if len(vnf_names) == 0 :
            ret = 'vnf list is empty, no xterms started'
        return ret

    def update_skewness_monitor(self, vnf_name, resource_name, action):

        actions = {'start': self.session.put, 'stop': self.session.delete}
        if not valid_arguments(action, vnf_name, resource_name):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        params = create_dict(
            vnf_name=vnf_name,
            resource_name=resource_name,
        )

        response = actions[action]("{0}/restapi/monitor/skewness".format(self.url),
                                   params=params)

        return response.text

    def update_vnf_resources(self, vnf_name, resource_dict):

        dc = self._find_dc(vnf_name)
        #LOG.info('dc name: {0} vnf: {1}, res: {2}'.format(dc, vnf_name, resource_dict))
        response = self.session.put("{url}/restapi/compute/resources/{dc}/{name}".format(
                                    url=self.url,
                                    dc=self._find_dc(vnf_name),
                                    name=vnf_name),
                                   params=resource_dict)
        return response.text

