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
son-monitor features available by cli

In current implementation, the son-monitor commands connects either to:
1) the SDK emulator (son-emu)
    supported functions:
        - query monitored data via Prometheus API
        - add a (temporarily) monitor metric to the son-emu monitor framework:
            - ryu metrics
            - custom metrics exported by a dedicated agent
        - perform a profiling action and return a profiling table

or

2) the SP Monitor Manager:
    supported functions:
        - query monitored data via Prometheus API
        - generate a profiling table for a vnf

(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>
"""

import argparse

from son.monitor.son_emu import Emu
from son.monitor.son_sp import sp

import pprint
pp = pprint.PrettyPrinter(indent=4)

import logging
logging.basicConfig(level=logging.INFO)

import docker
from subprocess import Popen
import os
import pkg_resources
from shutil import copy, rmtree
from time import sleep

## parameters for the emulator VIM
# TODO: these settings come from the deployed topology in the emulator, read from centralized config file?
# API from docker container
SON_EMU_IP = '172.17.0.1'
SON_EMU_REST_API_PORT = 5001
SON_EMU_API = "http://{0}:{1}".format(SON_EMU_IP, SON_EMU_REST_API_PORT)
# API when docker network=host in son-cli, or when not started as container
#SON_EMU_API = "http://localhost:5001"
# API when started with docker-compose
#SON_EMU_API = "http://son-emu:5001"

# specify if son-emu is runnign in a seperate VM that has ssh login
SON_EMU_IN_VM = False
SON_EMU_USER = 'steven' # 'vagrant'
SONE_EMU_PASSW = 'test' # 'vagrant'

# initalize the vims accessible from the SDK
emu = Emu(SON_EMU_API, ip= SON_EMU_IP, vm=SON_EMU_IN_VM, user=SON_EMU_USER, password=SONE_EMU_PASSW)

# tmp directories that will be mounted in the Prometheus and Grafana Docker containers by son-emu
tmp_dir = '/tmp/son-monitor'
docker_dir = '/tmp/son-monitor/docker'
prometheus_dir = '/tmp/son-monitor/prometheus'
grafana_dir = '/tmp/son-monitor/grafana'

class sonmonitor():

    def __init__(self):

        for dir in [docker_dir, prometheus_dir, grafana_dir]:
            if not os.path.exists(dir):
                # make local working directory
                os.makedirs(dir)

        # status of son-monitor
        self.started = False

    def init(self, action, **kwargs):
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_containers, 'stop': self.stop_containers}
        return actions[action](**kwargs)

    # start the sdk monitoring framework (cAdvisor, Prometheus, Pushgateway, ...)
    def start_containers(self, **kwargs):
        # docker-compose up -d
        cmd = [
            'docker-compose',
            '-p sonmonitor',
            'up',
            '-d'
        ]

        docker_cli = docker.from_env()
        # check if containers are already running
        c1 = docker_cli.containers.list(filters={'status': 'running', 'name': 'prometheus'})
        if len(c1) >= 1:
            logging.info('prometheus is already running')
        c2 = docker_cli.containers.list(filters={'status': 'running', 'name': 'grafana'})
        if len(c2) >= 1:
            logging.info('grafana is already running')
        if len(c1 + c2) > 0:
            return 'son-monitor not started'

        docker_based = os.getenv('SON_CLI_IN_DOCKER', False)
        if docker_based:
            # we are running son-cli in a docker container
            logging.info('son-cli is running inside a docker container')
            src_path = os.path.join('docker_compose_files', 'docker-compose-docker.yml')
        else:
            # we are running son-cli locally
            src_path = os.path.join('docker_compose_files', 'docker-compose-local.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        # copy the docker compose file to a working directory
        copy(srcfile, os.path.join(docker_dir, 'docker-compose.yml'))

        # copy the prometheus config file for use in the prometheus docker container
        src_path = os.path.join('prometheus', 'prometheus_sdk.yml')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        copy(srcfile, prometheus_dir)

        # copy grafana directory
        src_path = os.path.join('grafana', 'grafana.db')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        copy(srcfile, grafana_dir)

        logging.info('Start son-monitor containers: {0}'.format(docker_dir))
        process = Popen(cmd, cwd=docker_dir)
        process.wait()

        # Wait a while for containers to be completely started
        self.started = False
        wait_time = 0
        while not self.started:
            list1 = emu.docker_client.containers.list(filters={'status':'running', 'name':'prometheus'})
            list2 = emu.docker_client.containers.list(filters={'status': 'running', 'name': 'grafana'})
            if len(list1+list2) >= 2:
                self.started = True
                sleep(3)
            if wait_time > 5:
                return 'son-monitor not started'
            sleep(1)
            wait_time += 1


        return 'son-monitor started'

    # stop the sdk monitoring framework
    def stop_containers(self, **kwargs):
        # docker-compose down, remove volumes
        cmd = [
            'docker-compose',
            '-p sonmonitor',
            'down',
            '-v'
        ]
        logging.info('stop and remove son-monitor containers')
        process = Popen(cmd, cwd=docker_dir)
        process.wait()
        # try to remove tmp directory
        try:
            if os.path.exists(tmp_dir):
                rmtree(tmp_dir)
        except:
            logging.info('cannot remove {0} (this is normal if mounted as a volume)'.format(tmp_dir))

        self.started = False
        return 'son-monitor stopped'

## cli parser

description = """
    Install monitor features on or get monitor data from the SONATA platform/emulator.
    """
examples = """Example usage:

    son-monitor flow_total start -src vnf1  -dst vnf2  -ma "dl_type=0x0800,nw_proto=17,udp_dst=5001"  -b -c 11 -me tx_bytes
    son-monitor query --vim emu -d datacenter1 -vnf vnf1 -q 'sum(rate(container_cpu_usage_seconds_total{id="/docker/<uuid>"}[10s]))'
    """

parser = argparse.ArgumentParser(description=description,
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog=examples)
# positional  arguments
parser.add_argument(
    "command",
    choices=['init', 'query', 'interface', 'flow_mon', 'flow_entry', 'flow_total', 'msd', 'dump', 'xterm'],
    nargs=1,
    help="""Monitoring feature to be executed:
         interface: export interface metric (tx/rx bytes/packets)
         flow_entry : (un)set the flow entry
         flow_mon : export flow_entry metric (tx/rx bytes/packets)
         flow_total : flow_entry + flow_mon
         init : start/stop the monitoring framework
         msd :  start/stop monitoring metrics from the msd (monitoring descriptor file)
         dump: start tcpdump for specified interface (save as .pcap)
         xterm: start an x-terminal for specific vnf(s)
         """)

parser.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""Action for interface, flow_mon, flow_entry, flow_total:
          start: install the flowentry and/or export the metric
          stop: delete the flowentry and/or stop exporting the metric
          Action for init:
          start: start the monitoring framework (cAdvisor, Prometheus DB + Pushgateway)
          stop: stop the monitoring framework
          Action for msd:
          start: start exporting the monitoring metrics from the msd
          stop: stop exporting the monitoring metrics from the msd
          """)
