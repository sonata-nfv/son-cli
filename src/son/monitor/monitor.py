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
from son.monitor.son_sp import Service_Platform

import pprint
pp = pprint.PrettyPrinter(indent=2)

import logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger('son_monitor')
LOG.setLevel(level=logging.INFO)

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
SON_EMU_USER = 'vagrant'
SON_EMU_PASSW = 'vagrant'

# Monitoring manager in the SP
SP_MONITOR_API = 'http://sp.int3.sonata-nfv.eu:8000/api/v1/'
# Gatekeeper api in the SP
GK_API = 'http://sp.int3.sonata-nfv.eu:32001/api/v2/'

# local port where the streamed metrics are served to Prometheus
PROMETHEUS_STREAM_PORT = 8082

# son-access config file (initialized by son-access workspace creation)
SON_ACCESS_CONFIG_PATH = "/home/steven/.son-workspace"

# tmp directories that will be mounted in the Prometheus and Grafana Docker containers by son-emu
tmp_dir = '/tmp/son-monitor'
docker_dir = '/tmp/son-monitor/docker'
prometheus_dir = '/tmp/son-monitor/prometheus'
grafana_dir = '/tmp/son-monitor/grafana'

# Prometheus config info
prometheus_server_api = 'http://127.0.0.1:9090'
prometheus_config_path = '/tmp/son-monitor/prometheus/prometheus_sdk.yml'

class sonmonitor():

    def __init__(self):

        for dir in [docker_dir, prometheus_dir, grafana_dir]:
            if not os.path.exists(dir):
                # make local working directory
                os.makedirs(dir)

        # status of son-monitor
        self.started = False

    def init(self, args):
        LOG.info("son-monitor init")
        action = args.action
        #startup SONATA SDK environment (cAdvisor, Prometheus, PushGateway, son-emu(experimental))
        actions = {'start': self.start_containers, 'stop': self.stop_containers}
        return actions[action]()

    def query(self, args):
        #LOG.info("son-monitor query command")
        sp = args.sp
        # choose the correct query function depending on the chosen vim (emu or SP)
        if sp == 'emu':
            return self.EMU_command(args)
        else:
            return self.SP_command(args)

    # start the sdk monitoring framework (cAdvisor, Prometheus, Pushgateway, ...)
    def start_containers(self):
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
            emu = Emu(SON_EMU_API, ip=SON_EMU_IP, vm=SON_EMU_IN_VM, user=SON_EMU_USER, password=SON_EMU_PASSW)
            list1 = emu.docker_client.containers.list(filters={'status':'running', 'name':'prometheus'})
            list2 = emu.docker_client.containers.list(filters={'status': 'running', 'name': 'grafana'})
            if len(list1+list2) >= 2:
                self.started = True
                sleep(8)
            if wait_time > 5:
                return 'son-monitor not started'
            sleep(1)
            wait_time += 1
        logging.info('son-monitor started')

        return 'son-monitor started'

    # stop the sdk monitoring framework
    def stop_containers(self):
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

    # start a monitoring action on the Service Platform
    def SP_command(self, args):
        command = args.command

        SP_class = Service_Platform(export_port=PROMETHEUS_STREAM_PORT, GK_api=GK_API,
                                    monitor_api=SP_MONITOR_API,
                                    prometheus_config_path=prometheus_config_path,
                                    prometheus_server_api=prometheus_server_api,
                                    son_access_config_path=SON_ACCESS_CONFIG_PATH,
                                    platform_id=args.sp)
        # call the SP class method with the same name as the command arg
        args = vars(args)
        args['monitor'] = self
        ret = getattr(SP_class, command)(**args)
        logging.debug("cmd: {0} \nreturn: {1}".format(command, ret))
        pp.pprint(ret)
        return 'end of SP command: {}'.format(command)


    # start a monitoring action on the Emulator
    def EMU_command(self, args):
        command = args.command
        EMU_class = Emu(SON_EMU_API, ip=SON_EMU_IP, vm=SON_EMU_IN_VM, user=SON_EMU_USER, password=SON_EMU_PASSW)
        # call the EMU class method with the same name as the command arg
        args = vars(args)
        args['monitor'] = self
        ret = getattr(EMU_class, command)(**args)
        logging.debug("cmd: {0} \nreturn: {1}".format(command, ret))
        pp.pprint(ret)
        return 'end of EMU command: {}'.format(command)



monitor = sonmonitor()
## cli parser
description = """
    Install monitor features or get monitor data from the SONATA platform/emulator.
    """
