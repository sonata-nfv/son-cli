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
from son.monitor.prometheus import query_Prometheus
from son.monitor.grafana_lib import Grafana
import son.monitor.profiler as profiler
from subprocess import Popen
import os
import sys
import pkg_resources
from shutil import copy, rmtree, copytree

import logging
logging.basicConfig(level=logging.INFO)

import pprint
pp = pprint.PrettyPrinter(indent=4)

"""
This class implements the son-emu commands via its REST api.
"""


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

    # parse the nsd file and install the grafana metrics
    def start_nsd(self, file=None, **kwargs):
        self.grafana = Grafana()
        self.grafana.init_dashboard()
        self.grafana.parse_nsd(file)

        return 'nsd metrics installed'

    def stop_nsd(self, **kwargs):
        self.grafana.init_dashboard()


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
        # then export its metrics (from the src_vnf/interface)
        ret2 = self.flow_mon(action, source, metric, cookie)
        ret3 = self.flow_mon(action, destination, metric, cookie)
        # show the metric in grafana
        self.grafana = Grafana()
        grafana_dict = {'tx_packets':'sonemu_tx_count_packets',
                        'rx_packets':'sonemu_rx_count_packets',
                        'tx_bytes':'sonemu_tx_count_bytes',
                        'rx_bytes': 'sonemu_rx_count_bytes'
                        }
        query1 = "{0}{{flow_id=\"{1}\",vnf_name=\"{2}\"}}".format(grafana_dict[metric], cookie, vnf_src_name)
        legend1 = "{0}-cookie:{2} ({1}:{3})".format(metric, vnf_src_name, cookie, parse_vnf_interface(source))
        query2 = "{0}{{flow_id=\"{1}\",vnf_name=\"{2}\"}}".format(grafana_dict[metric], cookie, vnf_dst_name)
        legend2 = "{0}-cookie:{2} ({1}:{3})".format(metric, vnf_dst_name, cookie, parse_vnf_interface(destination))
        ret4 = self.grafana.add_panel([dict(desc=legend1, metric=query1), dict(desc=legend2, metric=query2)])

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