# vnf names to start an xterm for
parser.add_argument(
    "--vnf_names", "-n", dest="vnf_names",
    default="",
    nargs='*',
    help="vnf names to open an xterm for")

## select the vim to execute the monitoring action on (default=emulator)
parser.add_argument(
    "--vim", "-v", dest="vim",
    default="emu",
    help="VIM where the command should be executed (emu/sp)")

## arguments to specify a vnf
parser.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
parser.add_argument(
    "--datacenter", "-d", dest="datacenter",
    default=None,
    help="Data center where the vnf is deployed")

## arguments to deploy a vnf
parser.add_argument(
    "--image","-i", dest="image",
    help="Name of container image to be used e.g. 'ubuntu:trusty'")
parser.add_argument(
    "--dcmd", "-cmd", dest="docker_command",
    help="Startup command of the container e.g. './start.sh'")
parser.add_argument(
    "--net", dest="network",
    help="Network properties of a compute instance e.g. \
          '(id=input,ip=10.0.10.3/24),(id=output,ip=10.0.10.4/24)' for multiple interfaces.")

## arguments to query prometheus
parser.add_argument(
    "--query", "-q", dest="query",
    help="prometheus query")

## arguments specific for vnf profiling
parser.add_argument(
    "--input", "-in", dest="input",
    help="input interface of the vnf to profile")
parser.add_argument(
    "--output", "-out", dest="output",
    help="output interface of the vnf to profile")

## arguments specific for metric/flow installing
parser.add_argument(
    "--source", "-src", dest="source",
    help="vnf name:interface of the source of the chain")
parser.add_argument(
    "--destination", "-dst", dest="destination",
    help="vnf name:interface of the destination of the chain")
parser.add_argument(
    "--weight", "-w", dest="weight",
    help="weight edge attribute to calculate the path")
parser.add_argument(
    "--match", "-ma", dest="match",
    help="string to specify how to match the monitored flow")
parser.add_argument(
    "--priority", "-p", dest="priority",
    help="priority of the flow match entry, installed to get counter metrics for the monitored flow.")
parser.add_argument(
    "--bidirectional", "-b", dest="bidirectional",
    action='store_false',
    help="add/remove the flow entries from src to dst and back")

## arguments specific for metric/flow monitoring
parser.add_argument(
    "--metric", "-me", dest="metric",
    default='tx_packets',
    help="tx_bytes, rx_bytes, tx_packets, rx_packets")
parser.add_argument(
    "--cookie", "-c", dest="cookie",
    help="integer value to identify this flow monitor rule")
parser.add_argument(
    "--file", "-f", dest="file",
    help="service descriptor file describing monitoring rules or pcap dump file")


monitor = sonmonitor()

# map the command and vim selections to the correct function
def _execute_command(args):
    # commands inside this class:
    sonmonitor_cmds = {'init':monitor.init}
    if args["command"][0] in sonmonitor_cmds:
        cmd = args["command"][0]
        ret = sonmonitor_cmds[cmd](**args)
        logging.debug("cmd: {0} \nreturn: {1}".format(args["command"][0], ret))

    elif args["command"] is not None:
        VIM_class = eval(args.get('vim'))
        # call the VIM class method with the same name as the command arg
        ret = getattr(VIM_class, args["command"][0])(**args)
        logging.debug("cmd: {0} \nreturn: {1}".format(args["command"][0], ret))

        pp.pprint(ret)
    else:
        logging.error("Command not implemented: {0}".format(args.get("command")))

def main():
    args = vars(parser.parse_args())

    if args is None:
        parser.print_help()
        return

    _execute_command(args)


if __name__ == "__main__":
    main()