examples = """General usage:
    son-monitor init
    son-monitor msd -f msd_example.yml
    son-monitor init stop
    son-monitor xterm -n vnf1 vnf2
    son-monitor dump -vnf vnf1:port0

Gathering metrics:
    son-monitor stream -sp sp2 -s demo_service -vnf vnf1 -me metric_name
    son-monitor query -vnf vnf1:port1 -me tx_packet_rate
    son-monitor query --sp emu -d datacenter1 -vnf vnf1 -q 'sum(rate(container_cpu_usage_seconds_total{id="/docker/<uuid>"}[10s]))'
    son-monitor query -sp sp2 -s sonata-service -vnf vnf1 -me vm_cpu_perc
    """

parser = argparse.ArgumentParser(description=description,
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog=examples)
parser.add_argument(
    "--verbose", "-v", dest="verbose",
    action='store_true',
    help="print extra logging")
# positional  arguments
subparsers = parser.add_subparsers(title="son-monitor subcommands",
description="""init : start/stop the monitoring framework
msd :  start/stop monitoring metrics defined in the MSD (monitoring descriptor file)
stream: stream monitored metrics from a Service Platform
query: query monitored metrics from the Service platform or the Emulator
dump: start tcpdump for specified interface (save as .pcap)
xterm: start an x-terminal for specific vnf(s)
interface: export interface metric (tx/rx bytes/packets) from the emulator network
flow : set a flow and export its metrics in the emulator network
flow_mon: export the metrics of an existing flow entry in the emulator network
""",
help="Execute one of these monitor actions")

###
# Initialize the Monitoring framework in the SDK
###
init = subparsers.add_parser('init',formatter_class=argparse.RawTextHelpFormatter,
                             description='start(default)/stop the monitoring framework')
init.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start: start the monitoring framework (cAdvisor, Prometheus DB + Pushgateway)
stop: stop the monitoring framework
""")
init.set_defaults(func=monitor.init, command='init')


###
# Install and export monitor metrics from the Emulator or the SP
###
msd = subparsers.add_parser('msd',formatter_class=argparse.RawTextHelpFormatter,
                             description='start(default)/stop monitoring metrics from the msd (monitoring descriptor file)')
msd.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start/stop monitoring metrics from the msd (monitoring descriptor file)""")
msd.add_argument(
    "--file", "-f", dest="file",
    required = True,
    help="Monitoring Service Descriptor file (MSD) describing the monitoring rules")
msd.set_defaults(func=monitor.EMU_command, command='msd')


stream_auth = subparsers.add_parser('stream',formatter_class=argparse.RawTextHelpFormatter,
                                    description="Stream monitor data from the SONATA Service Platform. (Authentication must be configured first via son-access)")
stream_auth.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start/stop streaming metrics from the SONATA Service Platform""")
stream_auth.add_argument(
    "--metric", "-me", dest="metric",
    help="SP metric")
stream_auth.add_argument(
    "--service", "-s", dest="service",
    default=None,
    help="Service name that includes the VNF to be monitored")
stream_auth.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf to be monitored")
stream_auth.add_argument(
    "--vdu", "-vdu", dest="vdu_id",
    help="vdu_id to be monitored (optional, picks the first vdu if not given)")
stream_auth.add_argument(
    "--vnfc", "-vnfc", dest="vnfc_id",
    help="vnfc_id to be monitored (optional, picks the first vnfc instance if not given)")
stream_auth.add_argument(
    "--sp", "-sp", dest="sp",
    default="sp1",
    help="Service Platform ID where the service is instantiated")
stream_auth.set_defaults(func=monitor.SP_command, command='stream_auth')


###
# Query metric values from the Prometheus database in the SDK or the SONATA Service Platform
###
query = subparsers.add_parser('query',formatter_class=argparse.RawTextHelpFormatter,
                             description="""Query monitored metrics from the Prometheus DB in the SDK or the Service Platform.
