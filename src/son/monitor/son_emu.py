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

from requests import get, put, delete
from son.monitor.utils import *
from son.monitor.prometheus import query_Prometheus, metric2total_query, metric2flowquery, metric2totalflowquery, metric2vnfquery
from son.monitor.grafana_lib import Grafana
import son.monitor.profiler as profiler
from subprocess import Popen
import os
import sys
import pkg_resources
from shutil import copy, rmtree, copytree
import paramiko
import shlex
import select

import logging
logging.basicConfig(level=logging.INFO)

import pprint
pp = pprint.PrettyPrinter(indent=4)

"""
This class implements the son-emu commands via its REST api.
"""

COOKIE_START = 100

metric2flow_metric = {
    "rx_packet_count": "rx_packets",
    "tx_packet_count": "tx_packets",
    "rx_byte_count": "tx_bytes",
    "tx_byte_count": "tx_bytes",
}

class emu():

    def __init__(self, REST_api):
        self.url = REST_api
        self.tmp_dir = '/tmp/son-monitor'
        self.docker_dir = '/tmp/son-monitor/docker'
        self.prometheus_dir = '/tmp/son-monitor/prometheus'
        self.grafana_dir = '/tmp/son-monitor/grafana'
        for dir in [self.docker_dir, self.prometheus_dir, self.grafana_dir]:
            if not os.path.exists(dir):
                # make local working directory
                os.makedirs(dir)

        self.docker_based = os.getenv('SON_CLI_IN_DOCKER', False)

        self.grafana = None


    def init(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_containers, 'stop': self.stop_containers}
        return actions[action](**kwargs)

    def nsd(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_nsd, 'stop': self.stop_nsd}
        return actions[action](**kwargs)

    def msd(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_msd, 'stop': self.stop_msd}
        return actions[action](**kwargs)

    # parse the nsd file and install the grafana metrics
    def start_nsd(self, file=None, **kwargs):
        self.grafana = Grafana()
        self.grafana.init_dashboard()
        self.grafana.parse_nsd(file)

        return 'nsd metrics installed'

    def stop_nsd(self, **kwargs):
        self.grafana.init_dashboard()

    # parse the msd file and export the metrics ffrom son-emu and show in grafana
    def start_msd(self, file=None, **kwargs):

        # Parse the msd file
        logging.info('parsing msd: {0}'.format(file))
        msd = load_yaml(file)

        # initialize a new Grafana dashboard
        self.grafana = Grafana()
        dashboard_name = msd['dashboard']
        self.grafana.init_dashboard(title=dashboard_name)

        # Install the defined vnf metrics
        vnf_metrics = msd['vnf_metrics']
        for metric_group in vnf_metrics:
            graph_list = []
            if metric_group['vnf_ids'] is None:
                # no vnfs need to be monitored
                break
            title = metric_group['desc']
            for vnf_id in metric_group['vnf_ids']:
                graph_dict = {}
                metric_type = metric_group['type']
                if metric_type not in metric2vnfquery:
                    logging.info("No query found for metric type: {0}".format(metric_type))
                    break
                query = metric2vnfquery[metric_type].format(vnf_id)
                graph_dict = dict(desc=vnf_id, metric=query)
                graph_list.append(graph_dict)

            self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=dashboard_name)

        # install the link metrics
        cookie = COOKIE_START
        for nsd_link in msd['nsd_links']:
            graph_list = []
            if nsd_link['metrics'] is None:
                # no vnfs need to be monitored
                break
            title = nsd_link['desc']
            metric_type = nsd_link['metric_type']
            source = nsd_link['source']
            destination = nsd_link['destination']
            if 'rx' in metric_type:
                vnf_name = parse_vnf_name(destination)
                vnf_interface = parse_vnf_interface(destination)
            elif 'tx' in metric_type:
                vnf_name = parse_vnf_name(source)
                vnf_interface = parse_vnf_interface(source)

            for metric in nsd_link['metrics']:
                graph_dict = {}

                if metric['type'] == "total":
                    query = metric2total_query[metric_type].format(
                        vnf_name, vnf_interface)
                    graph_dict = dict(desc=metric['desc'], metric=query)
                elif metric['type'] == "flow_total":
                    flow_metric = metric2flow_metric[metric_type]
                    self.interface('start', vnf_name + ':' + vnf_interface, flow_metric)
                    query = metric2totalflowquery[metric_type].format(vnf_name, vnf_interface)
                    graph_dict = dict(desc=metric['desc'], metric=query)
                elif metric['type'] == "flow":
                    flow_metric = metric2flow_metric[metric_type]
                    source = nsd_link['source']
                    destination = nsd_link['destination']
                    match = metric['match']
                    #install the flow and export the metric
                    self.flow_total('start', source, destination, flow_metric, cookie, match=match, bidirectional=False, priority=100)
                    query = metric2flowquery[metric_type].format(cookie, vnf_name, vnf_interface)
                    graph_dict = dict(desc=metric['desc'], metric=query)
                    cookie += 1

                graph_list.append(graph_dict)

            self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=dashboard_name, graph_type='bars')

        # execute the SAP commands
        for sap in msd['saps']:
            sap_docker_name = 'mn.' + sap['sap_name']
            for cmd in sap['commands']:
                if sap['method'] == 'son-emu-VM-ssh':
                    cmd = 'sudo docker exec -it ' + sap_docker_name + ' ' + cmd
                    process = self.ssh_cmd(cmd, username='steven', password='test')
                elif sap['method'] == 'son-emu-local':
                    process = self.docker_exec_cmd(cmd, sap_docker_name)

        return 'msd metrics installed'

    def stop_msd(self, file=None, **kwargs):
        logging.info('parsing msd: {0}'.format(file))
        msd = load_yaml(file)

        # clear the dashboard
        self.grafana = Grafana()
        dashboard_name = msd['dashboard']
        self.grafana.del_dashboard(title=dashboard_name)

        # delete all installed flow_metrics
        cookie = COOKIE_START
        for nsd_link in msd['nsd_links']:
            graph_list = []
            if nsd_link['metrics'] is None:
                # no vnfs need to be monitored
                break
            title = nsd_link['desc']
            metric_type = nsd_link['metric_type']
            source = nsd_link['source']
            destination = nsd_link['destination']
            if 'rx' in metric_type:
                vnf_name = parse_vnf_name(destination)
                vnf_interface = parse_vnf_interface(destination)
            elif 'tx' in metric_type:
                vnf_name = parse_vnf_name(source)
                vnf_interface = parse_vnf_interface(source)

            # delete the flows, identified by their cookie
            for metric in nsd_link['metrics']:
                if metric['type'] == "flow_total":
                    flow_metric = metric2flow_metric[metric_type]
                    self.interface('stop', vnf_name + ':' + vnf_interface, flow_metric)
                elif metric['type'] == "flow":
                    flow_metric = metric2flow_metric[metric_type]
                    source = nsd_link['source']
                    destination = nsd_link['destination']
                    # install the flow and export the metric
                    self.flow_total('stop', source, destination, flow_metric, cookie)
                    cookie += 1

        # kill all the SAP commands
        for sap in msd['saps']:
            sap_docker_name = 'mn.' + sap['sap_name']
            for cmd in sap['commands']:
                if sap['method'] == 'son-emu-VM-ssh':
                    cmd = 'sudo docker exec -it ' + sap_docker_name + " pkill '" + cmd + "'"
                    process = self.ssh_cmd(cmd, username='steven', password='test')
                elif sap['method'] == 'son-emu-local':
                    cmd = "pkill '" + cmd + "'"
                    process = self.docker_exec_cmd(cmd, sap_docker_name)

        return 'msd metrics deleted'

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
            src_path = os.path.join('docker', 'docker-compose-docker.yml')
        else:
            # we are running son-cli locally
            src_path = os.path.join('docker', 'docker-compose-local.yml')
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

        return 'son-monitor started'

    # start the sdk monitoring framework
    def stop_containers(self, **kwargs):
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

    def ssh_cmd(self, cmd, host='localhost', port=22, username='vagrant', password='vagrant'):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # ssh.connect(mgmt_ip, username='steven', password='test')
        ssh.connect(host, port=port, username=username, password=password)
        logging.info("executing command: {0}".format(cmd))
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

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


    def interface(self, action, vnf_name, metric, **kwargs):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(action, vnf_name, metric):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)

        url = construct_url(self.url, 'restapi/monitor',
                            vnf_name2, vnf_interface, metric)

        response = actions[action](url)
        return response.json()

    def flow_mon(self, action, vnf_name, metric, cookie, **kwargs):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(action, vnf_name, metric, cookie):
            return "Function arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)

        url = construct_url(self.url, 'restapi/flowmon',
                            vnf_name2, vnf_interface, metric, cookie)

        response = actions[action](url)

        return response.json()

    def flow_entry(self, action, source, destination, **args):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(source, destination):
            return "arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_src_name = parse_vnf_name(source)
        vnf_dst_name = parse_vnf_name(destination)

        params = create_dict(
            vnf_src_interface=parse_vnf_interface(source),
            vnf_dst_interface=parse_vnf_interface(destination),
            weight=args.get("weight"),
            match=args.get("match"),
            bidirectional=args.get("bidirectional"),
            priority=args.get("priority"),
            cookie=args.get("cookie"))

        response = actions[action]("{0}/restapi/network/{1}/{2}".format(
                    self.url,
                    vnf_src_name,
                    vnf_dst_name),
                    json=params)

        return response.json()

    def flow_total(self, action, source, destination, metric, cookie, **kwargs):
        # check required arguments
        actions = {'start': put, 'stop': delete}
        if not valid_arguments(source, destination, cookie):
            return "arguments not valid"
        if actions.get(action) is None:
            return "Action argument not valid"

        vnf_src_name = parse_vnf_name(source)
        vnf_dst_name = parse_vnf_name(destination)

        params = create_dict(
            vnf_src_interface=parse_vnf_interface(source),
            vnf_dst_interface=parse_vnf_interface(destination),
            weight=kwargs.get("weight"),
            match=kwargs.get("match"),
            bidirectional=kwargs.get("bidirectional"),
            priority=kwargs.get("priority"),
            cookie=cookie)

        # first add this specific flow to the emulator network
        ret1 = self.flow_entry(action ,source, destination, **params)
        # then export its metrics (from the src and dst vnf_interface)
        if kwargs.get("bidirectional") == True:
            ret3 = self.flow_mon(action, destination, metric, cookie)
            ret2 = self.flow_mon(action, source, metric, cookie)

        elif 'rx' in metric:
            ret3 = self.flow_mon(action, destination, metric, cookie)
            ret2 = ''

        elif 'tx' in metric:
            ret2 = self.flow_mon(action, source, metric, cookie)
            ret3 = ''

        return_value = "flow-entry:\n{0} \nflow-mon src:\n{1} \nflow-mon dst:\n{2}".format(ret1, ret2, ret3)
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

        profiler_emu = profiler.Emu_Profiler(self.url)

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

    # find the public ip address where we can log into the node
    def _find_public_ip(self, vnf_name):
        dc_label = self._find_dc(vnf_name)
        vnf_status = get("{0}/restapi/compute/{1}/{2}".format(self.url, dc_label, vnf_name)).json()
        return vnf_status['docker_network']
