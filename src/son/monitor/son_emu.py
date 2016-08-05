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
import son.monitor.profiler as profiler
from subprocess import Popen
import os
import sys
import pkg_resources

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


    def init(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_containers, 'stop': self.stop_containers}
        actions[action]()

    # start the sdk monitoring framework (cAdvisor, Prometheus, Pushgateway, ...)
    def start_containers(self):
        # docker-compose up -d
        cmd = [
            'docker-compose',
            'up',
            '-d'
        ]
        src_path = os.path.join('docker', 'docker-compose.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        cwd = os.path.dirname(srcfile)
        logging.info('Start son-monitor containers: {0}'.format(cwd))
        process = Popen(cmd, cwd=cwd)
        return 'done'

    # start the sdk monitoring framework
    def stop_containers(self):
        # docker-compose down
        cmd = [
            'docker-compose',
            'down'
        ]
        src_path = os.path.join('docker', 'docker-compose.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        cwd = os.path.dirname(srcfile)
        logging.info('stop and remove son-monitor containers')
        process = Popen(cmd, cwd=cwd)
        return 'done'

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
            vnf_src_interface=parse_vnf_interface(args.get("source")),
            vnf_dst_interface=parse_vnf_interface(args.get("destination")),
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
        self.flow_entry(action ,vnf_src_name, vnf_dst_name, **params)
        # then export its metrics (from the src_vnf/interface)
        self.flow_mon(action, source, metric, cookie)
        self.flow_mon(action, destination, metric, cookie)

    def query(self, vnf_name, datacenter, query,**kwargs):
        vnf_name2 = parse_vnf_name(vnf_name)
        vnf_interface = parse_vnf_interface(vnf_name)
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