(For querying the Service Platform, Authentication must be configured first via son-access)""")
query.add_argument(
    "--sp", "-sp", dest="sp",
    default="emu",
    help="Emulator or Service Platform ID where the service is instantiated (default = emulator)")
query.add_argument(
    "--service", "-s", dest="service",
    default=None,
    help="Service in the Service Platform that includes the VNF to be monitored")
query.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf to be monitored")
query.add_argument(
    "--vdu", "-vdu", dest="vdu_id",
    help="vdu_id to be monitored in the Service Platform (optional, picks the first vdu if not given)")
query.add_argument(
    "--vnfc", "-vnfc", dest="vnfc_id",
    help="vnfc_id to be monitored in the Service Platform (optional, picks the first vnfc instance if not given)")
query.add_argument(
    "--metric", "-me", dest="metric",
    help="The metric in the SDK or SP to query")
query.add_argument(
    "--since", "-si", dest="start",
    help="Retrieve the metric values since this start time (eg. 2017-05-05T17:10:22Z)")
query.add_argument(
    "--until", "-u", dest="stop",
    help="Retrieve the metric values until this stop time (eg. 2017-05-05T17:31:11Z)")
query.add_argument(
    "--query", "-q", dest="query",
    help="raw Prometheus query for the emulator")
query.add_argument(
    "--datacenter", "-d", dest="datacenter",
    default=None,
    help="Data center where the vnf is deployed in the emulator (if not given, the datacenter will be looked up first)")
query.set_defaults(func=monitor.query, command='query')

###
# Dump the packets for a specific interface
###
dump = subparsers.add_parser('dump',formatter_class=argparse.RawTextHelpFormatter,
                             description='start tcpdump for specified interface in a separate xterm window(optionally save as .pcap)')
dump.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start/stop dumping the packets""")
dump.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
dump.add_argument(
    "--file", "-f", dest="file",
    help="Export the dumped traffic to a .pcap file")
dump.set_defaults(func=monitor.EMU_command, command='dump')

###
# Open an xterm terminal for specific VNFs
###
xterm = subparsers.add_parser('xterm',formatter_class=argparse.RawTextHelpFormatter,
                             description='start an x-terminal for specific VNF(s)')
xterm.add_argument(
    "--vnf_names", "-n", dest="vnf_names",
    default="",
    nargs='*',
    help="vnf names to open an xterm for")
xterm.set_defaults(func=monitor.EMU_command, command='xterm')

###
# Export the monitored counters from a VNF interface in the Emulator (recommendation is to do this via the MSD file)
###
interface = subparsers.add_parser('interface',formatter_class=argparse.RawTextHelpFormatter,
                             description='export an interface metric (tx/rx bytes/packets) from a VNF deployed in the emulator (The recommended way is to group all metrics into an MSD file)')
interface.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start: export the metric
            stop: stop exporting the metric""")
interface.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
interface.add_argument(
    "--metric", "-me", dest="metric",
    help="VNF metric to monitor in the emulator")
interface.set_defaults(func=monitor.EMU_command, command='monitor_interface')


###
# Export the monitored counters from an existing flow in the Emulator (recommendation is to do this via the MSD file)
###
flow_mon = subparsers.add_parser('flow_mon',formatter_class=argparse.RawTextHelpFormatter,
                              description='export a metric (tx/rx bytes/packets) of an existing flow in the emulator network (The recommended way is to group all metrics into an MSD file)')
flow_mon.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start: export the metric
stop: stop exporting the metric""")
flow_mon.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
flow_mon.add_argument(
    "--metric", "-me", dest="metric",
    help="VNF metric to monitor in the emulator")
flow_mon.add_argument(
    "--cookie", "-c", dest="cookie",
    help="integer value to identify this flow monitor rule")
flow_mon.set_defaults(func=monitor.EMU_command, command='flow_mon')


###
# Add a flow and export its monitored counters in the Emulator (recommendation is to do this via the MSD file)
###
flow = subparsers.add_parser('flow',formatter_class=argparse.RawTextHelpFormatter,
                             description='set and export a flow entry in the emulator network (The recommended way is to group all metrics into an MSD file)')
flow.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""start: install the flowentry and/or export the metric
stop: delete the flowentry and/or stop exporting the metric""")
flow.add_argument(
    "--source", "-src", dest="source",
    help="vnf name:interface of the source of the chain")
flow.add_argument(
    "--destination", "-dst", dest="destination",
    help="vnf name:interface of the destination of the chain")
flow.add_argument(
    "--weight", "-w", dest="weight",
    help="weight edge attribute to calculate the path")
flow.add_argument(
    "--match", "-ma", dest="match",
    help="string to specify how to match the monitored flow")
flow.add_argument(
    "--priority", "-p", dest="priority",
    help="priority of the flow match entry, installed to get counter metrics for the monitored flow.")
flow.add_argument(
    "--bidirectional", "-b", dest="bidirectional",
    action='store_true',
    help="add/remove the flow entries from src to dst and back")
flow.add_argument(
    "--cookie", "-c", dest="cookie",
    help="integer value to identify this flow monitor rule")
flow.add_argument(
    "--metric", "-me", dest="metric",
    help="VNF metric to monitor in the emulator")
flow.set_defaults(func=monitor.EMU_command, command='flow_total')


def main():

    args = parser.parse_args()
    print(args.func(args))

if __name__ == "__main__":
    main()

